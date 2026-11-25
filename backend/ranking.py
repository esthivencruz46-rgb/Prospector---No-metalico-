"""Ranking nacional de cuadrículas 1:25 000 con geología silícea A/B LIBRE y UTILIZABLE, a partir de los
censos ya guardados en backend/datos (no consulta GEOCATMIN: funciona aunque INGEMMET esté caído).

Regla del usuario (CLAUDE.md, «RANKING NACIONAL»): UNA carta por cuadrícula —la 1:50 000 si tiene zonas
A/B; si no (o no hay 50K), la 1:100 000— indicando siempre de cuál salió. Importancia = km² de geología
A/B libre y utilizable. «Selva» = ≥ 50 % de bosque (WorldCover). Si existe el censo por tipo
(datos/censo_tipos.json) se agregan las hectáreas libres de arena · arenisca · cuarcita de la carta usada.
"""
from __future__ import annotations

import json
import math
import os
import re
import unicodedata

DATOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos")
FABRICA = (-13.0808, -76.3877)
ALFABETO = "abcdefghijklmnñopqrstuvxyz"
_cache: dict = {"firma": None, "filas": None}

# ---- prioridad de supermaduras (datos/supermaduras.json): las zonas del censo por tipo se asignan a una unidad
# supermadura por su nombre (mismas reglas que scripts/supermaduras/recopilar2.py) y su área libre y utilizable se
# pondera por la prioridad de la unidad (1 = mejor evidencia). La carta de cada unidad en cada cuadrícula es la que
# fijó el informe (1:50 000; la 1:100 000 solo donde no hay 1:50 000).
PESO_PRIORIDAD = {1: 1.0, 2: 0.7, 3: 0.45, 4: 0.25, 5: 0.15}
# Orden de SUPERMADUREZ (pedido del usuario: el ranking va por criterio de supermaduras, no por área). De la mejor a la
# peor evidencia del informe; el área libre y utilizable solo desempata entre cuadrículas con la misma mejor unidad.
ORDEN_SUPERMADUREZ = [
    ("chimu", "Química: SiO₂ 92,3–98,3 %, Fe₂O₃ 0,06–0,21 % (6 canteras, 33-B); ortocuarcita (26-A)"),
    ("goyllarisquizga", "Química: Utco 98,6 % SiO₂, Sumiate 96,9 % (33-B); areniscas blancas friables (76-A)"),
    ("marcavilca", "Petrografía: Q 92–96 %, feldespato 0 % (Alvan et al., 2025); sin química"),
    ("vivian", "Petrografía: «cuarzo-arenitas» bien clasificadas (98-A); sin química"),
    ("farrat", "Química más variable: SiO₂ 92,2–95,5 %, Fe₂O₃ 0,13–1,02 % (33-B)"),
    ("agua_caliente", "Textura: bien seleccionada (32-B); roca de yacimiento petrolífero (98-A)"),
    ("eolico", "Variable: mantos finos claros de cuarzo vs. mantos oscuros con ferromagnesianos (47-A)"),
    ("cushabatay", "Textura: monótona, granos subredondeados (100-A); sin química"),
    ("oriente", "Madura a supermadura; incluye lutitas de Esperanza y concreciones de hierro (98-A)"),
    ("hualhuani", "Madura; química de fundente: SiO₂ 90–93 %, Fe₂O₃ 0,5–1,1 % (26-B, 30-B)"),
    ("salto_fraile", "Madura: areniscas cuarzosas gris verdosas con niveles arcillosos (14-B)"),
    ("huancane", "Heterogénea: de sublitarenita a cuarzoarenita (74-A)"),
    ("labra", "Madura con óxidos de hierro (22-B)"),
    ("naupe", "Certeza baja"), ("yauca", "Certeza baja"),
    ("m_rio_seco", "Metamórfica: cuarcitas grises en estratos masivos"), ("m_ccatca", "Metamórfica: cuarcitas blanquecinas con pizarras"),
    ("m_sandia", "Metamórfica: pizarras con algo de cuarcitas (30-B)"), ("m_cerro_negro", "Metamórfica: cuarcitas oscuras recristalizadas (54-A)"),
    ("m_malaga", "Metamórfica: cuarcita y metaareniscas"), ("m_contaya", "Metamórfica: pizarras sobre cuarcita (101-A)"),
    ("m_excelsior", "Metamórfica: filitas con cuarcitas (14-B)"), ("m_figueroa", "Metamórfica: esquistos con niveles de cuarcita"),
    ("m_chagrapi", "Metamórfica: lutitas y pizarras con cuarcitas (58-A)"), ("m_iscaybamba", "Metamórfica: cuarcitas con micas (30-B)"),
]
RANGO_SM = {k: i + 1 for i, (k, _) in enumerate(ORDEN_SUPERMADUREZ)}
MIN_KM2_SM = 0.5   # mínimo de una unidad libre y utilizable para que cuente en el orden (evita astillas)
_REGLAS_SM = [
    ("eolico", r"DEPOSITO.*(EOLIC|MARIN|LITORAL|PLAYA)"), ("marcavilca", r"MARCAVILCA|^GRUPO MORRO SOLAR$"),
    ("salto_fraile", r"SALTO DEL FRAILE"), ("chimu", r"\bCHIMU\b"), ("farrat", r"FARRAT"),
    ("goyllarisquizga", r"^(GRUPO )?GOYLLARISQUIZGA( INDIVISO)?$"), ("hualhuani", r"HUALHUANI"), ("labra", r"\bLABRA\b"),
    ("huancane", r"FORMACION HUANCANE"), ("cushabatay", r"CUSHABATAY"), ("agua_caliente", r"AGUA CALIENTE"),
    ("oriente", r"^(GRUPO )?ORIENTE( INDIVISO)?$"), ("vivian", r"\bVIVIAN\b"), ("naupe", r"\bNAUPE\b"), ("yauca", r"\bYAUCA\b"),
    ("m_sandia", r"\bSANDIA\b"), ("m_cerro_negro", r"CERRO NEGRO"), ("m_rio_seco", r"RIO SECO"), ("m_malaga", r"\bMALAGA\b"),
    ("m_ccatca", r"CCATCA"), ("m_excelsior", r"EXCELSIOR"), ("m_chagrapi", r"CHAGRAPI"), ("m_contaya", r"CONTAYA"),
    ("m_figueroa", r"PUESTO FIGUEROA"), ("m_iscaybamba", r"ISCAYBAMBA"),
]


