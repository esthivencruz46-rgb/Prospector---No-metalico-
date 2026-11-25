"""Índices Sentinel-2 de "limpieza" de arena silícea sobre el área dibujada
— adaptado de MineLINK/backend/copernicus.py (mismas credenciales CDSE,
misma colección L2A, mismo mosaico de menor nubosidad en 18 meses).

QUÉ MIDE Y QUÉ NO (para no prometer de más):
Sentinel-2 no tiene bandas térmicas, así que NO detecta cuarzo de forma
directa (eso solo lo da el laboratorio). Lo que sí mide es si un afloramiento
cuarzoso está "limpio", que es lo que importa para vidrio:

- Óxidos de hierro férrico  B04/B02   (alto = arena rojiza/manchada → malo)
- Arcillas / OH             B11/B12   (alto = matriz arcillosa → malo)
- Brillo                    media(B02,B03,B04,B11) (alto = roca/arena clara → bueno)
- NDVI                      (B08-B04)/(B08+B04)   (vegetación: se enmascara)

Hierro (férrico B4/B2 + ferroso B11/B8A) y arcillas (B11/B12) se marcan desde
el percentil que elige el usuario (P1–P100), solo sobre los píxeles válidos
(sin nube, agua, sombra ni vegetación). Es RELATIVO a la cuadrícula y sirve
para DESCARTAR: no es una ley de SiO2. Lo que queda de las zonas A/B es la
«Sílice limpia», que la app cruza con las áreas libres (Prioridad libre).

UNA sola petición (7 bandas FLOAT32) por análisis — más barato que una
petición por índice como en MineLINK. Desactivado si faltan
CDSE_CLIENT_ID / CDSE_CLIENT_SECRET.
"""

from __future__ import annotations

import base64
import os
from datetime import date
from io import BytesIO
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

_MAX_NUBES = 0.20
_LADO_MAX = 768
_LADO_MIN = 256
_NDVI_MAX = 0.30
# Clases SCL que se descartan: 0 sin datos, 1 saturado, 3 sombra de nube,
# 6 agua, 8/9 nubes, 10 cirros, 11 nieve.
_SCL_MALAS = (0, 1, 3, 6, 8, 9, 10, 11)

# B8A va AL FINAL (índice 7) para no mover el SCL (índice 6): los análisis guardados y las
# pruebas con 7 bandas siguen funcionando (sin B8A se usa B08 como aproximación).
_EVALSCRIPT = """//VERSION=3
function setup() {
  return {
    input: [{ bands: ["B02","B03","B04","B08","B11","B12","SCL","B8A"], units: "DN" }],
    output: { bands: 8, sampleType: "FLOAT32" }
  };
}
function evaluatePixel(s) {
  return [s.B02, s.B03, s.B04, s.B08, s.B11, s.B12, s.SCL, s.B8A];
}
"""


def disponible() -> bool:
    return bool(os.environ.get("CDSE_CLIENT_ID") and os.environ.get("CDSE_CLIENT_SECRET"))


def _config():
    from sentinelhub import SHConfig
    c = SHConfig()
    c.sh_client_id = os.environ["CDSE_CLIENT_ID"].strip()
    c.sh_client_secret = os.environ["CDSE_CLIENT_SECRET"].strip()
    c.sh_base_url = "https://sh.dataspace.copernicus.eu"
    c.sh_token_url = ("https://identity.dataspace.copernicus.eu/auth/realms/CDSE/"
                      "protocol/openid-connect/token")
    return c


def _desde_18_meses() -> str:
    hoy = date.today()
    anio, mes = hoy.year, hoy.month - 18
    while mes <= 0:
        mes += 12
        anio -= 1
    return date(anio, mes, 1).isoformat()


def bbox_y_tamano(anillo: list) -> tuple[tuple, tuple[int, int]]:
    lngs = [p[0] for p in anillo]
    lats = [p[1] for p in anillo]
    bbox = (min(lngs), min(lats), max(lngs), max(lats))
    # aspecto en metros (corrige por latitud)
    import math
    cy = (bbox[1] + bbox[3]) / 2
    ancho_m = (bbox[2] - bbox[0]) * 111320 * math.cos(math.radians(cy))
    alto_m = (bbox[3] - bbox[1]) * 110540
    # 10 m/píxel como máximo detalle útil, acotado a _LADO_MAX
    escala = max(ancho_m, alto_m) / _LADO_MAX
    escala = max(escala, 10.0)
    ancho = max(_LADO_MIN, min(_LADO_MAX, round(ancho_m / escala)))
    alto = max(_LADO_MIN, min(_LADO_MAX, round(alto_m / escala)))
    return bbox, (ancho, alto)


def _coleccion(config):
    from sentinelhub import DataCollection
    return DataCollection.SENTINEL2_L2A.define_from("SENTINEL2_L2A_CDSE", service_url=config.sh_base_url)


def _intervalo_dia(dia: str) -> tuple[str, str]:
    return f"{dia}T00:00:00Z", f"{dia}T23:59:59Z"


