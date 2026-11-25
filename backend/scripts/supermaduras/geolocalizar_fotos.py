"""Ubica cada foto de los boletines (boletines_fotos/fotos_final.json) para mostrarla en la app por cuadrícula:
  1. cantera u ocurrencia con coordenadas (evidencia_boletines: QUIMICA / OCURRENCIAS) → cuadrícula 1:25 000 exacta;
  2. Serie B: coordenadas UTM del texto de esa cantera (misma página o la anterior a la foto) → cuadrícula exacta;
  3. Serie A: hoja 1:100 000 que nombra la leyenda (nombres de cuadrángulo del título del boletín); si no nombra
     ninguna, todas las hojas que cubre el boletín (índice SERV_BOLETINES, capa 1).
Uso (desde backend/): python scripts/supermaduras/geolocalizar_fotos.py <carpeta_boletines> <fotos_final.json>
Salida: scripts/supermaduras/fotos_ubicacion.json"""
import glob, json, math, os, re, sys, unicodedata

import fitz
from pyproj import Transformer
from shapely.geometry import MultiPolygon, Point, Polygon

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from evidencia_boletines import OCURRENCIAS, QUIMICA  # noqa: E402

DIR, FOTOS = sys.argv[1], sys.argv[2]
ALFA = "abcdefghijklmnñopqrstuvxyz"
# zona UTM de los estudios de UNA región; los de franjas (8-B, 11-B, 12-B, 14-B) abarcan varias: solo si el texto la dice
ZONA_B = {"33-B": 17, "26-B": 19, "30-B": 19, "22-B": 19, "32-B": 19}
TR = {z: Transformer.from_crs(f"EPSG:327{z}", "EPSG:4326", always_xy=True) for z in (17, 18, 19)}


def st(s):
    return unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().upper()


def celda(lat, lon):
    fila = math.floor(-lat / 0.5) + 1
    col = math.floor((lon + 81.5) / 0.5)
    norte, oeste = -(fila - 1) * 0.5, -81.5 + col * 0.5
    n50, e50 = lat >= norte - 0.25, lon >= oeste + 0.25
    cod50 = f"{fila}{ALFA[col]}" + str({(True, True): 1, (False, True): 2, (False, False): 3, (True, False): 4}[(n50, e50)])
    norte50 = norte if n50 else norte - 0.25
    oeste50 = oeste + 0.25 if e50 else oeste
    return f"{cod50}-" + ("N" if lat >= norte50 - 0.125 else "S") + ("E" if lon >= oeste50 + 0.125 else "O"), f"{fila}-{ALFA[col]}"


def utm_a_geo(z, e, n):
    lon, lat = TR[z].transform(e, n)
    return lat, lon


# 1) canteras con coordenadas conocidas
conocidas = {}   # (boletín, nombre) → (zona, N, E): una foto solo se ubica con canteras de SU boletín
for r in QUIMICA:
    bol, nombre, z, n, e = r[0], r[3], r[6], r[7], r[8]
    for parte in re.split(r"[·,]", nombre):
        k = st(re.sub(r"^(Cantera|Ocurrencia|Canteras)\s+", "", parte.strip())).replace("(3 ANALISIS SIN ROTULO)", "").strip()
        if len(k) > 3:
            conocidas[(bol, k)] = (z, n, e)
for o in OCURRENCIAS:
    conocidas[(o[0], st(o[2]))] = (o[5], o[6], o[7])
conocidas[("33-B", "SUMIAPE")] = conocidas.get(("33-B", "CERRO SUMIATE"))
conocidas[("26-B", "FATIMA 1")] = (19, 8030435, 382093)

