"""v2: unidades supermaduras + nuevas (indivisos, Labra, Salto del Fraile, Ñaupe, Yauca, Oyón-Chimú) + cuarcitas metamórficas.
Por unidad: filas por cuadrante 1:50 000 (o hoja 1:100 000 donde no hay 50K) y filas por cuadrícula 1:25 000 (código de la app).
Uso (venv del backend): python recopilar2.py salida.json"""
import json, math, os, re, sqlite3, sys, time, unicodedata
from collections import defaultdict

sys.path.insert(0, r"c:\Users\ESTHIVEN\Downloads\prospector-rmi_1\prospector-rmi\backend")
from pyproj import Transformer
from shapely import wkb
from shapely.geometry import Point, box, mapping
from shapely.ops import unary_union
import geocatmin_rmi as g
import laminas

ESC = os.path.dirname(os.path.abspath(__file__))
DB = r"c:\Users\ESTHIVEN\Downloads\prospector-rmi_1\prospector-rmi\backend\datos\geologia.sqlite"
SALIDA = sys.argv[1]
CACHE = os.path.join(ESC, "attrs50k_cache.json")
FAB = (-13.0808, -76.3877)
ALFABETO = "abcdefghijklmnñopqrstuvxyz"
CAMPOS = ("OBJECTID,UNIDAD,GROSOR_M,AMBIENTE_S,MEDIO_SEDI,COMP_MINE,REFERENCIA,CODHOJA,E_MAX_MA,E_MIN_MA,PISO_MAX,PISO_MIN,SERIE_MAX,SISTEMA_MAX")


def st(s):
    return unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().upper()


CUARZ = r"CUARCIT|CUARZOS|ORTOCUARC|METARENISCA"
UNIDADES = [
    # (id, nombre, tipo, filtro(unidad, texto))
    ("eolico", "Depósitos eólicos y litorales de arena cuarzosa (Cuaternario)", "sed", lambda u, t: re.search(r"DEPOSITO.*(EOLIC|MARIN|LITORAL|PLAYA)", u) and re.search(r"CUARZOS", t)),
    ("marcavilca", "Formación Marcavilca (Grupo Morro Solar)", "sed", lambda u, t: re.search(r"MARCAVILCA|^GRUPO MORRO SOLAR$", u)),
    ("salto_fraile", "Formación Salto del Fraile (Grupo Morro Solar)", "sed", lambda u, t: re.search(r"SALTO DEL FRAILE", u)),
    ("chimu", "Formación Chimú (Grupo Goyllarisquizga)", "sed", lambda u, t: re.search(r"\bCHIMU\b", u) and not re.search(r"OYON", u)),
    ("oyon_chimu", "Formaciones Oyón y Chimú (sin separar, 1:100 000)", "sed", lambda u, t: re.search(r"OYON", u) and re.search(r"CHIMU", u)),
    ("farrat", "Formación Farrat (Grupo Goyllarisquizga)", "sed", lambda u, t: re.search(r"FARRAT", u)),
    ("goyllarisquizga", "Grupo Goyllarisquizga sin dividir", "sed", lambda u, t: re.search(r"^(GRUPO )?GOYLLARISQUIZGA( INDIVISO)?$", u)),
    ("hualhuani", "Formación Hualhuani (Grupo Yura)", "sed", lambda u, t: re.search(r"HUALHUANI", u)),
    ("labra", "Formación Labra (Grupo Yura)", "sed", lambda u, t: re.search(r"\bLABRA\b", u)),
    ("huancane", "Formación Huancané", "sed", lambda u, t: re.search(r"FORMACION HUANCANE", u)),
    ("cushabatay", "Formación Cushabatay (Grupo Oriente)", "sed", lambda u, t: re.search(r"CUSHABATAY", u)),
    ("agua_caliente", "Formación Agua Caliente (Grupo Oriente)", "sed", lambda u, t: re.search(r"AGUA CALIENTE", u)),
    ("oriente", "Grupo Oriente sin dividir", "sed", lambda u, t: re.search(r"^(GRUPO )?ORIENTE( INDIVISO)?$", u)),
    ("vivian", "Formación Vivian", "sed", lambda u, t: re.search(r"\bVIVIAN\b", u)),
    ("naupe", "Formación Ñaupe", "sed", lambda u, t: re.search(r"\bNAUPE\b", u)),
    ("yauca", "Formación Yauca", "sed", lambda u, t: re.search(r"\bYAUCA\b", u)),
    # cuarcitas metamórficas: solo polígonos cuya descripción menciona cuarcita / roca cuarzosa
    ("m_sandia", "Formación Sandia (metamórfica)", "meta", lambda u, t: re.search(r"\bSANDIA\b", u) and re.search(CUARZ, t)),
    ("m_cerro_negro", "Formación Cerro Negro (metamórfica)", "meta", lambda u, t: re.search(r"CERRO NEGRO", u) and re.search(CUARZ, t)),
    ("m_rio_seco", "Formación Río Seco (metamórfica)", "meta", lambda u, t: re.search(r"RIO SECO", u) and re.search(CUARZ, t)),
    ("m_malaga", "Formación Málaga (metamórfica)", "meta", lambda u, t: re.search(r"\bMALAGA\b", u) and re.search(CUARZ, t)),
    ("m_ccatca", "Formación Ccatca (metamórfica)", "meta", lambda u, t: re.search(r"CCATCA", u) and re.search(CUARZ, t)),
    ("m_excelsior", "Grupo Excelsior (metamórfico)", "meta", lambda u, t: re.search(r"EXCELSIOR", u) and re.search(CUARZ, t)),
    ("m_chagrapi", "Formación Chagrapi", "meta", lambda u, t: re.search(r"CHAGRAPI", u) and re.search(CUARZ, t)),
    ("m_contaya", "Formación Contaya", "meta", lambda u, t: re.search(r"CONTAYA", u) and re.search(CUARZ, t)),
    ("m_figueroa", "Unidad Puesto Figueroa (metamórfica)", "meta", lambda u, t: re.search(r"PUESTO FIGUEROA", u) and re.search(CUARZ, t)),
    ("m_iscaybamba", "Complejo Iscaybamba – micaesquisto y cuarcita", "meta", lambda u, t: re.search(r"ISCAYBAMBA", u) and re.search(r"CUARCIT", t)),
    ("m_filita_cuarcita", "Filita y cuarcita (unidad sin nombre, 1:100 000)", "meta", lambda u, t: re.search(r"^FILITA, CUARCITA$", u)),
]