def descargar_bandas(anillo: list, dia: Optional[str] = None, config=None) -> tuple[np.ndarray, tuple, tuple[int, int]]:
    """(alto, ancho, 7) float32 con B02,B03,B04,B08,B11,B12,SCL.
    Con `dia` (AAAA-MM-DD): SOLO la toma de ese día (fecha y hora conocidas).
    Sin `dia` (respaldo si el catálogo falla): mosaico menos nublado de 18 meses (varias fechas)."""
    from sentinelhub import BBox, CRS, MimeType, SentinelHubRequest
    config = config or _config()
    bbox, tam = bbox_y_tamano(anillo)
    intervalo = _intervalo_dia(dia) if dia else (_desde_18_meses(), date.today().isoformat())
    req = SentinelHubRequest(
        evalscript=_EVALSCRIPT,
        input_data=[SentinelHubRequest.input_data(
            data_collection=_coleccion(config), time_interval=intervalo,
            maxcc=1.0 if dia else _MAX_NUBES, mosaicking_order="leastCC")],
        responses=[SentinelHubRequest.output_response("default", MimeType.TIFF)],
        bbox=BBox(bbox, crs=CRS.WGS84), size=tam, config=config)
    datos = req.get_data()[0]
    return np.asarray(datos, dtype=np.float32), bbox, tam


# ---------------------------------------------------------------- elegir UNA fecha despejada
# Nubosidad aceptada DENTRO de la cuadrícula (no en toda la escena de ~110 km). 0,5 % y no 0 %
# porque la clasificación SCL marca a veces como «nube» unos pocos píxeles muy claros.
NUBES_MAX_CUADRICULA = 0.5
_SCL_NUBE = (3, 8, 9, 10)     # sombra de nube, nube media, nube alta, cirros
_SCL_SIN_DATO = (0, 1)
_MAX_REVISAR = 8              # fechas candidatas que se miden (cada una cuesta casi nada: 1 banda, ~100 px)
_SCL_VEGETACION = 4
# ÉPOCA SECA (24/11/2026): con 0 % de nubes en mayo la sierra sale 97 % «vegetación» y Sentinel-2 no ve la roca.
# Entre las tomas DESPEJADAS se elige la de MENOS vegetación (SCL 4, de la misma petición): suele ser jun–oct.
_MESES_SECOS = (6, 7, 8, 9, 10)
_VEG_SUFICIENTE = 5.0         # % de vegetación con el que ya no se sigue buscando


def ordenar_candidatas(cands: list[dict], n: int = _MAX_REVISAR) -> list[dict]:
    """Hasta `n` fechas a medir: ~5/8 de época seca con menos nubes + las más despejadas del resto
    (en la costa el invierno trae neblina), completando con las que sigan. Cada una: {dia, nubes_escena, …}."""
    seco = [c for c in cands if int(c["dia"][5:7]) in _MESES_SECOS]
    otros = [c for c in cands if int(c["dia"][5:7]) not in _MESES_SECOS]
    k = max(1, round(n * 5 / 8))
    pool = seco[:k] + otros[: n - k]
    pool += [c for c in cands if c not in pool][: max(0, n - len(pool))]
    return pool[:n]


def escoger(medidas: list[dict]) -> Optional[dict]:
    """De las fechas medidas ({nubes_cuadricula, cobertura, vegetacion}): entre las despejadas (≤ NUBES_MAX y
    ≥ 98 % de cobertura) la de menos vegetación; si no hay despejadas, la de menos nubes."""
    if not medidas:
        return None
    claras = [c for c in medidas if c["cobertura"] >= 98 and c["nubes_cuadricula"] <= NUBES_MAX_CUADRICULA]
    if claras:
        return min(claras, key=lambda c: (round(c.get("vegetacion", 0)), c["nubes_cuadricula"]))
    return min(medidas, key=lambda c: (c["cobertura"] < 98, c["nubes_cuadricula"]))
_EVAL_SCL = """//VERSION=3
function setup() {
  return { input: [{ bands: ["SCL"], units: "DN" }], output: { bands: 1, sampleType: "UINT8" } };
}
function evaluatePixel(s) { return [s.SCL]; }
"""


def candidatas(bbox: tuple, config) -> list[dict]:
    """Tomas Sentinel-2 L2A de los últimos 18 meses sobre la cuadrícula, una por día,
    ordenadas por nubosidad de la escena (menor primero) y, a igualdad, la más reciente."""
    from sentinelhub import BBox, CRS, SentinelHubCatalog
    cat = SentinelHubCatalog(config=config)
    escenas = cat.search(_coleccion(config), bbox=BBox(bbox, crs=CRS.WGS84),
                         time=(_desde_18_meses(), date.today().isoformat()),
                         filter="eo:cloud_cover < 30",
                         fields={"include": ["id", "properties.datetime", "properties.eo:cloud_cover"], "exclude": []})
    por_dia: dict[str, dict] = {}
    for e in escenas:
        p = e.get("properties") or {}
        dt = str(p.get("datetime") or "")
        if len(dt) < 10:
            continue
        cc = float(p.get("eo:cloud_cover", 100) or 0)
        d = por_dia.setdefault(dt[:10], {"dia": dt[:10], "datetime": dt, "nubes_escena": cc})
        d["nubes_escena"] = max(d["nubes_escena"], cc)  # si la cuadrícula cae en 2 escenas, la peor
    return sorted(por_dia.values(), key=lambda d: (d["nubes_escena"], -int(d["dia"].replace("-", ""))))


