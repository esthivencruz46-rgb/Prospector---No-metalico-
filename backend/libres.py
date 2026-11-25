"""Áreas LIBRES: tierra del Perú sin derecho minero (catastro de INGEMMET) y fuera de
toda área protegida o restringida (SERV_AREA_RESERVADA).

Todo se consulta EN VIVO a GEOCATMIN (que INGEMMET actualiza a diario): no hay una
copia local que envejezca. Dos caminos:

- `imagen()`: lámina PNG transparente de cualquier vista del mapa, con las áreas libres
  en verde. Sirve para todo el Perú a cualquier zoom: GEOCATMIN dibuja las ~68 000
  concesiones (con relleno sólido gracias a `dynamicLayers`) y las áreas reservadas, y
  aquí se hace la resta píxel por píxel.
- `en_celda()`: cálculo exacto con geometrías dentro de UNA cuadrícula (ha, %, lista de
  derechos mineros con titular y estado).

Referencial: antes de pedir un petitorio, confirmar en GEOCATMIN / INGEMMET.
"""

from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from io import BytesIO
from math import log, pi, tan

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from shapely.geometry import Polygon, box, mapping
from shapely.ops import unary_union

import geocatmin_rmi as g
import restricciones as restr

CATASTRO = "SERV_CATASTRO_MINERO_WGS84"
CAPAS_CATASTRO = (0, 1)          # 0 = catastro de INGEMMET · 1 = derechos de la DGM (MINEM)
CAMPOS_CATASTRO = "CODIGOU,CONCESION,TIT_CONCES,LEYENDA,SUSTANCIA,HECTAGIS,FEC_DENU,FECHA_ACTUALIZACION"
ESTADOS = {
    "TITULADO": "titulado", "TRAMITE": "en trámite", "EXTINGUIDO": "extinguido (aún no de libre denunciabilidad)",
    "OTROS": "beneficio / cantera del Estado", "BLOQUEADO": "bloqueado", "CONSENTIDO": "extinción sin consentir",
}
NOTA = ("Libre = sin derecho minero vigente ni en trámite y fuera de áreas protegidas o restringidas. "
        "Datos en vivo de GEOCATMIN (INGEMMET los actualiza a diario); confirmar antes de pedir un petitorio.")

NOTA_POR_LIBERARSE = ("Incluye derechos mineros EXTINGUIDOS (gris en GEOCATMIN): ya no tienen titular, pero solo se "
                      "pueden pedir cuando INGEMMET publique su libre denunciabilidad. Vigilar la publicación.")

# Capas de áreas reservadas que INGEMMET rellena con trama o solo con borde: en la lámina
# de imagen se dibujan con su geometría (las de relleno sólido salen del export).
_RESERVA_TRAMA = [c for c in restr.CAPAS_MAPA if c in (3, 8, 14, 16)]
_RESERVA_SOLIDA = [c for c in restr.CAPAS_MAPA if c not in _RESERVA_TRAMA]

_VERDE = (22, 197, 94, 165)
# CONCESIÓN TITULADA o EN TRÁMITE fuera de áreas protegidas y apta para cantera (pedido del usuario, 23/11/2026):
# no es libre, pero se puede NEGOCIAR con el titular (compra, cesión, opción, contrato de explotación).
_INDIGO = (129, 140, 248, 150)
NEGOCIABLES = ("TITULADO", "TRAMITE")
NOTA_NEGOCIABLE = ("Concesionado negociable = derecho minero TITULADO o EN TRÁMITE, fuera de áreas protegidas o "
                   "restringidas y apto para cantera: no se puede pedir, pero sí negociar con el titular (compra, "
                   "cesión, opción o contrato de explotación). Un petitorio en trámite aún no es concesión.")
_MAX_LADO = 2048


# ------------------------------------------------------------ cachés de 24 h
_cache: dict[str, tuple[float, object]] = {}
_candado = threading.Lock()


def _cacheado(clave: str, horas: float, fn):
    with _candado:
        v = _cache.get(clave)
        if v and time.time() - v[0] < horas * 3600:
            return v[1]
    r = fn()
    with _candado:
        _cache[clave] = (time.time(), r)
    return r


def contorno_peru():
    """Contorno del Perú (SERV_CARTOGRAFIA_BASE_WGS84/23), generalizado a ~100 m."""
    def bajar():
        j = g._get(f"{g.BASE}/SERV_CARTOGRAFIA_BASE_WGS84/MapServer/23/query",
                   {"where": "1=1", "returnGeometry": "true", "outSR": 4326, "maxAllowableOffset": 0.001,
                    "geometryPrecision": 5, "outFields": "OBJECTID", "f": "json"}, timeout=90)
        geoms = [g.esri_a_shapely(f.get("geometry")) for f in j.get("features") or []]
        return unary_union([x for x in geoms if x is not None and not x.is_empty])
    return _cacheado("peru", 24 * 7, bajar)


