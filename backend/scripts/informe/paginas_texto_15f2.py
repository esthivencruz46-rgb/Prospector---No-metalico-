"""Páginas de texto del informe de 15f2-NO: antecedentes de boletines y análisis de las capas (con cifras reales)."""
import json
import os
import sys
sys.path.insert(0, r"c:/Users/ESTHIVEN/Downloads/prospector-rmi_1/prospector-rmi/backend")
os.chdir(r"c:/Users/ESTHIVEN/Downloads/prospector-rmi_1/prospector-rmi/backend")
import laminas
import supermaduras as sm

SAL = "../revision_informe/15f2-NO_v2/"
cf = json.load(open(SAL + "_cifras.json", encoding="utf-8"))
d = sm.datos()
c = sm.en_celda("15f2-NO")
U = {u["id"]: u for u in d["unidades"]}
B = d["boletines"]
celda = {"codigo": "15f2-NO", "sur": -7.375, "oeste": -78.75, "norte": -7.25, "este": -78.625}
base = {"autor": "Revisión técnica", "empresa": "KEDA Perú Building Materials Company",
        "proyecto": "Prospección de arena silícea para vidrio flotado", "celda": celda, "total": "16",
        "_lugar": "Contumaza, Cajamarca", "_zona": 17}
num = lambda v, k=1: f"{v:,.{k}f}".replace(",", " ").replace(".", ",")  # noqa: E731

# ------------------------------------------------------------- ANTECEDENTES
quim = [q for q in d["quimica"] if q.get("celda", "").startswith("15") and
        any(x in (q.get("unidad") or "") for x in ("Chimú", "Farrat"))]
quim.sort(key=lambda q: -float(str(q["sio2_txt"]).replace(",", ".")))
km = {x["id"]: x for x in c["unidades"]}
usados = sorted({x["bol"] for uid in ("chimu", "farrat") for x in U[uid]["citas"]})
secc = [
    {"titulo": "Unidades supermaduras en la cuadrícula",
     "parrafos": ["La carta geológica 1:50 000 de INGEMMET registra en 15f2-NO dos unidades del Grupo Goyllarisquizga "
                  "(Cretácico inferior) descritas en los boletines como areniscas cuarzosas y ortocuarcitas maduras a supermaduras:"],
     "vinetas": [f"Formación Chimú (Berriasiano – Valanginiano)|: {num(km['chimu']['km2'])} km² en {km['chimu']['afloramientos']} afloramientos. "
                 "Ortocuarcita de grano medio, recristalizada (Bol. 26-A, p. 29); cuarcita blanca de grano redondeado, fino a grueso, "
                 "con estratificación gruesa y cruzada (Bol. 17-A, p. 44). Espesor regional 500–700 m (Bol. 26-A, p. 28); la carta "
                 "local indica ~800 m.",
                 f"Formación Farrat (Aptiano superior)|: {num(km['farrat']['km2'])} km² en {km['farrat']['afloramientos']} afloramientos. "
                 "Ortocuarcitas blancas de grano fino con estratificación cruzada (Bol. 17-A, p. 50); cuarcitas y areniscas blancas de "
                 "grano medio a grueso, ~500 m de espesor (Bol. 31-A, p. 30). En Cajamarca los óxidos en fracturas obligan a lavar "
                 "el material (cantera Lavasil 1, Bol. 33-B, p. 267)."]},
    {"titulo": "Química de canteras y ocurrencias de la hoja 15-f (Bol. 33-B)",
     "parrafos": ["No hay canteras analizadas dentro de 15f2-NO. Las más cercanas, en las mismas formaciones y en la misma hoja "
                  "1:100 000, dan:"],
     "tabla": {"cab": ["Cantera / ocurrencia", "Unidad", "SiO₂ %", "Fe₂O₃ %", "Cuadrícula"],
               "anchos": [0.36, 0.22, 0.13, 0.13, 0.16],
               "filas": [[q["nombre"], q["unidad"].replace("Formación ", "Fm. "), q["sio2_txt"], q["fe2o3_txt"], q["celda"]] for q in quim],
               "nota": "Referencia para vidrio: arenas con 95–99,8 % de SiO₂; el hierro da tintes verdes y amarillos (Bol. 30-B, p. 181). "
                       "Para vidrio flotado se pide en la práctica SiO₂ ≥ 98,5 % y Fe₂O₃ ≤ 0,10 %: ninguna muestra lo cumple en bruto; "
                       "Huaca Corral (Fm. Chimú) es la más próxima. La Fm. Chimú es sistemáticamente más pobre en hierro que la Fm. Farrat."}},
    {"titulo": "Registro fotográfico (Bol. 33-B)", "nueva_columna": True,
     "imagenes": [{"archivo": os.path.join(sm.CARPETA_FOTOS, f["archivo"]), "pie": f["leyenda"][:150] + " — " + f["motivo"]}
                  for f in c["fotos"][:2]]},
    {"titulo": "Boletines consultados",
     "vinetas": [f"Bol. {k}|: {B[k]['autores']} ({B[k].get('anio') or 's. f.'}). {B[k]['titulo']}." for k in usados if k in B]},
]
for i, f in enumerate(c["fotos"][:2]):
    secc[2]["imagenes"][i]["pie"] = f.get("leyenda", "")[:160] + f" ({f.get('motivo', '')})"
