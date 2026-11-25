"""Paso 3 del censo nacional: hierro y arcilla de Sentinel-2 en las zonas A/B LIBRES y
UTILIZABLES de cada cuadrícula, con el archivo PÚBLICO de Sentinel-2 L2A en AWS
(Element84 Earth Search: COG en s3://sentinel-cogs). Sin cuenta y sin gastar créditos de Copernicus.

Por cuadrícula 1:25 000 (las que sobrevivieron a datos/censo_libres.json):
  1. Grilla Web Mercator de ~20 m (la misma de las áreas libres de la app, `libres.Lienzo`):
     máscara libre-y-utilizable (`libres.mascaras`) y zonas A y B de la 1:50 000 y de la 1:100 000
     POR SEPARADO (`geocatmin_rmi.buscar_geologia`).
  2. Tomas L2A del último año con pocas nubes (STAC); se juntan hasta TOMAS fechas: mediana por
     píxel, sin nubes, sombras, cirros, nieve ni agua (SCL).
  3. Índices ABSOLUTOS (comparables entre cuadrículas): hierro férrico B4/B2, arcilla B11/B12,
     hierro ferroso B11/B8A, brillo (B2+B4+B11)/3; vegetación (NDVI ≥ 0,30) se descarta.
  4. Por escala y clase: píxeles de la zona, libres-utilizables, con dato, medianas y un histograma
     2D hierro × arcilla (para fijar después umbrales nacionales sin volver a descargar).

Se puede cortar y volver a correr (continúa). Salida: backend/datos/censo_s2.json

    cd backend
    python scripts/censo_s2_aws.py            # todas las que sobrevivieron
    python scripts/censo_s2_aws.py 3          # prueba con 3
    python scripts/censo_s2_aws.py 20g1-SO    # una cuadrícula
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, ".."))
sys.path.insert(0, AQUI)

import numpy as np  # noqa: E402
import rasterio  # noqa: E402
import requests  # noqa: E402
from rasterio.enums import Resampling  # noqa: E402
from rasterio.transform import from_bounds  # noqa: E402
from rasterio.vrt import WarpedVRT  # noqa: E402
from shapely.geometry import box, shape  # noqa: E402

import geocatmin_rmi as g  # noqa: E402
import libres as lib  # noqa: E402
from censo_libres import limites  # noqa: E402

LIBRES = os.path.join(AQUI, "..", "datos", "censo_libres.json")
SALIDA = os.path.join(AQUI, "..", "datos", "censo_s2.json")
STAC = "https://earth-search.aws.element84.com/v1/search"
BANDAS = ["blue", "red", "nir08", "swir16", "swir22", "scl"]
SCL_MALAS = (0, 1, 3, 6, 8, 9, 10, 11)   # sin dato, saturado, sombra, agua, nubes, cirros, nieve
TOMAS = 3            # fechas despejadas que se juntan
MESES = 12
PARALELO = 3
NDVI_MAX = 0.30
# histograma 2D: hierro férrico B4/B2 × arcilla B11/B12 (bordes; fuera de rango va al primer/último)
BORDES_FE = np.round(np.arange(0.8, 3.01, 0.1), 2)
BORDES_CL = np.round(np.arange(0.9, 1.81, 0.05), 2)

os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("GDAL_HTTP_MULTIRANGE", "YES")
os.environ.setdefault("GDAL_HTTP_MERGE_CONSECUTIVE_RANGES", "YES")
os.environ.setdefault("VSI_CACHE", "TRUE")
os.environ.setdefault("GDAL_HTTP_TIMEOUT", "30")          # sin límite GDAL puede quedarse colgado
os.environ.setdefault("GDAL_HTTP_CONNECTTIMEOUT", "10")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "3")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")


def grilla(b: dict) -> lib.Lienzo:
    m_merc = 20 / np.cos(np.radians((b["sur"] + b["norte"]) / 2))
    x0, y0 = lib._merc(b["oeste"], b["sur"])
    x1, y1 = lib._merc(b["este"], b["norte"])
    return lib.Lienzo(b["oeste"], b["sur"], b["este"], b["norte"],
                      int(round((x1 - x0) / m_merc)), int(round((y1 - y0) / m_merc)))


def tomas(b: dict) -> list[list[dict]]:
    """Fechas (cada una = lista de escenas de ese día que tocan la cuadrícula), de menos a más nubes."""
    hasta = date.today()
    desde = hasta - timedelta(days=30 * MESES)
    r = requests.post(STAC, json={
        "collections": ["sentinel-2-l2a"], "bbox": [b["oeste"], b["sur"], b["este"], b["norte"]],
        "datetime": f"{desde}T00:00:00Z/{hasta}T23:59:59Z", "limit": 100,
        "query": {"eo:cloud_cover": {"lt": 30}},
        "sortby": [{"field": "properties.eo:cloud_cover", "direction": "asc"}],
    }, timeout=60)
    r.raise_for_status()
    por_dia: dict[str, list] = defaultdict(list)
    for f in r.json().get("features", []):
        por_dia[f["properties"]["datetime"][:10]].append(f)
    dias = sorted(por_dia.values(), key=lambda fs: max(f["properties"]["eo:cloud_cover"] for f in fs))
    return dias


def leer(item: dict, banda: str, lz: lib.Lienzo) -> np.ndarray | None:
    a = item["assets"].get(banda)
    if not a:
        return None
    rb = (a.get("raster:bands") or [{}])[0]
    escala = rb.get("scale", 1.0)
    # Earth Search ya resta el desplazamiento BOA (-0,1) en los datos nuevos: no restarlo dos veces
    desplaz = 0.0 if item["properties"].get("earthsearch:boa_offset_applied") else rb.get("offset", 0.0)
    ancho, alto = lz.tam
    tr = from_bounds(*lz.bb, ancho, alto)
    rs = Resampling.nearest if banda == "scl" else Resampling.average
    # bandas de 10 m: se lee su vista general de 20 m (4 veces menos datos)
    extra = {"overview_level": 0} if rb.get("spatial_resolution") == 10 else {}
    with rasterio.open(a["href"], **extra) as src, \
            WarpedVRT(src, crs="EPSG:3857", transform=tr, width=ancho, height=alto, resampling=rs, nodata=0) as vrt:
        x = vrt.read(1).astype(np.float32)
    if banda == "scl":
        return x
    x[x == 0] = np.nan
    return x * escala + desplaz


def compuesto(dias: list[list[dict]], lz: lib.Lienzo) -> tuple[dict, list]:
    """Mediana de hasta TOMAS fechas, enmascarando nubes/agua con SCL."""
    alto, ancho = lz.tam[1], lz.tam[0]
    pilas: dict[str, list] = {k: [] for k in BANDAS[:-1]}
    usadas = []
    for escenas in dias:
        capa = {k: np.full((alto, ancho), np.nan, np.float32) for k in BANDAS}
        # todas las bandas de todas las escenas del día a la vez (lectura por internet)
        trabajos = [(it, k) for it in escenas for k in BANDAS]
        with ThreadPoolExecutor(len(trabajos)) as ex:
            leidos = list(ex.map(lambda t: leer(t[0], t[1], lz), trabajos))
        for (it, k), x in zip(trabajos, leidos):
            if x is None:
                continue
            vacio = np.isnan(capa[k]) if k != "scl" else ~(capa[k] > 0)
            capa[k][vacio] = x[vacio]
        mala = np.isin(np.nan_to_num(capa["scl"], nan=0).astype(int), SCL_MALAS)
        util = (~mala).mean()
        if util < 0.05:          # casi todo nube o sin dato: no aporta
            continue
        for k in pilas:
            c = capa[k]
            c[mala] = np.nan
            pilas[k].append(c)
        usadas.append({"fecha": escenas[0]["properties"]["datetime"][:10],
                       "nubes_escena": round(max(e["properties"]["eo:cloud_cover"] for e in escenas), 1),
                       "util_pct": round(100 * float(util), 1)})
        if len(usadas) >= TOMAS:
            break
    if not usadas:
        return {}, []
    with np.errstate(all="ignore"):
        return {k: np.nanmedian(np.stack(v), axis=0) for k, v in pilas.items()}, usadas


def resumen(mask: np.ndarray, ix: dict, ha_px: float) -> dict:
    n = int(mask.sum())
    if n == 0:
        return {}
    v = mask & ix["valido"]
    nv = int(v.sum())
    out = {"ha": round(n * ha_px, 1), "ha_dato": round(nv * ha_px, 1)}
    if nv:
        for k in ("fe", "cl", "fe2", "br"):
            out[k] = round(float(np.median(ix[k][v])), 4)
        h, _, _ = np.histogram2d(ix["fe"][v], ix["cl"][v],
                                 bins=[np.r_[-np.inf, BORDES_FE[1:-1], np.inf], np.r_[-np.inf, BORDES_CL[1:-1], np.inf]])
        out["hist"] = {f"{i},{j}": int(h[i, j]) for i, j in zip(*np.nonzero(h))}
    return out


def zonas(pol, escala: str) -> dict:
    """{"A": [geom], "B": [geom]} de la escala (C no interesa aquí)."""
    r = g.buscar_geologia("arena_silicea", pol, escala)
    out = {"A": [], "B": []}
    for a in r["afloramientos"]:
        if a["clase"] in out:
            out[a["clase"]].append(shape(a["geometria"]))
    return out


def analizar(codigo: str) -> dict:
    b = limites(codigo)
    pol = box(b["oeste"], b["sur"], b["este"], b["norte"])
    lz = grilla(b)
    ha_px = lz.m_por_px ** 2 / 1e4
    with ThreadPoolExecutor(4) as ex:
        f_m = ex.submit(lib.mascaras, b["oeste"], b["sur"], b["este"], b["norte"], *lz.tam)
        f_50 = ex.submit(zonas, pol, "50K")
        f_100 = ex.submit(zonas, pol, "100K")
        f_t = ex.submit(tomas, b)
        m, z50, z100, dias = f_m.result(), f_50.result(), f_100.result(), f_t.result()
    no_apto = np.zeros_like(m["tierra"])
    for k in lib.MOTIVOS:
        no_apto |= m[k]
    libre = m["tierra"] & ~m["ocupado"] & ~no_apto
    util, ext = libre & ~m["extinguido"], libre & m["extinguido"]
    if not dias:
        return {"ok": True, "sin_imagen": True}
    bandas, usadas = compuesto(dias, lz)
    if not bandas:
        return {"ok": True, "sin_imagen": True}
    with np.errstate(all="ignore"):
        bl, rd, n8, s1, s2 = (bandas[k] for k in ("blue", "red", "nir08", "swir16", "swir22"))
        ix = {"fe": rd / bl, "cl": s1 / s2, "fe2": s1 / n8, "br": (bl + rd + s1) / 3,
              "ndvi": (n8 - rd) / (n8 + rd)}
        ix["valido"] = np.isfinite(ix["fe"]) & np.isfinite(ix["cl"]) & (ix["ndvi"] < NDVI_MAX) & (bl > 0)
    out = {"ok": True, "tomas": usadas, "px_m": round(lz.m_por_px, 1),
           "pct_dato_celda": round(100 * float((ix["valido"] & m["tierra"]).sum()) / max(int(m["tierra"].sum()), 1), 1)}
    for escala, zs in (("50K", z50), ("100K", z100)):
        for clase, geoms in zs.items():
            if not geoms:
                continue
            zm = lz(geoms)
            r = {"zona": resumen(zm, ix, ha_px), "util": resumen(zm & util, ix, ha_px),
                 "ext": resumen(zm & ext, ix, ha_px)}
            r = {k: v for k, v in r.items() if v}
            if r:
                out.setdefault(escala, {})[clase] = r
    return out


def sobrevivientes() -> list[str]:
    with open(LIBRES, encoding="utf-8") as fh:
        d = json.load(fh)["celdas"]
    out = []
    for k, v in d.items():
        if not v.get("ok") or (v.get("util_pct_celda") or 0) < 1:
            continue
        hu = v.get("ha_util") or {}
        if (hu.get("A", 0) + hu.get("B", 0)) > 0 or (v.get("zonas_100k_A_ha") or 0) > 0:
            out.append(k)
    return sorted(out)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    hecho: dict = {}
    if os.path.exists(SALIDA):
        with open(SALIDA, encoding="utf-8") as fh:
            hecho = json.load(fh).get("celdas", {})
    if arg and "-" in arg:
        pendientes = [arg]
    else:
        todos = sobrevivientes()
        pendientes = [c for c in todos if not (hecho.get(c) or {}).get("ok")]
        print(f"{len(todos)} cuadrículas sobrevivientes · {len(todos) - len(pendientes)} ya hechas · "
              f"{len(pendientes)} por hacer", flush=True)
        if arg:
            pendientes = pendientes[:int(arg)]
    candado = threading.Lock()
    t0, n = time.time(), [0]

    def guardar():
        tmp = SALIDA + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"actualizado": time.strftime("%Y-%m-%d %H:%M"), "fuente": "Sentinel-2 L2A · AWS Earth Search",
                       "bordes_fe": BORDES_FE.tolist(), "bordes_cl": BORDES_CL.tolist(), "celdas": hecho}, fh,
                      ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, SALIDA)

    def una(codigo: str):
        t = time.time()
        try:
            fila = analizar(codigo)
        except Exception as e:  # noqa: BLE001
            fila = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:160]}"}
        fila["seg"] = round(time.time() - t)
        with candado:
            hecho[codigo] = fila
            n[0] += 1
            if n[0] % 10 == 0 or n[0] == len(pendientes):
                guardar()
                v = n[0] / max(time.time() - t0, 1)
                print(f"{n[0]}/{len(pendientes)} · {v * 60:.1f} por min · faltan ~{(len(pendientes) - n[0]) / v / 60:.0f} min",
                      flush=True)

    with ThreadPoolExecutor(PARALELO) as ex:
        list(ex.map(una, pendientes))
    guardar()
    ok = sum(1 for v in hecho.values() if v.get("ok"))
    print(f"listo: {ok} analizadas · {len(hecho) - ok} con error (volver a correr para reintentar)")


if __name__ == "__main__":
    main()