def _reservas_trama():
    """Geometrías (de todo el Perú) de las capas reservadas con trama: son pocas (~600)."""
    def bajar():
        out = []
        for lid in _RESERVA_TRAMA:
            try:
                j = g._post(f"{g.BASE}/{restr.SERVICIO}/MapServer/{lid}/query",
                            {"where": "1=1", "returnGeometry": "true", "outSR": 4326, "maxAllowableOffset": 0.0003,
                             "geometryPrecision": 5, "outFields": "OBJECTID", "f": "json"}, 60)
            except Exception:  # noqa: BLE001
                continue
            for f in j.get("features") or []:
                s = g.esri_a_shapely(f.get("geometry"))
                if s is not None and not s.is_empty:
                    out.append(s)
        return out
    return _cacheado("reservas_trama", 24, bajar)


# ---------------------------------------------------------------- IMAGEN
def _merc(lon: float, lat: float) -> tuple[float, float]:
    r = 6378137.0
    return r * lon * pi / 180, r * log(tan(pi / 4 + lat * pi / 360))


def _export(servicio: str, bbox3857: tuple, tam: tuple[int, int], **extra) -> np.ndarray | None:
    """Canal alfa (0/1) de un export de GEOCATMIN en Web Mercator."""
    try:
        r = g._SES.get(f"{g.BASE}/{servicio}/MapServer/export", params={
            "bbox": ",".join(f"{v:.2f}" for v in bbox3857), "bboxSR": 3857, "imageSR": 3857,
            "size": f"{tam[0]},{tam[1]}", "format": "png32", "transparent": "true", "dpi": 96, "f": "image", **extra,
        }, timeout=60)
        r.raise_for_status()
        if not r.headers.get("Content-Type", "").startswith("image"):
            return None
        im = Image.open(BytesIO(r.content)).convert("RGBA")
        if im.size != tam:
            im = im.resize(tam, Image.NEAREST)
        return np.asarray(im.getchannel("A")) > 0
    except Exception:  # noqa: BLE001
        return None


def _relleno_solido(capas, where: str | None = None) -> str:
    sim = {"type": "esriSFS", "style": "esriSFSSolid", "color": [0, 0, 0, 255],
           "outline": {"type": "esriSLS", "style": "esriSLSSolid", "color": [0, 0, 0, 255], "width": 0.6}}
    return json.dumps([{"id": c, "source": {"type": "mapLayer", "mapLayerId": c},
                        **({"definitionExpression": where} if where else {}),
                        "drawingInfo": {"renderer": {"type": "simple", "symbol": sim}, "showLabels": False}}
                       for c in capas])


def _limpiar_etiquetas(m: np.ndarray) -> np.ndarray:
    """Apertura 3×3: quita textos y bordes finos del export de áreas reservadas
    (INGEMMET dibuja sus nombres encima), deja los rellenos."""
    im = Image.fromarray((m * 255).astype(np.uint8))
    im = im.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))
    return np.asarray(im) > 0


def imagen(oeste: float, sur: float, este: float, norte: float, ancho: int, alto: int, modo: str = "mapa") -> bytes:
    """Con caché de 1 h por vista (INGEMMET actualiza el catastro a diario). `modo`: «mapa» (capa Áreas libres) o
    «prioridad» (colores de la Prioridad libre: verde libre · azul concesión titulada/en trámite · amarillo chacra,
    poblado, vía o río · celeste extinguido; lo protegido y las demás concesiones, transparente)."""
    modo = "prioridad" if modo == "prioridad" else "mapa"
    clave = f"img:{modo}:{oeste:.4f},{sur:.4f},{este:.4f},{norte:.4f},{ancho},{alto}"
    with _candado:   # que la caché de vistas no crezca sin límite
        viejas = [k for k, v in _cache.items() if k.startswith("img:") and time.time() - v[0] > 3600]
        for k in viejas:
            del _cache[k]
    return _cacheado(clave, 1, lambda: _imagen(oeste, sur, este, norte, ancho, alto, modo))


