"""APTITUD PARA VIDRIO FLOTADO según la DESCRIPCIÓN litológica de INGEMMET (pedido del usuario, 24/11/2026).

RÉPLICA EXACTA de frontend/src/vidrio.ts (`aptitudVidrio`): mantener iguales (reglas, puntos y textos). La usa el
ranking nacional por descripción (scripts/censo_descripcion.py → datos/censo_descripcion.json → GET /ranking).

La descripción se corta en TRAMOS, uno por roca nombrada (los calificativos van después del nombre). Cada tramo de
roca silícea suma por tipo (arena > arenisca cuarzosa > cuarcita), grano grueso/medio, color claro, madurez y
estratos potentes, y resta por colores de hierro, oscuros, ferromagnesianos, pirita, micas, feldespato. Cada roca
que NO sirve (limolita, lutita, caliza, volcánica…) resta: con alguna intercalada → como mucho «media»; si es la
roca principal → como mucho «baja». Lectura del texto, no análisis químico.
"""
from __future__ import annotations

import math
import re

_A = re.ASCII
_TILDES = str.maketrans("áéíóúüàèìòù", "aeiouuaeiou")


def plano(s: str) -> str:
    """minúsculas y sin tildes, MISMO largo que el original."""
    return s.lower().translate(_TILDES)


ROCAS = [
    (re.compile(r"arenas? (?:eolicas?,? )?(?:cuarzosas?|siliceas?|de cuarzo|blancas? cuarzosas?)", _A), "arena cuarzosa", "silice", 46),
    (re.compile(r"(?:cuarzoarenitas?|ortocuarcitas?|cuarzo ?arenitas?)", _A), "cuarzoarenita", "silice", 42),
    (re.compile(r"areniscas? (?:\w+ ){0,2}?(?:cuarzosas?|cuarciticas?|de cuarzo|siliceas?)", _A), "arenisca cuarzosa", "silice", 38),
    (re.compile(r"(?:areniscas? arcosicas?|arcosas?|subarcosas?|grauvacas?|litarenitas?|areniscas? feldespaticas?|areniscas? tobaceas?|areniscas? calcareas?)", _A), "arenisca arcósica o lítica", "mala", 0),
    (re.compile(r"(?:metareniscas?|metacuarcitas?|cuarcitas?)", _A), "cuarcita", "silice", 28),
    (re.compile(r"(?:arenas?|areniscas?)", _A), "arena o arenisca", "neutra", 12),
    (re.compile(r"(?:microconglomerados?|conglomerados?|gravas?|brechas?)", _A), "conglomerado", "neutra", 0),
    (re.compile(r"(?:limoarcillitas?|limolitas?|lodolitas?|arcillitas?|lutitas?|pelitas?|argilitas?|arcillas?|limos?\b)", _A), "limolita / lutita", "mala", 0),
    (re.compile(r"(?:pizarras?|filitas?|esquistos?|gneis\w*|micaesquistos?)", _A), "pizarra / esquisto", "mala", 0),
    (re.compile(r"(?:calizas?|margas?|dolomitas?|dolomias?|yesos?|evaporitas?|travertinos?|carbon\b|carbones|mantos? de carbon)", _A), "caliza / marga / yeso", "mala", 0),
    (re.compile(r"(?:lavas?|andesit\w*|basalt\w*|dacit\w*|riolit\w*|tobas?|piroclast\w*|volcan\w*|ignimbrit\w*|aglomerados?|granit\w*|granodiorit\w*|diorit\w*|tonalit\w*|intrusiv\w*)", _A), "volcánica / ígnea", "mala", 0),
]

