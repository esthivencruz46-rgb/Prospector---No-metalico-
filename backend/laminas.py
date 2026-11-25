"""Láminas cartográficas profesionales (PNG, A3 apaisado a 150 ppp) de una cuadrícula o de una ruta.

Plantilla común (como un informe técnico):
  · marco del mapa con cuadrícula UTM rotulada en los 4 lados, norte, escala gráfica y numérica;
  · columna derecha: título, mapa de UBICACIÓN (Perú por departamentos, el de la cuadrícula
    resaltado), LEYENDA y DATOS;
  · membrete inferior: título · elaborado por · fuente · lugar (provincia, departamento) · datum ·
    escala · logo.

Contenido (lo arma la app con lo que ya tiene del análisis; aquí solo se dibuja):
  · `capas`: imágenes georreferenciadas (PNG data URL) en EPSG:4326 lineal (Sentinel-2, prioridad)
    o Web Mercator (áreas libres); se reproyectan al UTM de la lámina píxel a píxel.
  · `zonas`: polígonos GeoJSON (zonas A/B/C) con su clase y nombre de unidad.
  · `ruta`: tramos (pista / trocha / a pie) con tabla de distancias.
  · tipo «libres»: la lámina de áreas libres se pide aquí mismo a `libres.imagen` (GEOCATMIN).

Límites de departamentos y provincias: geoBoundaries (CC BY 4.0) en backend/datos/limites/.
"""
from __future__ import annotations

import base64
import json
import math
import os
import re
from datetime import date
from functools import lru_cache
from io import BytesIO

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFilter
from pyproj import Transformer
from shapely.geometry import Point, box, shape
from shapely.ops import unary_union

from mapa_geologico import _exportar, _fuente, _opacidad, gms

AQUI = os.path.dirname(os.path.abspath(__file__))
LIMITES = os.path.join(AQUI, "datos", "limites")
ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services"
FABRICA = (-13.0808, -76.3877)    # San Vicente de Cañete (fija)

# lienzo A3 apaisado a 150 ppp
LW, LH = 2480, 1754
M = 34                               # margen exterior
COL = 600                            # ancho de la columna derecha
MEMBRETE = 168                       # alto del membrete
ROT = 64                             # franja de rótulos de coordenadas alrededor del mapa

NEGRO, GRIS, GRIS_C, BLANCO = (20, 24, 31), (92, 104, 120), (196, 203, 212), (255, 255, 255)
COBRE, COBRE_O = (192, 138, 74), (122, 82, 40)
COLOR_CLASE = {"A": (220, 38, 38), "B": (245, 158, 11), "C": (250, 204, 21)}
COLOR_TRAMO = {"pista": (59, 130, 246), "trocha": (180, 83, 9), "a_pie": (236, 72, 153)}
NOMBRE_TRAMO = {"pista": "Carretera asfaltada", "trocha": "Trocha / afirmado", "a_pie": "A pie"}


# ------------------------------------------------------------------ límites administrativos
@lru_cache(maxsize=1)
def _adm() -> dict:
    """{"dep": [(nombre, geom)], "prov": [(nombre, geom)]} (geoBoundaries, simplificado)."""
    out = {}
    for clave, n in (("dep", 1), ("prov", 2)):
        try:
            with open(os.path.join(LIMITES, f"PER_ADM{n}.geojson"), encoding="utf-8") as fh:
                fs = json.load(fh)["features"]
            out[clave] = [(_arreglar(f["properties"].get("shapeName", "")), shape(f["geometry"]).buffer(0)) for f in fs]
        except (OSError, ValueError, KeyError):
            out[clave] = []
    return out


def _arreglar(t: str) -> str:
    """geoBoundaries trae algunos nombres con la codificación rota («CaÃ±ete» → «Cañete»)."""
    try:
        return t.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return t


def _nombre_dep(n: str) -> str:
    # geoBoundaries separa «Lima Province» (Lima Metropolitana) del departamento
    return {"Lima Province": "Lima", "Municipalidad Metropolitana de Lima": "Lima", "El Callao": "Callao",
            "Ancash": "Áncash"}.get(n, n)


def lugar(lat: float, lon: float) -> dict:
    p = Point(lon, lat)
    a = _adm()
    dep = next((_nombre_dep(n) for n, g in a["dep"] if g.contains(p)), None)
    prov = next((n for n, g in a["prov"] if g.contains(p)), None)
    if dep is None and a["dep"]:   # en la costa el punto puede caer en el mar: el más cercano
        dep = _nombre_dep(min(a["dep"], key=lambda t: t[1].distance(p))[0])
    return {"departamento": dep or "—", "provincia": prov or "—"}


# ------------------------------------------------------------------ utilidades de dibujo
def _hex(c) -> tuple:
    if isinstance(c, (list, tuple)):
        return tuple(int(v) for v in c[:3])
    c = str(c).lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    try:
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return GRIS


def _png_de(data_url: str) -> Image.Image:
    b = base64.b64decode(re.sub(r"^data:image/[a-z]+;base64,", "", data_url))
    return Image.open(BytesIO(b)).convert("RGBA")