# Uso del suelo que impide una cantera aunque el terreno esté legalmente libre.
# Cobertura Sentinel-2 10 m de Esri/Impact Observatory (clase por píxel, un mapa por año).
COBERTURA = os.environ.get("COBERTURA_URL", "https://ic.imagery1.arcgis.com/arcgis/rest/services/Sentinel2_10m_LandCover/ImageServer")
CLASES_NO_APTAS = {1: "agua", 4: "agua", 5: "cultivo", 7: "urbano", 9: "agua"}  # 4 = vegetación inundada, 9 = nieve/hielo
# Franjas (m a cada lado) alrededor de vías, ríos y centros poblados de la cartografía base de
# GEOCATMIN. Referenciales: derecho de vía (MTC), faja marginal (ANA) y distancia prudente a viviendas.
FRANJAS = {
    "vias": [(1, 50), (2, 25), (3, 15)],             # vía nacional, departamental, vecinal
    "rios": [(14, 50), (15, 25), (16, 25), (17, 25), (18, 25)],  # ríos (líneas y polígonos) y lagunas
    "poblados": [(12, 300)],                        # centros poblados (radio)
}
MOTIVOS = {"cultivo": "chacras / cultivos", "urbano": "zona construida", "agua": "agua, bofedal o nieve",
           "vias": "franja de carreteras", "rios": "faja de ríos y lagunas", "poblados": "cerca de un centro poblado"}
_AMBAR = (245, 158, 11, 70)
_CELESTE = (56, 189, 248, 175)
# colores de la PRIORIDAD LIBRE (modo «prioridad»); el frontend (prioridadLibre.ts) los reconoce: mantener iguales
PRIO_VERDE = (22, 197, 94, 255)      # libre y utilizable
PRIO_AZUL = (37, 99, 235, 255)       # concesión titulada o en trámite (fuera de áreas protegidas)
PRIO_AMARILLO = (250, 204, 21, 255)  # libre pero chacra, zona construida, agua, vía, río o centro poblado
PRIO_CELESTE = (125, 211, 252, 255)  # derecho extinguido (libre cuando INGEMMET publique la libre denunciabilidad)