A_FAVOR = [
    (r"blanc[oa]s?|blanquecin[oa]s?|hialin[oa]s?", 9, "color blanco"),
    (r"gris(?:es)? clar[oa]s?|crema|beige|bieges?", 3, "color claro"),
    (r"bien clasificad|buena seleccion|bien seleccionad", 5, "bien clasificada"),
    (r"redondead|subredondead", 3, "granos redondeados"),
    (r"supermadur|madur[oa]s?\b|limpi[oa]s?", 5, "madura / limpia"),
    (r"eolic", 3, "eólica"),
    (r"estratificacion (?:cruzada|sesgada|oblicua)|laminacion (?:oblicua|sesgada)", 1, "estratificación cruzada"),
]
EN_CONTRA = [
    (r"rojiz|rojo|roja|rojas|rosad|rosace|ros[oa]s?\b|morad|violace", -9, "color rojizo (hierro)"),
    (r"pard[oa]|marron|amarill|ocre|naranj|anaranjad|abigarrad|limonit|hematit|goetit|ferrugin|oxidos? de hierro|ferrosos?|ferric", -9, "color pardo-amarillento (óxidos de hierro)"),
    (r"negr[oa]s?|oscur[oa]s?|carbonos|bitumin|materia organica", -7, "oscura / materia orgánica"),
    (r"verdos|glauconit|clorit", -5, "verdosa (glauconita, clorita)"),
    (r"ferromagnesian|mafic|biotit|anfibol|piroxen|magnetit|minerales pesados|minerales oscuros", -8, "ferromagnesianos / minerales pesados"),
    (r"pirit", -7, "pirita"),
    (r"micace|mica\b|micas\b|moscovit|sericit", -4, "micácea"),
    (r"feldesp|arcosic|litic", -6, "feldespato o líticos"),
    (r"calcare|calcit|carbonat", -4, "cemento calcáreo"),
    (r"arcillos|matriz", -4, "matriz arcillosa"),
]
A_FAVOR = [(re.compile(r, _A), v, t) for r, v, t in A_FAVOR]
EN_CONTRA = [(re.compile(r, _A), v, t) for r, v, t in EN_CONTRA]

ESTRATO = re.compile(r"(?:en |de |con )?(?:estratos?|capas?|bancos?|paquetes?|horizontes?|lentes?|niveles?|secuencias?|"
                     r"estratificad[oa]s?|laminad[oa]s?|masiv[oa]s?)(?: (?:de|en|muy|poco|bien))?[^,;.()]{0,48}", _A)
POTENTE = re.compile(r"grues|metric|potent|masiv|\d+(?:[.,]\d+)? ?m\b|\d+ ?a ?\d+ ?m\b|decametric|bancos?", _A)
DELGADO = re.compile(r"delgad|centimetric|laminad|finos? estratos|milimetric|lajos", _A)
ESPESOR = re.compile(r"(?:espesor|potencia|grosor)[^.;]{0,40}?(?:de |aprox\w*\.? |aproximad[oa] de |entre )?"
                     r"(\d[\d.,]*(?: ?a ?\d[\d.,]*)? ?(?:m|metros|km)\b)|[±+-]\s?(\d[\d.,]*) ?m\b", _A)
GRANO = re.compile(r"grano (?:muy )?(grueso|medio|fino)(?: (?:a|y) (?:muy )?(grueso|medio|fino))?", _A)
CLASTO = re.compile(r"(?:clastos?|fragmentos?|cantos?|guijarros?|rodados?|bloques?) (?:\w+ ){0,2}de $", _A)
COLOR_MALA = re.compile(r"rojiz|pard|amarill|marron|negr|oscur|bitumin|carbonos|morad|verdos", _A)
PARAR = {"con", "de", "del", "y", "e", "en", "a", "o", "que", "hacia", "para", "fisible", "fisibles"}
NIVEL_TEXTO = {"alta": "Apta para vidrio", "media": "Aptitud media", "baja": "Aptitud baja", "no": "No apta"}
ORDEN_NIVEL = {"alta": 0, "media": 1, "baja": 2, "no": 3}


def _redondear(x: float) -> int:      # = Math.round de JavaScript
    return math.floor(x + 0.5)


def _hallar_rocas(p: str) -> list[tuple[int, int, str, str, int]]:
    out, i = [], 0
    while i < len(p):
        if "a" <= p[i] <= "z" and (i == 0 or not ("a" <= p[i - 1] <= "z")):
            for rx, nombre, clase, base in ROCAS:
                m = rx.match(p, i)
                if m:
                    out.append((i, m.end(), nombre, clase, base))
                    i = m.end()
                    break
            else:
                i += 1
            continue
        i += 1
    return out


