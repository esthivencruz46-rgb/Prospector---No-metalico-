"""Ruta de la fábrica a un punto, POR TRAMOS según el tipo de vía (sobre OpenStreetMap):

- «pista»:  vía asfaltada (Panamericana, nacionales, departamentales, calles pavimentadas);
- «trocha»: vía para carro SIN asfaltar (afirmado, ripio, tierra, trochas carrozables);
- «a_pie»:  desde donde se acaba la vía para carro hasta el punto: por senderos si los hay, o en
            línea recta (sin camino).

Motor: Valhalla (servidor público de FOSSGIS, uso ligero, sin clave), que da la superficie de
cada tramo (`trace_attributes`: unpaved, surface, use). Ruta en auto = la más rápida → prioriza la
Panamericana y las vías nacionales. Respaldo: OSRM (sin detalle de superficie: todo «pista»).
Para uso intensivo, montar Valhalla propio con el mapa del Perú y apuntar `VALHALLA_URL` a él.
No se calcula tiempo (no es fiable para camiones cargados): solo km por tramo.
"""

from __future__ import annotations

import os
import threading
import time
from math import asin, cos, radians, sin, sqrt

import requests

VALHALLA_URL = os.environ.get("VALHALLA_URL", "https://valhalla1.openstreetmap.de").rstrip("/")
OSRM_URL = os.environ.get("OSRM_URL", "https://router.project-osrm.org").rstrip("/")
_SES = requests.Session()
_SES.headers.update({"User-Agent": "ProspectorRMI/1.0 (rutas a planta; uso ligero)"})
_cache: dict[tuple, tuple[float, dict]] = {}
_candado = threading.Lock()
_ultima = [0.0]

TIPOS = {"pista": "Pista asfaltada", "trocha": "Trocha / afirmado (carro, sin asfaltar)",
         "a_pie": "A pie (sin vía para carro)"}
_SIN_ASFALTO = ("compacted", "dirt", "gravel", "path", "impassable", "unpaved")


