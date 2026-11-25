"""Genera frontend/src/celdas_peru.json: qué cuadrículas 1:25 000 de la
Carta Nacional tocan territorio peruano (aunque sea un pedazo de costa o
una isla). El mapa solo dibuja esas; las de puro océano (o fuera del Perú)
no se muestran.

Fuente: GEOCATMIN · SERV_CARTOGRAFIA_BASE_WGS84, capa 23 "Peru".
Se corre a mano solo si cambia la grilla o el contorno (necesita internet):

    cd backend
    python scripts/generar_celdas_peru.py

Formato de salida: {"27k4": 13, ...}  → hoja 1:50 000 y, en bits, cuáles
de sus 4 cuadrículas 1:25 000 tienen tierra: NE=1, SE=2, SO=4, NO=8.
La numeración es la misma de frontend/src/geo.ts (verificada con INGEMMET:
cuadrantes 50K 1=NE, 2=SE, 3=SO, 4=NO).
"""
import json
import math
import os
import sys

import requests
from shapely.geometry import box, shape
from shapely.ops import unary_union
from shapely.prepared import prep

URL = ("https://geocatmin.ingemmet.gob.pe/arcgis/rest/services/"
       "SERV_CARTOGRAFIA_BASE_WGS84/MapServer/23/query")
SALIDA = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src", "celdas_peru.json")

LADO_100K = 0.5
LON_ORIGEN = -81.5
# Columnas: alfabeto español con «ñ» y sin «w» (las 501 hojas 100K de GEOCATMIN lo confirman)
ALFABETO = "abcdefghijklmnñopqrstuvxyz"
NUM_50K = {"NE": 1, "SE": 2, "SO": 3, "NO": 4}
BIT_25K = {"NE": 1, "SE": 2, "SO": 4, "NO": 8}


def cuadrante(norte: bool, este: bool) -> str:
    return ("NE" if este else "NO") if norte else ("SE" if este else "SO")


def codigo_25k(lat: float, lon: float) -> tuple[str, str]:
    """(código hoja 50K, cuadrante 25K) del punto — igual que celdaEn() en geo.ts."""
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


def contorno_peru():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    from geocatmin_rmi import bundle_ca  # cadena de certificados completa para GEOCATMIN

    r = requests.get(URL, verify=bundle_ca(), params={
        "f": "geojson", "where": "1=1", "outFields": "", "returnGeometry": "true",
        "outSR": 4326, "maxAllowableOffset": 0.0003,
    }, timeout=180)
    r.raise_for_status()
    feats = r.json()["features"]
    if not feats:
        sys.exit("GEOCATMIN no devolvió el contorno del Perú.")
    return unary_union([shape(f["geometry"]) for f in feats]).buffer(0)


def main():
    peru = contorno_peru()
    p = prep(peru)
    o, s, e, n = peru.bounds
    paso = 0.125
    salida: dict[str, int] = {}
    lat = math.ceil(n / paso) * paso
    while lat > s:
        lon = math.floor(o / paso) * paso
        while lon < e:
            if p.intersects(box(lon, lat - paso, lon + paso, lat)):
                h50, q = codigo_25k(lat - paso / 2, lon + paso / 2)
                salida[h50] = salida.get(h50, 0) | BIT_25K[q]
            lon += paso
        lat -= paso
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(salida.items())), f, separators=(",", ":"))
    n25 = sum(bin(v).count("1") for v in salida.values())
    print(f"{len(salida)} hojas 1:50 000 · {n25} cuadrículas 1:25 000 con tierra → {os.path.abspath(SALIDA)}")


if __name__ == "__main__":
    main()