# 3) hojas de cada boletín Serie A: cobertura (polígono) y nombres de cuadrángulo del título
geo = json.load(open(os.path.join(AQUI, "boletines_geom.json"), encoding="utf-8"))
cobertura, nombres = {}, {}
for f in geo["1"]:
    a = f["attributes"]
    cod = f"{a.get('NUMERO_BOL')}-A"
    if not f.get("geometry"):
        continue
    g = MultiPolygon([Polygon(r) for r in f["geometry"]["rings"]]).buffer(0)
    hojas = []
    minx, miny, maxx, maxy = g.bounds
    la = math.floor(miny / 0.5) * 0.5
    while la < maxy:
        lo = math.floor(minx / 0.5) * 0.5
        while lo < maxx:
            if g.contains(Point(lo + 0.25, la + 0.25)):
                hojas.append(celda(la + 0.25, lo + 0.25)[1])
            lo += 0.5
        la += 0.5
    cobertura.setdefault(cod, set()).update(hojas)
    for nom, fila, letra in re.findall(r"([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\.\s]{2,40}?)\s*\(\s*(\d{1,2})\s*-\s*([A-ZÑa-zñ])\s*\)", str(a.get("TITULO") or "")):
        nombres.setdefault(cod, []).append((st(nom).strip(" ."), f"{int(fila)}-{letra.lower()}"))

docs = {}


def archivo_bol(cod):
    n, s = cod.split("-")
    for f in glob.glob(os.path.join(DIR, "*")):
        m = re.search(r"([AB])-?0*(\d+)", os.path.basename(f))
        if m and m.group(1) == s and m.group(2) == n:
            return f


fotos = json.load(open(FOTOS, encoding="utf-8"))
out = {}
for x in fotos:
    cod, ley = x["boletin"], st(x["leyenda"])
    res = {"celda": None, "hojas100": [], "precision": "unidad", "lat": None, "lon": None}
    # 1) cantera conocida
    hit = next((k for k in sorted(conocidas, key=lambda t: len(t[1]), reverse=True)
                if k[0] == cod and conocidas[k] and re.search(r"\b" + re.escape(k[1]) + r"\b", ley)), None)
    if hit:
        z, n, e = conocidas[hit]
        res["lat"], res["lon"] = utm_a_geo(z, e, n)
        res["precision"] = "cantera"
    elif cod.endswith("B"):
        # 2) UTM en el texto de la página de la foto o la anterior
        ruta = archivo_bol(cod)
        doc = docs.setdefault(ruta, fitz.open(ruta))
        txt = " ".join(re.sub(r"\s+", " ", doc[p - 1].get_text()) for p in (x["pag"] - 1, x["pag"]) if 1 <= p <= len(doc))
        ms = list(re.finditer(r"(\d[\d ]{6,9})\s?N\s*[,y]?\s*(\d[\d ]{5,7})\s?E", txt))
        mz = re.search(r"ZONA\s*(17|18|19)", st(txt))
        z = int(mz.group(1)) if mz else ZONA_B.get(cod)
        if ms and z:
            n_, e_ = int(ms[-1].group(1).replace(" ", "")), int(ms[-1].group(2).replace(" ", ""))
            lat, lon = utm_a_geo(z, e_, n_)
            if -18.5 < lat < 0 and -81.5 < lon < -68:
                res["lat"], res["lon"], res["precision"] = lat, lon, "utm_texto"
    if res["lat"] is not None:
        res["celda"], h = celda(res["lat"], res["lon"])
        res["hojas100"] = [h]
    elif cod.endswith("A"):
        # 3) hoja nombrada en la leyenda, o la cobertura del boletín
        nombradas = sorted({h for nom, h in nombres.get(cod, []) if len(nom) > 3 and re.search(r"\b" + re.escape(nom) + r"\b", ley)})
        if nombradas:
            res["hojas100"], res["precision"] = nombradas, "hoja_nombrada"
        else:
            res["hojas100"], res["precision"] = sorted(cobertura.get(cod, [])), "boletin"
    out[x["archivo_img"]] = res
json.dump(out, open(os.path.join(AQUI, "fotos_ubicacion.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
from collections import Counter
print(Counter(v["precision"] for v in out.values()))
for k, v in list(out.items())[:6]:
    print(k, v["precision"], v["celda"], v["hojas100"][:6])
