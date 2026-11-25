import json, sys
from collections import defaultdict
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
sys.stdout.reconfigure(encoding="utf-8")
d = json.load(open(sys.argv[1], encoding="utf-8"))["filas"]
F, FB = Font(name="Arial", size=10), Font(name="Arial", size=10, bold=True, color="FFFFFF")
FILL = PatternFill("solid", fgColor="1F3B57")


def hoja(wb, titulo, cab, filas, anchos):
    ws = wb.create_sheet(titulo)
    ws.append(cab)
    for c in ws[1]:
        c.font, c.fill, c.alignment = FB, FILL, Alignment(wrap_text=True, vertical="center")
    for r in filas:
        ws.append(r)
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.font = F
            c.alignment = Alignment(vertical="top", wrap_text=isinstance(c.value, str) and len(c.value) > 40)
    for i, w in enumerate(anchos, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(cab))}{ws.max_row}"
    return ws


wb = Workbook()
le = wb.active
le.title = "Criterios"
for t in ["Mejores cuadrículas 1:25 000 para VIDRIO FLOTADO según la descripción de la carta geológica (INGEMMET) — Prospector RMI, 23/11/2026.",
          "",
          "FILTRO (pedido del usuario): roca silícea (arenisca, cuarcita, ortocuarcita, arena) de las unidades supermaduras con",
          "  • COLOR cercano al blanco: blanco, blanquecino, blanco grisáceo, gris blanquecino. Se descarta la roca si en SU frase aparece cualquier otro color",
          "    (rojizo, amarillento, pardo, rosado, verde, gris a secas, gris oscuro, «blancas a grises»…). Los colores de otras rocas (lutitas negras, etc.) no cuentan.",
          "  • GRANO medio, medio a grueso o grueso. «Fino a medio» y «fino a grueso» quedan aparte (columna «km² fino a medio»); «fino» se descarta.",
          "  • Carta: 1:50 000; la 1:100 000 solo donde no hay 1:50 000.",
          "",
          "ORDEN: 1) rango de supermadurez de la mejor unidad (1 Chimú · 2 Goyllarisquizga · 3 Marcavilca · 4 Vivian · 5 Farrat …);",
          "       2) km² que cumplen y están libres y utilizables (estimado con el censo por tipo del 21–22/11/2026: % libre-utilizable de la misma unidad en la cuadrícula);",
          "       3) grano (medio antes que medio a grueso y grueso). Cada columna se puede reordenar con los filtros.",
          "",
          "VIDRIO FLOTADO (referencia de la industria, verificar con el comprador): SiO₂ ≥ 98,5–99 %, Fe₂O₃ ≤ 0,05–0,10 %, Al₂O₃ ≤ 0,5–1 %,",
          "  granulometría 0,1–0,5/0,6 mm (fina a media) con muy poco > 0,6 mm y < 0,1 mm. El grano GRUESO de la roca (0,5–1 mm) hay que molerlo o clasificarlo;",
          "  la arenisca se disgrega, se lava, se clasifica y a veces se trata con separación magnética o atrición para bajar el hierro.",
          "  Ninguna cantera analizada por INGEMMET llega a 99 % de SiO₂ en bruto: las mejores (Chimú, Cajamarca) dan 95–98 % y Fe₂O₃ 0,06–0,10 %, que",
          "  requieren beneficio. La columna «Química» muestra las canteras analizadas dentro de la cuadrícula.",
          "",
          "La descripción de la carta es una generalización por polígono: confirmar color, grano y química en campo y laboratorio (granulometría por tamizado,",
          "SiO₂, Fe₂O₃, Al₂O₃, TiO₂, Cr₂O₃)."]:
    le.append([t])
le.column_dimensions["A"].width = 160
for r in le.iter_rows():
    for c in r:
        c.font = F
filas = [[i + 1, f["codigo"], f["unidad"], f["rango"], f["grano"], f["km2"], f["km2_libre_aprox"], f["km2_casi_blanco"], f["km2_fino_a_medio"],
          f["afloramientos"], f["km_fabrica"], f["carta"], f["frase"], f["quimica"], f["unidades"], f["granos"], f["lat"], f["lon"]] for i, f in enumerate(d)]
hoja(wb, "Ranking cuadrículas", ["Puesto", "Cuadrícula 1:25 000", "Mejor unidad", "Rango supermadurez", "Grano (dominante)", "km² blanco + grano medio/grueso",
                                 "km² libres y utilizables (≈)", "km² casi blanco (gris claro, crema)", "km² blanco pero fino a medio", "Afloramientos",
                                 "km a la fábrica", "Carta", "Descripción de la carta (frase de la roca)", "Química de canteras en la cuadrícula",
                                 "Unidades (km²)", "Granos (km²)", "Lat", "Lon"], filas,
     (7, 13, 34, 9, 13, 12, 12, 12, 12, 10, 9, 8, 60, 50, 40, 30, 10, 10))
# por cuadrante 1:50 000
g = defaultdict(lambda: {"km2": 0.0, "libre": 0.0, "celdas": [], "uds": set(), "rango": 99, "km": 9999})
for f in d:
    k = f["codigo"].split("-")[0]
    x = g[k]
    x["km2"] += f["km2"]; x["libre"] += f["km2_libre_aprox"] or 0; x["celdas"].append(f["codigo"]); x["uds"].add(f["unidad"])
    x["rango"] = min(x["rango"], f["rango"]); x["km"] = min(x["km"], f["km_fabrica"])
g50 = sorted(g.items(), key=lambda kv: (kv[1]["rango"], -kv[1]["libre"]))
hoja(wb, "Por cuadrante 50K", ["Cuadrante 1:50 000", "Rango supermadurez (mejor)", "km² que cumplen", "km² libres y utilizables (≈)", "km a la fábrica (mín.)",
                                    "Unidades", "Cuadrículas 1:25 000"],
     [[k, v["rango"], round(v["km2"], 2), round(v["libre"], 2), v["km"], "; ".join(sorted(v["uds"])), ", ".join(v["celdas"])] for k, v in g50],
     (12, 12, 12, 14, 12, 50, 60))
wb.save(sys.argv[2])
print("filas:", len(filas), "| cuadrantes 50K:", len(g50))
