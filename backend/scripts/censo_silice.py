"""Censo nacional: ¿qué cuadrículas 1:25 000 tienen roca o arena silícea según la geología
de INGEMMET (1:50 000 y 1:100 000)?

Consulta GEOCATMIN para TODO el Perú con un filtro SQL amplio (cuarcita, arenisca, arena
cuarzosa/silícea, sílice, eólico/dunas y las formaciones cuarzosas conocidas), clasifica cada
polígono con la MISMA regla de la app (`materiales.clasificar`: A / B / C) y lo cruza con la
grilla 1:25 000 (solo cuadrículas con tierra, `frontend/src/celdas_peru.json`).

Salida: backend/datos/censo_silice.json
    {"generado": ..., "celdas": {"27k4-NE": {"50K": {"A": ha, "B": ha, "C": ha}, "100K": {...}}, ...}}

Se corre a mano (necesita internet; tarda varios minutos):
    cd backend
    python scripts/censo_silice.py
"""
from __future__ import annotations

import json
import io
import math
import os
import sys
import time
from collections import defaultdict

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, ".."))

from shapely.geometry import box  # noqa: E402

import geocatmin_rmi as g  # noqa: E402
from materiales import clasificar  # noqa: E402

SALIDA = os.path.join(AQUI, "..", "datos", "censo_silice.json")
CELDAS = os.path.join(AQUI, "..", "..", "frontend", "src", "celdas_peru.json")
LOTE = 400
PASO = 0.125
LADO_100K = 0.5
LON_ORIGEN = -81.5
ALFABETO = "abcdefghijklmnñopqrstuvxyz"
NUM_50K = {"NE": 1, "SE": 2, "SO": 3, "NO": 4}
BIT_25K = {"NE": 1, "SE": 2, "SO": 4, "NO": 8}

_TERMINOS = ["CUARCIT", "CUARCÍT", "CUARZOARENIT", "CUARZO ARENIT", "ARENISC", "ARENA%SIL", "SILICE", "SÍLICE",
             "ARENA%CUARZOS", "EOLIC", "EÓLIC", "DUNA"]
_FORMACIONES = ["MARCAVILCA", "HERRADURA", "SALTO DEL FRAILE", "MORRO SOLAR", "CHIMU", "CHIMÚ", "FARRAT",
                "GOYLLARISQUI", "HUALHUANI", "CUSHABATAY", "AGUA CALIENTE", "HUANCAN"]


def _like(campos, terminos):
    return [f"UPPER({c}) LIKE '%{t}%'" for c in campos for t in terminos]


SQL = {
    "50K": " OR ".join(_like(["LITOLOGIA", "DESCRIP"], _TERMINOS) + _like(["UNIDAD"], _FORMACIONES)),
    "100K": " OR ".join(_like(["DESCRIP"], _TERMINOS) + _like(["UNIDAD"], _FORMACIONES) + ["UPPER(NAME) LIKE 'Q-EO%'"]),
}


def cuadrante(norte: bool, este: bool) -> str:
    return ("NE" if este else "NO") if norte else ("SE" if este else "SO")


def codigo_25k(lat: float, lon: float) -> tuple[str, str]:
    """Igual que celdaEn() en geo.ts y que scripts/generar_celdas_peru.py."""
    fila = math.floor(-lat / LADO_100K) + 1
    col = math.floor((lon - LON_ORIGEN) / LADO_100K)
    norte100, oeste100 = -(fila - 1) * LADO_100K, LON_ORIGEN + col * LADO_100K
    m50 = LADO_100K / 2
    n50, e50 = lat >= norte100 - m50, lon >= oeste100 + m50
    norte50 = norte100 if n50 else norte100 - m50
    oeste50 = oeste100 + m50 if e50 else oeste100
    m25 = m50 / 2
    q25 = cuadrante(lat >= norte50 - m25, lon >= oeste50 + m25)
    return f"{fila}{ALFABETO[col]}{NUM_50K[cuadrante(n50, e50)]}", q25


def ha_grados(geom, lat: float) -> float:
    return geom.area * 111320 * math.cos(math.radians(lat)) * 110540 / 1e4


