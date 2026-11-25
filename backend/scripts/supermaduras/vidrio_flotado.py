"""Mejores cuadrículas para VIDRIO FLOTADO según la descripción de la carta (pedido del usuario, 23/11/2026):
roca silícea de las unidades supermaduras con COLOR cercano al blanco (blanco, blanquecino, blanco grisáceo, gris
blanquecino; ningún otro color en la frase de esa roca) y GRANO medio a grueso. Regla de cartas: 1:50 000; la
1:100 000 solo donde no hay 1:50 000. Por cuadrícula 1:25 000: km² que cumplen, unidad, estimación libre-utilizable
(censo por tipo) y química de canteras cercana. Uso (desde backend/): python scripts/supermaduras/vidrio_flotado.py datos/vidrio_flotado.json  (lo lee ranking.py → GET /ranking «vidrio»)"""
import json, math, os, re, sqlite3, sys, unicodedata
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from shapely import wkb
from shapely.geometry import Point, box
import ranking

DB = os.path.join(os.path.dirname(ranking.DATOS), "datos", "geologia.sqlite")
SALIDA = sys.argv[1]
FAB = (-13.0808, -76.3877)
ALFA = "abcdefghijklmnñopqrstuvxyz"


def st(s):
    return unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().upper()


ROCA = r"\b(ARENISCAS?|CUARCITAS?|ORTOCUARCITAS?|CUARZOARENITAS?|METARENISCAS?|ARENAS?)\b"
FIN = r"(;|\.|\bINTERCALAD|\bALTERNAD|\bCON (NIVELES|INTERCALACIONES|ESTRATOS|CAPAS|HORIZONTES|LENTES)|\b(Y|,|E|O|A)\s+(LUTIT|LIMOLIT|CALIZ|ARCILL|MARGA|CONGLOMER|PIZARR|CARBON|LODOLIT|LIMOARCILL|TOBA|ANDESIT|FILIT|ESQUIST|DOLOMI))"
BLANCO = r"\b(BLANC\w*|GRIS(ES)? BLANQUE[CS]IN\w*|BLANQUE[CS]IN\w*|HIALIN\w*)"
CASI = r"\b(GRIS(ES)? CLAR\w*|CREMA|BEIGE)\b"
OTRO = (r"\b(ROJ\w*|PARD\w*|MARRON\w*|AMARILL\w*|ROSAD\w*|ROSACE\w*|VERD\w*|NEGR\w*|VIOL\w*|OCRE|ABIGARR\w*|NARANJ\w*|"
        r"MORAD\w*|LILA|PURPUR\w*|AZUL\w*|OSCUR\w*|CHOCOLATE|RUBI\w*|GRIS(ES)?(?! BLANQUE| CLAR))\b")
# primero los RANGOS (si no, «grano medio a fino» se leería como «medio»); «en grano» y «grano, medio» también valen
GRANO = [("medio a grueso", r"GRANO,? (MEDIO A GRUESO|GRUESO A MEDIO)"), ("fino a grueso", r"GRANO,? (FINO A GRUESO|GRUESO A FINO)"),
         ("fino a medio", r"GRANO,? (FINO A MEDIO|MEDIO A FINO)"), ("grueso", r"GRANO,? (MUY )?GRUESO"),
         ("medio", r"GRANO,? MEDIO"), ("fino", r"GRANO,? (MUY )?FINO")]
GRANO_OK = {"medio a grueso": 3, "medio": 2, "grueso": 2}           # cumple (pedido del usuario)
GRANO_PARCIAL = {"fino a grueso": 1, "fino a medio": 1}


