"""Arma el INFORME PDF de una cuadrícula a partir de sus láminas (revision_informe/<código>_v2/):
portada con índice, numeración corrida en el cajetín («NN de TT») y un PDF A3 apaisado a 150 ppp.

Uso:  python scripts/informe/armar_informe.py 15f2-NO
"""
import os
import sys
from datetime import date

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(AQUI)))
from PIL import Image, ImageDraw  # noqa: E402
import laminas as L  # noqa: E402

cod = sys.argv[1] if len(sys.argv) > 1 else "15f2-NO"
RAIZ = os.path.abspath(os.path.join(AQUI, "..", "..", ".."))
DIR = os.path.join(RAIZ, "revision_informe", f"{cod}_v2")

# orden del informe (pedido del usuario): satélite → condición legal → geología → topografía → resultado → texto
ORDEN = [
    ("natural", "Imagen real · Sentinel-2 (4-3-2): fecha, hora y nubosidad"),
    ("swir", "Imagen geológica · Sentinel-2 (12-11-2): bandas y motivo"),
    ("ndvi", "NDVI · vegetación"),
    ("bsi", "BSI · suelo y roca desnuda"),
    ("ferruginosas", "Anomalías ferruginosas (férrico + ferroso) al 100 %"),
    ("arcillas", "Arcillas, micas y sulfatos (B11/B12) al 100 %"),
    ("protegidas", "Áreas protegidas y restringidas"),
    ("concesiones", "Concesiones mineras (catastro de INGEMMET)"),
    ("libres", "Zonas libres para petitorio y aptas para cantera"),
    ("geologia_completa", "Mapa geológico de la cuadrícula (1:50 000)"),
    ("geologia_desc", "Descripción de las unidades geológicas"),
    ("topografia", "Mapa topográfico"),
    ("prioridad", "Prioridad libre (geología A/B − hierro − arcillas − áreas protegidas)"),
    ("ruta", "Ruta desde la planta KEDA (San Vicente de Cañete)"),
    ("antecedentes", "Antecedentes bibliográficos (boletines de INGEMMET)"),
    ("analisis", "Análisis de las capas y síntesis"),
]
paginas = [(k, t, os.path.join(DIR, f"{cod}_{k}.png")) for k, t in ORDEN]
faltan = [p for _, _, p in paginas if not os.path.exists(p)]
if faltan:
    sys.exit("Faltan láminas: " + ", ".join(os.path.basename(p) for p in faltan))
total = len(paginas)


def renumerar(img: Image.Image, n: int) -> Image.Image:
    """Reescribe el N.º de lámina del cajetín («NN de TT») con la numeración del informe."""
    d = ImageDraw.Draw(img)
    by0, by1 = L.LH - L.M - L.MEMBRETE, L.LH - L.M
    bx1 = L.LW - L.M
    xx = bx1 - 190
    d.rectangle([xx + 4, by0 + 56, bx1 - 4, by1 - 4], fill=L.BLANCO)
    d.text(((xx + bx1) / 2, by0 + 92), f"{n:02d}", font=L._fuente(44, True), fill=L.NEGRO, anchor="mm")
    d.text(((xx + bx1) / 2, by1 - 22), f"de {total:02d}", font=L._fuente(13), fill=L.GRIS, anchor="mm")
    return img


# ---------------------------------------------------------------- portada
celda = {"codigo": cod}
portada = L.pagina_texto({
    "titulo": f"Informe de prospección de arena silícea · cuadrícula {cod}",
    "empresa": "KEDA Perú Building Materials Company", "proyecto": "Prospección de arena silícea para vidrio flotado",
    "autor": "Revisión técnica", "fuente": "INGEMMET · ESA Copernicus · SERFOR", "lamina": "—",
    "_lugar": "Contumaza, Cajamarca", "_zona": 17,
    "secciones": [
        {"titulo": "Objeto",
         "parrafos": [f"Evaluar la cuadrícula 1:25 000 {cod} (hoja 1:50 000 15f2, hoja 1:100 000 15-f «Cajamarca»; "
                      "7°15′00″–7°22′30″ S, 78°45′00″–78°37′30″ O) como fuente de arena silícea para la planta de vidrio "
                      "flotado de KEDA Perú en San Vicente de Cañete: geología de interés, limpieza superficial vista por "
                      "satélite, condición legal (áreas protegidas, concesiones, terreno libre), relieve y acceso."]},
        {"titulo": "Fuentes",
         "vinetas": ["Geología|: INGEMMET, geología integrada 1:50 000 (GEOCATMIN) y boletines de las Series A y B.",
                     "Satélite|: Sentinel-2 L2A (ESA Copernicus), toma del 28/08/2026, 10:45 h (hora de Perú), 0 % de nubes.",
                     "Condición legal|: catastro minero y áreas reservadas de INGEMMET; catastro forestal de SERFOR; consultados en vivo.",
                     "Uso del suelo|: cobertura Sentinel-2 10 m (Esri / Impact Observatory) y cartografía base de INGEMMET.",
                     "Relieve|: Copernicus DEM GLO-30. Ruta: OpenStreetMap (Valhalla)."]},
        {"titulo": "Contenido", "nueva_columna": True,
         "tabla": {"cab": ["N.º", "Lámina"], "anchos": [0.12, 0.88],
                   "filas": [[f"{i:02d}", t] for i, (_, t, _) in enumerate(paginas, 1)],
                   "nota": "Información referencial elaborada con datos públicos. Los índices satelitales son relativos a la "
                           "cuadrícula y no reemplazan el muestreo ni el análisis de laboratorio. Verificar en campo y en "
                           f"INGEMMET antes de cualquier petitorio. Fecha de elaboración: {date.today():%d/%m/%Y}."}},
    ]})
imgs = [Image.open(__import__("io").BytesIO(portada)).convert("RGB")]
# en la portada el recuadro de lámina queda en blanco (sin número)
d = ImageDraw.Draw(imgs[0])
by0, by1, bx1 = L.LH - L.M - L.MEMBRETE, L.LH - L.M, L.LW - L.M
d.rectangle([bx1 - 190 + 4, by0 + 56, bx1 - 4, by1 - 4], fill=L.BLANCO)
d.text(((bx1 - 190 + bx1) / 2, by0 + 100), "PORTADA", font=L._fuente(17, True), fill=L.NEGRO, anchor="mm")

for i, (_, _, ruta) in enumerate(paginas, 1):
    imgs.append(renumerar(Image.open(ruta).convert("RGB"), i))

salida = os.path.join(RAIZ, "revision_informe", f"Informe_prospeccion_{cod}.pdf")
imgs[0].save(salida, "PDF", resolution=150, save_all=True, append_images=imgs[1:])
imgs[0].save(os.path.join(DIR, f"{cod}_00_portada.png"))
print("PDF:", salida, "·", len(imgs), "páginas ·", round(os.path.getsize(salida) / 1e6, 1), "MB")
