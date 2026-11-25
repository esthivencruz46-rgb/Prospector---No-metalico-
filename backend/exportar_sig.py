"""Exportación SIG de una cuadrícula (24/11/2026): KMZ (Google Earth, GPS) o shapefile (QGIS, ArcGIS) con las capas
que sirven en campo, todas en WGS 84 (EPSG:4326):

  · limite        cuadrícula 1:25 000
  · zonas         zonas geológicas A/B/C (vectores de INGEMMET recortados a la cuadrícula)
  · prioridad     Prioridad libre (geología A/B − hierro − arcillas − áreas protegidas) por categoría: libre ·
                  concesión titulada/en trámite · chacra/poblado/vía · extinguido — se VECTORIZA la imagen que compuso la app
  · libres        zonas libres y utilizables, extinguidas y cada motivo de «libre pero no apto» (vectorizado de las máscaras)
  · protegidas    áreas protegidas y restringidas (vectores de INGEMMET / SERFOR)
  · concesiones   derechos mineros (vectores del catastro de INGEMMET)

Los rásteres se vectorizan con rasterio (si no está, por tramos de fila) y se simplifican a ~1 píxel.
"""
from __future__ import annotations

import base64
import math
import re
import zipfile
from io import BytesIO
from xml.sax.saxutils import escape

import numpy as np
from PIL import Image
from shapely.geometry import MultiPolygon, Polygon, box, mapping, shape
from shapely.ops import transform as sh_transform, unary_union

import geocatmin_rmi as g

PRJ_WGS84 = ('GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
             'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]')

# color de cada categoría (RGBA para el KML; el mismo de las láminas)
ESTILO = {
    "limite": ((220, 38, 38), 0), "A": ((220, 38, 38), 90), "B": ((245, 158, 11), 90), "C": ((250, 204, 21), 70),
    "prio_libre": ((22, 197, 94), 150), "prio_concesion": ((37, 99, 235), 130), "prio_no_apto": ((250, 204, 21), 130),
    "prio_extinguido": ((125, 211, 252), 140),
    "libre": ((22, 163, 74), 120), "extinguido": ((125, 211, 252), 130), "urbano": ((126, 34, 206), 130),
    "poblados": ((236, 72, 153), 120), "rios": ((14, 165, 233), 130), "vias": ((82, 82, 91), 130), "agua": ((37, 99, 235), 130),
    "cultivo": ((234, 179, 8), 130),
    "prohibido": ((220, 38, 38), 90), "restringido": ((217, 119, 6), 90),
    "titulado": ((37, 99, 235), 70), "en trámite (petitorio)": ((124, 58, 237), 70), "extinguido_c": ((100, 116, 139), 60),
    "otro": ((217, 70, 239), 60),
}
NOMBRE_MOTIVO = {"urbano": "Zona construida", "poblados": "A menos de 300 m de un centro poblado", "rios": "Faja de ríos y lagunas",
                 "vias": "Franja de carreteras", "agua": "Agua, bofedal o nieve", "cultivo": "Chacras y cultivos"}


# ------------------------------------------------------------------ vectorización
def _vectorizar(clases: np.ndarray, oeste: float, sur: float, este: float, norte: float) -> dict[int, object]:
    """{clase: (Multi)Polygon} de una grilla lineal en el recuadro dado (clase 0 = nada)."""
    alto, ancho = clases.shape
    px_x, px_y = (este - oeste) / ancho, (norte - sur) / alto
    out: dict[int, list] = {}
    try:
        from rasterio.features import shapes
        from rasterio.transform import from_bounds
        tr = from_bounds(oeste, sur, este, norte, ancho, alto)
        for geom, val in shapes(clases.astype(np.uint8), mask=clases > 0, transform=tr):
            out.setdefault(int(val), []).append(shape(geom))
    except ImportError:          # respaldo sin rasterio: tramos horizontales de cada fila
        for k in np.unique(clases[clases > 0]):
            m = clases == k
            cajas = []
            for f in range(alto):
                fila = np.concatenate([[False], m[f], [False]])
                cambios = np.flatnonzero(np.diff(fila.astype(np.int8)))
                for i0, i1 in zip(cambios[::2], cambios[1::2]):
                    cajas.append(box(oeste + i0 * px_x, norte - (f + 1) * px_y, oeste + i1 * px_x, norte - f * px_y))
            out[int(k)] = cajas
    tol = 0.6 * max(px_x, px_y)
    return {k: unary_union(v).simplify(tol, preserve_topology=True) for k, v in out.items()}


