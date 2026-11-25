"""Búsqueda por ÁREA en GEOCATMIN (INGEMMET) — adaptado de
MineLINK/backend/geocatmin.py, que consulta por punto/concesión.

Cascada para un material (hoy: arena silícea) dentro del polígono que
dibuja el geólogo:

1. Inventario RMI de INGEMMET: canteras y ocurrencias ya registradas del
   material (SERV_ROCAS_MINERALES_INDUSTRIALES). Es lo mejor que puede haber.
2. Geología 1:50 000 (SERV_GEOLOGIA_50K_INTEGRADA, capa 7 "Litología",
   campos UNIDAD, LITOLOGIA, DESCRIP): afloramientos cuya litología o
   formación es favorable (ver materiales.py).
3. Geología 1:100 000 (SERV_GEOLOGIA_100K_INTEGRADA, capa 6, campos
   UNIDAD, DESCRIP, NAME): SOLO si la 50K no tiene carta en el área o no
   encontró afloramientos favorables.

Lecciones heredadas de MineLINK (errores_aprendidos.md):
- GEOCATMIN no envía cabeceras CORS: el navegador no puede leer su JSON,
  por eso estas consultas viven en el backend.
- La codificación del servidor varía (UTF-8 real o latin-1): se decodifica
  UTF-8 estricto con respaldo latin-1 (`_json_de_respuesta`).
- La 50K es lenta (hasta ~25 s): timeout propio más largo.
"""

from __future__ import annotations

import json
import os
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
import requests
from pyproj import Transformer
from shapely.geometry import LinearRing, Point, Polygon, mapping
from shapely.geometry import shape as shape_geojson
from shapely.ops import transform as shp_transform
from shapely.ops import unary_union
from shapely.validation import make_valid

import re

from materiales import FORMACIONES, MATERIALES, clasificar, formaciones_de

BASE = os.environ.get("GEOCATMIN_BASE", "https://geocatmin.ingemmet.gob.pe/arcgis/rest/services")
_TIMEOUT = 25
_TIMEOUT_50K = 40
_LOTE_IDS = 400
# Generalización de geometrías que devuelve el servidor (grados, ~11 m):
# suficiente para un mapa de celular y reduce mucho el peso de la 50K.
_GENERALIZAR = 0.0001

GEOLOGIA = {
    "50K": {"servicio": "SERV_GEOLOGIA_50K_INTEGRADA", "capa": 7,
            # LITO1 = roca dominante del polígono (LITO2..5 las demás)
            "campos": "UNIDAD,LITOLOGIA,DESCRIP,LITO1,LITO2,LITO3", "timeout": _TIMEOUT_50K},
    "100K": {"servicio": "SERV_GEOLOGIA_100K_INTEGRADA", "capa": 6,
             "campos": "UNIDAD,DESCRIP,NAME", "timeout": _TIMEOUT},
}
RMI_SERVICIO = "SERV_ROCAS_MINERALES_INDUSTRIALES"

AREA_MAX_KM2 = float(os.environ.get("AREA_MAX_KM2", "2500"))

def bundle_ca() -> str:
    """Raíces de certifi + el intermedio de Sectigo que GEOCATMIN NO envía.

    El servidor de INGEMMET solo manda su certificado hoja (*.ingemmet.gob.pe)
    sin el intermedio "Sectigo Public Server Authentication CA OV R36".
    Windows/navegadores lo descargan solos (AIA); Python/requests no, y falla
    con CERTIFICATE_VERIFY_FAILED → todas las búsquedas "no respondieron".
    Se valida igual (no se desactiva la verificación): solo se completa la cadena."""
    import certifi
    import tempfile

    destino = os.path.join(tempfile.gettempdir(), "prospector_rmi_ca.pem")
    intermedio = os.path.join(os.path.dirname(os.path.abspath(__file__)), "certs", "sectigo_ov_r36.pem")
    with open(certifi.where(), "rb") as f:
        raices = f.read()
    with open(intermedio, "rb") as f:
        extra = f.read()
    with open(destino, "wb") as f:
        f.write(raices + b"\n" + extra)
    return destino


_SES = requests.Session()
_SES.headers.update({"User-Agent": "ProspectorRMI/1.0 (+geologia; contacto en README)"})
_SES.verify = bundle_ca()


class ErrorBusqueda(Exception):
    """Error mostrable al usuario (área inválida, demasiado grande…)."""