def _st(s: str) -> str:
    return unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().upper()


def unidad_sm(nombre: str) -> str | None:
    """Id de la unidad supermadura a la que pertenece una zona del censo (por su nombre de unidad), o None."""
    u = _st(nombre)
    if re.search(r"OYON", u) and re.search(r"CHIMU", u):
        return None
    for k, rx in _REGLAS_SM:
        if re.search(rx, u):
            return k
    return None


def _supermaduras() -> tuple[dict, dict]:
    """({id: (nombre, prioridad)}, {(cuadrícula, id): cartas}) desde datos/supermaduras.json."""
    try:
        with open(os.path.join(DATOS, "supermaduras.json"), encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError):
        return {}, {}
    info = {u["id"]: (re.sub(r"\s*\(.*\)$", "", u["nombre"]), u["prioridad"]) for u in d.get("unidades", [])}
    cartas = {(c[0], u["id"]): set(c[3].split("/")) for u in d.get("unidades", []) for c in u["celdas"]}
    return info, cartas


def _leer(nombre: str) -> dict:
    try:
        with open(os.path.join(DATOS, nombre), encoding="utf-8") as fh:
            return json.load(fh).get("celdas", {})
    except (OSError, ValueError):
        return {}


def _centro(codigo: str) -> tuple[float, float]:
    hoja, q25 = codigo.split("-")
    i = 0
    while hoja[i].isdigit():
        i += 1
    norte = -(int(hoja[:i]) - 1) * 0.5
    oeste = -81.5 + ALFABETO.index(hoja[i]) * 0.5
    q50 = {1: "NE", 2: "SE", 3: "SO", 4: "NO"}[int(hoja[i + 1:])]
    norte -= 0.25 if q50[0] == "S" else 0
    oeste += 0.25 if q50[1] == "E" else 0
    norte -= 0.125 if q25[0] == "S" else 0
    oeste += 0.125 if q25[1] == "E" else 0
    return norte - 0.0625, oeste + 0.0625


def _km(lat: float, lon: float) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (FABRICA[0], FABRICA[1], lat, lon))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def _ab(d: dict | None) -> float:
    return (d or {}).get("A", 0) + (d or {}).get("B", 0)