def _merc_a_geo(x, y, z=None):
    lon = np.degrees(np.asarray(x) / 6378137.0)
    lat = np.degrees(2 * np.arctan(np.exp(np.asarray(y) / 6378137.0)) - math.pi / 2)
    return lon, lat


def _poligonal(geom):
    """Solo la parte poligonal (los recortes pueden dejar líneas o puntos)."""
    if geom is None or geom.is_empty:
        return None
    if geom.geom_type in ("Polygon", "MultiPolygon"):
        return geom
    partes = [p for p in getattr(geom, "geoms", []) if p.geom_type in ("Polygon", "MultiPolygon")]
    return unary_union(partes) if partes else None


# ------------------------------------------------------------------ capas
def capas(p: dict) -> list[dict]:
    """[{id, nombre, features:[{geom, props, estilo}]}] de la cuadrícula. p: {celda, zonas, prioridad{png,bbox}}."""
    import libres as lib
    import restricciones as restr
    c = p["celda"]
    o, s, e, n = c["oeste"], c["sur"], c["este"], c["norte"]
    celda = box(o, s, e, n)
    out = [{"id": "limite", "nombre": f"Cuadrícula {c['codigo']}",
            "features": [{"geom": celda, "estilo": "limite", "props": {"codigo": c["codigo"], "escala": "1:25 000"}}]}]
    # zonas geológicas A/B/C
    fz = []
    for z in p.get("zonas") or []:
        try:
            geom = _poligonal(shape(z["geometria"]).intersection(celda))
        except Exception:  # noqa: BLE001
            continue
        if geom is None:
            continue
        fz.append({"geom": geom, "estilo": z.get("clase", "C"),
                   "props": {"clase": z.get("clase", ""), "unidad": z.get("unidad", ""), "litologia": z.get("litologia", "")[:250],
                             "area_ha": round(g.area_ha(geom), 1)}})
    if fz:
        out.append({"id": "zonas", "nombre": "Zonas geológicas A/B/C (INGEMMET)", "features": fz})
    # Prioridad libre: se vectoriza la imagen que compuso la app (colores = libres.PRIO_*)
    pr = p.get("prioridad") or {}
    if pr.get("png") and pr.get("bbox"):
        img = np.asarray(Image.open(BytesIO(base64.b64decode(pr["png"].split(",", 1)[-1]))).convert("RGBA")).astype(int)
        cls = np.zeros(img.shape[:2], np.uint8)
        cats = [(1, lib.PRIO_VERDE, "prio_libre", "Libre"), (2, lib.PRIO_AZUL, "prio_concesion", "En concesión titulada o en trámite"),
                (3, lib.PRIO_AMARILLO, "prio_no_apto", "Libre, pero chacra, poblado, vía o río"),
                (4, lib.PRIO_CELESTE, "prio_extinguido", "Sobre derecho extinguido")]
        for k, col, _, _ in cats:
            cls[(np.abs(img[..., :3] - np.array(col[:3])).max(axis=2) < 16) & (img[..., 3] > 100)] = k
        po, ps, pe, pn = pr["bbox"]
        polis = _vectorizar(cls, po, ps, pe, pn)
        fp = []
        for k, _, est, nom in cats:
            geom = _poligonal(polis.get(k).intersection(celda)) if k in polis else None
            if geom is not None:
                fp.append({"geom": geom, "estilo": est, "props": {"categoria": nom, "area_ha": round(g.area_ha(geom), 1)}})
        if fp:
            out.append({"id": "prioridad", "nombre": "Prioridad libre", "features": fp})
    # zonas libres (máscaras Web Mercator → polígonos WGS 84)
    w = 900
    h = max(64, int(w * (n - s) / (e - o)))
    mk = lib.mascaras(o, s, e, n, w, h)
    lz = lib.Lienzo(o, s, e, n, w, h)
    tierra = lz([celda]) & mk["tierra"]
    libre_legal = tierra & ~mk["ocupado"]
    cls = np.zeros((h, w), np.uint8)
    ya = np.zeros((h, w), bool)
    orden = ["urbano", "poblados", "rios", "vias", "agua", "cultivo"]
    for i, k in enumerate(orden, start=3):
        mm = libre_legal & mk[k] & ~ya
        cls[mm] = i
        ya |= mm
    util = libre_legal & ~ya
    cls[util & ~mk["extinguido"]] = 1
    cls[util & mk["extinguido"]] = 2
    polis = _vectorizar(cls, lz.x0, lz.y0, lz.x1, lz.y1)
    fl = []
    nombres = {1: ("libre", "Libre y utilizable"), 2: ("extinguido", "Libre: derecho extinguido (falta publicar la libre denunciabilidad)"),
               **{i: (k, f"Libre pero no apto: {NOMBRE_MOTIVO[k]}") for i, k in enumerate(orden, start=3)}}
    for k, geom in polis.items():
        geom = _poligonal(sh_transform(_merc_a_geo, geom).intersection(celda))
        if geom is None:
            continue
        est, nom = nombres[k]
        fl.append({"geom": geom, "estilo": est, "props": {"categoria": nom, "area_ha": round(g.area_ha(geom), 1)}})
    out.append({"id": "libres", "nombre": "Zonas libres para petitorio y aptas para cantera", "features": fl})
    # áreas protegidas y concesiones (vectores en vivo)
    fa = [{"geom": _poligonal(a["_geom"]), "estilo": a.get("nivel") or "restringido",
           "props": {"nombre": a["nombre"], "tipo": a["tipo"], "nivel": "no concesionable" if a.get("nivel") == "prohibido" else "restringido",
                     "categoria": a.get("categoria", ""), "norma": a.get("norma", ""), "area_ha": a["ha_en_cuadricula"]}}
          for a in restr.consultar(celda)]
    fa = [f for f in fa if f["geom"] is not None]
    out.append({"id": "protegidas", "nombre": "Áreas protegidas y restringidas", "features": fa})
    fc = []
    for k in lib.concesiones(celda):
        geom = _poligonal(k["_geom"])
        if geom is None:
            continue
        est = "extinguido_c" if k["estado"] == "extinguido" else k["estado"] if k["estado"] in ESTILO else "otro"
        fc.append({"geom": geom, "estilo": est,
                   "props": {"codigo": k["codigo"], "nombre": k["nombre"], "titular": k.get("titular") or "", "estado": k["estado"],
                             "sustancia": k.get("sustancia") or "", "ha_total": k.get("ha_total") or 0, "ha_celda": k["ha_en_cuadricula"],
                             "petitorio": k.get("fecha_petitorio") or ""}})
    out.append({"id": "concesiones", "nombre": "Concesiones mineras (catastro de INGEMMET)", "features": fc})
    return out


