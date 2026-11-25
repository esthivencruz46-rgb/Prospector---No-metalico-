"""Inventario de fotos de los boletines: leyenda (Foto/Fotografía/Lámina/Figura…), página, imágenes de la página
y relevancia para las unidades supermaduras. Uso: python -I inventario_fotos.py <carpeta> <salida.json>"""
import json, os, re, sys, unicodedata
import fitz
sys.stdout.reconfigure(encoding="utf-8")
DIR, OUT = sys.argv[1], sys.argv[2]


def st(s):
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().upper()


LEY = re.compile(r"^\s*(FOTO|FOTOGRAFIA|FOTOMICROGRAFIA|MICROFOTOGRAFIA|FOTOS|LAMINA|FIG\.?|FIGURA)\s*(N\s*[°ºO\.]?\s*)?(\d{1,3}(\.\d{1,3})?[A-Z]?)\b")
UNIDADES = {
    "chimu": r"CHIMU", "farrat": r"FARRAT", "goyllarisquizga": r"GOYLLARISQUIZGA", "hualhuani": r"HUALHUANI",
    "marcavilca": r"MARCAVILCA|MORRO SOLAR", "salto_fraile": r"SALTO DEL FRAILE", "vivian": r"VIVIAN",
    "cushabatay": r"CUSHABATAY", "agua_caliente": r"AGUA CALIENTE", "oriente": r"GRUPO ORIENTE", "huancane": r"HUANCANE",
    "labra": r"\bLABRA\b", "eolico": r"EOLIC|DUNA|MEDANO|BARCAN|BARJAN", "m_sandia": r"SANDIA", "m_cerro_negro": r"CERRO NEGRO",
    "m_chagrapi": r"CHAGRAPI", "m_excelsior": r"EXCELSIOR", "m_contaya": r"CONTAYA",
}
TEMA = r"CUARZ|CUARCIT|ARENISC|ARENA|SILICE|SILICEA|SECCION DELGADA|NICOLES|MICROSCOP|MUESTRA|CANTERA|AFLORAMIENTO|ESTRATIFICACION"
res = []
for f in sorted(os.listdir(DIR)):
    if not f.lower().endswith(".pdf"):
        continue
    m = re.search(r"([AB])-?0*(\d+)", f)
    cod = f"{m.group(2)}-{m.group(1)}"
    try:
        doc = fitz.open(os.path.join(DIR, f))
    except Exception:  # noqa: BLE001
        continue
    n_ley = 0
    for i, pg in enumerate(doc):
        area_pag = pg.rect.width * pg.rect.height
        imgs = []
        for inf in pg.get_image_info(xrefs=True):
            r = fitz.Rect(inf["bbox"])
            frac = (r.width * r.height) / area_pag
            if frac > 0.02:
                imgs.append({"xref": inf.get("xref"), "bbox": [round(x, 1) for x in r], "frac": round(frac, 3),
                             "w": inf.get("width"), "h": inf.get("height")})
        bloques = pg.get_text("blocks")
        for b in bloques:
            txt = re.sub(r"\s+", " ", b[4]).strip()
            S = st(txt)
            mm = LEY.match(S)
            if not mm or len(txt) < 12:
                continue
            n_ley += 1
            uds = [k for k, rx in UNIDADES.items() if re.search(rx, S)]
            res.append({"boletin": cod, "archivo": f, "pag": i + 1, "leyenda": txt[:400], "bbox": [round(x, 1) for x in b[:4]],
                        "pag_wh": [round(pg.rect.width, 1), round(pg.rect.height, 1)], "imagenes": imgs,
                        "unidades": uds, "tema": bool(re.search(TEMA, S)), "tipo": mm.group(1)})
    print(cod, len(doc), "págs ·", n_ley, "leyendas", flush=True)
json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
rel = [r for r in res if r["unidades"] or r["tema"]]
print("total leyendas:", len(res), "| relevantes:", len(rel), "| con unidad:", sum(bool(r["unidades"]) for r in res))
print("con imagen no de página completa:", sum(any(im["frac"] < 0.8 for im in r["imagenes"]) for r in rel),
      "| solo escaneo de página:", sum(r["imagenes"] and all(im["frac"] >= 0.8 for im in r["imagenes"]) for r in rel),
      "| sin imagen:", sum(not r["imagenes"] for r in rel))