def nubes_en_cuadricula(anillo: list, bbox: tuple, dia: str, config) -> tuple[float, float, float]:
    """(% de nubes, % de la cuadrícula cubierta por la toma, % de vegetación) en ese día, con la capa SCL
    a baja resolución (~100 px por lado: costo mínimo)."""
    from sentinelhub import BBox, CRS, MimeType, SentinelHubRequest
    tam = (96, 96)
    req = SentinelHubRequest(
        evalscript=_EVAL_SCL,
        input_data=[SentinelHubRequest.input_data(data_collection=_coleccion(config), time_interval=_intervalo_dia(dia),
                                                  mosaicking_order="leastCC")],
        responses=[SentinelHubRequest.output_response("default", MimeType.TIFF)],
        bbox=BBox(bbox, crs=CRS.WGS84), size=tam, config=config)
    scl = np.asarray(req.get_data()[0]).astype(int)
    if scl.ndim == 3:
        scl = scl[..., 0]
    m = _mascara_poligono([[anillo]], bbox, tam)
    return (*medir_nubes(scl, m), medir_vegetacion(scl, m))


def medir_vegetacion(scl: np.ndarray, area: np.ndarray) -> float:
    """% de vegetación (SCL 4) sobre lo visible (con dato y sin nube)."""
    visible = area & ~np.isin(scl, _SCL_SIN_DATO) & ~np.isin(scl, _SCL_NUBE)
    return float(round(100.0 * int((visible & (scl == _SCL_VEGETACION)).sum()) / max(int(visible.sum()), 1), 1))


def medir_nubes(scl: np.ndarray, area: np.ndarray) -> tuple[float, float]:
    """(% de nubes sobre lo cubierto, % del área cubierta por la toma)."""
    con_dato = area & ~np.isin(scl, _SCL_SIN_DATO)
    nube = con_dato & np.isin(scl, _SCL_NUBE)
    cobertura = 100.0 * int(con_dato.sum()) / max(int(area.sum()), 1)
    # float() explícito: los tipos de numpy (np.float64/np.bool_) no siempre se serializan a JSON
    return float(round(100.0 * int(nube.sum()) / max(int(con_dato.sum()), 1), 2)), float(round(cobertura, 1))


def hora_peru(dt_iso: str) -> str:
    """'2026-08-12T15:21:39.024Z' → '12/08/2026 10:21' (Perú = UTC−5, sin horario de verano)."""
    from datetime import datetime, timedelta, timezone
    t = datetime.fromisoformat(dt_iso.replace("Z", "+00:00")).astimezone(timezone(timedelta(hours=-5)))
    return t.strftime("%d/%m/%Y %H:%M")


def elegir_fecha(anillo: list, bbox: tuple, config) -> Optional[dict]:
    """La toma DESPEJADA y con MENOS VEGETACIÓN sobre la cuadrícula (`ordenar_candidatas` + `escoger`): se
    deja de buscar al hallar una despejada con ≤ 5 % de vegetación. None si el catálogo no responde
    (se usa el mosaico de respaldo)."""
    try:
        cands = candidatas(bbox, config)
    except Exception:  # noqa: BLE001
        return None
    medidas = []
    for c in ordenar_candidatas(cands):
        try:
            nubes, cobertura, veg = nubes_en_cuadricula(anillo, bbox, c["dia"], config)
        except Exception:  # noqa: BLE001
            continue
        medidas.append({**c, "nubes_cuadricula": nubes, "cobertura": cobertura, "vegetacion": veg})
        if cobertura >= 98 and nubes <= NUBES_MAX_CUADRICULA and veg <= _VEG_SUFICIENTE:
            break
    revisadas = len(medidas)
    mejor = escoger(medidas)
    if mejor:
        mejor.update(revisadas=revisadas, candidatas=len(cands), despejada=bool(mejor["nubes_cuadricula"] <= NUBES_MAX_CUADRICULA))
    return mejor


# ------------------------------------------------------------ cálculo
def _mascara_poligono(geom_rings: list[list], bbox: tuple, tam: tuple[int, int]) -> np.ndarray:
    """Rasteriza anillos [lng,lat] (exteriores y huecos alternados por
    polígono) al lienzo. Devuelve bool (alto, ancho)."""
    ancho, alto = tam
    xmin, ymin, xmax, ymax = bbox
    img = Image.new("L", (ancho, alto), 0)
    dib = ImageDraw.Draw(img)

    def px(p):
        return ((p[0] - xmin) / (xmax - xmin) * ancho, (ymax - p[1]) / (ymax - ymin) * alto)

    for poligono in geom_rings:
        for i, anillo in enumerate(poligono):
            if len(anillo) >= 3:
                dib.polygon([px(p) for p in anillo], fill=255 if i == 0 else 0)
    return np.asarray(img) > 0


def _rings_de_geojson(g: dict) -> list[list]:
    if g["type"] == "Polygon":
        return [g["coordinates"]]
    if g["type"] == "MultiPolygon":
        return list(g["coordinates"])
    return []


def _rango_percentil(v: np.ndarray, validos: np.ndarray) -> np.ndarray:
    """0–1 según la posición de cada píxel dentro de los válidos."""
    out = np.zeros_like(v, dtype=np.float32)
    x = v[validos]
    if x.size == 0:
        return out
    orden = np.argsort(np.argsort(x))
    out[validos] = orden / max(x.size - 1, 1)
    return out


# ---------------------------------------------------------------- combinaciones de bandas
def _estirar(b: np.ndarray, area: np.ndarray) -> np.ndarray:
    """Estira una banda al 2–98 % de los píxeles del área → 0–255."""
    x = b[area & (b > 0)]
    if x.size < 10:
        return np.zeros_like(b, dtype=np.uint8)
    lo, hi = np.percentile(x, [2, 98])
    return (np.clip((b - lo) / max(hi - lo, 1e-6), 0, 1) * 255).astype(np.uint8)


