"""Respaldo GRATIS de Sentinel-2 L2A: el archivo público de AWS (Element84 Earth Search, COG).

Se usa cuando Copernicus (Sentinel Hub) no puede: cupo de unidades/peticiones agotado, sin claves
configuradas, o el servicio no responde. Entrega las bandas EXACTAMENTE como `sentinel_silice.descargar_bandas`
(misma grilla EPSG:4326 lineal del recuadro, mismo orden B02,B03,B04,B08,B11,B12,SCL,B8A y misma escala
«DN armonizado» = reflectancia × 10 000), así que `calcular()` no cambia.

Elige la fecha como Copernicus: candidatas del catálogo de menos nubes en 18 meses, mide las nubes DENTRO de
la cuadrícula (SCL a baja resolución) y se queda con la primera ≤ 0,5 % de nubes y ≥ 98 % de cobertura, o con
la de menos nubes. Sin cuenta ni créditos; más lento (descarga ~20 MB por cuadrícula).
"""
from __future__ import annotations

import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import numpy as np
import requests

STAC = "https://earth-search.aws.element84.com/v1/search"
# orden de sentinel_silice._EVALSCRIPT; SCL en el índice 6
ACTIVOS = ["blue", "green", "red", "nir", "swir16", "swir22", "scl", "nir08"]
MAX_REVISAR = 6
for _k, _v in {"AWS_NO_SIGN_REQUEST": "YES", "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR", "GDAL_HTTP_MULTIRANGE": "YES",
               "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES": "YES", "VSI_CACHE": "TRUE", "GDAL_HTTP_TIMEOUT": "30",
               "GDAL_HTTP_CONNECTTIMEOUT": "10", "GDAL_HTTP_MAX_RETRY": "3", "GDAL_HTTP_RETRY_DELAY": "2"}.items():
    os.environ.setdefault(_k, _v)


def disponible() -> bool:
    try:
        import rasterio  # noqa: F401
        return True
    except ImportError:
        return False


def _dias(bbox: tuple) -> list[list[dict]]:
    """Fechas (escenas del mismo día que tocan el recuadro), de menos a más nubes, últimos 18 meses."""
    hasta = date.today()
    r = requests.post(STAC, json={
        "collections": ["sentinel-2-l2a"], "bbox": list(bbox), "limit": 100,
        "datetime": f"{hasta - timedelta(days=548)}T00:00:00Z/{hasta}T23:59:59Z",
        "query": {"eo:cloud_cover": {"lt": 30}},
        "sortby": [{"field": "properties.eo:cloud_cover", "direction": "asc"}],
    }, timeout=60)
    r.raise_for_status()
    por_dia: dict[str, list] = defaultdict(list)
    for f in r.json().get("features", []):
        por_dia[f["properties"]["datetime"][:10]].append(f)
    return sorted(por_dia.values(), key=lambda fs: max(f["properties"]["eo:cloud_cover"] for f in fs))


def _leer(item: dict, activo: str, bbox: tuple, tam: tuple[int, int]) -> np.ndarray | None:
    """Una banda de una escena en la grilla EPSG:4326 lineal del recuadro (0 = sin dato)."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.transform import from_bounds
    from rasterio.vrt import WarpedVRT
    a = item["assets"].get(activo)
    if not a:
        return None
    ancho, alto = tam
    rs = Resampling.nearest if activo == "scl" else Resampling.bilinear
    with rasterio.open(a["href"]) as src, WarpedVRT(src, crs="EPSG:4326", transform=from_bounds(*bbox, ancho, alto),
                                                    width=ancho, height=alto, resampling=rs, nodata=0) as vrt:
        x = vrt.read(1).astype(np.float32)
    if activo != "scl":
        # «DN armonizado» como Sentinel Hub: desde la línea base 04.00 los DN traen +1000 (BOA_ADD_OFFSET);
        # Earth Search ya lo resta en las escenas nuevas (earthsearch:boa_offset_applied)
        p = item["properties"]
        if not p.get("earthsearch:boa_offset_applied") and str(p.get("s2:processing_baseline", "00")) >= "04.00":
            x = np.where(x > 0, np.maximum(x - 1000, 1), 0)
    return x


def _dia(escenas: list[dict], activos: list[str], bbox: tuple, tam: tuple[int, int]) -> dict[str, np.ndarray]:
    """Mosaico de las escenas de UN día (la cuadrícula puede caer en dos teselas)."""
    trabajos = [(e, k) for e in escenas for k in activos]
    with ThreadPoolExecutor(min(16, len(trabajos))) as ex:
        leidos = list(ex.map(lambda t: _leer(t[0], t[1], bbox, tam), trabajos))
    out = {k: np.zeros((tam[1], tam[0]), np.float32) for k in activos}
    for (_, k), x in zip(trabajos, leidos):
        if x is not None:
            vacio = out[k] == 0
            out[k][vacio] = x[vacio]
    return out


def descargar(anillo: list, bbox: tuple, tam: tuple[int, int], area: np.ndarray) -> tuple[np.ndarray, dict]:
    """(bandas alto×ancho×8 como Sentinel Hub, toma {dia, datetime, nubes_escena, revisadas, candidatas})."""
    from sentinel_silice import NUBES_MAX_CUADRICULA, _VEG_SUFICIENTE, escoger, medir_nubes, medir_vegetacion, ordenar_candidatas
    dias = _dias(bbox)
    if not dias:
        raise RuntimeError("AWS (Earth Search) no tiene tomas Sentinel-2 con menos de 30 % de nubes en 18 meses.")
    chico = (max(64, tam[0] // 6), max(64, tam[1] // 6))
    from PIL import Image
    area_chica = np.asarray(Image.fromarray(area.astype(np.uint8) * 255).resize(chico, Image.NEAREST)) > 0
    # misma regla que Copernicus: época seca primero; entre las despejadas, la de menos vegetación
    porfecha = {fs[0]["properties"]["datetime"][:10]: fs for fs in dias}
    cands = [{"dia": d, "datetime": fs[0]["properties"]["datetime"],
              "nubes_escena": float(max(e["properties"]["eo:cloud_cover"] for e in fs))} for d, fs in porfecha.items()]
    candidatas = []
    for c in ordenar_candidatas(cands, MAX_REVISAR):
        scl = _dia(porfecha[c["dia"]], ["scl"], bbox, chico)["scl"].astype(int)
        nubes, cobertura = medir_nubes(scl, area_chica)
        c = {**c, "nubes_cuadricula": nubes, "cobertura": cobertura, "vegetacion": medir_vegetacion(scl, area_chica)}
        candidatas.append(c)
        if nubes <= NUBES_MAX_CUADRICULA and cobertura >= 98 and c["vegetacion"] <= _VEG_SUFICIENTE:
            break
    c = escoger(candidatas)
    escenas = porfecha[c["dia"]]
    b = _dia(escenas, ACTIVOS, bbox, tam)
    bandas = np.stack([b[k] for k in ACTIVOS], axis=-1)
    return bandas, {**c, "revisadas": len(candidatas), "candidatas": candidatas}