def _anio_cobertura() -> tuple[str, int]:
    """Parámetro `time` del último año publicado de la cobertura (se consulta una vez al día)."""
    def leer():
        j = g._SES.get(COBERTURA, params={"f": "json"}, timeout=30).json()
        fin = int(j["timeInfo"]["timeExtent"][1])
        anio = datetime.fromtimestamp(fin / 1000, tz=timezone.utc).year
        ini = int(datetime(anio, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
        return f"{ini},{fin}", anio
    return _cacheado("anio_cobertura", 24, leer)


# Respaldo de la cobertura: ESA WorldCover 10 m 2021 (COG público en AWS, sin cuenta; necesita
# `rasterio`). Sus clases se traducen a las de Esri para reutilizar CLASES_NO_APTAS.
# COBERTURA_FUENTE=worldcover lo fuerza (el censo nacional lo usa para medir todo igual).
WORLDCOVER = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{t}_Map.tif"
_WC_A_ESRI = {80: 1, 90: 4, 70: 9, 40: 5, 50: 7}   # agua, humedal, nieve, cultivo, construido
_esri_caido_hasta = 0.0                              # tras una falla, 10 min sin volver a esperar a Esri


def _cobertura_esri(bb: tuple, tam: tuple[int, int]) -> np.ndarray | None:
    tiempo, _ = _anio_cobertura()
    r = g._SES.get(f"{COBERTURA}/exportImage", params={
        "bbox": ",".join(f"{v:.2f}" for v in bb), "bboxSR": 3857, "imageSR": 3857, "size": f"{tam[0]},{tam[1]}",
        "format": "png", "pixelType": "U8", "interpolation": "RSP_NearestNeighbor", "time": tiempo,
        "renderingRule": json.dumps({"rasterFunction": "None"}), "f": "image"}, timeout=(6, 60))
    r.raise_for_status()
    if not r.headers.get("Content-Type", "").startswith("image"):
        return None
    a = np.asarray(Image.open(BytesIO(r.content)))
    if a.ndim == 3:
        a = a[..., 0]
    if a.shape != (tam[1], tam[0]):
        a = np.asarray(Image.fromarray(a).resize(tam, Image.NEAREST))
    return a


def _cobertura_worldcover(bb: tuple, tam: tuple[int, int]) -> np.ndarray | None:
    import math

    import rasterio
    from rasterio.enums import Resampling
    from rasterio.transform import from_bounds
    from rasterio.vrt import WarpedVRT

    os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
    # sin esto GDAL espera para siempre si AWS deja colgada una conexión (el censo se trabó así)
    os.environ.setdefault("GDAL_HTTP_TIMEOUT", "30")
    os.environ.setdefault("GDAL_HTTP_CONNECTTIMEOUT", "10")
    os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "3")
    os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")
    r = 6378137.0
    lon0, lon1 = bb[0] / r * 180 / pi, bb[2] / r * 180 / pi
    lat0 = math.degrees(2 * math.atan(math.exp(bb[1] / r)) - pi / 2)
    lat1 = math.degrees(2 * math.atan(math.exp(bb[3] / r)) - pi / 2)
    out = np.zeros((tam[1], tam[0]), np.uint8)
    tr = from_bounds(*bb, tam[0], tam[1])
    for la in range(math.floor(lat0 / 3) * 3, math.floor(lat1 / 3) * 3 + 1, 3):
        for lo in range(math.floor(lon0 / 3) * 3, math.floor(lon1 / 3) * 3 + 1, 3):
            t = f"{'S' if la < 0 else 'N'}{abs(la):02d}{'W' if lo < 0 else 'E'}{abs(lo):03d}"
            try:
                with rasterio.open(WORLDCOVER.format(t=t)) as src, WarpedVRT(
                        src, crs="EPSG:3857", transform=tr, width=tam[0], height=tam[1],
                        resampling=Resampling.nearest, nodata=0) as vrt:
                    x = vrt.read(1)
            except Exception:  # noqa: BLE001  (mosaico de puro océano: no existe)
                continue
            out = np.where(out == 0, x, out)
    if not out.any():
        return None
    esri = np.zeros_like(out)
    for wc, e in _WC_A_ESRI.items():
        esri[out == wc] = e
    return esri


def _cobertura(bb: tuple, tam: tuple[int, int]) -> tuple[np.ndarray | None, str | None]:
    """(clases tipo Esri, fuente). Esri (año más reciente) y, si no responde, ESA WorldCover 2021."""
    global _esri_caido_hasta
    if os.environ.get("COBERTURA_FUENTE", "").lower() != "worldcover" and time.time() > _esri_caido_hasta:
        try:
            a = _cobertura_esri(bb, tam)
            if a is not None:
                return a, f"Esri / Impact Observatory {_anio_cobertura()[1]}"
        except Exception:  # noqa: BLE001
            pass
        _esri_caido_hasta = time.time() + 600
    if "ic.imagery1" not in COBERTURA:      # en las pruebas (servidor simulado) no hay respaldo
        return None, None
    try:
        a = _cobertura_worldcover(bb, tam)
        return (a, "ESA WorldCover 2021") if a is not None else (None, None)
    except Exception:  # noqa: BLE001
        return None, None


def _franjas(capas_m: list[tuple[int, float]], m_por_px: float) -> str:
    """dynamicLayers con el ancho de línea (o tamaño de punto) en PUNTOS = franja en metros
    convertida a píxeles de esta vista (1 px = 0,75 pt a 96 dpi)."""
    out = []
    for lid, m in capas_m:
        px = max(1.0, 2 * m / m_por_px)
        pt = round(px * 0.75, 2)
        if lid == 12:
            sim = {"type": "esriSMS", "style": "esriSMSCircle", "color": [0, 0, 0, 255], "size": pt}
        elif lid in (17, 18):
            sim = {"type": "esriSFS", "style": "esriSFSSolid", "color": [0, 0, 0, 255],
                   "outline": {"type": "esriSLS", "style": "esriSLSSolid", "color": [0, 0, 0, 255], "width": pt}}
        else:
            sim = {"type": "esriSLS", "style": "esriSLSSolid", "color": [0, 0, 0, 255], "width": pt}
        out.append({"id": lid, "source": {"type": "mapLayer", "mapLayerId": lid},
                    "drawingInfo": {"renderer": {"type": "simple", "symbol": sim}, "showLabels": False}})
    return json.dumps(out)


class Lienzo:
    """Rasteriza geometrías WGS84 en la grilla Web Mercator de una vista."""
    def __init__(self, oeste, sur, este, norte, ancho, alto):
        self.x0, self.y0 = _merc(oeste, sur)
        self.x1, self.y1 = _merc(este, norte)
        self.tam = (ancho, alto)
        self.sx, self.sy = ancho / (self.x1 - self.x0), alto / (self.y1 - self.y0)
        self.bb = (self.x0, self.y0, self.x1, self.y1)
        # metros reales por píxel (Mercator exagera por 1/cos(lat))
        self.m_por_px = (self.x1 - self.x0) / ancho * np.cos(np.radians((sur + norte) / 2))

    def __call__(self, geoms) -> np.ndarray:
        lienzo = Image.new("L", self.tam, 0)
        d = ImageDraw.Draw(lienzo)

        def px(lon, lat):
            mx, my = _merc(lon, max(min(lat, 85), -85))
            return (mx - self.x0) * self.sx, (self.y1 - my) * self.sy

        for s in geoms:
            if s is None or s.is_empty:
                continue
            for p in getattr(s, "geoms", [s]):
                if p.geom_type != "Polygon" or len(p.exterior.coords) < 3:
                    continue
                d.polygon([px(*c[:2]) for c in p.exterior.coords], fill=255)
                for h in p.interiors:
                    d.polygon([px(*c[:2]) for c in h.coords], fill=0)
        return np.asarray(lienzo) > 0


def mascaras(oeste: float, sur: float, este: float, norte: float, ancho: int, alto: int,
             legal: bool = True) -> dict[str, np.ndarray]:
    """Máscaras booleanas (alto × ancho) de una vista: «tierra», «ocupado» (derecho minero o área
    protegida/restringida; solo con legal=True) y una por cada motivo de MOTIVOS."""
    lz = Lienzo(oeste, sur, este, norte, ancho, alto)
    bb, tam = lz.bb, lz.tam
    vista = box(oeste, sur, este, norte)
    try:
        peru = contorno_peru()
    except Exception:  # noqa: BLE001
        peru = None
    base = "SERV_CARTOGRAFIA_BASE_WGS84"
    with ThreadPoolExecutor(8) as ex:
        f = {
            "tierra": ex.submit(_export, base, bb, tam, dynamicLayers=_relleno_solido([23])),
            "cobertura": ex.submit(_cobertura, bb, tam),
            **{k: ex.submit(_export, base, bb, tam, dynamicLayers=_franjas(v, lz.m_por_px)) for k, v in FRANJAS.items()},
        }
        if legal:
            # derechos que ocupan el área (todo menos extinguidos) y extinguidos por separado
            f["cat"] = ex.submit(_export, CATASTRO, bb, tam,
                                 dynamicLayers=_relleno_solido(CAPAS_CATASTRO, "LEYENDA IS NULL OR LEYENDA <> 'EXTINGUIDO'"))
            f["ext"] = ex.submit(_export, CATASTRO, bb, tam, dynamicLayers=_relleno_solido(CAPAS_CATASTRO, "LEYENDA = 'EXTINGUIDO'"))
            f["neg"] = ex.submit(_export, CATASTRO, bb, tam, dynamicLayers=_relleno_solido(
                CAPAS_CATASTRO, "LEYENDA IN (" + ",".join(f"'{x}'" for x in NEGOCIABLES) + ")"))
            f["res"] = ex.submit(_export, restr.SERVICIO, bb, tam, layers="show:" + ",".join(map(str, _RESERVA_SOLIDA)))
            f["trama"] = ex.submit(_reservas_trama)
            svc_for, lid_for, where_for = restr.FORESTAL
            f["forestal"] = ex.submit(_export, svc_for, bb, tam, dynamicLayers=_relleno_solido([lid_for], where_for))
        r = {k: v.result() if k != "trama" else None for k, v in f.items()}  # noqa: E501
        if legal:
            try:
                r["trama"] = f["trama"].result()
            except Exception:  # noqa: BLE001
                r["trama"] = []
    vacio = np.zeros((alto, ancho), dtype=bool)
    out: dict[str, np.ndarray] = {}
    tierra = r["tierra"]
    # la capa «Perú» de GEOCATMIN solo se dibuja a escala mayor que 1:1 000 000:
    # con la vista más alejada se usa el contorno en caché
    if (tierra is None or not tierra.any()) and peru is not None:
        tierra = lz([peru.intersection(vista.buffer(0.05))])
    out["tierra"] = tierra if tierra is not None else vacio
    if legal:
        if r["cat"] is None or r["res"] is None:
            # sin alguno de los dos no se puede afirmar que algo está libre
            raise RuntimeError("GEOCATMIN no respondió (catastro o áreas reservadas).")
        if r["forestal"] is None:
            raise RuntimeError("GEOCATMIN no respondió (catastro forestal).")
        reservado = _limpiar_etiquetas(r["res"]) | r["forestal"]
        out["extinguido"] = r["ext"] if r["ext"] is not None else np.zeros((alto, ancho), dtype=bool)
        cerca = [s for s in r["trama"] if s.intersects(vista)]
        if cerca:
            reservado |= lz(cerca)
        out["ocupado"] = r["cat"] | reservado
        # titulados y en trámite FUERA de áreas reservadas: negociables con el titular
        neg = r["neg"] if r["neg"] is not None else np.zeros((alto, ancho), dtype=bool)
        out["negociable"] = neg & ~reservado
    cob, fuente_cob = r["cobertura"]
    for motivo in ("cultivo", "urbano", "agua"):
        if cob is None:
            out[motivo] = vacio
            continue
        m = np.isin(cob, [k for k, v in CLASES_NO_APTAS.items() if v == motivo])
        if motivo == "urbano" and m.any():   # un píxel de margen alrededor de lo construido
            m = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))) > 0
        out[motivo] = m
    for k in FRANJAS:
        out[k] = r[k] if r[k] is not None else vacio
    out["_sin_cobertura"] = cob is None
    out["_fuente_cobertura"] = fuente_cob
    return out


