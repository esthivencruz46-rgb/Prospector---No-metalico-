"""Excel anexo: cuadrículas 1:25 000, cuadrantes 1:50 000 y canteras de las unidades supermaduras (v3).
Uso: python excel_cuadriculas.py <salida.xlsx>"""
import json, math, os, sys
from collections import defaultdict
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from pyproj import Transformer

sys.stdout.reconfigure(encoding="utf-8")
ESC = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ESC)
from evidencia_boletines import QUIMICA, OCURRENCIAS, AUTORES  # noqa: E402

D = json.load(open(os.path.join(ESC, "supermaduras2.json"), encoding="utf-8"))
FAB = D["fabrica"]
ALFA = "abcdefghijklmnñopqrstuvxyz"
PRIORIDAD = {"chimu": "1 · supermadura con química", "goyllarisquizga": "1 · supermadura con química", "marcavilca": "1 · supermadura (petrografía)",
             "farrat": "2 · madura a supermadura con química", "hualhuani": "3 · madura; química de fundente", "eolico": "2 · variable (depende del manto)",
             "vivian": "2 · supermadura por textura", "agua_caliente": "2 · supermadura por textura", "cushabatay": "3 · madura",
             "oriente": "3 · madura a supermadura", "huancane": "3 · heterogénea", "labra": "4 · madura con óxidos",
             "salto_fraile": "3 · madura", "naupe": "4 · certeza baja", "yauca": "4 · certeza baja", "oyon_chimu": "3 · mezcla"}


def celda(lat, lon):
    fila = math.floor(-lat / 0.5) + 1
    col = math.floor((lon + 81.5) / 0.5)
    norte, oeste = -(fila - 1) * 0.5, -81.5 + col * 0.5
    n50, e50 = lat >= norte - 0.25, lon >= oeste + 0.25
    cod50 = f"{fila}{ALFA[col]}" + str({(True, True): 1, (False, True): 2, (False, False): 3, (True, False): 4}[(n50, e50)])
    norte50 = norte if n50 else norte - 0.25
    oeste50 = oeste + 0.25 if e50 else oeste
    return f"{cod50}-" + ("N" if lat >= norte50 - 0.125 else "S") + ("E" if lon >= oeste50 + 0.125 else "O")


