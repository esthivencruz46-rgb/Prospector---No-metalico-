"""Informe PDF: arenas y areniscas supermaduras del Perú (recopilación técnica por unidad y cuadrángulo)."""
import html, json, os, sys, time
import fitz
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPoly

ESC = os.path.dirname(os.path.abspath(__file__))
DATOS = json.load(open(os.path.join(ESC, "supermaduras2.json"), encoding="utf-8"))
BACK = r"c:\Users\ESTHIVEN\Downloads\prospector-rmi_1\prospector-rmi\backend"
SALIDA = sys.argv[1]
ARCH = os.path.join(ESC, "informe_arch")
os.makedirs(ARCH, exist_ok=True)
for f in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"):
    src = os.path.join(BACK, "fonts", f)
    if os.path.exists(src):
        open(os.path.join(ARCH, f), "wb").write(open(src, "rb").read())
FAB = DATOS["fabrica"]
e = lambda s: html.escape(str(s if s is not None else ""))  # noqa: E731

# ------------------------------------------------------------------ fichas técnicas (bibliografía verificada)
FUENTES = {
    "P1035": ("INGEMMET (2003). Memoria descriptiva de la revisión y actualización del cuadrángulo de Canta (23-j), cuadrante I. Dirección de Geología Regional.",
              "https://app.ingemmet.gob.pe/biblioteca/pdf/P-1035.pdf"),
    "P1033": ("INGEMMET (2003). Memoria descriptiva de la revisión y actualización del cuadrángulo de Canta (23-j), cuadrante II.",
              "https://app.ingemmet.gob.pe/biblioteca/pdf/P-1033.pdf"),
    "BSGP110": ("Boletín de la Sociedad Geológica del Perú v. 110, p. 110–114 (2015): estratigrafía del Grupo Goyllarisquizga; Fm. Farrat (Stappenbeck, 1929).",
                "https://app.ingemmet.gob.pe/biblioteca/pdf/BSGP-110-110.pdf"),
    "CPG1847": ("INGEMMET – XVIII Congreso Peruano de Geología (2016). Arena silícea del Grupo Goyllarisquizga al norte de Chachapoyas (cantera Peña Blanca, ocurrencia Huilcabamba).",
                "https://app.ingemmet.gob.pe/biblioteca/pdf/CPG18-47.pdf"),
    "P1053": ("INGEMMET (2003). Memoria descriptiva de la revisión y actualización del cuadrángulo de Laramate (29-n).",
              "https://app.ingemmet.gob.pe/biblioteca/pdf/P-1053.pdf"),
    "P1050": ("INGEMMET (2003). Memoria descriptiva de la revisión y actualización del cuadrángulo de Córdova (28-m).",
              "https://app.ingemmet.gob.pe/biblioteca/pdf/P-1050.pdf"),
    "CPG15208": ("Valdivia, W. et al. – XV Congreso Peruano de Geología (2010). Nuevas unidades reconocidas en el cartografiado del cuadrángulo de Aramango (11-g-IV), Cuenca Santiago (INGEMMET).",
                 "https://app.ingemmet.gob.pe/biblioteca/pdf/CPG15-208.pdf"),
    "CPG16074": ("Valdivia, W.; Chacaltana, C.; Chumpitaz, M. & Peña, D. – XVI Congreso Peruano de Geología (2012). Cartografiado geológico del sector centro y sur de la Cuenca Santiago (INGEMMET).",
                 "https://app.ingemmet.gob.pe/biblioteca/pdf/CPG16-074.pdf"),
    "CLG1207": ("Pariguana, A. – Formación Shaypaya: una nueva secuencia del Cretáceo inferior en la faja subandina (cuencas Ucayali y Marañón).",
                "https://app.ingemmet.gob.pe/biblioteca/pdf/CLG12-07.pdf"),
    "CPG1810": ("XVIII Congreso Peruano de Geología (2016). Sedimentología de la Formación Vivian en el río Apurucayali (Ucayali).",
                "https://app.ingemmet.gob.pe/biblioteca/pdf/CPG18-10.pdf"),
    "ALVAN2025": ("Alvan, A.; Criales, A. & Bernuy, A. (2025). Petrografía y proveniencia de las areniscas del Grupo Morro Solar (Berriasiano sup.–Valanginiano) de Lima. Andean Geology 52(2): 280–305. doi:10.5027/andgeoV52n2-3722.",
                  "https://andeangeology.cl/index.php/revista1/article/view/V52n2-3722"),
    "BSGP110181": ("Boletín de la Sociedad Geológica del Perú v. 110, p. 181–185 (2015): estructuras del Grupo Morro Solar (Chorrillos, Lima).",
                   "https://app.ingemmet.gob.pe/biblioteca/pdf/BSGP-110-181.pdf"),
    "P1152": ("INGEMMET (2003). Memoria descriptiva de la revisión y actualización del cuadrángulo de Lunahuaná (26-k).",
              "https://app.ingemmet.gob.pe/biblioteca/pdf/P-1152.pdf"),
    "CARLOTTO": ("Carlotto, V.; Cárdenas, J.; Chávez, R. & Gil, W. Sedimentología de la Formación Huancané (Neocomiano) de la región de Cusco y su relación con las variaciones del nivel del mar.",
                 "https://app.ingemmet.gob.pe/biblioteca/pdf/Reg-2.pdf"),
    "CPG18161": ("INGEMMET – IRD – IMARPE, XVIII Congreso Peruano de Geología (2016). Transporte eólico de arenas en Paracas (Estación Eólica Experimental, proyecto MIXPALEO).",
                 "https://app.ingemmet.gob.pe/biblioteca/pdf/CPG18-161.pdf"),
    "GEOCATMIN": ("INGEMMET – GEOCATMIN: Geología integrada 1:50 000 (SERV_GEOLOGIA_50K_INTEGRADA, capa 7) y 1:100 000 (capa 6); índice de boletines SERV_BOLETINES. Copia local del 22/11/2026 y consulta del 23/11/2026.",
                  "https://geocatmin.ingemmet.gob.pe/geocatmin/"),
}

