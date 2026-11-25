"""Copia LOCAL de la geología de INGEMMET (1:50 000 capa 7 y 1:100 000 capa 6 de GEOCATMIN).

La geología casi no cambia: se descarga una vez (`python scripts/descargar_geologia.py`) y
`geocatmin_rmi.buscar_geologia` la lee de aquí, sin depender de que GEOCATMIN responda.
Las concesiones y áreas protegidas NO se copian: cambian a diario y siguen en vivo.

Archivo: backend/datos/geologia.sqlite (o GEOLOGIA_DB). Tablas:
  pol(id, escala, oid, attrs JSON, wkb)  +  idx (R*Tree de recuadros)  +  meta(clave, valor)
Una escala se usa solo cuando su descarga terminó (meta «completo_50K» / «completo_100K»).
Con el servidor simulado de las pruebas (GEOCATMIN_BASE ≠ el real) NO se usa la copia local.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time

from shapely import wkb as shp_wkb

import geocatmin_rmi as g

RUTA = os.environ.get("GEOLOGIA_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos", "geologia.sqlite"))
REAL = "https://geocatmin.ingemmet.gob.pe/arcgis/rest/services"
LOTE = 400
_local = threading.local()


def _con(ruta: str = RUTA) -> sqlite3.Connection:
    """Una conexión por hilo (sqlite3 no comparte conexiones entre hilos)."""
    c = getattr(_local, "con", None)
    if c is None or getattr(_local, "ruta", None) != ruta:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        c = sqlite3.connect(ruta, timeout=60)
        c.execute("CREATE TABLE IF NOT EXISTS pol (id INTEGER PRIMARY KEY, escala TEXT, oid INTEGER, attrs TEXT, wkb BLOB)")
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS pol_oid ON pol(escala, oid)")
        c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS idx USING rtree(id, minx, maxx, miny, maxy)")
        c.execute("CREATE TABLE IF NOT EXISTS meta (clave TEXT PRIMARY KEY, valor TEXT)")
        _local.con, _local.ruta = c, ruta
    return c


def _meta(clave: str, ruta: str = RUTA) -> str | None:
    if not os.path.exists(ruta):
        return None
    r = _con(ruta).execute("SELECT valor FROM meta WHERE clave = ?", (clave,)).fetchone()
    return r[0] if r else None


def disponible(escala: str, ruta: str = RUTA) -> bool:
    """¿Hay copia local COMPLETA de esa escala y se está usando el GEOCATMIN real?"""
    if g.BASE.rstrip("/") != REAL and ruta == RUTA:
        return False
    try:
        return _meta(f"completo_{escala}", ruta) is not None
    except sqlite3.Error:
        return False


def estado(ruta: str = RUTA) -> dict:
    """Para /health y la app: fecha de cada escala descargada y nº de polígonos."""
    out = {}
    if not os.path.exists(ruta):
        return out
    c = _con(ruta)
    for e in g.GEOLOGIA:
        fecha = _meta(f"completo_{e}", ruta)
        n = c.execute("SELECT COUNT(*) FROM pol WHERE escala = ?", (e,)).fetchone()[0]
        out[e] = {"fecha": fecha, "poligonos": n, "completo": fecha is not None}
    return out


def features(escala: str, pol, ruta: str = RUTA) -> list[dict]:
    """Polígonos de la escala que tocan `pol`, con el mismo formato de `query_en_poligono`
    pero con la geometría ya en shapely (clave «_shapely»)."""
    o, s, e, n = pol.bounds
    filas = _con(ruta).execute(
        "SELECT p.attrs, p.wkb FROM idx JOIN pol p ON p.id = idx.id "
        "WHERE p.escala = ? AND idx.maxx >= ? AND idx.minx <= ? AND idx.maxy >= ? AND idx.miny <= ?",
        (escala, o, e, s, n)).fetchall()
    out = []
    for attrs, b in filas:
        geom = shp_wkb.loads(b)
        if geom.intersects(pol):
            out.append({"attributes": json.loads(attrs), "_shapely": geom})
    return out


_features_orig = features   # (las pruebas reemplazan `features` y llaman a la original)


def _ids_por_recuadros(url: str, aviso=print, paso: float = 1.0) -> set[int]:
    """OBJECTID de toda la capa pedidos por recuadros de 1° × 1° sobre el Perú: la consulta nacional de una
    sola vez agota el tiempo de GEOCATMIN (504). Cada recuadro se reintenta; si alguno falla del todo, se
    lanza error (la descarga no puede marcarse completa)."""
    import json as _json
    ids: set[int] = set()
    fallidos = []
    lat = 0.5
    while lat > -18.6:
        lon = -81.6
        while lon < -68.4:
            geom = _json.dumps({"rings": [[[lon, lat - paso], [lon + paso, lat - paso], [lon + paso, lat], [lon, lat], [lon, lat - paso]]],
                                "spatialReference": {"wkid": 4326}})
            ok = False
            for intento in range(4):
                try:
                    j = g._post(url, {"where": "1=1", "geometry": geom, "geometryType": "esriGeometryPolygon",
                                      "spatialRel": "esriSpatialRelIntersects", "inSR": 4326,
                                      "returnIdsOnly": "true", "f": "json"}, 120)
                    ids.update(j.get("objectIds") or [])
                    ok = True
                    break
                except Exception:  # noqa: BLE001
                    time.sleep(5 * (intento + 1))
            if not ok:
                fallidos.append((lon, lat))
            lon += paso
        lat -= paso
    if fallidos:
        raise RuntimeError(f"{len(fallidos)} recuadro(s) sin responder en GEOCATMIN; vuelve a correr la descarga más tarde.")
    aviso(f"  lista de polígonos armada por recuadros: {len(ids)}")
    return ids


def descargar(escala: str, ruta: str = RUTA, aviso=print) -> int:
    """Descarga (o completa) TODA la capa de esa escala. Reanudable: salta los OBJECTID ya guardados."""
    cfg = g.GEOLOGIA[escala]
    url = f"{g.BASE}/{cfg['servicio']}/MapServer/{cfg['capa']}/query"
    c = _con(ruta)
    ids = sorted(_ids_por_recuadros(url, aviso))
    ya = {r[0] for r in c.execute("SELECT oid FROM pol WHERE escala = ?", (escala,))}
    faltan = [i for i in ids if i not in ya]
    aviso(f"[{escala}] {len(ids)} polígonos en GEOCATMIN · {len(ya)} ya guardados · {len(faltan)} por bajar")
    t0 = time.time()
    for k in range(0, len(faltan), LOTE):
        lote = faltan[k:k + LOTE]
        j = g._post(url, {"objectIds": ",".join(map(str, lote)), "outFields": "OBJECTID," + cfg["campos"],
                          "returnGeometry": "true", "outSR": 4326, "maxAllowableOffset": g._GENERALIZAR,
                          "f": "json"}, 300)
        filas = []
        for f in j.get("features") or []:
            a = f.get("attributes") or {}
            geom = g.esri_a_shapely(f.get("geometry"))
            if geom is None or geom.is_empty:
                continue
            oid = a.pop("OBJECTID", None)
            filas.append((escala, oid, json.dumps(a, ensure_ascii=False), geom.wkb, geom.bounds))
        with c:
            for esc, oid, attrs, b, (minx, miny, maxx, maxy) in filas:
                cur = c.execute("INSERT OR IGNORE INTO pol (escala, oid, attrs, wkb) VALUES (?, ?, ?, ?)", (esc, oid, attrs, b))
                if cur.rowcount:
                    c.execute("INSERT INTO idx VALUES (?, ?, ?, ?, ?)", (cur.lastrowid, minx, maxx, miny, maxy))
        hechos = k + len(lote)
        if (k // LOTE) % 25 == 0 or hechos == len(faltan):
            v = hechos / max(time.time() - t0, 1)
            aviso(f"[{escala}] {hechos}/{len(faltan)} · faltan ~{(len(faltan) - hechos) / max(v, 1e-9) / 60:.0f} min")
    n = c.execute("SELECT COUNT(*) FROM pol WHERE escala = ?", (escala,)).fetchone()[0]
    if n >= len(ids) * 0.995:      # alguna geometría vacía se descarta: tolerancia de 0,5 %
        with c:
            c.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (f"completo_{escala}", time.strftime("%Y-%m-%d")))
    return n