def _grano(t: str):
    m = GRANO.search(t)
    if not m:
        return None
    s = {x for x in (m.group(1), m.group(2)) if x}
    if "grueso" in s and "fino" not in s:
        return 10, f"grano {m.group(1)} a {m.group(2)}" if m.group(2) else f"grano {m.group(1)}"
    if "medio" in s and "fino" not in s:
        return 8, "grano medio"
    if "fino" in s and len(s) > 1:
        return 2, f"grano {m.group(1)} a {m.group(2)}"
    return -4, "grano fino"


def aptitud(descripcion: str, litologia: str = "", roca_principal: str = "") -> dict:
    texto = (descripcion if descripcion and descripcion != "<Null>" else (litologia or "")).replace("<Null>", "").strip()
    p = plano(texto)
    rocas = _hallar_rocas(p)
    a_favor: list[str] = []
    con_mejor: list[str] = []
    malas: list[str] = []
    estratos: list[dict] = []
    mejor, mejor_roca, castigo, n_malas, principal_mala = -1, None, 0, 0, False
    for k, (i, f, nombre, clase, base) in enumerate(rocas):
        fin = rocas[k + 1][0] if k + 1 < len(rocas) else len(texto)
        t = p[i:fin]
        if CLASTO.search(p[max(0, i - 40):i]):
            malas.append(f"{nombre} solo como clastos")
            continue
        if k == 0 and nombre == "conglomerado":
            castigo += 15
            principal_mala = True
            malas.append("conglomerado como roca principal")
        if clase == "silice" or (clase == "neutra" and base > 0):
            pts = base
            fav: list[str] = []
            con: list[str] = []
            g = _grano(t)
            if g:
                pts += g[0]
                (fav if g[0] > 0 else con).append(g[1])
            for rx, v, txt in A_FAVOR:
                if rx.search(t):
                    pts += v
                    fav.append(txt)
            for rx, v, txt in EN_CONTRA:
                if rx.search(t):
                    pts += v
                    con.append(txt)
            for m in ESTRATO.finditer(t):
                frase = texto[i + m.start():i + m.end()].strip()
                if len(frase) < 6:
                    continue
                tipo = "potente" if POTENTE.search(m.group(0)) else "delgado" if DELGADO.search(m.group(0)) else "medio"
                if clase == "silice":
                    estratos.append({"roca": nombre, "texto": frase, "tipo": tipo})
                    pts += 5 if tipo == "potente" else -3 if tipo == "delgado" else 0
            if pts > mejor:
                mejor, mejor_roca = pts, nombre
                a_favor = [nombre, *fav]
                con_mejor = con
        elif clase == "mala":
            v = 30 if k == 0 else 18 if n_malas == 0 else 6
            if k == 0:
                principal_mala = True
            n_malas += 1
            if COLOR_MALA.search(t):
                v += 5
            castigo += v
            palabras: list[str] = []
            for w in re.split(r"\s+", texto[i:fin]):
                limpio = re.sub(r"[,;.:()]+$", "", w)
                lp = plano(limpio)
                if palabras and (lp in PARAR or re.match(r"(intercal|interestrat|altern)", lp)):
                    break
                if limpio:
                    palabras.append(limpio)
                if len(palabras) >= 4 or limpio != w:
                    break
            nom = " ".join(palabras)
            if nom not in malas:
                malas.append(nom)
    if roca_principal and not re.search(r"cuarz|cuarcit|silice|arena", plano(roca_principal)) \
            and not (rocas and rocas[0][3] == "mala"):
        castigo += 8
    puntaje = 0 if mejor < 0 else max(0, min(100, _redondear(mejor + 30 - castigo)))
    nivel = "no" if mejor < 0 else "alta" if puntaje >= 62 else "media" if puntaje >= 42 else "baja" if puntaje >= 20 else "no"
    if (mejor_roca == "arena o arenisca" or n_malas > 0) and nivel == "alta":
        nivel = "media"
    if principal_mala and nivel == "media":
        nivel = "baja"
    e = ESPESOR.search(p)
    espesor = (e.group(1) or f"±{e.group(2)}").replace("metros", "m") if e else None
    return {"puntaje": puntaje, "nivel": nivel, "roca": mejor_roca, "a_favor": a_favor,
            "en_contra": [*con_mejor, *malas], "estratos": estratos, "espesor": espesor}
