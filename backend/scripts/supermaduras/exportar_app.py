"""Arma backend/datos/supermaduras.json (lo que sirve GET /supermaduras) a partir de:
  - la base por unidad y cuadrícula de recopilar2.py (supermaduras2.json; necesita datos/geologia.sqlite + GEOCATMIN),
  - las fichas finales del informe (fichas_final.json),
  - la evidencia curada de los boletines (evidencia_boletines.py + evidencia_v3.py; páginas en citas_paginas.json).
Uso (desde backend/): python scripts/supermaduras/exportar_app.py <supermaduras2.json>
"""
import json, math, os, re, sys, time, unicodedata

from pyproj import Transformer

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from evidencia_boletines import AUTORES, CITAS, QUIMICA, ESPECIFICACIONES, OCURRENCIAS  # noqa: E402

BASE = json.load(open(sys.argv[1], encoding="utf-8"))
FICHAS = json.load(open(os.path.join(AQUI, "fichas_final.json"), encoding="utf-8"))
PAGS = json.load(open(os.path.join(AQUI, "citas_paginas.json"), encoding="utf-8"))
LISTA = json.load(open(os.path.join(AQUI, "lista_boletines.json"), encoding="utf-8"))
SALIDA = os.path.join(AQUI, "..", "..", "datos", "supermaduras.json")
FAB = BASE["fabrica"]
ALFA = "abcdefghijklmnñopqrstuvxyz"
LINKS = {f"{b['num']}-A": b["link"] for b in LISTA["serieA"]}
LINKS.update({b["num"]: b["link"] for b in LISTA["serieB"]})

# prioridad = lectura del informe (1 = mejor evidencia de supermadurez); es una guía, no el ranking del usuario
PRIORIDAD = {"chimu": (1, "Supermadura con química"), "goyllarisquizga": (1, "Supermadura con química"),
             "marcavilca": (1, "Supermadura (petrografía)"), "vivian": (2, "Supermadura (petrografía, sin química)"),
             "farrat": (2, "Madura a supermadura con química"), "eolico": (2, "Variable según el manto"),
             "agua_caliente": (2, "Supermadura por textura"), "hualhuani": (3, "Madura; química de fundente"),
             "cushabatay": (3, "Madura"), "oriente": (3, "Madura a supermadura"), "huancane": (3, "Heterogénea"),
             "salto_fraile": (3, "Madura"), "labra": (4, "Madura con óxidos"), "naupe": (4, "Certeza baja"), "yauca": (4, "Certeza baja")}
UNI_ID = {"Formación Chimú": "chimu", "Grupo Goyllarisquizga": "goyllarisquizga", "Formación Farrat": "farrat",
          "Formación Hualhuani": "hualhuani", "Fm. Hualhuani": "hualhuani", "Formación Huancané": "huancane"}
TR = {z: Transformer.from_crs(f"EPSG:327{z}", "EPSG:4326", always_xy=True) for z in (17, 18, 19)}


def celda(lat, lon):
    fila = math.floor(-lat / 0.5) + 1
    col = math.floor((lon + 81.5) / 0.5)
    norte, oeste = -(fila - 1) * 0.5, -81.5 + col * 0.5
    n50, e50 = lat >= norte - 0.25, lon >= oeste + 0.25
    cod50 = f"{fila}{ALFA[col]}" + str({(True, True): 1, (False, True): 2, (False, False): 3, (True, False): 4}[(n50, e50)])
    norte50 = norte if n50 else norte - 0.25
    oeste50 = oeste + 0.25 if e50 else oeste
    return f"{cod50}-" + ("N" if lat >= norte50 - 0.125 else "S") + ("E" if lon >= oeste50 + 0.125 else "O")


