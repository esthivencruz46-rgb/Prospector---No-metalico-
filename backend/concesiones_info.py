"""Ficha de cada derecho minero (catastro de INGEMMET) y lo que se puede cruzar con él en
GEOCATMIN: mineros en formalización (REINFO), unidades económicas administrativas (UEA),
pasivos ambientales y certificaciones ambientales.

Lo que GEOCATMIN NO tiene: el estado de PAGO del Derecho de Vigencia y la Penalidad. Eso está
en SIDEMCAT de INGEMMET (consulta por código único), que no ofrece un servicio abierto: la app
solo da el monto anual estimado, los indicios (extinción con resolución) y los enlaces para verificarlo.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import quote_plus

from shapely.geometry import Point

import geocatmin_rmi as g

ESTADOS = {
    "TITULADO": "titulado", "TRAMITE": "en trámite (petitorio)", "EXTINGUIDO": "extinguido",
    "OTROS": "cantera del Estado / planta / relavera", "BLOQUEADO": "bloqueado", "CONSENTIDO": "extinción sin consentir",
}
# Calificación (campo CALIFICA): define cuánto se paga de Derecho de Vigencia por hectárea y año
CALIFICACION = {
    "M": ("Pequeño productor minero (PPM)", 1.0),
    "A": ("Productor minero artesanal (PMA)", 0.5),
    None: ("Régimen general (sin calificación PPM/PMA)", 3.0),
}
PADRON = "https://www.gob.pe/institucion/ingemmet/colecciones/4949-padron-minero-nacional"


def _t(v) -> str:
    return str(v or "").strip()


def _fecha(ms) -> str | None:
    try:
        return datetime.fromtimestamp(float(ms) / 1000, tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _google(texto: str) -> str:
    return f"https://www.google.com/search?q={quote_plus(texto)}"


# ¿Qué extrae una concesión NO metálica? INGEMMET solo registra «N» (no metálica), no el mineral.
# Indicios por palabras en el nombre del derecho, el titular, los proyectos con certificación
# ambiental y el derecho declarado en REINFO. Orden: lo más específico primero.
import re as _re
from unicodedata import normalize as _norm

MATERIALES_NM = [
    ("Sílice / arena silícea", r"S[IÍ]LIC|CUARZ|CUARC[IÍ]T|VIDRI"),
    ("Fosfatos", r"FOSFAT|BAYOVAR"),
    ("Boratos", r"BORAT|BORAX|ULEXIT|SOMINBOR"),
    ("Carbón", r"CARB[OÓ]N|ANTRACIT|ANTHRACITE"),
    ("Yeso", r"\bYESO"),
    ("Caliza / cal / cemento", r"CALIZ|CALC[AÁ]R|CALERA|\bCAL\b|CEMENT|CALCESUR|M[AÁ]RMOL|TRAVERTIN"),
    ("Dolomita", r"DOLOMI"),
    ("Arcilla / caolín / bentonita", r"ARCILL|CAOL[IÍ]N|LADRILL|BENTONIT"),
    ("Sal", r"\bSAL\b|SALINA"),
    ("Diatomita", r"DIATOMIT"),
    ("Baritina", r"BARIT"),
    ("Feldespato", r"FELDESP"),
    ("Puzolana", r"PUZOLAN"),
    ("Talco", r"\bTALCO"),
    ("Roca ornamental", r"GRANITO|ORNAMENT|\bLAJA"),
    ("Arena / agregados (construcción)", r"\bARENA|ARENER|ARENAL|AGREGAD|HORMIG|CONFITILL|GRAVA|CHANCAD"),
    ("Cantera (material no precisado)", r"CANTERA"),
]


def _sin_tildes(s: str) -> str:
    return _norm("NFD", s.upper()).encode("ascii", "ignore").decode()


def material_probable(textos: list[tuple[str, str]]) -> dict | None:
    """textos = [(fuente, texto)] → primer material NM cuyo patrón aparece, con la evidencia."""
    for material, patron in MATERIALES_NM:
        rx = _re.compile(_sin_tildes(patron))
        for fuente, texto in textos:
            if texto and rx.search(_sin_tildes(texto)):
                return {"material": material, "fuente": fuente, "texto": texto[:80]}
    return None


def ficha(a: dict) -> dict:
    """Datos del derecho minero tal como los publica INGEMMET en GEOCATMIN + lo que se deduce."""
    codigo = _t(a.get("CODIGOU"))
    leyenda = _t(a.get("LEYENDA")).upper()
    detalle = _t(a.get("D_ESTADO"))
    cal = _t(a.get("CALIFICA")).upper() or None
    cal_txt, tarifa = CALIFICACION.get(cal, CALIFICACION[None])
    ha = round(float(a.get("HECTAGIS") or a.get("HASDATUM") or 0), 2) or None
    vigente = leyenda in ("TITULADO", "TRAMITE")
    ubic = " · ".join(x for x in (_t(a.get("DISTRI")), _t(a.get("PROVI")), _t(a.get("DEPA"))) if x)
    sust = _t(a.get("SUSTANCIA")).upper()

    alertas: list[str] = []
    d = detalle.upper()
    if leyenda == "TRAMITE":
        alertas.append("Petitorio en trámite: todavía no es concesión, pero ya bloquea el área (prioridad por fecha y hora).")
    if "A PUBLICAR DE L.D" in d:
        alertas.append("Extinguido: quedará libre cuando INGEMMET publique su libre denunciabilidad (vigilar la publicación).")
    elif "NO PETICIONABLE" in d:
        alertas.append("Extinguido, pero el área aún no es peticionable.")
    if "AVISO DE RETIRO" in d:
        alertas.append("Publicado aviso de retiro (Ley 30428).")
    if "CANTERA D.S. 037-96-EM" in d:
        alertas.append("Cantera del Estado reservada para obras viales (MTC): no se puede pedir como concesión.")
    if "CAUTELAR" in d:
        alertas.append("Medida cautelar del Poder Judicial sobre el derecho.")
    if "ACUMULACI" in d:
        alertas.append("Forma parte de una acumulación de derechos mineros.")
    if "PLANTA DE BENEFICIO" in d or "RELAVES" in d:
        alertas.append("Concesión de beneficio o depósito de relaves (no es de exploración/explotación).")
    resol = _t(a.get("RESOL_EXTI"))
    f_resol = _fecha(a.get("FECHA_RESOL_EXTI"))
    if resol and not vigente:
        alertas.append(f"Extinguido por resolución {resol}{f' del {f_resol}' if f_resol else ''}.")
    # Indicio sobre el pago (GEOCATMIN no tiene el estado de pago): un derecho todavía vigente con
    # resolución de extinción suele estar en caducidad por no pagar el Derecho de Vigencia (aún no firme)
    if not vigente:
        indicio = {"nivel": "na", "texto": "No está vigente: no paga Derecho de Vigencia."}
    elif resol:
        indicio = {"nivel": "alerta", "texto": (
            f"Tiene resolución de extinción {resol}{f' del {f_resol}' if f_resol else ''} y aún figura vigente: "
            "suele ser caducidad por no pagar el Derecho de Vigencia (o abandono), todavía sin quedar firme. "
            "Si queda firme, el área pasará a libre denunciabilidad. Verificar en SIDEMCAT.")}
    else:
        indicio = {"nivel": "ok", "texto": "Sin resolución de extinción registrada: no hay indicio de deuda "
                                           "(confirmar el pago del año en SIDEMCAT)."}

    return {
        "codigo": codigo,
        "nombre": _t(a.get("CONCESION")) or "(sin nombre)",
        "titular": _t(a.get("TIT_CONCES")),
        "estado": ESTADOS.get(leyenda, leyenda.lower() or "—"),
        "estado_detalle": detalle,
        "vigente": vigente,
        "sustancia": {"M": "metálica", "N": "no metálica"}.get(sust, sust.lower()),
        "calificacion": cal_txt,
        "ha_total": ha,
        "fecha_petitorio": _fecha(a.get("FEC_DENU")),
        "hora_petitorio": _t(a.get("HOR_DENU")) or None,
        "carta": _t(a.get("CARTA")),
        "ubicacion": ubic,
        "expediente_en": _t(a.get("UBICA_EXP")),
        "resolucion_extincion": _t(a.get("RESOL_EXTI")) or None,
        # Derecho de Vigencia anual (Ley General de Minería): US$ 3/ha régimen general, 1 PPM, 0,5 PMA.
        # La penalidad (por no acreditar producción/inversión mínima) se suma aparte y no se puede calcular aquí.
        "vigencia_usd_anual": round(ha * tarifa, 2) if (vigente and ha) else None,
        "tarifa_usd_ha": tarifa if vigente else None,
        "pago": ("INGEMMET no publica el estado de pago en un servicio abierto. Verifícalo en SIDEMCAT "
                 f"(Derecho de Vigencia → Registro de pagos) con el código {codigo}. Indicio: si un titular deja de "
                 "pagar dos años, INGEMMET declara la caducidad y el derecho aparece aquí como extinguido con resolución."),
        "indicio_pago": indicio,
        # solo para no metálicas; se completa en enriquecer() con certificaciones/REINFO y en
        # geocatmin_rmi.buscar con la geología que hay debajo
        "material_probable": material_probable([("nombre del derecho", _t(a.get("CONCESION"))),
                                                ("titular", _t(a.get("TIT_CONCES")))]) if sust == "N" else None,
        "alertas": alertas,
        "enlaces": [
            {"titulo": "Padrón Minero Nacional (lo que debe pagar cada derecho)", "url": PADRON},
            {"titulo": f"Buscar {codigo} en INGEMMET", "url": _google(f'site:ingemmet.gob.pe "{codigo}"')},
            {"titulo": "Resoluciones en El Peruano (caducidad, extinción…)", "url": _google(f'site:elperuano.pe "{codigo}"')},
        ],
    }


# ------------------------------------------------------------ cruces con otros servicios
def _seguro(fn, *args):
    try:
        return fn(*args), None
    except Exception as e:  # noqa: BLE001
        return None, type(e).__name__


def _reinfo(anillo):
    return g.query_en_poligono("SERV_REINFO", 0, anillo, "NOMBRE_MIN,ID_UNIDAD,NOMBRE_DM,TIPO_ACT,ORIGEN,ESTE,NORTE,ID_ZONA")


def _uea(anillo):
    integ = g.query_en_poligono("SERV_UEAs", 1, anillo, "CG_CODIGO,CG_CODPET,PE_NOMDER,SE_SITUEX", con_geometria=False)
    nombres = {}
    for f in g.query_en_poligono("SERV_UEAs", 0, anillo, "CG_CODIGO,UE_NOMUEA,ESTADO,TITULARES_UEA,NUM_DM", con_geometria=False):
        a = f.get("attributes") or {}
        nombres[_t(a.get("CG_CODIGO"))] = a
    return integ, nombres


def _pasivos(anillo):
    return g.query_en_poligono("SERV_PASIVO_AMBIENTAL", 0, anillo, "CODIGODM,NOMBREDM,TIPO,SUBTIPO")


def _certificados(anillo):
    out = []
    for lid in (0, 1, 2):
        for f in g.query_en_poligono("SERV_CERTIFICADO_AMBIENTAL", lid, anillo,
                                     "NOMBRE,PROYECTO,TIPO_CERTIFICACION,RD_NUMERO,RD_FECHA,TC_ESTCER,LINK"):
            out.append(f)
    return out


def _codigo_igual(a: str, b: str) -> bool:
    a, b = _t(a).lstrip("0"), _t(b).lstrip("0")
    return bool(a) and a == b


def _punto(f):
    geom = f.get("geometry") or {}
    if "x" in geom and "y" in geom:
        return Point(geom["x"], geom["y"])
    return None


def descargar(pol) -> tuple:
    """REINFO, UEA, pasivos y certificaciones de la cuadrícula (en paralelo; cada uno puede fallar)."""
    anillo = g._anillo_esri(pol)
    with ThreadPoolExecutor(4) as ex:
        fs = [ex.submit(_seguro, fn, anillo) for fn in (_reinfo, _uea, _pasivos, _certificados)]
        return tuple(f.result() for f in fs)


def enriquecer(pol, cons: list[dict], datos: tuple | None = None) -> list[str]:
    """Agrega a cada concesión (in situ) REINFO, UEA, pasivos y certificaciones. Devuelve avisos.
    `datos` = resultado de descargar(pol), si ya se pidió en paralelo con el catastro."""
    if not cons:
        return []
    (reinfo, er), (uea, eu), (pasivos, ep), (certs, ec) = datos if datos is not None else descargar(pol)
    avisos = [f"No respondió {n} ({e})." for n, e in
              (("REINFO", er), ("el registro de UEA", eu), ("pasivos ambientales", ep), ("certificación ambiental", ec)) if e]
    integ, nombres_uea = uea if uea else ([], {})
    for c in cons:
        cod, geom = c["codigo"], c.get("_geom")
        if reinfo is not None:
            lista = []
            for f in reinfo:
                a = f.get("attributes") or {}
                p = _punto(f)
                if _codigo_igual(a.get("ID_UNIDAD"), cod) or (p is not None and geom is not None and geom.contains(p)):
                    lista.append({"nombre": _t(a.get("NOMBRE_MIN")).replace("?", "Ñ"), "actividad": _t(a.get("TIPO_ACT")).lower(),
                                  "derecho_declarado": _t(a.get("NOMBRE_DM")), "origen": _t(a.get("ORIGEN"))})
            c["reinfo"] = lista[:20]
            if lista:
                c["alertas"].append(f"{len(lista)} minero(s) en formalización (REINFO) declarados aquí: mientras sigan "
                                    "inscritos, el titular no puede desalojarlos sin el proceso de formalización.")
        if uea is not None:
            u = next((a for a in ((f.get("attributes") or {}) for f in integ) if _codigo_igual(a.get("CG_CODPET"), cod)), None)
            if u:
                info = nombres_uea.get(_t(u.get("CG_CODIGO")), {})
                c["uea"] = {"codigo": _t(u.get("CG_CODIGO")), "nombre": _t(info.get("UE_NOMUEA")) or None,
                            "derechos": info.get("NUM_DM")}
                c["alertas"].append(f"Integra la UEA {c['uea']['nombre'] or c['uea']['codigo']}: paga y produce en conjunto con otros derechos.")
        if pasivos is not None:
            ps = [f.get("attributes") or {} for f in pasivos]
            ps = [a for a in ps if any(_codigo_igual(x, cod) for x in _t(a.get("CODIGODM")).split(";"))]
            if ps:
                c["pasivos"] = {"n": len(ps), "tipos": sorted({_t(a.get("SUBTIPO") or a.get("TIPO")).lower() for a in ps})[:6]}
                c["alertas"].append(f"{len(ps)} pasivo(s) ambiental(es) minero(s) inventariados en este derecho.")
        if certs is not None and geom is not None:
            cs = []
            for f in certs:
                p = _punto(f)
                if p is not None and geom.contains(p):
                    a = f.get("attributes") or {}
                    link = _t(a.get("LINK"))
                    cs.append({"tipo": _t(a.get("TIPO_CERTIFICACION")), "titular": _t(a.get("NOMBRE")),
                               "proyecto": _t(a.get("PROYECTO")), "resolucion": _t(a.get("RD_NUMERO")),
                               "fecha": _fecha(a.get("RD_FECHA")), "etapa": _t(a.get("TC_ESTCER")),
                               "url": link if link.startswith("http") else None})
            if cs:
                c["certificaciones"] = cs[:10]
        # no metálica sin pista en el nombre: probar con los proyectos certificados y REINFO
        if c.get("sustancia") == "no metálica" and not c.get("material_probable"):
            c["material_probable"] = material_probable(
                [("proyecto con certificación ambiental", x.get("proyecto") or x.get("titular", "")) for x in c.get("certificaciones", [])]
                + [("derecho declarado en REINFO", x.get("derecho_declarado", "")) for x in c.get("reinfo", [])])
        c["actividad"] = actividad(c)
    return avisos


def actividad(c: dict) -> dict:
    """¿Hay indicios de que se esté explotando? (no basta con tener la concesión: muchas son especulativas)"""
    señales = []
    if any("EXPLOT" in (x.get("actividad") or "").upper() for x in c.get("reinfo", [])):
        señales.append("minero(s) en REINFO declaran EXPLOTACIÓN")
    elif c.get("reinfo"):
        señales.append("minero(s) inscritos en REINFO")
    if any("EXPLOT" in (x.get("etapa") or "").upper() for x in c.get("certificaciones", [])):
        señales.append("certificación ambiental de EXPLOTACIÓN")
    elif c.get("certificaciones"):
        señales.append("certificación ambiental (exploración u otra)")
    if c.get("pasivos"):
        señales.append("labores o residuos mineros inventariados (pasivos)")
    nivel = "alta" if any("EXPLOT" in s for s in señales) else "posible" if señales else "sin indicios"
    return {"nivel": nivel, "senales": señales}


def geologia_debajo(cons: list[dict], afloramientos: list[dict]) -> None:
    """Para cada derecho: qué zonas favorables (A/B/C) tiene debajo. Una concesión NO metálica sobre
    roca cuarzosa (A/B) es un indicio fuerte de que se pide (o explota) arena silícea / sílice."""
    from shapely.geometry import shape
    zonas = []
    for a in afloramientos:
        try:
            zonas.append((a, shape(a["geometria"])))
        except Exception:  # noqa: BLE001
            continue
    for c in cons:
        cg = c.get("_geom")
        if cg is None or cg.is_empty:
            continue
        area = max(g.area_ha(cg), 1e-9)
        debajo = []
        for a, zg in zonas:
            if not cg.intersects(zg):
                continue
            pct = round(100 * g.area_ha(g._limpiar(cg.intersection(zg))) / area, 1)
            if pct >= 1:
                debajo.append({"clase": a["clase"], "unidad": a["unidad"], "litologia": a.get("litologia") or "", "pct": pct})
        debajo.sort(key=lambda x: ({"A": 0, "B": 1, "C": 2}[x["clase"]], -x["pct"]))
        c["sobre_zonas"] = debajo[:5]
        if c.get("sustancia") != "no metálica":
            continue
        ab = sum(x["pct"] for x in debajo if x["clase"] in ("A", "B"))
        cc = sum(x["pct"] for x in debajo if x["clase"] == "C")
        mp = (c.get("material_probable") or {}).get("material", "")
        if ab >= 5 or mp.startswith("Sílice"):
            c["indicio_silice"] = {"nivel": "alto", "texto": (
                f"No metálica sobre roca cuarzosa (zonas A/B: {round(ab)} % del derecho en esta cuadrícula)"
                if ab >= 5 else "No metálica y su nombre/titular/proyecto apunta a sílice")
                + (": muy probablemente arena silícea / sílice." if ab >= 5 and mp.startswith("Sílice") else
                   ": es probable que se busque arena silícea / sílice.")}
        elif cc >= 5:
            unidades = ", ".join(dict.fromkeys(x["unidad"] for x in debajo if x["clase"] == "C"))
            c["indicio_silice"] = {"nivel": "medio", "texto": (
                f"No metálica sobre zonas C ({unidades}; {round(cc)} % del derecho): roca compatible "
                "pero sin cuarzo confirmado; verificar.")}
        if not c.get("material_probable") and ab >= 5:
            c["material_probable"] = {"material": "Sílice / arena silícea (por la geología)",
                                      "fuente": "geología 1:50 000 / 1:100 000 debajo",
                                      "texto": debajo[0]["unidad"]}


def en_zona(cons: list[dict], geom) -> list[dict]:
    """Derechos mineros que tocan una zona favorable y qué % de la zona ocupan."""
    if not cons or geom is None or geom.is_empty:
        return []
    area = max(g.area_ha(geom), 1e-9)
    out = []
    for c in cons:
        cg = c.get("_geom")
        if cg is None or not cg.intersects(geom):
            continue
        pct = round(100 * g.area_ha(g._limpiar(cg.intersection(geom))) / area, 1)
        if pct >= 0.5:
            out.append({"codigo": c["codigo"], "nombre": c["nombre"], "estado": c["estado"], "titular": c["titular"], "pct": pct,
                        "extinguido": bool(c.get("_extinguido"))})
    return sorted(out, key=lambda x: -x["pct"])