def _texto_rotado(lam: Image.Image, xy, texto: str, fuente, color=NEGRO, angulo=90):
    d0 = ImageDraw.Draw(lam)
    x0, y0, x1, y1 = d0.textbbox((0, 0), texto, font=fuente)
    tmp = Image.new("RGBA", (x1 - x0 + 4, y1 - y0 + 4), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((2 - x0, 2 - y0), texto, font=fuente, fill=color)
    tmp = tmp.rotate(angulo, expand=True)
    lam.paste(tmp, (int(xy[0] - tmp.width / 2), int(xy[1] - tmp.height / 2)), tmp)


def _envolver(texto: str, fuente, ancho: int, d: ImageDraw.ImageDraw) -> list[str]:
    lineas, actual = [], ""
    for p in str(texto).split():
        prueba = f"{actual} {p}".strip()
        if d.textlength(prueba, font=fuente) <= ancho:
            actual = prueba
        else:
            if actual:
                lineas.append(actual)
            actual = p
    if actual:
        lineas.append(actual)
    return lineas


def _logo(d: ImageDraw.ImageDraw, x: int, y: int, s: int):
    """Marca de la app (estratos y cumbre), como en la cabecera."""
    k = s / 32
    P = lambda pts: [(x + px * k, y + py * k) for px, py in pts]  # noqa: E731
    d.rounded_rectangle([x, y, x + s, y + s], radius=int(7 * k), fill=(30, 41, 59))
    d.polygon(P([(5, 21), (11, 13), (15, 18), (20, 9), (27, 21)]), fill=COBRE)
    d.polygon(P([(5, 21), (27, 21), (27, 24), (5, 24)]), fill=(138, 90, 43))
    d.polygon(P([(5, 24), (27, 24), (27, 27), (5, 27)]), fill=(91, 59, 29))
    d.ellipse([x + 18 * k, y + 7 * k, x + 22 * k, y + 11 * k], fill=(233, 213, 179))


# ------------------------------------------------------------------ marco geográfico
class Marco:
    """Extensión UTM del mapa ajustada al tamaño del recuadro (sin deformar)."""

    def __init__(self, oeste, sur, este, norte, ancho_px, alto_px, margen=0.07):
        self.zona = int((((oeste + este) / 2) + 180) // 6) + 1
        self.epsg = 32700 + self.zona
        self.a_utm = Transformer.from_crs(4326, self.epsg, always_xy=True)
        self.a_geo = Transformer.from_crs(self.epsg, 4326, always_xy=True)
        xs, ys = self.a_utm.transform([oeste, este, este, oeste], [sur, sur, norte, norte])
        X0, X1, Y0, Y1 = min(xs), max(xs), min(ys), max(ys)
        mx, my = (X1 - X0) * margen, (Y1 - Y0) * margen
        X0, X1, Y0, Y1 = X0 - mx, X1 + mx, Y0 - my, Y1 + my
        # ajustar al aspecto del recuadro
        asp = ancho_px / alto_px
        if (X1 - X0) / (Y1 - Y0) < asp:
            c, w = (X0 + X1) / 2, (Y1 - Y0) * asp
            X0, X1 = c - w / 2, c + w / 2
        else:
            c, h = (Y0 + Y1) / 2, (X1 - X0) / asp
            Y0, Y1 = c - h / 2, c + h / 2
        self.X0, self.X1, self.Y0, self.Y1 = X0, X1, Y0, Y1
        self.W, self.H = ancho_px, alto_px

    def px(self, x, y):
        return (x - self.X0) / (self.X1 - self.X0) * self.W, (self.Y1 - y) / (self.Y1 - self.Y0) * self.H

    def geo_px(self, lon, lat):
        return self.px(*self.a_utm.transform(lon, lat))

    @property
    def bbox(self):
        return (self.X0, self.Y0, self.X1, self.Y1)

    def reproyectar(self, img: Image.Image, crs: str, bb: tuple) -> Image.Image:
        """Imagen en EPSG:4326 lineal («4326») o Web Mercator («3857») con recuadro (o, s, e, n) en grados
        → misma imagen en la grilla UTM del mapa (vecino más cercano)."""
        W, H = self.W, self.H
        xs = self.X0 + (np.arange(W) + 0.5) * (self.X1 - self.X0) / W
        ys = self.Y1 - (np.arange(H) + 0.5) * (self.Y1 - self.Y0) / H
        gx, gy = np.meshgrid(xs, ys)
        lon, lat = self.a_geo.transform(gx, gy)
        o, s, e, n = bb
        if crs == "3857":
            r = 6378137.0
            mx = lambda v: r * np.radians(v)  # noqa: E731
            my = lambda v: r * np.log(np.tan(np.pi / 4 + np.radians(v) / 2))  # noqa: E731
            u = (mx(lon) - mx(o)) / (mx(e) - mx(o))
            v = (my(n) - my(lat)) / (my(n) - my(s))
        else:
            u = (lon - o) / (e - o)
            v = (n - lat) / (n - s)
        a = np.asarray(img)
        h, w = a.shape[:2]
        ci = np.floor(u * w).astype(int)
        ri = np.floor(v * h).astype(int)
        dentro = (ci >= 0) & (ci < w) & (ri >= 0) & (ri < h)
        out = np.zeros((H, W, 4), np.uint8)
        out[dentro] = a[ri[dentro], ci[dentro]]
        return Image.fromarray(out, "RGBA")


def _fondo(mr: Marco, tipo: str) -> Image.Image:
    """Relieve sombreado (o imagen satelital para la ruta) + límites y poblados de Esri."""
    base = Image.new("RGBA", (mr.W, mr.H), (246, 246, 243, 255))
    if tipo == "ruta":
        sat = _exportar(f"{ESRI}/World_Imagery/MapServer/export", mr.bbox, mr.epsg, (mr.W, mr.H), sesion=requests)
        if sat is not None:
            base = Image.alpha_composite(base, _opacidad(sat, 0.92))
    else:
        som = _exportar(f"{ESRI}/Elevation/World_Hillshade/MapServer/export", mr.bbox, mr.epsg, (mr.W, mr.H), sesion=requests)
        if som is not None:
            base = Image.alpha_composite(base, _opacidad(som, 0.55))
    ref = _exportar(f"{ESRI}/Reference/World_Boundaries_and_Places/MapServer/export", mr.bbox, mr.epsg,
                    (mr.W, mr.H), sesion=requests)
    if ref is not None:
        base = Image.alpha_composite(base, _opacidad(ref, 0.85))
    return base


# ------------------------------------------------------------------ lámina
def _hexc(c) -> str:
    return "#%02x%02x%02x" % tuple(int(v) for v in c[:3])


def _poligonos(geom):
    for g in getattr(geom, "geoms", [geom]):
        if g.geom_type == "Polygon":
            yield g
        elif hasattr(g, "geoms"):
            yield from _poligonos(g)


def _dibujar_poligono(dm, mr, pol, relleno, borde, ancho=3):
    dm.polygon([mr.geo_px(x, y) for x, y in pol.exterior.coords], fill=relleno, outline=borde, width=ancho)
    for h in pol.interiors:
        dm.polygon([mr.geo_px(x, y) for x, y in h.coords], fill=(0, 0, 0, 0), outline=borde, width=max(1, ancho - 1))


COLOR_RESTR = {"prohibido": (220, 38, 38), "restringido": (217, 119, 6)}
COLOR_ESTADO = {"titulado": (37, 99, 235), "en trámite (petitorio)": (124, 58, 237), "extinguido": (100, 116, 139)}


def _geologia_unidades(pol, escala: str = "50K") -> list[dict]:
    """Unidades geológicas de TODA la cuadrícula (GEOCATMIN 50K, o 100K sin cobertura 50K), con descripción."""
    import geocatmin_rmi as g
    if escala == "50K":
        servicio, capa, campos = ("SERV_GEOLOGIA_50K_INTEGRADA", 7, "CODI,ETIQUETA,UNIDAD,LITOLOGIA,DESCRIP,E_MAX_MA,E_MIN_MA,"
                                  "SISTEMA_MAX,SISTEMA_MIN,SERIE_MAX,SERIE_MIN,PISO_MAX,PISO_MIN,GROSOR_M,AMBIENTE_S,REFERENCIA")
    else:
        servicio, capa, campos = "SERV_GEOLOGIA_100K_INTEGRADA", 6, "NAME,UNIDAD,DESCRIP"
    feats = g.query_en_poligono(servicio, capa, g._anillo_esri(pol), campos, timeout=g.GEOLOGIA[escala]["timeout"])
    out = []
    for f in feats:
        a = f.get("attributes") or {}
        geom = g.esri_a_shapely(f.get("geometry"))
        if geom is None or geom.is_empty:
            continue
        inter = geom.intersection(pol)
        if inter.is_empty:
            continue
        def t(k):
            v = str(a.get(k) or "").strip()
            return "" if v.upper() in ("<NULL>", "NULL", "NONE", "0") else v
        try:
            emin, emax = float(a.get("E_MIN_MA")), float(a.get("E_MAX_MA"))
        except (TypeError, ValueError):
            emin = emax = None
        out.append({"etiqueta": t("ETIQUETA") or t("NAME"), "unidad": t("UNIDAD"), "lito": t("LITOLOGIA"),
                    "descripcion": t("DESCRIP"), "geom": geom, "inter": inter, "ha": g.area_ha(inter),
                    "emin": emin, "emax": emax, "sistema": t("SISTEMA_MIN") or t("SISTEMA_MAX"),
                    "sistema_max": t("SISTEMA_MAX"), "serie": t("SERIE_MIN") or t("SERIE_MAX"), "serie_max": t("SERIE_MAX"),
                    "piso": " – ".join(x for x in dict.fromkeys((t("PISO_MAX"), t("PISO_MIN"))) if x),
                    "grosor": t("GROSOR_M"), "ambiente": "" if t("AMBIENTE_S").isdigit() else t("AMBIENTE_S"),
                    "referencia": t("REFERENCIA")})
    return out


def orden_estratigrafico(unidades: list[dict]) -> list[dict]:
    """De lo más JOVEN (arriba) a lo más ANTIGUO, como en la leyenda de una carta geológica; sin edad, al final."""
    return sorted(unidades, key=lambda u: (u.get("emin") is None, u.get("emin") or 0, u.get("emax") or 0, -u["ha"]))


def edad_txt(u: dict) -> str:
    sis = u.get("sistema") or ""
    if u.get("sistema_max") and u["sistema_max"] != sis:
        sis = f"{u['sistema_max']} – {sis}"
    ser = u.get("serie") or ""
    if u.get("serie_max") and u["serie_max"] != ser:
        ser = f"{u['serie_max']} – {ser}"
    return " · ".join(x for x in (sis, ser) if x)


def _cajetin(lam: Image.Image, p: dict, titulo: str, lugar_txt: str, zona: int, escala_txt: str):
    """Cajetín de lámina técnica: título · EMPRESA · PROYECTO · ELABORADO POR · FUENTE · LUGAR · DATUM · ESCALA ·
    FECHA y, a la derecha, el N.º de lámina (en lugar del logo de la app)."""
    d = ImageDraw.Draw(lam)
    f8, f10, f10b, f11b = _fuente(13), _fuente(17), _fuente(17, True), _fuente(19, True)
    by0, by1 = LH - M - MEMBRETE, LH - M
    bx0, bx1 = M, LW - M
    ancho_num = 190
    d.rectangle([bx0, by0, bx1, by1], outline=NEGRO, width=3)
    fila1 = by0 + 52
    d.line([(bx0, fila1), (bx1 - ancho_num, fila1)], fill=NEGRO, width=2)
    sub = p.get("subtitulo") or ""
    d.text(((bx0 + bx1 - ancho_num) / 2, by0 + 26), (titulo + (f" · {sub.upper()}" if sub else ""))[:150], font=f11b, fill=NEGRO, anchor="mm")
    celdas = [("EMPRESA", p.get("empresa") or "—", 0.15), ("PROYECTO", p.get("proyecto") or "—", 0.17),
              ("ELABORADO POR", p.get("autor") or "—", 0.12), ("FUENTE", p.get("fuente") or "INGEMMET · Copernicus", 0.17),
              ("LUGAR", lugar_txt, 0.13), ("DATUM · PROYECCIÓN", f"WGS 84 · UTM {zona} S", 0.10),
              ("ESCALA · FECHA" if escala_txt != "—" else "FECHA",
               f"{escala_txt} · {date.today():%d/%m/%Y}" if escala_txt != "—" else f"{date.today():%d/%m/%Y}", 0.16)]
    ancho_util = bx1 - bx0 - ancho_num
    xx = bx0
    for cab, val, fr in celdas:
        w = ancho_util * fr
        d.line([(xx, fila1), (xx, by1)], fill=NEGRO, width=2)
        d.text((xx + w / 2, fila1 + 24), cab, font=_fuente(14, True), fill=NEGRO, anchor="mm")
        d.line([(xx, fila1 + 46), (xx + w, fila1 + 46)], fill=GRIS_C, width=1)
        lin = _envolver(val, _fuente(15), w - 16, d)[:3]
        for i, l in enumerate(lin):
            d.text((xx + w / 2, fila1 + 80 + (i - (len(lin) - 1) / 2) * 20), l, font=_fuente(15), fill=NEGRO, anchor="mm")
        xx += w
    d.line([(xx, by0), (xx, by1)], fill=NEGRO, width=3)
    d.text(((xx + bx1) / 2, by0 + 34), "LÁMINA", font=f10b, fill=NEGRO, anchor="mm")
    d.text(((xx + bx1) / 2, by0 + 92), str(p.get("lamina") or "—"), font=_fuente(44, True), fill=NEGRO, anchor="mm")
    if p.get("total"):
        d.text(((xx + bx1) / 2, by1 - 22), f"de {p['total']}", font=f8, fill=GRIS, anchor="mm")


def generar(p: dict) -> bytes:
    """p: {tipo, titulo, subtitulo, autor, celda{codigo,sur,oeste,norte,este}, capas[{png,crs,bbox,opacidad}],
    zonas[{clase,unidad,geometria}], leyenda[{color,texto,forma}], datos[[clave, valor]], fuente, ruta{…}}"""
    tipo = p.get("tipo", "geologia")
    celda = p.get("celda") or {}
    ruta = p.get("ruta")

    # extensión: la cuadrícula o la ruta completa
    if ruta:
        pts = [(x, y) for b in ruta.get("bloques", []) for x, y in b["geometria"]["coordinates"]]
        pts += [(ruta["origen"]["lon"], ruta["origen"]["lat"]), (ruta["destino"]["lon"], ruta["destino"]["lat"])]
        o, e = min(x for x, _ in pts), max(x for x, _ in pts)
        s, n = min(y for _, y in pts), max(y for _, y in pts)
        lat_c, lon_c = ruta["destino"]["lat"], ruta["destino"]["lon"]
    else:
        o, s, e, n = celda["oeste"], celda["sur"], celda["este"], celda["norte"]
        lat_c, lon_c = (s + n) / 2, (o + e) / 2

    mx0, my0 = M + ROT, M + ROT
    mw = LW - M - COL - 24 - ROT - mx0
    mh = LH - M - MEMBRETE - 20 - ROT - my0
    mr = Marco(o, s, e, n, mw, mh, margen=0.09 if ruta else 0.06)

    # --- contenido del mapa
    mapa = _fondo(mr, tipo)
    for c in p.get("capas") or []:
        try:
            img = mr.reproyectar(_png_de(c["png"]), c.get("crs", "4326"), tuple(c["bbox"]))
            mapa = Image.alpha_composite(mapa, _opacidad(img, float(c.get("opacidad", 0.9))))
        except Exception:  # noqa: BLE001  (una capa rota no impide la lámina)
            continue
    srv_ley: list[dict] = []
    srv_datos: list[list] = []
    unidades_geo: list[dict] = []
    if tipo == "geologia_completa" and celda:
        from mapa_geologico import CONFIG as _CFG
        esc = p.get("escala") or "50K"
        cfg = _CFG.get(esc, _CFG["50K"])
        import geocatmin_rmi as _g
        img = _exportar(f"{_g.BASE}/{cfg['servicio']}/MapServer/export", mr.bbox, mr.epsg, (mr.W, mr.H), layers=f"show:{cfg['capa']}")
        if img is None:
            raise RuntimeError("GEOCATMIN no entregó la imagen de la geología.")
        # SOLO la cuadrícula (pedido del usuario): fuera de ella la geología no se pinta
        corte = Image.new("L", (mr.W, mr.H), 0)
        paso = 16
        borde_g = ([(o + (e - o) * i / paso, s) for i in range(paso)] + [(e, s + (n - s) * i / paso) for i in range(paso)]
                   + [(e - (e - o) * i / paso, n) for i in range(paso)] + [(o, n - (n - s) * i / paso) for i in range(paso)])
        ImageDraw.Draw(corte).polygon([mr.geo_px(x, y) for x, y in borde_g], fill=255)
        img_c = img.copy()
        img_c.putalpha(Image.fromarray(np.minimum(np.asarray(img.getchannel("A")), np.asarray(corte))))
        mapa = Image.alpha_composite(mapa, _opacidad(img_c, 0.88))
        try:
            unidades_geo = _geologia_unidades(box(o, s, e, n), esc)
        except Exception as ex:  # noqa: BLE001
            raise RuntimeError(f"No se pudo consultar la geología (GEOCATMIN): {type(ex).__name__}") from ex
        # color de cada unidad = el que GEOCATMIN dibujó (mediana alrededor de un punto interior)
        ga = np.asarray(img)
        por_unidad: dict[str, dict] = {}
        for u in sorted(unidades_geo, key=lambda u: -u["ha"]):
            k = u["etiqueta"] or u["unidad"]
            x = por_unidad.setdefault(k, {**u, "ha": 0.0})
            x["ha"] += u["ha"]
            if "color" not in x:
                pt = u["inter"].representative_point()
                cx, cy = (int(v) for v in mr.geo_px(pt.x, pt.y))
                ven = ga[max(0, cy - 7):cy + 8, max(0, cx - 7):cx + 8].reshape(-1, 4)
                ven = ven[ven[:, 3] > 200]
                x["color"] = tuple(int(v) for v in np.median(ven[:, :3], axis=0)) if len(ven) >= 10 else (200, 200, 200)
        p["_unidades_geo"] = orden_estratigrafico(list(por_unidad.values()))
        grupo = None
        for u in p["_unidades_geo"]:
            g_txt = edad_txt(u) or "Edad no indicada"
            if g_txt != grupo:
                srv_ley.append({"forma": "titulo", "texto": g_txt.upper()})
                grupo = g_txt
            nom = u["unidad"] or "—"
            srv_ley.append({"color": _hexc(u["color"]), "simbolo": u["etiqueta"], "texto": f"{nom}: {u['lito'] or '—'}"})
    areas_libres = None
    etq_pre: list = []
    if tipo == "topografia" and celda:
        import relieve
        try:
            z, (n0, o0) = relieve.dem(s, o, n, e)
        except Exception as ex:  # noqa: BLE001
            raise RuntimeError(f"No se pudo leer el relieve (Copernicus DEM): {type(ex).__name__}") from ex
        if not np.isfinite(z).any():
            raise RuntimeError("Sin datos de elevación en la cuadrícula.")
        PXd = relieve.PX
        zmin, zmax = float(np.nanmin(z)), float(np.nanmax(z))
        zf = np.nan_to_num(z, nan=zmin)
        # sombreado (luz del NO, 45°) + tintas hipsométricas
        gy, gx = np.gradient(zf, 30.0)
        pend = np.arctan(np.hypot(gx, gy))
        asp = np.arctan2(-gx, gy)
        az, alt = np.radians(315), np.radians(45)
        som = np.clip(np.sin(alt) * np.cos(pend) + np.cos(alt) * np.sin(pend) * np.cos(az - asp), 0, 1)
        t = (zf - zmin) / max(zmax - zmin, 1)
        paradas = [(0.0, (111, 168, 110)), (0.2, (170, 200, 130)), (0.4, (226, 220, 150)), (0.6, (214, 176, 112)),
                   (0.8, (168, 124, 88)), (1.0, (236, 232, 226))]
        rgb = np.zeros(z.shape + (3,), np.float32)
        for (x0, c0), (x1, c1) in zip(paradas, paradas[1:]):
            m = (t >= x0) & (t <= x1)
            u = ((t - x0) / (x1 - x0))[m]
            for k in range(3):
                rgb[..., k][m] = c0[k] + (c1[k] - c0[k]) * u
        rgb *= (0.55 + 0.45 * som)[..., None]
        # curvas de nivel (normales y maestras cada 5) a doble resolución
        intervalo = next(v for v in (10, 20, 25, 50, 100, 200) if v >= (zmax - zmin) / 40)
        rgba = np.dstack([np.clip(rgb, 0, 255).astype(np.uint8), np.full(z.shape, 255, np.uint8)])
        img = Image.fromarray(rgba, "RGBA").resize((z.shape[1] * 2, z.shape[0] * 2), Image.BILINEAR)
        zz = np.asarray(Image.fromarray(zf).resize((z.shape[1] * 2, z.shape[0] * 2), Image.BILINEAR))
        lv = np.floor(zz / intervalo)
        borde_c = np.zeros(zz.shape, bool)
        borde_c[:, 1:] |= lv[:, 1:] != lv[:, :-1]
        borde_c[1:, :] |= lv[1:, :] != lv[:-1, :]
        lm = np.floor(zz / (5 * intervalo))
        maestra = np.zeros(zz.shape, bool)
        maestra[:, 1:] |= lm[:, 1:] != lm[:, :-1]
        maestra[1:, :] |= lm[1:, :] != lm[:-1, :]
        a_img = np.asarray(img).copy()
        a_img[borde_c] = (92, 64, 40, 255)
        maestra = np.asarray(Image.fromarray((maestra * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))) > 0
        a_img[maestra] = (60, 36, 18, 255)
        img = Image.fromarray(a_img, "RGBA")
        bb_dem = (o0, n0 - z.shape[0] * PXd, o0 + z.shape[1] * PXd, n0)
        img_m = mr.reproyectar(img, "4326", bb_dem)
        # solo la cuadrícula
        corte = Image.new("L", (mr.W, mr.H), 0)
        paso_c = 16
        borde_g = ([(o + (e - o) * i / paso_c, s) for i in range(paso_c)] + [(e, s + (n - s) * i / paso_c) for i in range(paso_c)]
                   + [(e - (e - o) * i / paso_c, n) for i in range(paso_c)] + [(o, n - (n - s) * i / paso_c) for i in range(paso_c)])
        ImageDraw.Draw(corte).polygon([mr.geo_px(x, y) for x, y in borde_g], fill=255)
        img_m.putalpha(Image.fromarray(np.minimum(np.asarray(img_m.getchannel("A")), np.asarray(corte))))
        mapa = Image.alpha_composite(mapa, img_m)
        # rótulos de cota en las maestras (espaciados)
        ys, xs = np.nonzero(maestra[::6, ::6])
        tomados: list = []
        for yy, xx in zip(ys * 6, xs * 6):
            lon, lat = o0 + (xx / 2) * PXd, n0 - (yy / 2) * PXd
            if not (o < lon < e and s < lat < n):
                continue
            px_, py_ = mr.geo_px(lon, lat)
            if any(abs(px_ - a_) < 140 and abs(py_ - b_) < 60 for a_, b_ in tomados):
                continue
            tomados.append((px_, py_))
            cota = int(round(zz[yy, xx] / (5 * intervalo)) * 5 * intervalo)
            etq_pre.append(((px_, py_), f"{cota}", 1.0))
            if len(tomados) >= 40:
                break
        p["_topo"] = {"zmin": zmin, "zmax": zmax, "intervalo": intervalo,
                      "zmed": float(np.nanmean(z)), "pend": float(np.degrees(np.nanmean(pend))),
                      "pend90": float(np.degrees(np.nanpercentile(pend, 90)))}
        cotas = [zmin + (zmax - zmin) * f for f in (0, 0.2, 0.4, 0.6, 0.8, 1.0)]
        srv_ley = [{"forma": "titulo", "texto": "ALTITUD (m s. n. m.)"}]
        for (fx, col), c0_ in zip(paradas, cotas):
            srv_ley.append({"color": _hexc(col), "texto": f"{c0_:,.0f}".replace(",", " ")})
        srv_ley += [{"forma": "titulo", "texto": "CURVAS DE NIVEL"},
                    {"color": "#5c4028", "forma": "linea", "texto": f"Curva ordinaria · cada {intervalo} m"},
                    {"color": "#3c2412", "forma": "linea", "texto": f"Curva maestra · cada {5 * intervalo} m (con cota)"}]
        tp = p["_topo"]
        srv_datos = [["Cota mínima · máxima", f"{tp['zmin']:,.0f} · {tp['zmax']:,.0f} m".replace(",", " ")],
                     ["Desnivel", f"{tp['zmax'] - tp['zmin']:,.0f} m".replace(",", " ")],
                     ["Cota media", f"{tp['zmed']:,.0f} m".replace(",", " ")],
                     ["Pendiente media · P90", f"{tp['pend']:.0f}° · {tp['pend90']:.0f}°"],
                     ["Equidistancia", f"{intervalo} m (maestras cada {5 * intervalo} m)"],
                     ["Modelo de elevación", "Copernicus DEM GLO-30 (30 m)"],
                     ["Sombreado", "Iluminación desde el NO, 45°"]]
    if tipo == "libres" and celda:
        # (24/11/2026) Cada motivo por el que algo NO es libre y utilizable va con su color: las áreas protegidas son
        # LAS MISMAS de la lámina de áreas protegidas (mismos polígonos y colores); lo demás (centro poblado, ríos,
        # chacras, vías…) no es ANP sino tierra libre que no sirve para cantera.
        import libres as lib
        import restricciones as restr
        try:
            w = 900
            hgt = max(64, int(w * (n - s) / (e - o)))
            mk = lib.mascaras(o, s, e, n, w, hgt)
            areas_libres = restr.consultar(box(o, s, e, n))
        except Exception as ex:  # noqa: BLE001
            raise RuntimeError(f"No se pudieron calcular las áreas libres (GEOCATMIN): {type(ex).__name__}") from ex
        lz = lib.Lienzo(o, s, e, n, w, hgt)
        celda_m = lz([box(o, s, e, n)]) & mk["tierra"]
        tot = max(int(celda_m.sum()), 1)
        libre_legal = celda_m & ~mk["ocupado"]
        rgba = np.zeros((hgt, w, 4), np.uint8)
        pct = {}
        ya = np.zeros((hgt, w), bool)
        orden_no_apto = [("urbano", (126, 34, 206)), ("poblados", (236, 72, 153)), ("rios", (14, 165, 233)),
                         ("vias", (82, 82, 91)), ("agua", (37, 99, 235)), ("cultivo", (234, 179, 8))]
        for k, col in orden_no_apto:
            mm = libre_legal & mk[k] & ~ya
            rgba[mm] = col + (200,)
            ya |= mm
            pct[k] = 100 * mm.sum() / tot
        util = libre_legal & ~ya
        rgba[util & ~mk["extinguido"]] = (22, 163, 74, 190)
        rgba[util & mk["extinguido"]] = (125, 211, 252, 200)
        concesion = celda_m & mk["ocupado"] & ~lz([a["_geom"] for a in areas_libres])
        rgba[concesion] = (148, 163, 184, 150)
        pct["util"] = 100 * (util & ~mk["extinguido"]).sum() / tot
        pct["ext"] = 100 * (util & mk["extinguido"]).sum() / tot
        pct["concesion"] = 100 * concesion.sum() / tot
        pct["protegido"] = sum(a["pct_cuadricula"] for a in areas_libres)
        img = Image.fromarray(rgba, "RGBA")
        mapa = Image.alpha_composite(mapa, mr.reproyectar(img, "3857", (o, s, e, n)))
        f1 = lambda v: f"{v:.1f} %".replace(".", ",")  # noqa: E731
        srv_ley = [{"forma": "titulo", "texto": "SE PUEDE PEDIR"},
                   {"color": "#16a34a", "texto": f"Libre y utilizable · {f1(pct['util'])}"},
                   {"color": "#7dd3fc", "texto": f"Derecho extinguido (falta publicar la libre denunciabilidad) · {f1(pct['ext'])}"},
                   {"forma": "titulo", "texto": "NO SE PUEDE PEDIR"},
                   {"color": "#dc2626", "forma": "borde", "texto": f"Área protegida no concesionable (= lámina de áreas protegidas)"},
                   {"color": "#d97706", "forma": "borde", "texto": f"Área restringida · áreas protegidas en total {f1(pct['protegido'])}"},
                   {"color": "#94a3b8", "texto": f"Con derecho minero (ver lámina de concesiones) · {f1(pct['concesion'])}"},
                   {"forma": "titulo", "texto": "LIBRE, PERO NO APTO PARA CANTERA (NO ES ÁREA PROTEGIDA)"}]
        nombres = {"urbano": "Zona construida", "poblados": "A menos de 300 m de un centro poblado",
                   "rios": "Faja de ríos y lagunas (25–50 m)", "vias": "Franja de carreteras (15–50 m)",
                   "agua": "Agua, bofedal o nieve", "cultivo": "Chacras y cultivos"}
        for k, col in orden_no_apto:
            if pct[k] >= 0.01:
                srv_ley.append({"color": _hexc(col), "texto": f"{nombres[k]} · {f1(pct[k])}"})
        srv_datos = [["Libre y utilizable", f1(pct["util"])], ["Extinguido (libre con observación)", f1(pct["ext"])],
                     ["Áreas protegidas o restringidas", f1(pct["protegido"])], ["Con derecho minero", f1(pct["concesion"])],
                     ["Libre pero no apto", f1(sum(pct[k] for k, _ in orden_no_apto))],
                     ["Uso del suelo", str(mk.get("_fuente_cobertura") or "—")],
                     ["Criterio no apto", "Cobertura Sentinel-2 10 m (cultivos, construido, agua) y franjas de la cartografía base de INGEMMET (vías, ríos, centros poblados)"]]

    capa = Image.new("RGBA", (mr.W, mr.H), (0, 0, 0, 0))
    dm = ImageDraw.Draw(capa)
    etq_srv: list = list(etq_pre)
    if areas_libres:
        for a in areas_libres:
            col = COLOR_RESTR.get(a.get("nivel"), COLOR_RESTR["restringido"])
            for pol in _poligonos(a["_geom"]):
                _dibujar_poligono(dm, mr, pol, col + (60,), col + (255,), 3)
    # ---- áreas protegidas / restringidas (GEOCATMIN, en vivo)
    if tipo == "protegidas" and celda:
        import restricciones as restr
        try:
            areas = restr.consultar(box(o, s, e, n))
        except Exception as ex:  # noqa: BLE001
            raise RuntimeError(f"No se pudieron consultar las áreas protegidas (GEOCATMIN): {type(ex).__name__}") from ex
        for a in sorted(areas, key=lambda a: -a["pct_cuadricula"]):
            col = COLOR_RESTR.get(a.get("nivel"), COLOR_RESTR["restringido"])
            for pol in _poligonos(a["_geom"]):
                _dibujar_poligono(dm, mr, pol, col + (70,), col + (255,), 3)
            if a["pct_cuadricula"] >= 0.5:
                rp = a["_geom"].representative_point()
                etq_srv.append((mr.geo_px(rp.x, rp.y), str(a["nombre"])[:42], a["pct_cuadricula"]))
        niveles = {a.get("nivel") for a in areas}
        if "prohibido" in niveles:
            srv_ley.append({"color": _hexc(COLOR_RESTR["prohibido"]), "texto": "No concesionable (ANP de uso indirecto, arqueológica, ANAP, defensa…)"})
        if "restringido" in niveles or not niveles:
            srv_ley.append({"color": _hexc(COLOR_RESTR["restringido"]), "texto": "Restringido: requiere autorización u opinión previa"})
        srv_datos = [[str(a["nombre"]), f"{a['tipo']} · {'no concesionable' if a.get('nivel') == 'prohibido' else 'restringido'} · "
                      f"{a['pct_cuadricula']} % de la cuadrícula", "lista"]
                     for a in sorted(areas, key=lambda a: -a["pct_cuadricula"])[:12]] or [["Áreas protegidas", "Ninguna en la cuadrícula"]]
        srv_datos.insert(0, ["Total en la cuadrícula", f"{min(100, sum(a['pct_cuadricula'] for a in areas)):.1f} % · {len(areas)} área(s)"])
    # ---- concesiones mineras (catastro de INGEMMET, en vivo)
    if tipo == "concesiones" and celda:
        import libres as lib
        try:
            cons = lib.concesiones(box(o, s, e, n))
        except Exception as ex:  # noqa: BLE001
            raise RuntimeError(f"No se pudo consultar el catastro minero (GEOCATMIN): {type(ex).__name__}") from ex
        for c_ in sorted(cons, key=lambda c: -c["ha_en_cuadricula"]):
            col = COLOR_ESTADO.get(c_["estado"], (217, 70, 239))
            for pol in _poligonos(c_["_geom"]):
                _dibujar_poligono(dm, mr, pol, col + (60,), col + (255,), 2)
            if c_["ha_en_cuadricula"] >= 40:
                rp = c_["_geom"].representative_point()
                etq_srv.append((mr.geo_px(rp.x, rp.y), str(c_["nombre"])[:24], c_["ha_en_cuadricula"]))
        nombre_est = {"titulado": "Concesión titulada", "en trámite (petitorio)": "Petitorio en trámite",
                      "extinguido": "Derecho extinguido (sin titular; falta publicar la libre denunciabilidad)"}
        for est, col in COLOR_ESTADO.items():
            if any(c_["estado"] == est for c_ in cons):
                srv_ley.append({"color": _hexc(col), "texto": nombre_est.get(est, est)})
        if any(c_["estado"] not in COLOR_ESTADO for c_ in cons):
            srv_ley.append({"color": "#d946ef", "texto": "Otros (cantera del Estado, bloqueado…)"})
        ha_con = sum(c_["ha_en_cuadricula"] for c_ in cons)
        srv_datos = [["Derechos mineros", f"{len(cons)} · {ha_con:,.0f} ha en la cuadrícula".replace(",", " ")]]
        srv_datos += [[f"{c_['nombre']} · {c_['codigo']}",
                       f"{c_.get('titular') or '—'} · {c_['estado']} · {c_['ha_en_cuadricula']:,.0f} ha".replace(",", " "), "lista"]
                      for c_ in sorted(cons, key=lambda c: -c["ha_en_cuadricula"])[:12]]
    # ---- contactos geológicos y rótulos (geología completa)
    if tipo == "geologia_completa" and unidades_geo:
        caja = box(o, s, e, n)
        for u in unidades_geo:
            for pol in _poligonos(u["geom"].intersection(caja)):
                for anillo in [pol.exterior, *pol.interiors]:
                    dm.line([mr.geo_px(x, y) for x, y in anillo.coords], fill=(40, 46, 56, 255), width=2)
        for u in unidades_geo:
            for parte in _poligonos(u["inter"]):
                if parte.area > 0 and u["etiqueta"]:
                    rp = parte.representative_point()
                    import geocatmin_rmi as _g2
                    etq_srv.append((mr.geo_px(rp.x, rp.y), u["etiqueta"], _g2.area_ha(parte)))
    # zonas A/B/C (relleno suave + borde)
    zonas = sorted(p.get("zonas") or [], key=lambda z: "CBA".index(z.get("clase", "C")) if z.get("clase") in "ABC" else 0)
    etiquetas = []
    for z in zonas:
        col = COLOR_CLASE.get(z.get("clase"), GRIS)
        try:
            g = shape(z["geometria"])
        except Exception:  # noqa: BLE001
            continue
        relleno = int(z.get("relleno", 70))
        for pol in getattr(g, "geoms", [g]):
            if pol.geom_type != "Polygon":
                continue
            ext = [mr.geo_px(x, y) for x, y in pol.exterior.coords]
            dm.polygon(ext, fill=col + (relleno,), outline=col + (255,), width=3 if relleno else 2)
            for h in pol.interiors:
                dm.polygon([mr.geo_px(x, y) for x, y in h.coords], fill=(0, 0, 0, 0), outline=col + (255,), width=2)
        if g.area > 0 and z.get("unidad"):
            rp = g.representative_point()
            # la FORMACIÓN, no el grupo («Grupo Goyllarisquizga - Formación Farrat» → «Fm. Farrat»)
            nom = str(z["unidad"]).split(" - ")[-1].replace("Formación ", "Fm. ").replace("Grupo ", "Gpo. ")
            etiquetas.append((mr.geo_px(rp.x, rp.y), nom[:26], g.area))
    mapa = Image.alpha_composite(mapa, capa)

    d = ImageDraw.Draw(mapa)
    f_eti = _fuente(15, True)
    puestas: list[tuple] = []          # recuadros ya ocupados: las etiquetas no se pisan
    etiquetas = etq_srv + etiquetas
    for (x, y), t, _ in sorted(etiquetas, key=lambda t: -t[2])[:45 if tipo in ("geologia_completa", "topografia") else 24]:
        bx = d.textbbox((x, y), t, font=f_eti, anchor="mm")
        bx = (bx[0] - 6, bx[1] - 4, bx[2] + 6, bx[3] + 4)
        if bx[0] < 6 or bx[1] < 6 or bx[2] > mr.W - 6 or bx[3] > mr.H - 6:
            continue
        if tipo == "geologia_completa" and celda:      # el rótulo entero dentro de la cuadrícula
            cx_ = [mr.geo_px(x_, y_) for x_, y_ in ((o, s), (e, s), (e, n), (o, n))]
            if bx[0] < max(c_[0] for c_ in (cx_[0], cx_[3])) + 4 or bx[2] > min(c_[0] for c_ in (cx_[1], cx_[2])) - 4                     or bx[1] < max(c_[1] for c_ in (cx_[2], cx_[3])) + 4 or bx[3] > min(c_[1] for c_ in (cx_[0], cx_[1])) - 4:
                continue
        if any(not (bx[2] < q[0] or bx[0] > q[2] or bx[3] < q[1] or bx[1] > q[3]) for q in puestas):
            continue
        puestas.append(bx)
        d.text((x, y), t, font=f_eti, fill=NEGRO, anchor="mm", stroke_width=3, stroke_fill=BLANCO)

    # borde de la cuadrícula
    if celda:
        paso = 16
        borde = ([(o + (e - o) * i / paso, s) for i in range(paso)] + [(e, s + (n - s) * i / paso) for i in range(paso)]
                 + [(e - (e - o) * i / paso, n) for i in range(paso)] + [(o, n - (n - s) * i / paso) for i in range(paso)])
        pb = [mr.geo_px(x, y) for x, y in borde]
        d.line(pb + [pb[0]], fill=(10, 10, 10), width=6)
        d.line(pb + [pb[0]], fill=(220, 38, 38), width=3)

    # ruta: tramos de colores, origen y destino
    if ruta:
        for b in ruta.get("bloques", []):
            col = COLOR_TRAMO.get(b["tipo"], GRIS)
            pts = [mr.geo_px(x, y) for x, y in b["geometria"]["coordinates"]]
            if len(pts) < 2:
                continue
            d.line(pts, fill=BLANCO, width=11, joint="curve")
            if b["tipo"] == "a_pie":
                for i in range(len(pts) - 1):   # punteado
                    (x1, y1), (x2, y2) = pts[i], pts[i + 1]
                    L = math.hypot(x2 - x1, y2 - y1)
                    k = 0.0
                    while k < L:
                        a, b2 = k / L, min(k + 14, L) / L
                        d.line([(x1 + (x2 - x1) * a, y1 + (y2 - y1) * a), (x1 + (x2 - x1) * b2, y1 + (y2 - y1) * b2)], fill=col, width=7)
                        k += 24
            else:
                d.line(pts, fill=col, width=7, joint="curve")
        f_pin = _fuente(17, True)
        for clave, color, letra in (("origen", (21, 128, 61), "A"), ("destino", (185, 28, 28), "B")):
            q = ruta[clave]
            x, y = mr.geo_px(q["lon"], q["lat"])
            d.ellipse([x - 17, y - 17, x + 17, y + 17], fill=color, outline=BLANCO, width=4)
            d.text((x, y), letra, font=f_pin, fill=BLANCO, anchor="mm")
            nom, fn = q.get("nombre", ""), _fuente(17, True)
            izq = x + 24 + d.textlength(nom, font=fn) > mr.W - 10      # no cortar el nombre en el borde
            d.text((x - 24, y) if izq else (x + 24, y), nom, font=fn, fill=NEGRO, anchor="rm" if izq else "lm",
                   stroke_width=4, stroke_fill=BLANCO)

    # --- lámina
    lam = Image.new("RGB", (LW, LH), BLANCO)
    lam.paste(mapa.convert("RGB"), (mx0, my0))
    d = ImageDraw.Draw(lam)
    f8, f9, f10, f11 = _fuente(13), _fuente(15), _fuente(17), _fuente(19)
    f10b, f11b, f13b, f16b = _fuente(17, True), _fuente(19, True), _fuente(23, True), _fuente(28, True)

    # cuadrícula UTM con rótulos; en mapas de más de 250 km de ancho (rutas largas, varias zonas UTM) se rotula en
    # GRADOS: los estes UTM salían negativos («−200 000») fuera de la zona central
    ancho_km = (mr.X1 - mr.X0) / 1000
    if ancho_km > 250:
        lons, lats = mr.a_geo.transform([mr.X0, mr.X1, mr.X1, mr.X0], [mr.Y0, mr.Y0, mr.Y1, mr.Y1])
        o, e, s_, n = min(lons), max(lons), min(lats), max(lats)
        paso = 1 if max(e - o, n - s_) <= 8 else 2

        def cruce(pts, eje, valor):
            """Punto donde la polilínea cruza x (eje 0) o y (eje 1) = valor."""
            for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
                v1, v2 = (x1, y1)[eje], (x2, y2)[eje]
                if (v1 - valor) * (v2 - valor) <= 0 and v1 != v2:
                    t = (valor - v1) / (v2 - v1)
                    return x1 + t * (x2 - x1), y1 + t * (y2 - y1)
            return None

        def grados(v, lat):
            return f"{abs(v):.0f}° {('S' if v < 0 else 'N') if lat else ('O' if v < 0 else 'E')}"

        for lon in range(math.ceil(o / paso) * paso, math.floor(e) + 1, paso):
            pts = [mr.geo_px(lon, s_ + (n - s_) * i / 60) for i in range(61)]
            dentro = [(mx0 + x, my0 + y) for x, y in pts if 0 <= x <= mw and 0 <= y <= mh]
            if len(dentro) > 1:
                d.line(dentro, fill=(120, 130, 140), width=1)
            for yb, yy, anc in ((0, my0 - 10, "mb"), (mh, my0 + mh + 10, "mt")):
                c = cruce(pts, 1, yb)
                if c and 0 <= c[0] <= mw:
                    d.text((mx0 + c[0], yy), grados(lon, False), font=f9, fill=NEGRO, anchor=anc)
        for lat in range(math.ceil(s_ / paso) * paso, math.floor(n) + 1, paso):
            pts = [mr.geo_px(o + (e - o) * i / 60, lat) for i in range(61)]
            dentro = [(mx0 + x, my0 + y) for x, y in pts if 0 <= x <= mw and 0 <= y <= mh]
            if len(dentro) > 1:
                d.line(dentro, fill=(120, 130, 140), width=1)
            for xb, xx, ang in ((0, mx0 - 26, 90), (mw, mx0 + mw + 26, 270)):
                c = cruce(pts, 0, xb)
                if c and 0 <= c[1] <= mh:
                    _texto_rotado(lam, (xx, my0 + c[1]), grados(lat, True), f9, angulo=ang)
    paso_m = 10 ** 9 if ancho_km > 250 else next((k for k in (500, 1000, 2000, 2500, 5000, 10000, 20000, 25000, 50000, 100000, 200000, 250000, 500000)
                   if ancho_km * 1000 / k <= 7), 1000000)   # rutas largas (Cañete → sierra norte: ~700 km)
    gx = mr.X1 if ancho_km > 250 else math.ceil(mr.X0 / paso_m) * paso_m
    while gx < mr.X1:
        x, _ = mr.px(gx, mr.Y0)
        d.line([(mx0 + x, my0), (mx0 + x, my0 + mh)], fill=(120, 130, 140), width=1)
        for yy, anc in ((my0 - 10, "mb"), (my0 + mh + 10, "mt")):
            d.text((mx0 + x, yy), f"{gx:,.0f}".replace(",", " "), font=f9, fill=NEGRO, anchor=anc)
        d.line([(mx0 + x, my0 - 6), (mx0 + x, my0)], fill=NEGRO, width=2)
        d.line([(mx0 + x, my0 + mh), (mx0 + x, my0 + mh + 6)], fill=NEGRO, width=2)
        gx += paso_m
    gy = mr.Y1 if ancho_km > 250 else math.ceil(mr.Y0 / paso_m) * paso_m
    while gy < mr.Y1:
        _, y = mr.px(mr.X0, gy)
        d.line([(mx0, my0 + y), (mx0 + mw, my0 + y)], fill=(120, 130, 140), width=1)
        t = f"{gy:,.0f}".replace(",", " ")
        _texto_rotado(lam, (mx0 - 26, my0 + y), t, f9, angulo=90)
        _texto_rotado(lam, (mx0 + mw + 26, my0 + y), t, f9, angulo=270)
        d.line([(mx0 - 6, my0 + y), (mx0, my0 + y)], fill=NEGRO, width=2)
        d.line([(mx0 + mw, my0 + y), (mx0 + mw + 6, my0 + y)], fill=NEGRO, width=2)
        gy += paso_m
    d.rectangle([mx0, my0, mx0 + mw, my0 + mh], outline=NEGRO, width=3)
    d.rectangle([mx0 - ROT + 8, my0 - ROT + 8, mx0 + mw + ROT - 8, my0 + mh + ROT - 8], outline=NEGRO, width=1)

    # norte (rosa sobria)
    nx, ny = mx0 + 70, my0 + 78
    d.ellipse([nx - 46, ny - 46, nx + 46, ny + 46], fill=(255, 255, 255), outline=NEGRO, width=2)
    d.polygon([(nx, ny - 40), (nx - 16, ny + 6), (nx, ny - 4)], fill=NEGRO)
    d.polygon([(nx, ny - 40), (nx + 16, ny + 6), (nx, ny - 4)], fill=BLANCO, outline=NEGRO)
    d.polygon([(nx, ny + 40), (nx - 16, ny - 6), (nx, ny + 4)], fill=BLANCO, outline=NEGRO)
    d.polygon([(nx, ny + 40), (nx + 16, ny - 6), (nx, ny + 4)], fill=NEGRO)
    d.text((nx, ny - 54), "N", font=f13b, fill=NEGRO, anchor="mb", stroke_width=3, stroke_fill=BLANCO)

    # escala numérica (impresa en A3) y gráfica
    esc = (mr.X1 - mr.X0) / (mw / 150 * 0.0254)
    esc_red = next((v for v in (5000, 10000, 20000, 25000, 50000, 75000, 100000, 150000, 200000, 250000, 500000, 1000000,
                                2000000, 2500000, 3000000, 4000000, 5000000) if v >= esc * 0.92),
                   int(math.ceil(esc / 1e6) * 1e6))
    km_px = mw / ancho_km
    largo = next((k for k in (0.5, 1, 2, 4, 5, 10, 20, 40, 50, 100, 200, 250, 500) if k * km_px >= mw * 0.22), 1000)
    seg = largo * km_px / 4
    ex, ey = mx0 + 40, my0 + mh - 56
    d.rectangle([ex - 20, ey - 44, ex + 4 * seg + 66, ey + 40], fill=(255, 255, 255), outline=GRIS)
    d.text((ex, ey - 34), f"Escala 1:{esc_red:,}".replace(",", " ") + " (impresa en A3)", font=f10b, fill=NEGRO)
    for i in range(4):
        d.rectangle([ex + i * seg, ey, ex + (i + 1) * seg, ey + 11], fill=NEGRO if i % 2 == 0 else BLANCO, outline=NEGRO)
    for i in range(5):
        v = largo * i / 4
        d.text((ex + i * seg, ey + 16), f"{v:g}".replace(".", ","), font=f8, fill=NEGRO, anchor="mt")
    d.text((ex + 4 * seg + 14, ey + 16), "km", font=f8, fill=NEGRO, anchor="lt")

    # --- columna derecha
    cx0, cx1 = LW - M - COL, LW - M
    y = M
    titulo = (p.get("titulo") or "MAPA").upper()
    d.rectangle([cx0, y, cx1, y + 64], outline=NEGRO, width=3)
    for i, l in enumerate(_envolver(titulo, f13b, COL - 30, d)[:2]):
        d.text(((cx0 + cx1) / 2, y + (32 if len(_envolver(titulo, f13b, COL - 30, d)) == 1 else 19 + 26 * i)), l,
               font=f13b, fill=NEGRO, anchor="mm")
    y += 80

    # ubicación: Perú por departamentos
    lug = lugar(lat_c, lon_c)
    alto_ub = 430
    d.rectangle([cx0, y, cx1, y + alto_ub], outline=NEGRO, width=2)
    d.text((cx0 + 14, y + 12), "UBICACIÓN", font=f11b, fill=NEGRO)
    deps = _adm()["dep"]
    if deps:
        todo = unary_union([g for _, g in deps])
        bo, bs, be, bn = todo.bounds
        ix0, iy0, iw, ih = cx0 + 20, y + 44, COL - 40, alto_ub - 60
        k = min(iw / (be - bo), ih / (bn - bs))
        ox, oy = ix0 + (iw - (be - bo) * k) / 2, iy0 + (ih - (bn - bs) * k) / 2
        P = lambda lo, la: (ox + (lo - bo) * k, oy + (bn - la) * k)  # noqa: E731
        for nom, g in deps:
            col = (250, 204, 21) if _nombre_dep(nom) == lug["departamento"] else (226, 230, 235)
            for pol in getattr(g, "geoms", [g]):
                if pol.geom_type == "Polygon":
                    d.polygon([P(*c) for c in pol.exterior.coords], fill=col, outline=(120, 128, 140))
        px_, py_ = P(lon_c, lat_c)
        d.rectangle([px_ - 7, py_ - 7, px_ + 7, py_ + 7], outline=(220, 38, 38), width=3)
        d.text((cx1 - 14, y + alto_ub - 12), f"Dpto. de {lug['departamento']}", font=f9, fill=GRIS, anchor="rb")
    y += alto_ub + 14

    # leyenda
    leyenda = srv_ley + list(p.get("leyenda") or [])
    # zonas solo con contorno (láminas de satélite): en la leyenda también van como contorno
    if p.get("zonas") and all(not z.get("relleno") for z in p["zonas"]):
        leyenda = [({**it, "forma": "borde"} if str(it.get("texto", "")).startswith("Zona ") else it) for it in leyenda]
    if celda:
        leyenda.append({"color": "#dc2626", "texto": f"Cuadrícula 1:25 000 {celda.get('codigo', '')}", "forma": "borde"})
    if ruta:
        for t in ("pista", "trocha", "a_pie"):
            if any(b["tipo"] == t for b in ruta.get("bloques", [])):
                leyenda.append({"color": COLOR_TRAMO[t], "texto": NOMBRE_TRAMO[t], "forma": "linea" if t != "a_pie" else "punteada"})
    datos = list(p.get("datos") or []) + srv_datos
    tabla = ruta.get("bloques") if ruta else None
    y_fin_col = LH - M - MEMBRETE - 20
    def alto_item(it):
        if it.get("forma") == "titulo":
            return 30
        return 14 + 20 * max(1, min(3, len(_envolver(it.get("texto", ""), f9, COL - 104, d))))
    tope = int((y_fin_col - y) * (0.62 if any(it.get("forma") == "titulo" for it in leyenda) else 0.5))
    alto_ley = min(52 + sum(alto_item(it) for it in leyenda), tope if (datos or tabla) else y_fin_col - y)
    d.rectangle([cx0, y, cx1, y + alto_ley], outline=NEGRO, width=2)
    d.text((cx0 + 14, y + 12), "LEYENDA", font=f11b, fill=NEGRO)
    ly = y + 46
    for it in leyenda:
        if ly + alto_item(it) > y + alto_ley:
            d.text((cx0 + 16, ly + 2), "… (ver la página de descripción)" if tipo == "geologia_completa" else "…", font=f8, fill=GRIS)
            break
        forma = it.get("forma", "caja")
        if forma == "titulo":
            d.text((cx0 + 16, ly + 8), it.get("texto", ""), font=f9, fill=GRIS)
            d.line([(cx0 + 16, ly + 28), (cx1 - 16, ly + 28)], fill=GRIS_C, width=1)
            ly += 30
            continue
        col = _hex(it.get("color", "#888"))
        if forma == "borde":
            d.rectangle([cx0 + 16, ly + 3, cx0 + 60, ly + 25], outline=col, width=4)
        elif forma in ("linea", "punteada"):
            if forma == "linea":
                d.line([(cx0 + 16, ly + 14), (cx0 + 60, ly + 14)], fill=col, width=7)
            else:
                for k2 in range(0, 44, 14):
                    d.line([(cx0 + 16 + k2, ly + 14), (cx0 + 24 + k2, ly + 14)], fill=col, width=7)
        else:
            d.rectangle([cx0 + 16, ly + 2, cx0 + 76, ly + 28], fill=col, outline=NEGRO)
            if it.get("simbolo"):
                d.text((cx0 + 46, ly + 15), it["simbolo"][:9], font=f8, fill=NEGRO, anchor="mm")
        lineas = _envolver(it.get("texto", ""), f9, COL - 104, d)[:3]
        for i, l in enumerate(lineas):
            d.text((cx0 + 88, ly + 4 + 20 * i), l, font=f9, fill=NEGRO)
        ly += alto_item(it)
    y += alto_ley + 14

    # datos o tabla de la ruta
    if tabla is not None or datos:
        d.rectangle([cx0, y, cx1, y_fin_col], outline=NEGRO, width=2)
        nota = ("Nota: información referencial elaborada con datos públicos (INGEMMET, ESA Copernicus y otros). "
                "Verificar en campo y en INGEMMET antes de cualquier petitorio o inversión. Los índices satelitales "
                "describen la superficie; no reemplazan el muestreo ni el análisis de laboratorio.")
        lin = _envolver(nota, f8, COL - 32, d)
        alto_nota = 19 * len(lin) + 10          # la nota va al pie: lo demás termina antes
        if tabla is not None:
            d.text((cx0 + 14, y + 12), "TRAMOS DE LA RUTA", font=f11b, fill=NEGRO)
            ty = y + 48
            cols = [cx0 + 14, cx0 + 60, cx0 + 230, cx1 - 14]
            d.rectangle([cx0 + 8, ty - 6, cx1 - 8, ty + 24], fill=(236, 240, 244))
            for xx, t, an in zip(cols, ("N°", "Tipo", "Vía / detalle", "km"), ("la", "la", "la", "ra")):
                d.text((xx, ty), t, font=f10b, fill=NEGRO, anchor=an)
            ty += 32
            for i, b in enumerate(tabla, 1):
                if ty + 24 > y_fin_col - 92 - alto_nota:
                    d.text((cols[0], ty), f"… {len(tabla) - i + 1} tramos más", font=f9, fill=GRIS)
                    ty += 24
                    break
                d.rectangle([cols[0], ty + 4, cols[0] + 12, ty + 16], fill=COLOR_TRAMO.get(b["tipo"], GRIS))
                d.text((cols[0] + 20, ty), str(i), font=f9, fill=NEGRO)
                d.text((cols[1], ty), NOMBRE_TRAMO.get(b["tipo"], b["tipo"]), font=f9, fill=NEGRO)
                via = ", ".join(b.get("vias") or []) or (b.get("detalle") or "—")
                d.text((cols[2], ty), via[:26], font=f9, fill=GRIS)
                d.text((cols[3], ty), f"{b['km']:.2f}".replace(".", ","), font=f9, fill=NEGRO, anchor="ra")
                ty += 26
            ty = max(ty + 6, y_fin_col - 86 - alto_nota)
            d.line([(cx0 + 8, ty), (cx1 - 8, ty)], fill=NEGRO, width=1)
            for t, v in (("Distancia total por la ruta", ruta.get("km_total")),
                         ("Distancia en línea recta", ruta.get("km_linea_recta"))):
                d.text((cols[0], ty + 10), t, font=f10b, fill=NEGRO)
                d.text((cols[3], ty + 10), f"{v} km".replace(".", ","), font=f10b, fill=NEGRO, anchor="ra")
                ty += 32
        else:
            d.text((cx0 + 14, y + 12), "DATOS", font=f11b, fill=NEGRO)
            ty = y + 48
            for fila in datos:
                k2, v = fila[0], fila[1]
                if len(fila) > 2 and fila[2] == "lista":
                    # dos líneas a todo el ancho: nombre en negrita y detalle debajo
                    l1 = _envolver(str(k2), f9, COL - 34, d)[:1]
                    l2 = _envolver(str(v), f8, COL - 34, d)[:2]
                    alto = 22 + 18 * len(l2) + 6
                    if ty + alto > y_fin_col - 8 - alto_nota:
                        break
                    d.text((cx0 + 16, ty), l1[0] if l1 else "", font=_fuente(15, True), fill=NEGRO)
                    for i, l in enumerate(l2):
                        d.text((cx0 + 16, ty + 22 + 18 * i), l, font=f8, fill=GRIS)
                    ty += alto
                    d.line([(cx0 + 12, ty - 3), (cx1 - 12, ty - 3)], fill=GRIS_C, width=1)
                    continue
                lk = _envolver(str(k2), f9, 220, d)[:2]
                lv = _envolver(str(v), f10b, COL - 280, d)[:4]   # se mide con la negrita (la 1.ª línea va en negrita)
                alto = 10 + 20 * max(len(lk), len(lv))
                if ty + alto > y_fin_col - 8 - alto_nota:
                    break
                for i, l in enumerate(lk):
                    d.text((cx0 + 16, ty + 20 * i), l, font=f9, fill=GRIS)
                for i, l in enumerate(lv):
                    d.text((cx1 - 16, ty + 20 * i), l, font=f10b if i == 0 else f9, fill=NEGRO, anchor="ra")
                ty += alto
        for i, l in enumerate(lin):
            d.text((cx0 + 16, y_fin_col - 14 - (len(lin) - i) * 19), l, font=f8, fill=GRIS)

    # --- cajetín
    lugar_txt = f"{lug['provincia']}, {lug['departamento']}" if lug["provincia"] != "—" else lug["departamento"]
    _cajetin(lam, p, titulo, lugar_txt, mr.zona, f"1:{esc_red:,}".replace(",", " "))

    buf = BytesIO()
    lam.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def descripcion_geologica(p: dict) -> bytes:
    """Página A3 de texto: cada unidad geológica de la cuadrícula con su color, símbolo, nombre, litología, área y la
    DESCRIPCIÓN completa de la carta (GEOCATMIN). Mismo membrete que las láminas."""
    import geocatmin_rmi as g
    celda = p["celda"]
    o, s_, e, n = celda["oeste"], celda["sur"], celda["este"], celda["norte"]
    esc = p.get("escala") or "50K"
    uds = _geologia_unidades(box(o, s_, e, n), esc)
    por: dict[str, dict] = {}
    for u in sorted(uds, key=lambda u: -u["ha"]):
        k = u["etiqueta"] or u["unidad"]
        x = por.setdefault(k, {**u, "ha": 0.0})
        x["ha"] += u["ha"]
    # colores: los mismos de la lámina (se exporta la geología en la misma extensión)
    mr = Marco(o, s_, e, n, 1200, 900, margen=0.06)
    from mapa_geologico import CONFIG as _CFG
    cfg = _CFG.get(esc, _CFG["50K"])
    img = _exportar(f"{g.BASE}/{cfg['servicio']}/MapServer/export", mr.bbox, mr.epsg, (mr.W, mr.H), layers=f"show:{cfg['capa']}")
    ga = np.asarray(img) if img is not None else None
    for x in por.values():
        x["color"] = (200, 200, 200)
        if ga is not None:
            pt = x["inter"].representative_point()
            cx, cy = (int(v) for v in mr.geo_px(pt.x, pt.y))
            ven = ga[max(0, cy - 7):cy + 8, max(0, cx - 7):cx + 8].reshape(-1, 4)
            ven = ven[ven[:, 3] > 200]
            if len(ven) >= 10:
                x["color"] = tuple(int(v) for v in np.median(ven[:, :3], axis=0))
    unidades = orden_estratigrafico(list(por.values()))

    lam = Image.new("RGB", (LW, LH), BLANCO)
    d = ImageDraw.Draw(lam)
    f9, f10, f10b, f11b, f13b = _fuente(15), _fuente(17), _fuente(17, True), _fuente(19, True), _fuente(23, True)
    titulo = f"DESCRIPCIÓN DE LAS UNIDADES GEOLÓGICAS · CUADRÍCULA {celda.get('codigo', '')}"
    p = {**p, "subtitulo": ""}
    d.rectangle([M, M, LW - M, M + 64], outline=NEGRO, width=3)
    d.text((LW / 2, M + 32), titulo, font=f13b, fill=NEGRO, anchor="mm")
    y = M + 84
    # color+símbolo · unidad · edad · litología · descripción · espesor/ambiente · área
    cols = [M + 12, M + 96, M + 470, M + 800, M + 1080, LW - M - 330, LW - M - 130]
    d.rectangle([M, y, LW - M, y + 36], fill=(236, 240, 244))
    for xx, t in zip(cols[1:], ("UNIDAD", "EDAD", "LITOLOGÍA", "DESCRIPCIÓN (carta 1:" + ("50 000)" if esc == "50K" else "100 000)"), "ESPESOR · AMBIENTE")):
        d.text((xx, y + 9), t, font=f10b, fill=NEGRO)
    d.text((LW - M - 16, y + 9), "ÁREA", font=f10b, fill=NEGRO, anchor="ra")
    y += 44
    y_fin = LH - M - MEMBRETE - 20
    for u in unidades:
        nom = u["unidad"] or "—"
        lin_nom = _envolver(nom, f10, cols[2] - cols[1] - 16, d)[:3]
        lin_edad = _envolver(" · ".join(x for x in (edad_txt(u), u.get("piso"),
                             f"{u['emax']:g}–{u['emin']:g} Ma" if u.get("emin") is not None else "") if x) or "—", f9, cols[3] - cols[2] - 16, d)[:4]
        lin_lit = _envolver(u["lito"] or "—", f9, cols[4] - cols[3] - 16, d)[:3]
        lin_des = _envolver(u["descripcion"] or "—", f9, cols[5] - cols[4] - 16, d)
        lin_esp = _envolver(" · ".join(x for x in ((f"{u['grosor']} m" if u.get("grosor") else ""), u.get("ambiente") or "") if x) or "—",
                            f9, cols[6] - cols[5] - 16, d)[:4]
        alto = max(len(lin_nom) * 22, len(lin_edad) * 20, len(lin_lit) * 20, len(lin_des) * 20, len(lin_esp) * 20, 30) + 14
        if y + alto > y_fin:
            lin_des = lin_des[: max(1, (y_fin - y - 14) // 20)]
            alto = max(len(lin_nom) * 22, len(lin_edad) * 20, len(lin_lit) * 20, len(lin_des) * 20, 30) + 14
            if y + alto > y_fin:
                d.text((cols[1], y + 4), f"… y {len(unidades) - unidades.index(u)} unidades más (ver GEOCATMIN)", font=f9, fill=GRIS)
                break
        d.rectangle([cols[0], y + 4, cols[0] + 72, y + 32], fill=tuple(u["color"]), outline=NEGRO)
        d.text((cols[0] + 36, y + 18), (u["etiqueta"] or "—")[:9], font=_fuente(14, True), fill=NEGRO, anchor="mm")
        for i, l in enumerate(lin_nom):
            d.text((cols[1], y + 4 + 22 * i), l, font=f10, fill=NEGRO)
        for i, l in enumerate(lin_edad):
            d.text((cols[2], y + 5 + 20 * i), l, font=f9, fill=NEGRO)
        for i, l in enumerate(lin_lit):
            d.text((cols[3], y + 5 + 20 * i), l, font=f9, fill=NEGRO)
        for i, l in enumerate(lin_des):
            d.text((cols[4], y + 5 + 20 * i), l, font=f9, fill=GRIS)
        for i, l in enumerate(lin_esp):
            d.text((cols[5], y + 5 + 20 * i), l, font=f9, fill=NEGRO)
        d.text((LW - M - 16, y + 4), f"{u['ha']:,.0f} ha".replace(",", " "), font=f10, fill=NEGRO, anchor="ra")
        y += alto
        d.line([(M, y), (LW - M, y)], fill=GRIS_C, width=1)
    d.rectangle([M, M + 84, LW - M, y_fin], outline=NEGRO, width=2)

    lug = lugar((s_ + n) / 2, (o + e) / 2)
    lugar_txt = f"{lug['provincia']}, {lug['departamento']}" if lug["provincia"] != "—" else lug["departamento"]
    _cajetin(lam, {**p, "fuente": "INGEMMET · geología integrada (GEOCATMIN)"}, titulo, lugar_txt, mr.zona, "—")
    buf = BytesIO()
    lam.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def pagina_texto(p: dict) -> bytes:
    """Página A3 de texto en dos columnas con el cajetín de las láminas. p["secciones"] = [{titulo, parrafos[],
    vinetas[], tabla{cab[], filas[[]] , anchos[]}, imagenes[{archivo, pie}]}]."""
    lam = Image.new("RGB", (LW, LH), BLANCO)
    d = ImageDraw.Draw(lam)
    f_t, f_s, f_p, f_pb, f_m = _fuente(23, True), _fuente(21, True), _fuente(19), _fuente(19, True), _fuente(17)
    titulo = (p.get("titulo") or "").upper()
    d.rectangle([M, M, LW - M, M + 64], outline=NEGRO, width=3)
    d.text((LW / 2, M + 32), titulo, font=f_t, fill=NEGRO, anchor="mm")
    y0, y_fin = M + 90, LH - M - MEMBRETE - 24
    gap = 50
    colw = (LW - 2 * M - 40 - gap) // 2
    cols = [M + 20, M + 20 + colw + gap]
    d.line([(cols[1] - gap // 2, y0), (cols[1] - gap // 2, y_fin)], fill=GRIS_C, width=1)
    ci, y = 0, y0

    def espacio(h):
        nonlocal ci, y
        if y + h > y_fin:
            if ci == 1:
                return False
            ci, y = 1, y0
        return True

    for sec in p.get("secciones") or []:
        if sec.get("nueva_columna") and ci == 0:
            ci, y = 1, y0
        x = cols[ci]
        if sec.get("titulo"):
            if not espacio(70):
                break
            x = cols[ci]
            d.text((x, y + 6), sec["titulo"].upper(), font=f_s, fill=NEGRO)
            d.line([(x, y + 36), (x + colw, y + 36)], fill=NEGRO, width=2)
            y += 50
        for par in sec.get("parrafos") or []:
            lin = _envolver(par, f_p, colw, d)
            if not espacio(29 * len(lin) + 10):
                break
            x = cols[ci]
            for i, l in enumerate(lin):
                d.text((x, y + 29 * i), l, font=f_p, fill=NEGRO)
            y += 29 * len(lin) + 12
        for v in sec.get("vinetas") or []:
            neg, _, resto = v.partition("|")
            if not resto:
                neg, resto = "", neg
            # negrita (antes de «|») y luego el texto normal, en la MISMA línea, sin superponerse
            wneg = d.textlength(neg, font=f_pb) if neg else 0
            palabras, lin, act = resto.split(), [], ""
            ancho1 = colw - 26 - wneg
            for w_ in palabras:
                prueba = f"{act} {w_}".strip()
                lim = ancho1 if not lin else colw - 26
                if d.textlength(prueba, font=f_p) <= lim:
                    act = prueba
                else:
                    lin.append(act)
                    act = w_
            lin.append(act)
            if not espacio(29 * len(lin) + 6):
                break
            x = cols[ci]
            d.text((x + 4, y), "•", font=f_p, fill=NEGRO)
            if neg:
                d.text((x + 26, y), neg, font=f_pb, fill=NEGRO)
            for i, l in enumerate(lin):
                d.text((x + 26 + (wneg if i == 0 else 0), y + 29 * i), l, font=f_p, fill=NEGRO)
            y += 29 * len(lin) + 6
        y += 4
        tb = sec.get("tabla")
        if tb:
            an = tb.get("anchos") or [1 / len(tb["cab"])] * len(tb["cab"])
            xs_ = [0]
            for a in an:
                xs_.append(xs_[-1] + a * colw)
            if not espacio(34 + 26):
                break
            x = cols[ci]
            d.rectangle([x, y, x + colw, y + 34], fill=(236, 240, 244))
            for j, c in enumerate(tb["cab"]):
                d.text((x + xs_[j] + 6, y + 6), c, font=_fuente(16, True), fill=NEGRO)
            y += 32
            for fila in tb["filas"]:
                lins = [_envolver(str(c), f_m, int(an[j] * colw) - 12, d)[:2] for j, c in enumerate(fila)]
                h = 27 * max(len(l_) for l_ in lins) + 10
                if not espacio(h):
                    break
                x = cols[ci]
                for j, l_ in enumerate(lins):
                    for i, l in enumerate(l_):
                        d.text((x + xs_[j] + 6, y + 5 + 27 * i), l, font=f_m, fill=NEGRO)
                y += h
                d.line([(x, y), (x + colw, y)], fill=GRIS_C, width=1)
            if tb.get("nota"):
                lin = _envolver(tb["nota"], _fuente(13), colw, d)
                if espacio(20 * len(lin) + 8):
                    for i, l in enumerate(lin):
                        d.text((cols[ci], y + 6 + 20 * i), l, font=_fuente(13), fill=GRIS)
                    y += 20 * len(lin) + 10
            y += 14
        imgs = sec.get("imagenes") or []
        if imgs:
            w_ = (colw - 20 * (len(imgs) - 1)) // len(imgs)
            ims = []
            for im in imgs:
                try:
                    f = Image.open(im["archivo"]).convert("RGB")
                    f.thumbnail((w_, 520))
                    ims.append((f, im.get("pie", "")))
                except Exception:  # noqa: BLE001
                    continue
            if ims:
                h = max(f.height for f, _ in ims) + 70
                if espacio(h):
                    x = cols[ci]
                    for k, (f, pie) in enumerate(ims):
                        xx = x + k * (w_ + 20)
                        lam.paste(f, (int(xx), int(y)))
                        d.rectangle([xx, y, xx + f.width, y + f.height], outline=GRIS)
                        for i, l in enumerate(_envolver(pie, _fuente(13), w_, d)[:3]):
                            d.text((xx, y + f.height + 6 + 19 * i), l, font=_fuente(13), fill=GRIS)
                    y += h
    lug = p.get("_lugar") or "—"
    _cajetin(lam, {**p, "subtitulo": ""}, titulo, lug, p.get("_zona", 17), "—")
    buf = BytesIO()
    lam.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