def hav(la1, lo1, la2, lo2):
    r = math.radians
    a = math.sin(r(la2 - la1) / 2) ** 2 + math.cos(r(la1)) * math.cos(r(la2)) * math.sin(r(lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


TR = {z: Transformer.from_crs(f"EPSG:327{z}", "EPSG:4326", always_xy=True) for z in (17, 18, 19)}
F = Font(name="Arial", size=10)
FB = Font(name="Arial", size=10, bold=True, color="FFFFFF")
FILL = PatternFill("solid", fgColor="1F3B57")


def hoja(wb, titulo, cab, filas, anchos):
    ws = wb.create_sheet(titulo)
    ws.append(cab)
    for c in ws[1]:
        c.font = FB; c.fill = FILL; c.alignment = Alignment(wrap_text=True, vertical="center")
    for r in filas:
        ws.append(r)
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.font = F
    for i, w in enumerate(anchos, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(cab))}{ws.max_row}"
    return ws


wb = Workbook()
le = wb.active; le.title = "Léeme"
for t in ["Anexo del informe «Arenas y areniscas supermaduras del Perú» (versión 3) – Prospector RMI.",
          "Cuadrícula 1:25 000 = mismo código que la app (hoja 1:100 000 → cuadrante 1:50 000 numerado 1 NE, 2 SE, 3 SO, 4 NO → NE/NO/SE/SO), p. ej. 27k4-NE.",
          "Regla de cartas: donde hay geología 1:50 000 se usa SOLO la 1:50 000; la 1:100 000 únicamente donde no hay 1:50 000.",
          "km² = área cartografiada de la unidad dentro de la cuadrícula (sin descontar concesiones, áreas protegidas ni cobertura).",
          "Afloramientos = pedazos de polígono de la unidad dentro de la cuadrícula. Distancias a la fábrica (San Vicente de Cañete) en línea recta.",
          "Prioridad: lectura de este informe (1 = mejor evidencia de supermadurez) — es una guía, no un ranking definitivo.",
          "Metamórficas: solo polígonos cuya descripción menciona cuarcita o roca cuarzosa.",
          "Hojas: «Por cuadrícula» (todas las unidades juntas), «Cuadrículas 25K» (una fila por unidad y cuadrícula), «Cuadrantes 50K», «Canteras»."]:
    le.append([t])
le.column_dimensions["A"].width = 150
for row in le.iter_rows():
    for c in row:
        c.font = F

# por cuadrícula (todas las unidades)
pc = defaultdict(lambda: {"sed": 0.0, "meta": 0.0, "unidades": [], "km": 9999, "dep": "", "prov": "", "lat": None, "lon": None, "mayor": 0})
filas25, filas50 = [], []
for u in D["unidades"]:
    tipo = "metamórfica" if u["tipo"] == "meta" else "sedimentaria / depósito"
    prio = PRIORIDAD.get(u["id"], "5 · cuarcita metamórfica" if u["tipo"] == "meta" else "")
    for c in u["celdas25"]:
        filas25.append([c["codigo"], u["nombre"], tipo, prio, round(c["km2"], 3), c["pols"], c["carta"], c["departamento"], c["provincia"],
                        c["lat"], c["lon"], c["km_fabrica"]])
        x = pc[c["codigo"]]
        x["meta" if u["tipo"] == "meta" else "sed"] += c["km2"]
        x["unidades"].append((c["km2"], u["nombre"]))
        if c["km2"] > x["mayor"]:
            x.update(mayor=c["km2"], dep=c["departamento"], prov=c["provincia"], lat=c["lat"], lon=c["lon"])
        x["km"] = min(x["km"], c["km_fabrica"])
    for f in u["filas"]:
        filas50.append([f["hoja"], f["escala"], u["nombre"], tipo, f["area_km2"], f["poligonos"], f["departamento"], f["provincia"], f["lat"], f["lon"],
                        f["utm"], f["km_fabrica"], f["edad"], ", ".join(f["grosor"]), ", ".join(f["referencia"]), (f["descripciones"] or [""])[0]])
filas25.sort(key=lambda r: (r[1], -r[4]))
pcf = [[k, round(v["sed"], 3), round(v["meta"], 3), len(v["unidades"]),
        "; ".join(f"{n} ({a:.2f} km²)" for a, n in sorted(v["unidades"], reverse=True)), v["dep"], v["prov"], v["lat"], v["lon"], v["km"]]
       for k, v in pc.items()]
pcf.sort(key=lambda r: -r[1])
hoja(wb, "Por cuadrícula", ["Cuadrícula 1:25 000", "km² sedimentarias/depósitos", "km² cuarcitas metamórficas", "N.° unidades", "Unidades (km²)",
                            "Departamento", "Provincia", "Lat", "Lon", "km a la fábrica"], pcf, (14, 14, 14, 9, 90, 14, 16, 10, 10, 10))
hoja(wb, "Cuadrículas 25K", ["Cuadrícula 1:25 000", "Unidad", "Tipo", "Prioridad (lectura del informe)", "km²", "Afloramientos", "Carta",
                             "Departamento", "Provincia", "Lat", "Lon", "km a la fábrica"], filas25, (14, 44, 18, 30, 9, 11, 9, 14, 16, 10, 10, 10))
hoja(wb, "Cuadrantes 50K", ["Cuadrante / hoja", "Carta", "Unidad", "Tipo", "km²", "Polígonos", "Departamento", "Provincia", "Lat", "Lon", "UTM",
                            "km a la fábrica", "Edad", "Grosor", "Referencia del mapa", "Descripción INGEMMET (la de más área)"],
     filas50, (11, 7, 40, 16, 9, 9, 14, 16, 10, 10, 24, 10, 30, 14, 50, 80))
can = []
for r in QUIMICA:
    bol, tabla, pag, nombre, lugar, h100, z, n, e_, uni, esp, desc, muestra, si, fe, al, nota = r
    lo, la = TR[z].transform(e_, n)
    can.append([nombre, celda(la, lo), h100, lugar, uni, esp, si, fe, al, "con química", round(la, 5), round(lo, 5), f"{z}S {e_} E {n} N",
                round(hav(FAB[0], FAB[1], la, lo)), desc + (". " + nota if nota else ""), f"Bol. {bol}" + (f", tabla {tabla}" if tabla else "") + f", pág. {pag}"])
for bol, pag, nombre, lugar, h100, z, n, e_, uni, est in OCURRENCIAS:
    lo, la = TR[z].transform(e_, n)
    can.append([nombre, celda(la, lo), h100, lugar, uni, "", None, None, None, f"sin química · {est}", round(la, 5), round(lo, 5), f"{z}S {e_} E {n} N",
                round(hav(FAB[0], FAB[1], la, lo)), "", f"Bol. {bol}, pág. {pag}"])
ws = hoja(wb, "Canteras", ["Cantera / ocurrencia", "Cuadrícula 1:25 000", "Hoja 1:100 000", "Distrito / provincia", "Unidad", "Espesor",
                           "SiO₂ %", "Fe₂O₃ %", "Al₂O₃ %", "Datos", "Lat", "Lon", "UTM", "km a la fábrica", "Descripción", "Fuente (página del PDF)"],
          can, (34, 14, 10, 26, 34, 9, 8, 8, 8, 22, 10, 10, 26, 10, 60, 26))
ws.cell(len(can) + 3, 1, "Multicolor I y Choquisani (Bol. 30-B) solo informan SiO₂ «> 90 %»; la fila de Fátima 1 / V. de las Peñas III / Mercedes II resume 3 análisis sin rótulo (SiO₂ 92,8–93,0 %; Fe₂O₃ 0,70–1,07 %).").font = Font(name="Arial", size=9, italic=True)
wb.save(sys.argv[1])
print("cuadrículas únicas:", len(pc), "| filas 25K:", len(filas25), "| cuadrantes:", len(filas50), "| canteras:", len(can))