def _imagen(oeste: float, sur: float, este: float, norte: float, ancho: int, alto: int, modo: str = "mapa") -> bytes:
    if not (-90 < sur < norte < 90 and -180 < oeste < este < 180):
        raise ValueError("Recuadro inválido.")
    ancho, alto = max(16, min(int(ancho), _MAX_LADO)), max(16, min(int(alto), _MAX_LADO))
    tam = (ancho, alto)
    try:
        peru = contorno_peru()
    except Exception:  # noqa: BLE001
        peru = None
    if peru is not None and not peru.intersects(box(oeste, sur, este, norte)):
        return _png_vacio(tam)
    m = mascaras(oeste, sur, este, norte, ancho, alto)
    no_apto = np.zeros_like(m["tierra"])
    for k in MOTIVOS:
        no_apto |= m[k]
    libre_legal = m["tierra"] & ~m["ocupado"]
    rgba = np.zeros((alto, ancho, 4), dtype=np.uint8)
    util = libre_legal & ~no_apto
    if modo == "prioridad":
        rgba[libre_legal & no_apto] = PRIO_AMARILLO
        rgba[util & ~m["extinguido"]] = PRIO_VERDE
        rgba[util & m["extinguido"]] = PRIO_CELESTE
        rgba[m["tierra"] & m["negociable"] & ~libre_legal] = PRIO_AZUL   # también sobre chacras: manda el derecho minero
        out = BytesIO()
        Image.fromarray(rgba, "RGBA").save(out, "PNG", optimize=True)
        return out.getvalue()
    rgba[libre_legal & no_apto] = _AMBAR                  # libre en papel, pero chacra, pueblo, vía o río
    rgba[util & ~m["extinguido"]] = _VERDE                # libre y utilizable
    rgba[util & m["extinguido"]] = _CELESTE               # extinguido: libre cuando INGEMMET publique la L.D.
    rgba[m["tierra"] & m["negociable"] & ~libre_legal & ~no_apto] = _INDIGO   # titulado / en trámite: negociable
    out = BytesIO()
    Image.fromarray(rgba, "RGBA").save(out, "PNG", optimize=True)
    return out.getvalue()

