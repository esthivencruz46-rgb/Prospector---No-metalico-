"""Verifica que cada cita de evidencia_boletines.CITAS esté en su boletín y devuelve su página (PDF). Salida: citas_paginas.json"""
import glob, json, os, re, sys, unicodedata
import fitz
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evidencia_boletines import CITAS  # noqa: E402

DIR = r"c:/Users/ESTHIVEN/Downloads/prospector-rmi_1/prospector-rmi/boletines/"


def norm(s):
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\[[^\]]*\]", "", s)           # correcciones OCR entre corchetes
    return re.sub(r"[^a-z0-9]", "", s)


def archivo(cod):
    n, s = cod.split("-")
    for f in glob.glob(DIR + "*"):
        m = re.search(r"([AB])-?0*(\d+)", os.path.basename(f))
        if m and m.group(1) == s and m.group(2) == n:
            return f


cache = {}
res = {}
mal = 0
for uid, lista in CITAS.items():
    for cod, txt, tema in lista:
        if cod not in cache:
            doc = fitz.open(archivo(cod))
            cache[cod] = [norm(p.get_text()) for p in doc]
        pags = cache[cod]
        clave = norm(txt)
        pag = None
        for largo in (60, 40, 25):
            frag = clave[:largo]
            for i, t in enumerate(pags):
                if frag in t:
                    pag = i + 1; break
            if pag:
                break
        # comprobar también el final (puede cruzar de página)
        fin_ok = any(clave[-30:] in t for t in pags[max(0, (pag or 1) - 1):(pag or 1) + 1]) if pag else False
        res[f"{uid}|{cod}|{clave[:40]}"] = pag
        if not pag or not fin_ok:
            mal += 1
            print("REVISAR", uid, cod, pag, "fin" if not fin_ok else "", txt[:70])
json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "citas_paginas.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("citas:", len(res), "por revisar:", mal)