def hav(la1, lo1, la2, lo2):
    r = math.radians
    a = math.sin(r(la2 - la1) / 2) ** 2 + math.cos(r(la1)) * math.cos(r(la2)) * math.sin(r(lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def norm(s):
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\[[^\]]*\]", "", s))


def ref_corta(cod):
    a, anio, _ = AUTORES[cod]
    if "," not in a:
        quien = "INGEMMET" if a.startswith("INGEMMET") else a.split(" (")[0][:40]
    else:
        ap = [x.strip().split(",")[0] for x in re.split(r";| & ", a.split(" (")[0]) if x.strip()]
        quien = ap[0] if len(ap) == 1 else (f"{ap[0]} & {ap[1]}" if len(ap) == 2 else f"{ap[0]} et al.")
    return f"Bol. {cod} · {quien} ({anio or 's. f.'})"


def grado(si, fe, aprox):
    if aprox:
        return "fundente"
    if si >= 95 and fe <= 0.10:
        return "vidrio"
    if si >= 95 and fe <= 0.5:
        return "refractario"
    if si >= 90 and fe <= 1.5:
        return "fundente"
    return "no"


unidades = []
for u in BASE["unidades"]:
    if not u["filas"]:
        continue
    k = u["id"]
    f = FICHAS["fichas"][k]
    pr = PRIORIDAD.get(k, (5, "Cuarcita metamórfica") if u["tipo"] == "meta" else (4, ""))
    unidades.append({
        "id": k, "nombre": u["nombre"], "tipo": u["tipo"], "prioridad": pr[0], "prioridad_txt": pr[1],
        "madurez": f["madurez"], "certeza": f["certeza"], "definicion": f["definicion"], "puntos": f["puntos"],
        "area_km2": u["area_total"], "n_hojas": len(u["filas"]), "n_celdas": len(u["celdas25"]),
        # [código, km², afloramientos, carta, km a la fábrica, departamento, provincia]
        "celdas": [[c["codigo"], round(c["km2"], 2), c["pols"], c["carta"], c["km_fabrica"], c["departamento"], c["provincia"]]
                   for c in u["celdas25"]],
        "citas": [{"bol": cod, "ref": ref_corta(cod), "pag": PAGS.get(f"{k}|{cod}|{norm(txt)[:40]}"), "tema": tema, "texto": txt,
                   "link": LINKS.get(cod, "")} for cod, txt, tema in CITAS.get(k, [])],
    })
orden = {k: i for i, k in enumerate(FICHAS["orden"])}
unidades.sort(key=lambda x: orden.get(x["id"], 999))

quimica = []
for r in QUIMICA:
    bol, tabla, pag, nombre, lugar, hoja, z, n, e_, uni, esp, desc, muestra, si, fe, al, nota = r
    lo, la = TR[z].transform(e_, n)
    aprox = bol == "30-B"
    rango = "3 análisis" in nombre
    txt = {"si": f"{si:.2f}", "fe": f"{fe:.2f}", "al": f"{al:.2f}"}
    if aprox:
        cho = "Choquisani" in nombre
        txt = {"si": "> 90", "fe": "< 1,5" if cho else "0,53–0,96", "al": "> 1,5" if cho else "1,00–1,78"}
    elif rango:
        txt = {"si": "92,8–93,0", "fe": "0,70–1,07", "al": "2,78–2,88"}
    else:
        txt = {k2: v.replace(".", ",") for k2, v in txt.items()}
    quimica.append({"nombre": nombre, "lugar": lugar, "hoja": hoja, "celda": celda(la, lo), "lat": round(la, 5), "lon": round(lo, 5),
                    "km": round(hav(FAB[0], FAB[1], la, lo)), "unidad": uni, "unidad_id": next((v for k2, v in UNI_ID.items() if uni.startswith(k2)), None),
                    "espesor": esp, "descripcion": desc, "nota": nota, "muestra": muestra, "sio2": si, "fe2o3": fe, "al2o3": al,
                    "sio2_txt": txt["si"], "fe2o3_txt": txt["fe"], "al2o3_txt": txt["al"], "grado": grado(si, fe, aprox),
                    "fuente": f"{ref_corta(bol)}" + (f", tabla {tabla}" if tabla else "") + f", pág. {pag}", "link": LINKS.get(bol, "")})
quimica.sort(key=lambda q: (-q["sio2"], q["fe2o3"]))

ocurrencias = []
for bol, pag, nombre, lugar, hoja, z, n, e_, uni, est in OCURRENCIAS:
    lo, la = TR[z].transform(e_, n)
    ocurrencias.append({"nombre": nombre, "lugar": lugar, "hoja": hoja, "celda": celda(la, lo), "lat": round(la, 5), "lon": round(lo, 5),
                        "km": round(hav(FAB[0], FAB[1], la, lo)), "unidad": uni, "estado": est,
                        "fuente": f"{ref_corta(bol)}, pág. {pag}", "link": LINKS.get(bol, "")})

# fotos de los boletines (recortadas y revisadas a mano: fotos_final.json) con su ubicación (geolocalizar_fotos.py)
fotos = []
ubic = json.load(open(os.path.join(AQUI, "fotos_ubicacion.json"), encoding="utf-8")) if os.path.exists(os.path.join(AQUI, "fotos_ubicacion.json")) else {}
for x in json.load(open(os.path.join(AQUI, "fotos_final.json"), encoding="utf-8")):
    u = ubic.get(x["archivo_img"], {})
    fotos.append({"archivo": x["archivo_img"], "unidad": x["unidad"], "leyenda": x["leyenda"], "boletin": x["boletin"],
                  "ref": ref_corta(x["boletin"]), "pag": x["pag"], "pag_foto": x.get("pag_foto", x["pag"]),
                  "link": LINKS.get(x["boletin"], ""), "micro": bool(x.get("micro")), "cantera": x.get("origen") == "cantera",
                  "nota": x.get("nota", ""), "celda": u.get("celda"), "hojas100": u.get("hojas100", []),
                  "precision": u.get("precision", "unidad")})

salida = {
    "generado": time.strftime("%Y-%m-%d"), "fabrica": FAB, "n_boletines": len(AUTORES), "fotos": fotos,
    "unidades": unidades, "quimica": quimica, "ocurrencias": ocurrencias,
    "especificaciones": [{"uso": a, "texto": b, "fuente": f"{ref_corta(c)}, pág. {d}"} for a, b, c, d in ESPECIFICACIONES],
    "boletines": {c: {"autores": a, "anio": y, "titulo": t, "link": LINKS.get(c, "")} for c, (a, y, t) in AUTORES.items()},
}
json.dump(salida, open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("unidades:", len(unidades), "| cuadrículas:", sum(len(x["celdas"]) for x in unidades), "| química:", len(quimica),
      "| ocurrencias:", len(ocurrencias), "|", os.path.getsize(SALIDA) // 1024, "KB")
