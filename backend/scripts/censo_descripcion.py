"""RANKING NACIONAL POR DESCRIPCIÓN (pedido del usuario, 24/11/2026: «un ranking en base a la descripción
bibliográfica: muchas dicen arenisca cuarzosa blanco grisácea de grano grueso, pero si está mezclada con
limoarcillitas negras o pardas, malogra»).

Para cada cuadrícula 1:25 000 del censo por tipo (datos/censo_tipos.json: zonas silíceas con ha y % libre y
utilizable) se leen las DESCRIPCIONES de sus unidades en la geología local (datos/geologia.sqlite) y se califican con
`vidrio_desc.aptitud` (= frontend/src/vidrio.ts). Carta: la 1:50 000 si el censo trae zonas 50K en la cuadrícula; si
no, la 1:100 000. Cada descripción distinta de una unidad recibe la parte de los km² libres-utilizables de la unidad
proporcional a su área dentro de la cuadrícula.

Uso (desde backend/): python scripts/censo_descripcion.py   → datos/censo_descripcion.json (lo lee ranking.py)
"""
import json
import os
import sqlite3
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from shapely import wkb  # noqa: E402
from shapely.geometry import box  # noqa: E402

import ranking  # noqa: E402
import vidrio_desc  # noqa: E402

DB = os.path.join(ranking.DATOS, "geologia.sqlite")
SALIDA = os.path.join(ranking.DATOS, "censo_descripcion.json")
MIN_KM2 = 0.5          # una descripción cuenta para el puesto de la cuadrícula si tiene al menos esto libre y utilizable


def _txt(v) -> str:
    v = "" if v is None else str(v)
    return "" if v.strip() in ("<Null>", "Null", "None") else v.strip()


def main():
    tipos = json.load(open(os.path.join(ranking.DATOS, "censo_tipos.json"), encoding="utf-8"))["celdas"]
    con = sqlite3.connect(DB)
    t0 = time.time()
    salida = {}
    cache_apt: dict = {}
    for n, (cod, t) in enumerate(tipos.items(), 1):
        if not t.get("ok"):
            continue
        zonas = t.get("zonas", [])
        carta = "50K" if any(z["escala"] == "50K" for z in zonas) else "100K"
        lat, lon = ranking._centro(cod)
        celda = box(lon - 0.0625, lat - 0.0625, lon + 0.0625, lat + 0.0625)
        # km² libres y utilizables y km² totales por unidad (de la carta)
        libre_u: dict = defaultdict(float)
        total_u: dict = defaultdict(float)
        for z in zonas:
            if z["escala"] == carta:
                libre_u[z["unidad"]] += z["ha"] * (z.get("util_pct") or 0) / 100 / 100
                total_u[z["unidad"]] += z["ha"] / 100
        if not libre_u:
            continue
        o, s, e, nn = celda.bounds
        filas = con.execute(
            "SELECT p.attrs, p.wkb FROM idx JOIN pol p ON p.id = idx.id "
            "WHERE p.escala = ? AND idx.maxx >= ? AND idx.minx <= ? AND idx.maxy >= ? AND idx.miny <= ?",
            (carta, o, e, s, nn)).fetchall()
        # área (en grados², solo para repartir) de cada descripción distinta por unidad
        area_d: dict = defaultdict(float)
        for attrs, b in filas:
            a = json.loads(attrs)
            u = _txt(a.get("UNIDAD"))
            if u not in libre_u:
                continue
            g = wkb.loads(b)
            if not g.intersects(celda):
                continue
            ar = g.intersection(celda).area
            if ar <= 0:
                continue
            clave = (u, _txt(a.get("DESCRIP")), _txt(a.get("LITOLOGIA")), _txt(a.get("LITO1")))
            area_d[clave] += ar
        por_unidad: dict = defaultdict(float)
        for (u, *_), ar in area_d.items():
            por_unidad[u] += ar
        descs = []
        for (u, d, li, l1), ar in area_d.items():
            k = (d, li, l1)
            if k not in cache_apt:
                cache_apt[k] = vidrio_desc.aptitud(d, li, l1)
            ap = cache_apt[k]
            parte = ar / max(por_unidad[u], 1e-12)
            descs.append({"unidad": u, "descripcion": d or li, **ap,
                          "km2_libre": round(libre_u[u] * parte, 2), "km2": round(total_u[u] * parte, 2)})
        if not descs:
            continue
        orden = lambda x: (vidrio_desc.ORDEN_NIVEL[x["nivel"]], -x["puntaje"], -x["km2_libre"])  # noqa: E731
        descs.sort(key=orden)
        cuentan = [x for x in descs if x["km2_libre"] >= MIN_KM2] or []
        mejor = cuentan[0] if cuentan else None
        km_nivel = defaultdict(float)
        for x in descs:
            km_nivel[x["nivel"]] += x["km2_libre"]
        salida[cod] = {"carta": carta, "mejor": mejor, "descripciones": descs[:8],
                       "km2_nivel": {k: round(v, 2) for k, v in km_nivel.items()}}
        if n % 200 == 0:
            print(f"{n}/{len(tipos)} · {time.time() - t0:.0f} s", flush=True)
    json.dump({"actualizado": time.strftime("%Y-%m-%d %H:%M"), "min_km2": MIN_KM2, "celdas": salida},
              open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False)
    niveles = defaultdict(int)
    for v in salida.values():
        niveles[(v["mejor"] or {}).get("nivel", "sin área libre")] += 1
    print(f"listo: {len(salida)} cuadrículas en {time.time() - t0:.0f} s · mejor nivel: {dict(niveles)}")


if __name__ == "__main__":
    main()