def evaluar(texto):
    """Frases de roca silícea → (color, grano, frase) de la MEJOR frase; color: 'blanco' | 'casi' | None."""
    T = st(texto)
    mejor = None
    for m in re.finditer(ROCA, T):
        resto = T[m.start():m.start() + 220]
        f = re.search(FIN, resto[len(m.group(0)):])
        frase = resto[:len(m.group(0)) + f.start()] if f else resto
        if re.search(OTRO, frase):
            continue
        color = "blanco" if re.search(BLANCO, frase) else ("casi" if re.search(CASI, frase) else None)
        if not color:
            continue
        grano = next((g for g, rx in GRANO if re.search(rx, frase)), None)
        punt = (2 if color == "blanco" else 1) * 10 + GRANO_OK.get(grano, GRANO_PARCIAL.get(grano, 0))
        if not mejor or punt > mejor[0]:
            mejor = (punt, color, grano, frase.strip())
    return mejor


def celda(lat, lon):
    fila = math.floor(-lat / 0.5) + 1
    col = math.floor((lon + 81.5) / 0.5)
    norte, oeste = -(fila - 1) * 0.5, -81.5 + col * 0.5
    n50, e50 = lat >= norte - 0.25, lon >= oeste + 0.25
    cod50 = f"{fila}{ALFA[col]}" + str({(True, True): 1, (False, True): 2, (False, False): 3, (True, False): 4}[(n50, e50)])
    norte50 = norte if n50 else norte - 0.25
    oeste50 = oeste + 0.25 if e50 else oeste
    return f"{cod50}-" + ("N" if lat >= norte50 - 0.125 else "S") + ("E" if lon >= oeste50 + 0.125 else "O")


def km2(g, lat):
    return g.area * 111.32 ** 2 * math.cos(math.radians(lat))


