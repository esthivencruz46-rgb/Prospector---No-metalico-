"""Bibliografía geológica de una cuadrícula, para leer antes de ir a campo:

1. Boletines de INGEMMET que cubren la zona: índice espacial SERV_BOLETINES de
   GEOCATMIN (Carta Geológica 1:100 000 y 1:50 000, Serie B Geología Económica,
   Rocas y Minerales, Geoquímica, Geotermia, Prospección), con enlace directo al
   repositorio institucional.
2. Memorias descriptivas citadas en los polígonos de la geología 1:50 000
   (campo REFERENCIA): de dónde salió el mapa que estás viendo.
3. Mapa geológico integrado oficial de la hoja 1:100 000 (ZIP y vista PNG).
4. Búsquedas listas para el navegador (hoja y formaciones presentes).

El repositorio (repositorio.ingemmet.gob.pe) bloquea las consultas automáticas
(protección «Anubis»): por eso las búsquedas son ENLACES que el usuario abre
en su navegador, donde la verificación pasa sola. No se intenta saltarla.
"""

from __future__ import annotations

import json
from urllib.parse import quote_plus

from shapely.geometry import box

import geocatmin_rmi as g

SERVICIO = "SERV_BOLETINES"
# capa → (tipo legible, campos título/número/serie/url)
CAPAS = {
    1: ("Carta Geológica Nacional · boletín 1:100 000", "TITULO", "NUMERO_BOL", None, ("LINK", "REPOSITORIO")),
    2: ("Carta Geológica Nacional · boletín 1:50 000", "TITULO", "NUMERO", "SERIE", ("LINK", "REPOSITORIO")),
    4: ("Rocas y minerales / recursos minerales", "TITULOBOLETIN", "NUMERO", "SERIE", ("URL_REPOSITORIO", "URL_WEB")),
    5: ("Geoquímica", "TITULOBOLETIN", "NUMERO", "SERIE", ("URL_REPOSITORIO", "URL_WEB")),
    6: ("Geotermia", "TITULOBOLETIN", "NUMERO", "SERIE", ("URL_REPOSITORIO", "URL_WEB")),
    7: ("Prospección", "TITULOBOLETIN", "NUMERO", "SERIE", ("URL_REPOSITORIO", "URL_WEB")),
}


def _limpio(v) -> str:
    s = str(v or "").strip()
    return "" if s in ("<Null>", "None", "Null") else s


def buscar_en_navegador(texto: str) -> str:
    """Búsqueda de Google limitada al repositorio de INGEMMET (se abre en el navegador)."""
    return "https://www.google.com/search?q=" + quote_plus(f"site:repositorio.ingemmet.gob.pe {texto}")


