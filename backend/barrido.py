"""Barrido de una región: analiza muchas cuadrículas 1:25 000 de una vez (geología 50K/100K +
concesiones + áreas protegidas + uso del suelo), SIN Sentinel-2 (no gasta créditos), y las puntúa.

Es un trabajo en segundo plano (puede tardar minutos): POST /barrido lo crea, GET /barrido/{id}
devuelve el avance y los resultados nuevos (el frontend los va pintando en el mapa), DELETE lo cancela.
Cada cuadrícula se analiza con `geocatmin_rmi.buscar` (el mismo análisis de «Solo geología»), así que
el frontend guarda el resultado completo y abrir esa cuadrícula después es instantáneo.

Puntaje de una cuadrícula = hectáreas de zonas favorables LIBRES y UTILIZABLES, ponderadas por clase
(A 1 · B 0,7 · C 0,4). Más el detalle: ha por clase, % libre y la mejor zona.
"""

from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import geocatmin_rmi as g

MAX_CELDAS = 64
PESO = {"A": 1.0, "B": 0.7, "C": 0.4}
_trabajos: dict[str, dict] = {}
_candado = threading.Lock()


def puntaje(res: dict) -> dict:
    """Resumen y puntaje de una cuadrícula a partir del resultado de `buscar`."""
    ha = {"A": 0.0, "B": 0.0, "C": 0.0}
    ha_util = {"A": 0.0, "B": 0.0, "C": 0.0}
    mejor = None
    for a in res.get("afloramientos", []):
        cl = a["clase"]
        frac = a.get("util_pct")
        if frac is None:
            frac = a.get("libre_pct")
        frac = 100.0 if frac is None else frac
        u = a["area_ha"] * frac / 100
        ha[cl] += a["area_ha"]
        ha_util[cl] += u
        valor = u * PESO[cl]
        if mejor is None or valor > mejor[0]:
            mejor = (valor, {"clase": cl, "unidad": a["unidad"], "ha_util": round(u, 1), "centro": a["centro"]})
    lib = res.get("libres") or {}
    total = sum(ha_util[c] * PESO[c] for c in ha_util)
    return {
        "puntaje": round(total, 1),
        "ha": {c: round(v, 1) for c, v in ha.items()},
        "ha_util": {c: round(v, 1) for c, v in ha_util.items()},
        "util_pct_celda": lib.get("util_pct"), "libre_pct_celda": lib.get("libre_pct"),
        "n_concesiones": lib.get("n_concesiones"),
        "prohibido": any(r.get("nivel") == "prohibido" and r.get("pct_cuadricula", 0) >= 50 for r in res.get("restricciones") or []),
        "escala": res.get("escala_usada"),
        "mejor_zona": mejor[1] if mejor else None,
        "muestras": len(res.get("rmi", [])),
        "zonas_100k_A_ha": round(sum(x["area_ha"] for x in res.get("afloramientos_100k", []) if x["clase"] == "A"), 1),
    }


def _correr(tid: str, celdas: list[dict], material: str):
    t = _trabajos[tid]

    def una(c):
        if t["cancelado"]:
            return
        anillo = [[c["oeste"], c["sur"]], [c["este"], c["sur"]], [c["este"], c["norte"]], [c["oeste"], c["norte"]]]
        try:
            res = g.buscar(material, anillo)
            fila = {"codigo": c["codigo"], "ok": True, **puntaje(res), "resultado": res}
        except Exception as e:  # noqa: BLE001
            fila = {"codigo": c["codigo"], "ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}"}
        with _candado:
            t["resultados"].append(fila)

    # 3 cuadrículas a la vez: cada una ya hace varias consultas en paralelo a GEOCATMIN
    with ThreadPoolExecutor(3) as ex:
        list(ex.map(una, celdas))
    t["fin"] = time.time()


def iniciar(celdas: list[dict], material: str = "arena_silicea") -> str:
    if not celdas:
        raise g.ErrorBusqueda("No hay cuadrículas para barrer.")
    if len(celdas) > MAX_CELDAS:
        raise g.ErrorBusqueda(f"Máximo {MAX_CELDAS} cuadrículas por barrido (elegiste {len(celdas)}).")
    tid = uuid.uuid4().hex[:12]
    with _candado:
        # se olvidan los trabajos terminados hace más de 2 horas
        for k in [k for k, v in _trabajos.items() if v.get("fin") and time.time() - v["fin"] > 7200]:
            del _trabajos[k]
        _trabajos[tid] = {"total": len(celdas), "resultados": [], "inicio": time.time(), "fin": None, "cancelado": False}
    threading.Thread(target=_correr, args=(tid, celdas, material), daemon=True).start()
    return tid


def estado(tid: str, desde: int = 0) -> dict:
    t = _trabajos.get(tid)
    if not t:
        raise KeyError(tid)
    with _candado:
        nuevos = t["resultados"][desde:]
        hechas = len(t["resultados"])
    return {"total": t["total"], "hechas": hechas, "terminado": t["fin"] is not None or t["cancelado"],
            "cancelado": t["cancelado"], "segundos": round((t["fin"] or time.time()) - t["inicio"]),
            "resultados": nuevos}


def cancelar(tid: str) -> None:
    if tid in _trabajos:
        _trabajos[tid]["cancelado"] = True