png = laminas.pagina_texto({**base, "titulo": "Antecedentes bibliográficos · cuadrícula 15f2-NO", "lamina": "15",
                            "fuente": "INGEMMET · boletines Serie A y Serie B", "secciones": secc})
open(SAL + "15f2-NO_antecedentes.png", "wb").write(png)

# ------------------------------------------------------------- ANÁLISIS DE LAS CAPAS
z = {x["unidad"].split(" - ")[-1].replace("Formación ", ""): x for x in cf["zonas"]}
ce, L, dm = cf["celda"], cf["libres"], cf["dem"]
far, chi = z["Farrat"], z["Chimú"]
secc = [
    {"titulo": "Imagen satelital",
     "vinetas": [f"Imagen real (4-3-2)|: toma Sentinel-2 del 28/08/2026, 10:45 h, con 0 % de nubes y 40 % de vegetación (época seca). "
                 "Las areniscas forman crestas claras alineadas NO–SE; la vegetación se concentra en las quebradas y en la mitad sur.",
                 "Imagen geológica (SWIR 12-11-2)|: realza los estratos plegados de rumbo andino; las franjas claras corresponden a "
                 "las areniscas del Goyllarisquizga y las oscuras a quebradas con vegetación o humedad."]},
    {"titulo": "Índices espectrales (escala relativa a la cuadrícula, 0–100)",
     "tabla": {"cab": ["Unidad", "Área", "NDVI", "BSI", "Ferrug.", "Arcilla*"],
               "anchos": [0.34, 0.16, 0.12, 0.12, 0.13, 0.13],
               "filas": [[k, f"{num(x['ha'], 0)} ha", f"{x['ndvi_pct']:.0f}", f"{x['bsi_pct']:.0f}", f"{x['ferruginosa_pct']:.0f}",
                          f"{x['anomalia_arcilla_pct']:.0f} %"] for k, x in z.items()],
               "nota": "NDVI, BSI y ferruginosa = posición media de la unidad en la cuadrícula. *Arcilla = % de lo visible sobre el corte P90."},
     "vinetas": [f"NDVI y BSI|: la Fm. Farrat es la unidad más desnuda (BSI {far['bsi_pct']:.0f}, NDVI {far['ndvi_pct']:.0f}); la Fm. Chimú "
                 f"está más cubierta por vegetación (BSI {chi['bsi_pct']:.0f}, NDVI {chi['ndvi_pct']:.0f}). Sentinel-2 solo ve el suelo en el "
                 f"{cf['pct_valida']:.0f} % de la cuadrícula: el resto (vegetación densa, sombra) no se puede evaluar.",
                 f"Anomalías ferruginosas|: más altas en la Fm. Farrat ({far['ferruginosa_pct']:.0f}) que en la Fm. Chimú ({chi['ferruginosa_pct']:.0f}), "
                 "concentradas en el sector norte. Coincide con lo que reporta el Bol. 33-B: Farrat con más Fe₂O₃ (0,13–1,02 %) que Chimú (0,06–0,21 %).",
                 f"Arcillas|: bajas en las dos areniscas (≈ {far['anomalia_arcilla_pct']:.0f} % de lo visible sobre P90); mayores en la Fm. Santa "
                 "(lutitas) y en la Fm. Huaylas."]},
    {"titulo": "Condición legal y uso del suelo", "nueva_columna": True,
     "vinetas": ["Áreas protegidas|: 2,3 % de la cuadrícula — propuesta de área natural protegida regional «Cabeceras de cuenca» "
                 "(2,2 %, restringida, borde sur), zona arqueológica El Antivo (0,1 %, no concesionable) y derecho de vía de la PE-08.",
                 f"Concesiones|: {L['n_concesiones']} derechos mineros cubren el {num(L['concesiones_pct'])} % de la cuadrícula, sobre todo en la "
                 "mitad sur y el borde este; son mayoritariamente titulados, con petitorios en trámite al noreste.",
                 "Zonas libres|: 53,1 % libre y utilizable. Otro 8,9 % está libre pero no sirve para cantera: a menos de 300 m de centros "
                 "poblados (5,9 %), fajas de ríos (1,9 %), zona construida, chacras y carreteras."]},
    {"titulo": "Geología y relieve",
     "vinetas": ["Geología|: 11 unidades del Cretácico al Cuaternario, plegadas en franjas NO–SE. Las de interés (clase B) son la "
                 f"Fm. Farrat ({num(far['ha'], 0)} ha) y la Fm. Chimú ({num(chi['ha'], 0)} ha); Carhuaz, Santa e Inca son lutitas y "
                 "limoarcillitas con areniscas subordinadas (clase C, «verificar»).",
                 f"Topografía|: cotas de {num(dm['min'], 0)} a {num(dm['max'], 0)} m (desnivel {num(dm['max'] - dm['min'], 0)} m); "
                 f"pendiente media {dm['pend_media']:.0f}° y el 10 % del terreno supera {dm['pend_p90']:.0f}°. Las crestas altas del sur "
                 "(> 3 300 m) son de acceso difícil; el sector norte, más bajo (1 200–2 000 m), está junto a la carretera a Contumazá."]},
    {"titulo": "Síntesis",
     "parrafos": [f"La Prioridad libre (zonas A/B − anomalía ferruginosa − arcillas − áreas protegidas) suma ≈ 4 100 ha libres. "
                  "El blanco más accesible es la Fm. Farrat del sector centro-norte: está libre, aflora bien y está cerca de la vía, "
                  "aunque es la más ferruginosa y requerirá lavado. La Fm. Chimú tiene la mejor química regional, pero en esta cuadrícula "
                  "está más cubierta por vegetación y en buena parte dentro de concesiones al sur.",
                  "Recomendación: muestreo de canal en los bancos de la Fm. Farrat del sector norte y de la Fm. Chimú en las zonas "
                  "libres, con análisis químico (SiO₂, Fe₂O₃, Al₂O₃, TiO₂) y granulometría, antes de cualquier petitorio. "
                  "Los índices satelitales son relativos y no reemplazan el análisis de laboratorio."]},
]
png = laminas.pagina_texto({**base, "titulo": "Análisis de las capas · cuadrícula 15f2-NO", "lamina": "16",
                            "fuente": "Sentinel-2 · INGEMMET · Copernicus DEM", "secciones": secc})
open(SAL + "15f2-NO_analisis.png", "wb").write(png)
print("ok", len(quim), "filas de química;", usados)