def consultar(sur: float, oeste: float, norte: float, este: float) -> dict:
    # se encoge un poco: una cuadrícula que solo TOCA el borde de otra hoja no la «contiene»
    pol = box(oeste, sur, este, norte).buffer(-0.002)
    anillo = g._anillo_esri(pol)
    geom = json.dumps({"rings": [anillo], "spatialReference": {"wkid": 4326}})
    base = {"f": "json", "geometry": geom, "geometryType": "esriGeometryPolygon",
            "spatialRel": "esriSpatialRelIntersects", "returnGeometry": "false"}
    avisos: list[str] = []

    # 1) boletines
    boletines: list[dict] = []
    vistos: set[str] = set()
    for lid, (tipo, c_tit, c_num, c_serie, c_urls) in CAPAS.items():
        try:
            j = g._post(f"{g.BASE}/{SERVICIO}/MapServer/{lid}/query", {**base, "outFields": "*"}, 40)
        except Exception as e:  # noqa: BLE001
            avisos.append(f"No respondió el índice de boletines ({tipo}): {type(e).__name__}.")
            continue
        for f in j.get("features") or []:
            a = f.get("attributes") or {}
            url = next((_limpio(a.get(c)) for c in c_urls if _limpio(a.get(c))), "")
            titulo = _limpio(a.get(c_tit)).rstrip(", ")
            if not titulo or (url or titulo) in vistos:
                continue
            vistos.add(url or titulo)
            serie = _limpio(a.get(c_serie)) if c_serie else "A"
            numero = _limpio(a.get(c_num))
            boletines.append({"tipo": tipo, "serie": serie, "numero": numero, "titulo": titulo, "url": url,
                              "cita": f"INGEMMET, Boletín Serie {serie} N° {numero}" if numero else "INGEMMET"})

    # 2) memorias citadas en la geología 1:50 000 (+ formaciones presentes)
    memorias: dict[str, int] = {}
    formaciones: set[str] = set()
    try:
        feats = g.query_en_poligono("SERV_GEOLOGIA_50K_INTEGRADA", 7, anillo, "REFERENCIA,UNIDAD",
                                    timeout=g._TIMEOUT_50K, con_geometria=False)
        for f in feats:
            a = f.get("attributes") or {}
            ref = _limpio(a.get("REFERENCIA"))
            if ref:
                memorias[ref] = memorias.get(ref, 0) + 1
            u = _limpio(a.get("UNIDAD"))
            if "FORMACI" in u.upper() or "GRUPO" in u.upper():
                formaciones.add(u)
    except Exception as e:  # noqa: BLE001
        avisos.append(f"No respondió la geología 1:50 000 para las referencias ({type(e).__name__}).")

    # 3) mapa geológico integrado oficial de la hoja 1:100 000 (la que contiene el centro)
    hoja = None
    try:
        lat_c, lon_c = (sur + norte) / 2, (oeste + este) / 2
        j = g._post(f"{g.BASE}/SERV_GEOLOGIA_100K_INTEGRADA/MapServer/0/query", {
            "f": "json", "geometry": json.dumps({"x": lon_c, "y": lat_c, "spatialReference": {"wkid": 4326}}),
            "geometryType": "esriGeometryPoint", "spatialRel": "esriSpatialRelIntersects", "returnGeometry": "false",
            "outFields": "QDR_CODIGO_ALFANUMERICO,QDR_NOMBRE,LINK_GEO_INTEGRADA,FOTO_GEO_INTEGRADA"}, 40)
        a = ((j.get("features") or [{}])[0]).get("attributes") or {}
        if a:
            hoja = {"codigo": _limpio(a.get("QDR_CODIGO_ALFANUMERICO")), "nombre": _limpio(a.get("QDR_NOMBRE")),
                    "zip": _limpio(a.get("LINK_GEO_INTEGRADA")), "png": _limpio(a.get("FOTO_GEO_INTEGRADA"))}
    except Exception as e:  # noqa: BLE001
        avisos.append(f"No respondió el índice de hojas 1:100 000 ({type(e).__name__}).")

    # 4) búsquedas para el navegador
    busquedas = []
    if hoja:
        busquedas.append({"titulo": f"Geología del cuadrángulo de {hoja['nombre'].title()} ({hoja['codigo']})",
                          "url": buscar_en_navegador(f"\"{hoja['nombre']}\" {hoja['codigo']} geología")})
    for fm in sorted(formaciones)[:6]:
        nombre = fm.split(" - ")[-1]
        busquedas.append({"titulo": f"{nombre}", "url": buscar_en_navegador(f"\"{nombre}\"")})
    busquedas.append({"titulo": "Arena silícea / rocas y minerales industriales en la zona",
                      "url": buscar_en_navegador(f"rocas minerales industriales {hoja['nombre'] if hoja else ''} sílice")})

    return {
        "boletines": boletines,
        "memorias": [{"cita": m, "poligonos": n, "buscar": buscar_en_navegador(m[:150])}
                     for m, n in sorted(memorias.items(), key=lambda x: -x[1])],
        "hoja100k": hoja,
        "busquedas": busquedas,
        "avisos": avisos,
        "nota": "El repositorio de INGEMMET verifica que seas una persona: los enlaces se abren en tu navegador.",
    }
