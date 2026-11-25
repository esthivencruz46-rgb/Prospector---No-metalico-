"""Paso 2 del censo nacional: de las cuadrículas con geología A/B (datos/censo_silice.json),
¿cuántas hectáreas favorables están LIBRES y son UTILIZABLES?

Corre para cada cuadrícula el mismo análisis de «Solo geología» de la app
(`geocatmin_rmi.buscar`: geología, catastro minero, áreas protegidas/restringidas, concesiones
forestales, uso del suelo) y guarda SOLO el resumen (`barrido.puntaje`), sin geometrías.
NO usa Sentinel-2 (no gasta créditos).

Se puede cortar y volver a correr: continúa donde quedó (las cuadrículas con error se reintentan).
Salida: backend/datos/censo_libres.json

    cd backend
    python scripts/censo_libres.py            # todas las A/B (~2–3 h)
    python scripts/censo_libres.py 50         # solo las 50 primeras (prueba)
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, ".."))

import barrido  # noqa: E402
import geocatmin_rmi as g  # noqa: E402

ENTRADA = os.path.join(AQUI, "..", "datos", "censo_silice.json")
SALIDA = os.path.join(AQUI, "..", "datos", "censo_libres.json")
ALFABETO = "abcdefghijklmnñopqrstuvxyz"
PARALELO = 3          # suave con GEOCATMIN (cada cuadrícula ya hace varias consultas en paralelo)
# Cobertura del suelo: ESA WorldCover (AWS) en TODAS las cuadrículas, para medirlas igual. El servicio
# de Esri que usa la app se cayó a mitad del primer censo (20/11/2026) y esas cuadrículas quedaron sin
# descontar chacras/pueblos/agua: se rehacen todas las que no digan esta fuente.
FUENTE = "ESA WorldCover 2021"
os.environ["COBERTURA_FUENTE"] = "worldcover"


def limites(codigo: str) -> dict:
    """'27k4-NE' → {sur, oeste, norte, este} (igual que geo.ts)."""
    hoja, q25 = codigo.split("-")
    i = 0
    while hoja[i].isdigit():
        i += 1
    fila, letra, n50 = int(hoja[:i]), hoja[i], int(hoja[i + 1:])
    norte = -(fila - 1) * 0.5
    oeste = -81.5 + ALFABETO.index(letra) * 0.5
    q50 = {1: "NE", 2: "SE", 3: "SO", 4: "NO"}[n50]
    if q50[0] == "S":
        norte -= 0.25
    if q50[1] == "E":
        oeste += 0.25
    if q25[0] == "S":
        norte -= 0.125
    if q25[1] == "E":
        oeste += 0.125
    return {"sur": norte - 0.125, "oeste": oeste, "norte": norte, "este": oeste + 0.125}


def es_ab(x: dict) -> bool:
    return any(x.get(e, {}).get(c, 0) > 0 for e in ("50K", "100K") for c in ("A", "B"))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    tope = int(sys.argv[1]) if len(sys.argv) > 1 else None
    with open(ENTRADA, encoding="utf-8") as fh:
        censo = json.load(fh)["celdas"]
    codigos = sorted(k for k, v in censo.items() if es_ab(v))
    hecho: dict = {}
    if os.path.exists(SALIDA):
        with open(SALIDA, encoding="utf-8") as fh:
            hecho = json.load(fh).get("celdas", {})
    pendientes = [c for c in codigos if not ((hecho.get(c) or {}).get("ok") and hecho[c].get("cobertura") == FUENTE)]
    print(f"{len(codigos)} cuadrículas A/B · {len(codigos) - len(pendientes)} ya hechas · {len(pendientes)} por hacer", flush=True)
    if tope:
        pendientes = pendientes[:tope]
    candado = threading.Lock()
    t0 = time.time()
    n = [0]

    def guardar():
        tmp = SALIDA + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"actualizado": time.strftime("%Y-%m-%d %H:%M"), "celdas": hecho}, fh,
                      ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, SALIDA)

    def una(codigo: str):
        b = limites(codigo)
        anillo = [[b["oeste"], b["sur"]], [b["este"], b["sur"]], [b["este"], b["norte"]], [b["oeste"], b["norte"]]]
        try:
            res = g.buscar("arena_silicea", anillo)
            # sin catastro, áreas protegidas o cobertura del suelo no se puede afirmar «libre y
            # utilizable»: se reintenta en la próxima corrida
            cob = (res.get("libres") or {}).get("cobertura_fuente")
            ok = res.get("libres") is not None and cob == FUENTE
            fila = {"ok": ok, "cobertura": cob, **barrido.puntaje(res), "avisos": res.get("avisos") or []}
        except Exception as e:  # noqa: BLE001
            fila = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}"}
        with candado:
            hecho[codigo] = fila
            n[0] += 1
            if n[0] % 20 == 0 or n[0] == len(pendientes):
                guardar()
                v = n[0] / max(time.time() - t0, 1)
                print(f"{n[0]}/{len(pendientes)} · {v * 60:.0f} por min · faltan ~{(len(pendientes) - n[0]) / v / 60:.0f} min", flush=True)

    with ThreadPoolExecutor(PARALELO) as ex:
        list(ex.map(una, pendientes))
    guardar()
    ok = sum(1 for v in hecho.values() if v.get("ok"))
    print(f"listo: {ok} con áreas libres calculadas · {len(hecho) - ok} con error (volver a correr para reintentar)")


if __name__ == "__main__":
    main()