FICHAS = {
    "eolico": {
        "madurez": "Supermadura SOLO donde la carta y/o la petrografía la describen cuarzosa, bien seleccionada y blanca. Variable a escala regional.",
        "certeza": "Alta en las descripciones explícitas; BAJA donde no hay petrografía.",
        "definicion": "Unidad cartográfica cuaternaria (no formal en sentido estratigráfico): mantos de arena, dunas barjanas y pampas costeras modeladas por los vientos alisios del S–SSW.",
        "puntos": [
            ("Madurez textural", "Alta: el viento selecciona y redondea el grano (fino a medio, «bien seleccionado», «bien redondeado» en las descripciones de INGEMMET)."),
            ("Madurez composicional", "DEPENDE DE LA FUENTE. En la bahía de Paracas, las trampas eólicas de INGEMMET–IRD–IMARPE dieron 30–50 % de cuarzo, 35–50 % de feldespato, 5–20 % de micas y 0–5 % de carbonatos (CPG18161, p. 3): es una arena ARCÓSICA, no supermadura. En el cuadrángulo de Córdova (28-m) los depósitos eólicos se describen como «arenas cuarzo feldespáticas con micas y magnetita» (P1050, p. 8)."),
            ("Implicancia", "La palabra «cuarzosa» de la carta no basta: la madurez composicional se confirma con petrografía/DRX y química (Fe₂O₃, Al₂O₃ alto = feldespato). Los mantos que retrabajan areniscas cretácicas cuarzosas (p. ej., derivadas de Goyllarisquizga) tienden a ser más puros que los que retrabajan arenas de playa y rocas volcánicas."),
        ],
        "refs": ["CPG18161", "P1050", "GEOCATMIN"],
    },
    "marcavilca": {
        "madurez": "SUPERMADURA (cuarzoarenita) — evidencia cuantitativa.",
        "certeza": "Alta (conteo petrográfico publicado).",
        "definicion": "Grupo Morro Solar (Fernández-Concha, 1958), sobre el Grupo Puente Piedra y bajo la Fm. Pamplona (Rivera, 1951). Formaciones: Salto del Fraile, La Herradura y Marcavilca (miembros Morro Solar, Marcavilca y La Chira) (BSGP110181, p. 1 y 4). Edad Berriasiano superior–Valanginiano (ALVAN2025).",
        "puntos": [
            ("Petrografía (QFL)", "Conteo Gazzi-Dickinson del Miembro Marcavilca: Q = 92–96 %, F = 0 %, L = 4–7 % (muestras MO-55 a MO-58, Tabla 2). El feldespato es < 4 % en todo el grupo y prácticamente ausente en la Fm. Marcavilca (ALVAN2025, p. 12–13)."),
            ("Textura", "Cuarzo de grano fino a medio, subanguloso a subredondeado, con crecimiento sintaxial (cemento silíceo) y contactos largos: roca compacta → requiere trituración."),
            ("Afloramientos", "Morro Solar (Chorrillos), cerros de Lima sur y Lunahuaná (Punta de Asia, cerro Corral Omasino, Hualcará Grande, Quilmaná, cerro Isla; P1152, p. 5). En gran parte urbano o zona arqueológica/turística."),
        ],
        "refs": ["ALVAN2025", "BSGP110181", "P1152", "GEOCATMIN"],
    },
    "chimu": {
        "madurez": "SUPERMADURA (ortocuarcita / cuarzoarenita).",
        "certeza": "Alta.",
        "definicion": "Stappenbeck (1929) la describió como «cuarcitas del Wealdiano»; Benavides (1956) la designó Formación Chimú con localidad típica en Baños del Alto Chicama (La Libertad) (P1035, p. 8). Base del Grupo Goyllarisquizga; Valanginiano.",
        "puntos": [
            ("Litología", "Areniscas cuarzosas y ortocuarcitas blancas de grano fino a medio, en bancos gruesos, con intercalaciones de lutitas y mantos de carbón (descripciones de GEOCATMIN). Son SEDIMENTARIAS: «cuarcita» por el cemento silíceo, no por metamorfismo."),
            ("Procedencia", "Las areniscas del Grupo Goyllarisquizga son cuarzoarenitas de un orógeno reciclado rico en cuarzo (Sánchez et al., 2012, citado en CPG1847, p. 1)."),
            ("Implicancia", "Roca dura (trituración y molienda); vigilar intercalaciones de lutita/carbón y pátinas de óxido."),
        ],
        "refs": ["P1035", "CPG1847", "GEOCATMIN"],
    },
    "farrat": {
        "madurez": "SUPERMADURA.",
        "certeza": "Alta.",
        "definicion": "Nombrada por Stappenbeck (1929) para una secuencia de areniscas cuarzosas sobre las limolitas de la Fm. Carhuaz; techo del Grupo Goyllarisquizga; Barremiano superior–Aptiano; litoral-deltaica (BSGP110).",
        "puntos": [
            ("Litología", "Areniscas cuarzosas blancas de grano medio a grueso en capas gruesas; en la 1:100 000 aparece con areniscas y limolitas rojizas (descripciones de GEOCATMIN)."),
            ("Pureza documentada", "En el Grupo Goyllarisquizga de Chachapoyas (cantera Peña Blanca, ocurrencia Huilcabamba) INGEMMET reporta areniscas eólicas con > 95 % de cuarzo, poca o nula matriz, y muestras con > 97 % de SiO₂ y < 0,5 % de Fe₂O₃ (CPG1847, p. 1)."),
            ("Implicancia", "Menos compacta que Chimú en varios sectores (CPG1847 la señala favorable para vidrio, cerámica y fundente)."),
        ],
        "refs": ["BSGP110", "CPG1847", "P1033", "GEOCATMIN"],
    },
    "hualhuani": {
        "madurez": "SUPERMADURA (cuarzoarenita «madura» según INGEMMET).",
        "certeza": "Alta.",
        "definicion": "Techo del Grupo Yura (formaciones Cachíos, Labra y Hualhuani); Cretácico inferior (Berriasiano–Barremiano según GEOCATMIN: 145–121,4 Ma).",
        "puntos": [
            ("Litología", "«Areniscas cuarzosas maduras blancas con intercalaciones menores de limolitas pizarrosas» (P1053, p. 5, cuadrángulo de Laramate). En Córdova: «gruesa secuencia de cuarcitas blancas en estratos delgados» en la localidad de Callusca y Mina Minas (P1050, p. 9). GEOCATMIN la clasifica como «cuarciarenita»."),
            ("Espesor", "≈ 250–500 m según la sección (P1050, P1053)."),
            ("Implicancia", "Es la principal unidad supermadura del sur (Arequipa, Moquegua, Ayacucho, Ica); roca dura."),
        ],
        "refs": ["P1053", "P1050", "GEOCATMIN"],
    },
    "cushabatay": {
        "madurez": "SUPERMADURA (base fluvial algo conglomerádica; parte superior más pura).",
        "certeza": "Alta.",
        "definicion": "Base del Grupo Oriente (Kummel, 1946, sección del río Cushabatay ≈ 750 m; CLG1207). Parte inferior antes incluida en Cushabatay se separa hoy como Fm. Shaypaya (conglomerados y areniscas cíclicas; CLG1207).",
        "puntos": [
            ("Litología", "Base: bancos de 3–4 m de areniscas cuarzosas blanco-amarillentas de grano medio a grueso, en parte conglomerádicas, fluviales. Parte superior: areniscas cuarzosas blancas masivas con laminación oblicua e intercalaciones de lutitas, litorales (CPG15208, p. 3; CPG16074, p. 2)."),
            ("Implicancia", "Selva alta y faja subandina: cobertura vegetal, acceso y distancia son limitantes."),
        ],
        "refs": ["CPG15208", "CPG16074", "CLG1207", "GEOCATMIN"],
    },
    "vivian": {
        "madurez": "SUPERMADURA en su tramo basal («Vivian cuarcítico»); techo rojizo.",
        "certeza": "Alta (base) / media (techo con hierro).",
        "definicion": "Formación Vivian (Kummel, 1948); localidad tipo en la quebrada Vivian (Contamana), donde Morán y Fyfe (1933) la llamaron «areniscas azúcar» (CPG1810, p. 1). Campaniano (Jaillard, 1995), quizá desde el Santoniano.",
        "puntos": [
            ("Litología", "Areniscas cuarzosas de grano fino a medio, gris claro a blanco amarillento, con estratificación cruzada, fluvio-deltaicas; ≈ 100 m (CPG15208, p. 3; CPG1810)."),
            ("Implicancia", "Reservorio petrolero clásico; tramo superior rojizo (óxidos) → elegir la base."),
        ],
        "refs": ["CPG1810", "CPG15208", "GEOCATMIN"],
    },
    "huancane": {
        "madurez": "MADURA A SUPERMADURA (> 90 % de cuarzo).",
        "certeza": "Media–alta.",
        "definicion": "Definida por Newell (1949) en el Altiplano (Puno); Neocomiano; equivalente meridional del Grupo Goyllarisquizga (CARLOTTO).",
        "puntos": [
            ("Petrografía", "Areniscas blancas o rosadas con «más de 90 % de cuarzo, algunos feldespatos» y restos líticos; fluviales, con conglomerados y lutitas (CARLOTTO, p. 3)."),
            ("Implicancia", "Tramos rosados = hierro; seleccionar los bancos blancos."),
        ],
        "refs": ["CARLOTTO", "GEOCATMIN"],
    },
    "agua_caliente": {
        "madurez": "MADURA A SUPERMADURA.",
        "certeza": "Media.",
        "definicion": "Secuencia Agua Caliente (Morán y Fyfe, 1933); miembro de la Fm. Oriente según Kummel (1946); localidad típica en Agua Caliente, Contamana (Loreto). Cretácico inferior (Albiano).",
        "puntos": [
            ("Litología", "Areniscas cuarzosas blancas a cremas de grano fino a medio con lutitas y limolitas (CLG1207, columna del río Cushabatay; descripciones de GEOCATMIN)."),
        ],
        "refs": ["CLG1207", "GEOCATMIN"],
    },
}
ORDEN = ["eolico", "marcavilca", "chimu", "farrat", "hualhuani", "cushabatay", "vivian", "huancane", "agua_caliente"]