def _compuesto(r, g, b, area, conjunto: bool = False) -> str:
    """Composición RGB estirada al 2–98 %. `conjunto` = MISMOS límites para las tres bandas (color natural: estirar
    cada banda por separado le daba un tinte morado al terreno; 24/11/2026)."""
    if conjunto:
        x = np.concatenate([v[area & (v > 0)] for v in (r, g, b)])
        if x.size >= 10:
            lo, hi = np.percentile(x, [2, 98])
            f = lambda v: (np.clip((v - lo) / max(hi - lo, 1e-6), 0, 1) ** (1 / 1.15) * 255).astype(np.uint8)  # noqa: E731
            rgb = np.dstack([f(r), f(g), f(b)])
            rgb[~area] = 0
            buf = BytesIO()
            Image.fromarray(rgb, mode="RGB").save(buf, format="JPEG", quality=82, optimize=True)
            return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    rgb = np.dstack([_estirar(r, area), _estirar(g, area), _estirar(b, area)])
    rgb[~area] = 0
    buf = BytesIO()
    Image.fromarray(rgb, mode="RGB").save(buf, format="JPEG", quality=82, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


# Peso geológico de cada clase: solo separa A/B (≥ 0,6: entran en la Sílice limpia y en la Prioridad libre)
# de la C («verificar», no entra). Va en `datos.base` para que el navegador recalcule con otros cortes.
_PESO_CLASE = {"A": 1.0, "B": 0.7, "C": 0.4}
_PESO_MIN_INTERES = 0.6


def _peso(a: dict) -> float:
    try:
        return float(a["peso_geo"])
    except (KeyError, TypeError, ValueError):
        return _PESO_CLASE.get(a.get("clase"), 0.4)


# Cortes desde los que el hierro o la arcilla EXCLUYEN de la Prioridad libre (capas Hierro, Férrico, Ferroso y
# Arcillas). PERCENTIL dentro de la cuadrícula para los TRES (pedido del usuario, 23/11/2026: «no uses k como
# parámetro; quiero el histograma para modelar del percentil 1 al 100»): se marca lo que queda en o sobre el
# percentil elegido de cada cociente (férrico B4/B2, ferroso B11/B8A, arcilla B11/B12). Hierro final = férrico ∪
# ferroso. Por defecto: férrico P50, ferroso P50, arcilla P90. El usuario los cambia en la app con el histograma
# (frontend `cortes.ts` recalcula las capas con `datos`, sin volver a pedir la imagen): mantener iguales.
# (24/11/2026, pedido del usuario: «elimina lo que no se va a usar») Ya NO hay pureza, prioridad combinada
# (geología + pureza), índice combinado ni modos 1:100 000: la decisión es la Prioridad libre.
# (24/11/2026, pedido del usuario: «el histograma de anomalía ferruginosa y no de los otros dos») El hierro que se
# excluye se define con UN corte: el percentil de la ANOMALÍA FERRUGINOSA (férrico + ferroso). Arcilla aparte.
# PRIORIDAD LIBRE DEFINITIVA (definición del usuario, 24/11/2026): se QUEDA el píxel de zona A/B que cumple LOS
# TRES a la vez (intersección), cada uno por percentil en la cuadrícula y ajustable con su histograma:
#   NDVI < p_ndvi (0,57: «sin vegetación» + «vegetación escasa» de la leyenda)
#   anomalía ferruginosa < p_ferruginosa (0,30: clases 1–3 = índigo, azul, celeste)
#   arcilla < arcilla (0,30: clases 1–3)
# y además suelo visible (`validos`: sin nubes/agua y NDVI < 0,30). Luego se cruza con las áreas libres (app).
# Las capas ferruginosas y arcillas se dibujan SIEMPRE en 10 clases fijas (deciles P0–P100) para que el color
# signifique lo mismo que el corte (clase ≤ 3 = pasa). = frontend cortes.ts: mantener iguales.
# SIN BSI (decisión del usuario, 24/11/2026, tras comparar con y sin): BSI alto y ferruginosa baja casi no coinciden
# (el BSI lleva B4 en el numerador) y con BSI la prioridad quedaba casi vacía hasta en el desierto (28k2-NE: 0 ha;
# sin BSI 1 537 ha libres). La capa BSI se sigue mostrando, pero no entra en la Prioridad libre.
CORTES = {"p_ferruginosa": 0.30, "arcilla": 0.30, "p_ndvi": 0.57}


def calcular(bandas: np.ndarray, anillo: list, afloramientos: list[dict],
             bbox: tuple, tam: tuple[int, int], aster: Optional[np.ndarray] = None,   # (ASTER ya no se usa)
             afloramientos_100k: Optional[list[dict]] = None, cortes: Optional[dict] = None) -> dict:
    """`afloramientos_100k` se acepta por compatibilidad y se ignora (regla: una sola carta)."""
    c = {**CORTES, **{k: float(v) for k, v in (cortes or {}).items() if k in CORTES and v is not None}}
    b02, b03, b04, b08, b11, b12, scl = (bandas[..., i] for i in range(7))
    b8a = bandas[..., 7] if bandas.shape[-1] > 7 else b08
    eps = 1e-6
    ndvi = (b08 - b04) / (b08 + b04 + eps)
    ferrico = b04 / (b02 + eps)
    arcilla = b11 / (b12 + eps)
    brillo = (b02 + b03 + b04 + b11) / 4.0
    # Hierro ferroso (Fe²⁺: minerales máficos, clorita, piroxeno): absorbe en el infrarrojo
    # cercano (~0,9–1,1 µm) → B11/B8A alto. Malo para vidrio (roca oscura mezclada).
    ferroso = b11 / (b8a + eps)

    area = _mascara_poligono([[anillo]], bbox, tam)
    validos = area & ~np.isin(scl.astype(int), _SCL_MALAS) & (ndvi < _NDVI_MAX) & (b02 > 0)
    frac_validos = float(validos.sum()) / max(int(area.sum()), 1)

    r_fe = _rango_percentil(ferrico, validos)
    r_cl = _rango_percentil(arcilla, validos)
    r_br = _rango_percentil(brillo, validos)
    r_f2 = _rango_percentil(ferroso, validos)
    # El ferroso (B11/B8A) sube también con arena MUY clara y seca sin hierro: si el píxel es de los más
    # brillantes y casi sin férrico, no se cuenta como ferroso (falso positivo del desierto: arena silícea limpia).
    falso_ferroso = (r_br >= 0.75) & (r_fe < 0.50)
    con_dato = area & ~np.isin(scl.astype(int), _SCL_SIN_DATO + _SCL_NUBE) & (b02 > 0)
    # ANOMALÍA FERRUGINOSA = FÉRRICO + FERROSO: férrico = B4/B2 + B4/B3, ferroso = B11/B8A (salvo el falso ferroso),
    # cada uno como percentil sobre TODOS los píxeles con dato; la suma (0–2) se vuelve a ordenar (0–100 %).
    s_fer = _rango_percentil(ferrico + b04 / (b03 + eps), con_dato) + np.where(falso_ferroso, 0, _rango_percentil(ferroso, con_dato))
    r_ferrug = _rango_percentil(s_fer, con_dato)
    # anomalía ferruginosa / arcilla en o sobre el corte (donde se ve el suelo): lo que NO pasa por esos dos filtros
    fe_alto = validos & (r_ferrug >= c["p_ferruginosa"])
    arcilla_alta = validos & (r_cl >= c["arcilla"])
    hierro_final = _limpiar_mascara(fe_alto)
    arc_c = _limpiar_mascara(arcilla_alta)

    # ---- ESCALA CONTINUA (pedido del usuario, 24/11/2026: «sin histograma, todo al 100 % de datos»; él baja la
    # transparencia en la app). Se usan TODOS los píxeles con dato y sin nube (la vegetación también: es lo que
    # separa el afloramiento de lo cubierto) y el color es la posición del píxel en la cuadrícula (0–100 %).
    #  · NDVI y BSI POR SEPARADO (corrección del usuario, 24/11/2026: «haz capas aparte de NDVI, BSI»; antes iban
    #    combinados en «Afloramientos»). NDVI = (B8 − B4)/(B8 + B4): vegetación. BSI = suelo/roca desnuda; juntos y
    #    sobre las fotos RGB 4-3-2 o SWIR 12-11-2 muestran el afloramiento y su continuidad superficial (se lee sobre la foto
    #    RGB 4-3-2 o SWIR 12-11-2). BSI = ((B11 + B4) − (B8 + B2)) / ((B11 + B4) + (B8 + B2)).
    #  · ANOMALÍAS FERRUGINOSAS = FÉRRICO + FERROSO (definición del usuario, 24/11/2026): férrico = B4/B2 + B4/B3
    #    (óxidos férricos: hematita, goethita, limonita) y ferroso = B11/B8A (Fe²⁺: máficos, clorita, biotita),
    #    cada uno como percentil en la cuadrícula, sumados y vueltos a ordenar (0–100 %).
    bsi = ((b11 + b04) - (b08 + b02)) / ((b11 + b04) + (b08 + b02) + eps)
    r_ndvi = _rango_percentil(ndvi, con_dato)
    r_bsi = _rango_percentil(bsi, con_dato)
    # INTERSECCIÓN de los tres filtros (ver CORTES), limpiada de píxeles sueltos con la moda 3×3
    cumple = _limpiar_mascara(validos & (r_ndvi < c["p_ndvi"]) & (r_ferrug < c["p_ferruginosa"]) & (r_cl < c["arcilla"]))
    sucio = area & ~cumple          # lo que NO pasa (incluye vegetación, nubes y lo que no se ve)

    # Peso geológico por píxel (la mejor clase de las zonas que lo cubren)
    peso_geo = np.zeros(area.shape, dtype=np.float32)
    mascaras = {}
    for a in afloramientos:
        m = _mascara_poligono(_rings_de_geojson(a["geometria"]), bbox, tam) & area
        mascaras[a["id"]] = m
        peso_geo[m] = np.maximum(peso_geo[m], _peso(a))
    interes = area & (peso_geo >= _PESO_MIN_INTERES)       # zonas A y B
    # SÍLICE LIMPIA (base de la Prioridad libre, definición del 24/11/2026): zonas A/B ∩ NDVI bajo ∩
    # ferruginosa baja ∩ arcilla baja (sin BSI). Ya NO quedan los píxeles bajo vegetación o nubes.
    limpia = interes & cumple

    # Colores que no se confunden entre sí ni con las clases A/B/C. Leyenda = App.tsx VISTAS_S2.
    capas = {
        # (24/11/2026, pedido del usuario) ya NO se dibujan: hierro final, férrico, ferroso, cocientes ni cuarzo ASTER.
        # El hierro (férrico ∪ ferroso con los cortes del histograma) se sigue RESTANDO de la Prioridad libre.
        # 10 CLASES de colores distintos (pedido del usuario, 24/11/2026: «que cada zona sea de diferente color para
        # agrupar»): el rango mostrado (corte → P100) se parte en 10 tramos de igual número de píxeles
        # (24/11/2026) 10 clases FIJAS P0–P100: el corte elige cuántas clases pasan (no cambia los colores)
        "arcillas": _png_clases(r_cl, validos),
        # escala continua, 100 % de los datos (sin corte): verde oscuro = cubierto → blanco = roca desnuda
        # NDVI: pardo = sin vegetación (roca, suelo) → verde oscuro = vegetación densa
        "ndvi": _png_continua(r_ndvi, con_dato, _RAMPA_NDVI),
        # BSI: azul petróleo = cubierto o húmedo → blanco = suelo o roca desnuda
        "bsi": _png_continua(r_bsi, con_dato, _RAMPA_BSI),
        # escala continua: azul pizarra = sin óxidos → amarillo → rojo oscuro = más ferruginoso
        # sigue al CORTE del histograma (pedido del usuario, 24/11/2026: «que la capa cambie al modificar»): se pinta
        # lo que queda en o sobre el percentil elegido, con la rampa estirada del corte a P100 (con P1 = casi todo)
        "ferruginosas": _png_clases(r_ferrug, con_dato),
        # combinaciones de bandas (mismas bandas ya descargadas: sin costo extra)
        "natural": _compuesto(b04, b03, b02, area, conjunto=True),
        "swir": _compuesto(b12, b11, b02, area),        # geología: separa tipos de roca
    }
    if afloramientos:
        rgba = np.zeros(limpia.shape + (4,), np.uint8)
        rgba[limpia] = (22, 163, 74, 255)
        capas["silice_limpia"] = _png(Image.fromarray(rgba, "RGBA"))

    def media(arr, m):
        x = arr[m]
        x = x[np.isfinite(x)]
        return round(100 * float(x.mean()), 1) if x.size else None

    stats = []
    for a in afloramientos:
        m = mascaras[a["id"]]
        mv = m & validos
        n, nv = int(m.sum()), int(mv.sum())
        if n == 0:
            continue
        stats.append({
            "id": a["id"],
            "pixeles": n, "pct_validos": round(100 * nv / n, 1),
            # % de la zona que cumple los tres filtros (NDVI, ferruginosa, arcilla)
            "limpia_pct": round(100 * float((m & cumple).sum()) / n, 1),
            # % de los píxeles ÚTILES de la zona que no pasa algún filtro
            "excluido_pct": media(sucio.astype(np.float32), mv) if nv else None,
            "oxidos_hierro_pct": media(r_fe, mv) if nv else None,
            "arcillas_pct": media(r_cl, mv) if nv else None,
            "ferroso_pct": media(r_f2, mv) if nv else None,
            # hierro total = el mayor de los dos rangos (férrico o ferroso), 0–100: menos = mejor
            "hierro_pct": media(np.maximum(r_fe, r_f2), mv) if nv else None,
            "brillo_pct": media(r_br, mv) if nv else None,
            "anomalia_hierro_pct": media(hierro_final.astype(np.float32), mv) if nv else None,
            "anomalia_arcilla_pct": media(arc_c.astype(np.float32), mv) if nv else None,
            # escala continua (0–100, posición media de la zona en la cuadrícula; con todos los píxeles con dato)
            "ndvi_pct": media(r_ndvi, m & con_dato) if (m & con_dato).any() else None,
            "bsi_pct": media(r_bsi, m & con_dato) if (m & con_dato).any() else None,
            "ferruginosa_pct": media(r_ferrug, m & con_dato) if (m & con_dato).any() else None,
        })
    stats.sort(key=lambda s: -s["limpia_pct"] * s["pixeles"])

    def pct(m):
        return round(100 * float(m.sum()) / max(int(area.sum()), 1), 1)

    def util(m):
        return round(100 * float((m & validos).sum()) / max(int(validos.sum()), 1), 1)
    celda = {
        # % de la cuadrícula en zonas A/B y lo que queda sin hierro ni arcilla (antes de cruzar con áreas libres)
        "pct_interes": pct(interes) if afloramientos else None,
        "pct_silice_limpia": pct(limpia) if afloramientos else None,
        # % de la cuadrícula que cumple los tres filtros / que no los cumple
        "pct_cumple": pct(cumple),
        "pct_excluido_hierro_arcilla": pct(sucio),
        "pct_oxidos_altos": pct(hierro_final),
        "pct_hierro_alto": pct(hierro_final),
        "pct_arcilla_alta": pct(arc_c),
        # % de anomalía sobre los PÍXELES ÚTILES (sin nubes, agua ni vegetación): la medida que importa
        "anomalia_hierro_pct": util(hierro_final),
        "anomalia_arcilla_pct": util(arc_c),
        "pct_vegetacion_nubes_agua": round(100 - 100 * frac_validos, 1),
    }
    return {"bbox": list(bbox), "capas": capas, "afloramientos": stats, "celda": celda,
            "cortes": c, "datos": _datos_cortes(r_ferrug, r_cl, r_ndvi, r_bsi, validos, con_dato, area, peso_geo,
                                                s_fer, arcilla, ndvi, bsi),
            "solo_satelite": not afloramientos,
            "pct_area_valida": round(100 * frac_validos, 1)}


def _histograma(v: np.ndarray, validos: np.ndarray, bins: int = 60) -> Optional[dict]:
    """Histograma del cociente REAL (no del percentil) entre P1 y P99 + valor de cada percentil 0–100."""
    x = v[validos]
    x = x[np.isfinite(x)].astype(np.float64)
    if x.size < 10:
        return None
    p = np.percentile(x, np.arange(101))
    lo, hi = float(p[1]), float(p[99])
    hi = max(hi, lo + max(abs(lo), 1.0) * 1e-3)          # datos casi constantes: rango mínimo
    cuentas, _ = np.histogram(np.clip(x, lo, hi), bins=bins, range=(lo, hi))
    return {"min": round(lo, 4), "max": round(hi, 4), "cuentas": cuentas.tolist(),
            "percentiles": [round(float(y), 4) for y in p]}


def _datos_cortes(r_ferrug, r_cl, r_ndvi, r_bsi, validos, con_dato, area, peso50, s_fer, arcilla, ndvi, bsi) -> dict:
    """Lo necesario para que la app recalcule la Prioridad libre con OTROS cortes (sin créditos):
    «formato» 4 · «rangos» = RGB (percentil de la anomalía ferruginosa, percentil de NDVI, percentil de arcilla) ·
    «base» = RGB (R: 0 = píxel no útil, 255 = útil; G: 0 = fuera de la cuadrícula, si no 1 + 200·peso geológico;
    B: 0 fuera, 1 = dentro de la cuadrícula sin dato, 2–255 = píxel con dato y 2 + 253·percentil de BSI).
    (Formato 3: B = 2 en todo píxel con dato, sin BSI. Formato 2, antes del 24/11/2026: G de «rangos» = 0: sin NDVI.)
    El BSI por píxel sirve para dibujar la capa BSI solo dentro de las unidades elegidas (cortes.ts); no filtra.
    PNG sin transparencia (el canvas alteraría el RGB de los píxeles transparentes)."""
    q = lambda a: np.clip(np.round(a * 255), 0, 255).astype(np.uint8)  # noqa: E731
    rgb1 = np.dstack([q(r_ferrug), q(r_ndvi), q(r_cl)])
    br = np.where(validos, 255, 0).astype(np.uint8)
    g = np.where(area, 1 + np.round(peso50 * 200), 0).astype(np.uint8)
    b = np.where(con_dato, 2 + np.round(r_bsi * 253), np.where(area, 1, 0)).astype(np.uint8)   # ≥ 2 = píxel con dato
    rgb2 = np.dstack([br, g, b])
    # histograma de la anomalía ferruginosa = su valor real (suma de percentiles férrico + ferroso, 0–2)
    return {"formato": 4, "rangos": _png(Image.fromarray(rgb1, mode="RGB")), "base": _png(Image.fromarray(rgb2, mode="RGB")),
            "hist": {"ferruginosa": _histograma(s_fer, con_dato), "arcilla": _histograma(arcilla, validos),
                     "ndvi": _histograma(ndvi, con_dato), "bsi": _histograma(bsi, con_dato)}}   # bsi: solo referencia


# Rampas de las capas continuas (paradas 0 → 1). No usan verde/azul de la Prioridad libre ni el magenta de arcillas.
_RAMPA_NDVI = ((0.0, (120, 72, 36)), (0.45, (214, 199, 161)), (0.7, (134, 190, 90)), (1.0, (20, 83, 45)))
_RAMPA_BSI = ((0.0, (15, 60, 70)), (0.5, (150, 150, 125)), (0.8, (226, 214, 180)), (1.0, (255, 252, 240)))
_RAMPA_FERRUGINOSA = ((0.0, (30, 41, 59)), (0.5, (148, 120, 60)), (0.75, (245, 158, 11)), (0.9, (220, 38, 38)), (1.0, (127, 29, 29)))


# Paleta de 10 clases (índigo → azul → celeste → turquesa → verde → lima → amarillo → naranja → rojo → granate).
# = frontend `CLASES_COLOR` en cortes.ts: mantener iguales.
CLASES_COLOR = [(59, 42, 152), (63, 111, 224), (34, 167, 240), (20, 208, 196), (58, 229, 127), (163, 240, 58), (242, 217, 58), (251, 154, 42), (232, 70, 27), (143, 13, 13)]


def _png_clases(t: np.ndarray, mascara: np.ndarray) -> str:
    """PNG con paleta: clase = ⌊t·10⌋ (t en 0–1 dentro del rango mostrado); índice 0 transparente."""
    idx = np.where(mascara, 1 + np.minimum(9, np.floor(np.clip(t, 0, 1) * 10)), 0).astype(np.uint8)
    img = Image.fromarray(idx, mode="P")
    img.putpalette([0, 0, 0] + [v for c in CLASES_COLOR for v in c])
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True, transparency=0)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _png_continua(v: np.ndarray, mascara: np.ndarray, paradas) -> str:
    """PNG con paleta (256 colores, compacto): índice 0 = transparente (sin dato o nube), 1–255 = rampa de 0 a 1.
    Opaco: la transparencia la elige el usuario en la app."""
    xs = np.linspace(0, 1, 255)
    paleta = [0, 0, 0]
    for x in xs:
        for (x0, c0), (x1, c1) in zip(paradas, paradas[1:]):
            if x0 <= x <= x1:
                t = (x - x0) / max(x1 - x0, 1e-9)
                paleta += [round(c0[k] + (c1[k] - c0[k]) * t) for k in range(3)]
                break
    idx = np.where(mascara, 1 + np.round(np.clip(v, 0, 1) * 254), 0).astype(np.uint8)
    img = Image.fromarray(idx, mode="P")
    img.putpalette(paleta)
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True, transparency=0)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _limpiar_mascara(m: np.ndarray) -> np.ndarray:
    """Quita píxeles sueltos («sal y pimienta») con un filtro de moda 3×3, como en una clasificación
    profesional: un píxel aislado no es un afloramiento ni una alteración."""
    if not m.any():
        return m
    img = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.ModeFilter(3))
    return np.asarray(img) > 127