# ------------------------------------------------------------------ utilidades
def km_linea_recta(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def decodificar_polyline(s: str, precision: int = 6) -> list[list[float]]:
    """Polyline codificada de Valhalla (precisión 6) → [[lon, lat], …]."""
    coords, i, lat, lon, f = [], 0, 0, 0, 10 ** precision
    while i < len(s):
        for eje in (0, 1):
            res, sh = 0, 0
            while True:
                b = ord(s[i]) - 63
                i += 1
                res |= (b & 0x1F) << sh
                sh += 5
                if b < 0x20:
                    break
            d = ~(res >> 1) if res & 1 else res >> 1
            if eje == 0:
                lat += d
            else:
                lon += d
        coords.append([lon / f, lat / f])
    return coords


def _largo_km(coords: list[list[float]]) -> float:
    return sum(km_linea_recta(a[1], a[0], b[1], b[0]) for a, b in zip(coords, coords[1:]))


def _pausa():
    """Los servidores públicos piden ~1 petición por segundo."""
    with _candado:
        espera = 1.0 - (time.time() - _ultima[0])
        if espera > 0:
            time.sleep(espera)
        _ultima[0] = time.time()


def tipo_de_tramo(e: dict) -> str:
    """Clasifica un tramo de Valhalla en «pista» o «trocha»."""
    sup = str(e.get("surface") or "").lower()
    if e.get("unpaved") or e.get("use") == "track" or any(s in sup for s in _SIN_ASFALTO):
        return "trocha"
    return "pista"


def _agrupar(tramos: list[dict]) -> list[dict]:
    """Une tramos consecutivos del mismo tipo en bloques (km, vías, geometría)."""
    bloques: list[dict] = []
    for t in tramos:
        if bloques and bloques[-1]["tipo"] == t["tipo"]:
            b = bloques[-1]
            b["km"] += t["km"]
            b["coords"].extend(t["coords"][1:] if b["coords"] and b["coords"][-1] == t["coords"][0] else t["coords"])
            for n in t["vias"]:
                b["km_via"][n] = b["km_via"].get(n, 0) + t["km"]
        else:
            bloques.append({"tipo": t["tipo"], "km": t["km"], "km_via": {n: t["km"] for n in t["vias"]},
                            "coords": list(t["coords"]), "detalle": t.get("detalle")})
    # retazos < 100 m entre dos bloques del mismo tipo (un puente, un tramo mal etiquetado): se absorben
    i = 1
    while i < len(bloques) - 1:
        a, b, c = bloques[i - 1], bloques[i], bloques[i + 1]
        if b["km"] < 0.1 and a["tipo"] == c["tipo"] != b["tipo"] and b["tipo"] != "a_pie":
            a["km"] += b["km"] + c["km"]
            a["coords"] += b["coords"][1:] + c["coords"][1:]
            for n, k in list(b["km_via"].items()) + list(c["km_via"].items()):
                a["km_via"][n] = a["km_via"].get(n, 0) + k
            del bloques[i:i + 2]
        else:
            i += 1
    out = []
    for b in bloques:
        if b["km"] < 0.005 or len(b["coords"]) < 2:
            continue
        # vías del bloque ordenadas por km recorridos (las de < 3 % del bloque no se nombran)
        vias = [n for n, k in sorted(b["km_via"].items(), key=lambda x: -x[1]) if k >= 0.03 * b["km"]][:4]
        out.append({"tipo": b["tipo"], "nombre": TIPOS[b["tipo"]], "km": round(b["km"], 2), "vias": vias,
                    "detalle": b.get("detalle"),
                    "geometria": {"type": "LineString", "coordinates": [[round(x, 6), round(y, 6)] for x, y in b["coords"]]}})
    return out


# ------------------------------------------------------------------ Valhalla
def _valhalla_ruta(lat1, lon1, lat2, lon2, costing: str) -> dict:
    _pausa()
    r = _SES.post(f"{VALHALLA_URL}/route", json={
        "locations": [{"lat": lat1, "lon": lon1, "search_cutoff": 20000},
                      {"lat": lat2, "lon": lon2, "search_cutoff": 30000}],
        "costing": costing, "units": "kilometers", "directions_type": "none"}, timeout=45)
    r.raise_for_status()
    return r.json()["trip"]


def _valhalla_atributos(shape: str) -> tuple[list[dict], list[list[float]]]:
    _pausa()
    r = _SES.post(f"{VALHALLA_URL}/trace_attributes", json={
        "encoded_polyline": shape, "costing": "auto", "shape_match": "edge_walk",
        "filters": {"attributes": ["edge.road_class", "edge.surface", "edge.unpaved", "edge.length", "edge.use",
                                   "edge.names", "edge.begin_shape_index", "edge.end_shape_index", "shape"],
                    "action": "include"}}, timeout=45)
    r.raise_for_status()
    j = r.json()
    return j.get("edges", []), decodificar_polyline(j.get("shape") or shape)


def _por_valhalla(lat1, lon1, lat2, lon2) -> dict:
    trip = _valhalla_ruta(lat1, lon1, lat2, lon2, "auto")
    shape = trip["legs"][0]["shape"]
    edges, coords = _valhalla_atributos(shape)
    tramos = []
    for e in edges:
        i0, i1 = e.get("begin_shape_index", 0), e.get("end_shape_index", 0)
        seg = coords[i0:i1 + 1]
        if len(seg) < 2:
            continue
        tramos.append({"tipo": tipo_de_tramo(e), "km": float(e.get("length") or _largo_km(seg)),
                       "vias": [n for n in (e.get("names") or []) if n][:2], "coords": seg})
    fin_carro = coords[-1] if coords else [lon1, lat1]

    # tramo A PIE: de donde termina la vía para carro hasta el punto
    falta = km_linea_recta(fin_carro[1], fin_carro[0], lat2, lon2)
    if falta > 0.05:
        pie = None
        try:
            tp = _valhalla_ruta(fin_carro[1], fin_carro[0], lat2, lon2, "pedestrian")
            pc = decodificar_polyline(tp["legs"][0]["shape"])
            largo = _largo_km(pc)
            # solo si arranca donde termina el carro y no da una vuelta grande; si no, en línea recta
            arranca_bien = km_linea_recta(pc[0][1], pc[0][0], fin_carro[1], fin_carro[0]) <= 0.3 if pc else False
            if len(pc) >= 4 and arranca_bien and largo <= 1.6 * falta + 0.5:
                pie = {"tipo": "a_pie", "km": largo, "vias": [], "coords": pc, "detalle": "por sendero o camino peatonal"}
        except Exception:  # noqa: BLE001
            pie = None
        if pie:
            tramos.append(pie)
            ult = pie["coords"][-1]
            resto = km_linea_recta(ult[1], ult[0], lat2, lon2)
            if resto > 0.05:
                tramos.append({"tipo": "a_pie", "km": resto, "vias": [], "coords": [ult, [lon2, lat2]],
                               "detalle": "sin camino (línea recta)"})
        else:
            tramos.append({"tipo": "a_pie", "km": falta, "vias": [], "coords": [fin_carro, [lon2, lat2]],
                           "detalle": "sin camino (línea recta)"})
    return {"bloques": _agrupar(tramos), "motor": "Valhalla · OpenStreetMap"}


# ------------------------------------------------------------------ respaldo OSRM
def _por_osrm(lat1, lon1, lat2, lon2) -> dict:
    _pausa()
    r = _SES.get(f"{OSRM_URL}/route/v1/driving/{lon1:.6f},{lat1:.6f};{lon2:.6f},{lat2:.6f}",
                 params={"overview": "full", "geometries": "geojson", "steps": "false"}, timeout=30)
    r.raise_for_status()
    j = r.json()
    if j.get("code") != "Ok" or not j.get("routes"):
        raise RuntimeError(f"OSRM: {j.get('code')}")
    rt = j["routes"][0]
    coords = rt["geometry"]["coordinates"]
    tramos = [{"tipo": "pista", "km": rt["distance"] / 1000, "vias": [], "coords": coords,
               "detalle": "sin detalle de superficie (servicio de respaldo)"}]
    fin = coords[-1]
    falta = km_linea_recta(fin[1], fin[0], lat2, lon2)
    if falta > 0.05:
        tramos.append({"tipo": "a_pie", "km": falta, "vias": [], "coords": [fin, [lon2, lat2]], "detalle": "sin camino (línea recta)"})
    return {"bloques": _agrupar(tramos), "motor": "OSRM · OpenStreetMap (sin detalle de superficie)"}


# ------------------------------------------------------------------ API
def ruta(lat1: float, lon1: float, lat2: float, lon2: float) -> dict:
    """Ruta de (lat1, lon1) —la fábrica— a (lat2, lon2) por bloques pista/trocha/a pie. Caché 7 días."""
    clave = tuple(round(v, 4) for v in (lat1, lon1, lat2, lon2))
    with _candado:
        v = _cache.get(clave)
        if v and time.time() - v[0] < 7 * 86400:
            return v[1]
    avisos = []
    try:
        r = _por_valhalla(lat1, lon1, lat2, lon2)
    except Exception as e:  # noqa: BLE001
        avisos.append(f"El servicio con detalle de superficie no respondió ({type(e).__name__}); "
                      "se usó uno sin ese detalle (todo figura como pista).")
        r = _por_osrm(lat1, lon1, lat2, lon2)
    bloques = r["bloques"]
    resumen = {t: round(sum(b["km"] for b in bloques if b["tipo"] == t), 2) for t in TIPOS}
    a_pie = resumen["a_pie"]
    if a_pie >= 0.5:
        avisos.append(f"Los últimos {a_pie:.1f} km no tienen vía para carro: habría que abrir una trocha de acceso.")
    res = {
        "km_total": round(sum(resumen.values()), 1),
        "km_carro": round(resumen["pista"] + resumen["trocha"], 1),
        "km_linea_recta": round(km_linea_recta(lat1, lon1, lat2, lon2), 1),
        "resumen": resumen,
        "tipos": TIPOS,
        "bloques": bloques,
        "destino": [round(lon2, 6), round(lat2, 6)],
        "fuente": r["motor"],
        "nota": ("Ruta en auto por las vías de OpenStreetMap (prioriza la Panamericana y vías nacionales). "
                 "La superficie (asfaltada o no) es la registrada en OpenStreetMap: puede faltar o estar desactualizada."),
        "avisos": avisos,
    }
    with _candado:
        _cache[clave] = (time.time(), res)
        if len(_cache) > 2000:
            for k in sorted(_cache, key=lambda k: _cache[k][0])[:500]:
                _cache.pop(k, None)
    return res