# ------------------------------------------------------------------ v2: evidencia leída en los boletines descargados
sys.path.insert(0, ESC)
from evidencia_boletines import AUTORES, NO_LEIDOS, CITAS, QUIMICA, ESPECIFICACIONES, OCURRENCIAS, FICHAS_NUEVAS, FICHA_META  # noqa: E402
from pyproj import Transformer  # noqa: E402
import math, re, unicodedata  # noqa: E402,E401
PAG_CITAS = json.load(open(os.path.join(ESC, "citas_paginas.json"), encoding="utf-8"))
LISTA = json.load(open(os.path.join(ESC, "lista_boletines.json"), encoding="utf-8"))
LINKS = {f"{b['num']}-A": b["link"] for b in LISTA["serieA"]}
LINKS.update({b["num"]: b["link"] for b in LISTA["serieB"]})


def _norm(s):
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\[[^\]]*\]", "", s))


def pag_cita(uid, cod, txt):
    return PAG_CITAS.get(f"{uid}|{cod}|{_norm(txt)[:40]}")


def ref_bol(cod, corto=False):
    a, anio, tit = AUTORES[cod]
    serie = "Serie A" if cod.endswith("A") else "Serie B"
    if corto:
        if "," not in a:
            quien = "INGEMMET" if a.startswith("INGEMMET") else a.split(" (")[0][:40]
        else:
            ap = [x.strip().split(",")[0] for x in re.split(r";| & ", a.split(" (")[0]) if x.strip()]
            quien = ap[0] if len(ap) == 1 else (f"{ap[0]} & {ap[1]}" if len(ap) == 2 else f"{ap[0]} et al.")
        return f"Bol. {cod} · {quien} ({anio or 's. f.'})"
    return f"{a} ({anio or 's. f.'}). {tit}. INGEMMET, Boletín {serie} N.° {cod.split('-')[0]}."


_TR = {z: Transformer.from_crs(f"EPSG:327{z}", "EPSG:4326", always_xy=True) for z in (17, 18, 19)}