def _png_vacio(tam) -> bytes:
    out = BytesIO()
    Image.new("RGBA", tam, (0, 0, 0, 0)).save(out, "PNG")
    return out.getvalue()


# ----------------------------------------------------------- POR CUADRÍCULA
def _fecha(ms) -> str | None:
    try:
        return datetime.fromtimestamp(float(ms) / 1000, tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError):
        return None


def concesiones(pol: Polygon) -> list[dict]:
    """Derechos mineros que tocan el polígono (ambas capas del catastro) con su ficha completa
    (concesiones_info.ficha + REINFO, UEA, pasivos, certificaciones) y su geometría recortada en «_geom»."""
    import concesiones_info as ci
    anillo = g._anillo_esri(pol)
    area_total = max(g.area_ha(pol), 1e-9)

    def una(lid):
        # «*»: la capa 1 (DGM) no tiene todos los campos de la 0
        return [(lid, f) for f in g.query_en_poligono(CATASTRO, lid, anillo, "*", timeout=40)]

    with ThreadPoolExecutor(3) as ex:
        f_extra = ex.submit(ci.descargar, pol)
        feats = [x for r in ex.map(una, CAPAS_CATASTRO) for x in r]
        extra = f_extra.result()
    vistos: dict[str, dict] = {}
    for lid, f in feats:
        geom = g.esri_a_shapely(f.get("geometry"))
        if geom is None or geom.is_empty:
            continue
        inter = g._limpiar(geom.intersection(pol))
        if inter is None or inter.is_empty:
            continue
        a = f.get("attributes") or {}
        codigo = str(a.get("CODIGOU") or "").strip() or f"{lid}-{len(vistos)}"
        if codigo in vistos:      # el mismo derecho puede venir en las dos capas
            continue
        ha = g.area_ha(inter)
        vistos[codigo] = {
            **ci.ficha({**a, "CODIGOU": codigo}),
            "ha_en_cuadricula": round(ha, 1), "pct_cuadricula": round(100 * ha / area_total, 1),
            "_actualizado": a.get("FECHA_ACTUALIZACION"), "_geom": inter,
            "_extinguido": str(a.get("LEYENDA") or "").strip().upper() == "EXTINGUIDO",
            "_negociable": str(a.get("LEYENDA") or "").strip().upper() in NEGOCIABLES,
        }
    cons = sorted(vistos.values(), key=lambda c: -c["ha_en_cuadricula"])
    ci.enriquecer(pol, cons, extra)
    return cons