_tr = {}


def utm(lat, lon):
    z = int((lon + 180) // 6) + 1
    if z not in _tr:
        _tr[z] = Transformer.from_crs("EPSG:4326", f"EPSG:327{z:02d}", always_xy=True)
    e, n = _tr[z].transform(lon, lat)
    return z, round(e), round(n)


def hav(la1, lo1, la2, lo2):
    r = math.radians
    a = math.sin(r(la2 - la1) / 2) ** 2 + math.cos(r(la1)) * math.cos(r(la2)) * math.sin(r(lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def celda(lat, lon, escala):
    """Réplica de celdaEn() de frontend/src/geo.ts."""
    fila = math.floor(-lat / 0.5) + 1
    col = math.floor((lon + 81.5) / 0.5)
    letra = ALFABETO[col] if 0 <= col < len(ALFABETO) else "?"
    norte, oeste = -(fila - 1) * 0.5, -81.5 + col * 0.5
    m50 = 0.25
    n50, e50 = lat >= norte - m50, lon >= oeste + m50
    q = {(True, True): 1, (False, True): 2, (False, False): 3, (True, False): 4}[(n50, e50)]
    cod50 = f"{fila}{letra}{q}"
    if escala == "100K":
        return f"{fila}-{letra}"
    if escala == "50K":
        return cod50
    norte50 = norte if n50 else norte - m50
    oeste50 = oeste + m50 if e50 else oeste
    n25, e25 = lat >= norte50 - 0.125, lon >= oeste50 + 0.125
    return f"{cod50}-" + ("N" if n25 else "S") + ("E" if e25 else "O")


def km2(geom, lat):
    return geom.area * 111.32 ** 2 * math.cos(math.radians(lat))


con = sqlite3.connect(DB)
sel = {k: {"50K": [], "100K": []} for k, *_ in UNIDADES}
for escala, oid, attrs, b in con.execute("SELECT escala, oid, attrs, wkb FROM pol"):
    a = json.loads(attrs)
    u = st(a.get("UNIDAD"))
    t = st(" ".join(str(a.get(k) or "") for k in ("LITOLOGIA", "DESCRIP", "NAME", "LITO1", "LITO2", "LITO3")))
    for k, _, _, f in UNIDADES:
        if f(u, t):
            sel[k][escala].append((oid, a, b))
            break
print({k: (len(v["50K"]), len(v["100K"])) for k, v in sel.items()}, flush=True)


def con_50k(lon, lat):
    for (bb,) in con.execute("SELECT p.wkb FROM idx JOIN pol p ON p.id = idx.id WHERE p.escala='50K' AND "
                             "idx.minx <= ? AND idx.maxx >= ? AND idx.miny <= ? AND idx.maxy >= ? LIMIT 40", (lon, lon, lat, lat)):
        if wkb.loads(bb).contains(Point(lon, lat)):
            return True
    return False


# atributos ricos de la 50K (con caché)
ricos = {int(k): v for k, v in (json.load(open(CACHE, encoding="utf-8")).items() if os.path.exists(CACHE) else [])}
url = f"{g.BASE}/SERV_GEOLOGIA_50K_INTEGRADA/MapServer/7/query"
faltan = sorted({oid for v in sel.values() for oid, _, _ in v["50K"]} - set(ricos))
print("atributos en caché:", len(ricos), "faltan:", len(faltan), flush=True)
for i in range(0, len(faltan), 250):
    lote = faltan[i:i + 250]
    for intento in range(4):
        try:
            j = g._post(url, {"f": "json", "objectIds": ",".join(map(str, lote)), "outFields": CAMPOS, "returnGeometry": "false"}, 180)
            for f in j.get("features") or []:
                ricos[f["attributes"]["OBJECTID"]] = f["attributes"]
            break
        except Exception as e:  # noqa: BLE001
            print("reintento", i, type(e).__name__, flush=True); time.sleep(5 * (intento + 1))
    if i % 2500 == 0:
        json.dump(ricos, open(CACHE, "w", encoding="utf-8"))
    print(f"atributos {min(i + 250, len(faltan))}/{len(faltan)}", flush=True)
json.dump(ricos, open(CACHE, "w", encoding="utf-8"))


def limpio(v):
    v = str(v if v is not None else "").strip()
    return "" if v.upper() in ("", "<NULL>", "NULL", "-", "0", "0.0", "1") else v


salida = {"generado": time.strftime("%Y-%m-%d %H:%M"), "fabrica": FAB, "unidades": []}
for k, nombre, tipo, _ in UNIDADES:
    grupos = defaultdict(lambda: {"pols": [], "attrs": []})
    c25 = defaultdict(lambda: {"km2": 0.0, "pols": 0, "mayor": (0.0, None), "escalas": set()})
    geoms_mapa = []
    for escala in ("50K", "100K"):
        for oid, a, b in sel[k][escala]:
            geom = wkb.loads(b)
            if not geom.is_valid:
                geom = geom.buffer(0)
            p = geom.representative_point()
            if escala == "100K" and con_50k(p.x, p.y):
                continue
            r = ricos.get(oid, {}) if escala == "50K" else {}
            cod = celda(p.y, p.x, "50K") if escala == "50K" else celda(p.y, p.x, "100K")
            grupos[(escala, cod)]["pols"].append((geom, p))
            grupos[(escala, cod)]["attrs"].append({**a, **{kk: vv for kk, vv in r.items() if vv not in (None, " ")}})
            geoms_mapa.append(geom)
            # reparto por cuadrícula 1:25 000
            minx, miny, maxx, maxy = geom.bounds
            la = math.floor(miny / 0.125) * 0.125
            while la < maxy:
                lo = math.floor(minx / 0.125) * 0.125
                while lo < maxx:
                    caja = box(lo, la, lo + 0.125, la + 0.125)
                    if geom.intersects(caja):
                        pedazo = geom.intersection(caja)
                        if not pedazo.is_empty:
                            pp = pedazo.representative_point()
                            a2 = km2(pedazo, pp.y)
                            if a2 > 0.0005:
                                c = c25[celda(la + 0.0625, lo + 0.0625, "25K")]
                                c["km2"] += a2; c["pols"] += 1; c["escalas"].add(escala)
                                if a2 > c["mayor"][0]:
                                    c["mayor"] = (a2, (pp.y, pp.x))
                    lo += 0.125
                la += 0.125
    filas = []
    for (escala, cod), x in grupos.items():
        area = sum(km2(gm, p.y) for gm, p in x["pols"])
        if area < 0.05:
            continue
        gm, p = max(x["pols"], key=lambda gp: km2(gp[0], gp[1].y))
        lat, lon = p.y, p.x
        zona, e, n = utm(lat, lon)
        lug = laminas.lugar(lat, lon)
        cuenta = lambda campo: sorted({limpio(a.get(campo)) for a in x["attrs"] if limpio(a.get(campo))})  # noqa: E731
        descs = defaultdict(float)
        for (gm2, p2), a in zip(x["pols"], x["attrs"]):
            d = str(a.get("DESCRIP") or "").strip()
            if d:
                descs[d] += km2(gm2, p2.y)
        edad = ""
        a0 = next((a for a in x["attrs"] if limpio(a.get("PISO_MAX")) or limpio(a.get("SERIE_MAX"))), None)
        if a0:
            pisos = " – ".join(dict.fromkeys(v for v in (limpio(a0.get("PISO_MAX")), limpio(a0.get("PISO_MIN"))) if v))
            ma = f"{a0.get('E_MAX_MA')}–{a0.get('E_MIN_MA')} Ma" if a0.get("E_MAX_MA") else ""
            edad = ", ".join(v for v in (pisos, limpio(a0.get("SERIE_MAX")), ma) if v)
        filas.append({"escala": escala, "hoja": cod, "hoja100": cod if escala == "100K" else celda(lat, lon, "100K"),
                      "area_km2": round(area, 2), "poligonos": len(x["pols"]), "lat": round(lat, 5), "lon": round(lon, 5),
                      "utm": f"{zona}S {e} E {n} N", "departamento": lug["departamento"], "provincia": lug["provincia"],
                      "km_fabrica": round(hav(FAB[0], FAB[1], lat, lon)), "descripciones": [d for d, _ in sorted(descs.items(), key=lambda kv: -kv[1])[:3]],
                      "grosor": cuenta("GROSOR_M")[:3], "ambiente": cuenta("AMBIENTE_S")[:3], "medio": cuenta("MEDIO_SEDI")[:3],
                      "referencia": cuenta("REFERENCIA")[:4], "edad": edad})
    filas.sort(key=lambda f: -f["area_km2"])
    celdas = []
    for cod, c in c25.items():
        if c["km2"] < 0.05:
            continue
        lat, lon = c["mayor"][1]
        lug = laminas.lugar(lat, lon)
        celdas.append({"codigo": cod, "km2": round(c["km2"], 2), "pols": c["pols"], "carta": "/".join(sorted(c["escalas"])),
                       "lat": round(lat, 5), "lon": round(lon, 5), "km_fabrica": round(hav(FAB[0], FAB[1], lat, lon)),
                       "departamento": lug["departamento"], "provincia": lug["provincia"]})
    celdas.sort(key=lambda c: -c["km2"])
    mapa = unary_union(geoms_mapa).simplify(0.01) if geoms_mapa else None
    salida["unidades"].append({"id": k, "nombre": nombre, "tipo": tipo, "filas": filas, "celdas25": celdas,
                               "area_total": round(sum(f["area_km2"] for f in filas), 1),
                               "mapa": mapping(mapa) if mapa is not None and not mapa.is_empty else None})
    print(k, len(filas), "cuadrantes/hojas,", len(celdas), "cuadrículas 25K,", round(sum(f["area_km2"] for f in filas)), "km2", flush=True)
json.dump(salida, open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False)
print("listo")