# ------------------------------------------------------------------ KMZ
def _kml_color(rgb, alfa: int) -> str:
    r, gg, b = rgb
    return f"{alfa:02x}{b:02x}{gg:02x}{r:02x}"        # KML: aabbggrr


def _kml_poligono(p: Polygon) -> str:
    def anillo(coords):
        return " ".join(f"{x:.6f},{y:.6f},0" for x, y in coords)
    s = f"<Polygon><outerBoundaryIs><LinearRing><coordinates>{anillo(p.exterior.coords)}</coordinates></LinearRing></outerBoundaryIs>"
    for h in p.interiors:
        s += f"<innerBoundaryIs><LinearRing><coordinates>{anillo(h.coords)}</coordinates></LinearRing></innerBoundaryIs>"
    return s + "</Polygon>"


def kmz(lista: list[dict], titulo: str) -> bytes:
    estilos = "".join(
        f'<Style id="{escape(k)}"><LineStyle><color>{_kml_color(col, 255)}</color><width>{3 if k == "limite" else 1.5}</width></LineStyle>'
        f'<PolyStyle><color>{_kml_color(col, a)}</color><fill>{1 if a else 0}</fill></PolyStyle></Style>' for k, (col, a) in ESTILO.items())
    carpetas = []
    for capa in lista:
        marcas = []
        for f in capa["features"]:
            polis = list(getattr(f["geom"], "geoms", [f["geom"]]))
            geo = "".join(_kml_poligono(q) for q in polis if q.geom_type == "Polygon")
            if not geo:
                continue
            if len(polis) > 1:
                geo = f"<MultiGeometry>{geo}</MultiGeometry>"
            props = f["props"]
            nombre = props.get("nombre") or props.get("categoria") or props.get("unidad") or props.get("codigo") or capa["nombre"]
            datos = "".join(f'<Data name="{escape(str(k))}"><value>{escape(str(v))}</value></Data>' for k, v in props.items())
            marcas.append(f"<Placemark><name>{escape(str(nombre))}</name><styleUrl>#{escape(f['estilo'])}</styleUrl>"
                          f"<ExtendedData>{datos}</ExtendedData>{geo}</Placemark>")
        carpetas.append(f"<Folder><name>{escape(capa['nombre'])}</name>{''.join(marcas)}</Folder>")
    kml = (f'<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
           f"<name>{escape(titulo)}</name>{estilos}{''.join(carpetas)}</Document></kml>")
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("doc.kml", kml.encode("utf-8"))
    return buf.getvalue()