def filas() -> list[dict]:
    firma = tuple(os.path.getmtime(os.path.join(DATOS, f)) if os.path.exists(os.path.join(DATOS, f)) else 0
                  for f in ("censo_libres.json", "censo_silice.json", "censo_bosque.json", "censo_tipos.json", "supermaduras.json"))
    if _cache["firma"] == firma and _cache["filas"] is not None:
        return _cache["filas"]
    libres, silice, bosque, tipos = (_leer(f) for f in ("censo_libres.json", "censo_silice.json",
                                                        "censo_bosque.json", "censo_tipos.json"))
    sm_info, sm_cartas = _supermaduras()
    out = []
    for cod, v in libres.items():
        if not v.get("ok"):
            continue
        s = silice.get(cod, {})
        carta = "50K" if _ab(s.get("50K")) > 0 else "100K"
        aprox = False
        if carta == "50K" or v.get("escala") == "100K":
            ha = _ab(v.get("ha_util"))
        else:   # la 50K tenía algo (no A/B): estimación con el % utilizable de la cuadrícula
            ha = (v.get("zonas_100k_A_ha") or 0) * (v.get("util_pct_celda") or 0) / 100
            aprox = True
        fila = {"codigo": cod, "carta": carta, "km2": round(ha / 100, 2), "aprox": aprox,
                "util_pct": v.get("util_pct_celda"), "libre_pct": v.get("libre_pct_celda"),
                "n_concesiones": v.get("n_concesiones"), "prohibido": bool(v.get("prohibido")),
                "bosque_pct": (bosque.get(cod) or {}).get("bosque_pct")}
        fila["selva"] = (fila["bosque_pct"] or 0) >= 50
        lat, lon = _centro(cod)
        fila["km_fabrica"] = round(_km(lat, lon))
        t = tipos.get(cod)
        if t and t.get("ok"):   # hectáreas libres-utilizables por tipo, de la carta usada (A/B)
            por = {"arena": 0.0, "arenisca": 0.0, "cuarcita": 0.0}
            for z in t.get("zonas", []):
                if z["escala"] == carta and z["clase"] in "AB" and z["tipo"] in por:
                    por[z["tipo"]] += z["ha"] * (z.get("util_pct") or 0) / 100
            fila["tipos_km2"] = {k: round(x / 100, 2) for k, x in por.items()}
            fila["km2"] = round(sum(por.values()) / 100, 2)
            fila["aprox"] = False
            # supermaduras libres y utilizables (todas las clases A/B/C: la unidad decide, no la clase)
            sm: dict[str, float] = {}
            for z in t.get("zonas", []):
                k = unidad_sm(z.get("unidad", ""))
                if not k or k not in sm_info:
                    continue
                cartas = sm_cartas.get((cod, k))
                if cartas is None or z["escala"] not in cartas:
                    continue   # carta que el informe descartó para esa unidad en esta cuadrícula
                sm[k] = sm.get(k, 0.0) + z["ha"] * (z.get("util_pct") or 0) / 100
            uds = sorted(({"id": k, "nombre": sm_info[k][0], "prioridad": sm_info[k][1], "rango": RANGO_SM.get(k, 99),
                           "km2": round(ha / 100, 2)} for k, ha in sm.items() if ha >= 1), key=lambda x: (x["rango"], -x["km2"]))
            if uds:
                fila["sm"] = uds
                fila["sm_km2"] = round(sum(x["km2"] for x in uds), 2)
                fila["sm_puntaje"] = round(sum(x["km2"] * PESO_PRIORIDAD[x["prioridad"]] for x in uds), 2)
                fila["sm_prioridad"] = uds[0]["prioridad"]
                mejor = next((x for x in uds if x["km2"] >= MIN_KM2_SM), None)
                fila["sm_rango"] = mejor["rango"] if mejor else None
        if fila["km2"] > 0 or fila.get("sm"):
            out.append(fila)

    def clave(f: dict):   # supermadurez primero; el área solo desempata dentro de la misma mejor unidad
        if f.get("sm_rango") is None:
            return (999, 0, -f["km2"])
        mejor = next(x for x in f["sm"] if x["rango"] == f["sm_rango"])
        return (f["sm_rango"], -mejor["km2"], -f["km2"])
    out.sort(key=clave)
    for i, f in enumerate(out, 1):
        f["puesto"] = i
    _cache.update(firma=firma, filas=out)
    return out


_cache_vf: dict = {"firma": None, "filas": None}