def descargar(escala: str) -> list[tuple[str, dict]]:
    """[(clase, feature con geometría)] de toda la capa para esa escala."""
    cfg = g.GEOLOGIA[escala]
    url = f"{g.BASE}/{cfg['servicio']}/MapServer/{cfg['capa']}/query"
    t0 = time.time()
    ids = g._post(url, {"where": SQL[escala], "returnIdsOnly": "true", "f": "json"}, 300).get("objectIds") or []
    ids = sorted(ids)
    print(f"[{escala}] {len(ids)} polígonos con términos silíceos ({time.time() - t0:.0f} s)", flush=True)
    # 1) solo atributos → clasificar con la regla de la app
    clases: dict[int, str] = {}
    for i in range(0, len(ids), LOTE):
        j = g._post(url, {"objectIds": ",".join(map(str, ids[i:i + LOTE])), "outFields": "OBJECTID," + cfg["campos"],
                          "returnGeometry": "false", "f": "json"}, 300)
        for f in j.get("features") or []:
            a = f.get("attributes") or {}
            c = clasificar("arena_silicea", a)
            if c:
                clases[a["OBJECTID"]] = c[0]
    print(f"[{escala}] favorables: A {sum(v == 'A' for v in clases.values())} · "
          f"B {sum(v == 'B' for v in clases.values())} · C {sum(v == 'C' for v in clases.values())}", flush=True)
    # 2) geometría (generalizada ~50 m) solo de los favorables
    out = []
    fav = sorted(clases)
    for i in range(0, len(fav), LOTE):
        j = g._post(url, {"objectIds": ",".join(map(str, fav[i:i + LOTE])), "outFields": "OBJECTID",
                          "returnGeometry": "true", "outSR": 4326, "maxAllowableOffset": 0.0005, "f": "json"}, 300)
        for f in j.get("features") or []:
            out.append((clases[f["attributes"]["OBJECTID"]], f))
        if (i // LOTE) % 10 == 0:
            print(f"[{escala}] geometrías {min(i + LOTE, len(fav))}/{len(fav)}", flush=True)
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    with open(CELDAS, encoding="utf-8") as fh:
        tierra = json.load(fh)
    celdas: dict[str, dict] = defaultdict(lambda: {"50K": {"A": 0.0, "B": 0.0, "C": 0.0},
                                                    "100K": {"A": 0.0, "B": 0.0, "C": 0.0}})
    resumen = {}
    for escala in ("50K", "100K"):
        feats = descargar(escala)
        resumen[escala] = len(feats)
        for clase, f in feats:
            geom = g.esri_a_shapely(f.get("geometry"))
            if geom is None or geom.is_empty:
                continue
            geom = geom.buffer(0)
            if geom.is_empty:
                continue
            o, s, e, n = geom.bounds
            lat = math.ceil(n / PASO) * PASO
            while lat > s:
                lon = math.floor(o / PASO) * PASO
                while lon < e:
                    celda = box(lon, lat - PASO, lon + PASO, lat)
                    if geom.intersects(celda):
                        h50, q = codigo_25k(lat - PASO / 2, lon + PASO / 2)
                        if tierra.get(h50, 0) & BIT_25K[q]:
                            ha = ha_grados(geom.intersection(celda), lat - PASO / 2)
                            if ha >= 0.5:
                                celdas[f"{h50}-{q}"][escala][clase] += ha
                    lon += PASO
                lat -= PASO
    datos = {k: {e: {c: round(v, 1) for c, v in d.items() if v} for e, d in x.items() if any(d.values())}
             for k, x in sorted(celdas.items())}
    os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
    with open(SALIDA, "w", encoding="utf-8") as fh:
        json.dump({"generado": time.strftime("%Y-%m-%d"), "poligonos": resumen, "celdas": datos}, fh,
                  ensure_ascii=False, separators=(",", ":"))
    print(f"→ {os.path.abspath(SALIDA)} · {len(datos)} cuadrículas con algo silíceo")


if __name__ == "__main__":
    main()