def en_celda(pol: Polygon, areas: list[dict] | None = None) -> dict:
    """Cuánto de la cuadrícula está libre (sin derecho minero y fuera de áreas
    protegidas/restringidas). `areas` = resultado de restricciones.consultar (si ya se tiene)."""
    with ThreadPoolExecutor(2) as ex:
        f_con = ex.submit(concesiones, pol)
        f_res = ex.submit(restr.consultar, pol) if areas is None else None
        cons = f_con.result()
        if f_res is not None:
            areas = f_res.result()
    return calcular(pol, cons, areas or [])


def calcular(pol: Polygon, cons: list[dict], areas: list[dict]) -> dict:
    """Resta: tierra de la cuadrícula − derechos mineros − áreas protegidas/restringidas."""
    try:
        peru = contorno_peru()
    except Exception:  # noqa: BLE001
        peru = None
    tierra = g._limpiar(pol.intersection(peru)) if peru is not None else pol
    if tierra is None or tierra.is_empty:
        tierra = pol
    ha_tierra = max(g.area_ha(tierra), 1e-9)
    # Titulados, en trámite, canteras del Estado, bloqueados… ocupan el área. Los EXTINGUIDOS no:
    # cuentan como libres, pero «con observación» (falta que INGEMMET publique su libre denunciabilidad).
    activos = [c for c in cons if not c.get("_extinguido")]
    extinguidos = [c for c in cons if c.get("_extinguido")]
    u_con = unary_union([c["_geom"] for c in activos]) if activos else None
    u_ext = unary_union([c["_geom"] for c in extinguidos]) if extinguidos else None
    u_res = unary_union([a["_geom"] for a in areas]) if areas else None
    libre = tierra
    for u in (u_con, u_res):
        if u is not None and not u.is_empty:
            libre = g._limpiar(libre.difference(u.buffer(0)))
            if libre is None:
                break
    ha_libre = g.area_ha(libre) if libre is not None and not libre.is_empty else 0.0
    ha_con = g.area_ha(g._limpiar(u_con.intersection(tierra))) if u_con is not None else 0.0
    ha_res = g.area_ha(g._limpiar(u_res.intersection(tierra))) if u_res is not None else 0.0
    por_liberarse = (g._limpiar(libre.intersection(u_ext.buffer(0)))
                     if u_ext is not None and libre is not None and not libre.is_empty else None)
    ha_pl = g.area_ha(por_liberarse) if por_liberarse is not None else 0.0
    # titulados / en trámite fuera de áreas protegidas o restringidas: negociables con el titular
    negs = [c for c in cons if c.get("_negociable")]
    negociable = None
    if negs:
        negociable = g._limpiar(tierra.intersection(unary_union([c["_geom"] for c in negs]).buffer(0)))
        if negociable is not None and u_res is not None and not u_res.is_empty:
            negociable = g._limpiar(negociable.difference(u_res.buffer(0)))
    ha_neg = g.area_ha(negociable) if negociable is not None and not negociable.is_empty else 0.0

    fechas = [c["_actualizado"] for c in cons if c.get("_actualizado")]
    uso = _uso_en_celda(pol, libre, ha_tierra, negociable)
    return {
        "consultado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "catastro_actualizado": _fecha(max(fechas)) if fechas else None,
        "ha_tierra": round(ha_tierra, 1),
        "libre_ha": round(ha_libre, 1), "libre_pct": round(100 * ha_libre / ha_tierra, 1),
        "concesiones_ha": round(ha_con, 1), "concesiones_pct": round(100 * ha_con / ha_tierra, 1),
        "protegido_ha": round(ha_res, 1), "protegido_pct": round(100 * ha_res / ha_tierra, 1),
        "por_liberarse_ha": round(ha_pl, 1), "por_liberarse_pct": round(100 * ha_pl / ha_tierra, 1),
        "nota_por_liberarse": (NOTA_POR_LIBERARSE if ha_pl >= 0.5 else None),
        "negociable_ha": round(ha_neg, 1), "negociable_pct": round(100 * ha_neg / ha_tierra, 1),
        "nota_negociable": NOTA_NEGOCIABLE if ha_neg >= 0.5 else None,
        "_negociable": negociable,
        "n_concesiones": len(cons),
        "concesiones": [{k: v for k, v in c.items() if not k.startswith("_")} for c in cons],
        "geometria": mapping(libre.simplify(0.00005)) if libre is not None and not libre.is_empty else None,
        "nota": NOTA,
        "_libre": libre,
        **uso,
    }


