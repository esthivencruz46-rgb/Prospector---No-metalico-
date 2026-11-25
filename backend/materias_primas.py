"""Materias primas creadas por el usuario en la app (editor «🧪 Materias primas»).

El usuario no escribe expresiones regulares ni SQL: da PALABRAS por clase, FORMACIONES de interés,
palabras que DESCARTAN y capas de muestras RMI. Aquí se convierten en la misma estructura que usa
la arena silícea (`materiales.MATERIALES` / `materiales.FORMACIONES`), así que la búsqueda por
cuadrícula, el catálogo de formaciones, el filtro del mapa, las muestras y el barrido funcionan igual.

Se guardan en backend/datos/materias_primas.json (o MATERIAS_PRIMAS_JSON). La arena silícea es
de fábrica (en el código, con reglas finas): se puede ver y DUPLICAR, no editar.

Formato de una materia prima:
    {"id": "caliza", "nombre": "Caliza para cemento", "sinonimos": ["cemento"],
     "clases": {"A": ["caliza micrítica", "caliza"], "B": ["calizas con margas"], "C": ["marga", "calcáreo"]},
     "formaciones": ["Formación Chulec", "Grupo Pucará"],      # → clase B (si el polígono nombra una roca de interés)
     "descartar": ["dolomía", "volcánico"],                     # rebajan la clase o descartan
     "rmi": ["Caliza"],                                         # capas de SERV_ROCAS_MINERALES_INDUSTRIALES
     "nota": "texto libre"}
"""
from __future__ import annotations

import json
import os
import re
import threading
import unicodedata

import materiales as m

