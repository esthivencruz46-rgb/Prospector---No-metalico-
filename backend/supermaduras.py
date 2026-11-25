"""Unidades geológicas supermaduras del Perú (arenas y areniscas casi solo de cuarzo, y cuarcitas metamórficas).

Sirve datos/supermaduras.json, generado por scripts/supermaduras/exportar_app.py a partir del informe
«Arenas y areniscas supermaduras del Perú» (51 boletines de INGEMMET leídos): ficha por unidad, citas textuales con
página, química de canteras, ocurrencias de sílice y reparto del área por cuadrícula 1:25 000 (mismo código que la app).
No consulta a INGEMMET.
"""
import json
import os
import re

RUTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos", "supermaduras.json")
_cache: dict = {"mtime": None, "datos": None, "por_celda": None}


def datos() -> dict:
    """Todo el contenido (caché por fecha del archivo). {} si no existe."""
    if not os.path.exists(RUTA):
        return {}
    mt = os.path.getmtime(RUTA)
    if _cache["mtime"] != mt:
        with open(RUTA, encoding="utf-8") as f:
            d = json.load(f)
        idx: dict[str, list] = {}
        for u in d.get("unidades", []):
            for cod, km2, pols, carta, km, *_ in u["celdas"]:
                idx.setdefault(cod, []).append({"id": u["id"], "nombre": u["nombre"], "tipo": u["tipo"], "prioridad": u["prioridad"],
                                                "prioridad_txt": u["prioridad_txt"], "km2": km2, "afloramientos": pols, "carta": carta})
        for v in idx.values():
            v.sort(key=lambda x: (x["prioridad"], -x["km2"]))
        _cache.update(mtime=mt, datos=d, por_celda=idx)
    return _cache["datos"]


_COD25 = re.compile(r"^\d{1,2}[a-zñ][1-4]-(NE|NO|SE|SO)$")
CARPETA_FOTOS = os.path.join(os.path.dirname(RUTA), "fotos_boletines")
_ARCHIVO_FOTO = re.compile(r"^\d{1,3}-[AB]_p\d{1,4}_\d{1,4}\.jpg$")
# precisión de la ubicación de una foto (geolocalizar_fotos.py): cuanto menor, más cerca de la cuadrícula
_ORDEN_PRECISION = {"cantera": 0, "utm_texto": 0, "hoja_nombrada": 1, "boletin": 2}


def ruta_foto(archivo: str) -> str | None:
    """Ruta local de una foto de boletín (solo nombres válidos: nada de rutas)."""
    if not _ARCHIVO_FOTO.match(archivo or ""):
        return None
    p = os.path.join(CARPETA_FOTOS, archivo)
    return p if os.path.exists(p) else None


def fotos_de_celda(codigo: str, unidades: set[str]) -> list[dict]:
    """Fotos para una cuadrícula: las tomadas en ella (canteras/UTM) y las de su hoja 1:100 000 que muestran una
    unidad presente en la cuadrícula (la hoja la nombra la leyenda o la cubre el boletín)."""
    d = datos()
    m = re.match(r"^(\d{1,2})([a-zñ])", codigo)
    hoja = f"{int(m.group(1))}-{m.group(2)}" if m else ""
    out = []
    for f in d.get("fotos", []):
        if f.get("celda") == codigo:
            out.append({**f, "motivo": "Tomada en esta cuadrícula"})
        elif hoja in f.get("hojas100", []) and f["unidad"] in unidades and not f.get("celda"):
            out.append({**f, "motivo": "Misma hoja 1:100 000 y misma unidad" if f.get("precision") == "hoja_nombrada"
                        else "Boletín de esta hoja, misma unidad"})
        elif f.get("celda") and hoja in f.get("hojas100", []) and f["unidad"] in unidades:
            out.append({**f, "motivo": f"Cantera de la misma hoja ({f['celda']})"})
    out.sort(key=lambda f: (f["motivo"] != "Tomada en esta cuadrícula", _ORDEN_PRECISION.get(f.get("precision"), 3), not f.get("micro")))
    return out[:16]


def en_celda(codigo: str) -> dict:
    """Unidades supermaduras, canteras con química y ocurrencias dentro de una cuadrícula 1:25 000 (p. ej. «15g1-SE»)."""
    codigo = codigo.strip()
    if not _COD25.match(codigo):
        raise ValueError("Código de cuadrícula 1:25 000 inválido (ejemplo: 27k4-NE)")
    d = datos()
    if not d:
        return {"codigo": codigo, "disponible": False, "unidades": [], "quimica": [], "ocurrencias": [], "fotos": []}
    uds = _cache["por_celda"].get(codigo, [])
    return {"codigo": codigo, "disponible": True, "unidades": uds,
            "quimica": [q for q in d["quimica"] if q["celda"] == codigo],
            "ocurrencias": [o for o in d["ocurrencias"] if o["celda"] == codigo],
            "fotos": fotos_de_celda(codigo, {u["id"] for u in uds})}
