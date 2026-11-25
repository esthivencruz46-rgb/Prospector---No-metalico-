"""% de BOSQUE (ESA WorldCover 2021, clase 10 «árboles») de cada cuadrícula sobreviviente del
censo (datos/censo_libres.json). Lectura gruesa (~100 m por píxel): basta para separar
selva / ceja de selva de costa y sierra. Sin cuenta ni créditos.

Salida: backend/datos/censo_bosque.json  {"celdas": {"27k4-NE": {"bosque_pct": 3.2, "tierra_pct": 99.1}}}

    cd backend
    python scripts/censo_bosque.py
"""
from __future__ import annotations

import json
import math
import os
import sys
from concurrent.futures import ThreadPoolExecutor

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, ".."))
sys.path.insert(0, AQUI)

import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from rasterio.enums import Resampling  # noqa: E402
from rasterio.transform import from_bounds  # noqa: E402
from rasterio.vrt import WarpedVRT  # noqa: E402

from censo_libres import limites  # noqa: E402
from censo_s2_aws import sobrevivientes  # noqa: E402

SALIDA = os.path.join(AQUI, "..", "datos", "censo_bosque.json")
WORLDCOVER = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{t}_Map.tif"
LADO = 140      # píxeles por lado (~100 m)

for k, v in {"GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR", "GDAL_HTTP_TIMEOUT": "30",
             "GDAL_HTTP_CONNECTTIMEOUT": "10", "GDAL_HTTP_MAX_RETRY": "3", "GDAL_HTTP_RETRY_DELAY": "2",
             "VSI_CACHE": "TRUE"}.items():
    os.environ.setdefault(k, v)


def bosque(codigo: str) -> dict:
    b = limites(codigo)
    out = np.zeros((LADO, LADO), np.uint8)
    tr = from_bounds(b["oeste"], b["sur"], b["este"], b["norte"], LADO, LADO)
    for la in range(math.floor(b["sur"] / 3) * 3, math.floor(b["norte"] / 3) * 3 + 1, 3):
        for lo in range(math.floor(b["oeste"] / 3) * 3, math.floor(b["este"] / 3) * 3 + 1, 3):
            t = f"{'S' if la < 0 else 'N'}{abs(la):02d}{'W' if lo < 0 else 'E'}{abs(lo):03d}"
            try:
                with rasterio.open(WORLDCOVER.format(t=t)) as src, WarpedVRT(
                        src, crs="EPSG:4326", transform=tr, width=LADO, height=LADO,
                        resampling=Resampling.mode, nodata=0) as vrt:
                    x = vrt.read(1)
            except Exception:  # noqa: BLE001
                continue
            out = np.where(out == 0, x, out)
    tierra = (out != 0) & (out != 80)          # sin dato y agua permanente fuera
    n = int(tierra.sum())
    return {"bosque_pct": round(100 * float((out == 10).sum()) / n, 1) if n else None,
            "tierra_pct": round(100 * n / out.size, 1)}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    cods = sobrevivientes()
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda c: (c, bosque(c)), cods))
    os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
    with open(SALIDA, "w", encoding="utf-8") as fh:
        json.dump({"fuente": "ESA WorldCover 2021 (clase 10)", "celdas": dict(res)}, fh, separators=(",", ":"))
    print(f"{len(res)} cuadrículas → {os.path.abspath(SALIDA)}")


if __name__ == "__main__":
    main()
