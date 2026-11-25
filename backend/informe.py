"""Páginas de texto del INFORME PDF de una cuadrícula (botón «Informe PDF» de la app), armadas con los datos de la
propia cuadrícula, sin intervención manual:

  · portada   → objeto, fuentes y contenido (índice de láminas).
  · antecedentes → unidades supermaduras de la cuadrícula, citas de los boletines, química de canteras de la misma
                   hoja 1:100 000, fotos y boletines consultados (datos/supermaduras.json).
  · analisis  → tabla de índices por unidad, condición legal, relieve (Copernicus DEM) y síntesis.

El texto es de PLANTILLA con cifras: correcto y consistente, pero no reemplaza la lectura de un geólogo.
"""
from __future__ import annotations

import os
from datetime import date

import numpy as np

import laminas


def _num(v, k=1) -> str:
    return f"{v:,.{k}f}".replace(",", " ").replace(".", ",")


def _base(p: dict) -> dict:
    c = p["celda"]
    lug = laminas.lugar((c["sur"] + c["norte"]) / 2, (c["oeste"] + c["este"]) / 2)
    zona = int((((c["oeste"] + c["este"]) / 2) + 180) // 6) + 1
    return {**p, "_lugar": f"{lug['provincia']}, {lug['departamento']}" if lug["provincia"] != "—" else lug["departamento"],
            "_zona": zona}


def _corto(unidad: str) -> str:
    return (unidad or "—").split(" - ")[-1].replace("Formación ", "Fm. ").replace("Grupo ", "Gpo. ")


# ------------------------------------------------------------------ PORTADA
def portada(p: dict) -> bytes:
    c = p["celda"]
    gms = laminas.gms
    secc = [
        {"titulo": "Objeto",
         "parrafos": [f"Evaluar la cuadrícula 1:25 000 {c['codigo']} (hoja 1:50 000 {c['codigo'].split('-')[0]}, hoja 1:100 000 "
                      f"{p.get('hoja100') or '—'}; {gms(c['norte'], True)} – {gms(c['sur'], True)}, {gms(c['oeste'], False)} – "
                      f"{gms(c['este'], False)}) como fuente de {p.get('materia') or 'arena silícea'}"
                      f"{' para ' + p['empresa'] if p.get('empresa') else ''}: geología de interés, limpieza superficial vista por "
                      "satélite, condición legal (áreas protegidas, concesiones, terreno libre), relieve y acceso."]},
        {"titulo": "Fuentes",
         "vinetas": ["Geología|: INGEMMET, geología integrada (GEOCATMIN) y boletines de las Series A y B.",
                     f"Satélite|: Sentinel-2 L2A (ESA Copernicus), toma {p.get('toma') or '—'}.",
                     "Condición legal|: catastro minero y áreas reservadas de INGEMMET; catastro forestal de SERFOR, consultados en vivo.",
                     "Uso del suelo|: cobertura Sentinel-2 10 m y cartografía base de INGEMMET.",
                     "Relieve|: Copernicus DEM GLO-30. Ruta: OpenStreetMap (Valhalla)."]},
        {"titulo": "Contenido", "nueva_columna": True,
         "tabla": {"cab": ["N.º", "Lámina"], "anchos": [0.12, 0.88],
                   "filas": [[f"{i:02d}", t] for i, t in enumerate(p.get("contenido") or [], 1)],
                   "nota": "Información referencial elaborada con datos públicos. Los índices satelitales son relativos a la "
                           "cuadrícula y no reemplazan el muestreo ni el análisis de laboratorio. Verificar en campo y en INGEMMET "
                           f"antes de cualquier petitorio. Fecha de elaboración: {date.today():%d/%m/%Y}."}},
    ]
    return laminas.pagina_texto({**_base(p), "titulo": f"Informe de prospección · cuadrícula {c['codigo']}",
                                 "fuente": "INGEMMET · ESA Copernicus · SERFOR", "lamina": "—", "secciones": secc})


# ------------------------------------------------------------------ ANTECEDENTES
def antecedentes(p: dict) -> bytes:
    import supermaduras as sm
    c = p["celda"]
    d = sm.datos()
    en = sm.en_celda(c["codigo"])
    U = {u["id"]: u for u in d["unidades"]}
    B = d.get("boletines", {})
    # hoja 1:100 000 de la cuadrícula y sus vecinas (fila ±1, columna ±1; alfabeto de la Carta Nacional)
    import re as _re
    ALF = "abcdefghijklmnñopqrstuvxyz"
    mm = _re.match(r"(\d+)([a-zñ])", c["codigo"])
    fila, col = int(mm.group(1)), ALF.index(mm.group(2))
    hojas = {f"{f}{ALF[k]}" for f in (fila - 1, fila, fila + 1) for k in (col - 1, col, col + 1) if 0 <= k < len(ALF)}
    hoja = f"{fila}{ALF[col]}"
    secc = []
    usados: set[str] = set()
    if en["unidades"]:
        vin = []
        for x in en["unidades"]:
            u = U.get(x["id"], {})
            citas = u.get("citas", [])[:3]
            usados.update(ci["bol"] for ci in citas)
            def recorta(t, n=170):
                t = t.strip()
                if len(t) <= n:
                    return t.rstrip(".")
                return t[:n].rsplit(" ", 1)[0].rstrip(",;:.") + "…"
            txt = "; ".join(f"«{recorta(ci['texto'])}» ({ci['ref'].split('·')[0].strip()}, p. {ci['pag']})" for ci in citas)
            vin.append(f"{x['nombre']}|: {_num(x['km2'])} km² en {x['afloramientos']} afloramientos (prioridad {x['prioridad']}: "
                       f"{x['prioridad_txt'].lower()}). {txt}.")
        secc.append({"titulo": "Unidades supermaduras en la cuadrícula",
                     "parrafos": ["Unidades de la cuadrícula descritas en los boletines de INGEMMET como areniscas cuarzosas, "
                                  "ortocuarcitas o arenas maduras a supermaduras:"], "vinetas": vin})
        nombres = {U[x["id"]]["nombre"].split(" (")[0] for x in en["unidades"] if x["id"] in U}
        hoja_de = lambda cod: (_re.match(r"(\d+[a-zñ])", str(cod)) or [None, ""])[1]  # noqa: E731
        quim = [q for q in d.get("quimica", []) if hoja_de(q.get("celda", "")) in hojas
                and any(n.split()[-1] in (q.get("unidad") or "") for n in nombres)]
        quim.sort(key=lambda q: -float(str(q.get("sio2_txt", "0")).replace(",", ".") or 0))
        if quim:
            usados.update(str(q.get("fuente", "")).split("·")[0].replace("Bol.", "").strip() for q in quim)
            secc.append({"titulo": f"Química de canteras (hoja {hoja} y vecinas)",
                         "tabla": {"cab": ["Cantera / ocurrencia", "Unidad", "SiO₂ %", "Fe₂O₃ %", "Cuadrícula"],
                                   "anchos": [0.36, 0.22, 0.13, 0.13, 0.16],
                                   "filas": [[q["nombre"], _corto(q.get("unidad", "")), q.get("sio2_txt", "—"),
                                              q.get("fe2o3_txt", "—"), q.get("celda", "—")] for q in quim[:12]],
                                   "nota": "Referencia para vidrio flotado: SiO₂ ≥ 98,5 % y Fe₂O₃ ≤ 0,10 % (en la práctica). "
                                           "Valores de INGEMMET, Bol. 33-B / 26-B / 30-B según la región."}})
        else:
            secc.append({"titulo": "Química", "parrafos": ["No hay canteras con análisis químico de estas unidades en la misma hoja 1:100 000."]})
    else:
        secc.append({"titulo": "Unidades supermaduras",
                     "parrafos": ["La cuadrícula no tiene unidades supermaduras registradas en el informe de boletines (51 boletines de "
                                  "INGEMMET). La evaluación se apoya solo en la carta geológica y en el satélite."]})
    if en.get("fotos"):
        secc.append({"titulo": "Registro fotográfico (boletines de INGEMMET)", "nueva_columna": True,
                     "imagenes": [{"archivo": os.path.join(sm.CARPETA_FOTOS, f["archivo"]),
                                   "pie": f"{f.get('leyenda', '')[:150]} ({f.get('motivo', '')})"} for f in en["fotos"][:2]]})
    bol = [k for k in sorted(usados) if k in B]
    if bol:
        secc.append({"titulo": "Boletines consultados", "nueva_columna": not en.get("fotos"),
                     "vinetas": [f"Bol. {k}|: {B[k].get('autores', '')} ({B[k].get('anio') or 's. f.'}). {B[k].get('titulo', '')}." for k in bol]})
    return laminas.pagina_texto({**_base(p), "titulo": f"Antecedentes bibliográficos · cuadrícula {c['codigo']}",
                                 "fuente": "INGEMMET · boletines Serie A y Serie B", "secciones": secc})


# ------------------------------------------------------------------ UNIDADES ELEGIDAS (análisis bibliográfico)
def unidades(p: dict) -> bytes:
    """ANÁLISIS BIBLIOGRÁFICO DE LAS UNIDADES ELEGIDAS para la Prioridad libre (pedido del usuario, 24/11/2026: «de las
    que se seleccionan se analizan bibliográficamente, en el informe individual de cuadrícula»). Por unidad: la
    descripción de la carta de INGEMMET y su lectura para vidrio flotado (vidrio_desc = vidrio.ts: a favor, en contra,
    estrato, espesor), las citas de los boletines si es una unidad supermadura, la química de canteras de esa unidad en
    la hoja 1:100 000 y vecinas, y su resultado en la Prioridad libre (percentiles calculados dentro de la unidad)."""
    import re as _re
    import ranking
    import supermaduras as sm
    import vidrio_desc
    c = p["celda"]
    d = sm.datos() or {}
    U = {u["id"]: u for u in d.get("unidades", [])}
    B = d.get("boletines", {})
    ALF = "abcdefghijklmnñopqrstuvxyz"
    mm = _re.match(r"(\d+)([a-zñ])", c["codigo"])
    fila, col = int(mm.group(1)), ALF.index(mm.group(2))
    hojas = {f"{f}{ALF[k]}" for f in (fila - 1, fila, fila + 1) for k in (col - 1, col, col + 1) if 0 <= k < len(ALF)}
    hoja_de = lambda cod: (_re.match(r"(\d+[a-zñ])", str(cod)) or [None, ""])[1]  # noqa: E731

    def recorta(t, n):
        t = (t or "").strip()
        return t if len(t) <= n else t[:n].rsplit(" ", 1)[0].rstrip(",;:.") + "…"

    uds = p.get("unidades") or []
    filas_resumen = []
    secc = []
    usados: set[str] = set()
    for k, u in enumerate(uds[:6]):
        # la descripción que más área ocupa en la cuadrícula manda; las demás se mencionan
        descs = sorted(u.get("descripciones") or [], key=lambda x: -(x.get("ha") or 0))
        principal = descs[0] if descs else {"texto": "", "litologia": "", "roca": ""}
        ap = vidrio_desc.aptitud(principal.get("texto", ""), principal.get("litologia", ""), principal.get("roca", ""))
        vin = [f"Descripción (carta {p.get('escala') or '1:50 000'})|: «{recorta(principal.get('texto') or principal.get('litologia'), 330)}»"]
        lectura = f"{vidrio_desc.NIVEL_TEXTO[ap['nivel']]} (puntaje {ap['puntaje']}/100)"
        if ap["a_favor"]:
            lectura += f". A favor: {', '.join(ap['a_favor'])}"
        if ap["en_contra"]:
            lectura += f". En contra: {', '.join(ap['en_contra'])}"
        vin.append(f"Lectura para vidrio|: {lectura}.")
        estr = "; ".join(f"«{e['texto']}» ({e['tipo']})" for e in ap["estratos"]) or "la descripción no lo indica"
        vin.append(f"Estrato|: {estr}{'; espesor de la unidad ≈ ' + ap['espesor'] if ap['espesor'] else ''}.")
        if len(descs) > 1:
            vin.append(f"Otras descripciones|: la unidad tiene {len(descs)} polígonos con textos distintos en la cuadrícula; "
                       "se resume el de mayor área.")
        k_sm = ranking.unidad_sm(u.get("nombre", ""))
        usm = U.get(k_sm) if k_sm else None
        if usm:
            citas = usm.get("citas", [])[:2]
            usados.update(ci["bol"] for ci in citas)
            txt = "; ".join(f"«{recorta(ci['texto'], 160)}» ({ci['ref'].split('·')[0].strip()}, p. {ci['pag']})" for ci in citas)
            vin.append(f"Boletines|: unidad supermadura (prioridad {usm.get('prioridad')}: {str(usm.get('prioridad_txt', '')).lower()}; "
                       f"madurez {str(usm.get('madurez', '—')).rstrip('. ')}). {txt}.")
            quim = [q for q in d.get("quimica", []) if q.get("unidad_id") == k_sm and hoja_de(q.get("celda", "")) in hojas]
            quim.sort(key=lambda q: -float(q.get("sio2") or 0))
            if quim:
                q = quim[0]
                usados.update(str(x.get("fuente", "")).split("·")[0].replace("Bol.", "").strip() for x in quim)
                vin.append(f"Química|: {len(quim)} cantera(s) de esta unidad en la hoja y vecinas; la mejor, {q['nombre']} "
                           f"({q.get('celda', '—')}): SiO₂ {q.get('sio2_txt', '—')} %, Fe₂O₃ {q.get('fe2o3_txt', '—')} %.")
            else:
                vin.append("Química|: sin canteras analizadas de esta unidad en la hoja 1:100 000 ni en las vecinas.")
        else:
            vin.append("Boletines|: no figura entre las unidades supermaduras de los 51 boletines revisados; solo la carta la describe.")
        if u.get("libre") is not None:
            vin.append(f"Prioridad libre|: {_num(u.get('libre') or 0, 0)} ha libres y {_num(u.get('negociable') or 0, 0)} ha en concesión; "
                       f"pasa el {_num(u.get('pasa') or 0)} % de su parte visible (NDVI, anomalía ferruginosa y arcilla con percentiles de la propia unidad).")
        secc.append({"titulo": f"{k + 1}. {u.get('nombre', '—')} · clase {u.get('clase', '—')} · {_num(u.get('ha') or 0, 0)} ha",
                     "vinetas": vin, **({"nueva_columna": True} if k == (min(len(uds), 6) + 1) // 2 else {})})
        filas_resumen.append((vidrio_desc.ORDEN_NIVEL[ap["nivel"]], -ap["puntaje"], -(u.get("libre") or 0), u.get("nombre", "—"),
                              vidrio_desc.NIVEL_TEXTO[ap["nivel"]], u.get("libre") or 0, bool(usm)))
    if filas_resumen:
        filas_resumen.sort()
        mejor = filas_resumen[0]
        par = [f"Unidades elegidas para la Prioridad libre: {len(uds)}. Por su descripción bibliográfica, la mejor para vidrio flotado es "
               f"{mejor[3]} ({mejor[4].lower()}, {_num(mejor[5], 0)} ha libres)"
               + (", además respaldada por los boletines como unidad supermadura." if mejor[6] else ".")]
        malas = [f[3] for f in filas_resumen if f[0] >= 2]
        if malas:
            par.append("Con lectura baja o no apta (rocas finas intercaladas, colores de hierro o roca principal no silícea): "
                       + ", ".join(malas) + ". Conviene revisarlas en campo antes de incluirlas.")
        par.append("La lectura es del texto de la carta y de los boletines, no un análisis químico: confirmar con muestreo de canal "
                   "(SiO₂, Fe₂O₃, Al₂O₃, TiO₂) y granulometría.")
        secc.append({"titulo": "Síntesis bibliográfica", "parrafos": par})
    else:
        secc.append({"titulo": "Unidades elegidas", "parrafos": ["No se eligió ninguna unidad para la Prioridad libre."]})
    bol = [k for k in sorted(usados) if k in B]
    if bol:
        secc.append({"titulo": "Boletines citados",
                     "vinetas": [f"Bol. {k}|: {B[k].get('autores', '')} ({B[k].get('anio') or 's. f.'}). {B[k].get('titulo', '')}." for k in bol]})
    return laminas.pagina_texto({**_base(p), "titulo": f"Análisis bibliográfico de las unidades elegidas · cuadrícula {c['codigo']}",
                                 "fuente": "INGEMMET · carta geológica y boletines Serie A y Serie B", "secciones": secc})


# ------------------------------------------------------------------ ANÁLISIS
def analisis(p: dict) -> bytes:
    import relieve
    c = p["celda"]
    zonas = p.get("zonas_s2") or []       # [{unidad, clase, ha, ndvi, bsi, ferr, arcilla}]
    im = p.get("imagen") or {}
    L = p.get("libres") or {}
    restr = p.get("restricciones") or []
    pl = p.get("prioridad") or {}
    ha_celda = max(float(p.get("ha_celda") or 1), 1)
    secc = []
    # satélite
    secc.append({"titulo": "Imagen satelital",
                 "vinetas": [f"Toma Sentinel-2|: {im.get('fecha') or '—'} (hora de Perú), {im.get('nubes', '—')} % de nubes en la "
                             f"cuadrícula y {im.get('vegetacion', '—')} % de vegetación. Sentinel-2 ve el suelo en el "
                             f"{_num(float(p.get('pct_valida') or 0), 0)} % de la cuadrícula; el resto (vegetación densa, sombra, agua) no se evalúa.",
                             "Imagen geológica (SWIR 12-11-2)|: separa las rocas por su respuesta en el infrarrojo de onda corta; "
                             "las areniscas y cuarcitas claras se ven en tonos claros."]})
    con = [z for z in zonas if z.get("ndvi") is not None]
    if con:
        ab = [z for z in con if z.get("clase") in ("A", "B")] or con
        mas_desnuda = max(ab, key=lambda z: z["bsi"])
        mas_cubierta = max(ab, key=lambda z: z["ndvi"])
        mas_fe = max(ab, key=lambda z: z["ferr"])
        menos_fe = min(ab, key=lambda z: z["ferr"])
        vin = [f"NDVI y BSI|: entre las unidades de interés, {_corto(mas_desnuda['unidad'])} es la más desnuda (BSI {mas_desnuda['bsi']:.0f}) "
               f"y {_corto(mas_cubierta['unidad'])} la más cubierta por vegetación (NDVI {mas_cubierta['ndvi']:.0f})."]
        if mas_fe is not menos_fe:
            vin.append(f"Anomalías ferruginosas|: más altas en {_corto(mas_fe['unidad'])} ({mas_fe['ferr']:.0f}) y más bajas en "
                       f"{_corto(menos_fe['unidad'])} ({menos_fe['ferr']:.0f}).")
        arc = max(con, key=lambda z: z.get("arcilla") or 0)
        vin.append(f"Arcillas|: la unidad con más arcilla sobre el corte es {_corto(arc['unidad'])} ({arc.get('arcilla') or 0:.0f} % de lo visible).")
        secc.append({"titulo": "Índices espectrales (relativos a la cuadrícula, 0–100)", "vinetas": vin,
                     "tabla": {"cab": ["Unidad", "Clase", "Área", "NDVI", "BSI", "Ferrug.", "Arcilla*"],
                               "anchos": [0.30, 0.09, 0.15, 0.11, 0.11, 0.12, 0.12],
                               "filas": [[_corto(z["unidad"]), z.get("clase", ""), f"{_num(z['ha'], 0)} ha", f"{z['ndvi']:.0f}",
                                          f"{z['bsi']:.0f}", f"{z['ferr']:.0f}", f"{z.get('arcilla') or 0:.0f} %"] for z in con[:10]],
                               "nota": "NDVI, BSI y ferruginosa = posición media de la unidad en la cuadrícula. *Arcilla = % de lo visible sobre el corte."}})
    # condición legal
    vin = []
    if restr:
        tot = sum(r.get("pct", 0) for r in restr)
        lista = ", ".join(f"{r['nombre']} ({r['tipo'].lower()}, {_num(r['pct'])} %, "
                          f"{'no concesionable' if r.get('nivel') == 'prohibido' else 'restringido'})" for r in restr[:4])
        vin.append(f"Áreas protegidas|: {_num(tot)} % de la cuadrícula — {lista}.")
    else:
        vin.append("Áreas protegidas|: ninguna dentro de la cuadrícula.")
    if L:
        vin.append(f"Concesiones|: {L.get('n_concesiones', 0)} derechos mineros cubren el {_num(L.get('concesiones_pct') or 0)} % de la cuadrícula.")
        no_apto = sorted(L.get("no_apto") or [], key=lambda x: -x.get("ha", 0))
        na = "; ".join(f"{x['texto']} {_num(100 * x['ha'] / ha_celda)} %" for x in no_apto[:4])
        vin.append(f"Zonas libres|: {_num(L.get('util_pct') or L.get('libre_pct') or 0)} % libre y utilizable."
                   + (f" Libre pero no apto para cantera: {na}." if na else ""))
    secc.append({"titulo": "Condición legal y uso del suelo", "nueva_columna": True, "vinetas": vin})
    # geología y relieve
    ab_all = [z for z in zonas if z.get("clase") in ("A", "B")]
    vin = [f"Geología de interés|: {len(ab_all)} zona(s) A/B ("
           + ", ".join(f"{_corto(z['unidad'])} {_num(z['ha'], 0)} ha" for z in sorted(ab_all, key=lambda z: -z["ha"])[:4])
           + "); la clase C es «verificar»." if ab_all else "Geología de interés|: sin zonas A/B en la cuadrícula."]
    try:
        z, _ = relieve.dem(c["sur"], c["oeste"], c["norte"], c["este"])
        gy, gx = np.gradient(np.nan_to_num(z, nan=float(np.nanmin(z))), 30.0)
        pend = np.degrees(np.arctan(np.hypot(gx, gy)))
        vin.append(f"Topografía|: cotas de {_num(float(np.nanmin(z)), 0)} a {_num(float(np.nanmax(z)), 0)} m (desnivel "
                   f"{_num(float(np.nanmax(z) - np.nanmin(z)), 0)} m); pendiente media {np.nanmean(pend):.0f}° y el 10 % del terreno "
                   f"supera {np.nanpercentile(pend, 90):.0f}°.")
    except Exception:  # noqa: BLE001
        pass
    if p.get("ruta_km"):
        vin.append(f"Acceso|: {_num(p['ruta_km'], 0)} km por carretera desde la planta "
                   f"({_num(p.get('ruta_pista') or 0, 0)} km asfaltados, {_num(p.get('ruta_trocha') or 0, 0)} km de trocha).")
    secc.append({"titulo": "Geología y relieve", "vinetas": vin})
    # síntesis
    par = []
    if pl:
        par.append(f"La Prioridad libre (zonas A/B que cumplen a la vez NDVI bajo, anomalía ferruginosa baja y arcilla baja, menos áreas protegidas) suma "
                   f"{_num(pl.get('libre') or 0, 0)} ha libres y {_num(pl.get('negociable') or 0, 0)} ha en concesiones tituladas o en trámite.")
        mejor = pl.get("mejor")
        if mejor:
            par.append(f"La unidad con más superficie libre y limpia es {_corto(mejor['unidad'])} ({_num(mejor['ha'], 0)} ha libres).")
    par.append("Recomendación: muestreo de canal en las zonas libres de las unidades A/B, con análisis químico (SiO₂, Fe₂O₃, Al₂O₃, "
               "TiO₂) y granulometría, antes de cualquier petitorio. Los índices satelitales son relativos y no reemplazan el "
               "análisis de laboratorio.")
    secc.append({"titulo": "Síntesis", "parrafos": par})
    return laminas.pagina_texto({**_base(p), "titulo": f"Análisis de las capas · cuadrícula {c['codigo']}",
                                 "fuente": "Sentinel-2 · INGEMMET · Copernicus DEM", "secciones": secc})
