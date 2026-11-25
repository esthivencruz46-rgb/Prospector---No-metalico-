"""Selecciona las fotos de los boletines relevantes para cada unidad supermadura. Salida: sel_fotos.json"""
import json, os, re, sys, unicodedata
sys.stdout.reconfigure(encoding="utf-8")
ESC = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ESC)
from evidencia_boletines import QUIMICA, OCURRENCIAS  # noqa: E402


def st(s):
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().upper()


inv = json.load(open(os.path.join(ESC, "fotos_inventario.json"), encoding="utf-8"))
ext = json.load(open(os.path.join(ESC, "bol_extractos2.json"), encoding="utf-8"))
FOTO = ("FOTO", "FOTOGRAFIA", "FOTOS", "FOTOMICROGRAFIA", "MICROFOTOGRAFIA", "LAMINA")
FOSIL = r"CODIGO DE CAMPO|\(X ?\d|X\d+[,.]?\d*\)|AMMONIT|AMONIT|BIVALV|GASTEROPOD|TISSOTIA|PELECIPOD|BRAQUIOPOD|EDAD ?:"
UNI_ID = {"Formación Chimú": "chimu", "Grupo Goyllarisquizga": "goyllarisquizga", "Formación Farrat": "farrat",
          "Formación Hualhuani": "hualhuani", "Fm. Hualhuani": "hualhuani", "Formación Huancané": "huancane", "Fm. Labra": "labra",
          "Fm. Hualhuani – cuarcitas": "hualhuani"}
# canteras / ocurrencias → unidad
canteras = {}
for r in QUIMICA:
    nombre, uni = r[3], r[9]
    k = next((v for kk, v in UNI_ID.items() if uni.startswith(kk)), "goyllarisquizga" if r[0] == "33-B" else None)
    for parte in re.split(r"[·,]", nombre):
        n = st(re.sub(r"^(Cantera|Ocurrencia|Canteras)\s+", "", parte.strip())).replace("(3 ANALISIS SIN ROTULO)", "").strip()
        if len(n) > 3 and k:
            canteras[n] = k
for o in OCURRENCIAS:
    k = next((v for kk, v in UNI_ID.items() if o[8].startswith(kk)), "goyllarisquizga" if "Goyllarisquizga" in o[8] else None)
    if k:
        canteras[st(o[2])] = k
canteras.update({"SUMIAPE": "goyllarisquizga", "FATIMA 1": "hualhuani", "OXANA": "labra"})
# rangos de páginas de cada sección de unidad en cada boletín
MAPA_SEC = {"chimu": "chimu", "farrat": "farrat", "goyllarisquizga": "goyllarisquizga", "hualhuani": "hualhuani", "yura": "hualhuani",
            "marcavilca": "marcavilca", "huancane": "huancane", "cushabatay": "cushabatay", "vivian": "vivian",
            "agua_caliente": "agua_caliente", "oriente": "oriente", "eolico": "eolico", "labra": "labra", "salto_fraile": "salto_fraile",
            "m_sandia": "m_sandia", "m_cerro_negro": "m_cerro_negro", "m_chagrapi": "m_chagrapi", "m_excelsior": "m_excelsior", "m_contaya": "m_contaya"}
secciones = {}
for b in ext.values():
    for k, lst in b["secciones"].items():
        if k in MAPA_SEC:
            for s in lst:
                secciones.setdefault(b["codigo"], []).append((s["pag"], s["pag_fin"] + 1, MAPA_SEC[k]))
TEMA = r"CUARZ|CUARCIT|ARENISCA|ARENA|SILICE|SILICEA|SECCION DELGADA|NICOLES|MICROFOTO|FOTOMICRO|AUMENTO|MUESTRA DE MANO|DUNA|EOLIC"
sel = []
for x in inv:
    if x["tipo"] not in FOTO or not x["imagenes"] and x["tipo"] != "LAMINA":
        continue
    S = st(x["leyenda"])
    if re.search(FOSIL, S):
        continue
    uds = [u for u in x["unidades"] if u != "oriente" or "ORIENTE" in S]
    origen = "nombre" if uds else None
    if not uds:
        for n, k in canteras.items():
            if re.search(r"\b" + re.escape(n) + r"\b", S):
                uds, origen = [k], "cantera"
                break
    if not uds and re.search(TEMA, S):
        en = [u for (a, b, u) in secciones.get(x["boletin"], []) if a <= x["pag"] <= b]
        if en:
            uds, origen = [en[0]], "seccion"
    if uds:
        sel.append({**x, "unidad": uds[0], "origen": origen,
                    "micro": bool(re.search(r"SECCION DELGADA|NICOLES|MICROFOTO|FOTOMICRO|AUMENTO|\d+ ?X\b|CZ\)", S))})
json.dump(sel, open(os.path.join(ESC, "sel_fotos.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
from collections import Counter
print(len(sel), Counter(s["unidad"] for s in sel).most_common(), Counter(s["origen"] for s in sel), "micro:", sum(s["micro"] for s in sel))