def _uso_en_celda(pol: Polygon, libre, ha_tierra: float, negociable=None) -> dict:
    """De lo legalmente libre, cuánto es utilizable para una cantera (sin chacras, zonas
    construidas, agua, franjas de vías y ríos, ni cercanía a centros poblados). Por píxeles de ~20 m."""
    oeste, sur, este, norte = pol.bounds
    x0, y0 = _merc(oeste, sur)
    x1, y1 = _merc(este, norte)
    m_merc = 20 / np.cos(np.radians((sur + norte) / 2))
    ancho = int(min(max((x1 - x0) / m_merc, 64), 1500))
    alto = int(min(max((y1 - y0) / m_merc, 64), 1500))
    try:
        m = mascaras(oeste, sur, este, norte, ancho, alto, legal=False)
    except Exception:  # noqa: BLE001
        return {"util_pct": None, "util_ha": None, "no_apto": None, "negociable_util_ha": None, "negociable_util_pct": None}
    lz = Lienzo(oeste, sur, este, norte, ancho, alto)
    celda = lz([pol])
    ha_px = g.area_ha(pol) / max(int(celda.sum()), 1)
    lib = lz([libre]) & celda if libre is not None and not libre.is_empty else np.zeros_like(celda)
    no_apto = np.zeros_like(celda)
    perdido = {}
    for k in MOTIVOS:
        no_apto |= m[k]
        perdido[k] = round(float((lib & m[k]).sum()) * ha_px, 1)
    util = lib & ~no_apto
    ha_util = float(util.sum()) * ha_px
    neg = (lz([negociable]) & celda & ~no_apto) if negociable is not None and not negociable.is_empty else np.zeros_like(celda)
    ha_neg_util = float(neg.sum()) * ha_px
    fuente = m.get("_fuente_cobertura")
    anio = int(fuente[-4:]) if fuente and fuente[-4:].isdigit() else None
    return {
        "util_ha": round(ha_util, 1), "util_pct": round(100 * ha_util / ha_tierra, 1),
        # concesionado negociable y apto para cantera
        "negociable_util_ha": round(ha_neg_util, 1), "negociable_util_pct": round(100 * ha_neg_util / ha_tierra, 1),
        "_neg_util": neg,
        "no_apto": [{"motivo": k, "texto": MOTIVOS[k], "ha": v} for k, v in
                    sorted(perdido.items(), key=lambda kv: -kv[1]) if v >= 0.5],
        "cobertura_anio": anio,
        "cobertura_fuente": fuente,
        "nota_uso": ("Utilizable = libre y sin chacras, zonas construidas, agua, franja de carreteras "
                     f"(50/25/15 m), faja de ríos y lagunas (25–50 m) ni a menos de 300 m de un centro poblado. "
                     + (f"Cobertura del suelo 10 m: {fuente}." if fuente
                        else "SIN cobertura del suelo (el servicio no respondió): chacras, zonas construidas y agua NO se descontaron.")),
        "_util": util, "_lienzo": lz,
    }


def publico(r: dict | None) -> dict | None:
    return None if r is None else {k: v for k, v in r.items() if not k.startswith("_")}


def util_en_zona(libres: dict | None, geom) -> float | None:
    """% de una zona favorable libre Y utilizable (sin chacras, pueblos, vías, ríos)."""
    if not libres or geom is None or geom.is_empty or libres.get("_util") is None:
        return None
    lz: Lienzo = libres["_lienzo"]
    z = lz([geom])
    n = int(z.sum())
    if n == 0:
        return None
    return round(100 * float((z & libres["_util"]).sum()) / n, 1)


def negociable_en_zona(libres: dict | None, geom) -> float | None:
    """% de una zona favorable sobre concesión titulada / en trámite, apta para cantera (negociable)."""
    if not libres or geom is None or geom.is_empty or libres.get("_neg_util") is None:
        return None
    lz: Lienzo = libres["_lienzo"]
    z = lz([geom])
    n = int(z.sum())
    if n == 0:
        return None
    return round(100 * float((z & libres["_neg_util"]).sum()) / n, 1)


def libre_en_zona(libres: dict | None, geom) -> float | None:
    """% de una zona favorable que está libre (legalmente)."""
    if not libres or geom is None or geom.is_empty:
        return None
    lib = libres.get("_libre")
    if lib is None or lib.is_empty:
        return 0.0
    return round(100 * g.area_ha(g._limpiar(lib.intersection(geom)) or Polygon()) / max(g.area_ha(geom), 1e-9), 1)