def _rampa_color(v: np.ndarray, sel_base: np.ndarray, umbral: float, claro, oscuro, tope: float = 1.0) -> Image.Image:
    """Rampa de color claro→oscuro para v ≥ umbral, saturada en `tope` (más oscuro y opaco = mayor)."""
    alto, ancho = v.shape
    rgba = np.zeros((alto, ancho, 4), dtype=np.uint8)
    sel = sel_base & (v >= umbral)
    t = np.clip((v - umbral) / max(tope - umbral, 1e-6), 0, 1)
    for k in range(3):
        rgba[..., k] = (claro[k] + (oscuro[k] - claro[k]) * t).astype(np.uint8)
    rgba[..., 3] = np.where(sel, (140 + 100 * t).astype(np.uint8), 0)
    return Image.fromarray(rgba, mode="RGBA")


def _png(img: Image.Image) -> str:
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def sin_cupo(e: Exception) -> bool:
    """¿El error de Sentinel Hub es por cupo agotado (unidades o peticiones) o por límite de ritmo?"""
    t = f"{type(e).__name__} {e}".upper()
    return any(k in t for k in ("INSUFFICIENT", "QUOTA", "429", "TOO MANY REQUESTS", "RATE LIMIT"))


def analizar(anillo: list, afloramientos: list[dict], afloramientos_100k: Optional[list[dict]] = None) -> dict:
    """Copernicus (Sentinel Hub) primero; si su cupo se acabó (o no hay claves, o no responde), el archivo
    público de AWS (sentinel_aws), gratis y sin límite. `imagen.fuente` dice cuál se usó y por qué.
    SENTINEL_FUENTE=aws fuerza AWS."""
    import sentinel_aws
    bbox, tam = bbox_y_tamano(anillo)
    motivo_aws = None
    if os.environ.get("SENTINEL_FUENTE", "").lower() == "aws":
        motivo_aws = "configurado para usar AWS"
    elif not disponible():
        motivo_aws = "Copernicus sin claves configuradas"
    toma = bandas = None
    if motivo_aws is None:
        try:
            config = _config()
            toma = elegir_fecha(anillo, bbox, config)
            bandas, bbox, tam = descargar_bandas(anillo, dia=toma["dia"] if toma else None, config=config)
        except Exception as e:  # noqa: BLE001
            if not sentinel_aws.disponible():
                raise
            motivo_aws = ("cupo de Copernicus agotado (unidades o peticiones del mes)" if sin_cupo(e)
                          else f"Copernicus no respondió ({type(e).__name__})")
            toma = bandas = None
    fuente = "Copernicus (Sentinel Hub)"
    if motivo_aws is not None:
        if not sentinel_aws.disponible():
            return {"disponible": False, "motivo": f"Sentinel-2 no disponible: {motivo_aws} y falta rasterio para AWS."}
        bandas, toma = sentinel_aws.descargar(anillo, bbox, tam, _mascara_poligono([[anillo]], bbox, tam))
        fuente = f"AWS · Earth Search ({motivo_aws})"
    res = calcular(bandas, anillo, afloramientos, bbox, tam)
    if toma:
        # nubes medidas en la imagen FINAL (resolución completa), no solo en la vista previa
        nubes_final, _ = medir_nubes(bandas[..., 6].astype(int), _mascara_poligono([[anillo]], bbox, tam))
        imagen = {
            "metodo": "una_fecha", "fecha_utc": toma["datetime"], "fecha_peru": hora_peru(toma["datetime"]),
            "nubes_cuadricula": nubes_final, "nubes_escena": float(round(toma["nubes_escena"], 1)),
            "despejada": bool(nubes_final <= NUBES_MAX_CUADRICULA), "nubes_max": NUBES_MAX_CUADRICULA,
            "revisadas": toma["revisadas"], "candidatas": toma["candidatas"], "fuente": fuente,
            # vegetación (SCL) en la imagen FINAL: lo que Sentinel-2 no puede «ver» como roca
            "vegetacion_cuadricula": medir_vegetacion(bandas[..., 6].astype(int), _mascara_poligono([[anillo]], bbox, tam)),
        }
        periodo = f"toma del {imagen['fecha_peru']} (hora Perú)"
    else:
        imagen = {"metodo": "mosaico", "nubes_cuadricula": None, "fuente": fuente,
                  "nota": "El catálogo de Copernicus no respondió: se usó un mosaico de varias fechas (18 meses), sin fecha única."}
        periodo = f"mosaico {_desde_18_meses()} a {date.today().isoformat()}"
    res.update(disponible=True, periodo=periodo, imagen=imagen, fuente=fuente,
               nota=("Índices relativos a la cuadrícula analizada (percentiles): marcan dónde hay más hierro "
                     "y arcilla para descartarlo. No mide SiO2: confirmar con muestreo y laboratorio."))
    return res