# ------------------------------------------------------------------ shapefile
def _campo(nombre: str, usados: set) -> str:
    base = re.sub(r"[^A-Za-z0-9_]", "_", nombre)[:10] or "campo"
    k, i = base, 1
    while k.upper() in usados:
        k = f"{base[:8]}{i}"
        i += 1
    usados.add(k.upper())
    return k


def shp_zip(lista: list[dict], prefijo: str) -> bytes:
    """ZIP con un shapefile por capa (+ .prj WGS 84 y .cpg UTF-8)."""
    import shapefile   # pyshp
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for capa in lista:
            if not capa["features"]:
                continue
            shp, shx, dbf = BytesIO(), BytesIO(), BytesIO()
            w = shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=shapefile.POLYGON, encoding="utf-8")
            claves = list(dict.fromkeys(k for f in capa["features"] for k in f["props"]))
            usados: set = set()
            nombres = {}
            for k in claves:
                nombres[k] = _campo(k, usados)
                numerico = all(isinstance(f["props"].get(k), (int, float)) for f in capa["features"] if k in f["props"])
                if numerico:
                    w.field(nombres[k], "N", 18, 2)
                else:
                    w.field(nombres[k], "C", 254)
            for f in capa["features"]:
                partes = []
                for q in getattr(f["geom"], "geoms", [f["geom"]]):
                    if q.geom_type != "Polygon":
                        continue
                    ext = list(q.exterior.coords)
                    if Polygon(ext).exterior.is_ccw:      # shapefile: exterior en sentido horario
                        ext = ext[::-1]
                    partes.append(ext)
                    for h in q.interiors:
                        hh = list(h.coords)
                        if not Polygon(hh).exterior.is_ccw:
                            hh = hh[::-1]
                        partes.append(hh)
                if not partes:
                    continue
                w.poly(partes)
                w.record(*[f["props"].get(k, "" if not isinstance(f["props"].get(k), (int, float)) else 0) for k in claves])
            w.close()
            nom = f"{prefijo}_{capa['id']}"
            zf.writestr(nom + ".shp", shp.getvalue())
            zf.writestr(nom + ".shx", shx.getvalue())
            zf.writestr(nom + ".dbf", dbf.getvalue())
            zf.writestr(nom + ".prj", PRJ_WGS84)
            zf.writestr(nom + ".cpg", "UTF-8")
        zf.writestr("LEEME.txt", ("Capas de la cuadrícula en WGS 84 (EPSG:4326). Fuente: INGEMMET (geología, catastro, áreas reservadas), "
                                  "SERFOR, ESA Copernicus (Sentinel-2) y cobertura del suelo Sentinel-2 10 m. Información referencial: "
                                  "verificar en campo y en INGEMMET antes de cualquier petitorio.\n").encode("utf-8"))
    return buf.getvalue()


def exportar(p: dict) -> tuple[bytes, str, str]:
    """(bytes, media type, nombre de archivo)."""
    c = p["celda"]
    lista = capas(p)
    if p.get("formato") == "shp":
        return shp_zip(lista, c["codigo"].replace("-", "_")), "application/zip", f"{c['codigo']}_capas_shp.zip"
    return kmz(lista, f"Prospector RMI · cuadrícula {c['codigo']}"), "application/vnd.google-earth.kmz", f"{c['codigo']}_capas.kmz"
