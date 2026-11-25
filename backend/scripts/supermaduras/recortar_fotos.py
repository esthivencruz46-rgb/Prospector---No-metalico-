"""Recorta la foto que acompaña a cada leyenda de los boletines. Detecta los bloques de imagen de la página
(sirve para imágenes embebidas y para páginas escaneadas): píxeles no blancos fuera de los bloques de texto,
agrupados en una grilla y unidos en componentes; luego asigna a cada leyenda el bloque más cercano (arriba,
abajo o al costado; o en la página siguiente si la leyenda lo dice).
Uso: python -I recortar_fotos.py <carpeta_boletines> <seleccion.json> <carpeta_salida>"""
import json, os, re, sys, unicodedata
from collections import defaultdict
import fitz
import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")
DIR, SEL, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(OUT, exist_ok=True)
DPI_A, DPI_FINAL, CEL = 50, 150, 5          # análisis a 50 ppp, celdas de 5 px


def st(s):
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().upper()


def bloques_imagen(pg):
    """Rectángulos (puntos) de las zonas con imagen de la página."""
    W, H = pg.rect.width, pg.rect.height
    e = DPI_A / 72.0
    pix = pg.get_pixmap(dpi=DPI_A, colorspace=fitz.csGRAY)
    a = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width).copy()
    for b in pg.get_text("blocks"):                       # borrar el texto (OCR o digital)
        if len(b[4].strip()) < 3:
            continue
        x0, y0, x1, y1 = (int(v * e) for v in b[:4])
        a[max(0, y0 - 1):y1 + 2, max(0, x0 - 1):x1 + 2] = 255
    osc = a < 215
    gh, gw = osc.shape[0] // CEL, osc.shape[1] // CEL
    g = osc[:gh * CEL, :gw * CEL].reshape(gh, CEL, gw, CEL).mean(axis=(1, 3)) > 0.30
    # cierre morfológico 3×3 (une la foto aunque tenga zonas claras)
    def dil(m):
        o = m.copy()
        o[1:] |= m[:-1]; o[:-1] |= m[1:]; o[:, 1:] |= m[:, :-1]; o[:, :-1] |= m[:, 1:]
        return o
    def ero(m):
        o = m.copy()
        o[1:] &= m[:-1]; o[:-1] &= m[1:]; o[:, 1:] &= m[:, :-1]; o[:, :-1] &= m[:, 1:]
        return o
    g = ero(dil(dil(g)))
    g = ero(g)
    # componentes conexas
    vis = np.zeros_like(g)
    rects = []
    for y in range(gh):
        for x in range(gw):
            if g[y, x] and not vis[y, x]:
                pila, ys, xs = [(y, x)], [], []
                vis[y, x] = True
                while pila:
                    cy, cx = pila.pop(); ys.append(cy); xs.append(cx)
                    for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                        if 0 <= ny < gh and 0 <= nx < gw and g[ny, nx] and not vis[ny, nx]:
                            vis[ny, nx] = True; pila.append((ny, nx))
                r = fitz.Rect(min(xs) * CEL / e, min(ys) * CEL / e, (max(xs) + 1) * CEL / e, (max(ys) + 1) * CEL / e)
                if r.width > 0.18 * W and r.height > 0.07 * H and r.width * r.height < 0.92 * W * H and len(ys) > 0.35 * (r.width * e / CEL) * (r.height * e / CEL):
                    rects.append(r)
    return rects


def distancia(a, b):
    dy = max(0, b.y0 - a.y1, a.y0 - b.y1)
    dx = max(0, b.x0 - a.x1, a.x0 - b.x1)
    return dx + dy


sel = json.load(open(SEL, encoding="utf-8"))
por_pag = defaultdict(list)
for i, s in enumerate(sel):
    por_pag[(s["archivo"], s["pag"])].append((i, s))
docs, out, cache = {}, [], {}
for (arch, pag), items in por_pag.items():
    ruta = os.path.join(DIR, arch)
    doc = docs.setdefault(ruta, fitz.open(ruta))
    usados = set()
    # cada leyenda: candidatos de su página (o de la siguiente si lo dice)
    pares = []
    for i, s in items:
        p = pag + 1 if re.search(r"SIGUIENTE PAGINA|PAGINA SIGUIENTE", st(s["leyenda"])) and pag < len(doc) else pag
        if (arch, p) not in cache:
            cache[(arch, p)] = bloques_imagen(doc[p - 1])
        cap = fitz.Rect(s["bbox"]) if p == pag else fitz.Rect(0, 0, 0, 0)
        for j, r in enumerate(cache[(arch, p)]):
            d = distancia(cap, r) if p == pag else 0
            if d <= 0.22 * doc[p - 1].rect.height:
                pares.append((d, i, s, p, j, r))
    hecho = set()
    for d, i, s, p, j, r in sorted(pares, key=lambda t: t[0]):
        if i in hecho or (p, j) in usados:
            continue
        hecho.add(i); usados.add((p, j))
        pg = doc[p - 1]
        pix = pg.get_pixmap(dpi=DPI_FINAL, clip=r)
        img = Image.frombytes("RGB" if pix.n >= 3 else "L", (pix.width, pix.height), pix.samples)
        if img.width > 1100:
            img = img.resize((1100, round(img.height * 1100 / img.width)))
        nombre = f"{s['boletin']}_p{p}_{i}.jpg"
        img.convert("RGB").save(os.path.join(OUT, nombre), quality=72, optimize=True)
        out.append({**s, "pag_foto": p, "archivo_img": nombre, "recorte": [round(x, 1) for x in r], "px": [img.width, img.height]})
    for i, s in items:
        if i not in hecho:
            print("sin foto:", s["boletin"], s["pag"], s["leyenda"][:60])
json.dump(out, open(os.path.join(OUT, "fotos.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("recortadas:", len(out), "de", len(sel))