def hav(la1, lo1, la2, lo2):
    r = math.radians
    a = math.sin(r(la2 - la1) / 2) ** 2 + math.cos(r(la1)) * math.cos(r(la2)) * math.sin(r(lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def grado(si, fe, al, aprox=False):
    if aprox:
        return "Fundente (SiO₂ > 90 %)"
    if si >= 95 and fe <= 0.10:
        return "Candidata a vidrio (con lavado y clasificación)"
    if si >= 95 and fe <= 0.5:
        return "Refractario / vidrio de color"
    if si >= 90 and fe <= 1.5:
        return "Fundente / ferrosilicio"
    return "No es sílice industrial"


# fichas actualizadas con lo leído en los boletines
FICHAS["eolico"]["madurez"] = ("Variable. El boletín 47-A separa mantos finos y claros «compuestos mayormente de cuarzo» de mantos gruesos "
                               "oscuros con ferromagnesianos; las arenas de playa llevan granos volcánicos.")
FICHAS["eolico"]["certeza"] = "Media: descripción textual de 7 boletines; sin análisis químico en la Serie B."
FICHAS["marcavilca"]["madurez"] = "Supermadura: Q 92–96 %, F 0 % (Alvan et al., 2025); «cuarcitas y areniscas cuarzosas gris blanquecinas» (44-A)."
FICHAS["marcavilca"]["certeza"] = "Alta (petrografía cuantitativa); sin química de canteras."
FICHAS["chimu"]["madurez"] = ("Supermadura confirmada por química: 6 canteras de la Fm. Chimú en Cajamarca con SiO₂ 92,3–98,3 % "
                             "y Fe₂O₃ 0,06–0,21 % (33-B); «ortocuarcita» (26-A), grano redondeado a subredondeado (17-A).")
FICHAS["chimu"]["certeza"] = "Muy alta: petrografía + química de laboratorio (INGEMMET)."
FICHAS["chimu"]["puntos"] = [(t, ("Doble comportamiento: en la sierra de Lima–Áncash es ortocuarcita recristalizada y dura (26-A), pero en Cajamarca "
                                  "las canteras explotan horizontes de «arenas silíceas… disgregables» de 8,5 a 25 m (33-B), que se extraen sin "
                                  "voladura y solo requieren lavado y clasificación. Priorizar los niveles disgregables.") if t == "Implicancia" else x)
                             for t, x in FICHAS["chimu"]["puntos"]]
FICHAS["hualhuani"]["puntos"] = [(t, ("Principal unidad cuarzosa del sur (Arequipa, Moquegua, Tacna, Puno, Apurímac), roca dura. Las canteras "
                                      "activas de Tacna y Puno la venden como fundente (SiO₂ 90–93 %) porque el hierro está en óxidos y vetillas "
                                      "de las fracturas (26-B): para vidrio habría que buscar bancos blancos sin fracturas oxidadas y lavar.") if t == "Implicancia" else x)
                                 for t, x in FICHAS["hualhuani"]["puntos"]]
FICHAS["farrat"]["madurez"] = ("Madura a supermadura, más variable: «ortocuarcitas blancas» (17-A); 4 canteras con SiO₂ 92,2–95,5 % y "
                              "Fe₂O₃ 0,13–1,02 % (33-B); óxidos en fracturas obligan a lavar (Lavasil 1).")
FICHAS["farrat"]["certeza"] = "Alta: petrografía + química."
FICHAS["hualhuani"]["madurez"] = ("Madura por textura («limpieza de sus elementos, selección, madurez», 46-A), pero las canteras de Tacna y "
                                 "Puno dan SiO₂ 90–93 % y Fe₂O₃ 0,5–1,1 % (óxidos en fracturas): hoy es sílice para fundente.")
FICHAS["hualhuani"]["certeza"] = "Alta: descripción + química (26-B, 30-B)."
FICHAS["huancane"]["madurez"] = "Heterogénea: «pueden variar de sublitarenitas a cuarzoarenitas» (74-A); con niveles arcósicos y muy feldespáticos (58-A)."
FICHAS["huancane"]["certeza"] = "Media: química solo de una ocurrencia (SiO₂ > 90 %)."
FICHAS["cushabatay"]["madurez"] = "Madura: «secuencia monótona de areniscas cuarzosas… granos subredondeados y ligeramente friables» (100-A)."
FICHAS["cushabatay"]["certeza"] = "Media: descripciones de 21 boletines; sin química."
FICHAS["vivian"]["madurez"] = ("Supermadura por petrografía: clasificada como «cuarzo-arenitas… deleznables con un aspecto sacaroide» (98-A); "
                              "«bien seleccionadas, friables, con poca matriz arcillosa» (94-A); granos «subredondeados a redondeados» de transporte eólico (32-B).")
FICHAS["vivian"]["certeza"] = "Alta en petrografía (24 boletines); sin química."
FICHAS["agua_caliente"]["madurez"] = ("Madura a supermadura por textura: «areniscas cuarzosas bien seleccionadas» (32-B); lámina delgada con abundante cuarzo "
                                      "subredondeado (92-A). Ojo: es la roca del yacimiento petrolífero de Agua Caliente (Ganso Azul, 98-A).")
FICHAS["agua_caliente"]["certeza"] = "Media: sin química."

UNI_QUIM = {"chimu": ("Formación Chimú", "Grupo Goyllarisquizga", "— (no indicada)"), "farrat": ("Formación Farrat",),
            "hualhuani": ("Formación Hualhuani", "Fm. Hualhuani"), "huancane": ("Formación Huancané",)}
COLOR_UNI = {"Formación Chimú": "#1f77b4", "Grupo Goyllarisquizga": "#7fb3e6", "Formación Farrat": "#2ca02c",
             "Formación Hualhuani": "#d98c1f", "Fm. Hualhuani": "#d98c1f", "Formación Huancané": "#9467bd", "— (no indicada)": "#8c8c8c"}


def filas_quimica():
    out = []
    for r in QUIMICA:
        bol, tabla, pag, nombre, lugar, hoja, zona, n, e_, uni, esp, desc, muestra, si, fe, al, nota = r
        lon, lat = _TR[zona].transform(e_, n)
        aprox = bol == "30-B"
        out.append({"bol": bol, "tabla": tabla, "pag": pag, "nombre": nombre, "lugar": lugar, "hoja": hoja, "utm": f"{zona}S {e_:,} E · {n:,} N".replace(",", " "),
                    "lat": lat, "lon": lon, "km": round(hav(FAB[0], FAB[1], lat, lon)), "unidad": uni, "esp": esp, "desc": desc,
                    "muestra": muestra, "si": si, "fe": fe, "al": al, "nota": nota, "aprox": aprox, "grado": grado(si, fe, al, aprox)})
    return out


ALFA = "abcdefghijklmnñopqrstuvxyz"

# ---- fotos de los boletines (recortadas de los PDF y revisadas una por una: fotos_final.json + fotos_final/)
import base64 as _b64  # noqa: E402
FOTOS = {}
for _x in json.load(open(os.path.join(ESC, "fotos_final.json"), encoding="utf-8")):
    FOTOS.setdefault(_x["unidad"], []).append(_x)
for _k in FOTOS:   # primero las láminas delgadas, luego canteras, luego afloramientos
    FOTOS[_k].sort(key=lambda x: (not x.get("micro"), x.get("origen") != "cantera", x["boletin"], x["pag"]))


def galeria(fotos, titulo):
    celdas = []
    for x in fotos:
        uri = "data:image/jpeg;base64," + _b64.b64encode(open(os.path.join(ESC, "fotos_final", x["archivo_img"]), "rb").read()).decode()
        pag = f"pág. {x['pag']}" + (f" (foto en la pág. {x['pag_foto']})" if x.get("pag_foto") and x["pag_foto"] != x["pag"] else "")
        nota = f" <i>{e(x['nota'])}</i>" if x.get("nota") else ""
        celdas.append(f"<td class='foto'><img src='{uri}'/><p class='cita'><i>«{e(x['leyenda'])}»</i><br/>"
                      f"<a href='{e(LINKS.get(x['boletin'], ''))}'>{e(ref_bol(x['boletin'], True))}</a>, {pag}.{nota}</p></td>")
    filas = ["<tr>" + "".join(celdas[i:i + 2]) + ("<td class='foto'></td>" if len(celdas[i:i + 2]) == 1 else "") + "</tr>"
             for i in range(0, len(celdas), 2)]
    return (f"<h3>{titulo}</h3><p class='cita'>Recortes de las fotos de los boletines con su leyenda tal como aparece en el PDF "
            "(texto leído por OCR: puede traer errores de letras). Primero las láminas delgadas, luego las canteras y después los afloramientos.</p>"
            f"<table class='galeria'>{''.join(filas)}</table>")


def celda(lat, lon, escala="25K"):
    """Código de cuadrícula igual a celdaEn() de frontend/src/geo.ts (100K: 27-k · 50K: 27k4 · 25K: 27k4-NE)."""
    fila = math.floor(-lat / 0.5) + 1
    col = math.floor((lon + 81.5) / 0.5)
    letra = ALFA[col] if 0 <= col < len(ALFA) else "?"
    norte, oeste = -(fila - 1) * 0.5, -81.5 + col * 0.5
    n50, e50 = lat >= norte - 0.25, lon >= oeste + 0.25
    cod50 = f"{fila}{letra}" + str({(True, True): 1, (False, True): 2, (False, False): 3, (True, False): 4}[(n50, e50)])
    if escala == "100K":
        return f"{fila}-{letra}"
    if escala == "50K":
        return cod50
    norte50 = norte if n50 else norte - 0.25
    oeste50 = oeste + 0.25 if e50 else oeste
    return f"{cod50}-" + ("N" if lat >= norte50 - 0.125 else "S") + ("E" if lon >= oeste50 + 0.125 else "O")


# boletín Serie A que cubre un punto (índice espacial SERV_BOLETINES, capa 1)
from shapely.geometry import Point as _Pt, Polygon as _Pg, MultiPolygon as _MPg  # noqa: E402
_BG = json.load(open(os.path.join(ESC, "boletines_geom.json"), encoding="utf-8"))
_BOLS = []
for _f in _BG["1"]:
    if _f.get("geometry"):
        _BOLS.append((_MPg([_Pg(r) for r in _f["geometry"]["rings"]]).buffer(0), _f["attributes"]))


def bol_en(lat, lon):
    p = _Pt(lon, lat)
    return [a for g_, a in _BOLS if g_.contains(p)][:2]


FICHAS.update(FICHAS_NUEVAS)
ORDEN_SED = ["eolico", "marcavilca", "salto_fraile", "chimu", "farrat", "goyllarisquizga", "oyon_chimu", "hualhuani", "labra",
             "huancane", "cushabatay", "agua_caliente", "oriente", "vivian", "naupe", "yauca"]
ORDEN_META = sorted([u["id"] for u in DATOS["unidades"] if u.get("tipo") == "meta" and u["filas"]],
                    key=lambda k: -next(u["area_total"] for u in DATOS["unidades"] if u["id"] == k))
for _k in ORDEN_META:
    FICHAS[_k] = dict(FICHA_META)
ORDEN = [k for k in ORDEN_SED if any(u["id"] == k and u["filas"] for u in DATOS["unidades"])] + ORDEN_META
UNI_QUIM["goyllarisquizga"] = ("Grupo Goyllarisquizga",)
UNI_QUIM["chimu"] = ("Formación Chimú", "— (no indicada)")
QF = filas_quimica()
json.dump({"fichas": FICHAS, "orden": ORDEN, "fuentes": FUENTES}, open(os.path.join(ESC, "fichas_final.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def fmt(v, fila, ox):
    if fila["aprox"]:
        return {"si": "> 90", "fe": ("< 1,5" if "Choquisani" in fila["nombre"] else "0,53–0,96"),
                "al": ("> 1,5" if "Choquisani" in fila["nombre"] else "1,00–1,78")}[ox]
    if "3 análisis" in fila["nombre"]:
        return {"si": "92,8–93,0", "fe": "0,70–1,07", "al": "2,78–2,88"}[ox]
    return f"{v:.2f}".replace(".", ",")


def tabla_quimica(filas, titulo):
    t = [f"<h3>{titulo}</h3><table><thead><tr><th>Cantera / ocurrencia</th><th>Distrito / provincia · hoja · cuadrícula 1:25 000</th><th>UTM WGS84 · lat, lon</th>"
         "<th>km fábrica</th><th>Unidad · espesor</th><th>SiO₂ %</th><th>Fe₂O₃ %</th><th>Al₂O₃ %</th><th>Uso posible (criterio de este informe)</th>"
         "<th>Fuente</th></tr></thead>"]
    for f in filas:
        fuente = f"Bol. {f['bol']}, {('tabla ' + str(f['tabla']) + ', ') if f['tabla'] else ''}pág. {f['pag']}" + (f" · muestra {f['muestra']}" if f['muestra'] not in ('—', '2 muestras') else "")
        t.append(f"<tr><td><b>{e(f['nombre'])}</b><br/><span class='cita'>{e(f['desc'])}{('. ' + e(f['nota'])) if f['nota'] else ''}</span></td>"
                 f"<td>{e(f['lugar'])} · {e(f['hoja'])} · <b>{e(celda(f['lat'], f['lon']))}</b></td><td>{e(f['utm'])}<br/>{f['lat']:.4f}, {f['lon']:.4f}</td><td class='n'>{f['km']}</td>"
                 f"<td>{e(f['unidad'])} · {e(f['esp'])}</td><td class='n'>{fmt(f['si'], f, 'si')}</td><td class='n'>{fmt(f['fe'], f, 'fe')}</td>"
                 f"<td class='n'>{fmt(f['al'], f, 'al')}</td><td>{e(f['grado'])}</td><td>{e(fuente)}</td></tr>")
    t.append("</table>")
    return "".join(t)


def grafico_quimica(ruta):
    fig, ax = plt.subplots(figsize=(6.4, 3.6), dpi=170)
    vistos = set()
    for f in QF:
        if f["aprox"] or "3 análisis" in f["nombre"]:
            continue
        c = COLOR_UNI.get(f["unidad"], "#8c8c8c")
        lab = f["unidad"] if f["unidad"] not in vistos else None
        vistos.add(f["unidad"])
        ax.scatter(f["fe"], f["si"], s=26, c=c, edgecolors="#1b2430", linewidths=0.4, label=lab, zorder=3)
    ax.axhline(95, color="#c0392b", lw=0.8, ls="--"); ax.text(0.042, 95.25, "SiO₂ 95 %", fontsize=6, color="#c0392b")
    ax.axvline(0.10, color="#1f3a5f", lw=0.8, ls=":"); ax.text(0.103, 61.5, "Fe₂O₃ 0,10 %", fontsize=6, color="#1f3a5f", rotation=90)
    ax.axvline(0.5, color="#1f3a5f", lw=0.8, ls=":"); ax.text(0.515, 61.5, "0,5 % (refractario)", fontsize=6, color="#1f3a5f", rotation=90)
    ax.set_xscale("log"); ax.set_xlim(0.04, 2.5); ax.set_ylim(60, 100)
    ax.set_xlabel("Fe₂O₃ (%) — escala logarítmica", fontsize=7); ax.set_ylabel("SiO₂ (%) en bruto", fontsize=7)
    ax.tick_params(labelsize=6); ax.grid(alpha=0.25, lw=0.4)
    ax.legend(fontsize=6, loc="lower left", frameon=False)
    fig.tight_layout(pad=0.3); fig.savefig(ruta); plt.close(fig)


def mapa_quimica(ruta):
    fig, ax = plt.subplots(figsize=(3.4, 4.2), dpi=170)
    for f in deps["features"]:
        for r in anillos(f["geometry"]):
            ax.add_patch(MplPoly(r, closed=True, fc="#f4f1ea", ec="#9aa3ad", lw=0.35))
    for f in QF:
        ax.scatter(f["lon"], f["lat"], s=14, c=COLOR_UNI.get(f["unidad"].split(" (")[0], "#d98c1f" if "Hualhuani" in f["unidad"] else "#8c8c8c"),
                   edgecolors="#1b2430", linewidths=0.3, zorder=3)
    ax.scatter([FAB[1]], [FAB[0]], marker="*", s=80, c="#1f3a5f", zorder=4)
    ax.annotate("Fábrica", (FAB[1], FAB[0]), xytext=(4, -9), textcoords="offset points", fontsize=6, color="#1f3a5f")
    for txt, (lo, la) in {"Cajamarca (33-B)": (-78.3, -7.0), "Puno (30-B)": (-70.6, -15.2), "Tacna (26-B)": (-70.4, -17.9)}.items():
        ax.annotate(txt, (lo, la), fontsize=6, color="#1b2430")
    ax.set_xlim(-81.5, -68.5); ax.set_ylim(-18.5, 0.2); ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    fig.tight_layout(pad=0.2); fig.savefig(ruta); plt.close(fig)


# ------------------------------------------------------------------ mapas
def anillos(geo):
    if not geo:
        return []
    t = geo["type"]
    if t == "Polygon":
        return [geo["coordinates"][0]]
    if t == "MultiPolygon":
        return [p[0] for p in geo["coordinates"]]
    if t == "GeometryCollection":
        return [a for g in geo["geometries"] for a in anillos(g)]
    return []


deps = json.load(open(os.path.join(BACK, "datos", "limites", "PER_ADM1.geojson"), encoding="utf-8"))


def mapa(u, ruta):
    fig, ax = plt.subplots(figsize=(4.6, 5.6), dpi=170)
    for f in deps["features"]:
        for r in anillos(f["geometry"]):
            ax.add_patch(MplPoly(r, closed=True, fc="#f4f1ea", ec="#9aa3ad", lw=0.35))
    for r in anillos(u["mapa"]):
        ax.add_patch(MplPoly(r, closed=True, fc="#c0392b", ec="#7b1e15", lw=0.4, alpha=0.9))
    # puntos de cuadrángulos (para que se vean los afloramientos pequeños)
    xs = [f["lon"] for f in u["filas"]]; ys = [f["lat"] for f in u["filas"]]
    ax.scatter(xs, ys, s=6, c="#7b1e15", zorder=3)
    ax.scatter([FAB[1]], [FAB[0]], marker="*", s=90, c="#1f3a5f", zorder=4)
    ax.annotate("Fábrica", (FAB[1], FAB[0]), xytext=(4, -10), textcoords="offset points", fontsize=6, color="#1f3a5f")
    ax.set_xlim(-81.5, -68.5); ax.set_ylim(-18.5, 0.2)
    ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color("#9aa3ad")
    fig.tight_layout(pad=0.2)
    fig.savefig(ruta); plt.close(fig)


# ------------------------------------------------------------------ HTML
CSS = """
@font-face { font-family: dv; src: url(DejaVuSans.ttf); }
@font-face { font-family: dv; font-weight: bold; src: url(DejaVuSans-Bold.ttf); }
body { font-family: dv; font-size: 9pt; color: #1b2430; }
h1 { font-size: 20pt; color: #1f3a5f; margin: 0 0 6pt 0; }
h2 { font-size: 14pt; color: #1f3a5f; border-bottom: 1.2pt solid #c08a4a; padding-bottom: 2pt; margin-top: 4pt; }
h3 { font-size: 11pt; color: #1f3a5f; margin: 10pt 0 3pt 0; }
p { margin: 0 0 5pt 0; text-align: justify; }
.sub { color: #5b6775; font-size: 9.5pt; }
.caja { background-color: #eef3f8; border: 0.6pt solid #b8c7d9; padding: 5pt; margin: 4pt 0 6pt 0; }
.alerta { background-color: #fdf2e3; border: 0.6pt solid #e2b878; padding: 5pt; margin: 4pt 0 6pt 0; }
table { border-collapse: collapse; width: 100%; margin: 3pt 0 6pt 0; }
th { background-color: #1f3a5f; color: #ffffff; font-size: 7pt; padding: 2pt; text-align: left; }
td { font-size: 6.8pt; padding: 1.6pt 2pt; border-bottom: 0.4pt solid #d0d7e2; vertical-align: top; }
td.n { text-align: right; }
.k { font-weight: bold; color: #1f3a5f; }
.cita { font-size: 7.5pt; color: #3b4652; }
a { color: #1f5fa8; }
"""

h = []
total_cuad = sum(len(u["filas"]) for u in DATOS["unidades"])
h.append(f"""
<h1>Arenas y areniscas supermaduras del Perú</h1>
<p class="sub">Versión 4: 51 boletines de INGEMMET, unidades sedimentarias y cuarcitas metamórficas, química de canteras, 88 fotos de los boletines y ubicación por cuadrícula 1:25 000 · Prospector RMI · {time.strftime('%d/%m/%Y')}</p>
<div class="caja"><p><span class="k">Objetivo.</span> Identificar y documentar las unidades geológicas del Perú cuyas arenas o areniscas son
<b>supermaduras</b> —compuestas casi solo por granos de cuarzo, bien seleccionados y redondeados, con muy poca matriz, feldespato,
fragmentos líticos y hierro— como fuente de sílice para vidrio, y reunir para cada una la información de las cartas geológicas de
INGEMMET por cuadrángulo.</p>
<p><span class="k">Alcance.</span> {len(DATOS['unidades'])} unidades · {total_cuad} cuadrángulos/hojas con afloramientos · regla de cartas: donde existe hoja
1:50 000 se usa SOLO la 1:50 000; la 1:100 000 únicamente donde no hay 1:50 000.</p></div>

<h2>1. Criterios y método</h2>
<p><span class="k">Madurez.</span> Se considera supermadura una arenisca cuarzoarenítica (Q &gt; 90–95 % en el diagrama QFL), de buena selección y
redondez, sin matriz arcillosa. Una «cuarcita» del Cretácico peruano (Chimú, Farrat, Hualhuani, Marcavilca) es en general una
<b>ortocuarcita</b>: arenisca cuarzosa sedimentaria cementada por sílice, no una roca metamórfica.</p>
<p><span class="k">Datos de cada cuadrángulo</span> (GEOCATMIN, capa 7 de la geología integrada 1:50 000): unidad, litología, descripción,
grosor, ambiente y medio sedimentario, composición mineral, edad (piso, serie y Ma), hoja (CODHOJA) y <b>REFERENCIA</b> (autores del mapa).
Para la 1:100 000 (capa 6) solo hay unidad, descripción y código. La ubicación administrativa se obtuvo de los límites oficiales
(geoBoundaries ADM1/ADM2) y las coordenadas corresponden al punto representativo del polígono más grande de la unidad en cada hoja
(geográficas WGS84 y UTM WGS84 sur). Las distancias a la fábrica (San Vicente de Cañete) son en línea recta.</p>
<p><span class="k">Cuadrícula 1:25 000 (versión 3).</span> Cada polígono se recortó con la grilla de la app (hoja 1:100 000 de 30′ →
cuadrante 1:50 000 de 15′ numerado 1 NE, 2 SE, 3 SO, 4 NO → cuadrícula 1:25 000 de 7′30″: NE, NO, SE, SO; p. ej. <b>27k4-NE</b>).
Para cada cuadrícula se da el área de la unidad dentro, el número de afloramientos (pedazos de polígono), el punto del pedazo
más grande y la distancia a la fábrica. Con ese código se abre la cuadrícula en la app. En el PDF se listan las 40 de más área
y todas las que están a 300 km o menos de la fábrica; la lista completa está en <b>cuadriculas_supermaduras_peru.xlsx</b>.</p>
<p><span class="k">Unidades (versión 3).</span> {len([k for k in ORDEN if not k.startswith('m_')])} sedimentarias (incluye los grupos sin dividir
Goyllarisquizga y Oriente, que en la v2 faltaban) y {len([k for k in ORDEN if k.startswith('m_')])} metamórficas con bancos de cuarcita.
De las metamórficas solo se cuentan los polígonos cuya descripción menciona cuarcita o roca cuarzosa; se descartaron las de solo pizarras
(Grupo San José, Fm. Ananea), los gneises, los conglomerados y la «Fm. Chicama» (lutitas).</p>
<p><span class="k">Bibliografía (versión 2).</span> Se leyeron <b>{len(AUTORES)} boletines completos de INGEMMET</b> descargados por el usuario
desde el repositorio institucional: {sum(c.endswith('A') for c in AUTORES)} de la Serie A (Carta Geológica Nacional) y
{sum(c.endswith('B') for c in AUTORES)} de la Serie B (Geología Económica: estudios regionales de rocas y minerales industriales).
Se eligieron para cubrir al menos el 60 % del área de cada unidad más el cuadrángulo más cercano a la fábrica. De cada uno se extrajeron
las secciones de las unidades, se seleccionaron frases técnicas (petrografía, redondez y selección, espesor, localidad tipo) y las tablas
químicas de sílice. Además se recortaron de los PDF <b>las fotos de afloramientos, canteras y láminas delgadas</b> de cada unidad
(88, revisadas una por una), con su leyenda original. <b>Cada cita es textual y se comprobó que está en la página indicada</b> (página del archivo PDF); las correcciones
de OCR van entre corchetes. También se usaron memorias descriptivas, artículos de congreso y artículos arbitrados de acceso abierto.</p>
<div class="alerta"><p><span class="k">Advertencia.</span> La madurez descrita en las cartas no reemplaza el análisis de laboratorio
(SiO₂, Fe₂O₃, Al₂O₃, TiO₂, granulometría, DRX). Los análisis químicos citados son de una muestra por cantera u ocurrencia
(representativa según INGEMMET). Las áreas son de afloramiento cartografiado, sin descontar concesiones, áreas protegidas ni cobertura.</p></div>

<!--SECCION_BOLETINES-->

<h2>3. Resumen</h2>
<table><thead><tr><th>Unidad</th><th>Madurez</th><th>Certeza</th><th>Área (km²)</th><th>Hojas</th><th>Cuadrículas 1:25 000</th><th>Cuadrícula más cercana a la fábrica</th></tr></thead>
""")
por_id = {u["id"]: u for u in DATOS["unidades"]}
for k in ORDEN:
    u = por_id.get(k)
    if not u:
        continue
    if k == ORDEN_META[0] if ORDEN_META else False:
        h.append("<tr><td colspan='7' style='background-color:#eef3f8'><b>Cuarcitas metamórficas</b></td></tr>")
    elif k == ORDEN[0]:
        h.append("<tr><td colspan='7' style='background-color:#eef3f8'><b>Sedimentarias y depósitos</b></td></tr>")
    fz = FICHAS[k]
    cerca = min(u["celdas25"], key=lambda c: c["km_fabrica"]) if u["celdas25"] else None
    h.append(f"<tr><td>{e(u['nombre'])}</td><td>{e(fz['madurez'])}</td><td>{e(fz['certeza'])}</td>"
             f"<td class='n'>{u['area_total']:,.0f}</td><td class='n'>{len(u['filas'])}</td><td class='n'>{len(u['celdas25'])}</td>"
             f"<td>{('<b>' + e(cerca['codigo']) + '</b> · ' + e(cerca['provincia']) + ', ' + e(cerca['departamento']) + ' · ' + str(cerca['km_fabrica']) + ' km') if cerca else '—'}</td></tr>")
h.append("</table>")
_vacias = [u["nombre"] for u in DATOS["unidades"] if not u["filas"]]
if _vacias:
    h.append("<p class='cita'>Sin afloramientos que cuenten con la regla de cartas (toda su área está en hojas con 1:50 000, donde la unidad tiene otro nombre): "
             + e("; ".join(_vacias)) + ".</p>")

# ---- sección 2: lo que agregan los boletines (química + especificaciones + hallazgos)
import base64  # noqa: E402
grafico_quimica(os.path.join(ARCH, "quimica.png"))
mapa_quimica(os.path.join(ARCH, "mapa_quimica.png"))
b64 = lambda p: "data:image/png;base64," + base64.b64encode(open(os.path.join(ARCH, p), "rb").read()).decode()  # noqa: E731
n_vid = sum(1 for f in QF if f["grado"].startswith("Candidata"))
s2 = [f"""<h2>2. Lo que agregan los boletines de INGEMMET</h2>
<div class='caja'>
<p><span class='k'>1. Hay química de laboratorio para Chimú y Farrat, y es buena.</span> En la región Cajamarca, INGEMMET (Bol. 33-B) analizó
22 canteras y ocurrencias de sílice: las de la <b>Formación Chimú</b> dan SiO₂ 92,3–98,3 % y <b>Fe₂O₃ 0,06–0,21 %</b>; en toda la región, {n_vid} muestras cumplen a la vez
SiO₂ ≥ 95 % y Fe₂O₃ ≤ 0,10 % (Hualqui, Huaca Corral y Carbonífera Chicama 31). Son arenas blancas y disgregables (no hay que moler roca dura) con espesores de 8,5 a 25 m.</p>
<p><span class='k'>2. La Formación Hualhuani se usa hoy como fundente, no para vidrio.</span> Las canteras de Pachía y Palca (Tacna) y Multicolor I (Puno)
dan SiO₂ 90–93 % y Fe₂O₃ 0,5–1,1 % por los óxidos de hierro de las fracturas; van a la fundición de Ilo (26-B, 30-B). Su textura sí es madura (46-A).</p>
<p><span class='k'>3. Las arenas eólicas no son todas iguales.</span> En Pisco–Ica (47-A) hay mantos gruesos oscuros con ferromagnesianos y mantos finos y claros
«compuestos mayormente de cuarzo»; las dunas de Guadalupe (margen derecha del río Ica) miden 63 km × 10 km y 100–150 m de grosor. Cerca de la
fábrica, el 44-A ubica barjanas al este del cerro La Bruja (Chilca) y en la pampa Clarita (sureste de Cañete). No hay química publicada.</p>
<p><span class='k'>4. Las unidades de la selva (Vivian, Agua Caliente, Cushabatay)</span> se describen como areniscas cuarzosas blancas, bien seleccionadas y friables,
con granos subredondeados a redondeados (indicadores de supermadurez), pero no tienen análisis químicos en los boletines leídos. El 98-A clasifica
a la <b>Fm. Vivian como «cuarzo-arenitas»</b> deleznables (160 m en la montaña del Sira); advierte también «abundantes concreciones de fierro» en el
Grupo Oriente y que la Fm. Agua Caliente es la roca del yacimiento petrolífero de Ganso Azul (Huánuco).</p>
<p><span class='k'>5. Huancané es heterogénea:</span> «pueden variar de sublitarenitas a cuarzoarenitas» (74-A), con niveles arcósicos (58-A).</p>
<p><span class='k'>6. El Grupo Goyllarisquizga sin dividir también produce sílice:</span> además de las 9 ocurrencias analizadas en Cajamarca, el 14-B registra
canteras activas de «arena silícea» en Curva Blanca (Chiquián, Áncash) y Agopunco (Yanahuanca, Pasco); el 76-A lo describe como «areniscas blancas friables de 500 m».</p>
<p><span class='k'>7. Las cuarcitas metamórficas son una opción débil:</span> la Fm. Sandía es una «gruesa secuencia de pizarras con algo de cuarcitas» (30-B), las cuarcitas
de Cerro Negro son «de color oscuro recristalizadas» (54-A) y las de Iscaybamba llevan muscovita y sericita (30-B). Ninguna tiene química publicada.</p>
</div>
<table class='sinborde'><tr><td style='width:62%; border:none'><img src='{b64("quimica.png")}' width='430'/>
<p class='cita'>SiO₂ frente a Fe₂O₃ de las canteras con análisis numérico (Bol. 33-B y 26-B). Arriba a la izquierda = más puro.</p></td>
<td style='border:none'><img src='{b64("mapa_quimica.png")}' width='220'/><p class='cita'>Ubicación de las canteras con análisis químico.</p></td></tr></table>
<h3>2.1 Especificaciones y datos de mercado citados por INGEMMET</h3><table><thead><tr><th>Uso</th><th>Especificación / dato</th><th>Fuente</th></tr></thead>"""]
for uso, txt, bol, pg in ESPECIFICACIONES:
    s2.append(f"<tr><td>{e(uso)}</td><td>{e(txt)}</td><td>{e(ref_bol(bol, True))}, pág. {pg}</td></tr>")
s2.append("</table><p class='cita'><b>Criterio de este informe</b> para la columna «Uso posible»: candidata a vidrio = SiO₂ ≥ 95 % y Fe₂O₃ ≤ 0,10 %; "
          "refractario / vidrio de color = SiO₂ ≥ 95 % y Fe₂O₃ ≤ 0,5 %; fundente / ferrosilicio = SiO₂ ≥ 90 % y Fe₂O₃ ≤ 1,5 %. "
          "Es un tamizado preliminar: el vidrio incoloro suele exigir Fe₂O₃ aún más bajo y una granulometría controlada. "
          "Se usa el SiO₂ <b>en bruto</b>; INGEMMET publica también el valor normalizado a 100 %, con el que Santa Rosa de Matara II "
          "(96,55 %; Fe₂O₃ 0,06 %) y Casa Blanca (96,85 %; Fe₂O₃ 0,07 %), ambas de la Fm. Chimú, también pasarían a «candidata a vidrio».</p>")
s2.append(tabla_quimica(sorted(QF, key=lambda f: (-f["si"] if not f["aprox"] else 0, f["fe"])), "2.2 Canteras y ocurrencias de sílice con análisis químico"))
s2.append("<h3>2.3 Otras canteras y ocurrencias de sílice registradas por INGEMMET (sin análisis químico)</h3><table><thead><tr>"
          "<th>Nombre</th><th>Distrito / provincia · hoja</th><th>Cuadrícula 1:25 000</th><th>UTM WGS84 · lat, lon</th><th>km fábrica</th>"
          "<th>Unidad y roca (según el boletín)</th><th>Estado</th><th>Fuente</th></tr></thead>")
for bol, pg, nom, lug, hoja, z, n_, e_, uni, est in sorted(OCURRENCIAS, key=lambda o: o[0]):
    lo_, la_ = _TR[z].transform(e_, n_)
    s2.append(f"<tr><td><b>{e(nom)}</b></td><td>{e(lug)} · {e(hoja)}</td><td><b>{e(celda(la_, lo_))}</b></td>"
              f"<td>{z}S {str(e_)[:-3]} {str(e_)[-3:]} E · {str(n_)[:-6]} {str(n_)[-6:-3]} {str(n_)[-3:]} N<br/>{la_:.4f}, {lo_:.4f}</td>"
              f"<td class='n'>{round(hav(FAB[0], FAB[1], la_, lo_))}</td>"
              f"<td>{e(uni)}</td><td>{e(est)}</td><td>{e(ref_bol(bol, True))}, pág. {pg}</td></tr>")
s2.append("</table><p class='cita'>El Arenal (Chancay) está registrada como depósito aluvial, no eólico. Las unidades de Santiago 1 y Santa Rosa "
          "(La Oroya) se transcriben tal como figuran en la tabla del boletín 14-B.</p>")
h[0] = h[0].replace("<!--SECCION_BOLETINES-->", "".join(s2))

sec = 4
for k in ORDEN:
    u = por_id.get(k)
    if not u:
        continue
    if ORDEN_META and k == ORDEN_META[0]:
        h.append(f"<h2>{sec}. Cuarcitas metamórficas</h2><div class='alerta'><p>{e(FICHA_META['madurez'])} {e(FICHA_META['puntos'][0][1])} "
                 "Se incluyen porque contienen bancos de cuarcita; su prioridad para vidrio es baja frente a Chimú, Farrat o Marcavilca. "
                 "Para Río Seco, Málaga, Ccatca, Puesto Figueroa e Iscaybamba no hay boletín descargado con descripción propia: se usa solo la carta.</p></div>")
        sec += 1
    fz = FICHAS[k]
    img = f"mapa_{k}.png"
    mapa(u, os.path.join(ARCH, img))
    h.append(f"<h2>{sec}. {e(u['nombre'])}</h2>")
    h.append(f"<div class='caja'><p><span class='k'>Madurez:</span> {e(fz['madurez'])} &nbsp; <span class='k'>Certeza:</span> {e(fz['certeza'])}</p>"
             f"<p><span class='k'>Definición y edad:</span> {e(fz['definicion'])}</p></div>")
    import base64
    uri = "data:image/png;base64," + base64.b64encode(open(os.path.join(ARCH, img), "rb").read()).decode()
    h.append(f"<table class='sinborde'><tr><td style='width:46%; border:none'><img src='{uri}' width='300'/>"
             f"<p class='cita'>Distribución cartografiada (rojo) y fábrica (estrella). {u['area_total']:,.0f} km² en {len(u['filas'])} hojas.</p></td><td style='border:none'>")
    for t, txt in fz["puntos"]:
        h.append(f"<p><span class='k'>{e(t)}.</span> {e(txt)}</p>")
    h.append("<p class='cita'><b>Fuentes:</b> " + "; ".join(f"[{r}]" for r in fz["refs"]) + "</p></td></tr></table>")

    # evidencia textual de los boletines descargados
    h.append(f"<h3>{sec}.1 Lo que dicen los boletines de INGEMMET (citas textuales)</h3><table><thead><tr><th>Boletín y autores</th>"
             "<th>Pág.</th><th>Tema</th><th>Cita</th></tr></thead>")
    for cod, txt, tema in CITAS.get(k, []):
        pg = pag_cita(k, cod, txt)
        h.append(f"<tr><td style='width:24%'><a href='{e(LINKS.get(cod, ''))}'>{e(ref_bol(cod, True))}</a></td><td class='n'>{pg or '—'}</td>"
                 f"<td style='width:17%'>{e(tema)}</td><td><i>«{e(txt)}»</i></td></tr>")
    h.append("</table>")
    qf = [f for f in QF if any(f["unidad"].startswith(x) for x in UNI_QUIM.get(k, ()))]
    if k == "farrat":
        qf = [f for f in qf if f["unidad"].startswith("Formación Farrat")]
    if qf:
        tit = {"chimu": "Formación Chimú y canteras de Cajamarca sin unidad indicada"}.get(k, u["nombre"])
        h.append(tabla_quimica(sorted(qf, key=lambda f: (-f["si"] if not f["aprox"] else 0)), f"{sec}.2 Química de canteras — {tit}"))
    sub = 3 if qf else 2
    fts = FOTOS.get(k, [])
    if fts:
        h.append(galeria(fts, f"{sec}.{sub} Fotos de los boletines ({len(fts)})"))
        sub += 1

    # descripciones textuales de las cartas (las de más área)
    vistas, descs = set(), []
    for f in u["filas"]:
        for d in f["descripciones"]:
            if d not in vistas:
                vistas.add(d); descs.append((d, f["hoja"], f["escala"], f["referencia"]))
    h.append(f"<h3>{sec}.{sub} Descripciones de las cartas geológicas (textuales, GEOCATMIN)</h3><table><thead><tr><th>Hoja</th><th>Carta</th><th>Descripción</th><th>Referencia (autores del mapa)</th></tr></thead>")
    for d, hoja, esc, ref in descs[:14]:
        h.append(f"<tr><td>{e(hoja)}</td><td>{e(esc)}</td><td>{e(d)}</td><td>{e(', '.join(ref)) or '—'}</td></tr>")
    h.append("</table>")

    # tabla por cuadrángulo
    TOPE50 = 60
    h.append(f"<h3>{sec}.{sub + 1} Ubicaciones por cuadrante 1:50 000 (u hoja 1:100 000 donde no hay 1:50 000)</h3>"
             + (f"<p class='cita'>Se muestran los {TOPE50} de más área de {len(u['filas'])}; el resto está en el Excel.</p>" if len(u["filas"]) > TOPE50 else "")
             + "<table><thead><tr><th>Cuadrante</th><th>Carta</th><th>Área km²</th><th>Pol.</th><th>Departamento / provincia</th>"
             "<th>Punto representativo (lat, lon · UTM WGS84)</th><th>km fábrica</th><th>Edad · ambiente · grosor</th>"
             "<th>Referencia del mapa</th><th>Boletín Serie A</th></tr></thead>")
    for f in u["filas"][:TOPE50]:
        def _b(a):
            cod = f"{a.get('NUMERO_BOL')}-A"
            if cod in AUTORES:
                return f"<a href='{e(a.get('LINK') or '')}'>{e(ref_bol(cod, True))}</a> ✓ leído"
            return f"N° {a.get('NUMERO_BOL')}: <a href='{e(a.get('LINK') or '')}'>{e(str(a.get('TITULO') or '')[:80])}</a>"
        bol = "; ".join(_b(a) for a in bol_en(f["lat"], f["lon"])) or "—"
        edad = f["edad"]
        if "Pleistoceno" in edad or "Holoceno" in edad:
            edad = "Cuaternario"
        amb = [v for v in f["ambiente"] + f["medio"] if not v.strip().isdigit()]
        extra = " · ".join(x for x in (edad, ", ".join(amb), ", ".join(f["grosor"])) if x) or "—"
        h.append(f"<tr><td>{e(f['hoja'])}</td><td>{e(f['escala'])}</td><td class='n'>{f['area_km2']:,.1f}</td><td class='n'>{f['poligonos']}</td>"
                 f"<td>{e(f['departamento'])} / {e(f['provincia'])}</td><td>{f['lat']:.4f}, {f['lon']:.4f}<br/>{e(f['utm'])}</td>"
                 f"<td class='n'>{f['km_fabrica']}</td><td>{e(extra)}</td><td>{e(', '.join(f['referencia'])) or '—'}</td><td>{bol}</td></tr>")
    h.append("</table>")

    # cuadrículas 1:25 000 (código de la app)
    cs = u["celdas25"]
    elegidas = {c["codigo"] for c in cs[:40]} | {c["codigo"] for c in cs if c["km_fabrica"] <= 300}
    lista = [c for c in cs if c["codigo"] in elegidas]
    h.append(f"<h3>{sec}.{sub + 2} Cuadrículas 1:25 000 para abrir en la app</h3>"
             f"<p class='cita'>{len(cs)} cuadrículas con la unidad; se listan {len(lista)} (las 40 de más área y todas a 300 km o menos de la fábrica). "
             "«Afl.» = número de afloramientos (pedazos de polígono) dentro de la cuadrícula.</p>"
             "<table><thead><tr><th>Cuadrícula</th><th>km² de la unidad</th><th>Afl.</th><th>Carta</th><th>Departamento / provincia</th>"
             "<th>Punto del afloramiento mayor (lat, lon)</th><th>km fábrica</th></tr></thead>")
    for c in lista:
        h.append(f"<tr><td><b>{e(c['codigo'])}</b></td><td class='n'>{c['km2']:,.2f}</td><td class='n'>{c['pols']}</td><td>{e(c['carta'])}</td>"
                 f"<td>{e(c['departamento'])} / {e(c['provincia'])}</td><td>{c['lat']:.4f}, {c['lon']:.4f}</td><td class='n'>{c['km_fabrica']}</td></tr>")
    h.append("</table>")
    sec += 1

h.append(f"<h2>{sec}. Boletines de INGEMMET leídos</h2><table><thead><tr><th>Boletín</th><th>Autores (año)</th><th>Título</th><th>Enlace</th></tr></thead>")
for cod in sorted(AUTORES, key=lambda c: (c[-1], int(c.split("-")[0]))):
    a, anio, tit = AUTORES[cod]
    h.append(f"<tr><td>{e(cod)}</td><td>{e(a)} ({anio or 's. f.'})</td><td>{e(tit)}</td><td><a href='{e(LINKS.get(cod, ''))}'>{e(LINKS.get(cod, ''))}</a></td></tr>")
for cod, motivo in NO_LEIDOS.items():
    h.append(f"<tr><td>{e(cod)}</td><td colspan='2'><i>No leído: {e(motivo)}</i></td><td><a href='{e(LINKS.get(cod, ''))}'>{e(LINKS.get(cod, ''))}</a></td></tr>")
h.append("</table><p class='cita'>«s. f.»: el año y los autores están en la portada escaneada del PDF y no se leen en el texto. "
         "Las páginas citadas en el informe son las del archivo PDF (pueden diferir en ±5 de la numeración impresa).</p>")
sec += 1
h.append(f"<h2>{sec}. Fuentes</h2>")
for k, (t, url) in FUENTES.items():
    h.append(f"<p class='cita'><b>[{k}]</b> {e(t)} <a href='{e(url)}'>{e(url)}</a></p>")
h.append("<p class='cita'>Los boletines de la Serie A (Carta Geológica Nacional) se citan con el número y enlace del índice SERV_BOLETINES de "
         "GEOCATMIN; su texto completo se consulta en el repositorio institucional de INGEMMET.</p>")

CSS2 = CSS.replace("@font-face { font-family: dv; src: url(DejaVuSans.ttf); }", "").replace(
    "@font-face { font-family: dv; font-weight: bold; src: url(DejaVuSans-Bold.ttf); }", "").replace("font-family: dv;", "font-family: 'Segoe UI', Arial, sans-serif;")
CSS2 += """
.galeria td.foto { width: 50%; border: none; padding: 4pt; vertical-align: top; page-break-inside: avoid; }
.galeria img { width: 100%; max-height: 230pt; object-fit: contain; border: 0.5pt solid #d0d7e2; }
.galeria tr { page-break-inside: avoid; }
@page { size: A4; margin: 16mm 13mm 16mm 13mm; }
thead { display: table-header-group; }
tr { page-break-inside: avoid; }
h2 { page-break-after: avoid; }
h3 { page-break-after: avoid; }
.sinborde td { border: none; }
"""
documento = f"<!doctype html><html lang='es'><head><meta charset='utf-8'><title>Arenas y areniscas supermaduras del Perú (v4)</title><style>{CSS2}</style></head><body>{''.join(h)}</body></html>"
open(os.path.join(ESC, "informe_supermaduras.html"), "w", encoding="utf-8").write(documento)
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    nav = pw.chromium.launch(channel="msedge", headless=True)
    pg = nav.new_page()
    pg.set_content(documento, wait_until="load")
    pg.pdf(path=SALIDA, format="A4", print_background=True, display_header_footer=True,
           header_template="<div style='font-size:7px;color:#5b6775;width:100%;padding:0 13mm'>Arenas y areniscas supermaduras del Perú · Prospector RMI</div>",
           footer_template="<div style='font-size:7px;color:#5b6775;width:100%;text-align:right;padding:0 13mm'>Página <span class='pageNumber'></span> de <span class='totalPages'></span></div>",
           margin={"top": "16mm", "bottom": "16mm", "left": "13mm", "right": "13mm"})
    nav.close()
print("páginas:", len(fitz.open(SALIDA)))