# ---------------------------------------------------------------- HTTP
def _json_de_respuesta(r) -> dict:
    """Igual que MineLINK: UTF-8 estricto, respaldo latin-1."""
    try:
        return json.loads(r.content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return json.loads(r.content.decode("latin-1"))


def _post(url: str, data: dict, timeout: int, intentos: int = 3) -> dict:
    ultimo: Exception | None = None
    for i in range(intentos):
        try:
            r = _SES.post(url, data=data, timeout=timeout)
            r.raise_for_status()
            j = _json_de_respuesta(r)
            if isinstance(j, dict) and "error" in j:
                raise RuntimeError(f"ArcGIS: {j['error']}")
            return j
        except Exception as e:  # noqa: BLE001
            ultimo = e
            time.sleep(1.0 * (i + 1))
    raise RuntimeError(f"{url} -> {ultimo}")


def _get(url: str, params: dict, timeout: int = _TIMEOUT) -> dict:
    r = _SES.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return _json_de_respuesta(r)


def query_en_poligono(servicio: str, capa: int, anillo: list, campos: str,
                      timeout: int = _TIMEOUT, con_geometria: bool = True,
                      max_obj: int = 6000, where: str = "1=1") -> list[dict]:
    """Todas las entidades de la capa que intersectan el polígono.
    Pagina por objectIds (no depende de que el servidor soporte
    resultOffset) y usa POST (el polígono puede ser largo para una URL)."""
    url = f"{BASE}/{servicio}/MapServer/{capa}/query"
    geom = json.dumps({"rings": [anillo], "spatialReference": {"wkid": 4326}})
    base = {"geometry": geom, "geometryType": "esriGeometryPolygon",
            "spatialRel": "esriSpatialRelIntersects", "inSR": 4326, "f": "json"}
    ids = _post(url, {**base, "where": where, "returnIdsOnly": "true"}, timeout).get("objectIds") or []
    if len(ids) > max_obj:
        raise ErrorBusqueda(
            f"El área tiene demasiados polígonos ({len(ids)}). Dibuja un área más pequeña.")
    feats: list[dict] = []
    for i in range(0, len(ids), _LOTE_IDS):
        lote = sorted(ids)[i:i + _LOTE_IDS]
        j = _post(url, {"objectIds": ",".join(map(str, lote)), "outFields": campos,
                        "returnGeometry": "true" if con_geometria else "false",
                        "outSR": 4326, "maxAllowableOffset": _GENERALIZAR,
                        "f": "json"}, timeout)
        feats.extend(j.get("features") or [])
    return feats


# ---------------------------------------------------------- GEOMETRÍA
def _zona_utm(lon: float) -> int:
    return int((lon + 180) // 6) + 1


_TRANS: dict[int, Transformer] = {}


def area_ha(geom) -> float:
    if geom is None or geom.is_empty:
        return 0.0
    z = _zona_utm(geom.representative_point().x)
    if z not in _TRANS:
        _TRANS[z] = Transformer.from_crs(4326, 32700 + z, always_xy=True)
    t = _TRANS[z]
    try:
        import numpy as np
        import shapely
        g = shapely.transform(geom, lambda xy: np.column_stack(t.transform(xy[:, 0], xy[:, 1])))
    except Exception:  # noqa: BLE001  (shapely < 2.0)
        g = shp_transform(t.transform, geom)
    return g.area / 10000.0


def _limpiar(g):
    if g is None or g.is_empty:
        return g
    if not g.is_valid:
        g = make_valid(g)
    if g.geom_type == "GeometryCollection":
        polis = [x for x in g.geoms if x.geom_type in ("Polygon", "MultiPolygon")]
        g = unary_union(polis) if polis else Polygon()
    return g


def esri_a_shapely(g: dict, recorte=None):
    """Esri JSON (wkid 4326) → shapely. Anillos horarios = exteriores.

    `recorte` (geometría shapely, opcional): se descartan antes los anillos cuyo recuadro no lo
    toca. Algunas entidades de GEOCATMIN son UN polígono para todo el país (p. ej. la faja
    marginal de ríos, capa 21 de áreas reservadas: 2,4 MB y miles de anillos) y armarlo entero
    tardaba > 2 min por cuadrícula."""
    if not g:
        return None
    if "x" in g:
        return Point(g["x"], g["y"]) if g["x"] is not None else None
    if "rings" not in g:
        return None
    caja = recorte.bounds if recorte is not None else None
    externos, huecos = [], []
    for ring in g["rings"]:
        if len(ring) < 4:
            continue
        xs = [p[0] for p in ring]
        ys = [p[1] for p in ring]
        rb = (min(xs), min(ys), max(xs), max(ys))
        if caja and (rb[2] < caja[0] or rb[0] > caja[2] or rb[3] < caja[1] or rb[1] > caja[3]):
            continue
        try:
            (huecos if LinearRing(ring).is_ccw else externos).append([ring, [], rb, None])
        except Exception:  # noqa: BLE001
            continue
    for h in huecos:
        hp = Polygon(h[0])
        rp = hp.representative_point()
        for ext in externos:
            eb = ext[2]
            if not (eb[0] <= rp.x <= eb[2] and eb[1] <= rp.y <= eb[3]):
                continue      # descarte barato por recuadro antes de armar el polígono
            if ext[3] is None:
                ext[3] = Polygon(ext[0])
            if ext[3].contains(rp):
                ext[1].append(h[0])
                break
        else:
            externos.append([h[0], [], h[2], hp])
    polis = []
    for ext, hs, _, _ in externos:
        try:
            polis.append(_limpiar(Polygon(ext, hs)))
        except Exception:  # noqa: BLE001
            pass
    return _limpiar(unary_union(polis)) if polis else None


def validar_poligono(anillo: list) -> Polygon:
    if not anillo or len(anillo) < 3:
        raise ErrorBusqueda("El área necesita al menos 3 vértices.")
    try:
        pts = [(float(p[0]), float(p[1])) for p in anillo]
    except Exception as e:  # noqa: BLE001
        raise ErrorBusqueda("Coordenadas inválidas.") from e
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    if not all(-82 <= x <= -68 and -19 <= y <= 0.5 for x, y in pts):
        raise ErrorBusqueda("El área debe estar dentro del Perú.")
    pol = _limpiar(Polygon(pts))
    if pol.is_empty:
        raise ErrorBusqueda("El polígono no es válido (¿se cruzan sus lados?).")
    km2 = area_ha(pol) / 100
    if km2 > AREA_MAX_KM2:
        raise ErrorBusqueda(
            f"El área mide {km2:,.0f} km²; el máximo es {AREA_MAX_KM2:,.0f} km². "
            "Acércate y dibuja una zona más pequeña.")
    return pol


def _anillo_esri(pol: Polygon) -> list:
    """Anillo exterior en sentido horario (convención Esri)."""
    if pol.geom_type == "MultiPolygon":
        pol = max(pol.geoms, key=lambda p: p.area)
    coords = list(pol.exterior.coords)
    if LinearRing(coords).is_ccw:
        coords.reverse()
    return [[round(x, 6), round(y, 6)] for x, y in coords]


def _geojson(geom, decimales: int = 6) -> dict:
    g = geom.simplify(0.00005, preserve_topology=True)

    def redondear(c):
        if isinstance(c, (list, tuple)) and c and isinstance(c[0], (int, float)):
            return [round(c[0], decimales), round(c[1], decimales)]
        return [redondear(x) for x in c]

    m = mapping(g)
    return {"type": m["type"], "coordinates": redondear(m["coordinates"])}


# ------------------------------------------------------------- RMI
_CACHE_CAPAS: dict[str, list] = {}


def _sin_tildes(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(c) != "Mn").upper()


# ------------------------------------------------- CATÁLOGO DE FORMACIONES
_CACHE_HOJAS: dict[str, list] = {}


def hojas_de_formacion(material: str, fid: str) -> list[dict]:
    """Hojas 1:50 000 (CODHOJA, p. ej. "27k4") donde aparece el ítem del
    catálogo, con cuántos polígonos tiene en cada una."""
    item = next((f for f in FORMACIONES.get(material, []) if f["id"] == fid), None)
    if not item:
        raise ErrorBusqueda("Formación desconocida.")
    return hojas_por_sql(f"{material}:{fid}", item["sql50"])


def hojas_por_sql(clave: str, sql50: str) -> list[dict]:
    """Hojas 1:50 000 con polígonos que cumplen el filtro (agrupado en GEOCATMIN)."""
    if clave not in _CACHE_HOJAS:
        url = f"{BASE}/{GEOLOGIA['50K']['servicio']}/MapServer/{GEOLOGIA['50K']['capa']}/query"
        j = _post(url, {"f": "json", "where": sql50, "returnGeometry": "false",
                        "groupByFieldsForStatistics": "CODHOJA",
                        "outStatistics": json.dumps([{"statisticType": "count", "onStatisticField": "OBJECTID",
                                                      "outStatisticFieldName": "N"}])}, _TIMEOUT_50K)
        hojas = []
        for f in j.get("features") or []:
            a = {k.upper(): v for k, v in (f.get("attributes") or {}).items()}
            if a.get("CODHOJA"):
                hojas.append({"hoja": str(a["CODHOJA"]).strip(), "poligonos": int(a.get("N") or 0)})
        _CACHE_HOJAS[clave] = sorted(hojas, key=lambda h: h["hoja"])
    return _CACHE_HOJAS[clave]


_CACHE_HOJAS100: list[dict] = []


def hojas_100k() -> list[dict]:
    """Las 501 hojas 1:100 000 de la Carta Nacional con su nombre
    (p. ej. 27-k Chincha), para buscar cuadrángulos por nombre."""
    if not _CACHE_HOJAS100:
        j = _get(f"{BASE}/{GEOLOGIA['100K']['servicio']}/MapServer/0/query",
                 {"f": "json", "where": "1=1", "outFields": "QDR_CODIGO_ALFANUMERICO,QDR_NOMBRE",
                  "returnGeometry": "false"})
        for f in j.get("features") or []:
            a = f.get("attributes") or {}
            if a.get("QDR_CODIGO_ALFANUMERICO"):
                _CACHE_HOJAS100.append({"codigo": str(a["QDR_CODIGO_ALFANUMERICO"]).strip(),
                                        "nombre": str(a.get("QDR_NOMBRE") or "").strip()})
    return _CACHE_HOJAS100


# --------------------------------------------------------- GEOLOGÍA
def buscar_geologia(material: str, pol: Polygon, escala: str) -> dict:
    """Polígonos de la escala dada dentro del área, clasificados. Devuelve
    {"cobertura": bool, "afloramientos": [...], "n_poligonos": int}."""
    cfg = GEOLOGIA[escala]
    import geologia_local as gl   # diferido: ese módulo importa este
    if gl.disponible(escala):     # copia local descargada: no depende de que GEOCATMIN responda
        feats = gl.features(escala, pol)
    else:
        feats = query_en_poligono(cfg["servicio"], cfg["capa"], _anillo_esri(pol),
                                  cfg["campos"], timeout=cfg["timeout"])
    grupos: dict[tuple, dict] = {}
    excluir = MATERIALES[material].get("excluir")
    excluidas = []   # polígonos de roca ígnea/volcánica (sirven para no traer zonas «solo 100K» encima)
    todos, arenas = [], []   # todos los polígonos / los no favorables que describen arena suelta
    for f in feats:
        a = f.get("attributes") or {}
        clase = clasificar(material, a)
        # copia local: la geometría ya viene en shapely; GEOCATMIN: Esri JSON (se convierte UNA vez)
        ge0 = f["_shapely"] if "_shapely" in f else esri_a_shapely(f.get("geometry"))
        if ge0 is not None and not ge0.is_empty:
            todos.append(ge0)
            if not clase and tipo_material(a) == "arena":
                arenas.append(ge0)
        if not clase:
            if excluir:
                txt = _sin_tildes(f"{a.get('LITO1') or ''} {a.get('LITOLOGIA') or a.get('DESCRIP') or ''}").upper()
                lito1 = _sin_tildes(str(a.get("LITO1") or "")).upper()
                if re.search(excluir, lito1 if lito1 not in ("", "<NULL>", "NULL") else txt):
                    if ge0 is not None and not ge0.is_empty:
                        excluidas.append(ge0)
            continue
        g = ge0
        if g is None or g.is_empty:
            continue
        g = _limpiar(g.intersection(pol))
        if g is None or g.is_empty:
            continue
        clave = (clase[0], str(a.get("UNIDAD") or "").strip(),
                 str(a.get("LITOLOGIA") or a.get("DESCRIP") or "").strip()[:200])
        grupo = grupos.setdefault(clave, {"clase": clase[0], "motivo": clase[1],
                                          "atributos": a, "geoms": []})
        grupo["geoms"].append(g)

    afl = []
    for (clase, unidad, _), grupo in grupos.items():
        g = _limpiar(unary_union(grupo["geoms"]))
        ha = area_ha(g)
        if ha < 0.5:
            continue
        a = grupo["atributos"]
        c = g.representative_point()
        lito1 = str(a.get("LITO1") or "").strip()
        afl.append({
            "clase": clase, "motivo": grupo["motivo"], "escala": escala,
            "unidad": unidad or a.get("NAME") or "—",
            "formaciones": formaciones_de(material, a),
            "roca_dominante": "" if lito1.upper() in ("", "<NULL>", "NULL") else lito1,
            # rocas principal, secundaria y terciaria de la 50K (LITO1–3); la 100K no las tiene
            "rocas": [r for r in (str(a.get(k) or "").strip() for k in ("LITO1", "LITO2", "LITO3"))
                      if r and r.upper() not in ("<NULL>", "NULL", "-")],
            "litologia": a.get("LITOLOGIA") or "",
            "descripcion": a.get("DESCRIP") or a.get("NAME") or "",
            "area_ha": round(ha, 1), "partes": len(getattr(g, "geoms", [g])),
            "centro": [round(c.x, 6), round(c.y, 6)],
            "geometria": _geojson(g),
        })
    afl.sort(key=lambda x: ({"A": 0, "B": 1, "C": 2}[x["clase"]], -x["area_ha"]))
    for i, x in enumerate(afl, 1):
        x["id"] = f"{escala}-{i:03d}"
    def u(gs):
        return _limpiar(unary_union(gs).buffer(0).intersection(pol)) if gs else None
    return {"cobertura": len(feats) > 0, "n_poligonos": len(feats), "afloramientos": afl,
            "_excluidas": u(excluidas), "_todos": u(todos), "_arenas": u(arenas)}


_RX_ARENA = re.compile(r"\bARENAS?\b|E[OÓ]LIC|\bDUNAS?\b")
_RX_ROCA = re.compile(r"ARENISC|CUARCIT|CUARZOARENIT")


def tipo_material(a: dict) -> str | None:
    """«arena» (suelta: eólica, dunas, arenas) o «roca» (arenisca, cuarcita): para no mezclar
    una arena eólica de la 100K con una arenisca de la 50K (o al revés)."""
    # con roca dominante (LITO1 de la 50K) manda ella: «Arcilla, arena» con arenas eólicas encima NO es arena
    dom = str(a.get("LITO1") or a.get("roca_dominante") or "").strip()
    if dom and dom.upper() not in ("<NULL>", "NULL"):
        t = _sin_tildes(dom).upper()
        return "roca" if _RX_ROCA.search(t) else "arena" if _RX_ARENA.search(t) else None
    t = _sin_tildes(" ".join(str(a.get(k) or "") for k in ("UNIDAD", "LITO1", "LITOLOGIA", "DESCRIP",
                                                              "unidad", "litologia", "descripcion"))).upper()
    if _RX_ROCA.search(t):
        return "roca"
    if _RX_ARENA.search(t):
        return "arena"
    return None


# ----------------------------------------------------------- CASCADA
def buscar(material: str, anillo: list) -> dict:
    cfg = MATERIALES.get(material)
    if not cfg:
        raise ErrorBusqueda("Material desconocido.")
    if not cfg.get("activo"):
        raise ErrorBusqueda(f"{cfg['nombre']}: disponible próximamente.")
    pol = validar_poligono(anillo)
    t0 = time.time()
    avisos: list[str] = []

    import concesiones_info as ci  # importaciones diferidas: esos módulos importan este
    import libres as lib
    import restricciones as restr

    with ThreadPoolExecutor(6) as ex:
        f_50 = ex.submit(buscar_geologia, material, pol, "50K")
        # REGLA DEL USUARIO (23/11/2026): si hay hoja 1:50 000 en el área se usa SOLO la 50K (aunque no tenga
        # zonas silíceas); la 1:100 000 se consulta únicamente donde no hay 50K.
        f_res = ex.submit(restr.consultar, pol)  # áreas protegidas/restringidas, en paralelo
        f_con = ex.submit(lib.concesiones, pol)  # derechos mineros (catastro), en paralelo
        f_peru = ex.submit(lib.contorno_peru)    # precarga (caché de una semana)
        rmi: list = []   # las muestras RMI de INGEMMET ya no se consultan (pedido del usuario, 21/11/2026)
        try:
            g50 = f_50.result()
        except ErrorBusqueda:
            raise
        except Exception as e:  # noqa: BLE001
            g50 = {"cobertura": False, "n_poligonos": 0, "afloramientos": [], "error": True}
            avisos.append(f"La geología 50K no respondió ({type(e).__name__}); se usa 100K.")
        try:
            areas = f_res.result()
        except Exception as e:  # noqa: BLE001
            areas = None
            avisos.append(f"No se pudo consultar las áreas protegidas/restringidas ({type(e).__name__}): revísalas en el mapa.")
        try:
            cons = f_con.result()
        except Exception as e:  # noqa: BLE001
            cons = None
            avisos.append(f"No respondió el catastro minero ({type(e).__name__}): no se calcularon las áreas libres.")
        try:
            f_peru.result()
        except Exception:  # noqa: BLE001
            pass
        g100 = None
        if not g50["cobertura"]:
            try:
                g100 = buscar_geologia(material, pol, "100K")
            except ErrorBusqueda:
                raise
            except Exception as e:  # noqa: BLE001
                g100 = {"cobertura": False, "n_poligonos": 0, "afloramientos": []}
                avisos.append(f"La geología 100K no respondió ({type(e).__name__}).")

    # áreas libres: solo si se tienen AMBOS (sin uno de ellos no se puede afirmar que algo está libre)
    libres = None
    if cons is not None and areas is not None:
        try:
            libres = lib.calcular(pol, cons, areas)
        except Exception as e:  # noqa: BLE001
            avisos.append(f"No se pudo calcular las áreas libres ({type(e).__name__}).")

    if g50["cobertura"]:
        if g50["afloramientos"]:
            escala, geo = "50K", g50
            motivo_escala = "Carta 1:50 000 (hay hoja 1:50 000: no se usa la 1:100 000)."
        else:
            escala, geo = None, {"afloramientos": []}
            motivo_escala = "La carta 1:50 000 no muestra zonas silíceas aquí (con hoja 1:50 000 no se usa la 1:100 000)."
    elif g100 and g100["afloramientos"]:
        escala, geo = "100K", g100
        motivo_escala = ("La 1:50 000 no respondió; se usó la 1:100 000." if g50.get("error")
                         else "La carta 1:50 000 no cubre esta área: se usó la 1:100 000.")
    else:
        escala, geo = None, {"afloramientos": []}
        motivo_escala = "No hay hoja 1:50 000 y la 1:100 000 no muestra zonas silíceas aquí."

    # ¿cuánto de cada zona favorable cae en un área protegida o restringida?
    if areas:
        for a in geo["afloramientos"]:
            try:
                a["restriccion"] = restr.en_zona(areas, shape_geojson(a["geometria"]))
            except Exception:  # noqa: BLE001
                a["restriccion"] = None
    if libres:
        for a in geo["afloramientos"]:
            try:
                geom = shape_geojson(a["geometria"])
                a["libre_pct"] = lib.libre_en_zona(libres, geom)
                a["util_pct"] = lib.util_en_zona(libres, geom)
                a["negociable_pct"] = lib.negociable_en_zona(libres, geom)   # titulado / en trámite, apto
                a["concesiones"] = ci.en_zona(cons or [], geom)   # derechos mineros que tocan la zona
            except Exception:  # noqa: BLE001
                a["libre_pct"] = a["util_pct"] = None

    # qué geología favorable tiene debajo cada derecho minero (indicio de qué extrae una no metálica)
    if cons:
        try:
            ci.geologia_debajo(cons, geo["afloramientos"])
            if libres:
                libres["concesiones"] = [{k: v for k, v in x.items() if not k.startswith("_")} for x in cons]
        except Exception:  # noqa: BLE001
            pass

    c = pol.representative_point()
    return {
        "restricciones": restr.publicas(areas) if areas is not None else None,
        "libres": lib.publico(libres),
        "material": material, "material_nombre": cfg["nombre"],
        "area_km2": round(area_ha(pol) / 100, 2),
        "centro": [round(c.x, 6), round(c.y, 6)],
        "rmi": rmi,
        "escala_usada": escala, "motivo_escala": motivo_escala,
        "cobertura_50k": g50["cobertura"],
        "afloramientos": geo["afloramientos"],
        # la 1:100 000 ya NO se usa junto a la 50K (regla del usuario, 23/11/2026): se deja vacío por compatibilidad
        "afloramientos_100k": [],
        "resumen": {
            "rmi": len(rmi),
            "clase_A": sum(1 for x in geo["afloramientos"] if x["clase"] == "A"),
            "clase_B": sum(1 for x in geo["afloramientos"] if x["clase"] == "B"),
            "clase_C": sum(1 for x in geo["afloramientos"] if x["clase"] == "C"),
            "ha_favorables": round(sum(x["area_ha"] for x in geo["afloramientos"]), 1),
        },
        "avisos": avisos,
        "segundos": round(time.time() - t0, 1),
        "fuente": "GEOCATMIN · INGEMMET (información referencial)",
    }