RUTA = os.environ.get("MATERIAS_PRIMAS_JSON",
                      os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos", "materias_primas.json"))
FABRICA = {"arena_silicea"}
_candado = threading.Lock()

# rocas comunes en las descripciones de INGEMMET: las que NO son de interés para la materia prima
# sirven para rebajar la clase si dominan el polígono (como lutitas/calizas para la sílice)
_ROCAS_COMUNES = ["LUTITA", "LIMOLITA", "LIMOARCILLITA", "ARCILLITA", "CALIZA", "MARGA", "DOLOM", "PIZARRA",
                  "FILITA", "ESQUISTO", "CONGLOMERADO", "YESO", "CARBÓN", "ARENISCA", "CUARCITA", "ARENA",
                  "ANDESITA", "DACITA", "RIOLITA", "BASALTO", "TOBA", "GRANITO", "GRANODIORITA", "DIORITA",
                  "TONALITA", "GNEIS", "MÁRMOL", "BRECHA", "LAVA", "ARCOSA", "GRAUVACA"]
_VOCAL = {"A": "[AÁ]", "E": "[EÉ]", "I": "[IÍ]", "O": "[OÓ]", "U": "[UÚÜ]",
          "Á": "[AÁ]", "É": "[EÉ]", "Í": "[IÍ]", "Ó": "[OÓ]", "Ú": "[UÚÜ]", "Ü": "[UÚÜ]", "N": "[NÑ]", "Ñ": "[NÑ]"}


def _sin_tildes(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def slug(texto: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", _sin_tildes(str(texto)).lower()).strip("_")
    return s[:40] or "materia"


def _limpias(lista) -> list[str]:
    """Frases limpias, sin repetir (mayúsculas, espacios simples)."""
    out = []
    for x in lista or []:
        t = " ".join(re.sub(r"[^\wÁÉÍÓÚÜÑáéíóúüñ\- ]", " ", str(x)).split()).upper()
        if len(t) >= 3 and t not in out:
            out.append(t)
    return out


def regex_frase(frase: str) -> str:
    """«arenisca cuarzosa» → coincide con ARENISCAS CUARZOSAS, Arenisca cuarzosa… (sin importar tildes
    ni plural; cada palabra por su comienzo, con hasta 2 palabras en medio)."""
    palabras = [("".join(_VOCAL.get(c, re.escape(c)) for c in w)) + r"\w*" for w in frase.split()]
    return r"\b" + r"(?:\W+\w+){0,2}?\W+".join(palabras)


def _sql_frases(campos: list[str], frases: list[str]) -> str | None:
    """LIKE con y sin tildes (como lo escriben INGEMMET y el usuario)."""
    variantes = []
    for f in frases:
        for v in {f, _sin_tildes(f)}:
            v = v.replace("'", "''").replace(" ", "%")
            if v not in variantes:
                variantes.append(v)
    return m._sql(campos, variantes) if variantes else None


def compilar(d: dict) -> tuple[dict, list[dict]]:
    """Definición del usuario → (cfg para MATERIALES, ítems para FORMACIONES)."""
    clases = {k: _limpias((d.get("clases") or {}).get(k)) for k in ("A", "B", "C")}
    formaciones = _limpias(d.get("formaciones"))
    descartar = _limpias(d.get("descartar"))
    interes = [f for k in ("A", "B", "C") for f in clases[k]]
    # Las ROCAS de clase B entran como «A» con la marca «(clase B)» y bajan a B al final (motivos_b):
    # así pasan por las mismas reglas de rebaje que las A (subordinada a otra roca, roca descartada →
    # C). Las FORMACIONES usan la regla de formación (nombre en UNIDAD + que el polígono nombre una
    # roca de interés).
    reglas = [("A", f.capitalize(), regex_frase(f)) for f in clases["A"]]
    reglas += [("A", f"{f.capitalize()} (clase B)", regex_frase(f)) for f in clases["B"]]
    reglas += [("C", f"{f.capitalize()} (verificar)", regex_frase(f)) for f in clases["C"]]
    reglas += [("B", f"Formación de interés: {f.title()}", regex_frase(f)) for f in formaciones]
    rx_interes = "|".join(regex_frase(f) for f in interes) or r"(?!x)x"
    # rocas comunes que NO son de interés (si dominan el polígono, bajan la clase)
    no_interes = [r for r in _ROCAS_COMUNES if not re.search(rx_interes, r) and not any(r in f for f in interes)]
    cfg = {
        "nombre": str(d.get("nombre") or "Sin nombre").strip()[:60],
        "activo": True, "usuario": True,
        "sinonimos": [s.lower() for s in _limpias(d.get("sinonimos"))],
        "rmi": [(n.title(), None) for n in _limpias(d.get("rmi"))],
        "litologia": reglas,
        "excluir": "|".join(regex_frase(f) for f in descartar) or None,
        "roca_interes": rx_interes,
        "rocas_no": "|".join(regex_frase(r) for r in no_interes) or r"(?!x)x",
        "motivos_b": r".*\(CLASE B\)",   # rocas de clase B: bajan de A a B al final
        "sql50": " OR ".join(x for x in (_sql_frases(["LITOLOGIA", "DESCRIP"], interes),
                                          _sql_frases(["UNIDAD"], formaciones)) if x) or "1=0",
        "sql100": _sql_frases(["DESCRIP"], interes) or "1=0",
    }
    items = [{"id": slug(f), "nombre": f.title(), "tipo": "Formación", "edad": "", "region": "",
              "descripcion": "Formación de interés (definida por el usuario).",
              "patron": regex_frase(f), "sql50": _sql_frases(["UNIDAD"], [f]), "sql100": None} for f in formaciones]
    items += [{"id": "roca_" + slug(f), "nombre": f.capitalize(), "tipo": "Roca", "edad": "", "region": "Todo el Perú",
               "descripcion": f"Clase {k}: polígonos cuya litología o descripción dice «{f.lower()}».",
               "patron": regex_frase(f), "sql50": _sql_frases(["LITOLOGIA", "DESCRIP"], [f]),
               "sql100": _sql_frases(["DESCRIP"], [f])} for k in ("A", "B", "C") for f in clases[k]]
    return cfg, items


def validar(d: dict) -> dict:
    nombre = str(d.get("nombre") or "").strip()
    if len(nombre) < 3:
        raise ValueError("Ponle un nombre a la materia prima (mínimo 3 letras).")
    clases = d.get("clases") or {}
    if not any(_limpias(clases.get(k)) for k in ("A", "B", "C")) and not _limpias(d.get("formaciones")):
        raise ValueError("Agrega al menos una palabra (clase A, B o C) o una formación de interés.")
    mid = slug(d.get("id") or nombre)
    if mid in FABRICA:
        raise ValueError("Ese nombre es de una materia prima de fábrica: usa otro.")
    return {"id": mid, "nombre": nombre[:60], "sinonimos": _limpias(d.get("sinonimos")),
            "clases": {k: _limpias(clases.get(k)) for k in ("A", "B", "C")},
            "formaciones": _limpias(d.get("formaciones")), "descartar": _limpias(d.get("descartar")),
            "rmi": _limpias(d.get("rmi")), "nota": str(d.get("nota") or "")[:500]}


def leer() -> list[dict]:
    try:
        with open(RUTA, encoding="utf-8") as fh:
            return json.load(fh).get("materias", [])
    except (FileNotFoundError, ValueError):
        return []


def _escribir(lista: list[dict]) -> None:
    os.makedirs(os.path.dirname(RUTA), exist_ok=True)
    tmp = RUTA + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"materias": lista}, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, RUTA)


def recargar() -> None:
    """Vuelve a armar MATERIALES y FORMACIONES (se modifican en el sitio: todos los módulos los ven)."""
    with _candado:
        for k in [k for k, v in m.MATERIALES.items() if v.get("usuario")]:
            m.MATERIALES.pop(k, None)
            m.FORMACIONES.pop(k, None)
        for d in leer():
            try:
                cfg, items = compilar(d)
            except Exception:  # noqa: BLE001  (una definición rota no tumba las demás)
                continue
            m.MATERIALES[d["id"]] = cfg
            m.FORMACIONES[d["id"]] = items


def guardar(d: dict) -> dict:
    limpio = validar(d)
    compilar(limpio)                 # que compile antes de guardarla
    lista = [x for x in leer() if x["id"] != limpio["id"]] + [limpio]
    _escribir(lista)
    recargar()
    return limpio


def borrar(mid: str) -> bool:
    lista = leer()
    nueva = [x for x in lista if x["id"] != mid]
    if len(nueva) == len(lista):
        return False
    _escribir(nueva)
    recargar()
    return True


def probar(d: dict, textos: dict) -> dict:
    """Clasifica un texto de ejemplo con una definición SIN guardarla (botón «Probar»)."""
    cfg, _ = compilar(validar(d))
    clave = "__prueba__"
    m.MATERIALES[clave] = cfg
    try:
        r = m.clasificar(clave, textos)
    finally:
        m.MATERIALES.pop(clave, None)
    return {"clase": r[0] if r else None, "motivo": r[1] if r else "No coincide con ninguna regla."}


def publica(mid: str) -> dict | None:
    """Definición para mostrar en el editor (las de fábrica, como resumen de solo lectura)."""
    if mid in FABRICA:
        cfg = m.MATERIALES[mid]
        # clases FINALES (las rocas que internamente entran como A terminan en B: m._MOTIVOS_ROCA)
        roca = lambda mot: re.match(m._MOTIVOS_ROCA, m.normalizar(mot))  # noqa: E731
        clases = {"A": [mot for c, mot, _ in cfg["litologia"] if c == "A" and not roca(mot)],
                  "B": [mot for c, mot, _ in cfg["litologia"] if (c == "A" and roca(mot)) or c == "B"],
                  "C": [mot for c, mot, _ in cfg["litologia"] if c == "C"]}
        return {"id": mid, "nombre": cfg["nombre"], "fabrica": True,
                "clases": clases,
                "formaciones": [f["nombre"] for f in m.FORMACIONES.get(mid, []) if f["tipo"] in ("Formación", "Grupo")],
                "descartar": ["rocas ígneas y volcánicas (andesita, granito, toba…)"],
                "rmi": [n for n, _ in cfg["rmi"]], "sinonimos": cfg.get("sinonimos", []), "nota":
                "De fábrica: A = depósitos de arena silícea/cuarzosa · B = arenisca cuarzosa/cuarcítica, cuarcita y "
                "formaciones silíceas conocidas · C = verificar. Duplícala para crear una variante editable."}
    return next((x for x in leer() if x["id"] == mid), None)


recargar()
