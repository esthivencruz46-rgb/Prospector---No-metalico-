"""Descarga TODA la geología de INGEMMET (1:50 000 y 1:100 000) a backend/datos/geologia.sqlite.
Después la app la lee de ahí y no depende de que GEOCATMIN responda para la geología.

Reanudable: si se corta, se vuelve a correr y sigue. Para actualizar a la versión más reciente de
INGEMMET (p. ej. cada pocos meses) borrar datos/geologia.sqlite y volver a correrlo.

    cd backend
    python scripts/descargar_geologia.py            # las dos escalas
    python scripts/descargar_geologia.py 100K       # solo una
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import geologia_local as gl  # noqa: E402


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    escalas = sys.argv[1:] or ["100K", "50K"]     # la 100K primero: es más chica
    for e in escalas:
        n = gl.descargar(e, aviso=lambda m: print(m, flush=True))
        print(f"[{e}] listo: {n} polígonos guardados", flush=True)
    print(gl.estado())


if __name__ == "__main__":
    main()
