"""Áreas protegidas y restringidas para concesiones mineras (GEOCATMIN ·
SERV_AREA_RESERVADA), dentro de una cuadrícula.

Dos niveles (referenciales: siempre confirmar con INGEMMET y SERNANP):
- «prohibido»: no se otorgan concesiones o no se admiten petitorios
  (ANP de uso INDIRECTO —parques y santuarios nacionales—, áreas de no admisión
  de petitorios/ANAP, zonas arqueológicas intangibles, defensa nacional).
- «restringido»: se puede pedir, pero la actividad necesita autorización u
  opinión previa (ANP de uso DIRECTO y zonas de amortiguamiento → compatibilidad
  u opinión técnica de SERNANP; propuestas de ANP; zonas urbanas; puertos y
  aeropuertos; proyectos especiales; otras áreas restringidas).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from shapely.geometry import Polygon
from shapely.ops import unary_union

import geocatmin_rmi as g

SERVICIO = "SERV_AREA_RESERVADA"
# (id de capa, tipo, nivel; None = depende del uso del ANP)
CAPAS = [
    (10, "Área natural protegida (ANP)", None),
    (11, "Zona de amortiguamiento de ANP", "restringido"),
    (7, "Propuesta de área natural protegida", "restringido"),
    (1, "Zona arqueológica", "prohibido"),
    (3, "Área de no admisión de petitorios", "prohibido"),
    (4, "ANAP · no admisión de petitorios (INGEMMET)", "prohibido"),
    (0, "Área de defensa nacional", "prohibido"),
    (6, "Zona urbana", "restringido"),
    (5, "Puerto o aeropuerto", "restringido"),
    (8, "Otra área restringida", "restringido"),
    (9, "Proyecto especial", "restringido"),
    (19, "Reserva indígena", "prohibido"),
    (20, "Reserva territorial", "prohibido"),
    (13, "Sitio histórico de batalla", "prohibido"),
    (17, "Paisaje cultural", "restringido"),
    (14, "Sitio Ramsar (humedal)", "restringido"),
    (16, "Ecosistema frágil", "restringido"),
    (12, "Zona de riesgo no mitigable", "restringido"),
    (21, "Faja marginal (ríos y lagos)", "restringido"),
    (18, "Red vial nacional (derecho de vía)", "restringido"),
    # La capa 15 «Concesión forestal» de este servicio está incompleta (1 054): se usa el catastro
    # forestal propio (FORESTAL, 1 776, actualizado cada 15 días por SERFOR/INGEMMET).
]
CAPAS_MAPA = [c[0] for c in CAPAS]

# Catastro forestal (SERFOR): concesiones VIGENTES o SUSPENDIDAS (las extinguidas ya no cuentan)
FORESTAL = ("SERV_CATASTRO_FORESTAL", 0, "ESTCON_DES <> 'EXTINGUIDO'")
NOTA_FORESTAL = ("Concesión forestal vigente: se puede pedir concesión minera encima, pero para operar hay que respetar "
                 "el derecho del concesionario forestal y contar con la opinión/autorización de SERFOR o de la autoridad "
                 "forestal regional (más difícil en concesiones de conservación y ecoturismo).")

NOTA = {
    "prohibido": "No se otorgan concesiones ni se admiten petitorios mineros en esta área.",
    "restringido": "Se puede pedir concesión, pero la actividad requiere autorización u opinión previa "
                   "(p. ej. compatibilidad de SERNANP en ANP de uso directo y zonas de amortiguamiento).",
}


def _nivel(tipo_nivel: str | None, uso: str) -> str:
    if tipo_nivel:
        return tipo_nivel
    # ANP: uso indirecto (parques, santuarios) → sin extracción; uso directo → con compatibilidad SERNANP
    return "prohibido" if "INDIRECTO" in (uso or "").upper() else "restringido"


def _texto(v) -> str:
    return str(v or "").strip()


def consultar(pol: Polygon) -> list[dict]:
    """Áreas que tocan el polígono, con su % de cubrimiento y su geometría recortada
    (shapely, clave «_geom»: solo para cálculos internos, no se envía al cliente)."""
    anillo = g._anillo_esri(pol)
    area_total = max(g.area_ha(pol), 1e-9)

    def una(cfg):
        lid, tipo, nivel_fijo = cfg
        # «*»: las capas 12–21 no tienen todos los campos (USO falta en varias) y ArcGIS
        # rechaza la consulta entera si se pide un campo que no existe
        feats = g.query_en_poligono(SERVICIO, lid, anillo, "*")
        out = []
        for f in feats:
            geom = g.esri_a_shapely(f.get("geometry"), recorte=pol)
            if geom is None or geom.is_empty:
                continue
            inter = g._limpiar(geom.intersection(pol))
            if inter is None or inter.is_empty:
                continue
            a = f.get("attributes") or {}
            nivel = _nivel(nivel_fijo, _texto(a.get("USO")))
            ha = g.area_ha(inter)
            out.append({
                "tipo": tipo, "nivel": nivel, "nombre": _texto(a.get("NOMBRE")) or "(sin nombre)",
                "categoria": _texto(a.get("CATEGORI")), "uso": _texto(a.get("USO")), "norma": _texto(a.get("NORMA")),
                "ha_en_cuadricula": round(ha, 1), "pct_cuadricula": round(100 * ha / area_total, 1),
                "nota": NOTA[nivel], "_geom": inter,
            })
        return out

    def forestal():
        svc, lid, where = FORESTAL
        out = []
        for f in g.query_en_poligono(svc, lid, anillo, "NOMTIT,CONTRA,TP_CONCE,ESTCON_DES,SUPSIG", where=where):
            geom = g.esri_a_shapely(f.get("geometry"), recorte=pol)
            if geom is None or geom.is_empty:
                continue
            inter = g._limpiar(geom.intersection(pol))
            if inter is None or inter.is_empty:
                continue
            a = f.get("attributes") or {}
            tipo_conc = _texto(a.get("TP_CONCE")).capitalize()
            estado = _texto(a.get("ESTCON_DES")).lower()
            ha = g.area_ha(inter)
            out.append({
                "tipo": f"Concesión forestal ({tipo_conc.lower() or 's/d'})", "nivel": "restringido",
                "nombre": _texto(a.get("NOMTIT")) or "(sin titular)", "categoria": tipo_conc,
                "uso": estado, "norma": f"Contrato {_texto(a.get('CONTRA'))}" if a.get("CONTRA") else "",
                "ha_en_cuadricula": round(ha, 1), "pct_cuadricula": round(100 * ha / area_total, 1),
                "nota": NOTA_FORESTAL + (" Contrato SUSPENDIDO." if estado == "suspendido" else ""), "_geom": inter,
            })
        return out

    with ThreadPoolExecutor(8) as ex:
        f_for = ex.submit(forestal)
        resultados = list(ex.map(una, CAPAS))
        resultados.append(f_for.result())
    areas = [x for r in resultados for x in r]
    # la misma área puede venir de dos capas (p. ej. 3 y 4): se deja una por nombre+tipo
    unicas: dict[tuple, dict] = {}
    for a in sorted(areas, key=lambda x: (x["nivel"] != "prohibido", -x["pct_cuadricula"])):
        unicas.setdefault((a["tipo"], a["nombre"]), a)
    return list(unicas.values())


def publicas(areas: list[dict]) -> list[dict]:
    return [{k: v for k, v in a.items() if not k.startswith("_")} for a in areas]


def en_zona(areas: list[dict], geom) -> dict | None:
    """Cuánto de una zona favorable cae en áreas prohibidas o restringidas."""
    if not areas or geom is None or geom.is_empty:
        return None
    area_zona = max(g.area_ha(geom), 1e-9)
    res = {}
    for nivel in ("prohibido", "restringido"):
        sel = [a for a in areas if a["nivel"] == nivel]
        if not sel:
            continue
        inter = g._limpiar(unary_union([a["_geom"] for a in sel]).intersection(geom))
        if inter is None or inter.is_empty:
            continue
        pct = round(100 * g.area_ha(inter) / area_zona, 1)
        if pct >= 0.1:
            nombres = sorted({a["nombre"] for a in sel if a["_geom"].intersects(geom)})
            res[nivel] = {"pct": pct, "nombres": nombres}
    if not res:
        return None
    peor = "prohibido" if "prohibido" in res else "restringido"
    return {"nivel": peor, "pct": res[peor]["pct"], "nombres": res[peor]["nombres"], "detalle": res}