def hav(la1, lo1, la2, lo2):
    r = math.radians
    a = math.sin(r(la2 - la1) / 2) ** 2 + math.cos(r(la1)) * math.cos(r(la2)) * math.sin(r(lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


con = sqlite3.connect(DB)


def con_50k(lon, lat):
    for (bb,) in con.execute("SELECT p.wkb FROM idx JOIN pol p ON p.id = idx.id WHERE p.escala='50K' AND "
                             "idx.minx <= ? AND idx.maxx >= ? AND idx.miny <= ? AND idx.maxy >= ? LIMIT 40", (lon, lon, lat, lat)):
        if wkb.loads(bb).contains(Point(lon, lat)):
            return True
    return False


nombres = {u["id"]: u["nombre"] for u in json.load(open(os.path.join(ranking.DATOS, "supermaduras.json"), encoding="utf-8"))["unidades"]}
celdas = defaultdict(lambda: {"km2": 0.0, "km2_casi": 0.0, "km2_parcial": 0.0, "unidades": defaultdict(float), "granos": defaultdict(float),
                              "frases": {}, "afl": 0, "mayor": (0.0, None), "cartas": set()})
n_pol = n_ok = 0
for esc, attrs, b in con.execute("SELECT escala, attrs, wkb FROM pol"):
    a = json.loads(attrs)
    uid = ranking.unidad_sm(a.get("UNIDAD", ""))
    if not uid or uid not in nombres:
        continue
    n_pol += 1
    texto = " ; ".join(str(a.get(k) or "") for k in ("LITOLOGIA", "DESCRIP", "NAME", "LITO1", "LITO2", "LITO3"))
    ev = evaluar(texto)
    if not ev:
        continue
    _, color, grano, frase = ev
    ok = color == "blanco" and grano in GRANO_OK
    casi = color == "casi" and grano in GRANO_OK
    parcial = color == "blanco" and grano in GRANO_PARCIAL
    if not (ok or casi or parcial):
        continue
    g = wkb.loads(b)
    if not g.is_valid:
        g = g.buffer(0)
    rp = g.representative_point()
    if esc == "100K" and con_50k(rp.x, rp.y):
        continue
    n_ok += ok
    minx, miny, maxx, maxy = g.bounds
    la = math.floor(miny / 0.125) * 0.125
    while la < maxy:
        lo = math.floor(minx / 0.125) * 0.125
        while lo < maxx:
            caja = box(lo, la, lo + 0.125, la + 0.125)
            if g.intersects(caja):
                p = g.intersection(caja)
                if not p.is_empty:
                    pp = p.representative_point()
                    ar = km2(p, pp.y)
                    if ar > 0.001:
                        c = celdas[celda(la + 0.0625, lo + 0.0625)]
                        c["cartas"].add(esc)
                        if ok:
                            c["km2"] += ar; c["unidades"][uid] += ar; c["granos"][grano] += ar; c["afl"] += 1
                            c["frases"].setdefault(frase[:200], 0.0)
                            c["frases"][frase[:200]] += ar
                            if ar > c["mayor"][0]:
                                c["mayor"] = (ar, (pp.y, pp.x))
                        elif casi:
                            c["km2_casi"] += ar
                        else:
                            c["km2_parcial"] += ar
            lo += 0.125
        la += 0.125

# libre y utilizable (censo por tipo: % por zona de la misma unidad) y química de canteras en la cuadrícula
tipos = ranking._leer("censo_tipos.json")
sm = json.load(open(os.path.join(ranking.DATOS, "supermaduras.json"), encoding="utf-8"))
quim = defaultdict(list)
for q in sm["quimica"]:
    quim[q["celda"]].append(q)
filas = []
for cod, c in celdas.items():
    if c["km2"] < 0.05:
        continue
    lat, lon = c["mayor"][1]
    t = tipos.get(cod) or {}
    util = {}
    for z in t.get("zonas", []):
        k = ranking.unidad_sm(z.get("unidad", ""))
        if k:
            a, u = util.get(k, (0.0, 0.0))
            util[k] = (a + z["ha"], u + z["ha"] * (z.get("util_pct") or 0) / 100)
    libre = sum(km * (util[k][1] / util[k][0] if k in util and util[k][0] else 0) for k, km in c["unidades"].items())
    con_dato = any(k in util for k in c["unidades"])
    uds = sorted(c["unidades"].items(), key=lambda kv: (ranking.RANGO_SM.get(kv[0], 99), -kv[1]))
    mejor = uds[0][0]
    gr = max(c["granos"].items(), key=lambda kv: kv[1])[0]
    q = sorted(quim.get(cod, []), key=lambda x: x["fe2o3"])
    filas.append({"codigo": cod, "km2": round(c["km2"], 2), "km2_libre_aprox": round(libre, 2) if con_dato else None,
                  "unidad": nombres[mejor], "rango": ranking.RANGO_SM.get(mejor, 99),
                  "unidades": "; ".join(f"{nombres[k]} {v:.2f}" for k, v in uds), "grano": gr,
                  "granos": "; ".join(f"{k} {v:.2f}" for k, v in sorted(c["granos"].items(), key=lambda kv: -kv[1])),
                  "km2_casi_blanco": round(c["km2_casi"], 2), "km2_fino_a_medio": round(c["km2_parcial"], 2),
                  "frase": max(c["frases"].items(), key=lambda kv: kv[1])[0].capitalize(), "afloramientos": c["afl"],
                  "carta": "/".join(sorted(c["cartas"])), "lat": round(lat, 5), "lon": round(lon, 5),
                  "km_fabrica": round(hav(FAB[0], FAB[1], lat, lon)),
                  "quimica": "; ".join(f"{x['nombre']}: SiO₂ {x['sio2_txt']} %, Fe₂O₃ {x['fe2o3_txt']} %" for x in q[:3])})
GORDEN = {"medio": 0, "medio a grueso": 1, "grueso": 2}
filas.sort(key=lambda f: (f["rango"], -(f["km2_libre_aprox"] if f["km2_libre_aprox"] is not None else f["km2"] * 0.3), GORDEN.get(f["grano"], 3)))
json.dump({"filas": filas, "polígonos_evaluados": n_pol, "polígonos_ok": n_ok}, open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("polígonos de unidades supermaduras:", n_pol, "| cumplen color blanco + grano medio/grueso:", n_ok, "| cuadrículas:", len(filas))
