"""Censo por TIPO DE MATERIAL: para cada cuadrícula sobreviviente (datos/censo_libres.json), cada
zona favorable de la 1:50 000 y de la 1:100 000 con su tipo (arena · arenisca · cuarcita), clase
(A/B/C), hectáreas y % libre y utilizable. Prioridad geológica del usuario: arena silícea/cuarzosa
ALTA · arenisca cuarzosa MEDIA · cuarcita BAJA.

Hace solo lo necesario (geología 50K y 100K, áreas protegidas, catastro, libres/utilizable con
ESA WorldCover); no consulta muestras RMI ni la ficha de cada concesión. Reanudable.

Salida: backend/datos/censo_tipos.json
    cd backend
    python scripts/censo_tipos.py          # todas · python scripts/censo_tipos.py 5 (prueba)
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, ".."))
sys.path.insert(0, AQUI)
os.environ["COBERTURA_FUENTE"] = "worldcover"   # igual que el censo de áreas libres

from shapely.geometry import box, shape  # noqa: E402

import geocatmin_rmi as g  # noqa: E402
import libres as lib  # noqa: E402
import restricciones as restr  # noqa: E402
from censo_libres import limites  # noqa: E402
from censo_s2_aws import sobrevivientes  # noqa: E402
from materiales import normalizar  # noqa: E402

SALIDA = os.path.join(AQUI, "..", "datos", "censo_tipos.json")
PARALELO = 3


def tipo(z: dict) -> str:
    """arena · arenisca · cuarcita (lo que manda: motivo de la clase, luego la roca dominante)."""
    m = normalizar(z.get("motivo") or "")
    if m.startswith("ARENA ") or m.startswith("DEPOSITO EOLICO") or m.startswith("DEPÓSITO EÓLICO"):
        return "arena"
    if m.startswith("CUARCITA"):
        return "cuarcita"
    if m.startswith("ARENISCA"):
        return "arenisca"
    # clase B (formación conocida) u otros: roca dominante y, si no, la primera roca nombrada
    for txt in (z.get("roca_dominante") or "", f"{z.get('litologia') or ''} {z.get('descripcion') or ''}"):
        t = normalizar(txt)
        pos = {k: m.start() for k, rx in (("cuarcita", r"CUARCIT|CUARZO ?ARENIT"), ("arenisca", r"ARENISC"),
                                          ("arena", r"\bARENAS?\b|E[OÓ]LIC|\bDUNAS?\b"))
               if (m := re.search(rx, t))}
        if pos:
            return min(pos, key=pos.get)
    return "arenisca"


def analizar(codigo: str) -> dict:
    b = limites(codigo)
    pol = box(b["oeste"], b["sur"], b["este"], b["norte"])
    with ThreadPoolExecutor(4) as ex:
        f50 = ex.submit(g.buscar_geologia, "arena_silicea", pol, "50K")
        f100 = ex.submit(g.buscar_geologia, "arena_silicea", pol, "100K")
        fres = ex.submit(restr.consultar, pol)
        fcon = ex.submit(lib.concesiones, pol)
        g50, g100, areas, cons = f50.result(), f100.result(), fres.result(), fcon.result()
    libres = lib.calcular(pol, cons, areas)
    if libres.get("cobertura_fuente") != "ESA WorldCover 2021":
        return {"ok": False, "error": "sin cobertura del suelo"}
    zonas = []
    for escala, r in (("50K", g50), ("100K", g100)):
        for z in r["afloramientos"]:
            geom = shape(z["geometria"])
            zonas.append({"escala": escala, "clase": z["clase"], "tipo": tipo(z), "unidad": z["unidad"][:60],
                          "ha": z["area_ha"], "util_pct": lib.util_en_zona(libres, geom),
                          "centro": z["centro"]})
    return {"ok": True, "util_pct_celda": libres.get("util_pct"), "zonas": zonas}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    tope = int(sys.argv[1]) if len(sys.argv) > 1 else None
    hecho: dict = {}
    if os.path.exists(SALIDA):
        with open(SALIDA, encoding="utf-8") as fh:
            hecho = json.load(fh).get("celdas", {})
    todos = sobrevivientes()
    pend = [c for c in todos if not (hecho.get(c) or {}).get("ok")]
    print(f"{len(todos)} sobrevivientes · {len(todos) - len(pend)} hechas · {len(pend)} por hacer", flush=True)
    if tope:
        pend = pend[:tope]
    candado, t0, n = threading.Lock(), time.time(), [0]

    def guardar():
        tmp = SALIDA + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"actualizado": time.strftime("%Y-%m-%d %H:%M"), "celdas": hecho}, fh,
                      ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, SALIDA)

    def una(c):
        try:
            fila = analizar(c)
        except Exception as e:  # noqa: BLE001
            fila = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}"}
        with candado:
            hecho[c] = fila
            n[0] += 1
            if n[0] % 20 == 0 or n[0] == len(pend):
                guardar()
                v = n[0] / max(time.time() - t0, 1)
                print(f"{n[0]}/{len(pend)} · {v * 60:.0f} por min · faltan ~{(len(pend) - n[0]) / v / 60:.0f} min", flush=True)

    with ThreadPoolExecutor(PARALELO) as ex:
        list(ex.map(una, pend))
    guardar()
    ok = sum(1 for v in hecho.values() if v.get("ok"))
    print(f"listo: {ok} analizadas · {len(hecho) - ok} con error (volver a correr para reintentar)")


if __name__ == "__main__":
    main()