def vidrio() -> list[dict]:
    """VIDRIO FLOTADO (pedido del usuario, 23/11/2026): cuadrículas cuya carta describe la roca silícea de una unidad
    supermadura con color cercano al blanco y grano medio a grueso (datos/vidrio_flotado.json, de
    scripts/supermaduras/vidrio_flotado.py), con la marca de selva del censo de bosque. Ya vienen ordenadas
    (supermadurez → km² libres ≈ → grano)."""
    rutas = [os.path.join(DATOS, f) for f in ("vidrio_flotado.json", "censo_bosque.json")]
    firma = tuple(os.path.getmtime(r) if os.path.exists(r) else 0 for r in rutas)
    if _cache_vf["firma"] == firma and _cache_vf["filas"] is not None:
        return _cache_vf["filas"]
    try:
        with open(rutas[0], encoding="utf-8") as fh:
            fs = json.load(fh).get("filas", [])
    except (OSError, ValueError):
        fs = []
    bosque = _leer("censo_bosque.json")
    out = []
    for i, f in enumerate(fs, 1):
        b = (bosque.get(f["codigo"]) or {}).get("bosque_pct")
        out.append({**f, "puesto": i, "bosque_pct": b, "selva": (b or 0) >= 50})
    _cache_vf.update(firma=firma, filas=out)
    return out


_cache_desc: dict = {"firma": None, "filas": None}


def descripcion() -> list[dict]:
    """POR DESCRIPCIÓN (pedido del usuario, 24/11/2026): cuadrículas ordenadas por la aptitud para vidrio flotado que
    da la DESCRIPCIÓN de INGEMMET de su mejor unidad con ≥ 0,5 km² libres y utilizables (vidrio_desc.aptitud =
    frontend/src/vidrio.ts; datos/censo_descripcion.json de scripts/censo_descripcion.py). Orden: nivel (alta → no)
    → puntaje → km² libres. Una arenisca cuarzosa blanca de grano grueso intercalada con limoarcillitas pardas o
    lutitas negras baja de nivel."""
    import vidrio_desc
    rutas = [os.path.join(DATOS, f) for f in ("censo_descripcion.json", "censo_bosque.json")]
    firma = tuple(os.path.getmtime(r) if os.path.exists(r) else 0 for r in rutas)
    if _cache_desc["firma"] == firma and _cache_desc["filas"] is not None:
        return _cache_desc["filas"]
    celdas = _leer("censo_descripcion.json")
    bosque = _leer("censo_bosque.json")
    out = []
    for cod, v in celdas.items():
        m = v.get("mejor")
        if not m:
            continue
        b_ = (bosque.get(cod) or {}).get("bosque_pct")
        lat, lon = _centro(cod)
        out.append({"codigo": cod, "carta": v["carta"], "nivel": m["nivel"], "puntaje": m["puntaje"], "unidad": m["unidad"],
                    "descripcion": m["descripcion"], "roca": m["roca"], "a_favor": m["a_favor"], "en_contra": m["en_contra"],
                    "estratos": m["estratos"], "espesor": m["espesor"], "km2_libre": m["km2_libre"], "km2": m["km2"],
                    "km2_nivel": v.get("km2_nivel", {}), "otras": [{"unidad": x["unidad"], "nivel": x["nivel"], "puntaje": x["puntaje"],
                                                                   "km2_libre": x["km2_libre"]} for x in v.get("descripciones", [])[1:5]],
                    "bosque_pct": b_, "selva": (b_ or 0) >= 50, "km_fabrica": round(_km(lat, lon))})
    out.sort(key=lambda f: (vidrio_desc.ORDEN_NIVEL[f["nivel"]], -f["puntaje"], -f["km2_libre"]))
    for i, f in enumerate(out, 1):
        f["puesto"] = i
    _cache_desc.update(firma=firma, filas=out)
    return out


def resumen() -> dict:
    fs = filas()
    return {"total": len(fs), "con_tipos": any("tipos_km2" in f for f in fs), "con_vidrio": bool(vidrio()), "con_descripcion": bool(descripcion()),
            "con_supermaduras": any("sm" in f for f in fs), "pesos_prioridad": PESO_PRIORIDAD, "min_km2_sm": MIN_KM2_SM,
            "orden_supermadurez": [{"id": k, "rango": i + 1, "motivo": m} for i, (k, m) in enumerate(ORDEN_SUPERMADUREZ)],
            "sm_km2_total": round(sum(f.get("sm_km2", 0) for f in fs)),
            "km2_total": round(sum(f["km2"] for f in fs)),
            "grupos": {f"{c}_{'selva' if s else 'sin_selva'}": sum(1 for f in fs if f["carta"] == c and f["selva"] == s)
                       for c in ("50K", "100K") for s in (False, True)}}
