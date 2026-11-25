"""v3: citas de las unidades nuevas y de las cuarcitas metamórficas; ocurrencias de sílice sin química; fichas nuevas."""

CITAS_V3 = {
    "goyllarisquizga": [
        ("76-A", "El Grupo Goyllarisquizga consiste de areniscas blancas friables de 500 m, con miembros de estratificación cruzada de 2 m de grosor", "Litología y espesor (Huaraz–La Unión)"),
        ("76-A", "En el sector oriental sobre el Bloque del Marañón se encuentra una secuencia de areniscas blancas friables de grano medio a grueso, en parte algo conglomerádicas con intercalaciones muy delgadas de limoarcillitas grises.", "Areniscas friables"),
        ("33-B", "consiste en cuarcitas blancas masivas y areniscas generalmente de grano medio y color blanquecino, en la parte inferior, con intercalaciones delgadas de lutitas marrones y grises en la parte superior, su grosor oscila entre los 200 y 500 m", "Cajamarca"),
        ("56-A", "ARENISCAS CUARZOSAS DE GRANO MEDIO COLOR AMARILLENTO MACIZO HACIA LA BASE ESTRATIFICACION SESGADA", "Columna (Bagua–Chachapoyas)"),
        ("14-B", "Curva Blanca Ancash Chiquián 21-i 8 879 479 264 961 Arena silícea Sedimentario Cuarcitas Gpo. Goyllarisquizga", "Cantera activa de arena silícea (Chiquián)"),
    ],
    "oriente": [
        ("115-A", "Descrita como Formación Oriente por KUMMEL, B. (1946) quien las describe como una secuencia de areniscas cuarzosas del oriente peruano", "Definición"),
        ("115-A", "Litológicamente, la base consiste de areniscas cuarzosas blancas de grano grueso en estratos gruesos, con estratificación cruzada", "Litología"),
        ("14-B", "conformada por areniscas cuarzosas blanquecinas de grano fino a medio con estratificación sesgada", "Litología"),
    ],
    "labra": [
        ("22-B", "Conformado por areniscas, areniscas cuarciticas y cuarcitas, interestratificadas con menores proporciones de lutitas y escasa participación de margas y calizas. Las areniscas son de color gris claro a parduzco, de grano fino a medio, con óxidos de hierro.", "Litología (Arequipa)"),
        ("22-B", "La potencia medida en la sección típica, a lo largo de la quebrada Cachios y en la falda del cerro Labra es de 807 m", "Espesor y localidad tipo"),
        ("26-B", "Se trata de areniscas silicificadas de color marrón grisáceo, de grano grueso, con un alto grado de compactación, pertenecientes a la Formación Labra del Grupo Yura.", "Cantera Oxana (Candarave, Tacna)"),
        ("26-B", "Años atrás la cantera se explotó para la producción de sílice.", "Uso histórico"),
    ],
    "oyon_chimu": [
        ("14-B", "Está constituida por una intercalación de estratos de cuarcitas y limoarenitas negras con intercalaciones de carbón.", "Fm. Oyón: cuarcitas con carbón"),
        ("26-A", "Wilson (1963) le dió el nombre y, basado en los fósiles hallados, consideró como una posibilidad el que pertenezca al Valanginiano", "Definición de la Fm. Oyón"),
    ],
    "m_sandia": [
        ("30-B", "Durante los trabajos de campo se ha observado que la gruesa secuencia de pizarras con algo de cuarcitas, se diferencia de su parte superior dado su litología más fina y grosores considerables (metalutitas)", "Litología: pizarras con algo de cuarcitas"),
        ("30-B", "Cruz y Carpio (1996) estiman un grosor de mas de 4000 m en Sandia y San Ignacio.", "Espesor"),
        ("11-B", "El ambiente geológico del área se encuentra conformado por cuarcitas y pizarras de la Formación Sandía.", "Sandía (Puno)"),
    ],
    "m_cerro_negro": [
        ("54-A", "Con este nombre Martínez M. (1970), reconoce una secuencia epimetamórfica", "Definición"),
        ("54-A", "siendo las cuarcitas de grano fino de color oscuro recristalizadas y en partes con cierto bandeamiento.", "Cuarcitas oscuras"),
        ("54-A", "Se estima que el grosor de la secuencia puede pasar de los 3,000 m.", "Espesor"),
    ],
    "m_excelsior": [
        ("14-B", "Consta de pizarras y filitas con intercalación de areniscas finas; en la hoja de Cerro de Paseo se observan pizarras y filitas intercaladas con cuarcitas de grano fino", "Litología"),
    ],
    "m_contaya": [
        ("101-A", "para estas rocas consistentes de pizarras, es decir, limoarcillitas esquistosas de color gris, bien laminadas.", "Definición (Fyfe)"),
        ("101-A", "NEWELL y TAFUR, estimaron que la Formación Contaya tiene 150m de espesor, encontrándose yacente sobre una sólida cuarcita, de espesor y edad desconocidos", "Cuarcita basal"),
    ],
    "m_chagrapi": [
        ("58-A", "en aparente discordancia angular se encuentra una secuencia monótona y persistente de lutitas grisáceas claras", "Litología: lutitas"),
    ],
    "m_iscaybamba": [
        ("30-B", "El núcleo está conformado por gneis, sobreyacidos por anfibolitas foliada, y luego cuarcitas y micaesquistos que excedan los 1500 m de potencia.", "Estructura"),
        ("30-B", "En las cuarcitas se observa esquistosidad de flujo con contenido de muscovita y sericita.", "Mineralogía: micas"),
    ],
}

# Ocurrencias de sílice registradas SIN análisis químico: (boletín, pág., nombre, lugar, hoja, zona, N, E, unidad registrada, estado)
OCURRENCIAS = [
    ("14-B", 197, "Curva Blanca", "Chiquián / Áncash", "21-i", 18, 8879479, 264961, "Grupo Goyllarisquizga (Ki-ch: Chimú) – cuarcitas", "Activa"),
    ("14-B", 197, "Agopunco", "Yanahuanca / Pasco", "21-j", 18, 8845308, 334968, "Grupo Goyllarisquizga – arenisca cuarzosa", "Activa"),
    ("14-B", 200, "El Arenal", "Chancay / Lima", "24-i", 18, 8721864, 263475, "Cuaternario aluvial", "Inactiva"),
    ("14-B", 201, "Santiago 1", "La Oroya / Junín", "24-l", 18, 8696782, 440267, "Fm. Jumasha según la tabla (arenisca y caliza)", "Activa"),
    ("14-B", 201, "Santa Rosa", "La Oroya / Junín", "24-l", 18, 8692006, 432244, "Fm. Chúlec según la tabla", "Activa"),
    ("14-B", 199, "Perdiz Machay", "Tarma / Junín", "23-l", 18, 8753254, 404134, "Grupo Pucará (caliza y arena silícea)", "Inactiva"),
    ("33-B", 258, "Cerro Campana", "San Ignacio / Cajamarca", "11-e", 17, 9432954, 720546, "Grupo Goyllarisquizga – arenisca cuarzosa blanca deleznable, 3 m", "Artesanal"),
    ("33-B", 267, "San Felipe", "Cutervo / Cajamarca", "13-f", 17, 9289505, 744804, "Grupo Goyllarisquizga – arena silícea blanco grisácea, 4 m", "Artesanal"),
    ("26-B", 110, "Oxana", "Quilahuani, Candarave / Tacna", "35-v", 19, 8085834, 369539, "Fm. Labra – areniscas silicificadas, 800 × 500 m", "Paralizada (antes producía sílice)"),
    ("26-B", 114, "Tres de Mayo", "Palca / Tacna", "36-x", 19, 8035532, 405551, "Fm. Hualhuani – cuarcitas; SiO₂ > 95 % según el texto", "Activa (fundición de Ilo)"),
    ("22-B", 165, "River Campeón 15", "Yura / Arequipa", "33-s", 19, 8204834, 208441, "Fm. Labra – areniscas", "Registrada"),
    ("22-B", 165, "Elita I", "Yura / Arequipa", "33-s", 19, 8208401, 210925, "Fm. Labra – areniscas", "Registrada"),
    ("22-B", 165, "Chavalillo", "Huanca / Arequipa", "33-s", 18, 8219500, 832428, "Fm. Labra – areniscas", "Registrada"),
]

FICHAS_NUEVAS = {
    "goyllarisquizga": {"madurez": "Madura a supermadura: mismo paquete que Chimú + Farrat donde no se separaron; «areniscas blancas friables» (76-A).",
                        "certeza": "Alta: 9 canteras con química en Cajamarca (Utco 98,6 % SiO₂; Sumiate 96,9 %).",
                        "definicion": "Grupo del Cretácico inferior que, sin dividir, incluye Oyón, Chimú, Santa, Carhuaz y Farrat.",
                        "puntos": [("Ojo", "Sin dividir incluye también las calizas de Santa y las lutitas de Carhuaz: en cada cuadrícula hay que ubicar los bancos de arenisca blanca.")],
                        "refs": ["GEOCATMIN"]},
    "oriente": {"madurez": "Madura a supermadura (como Cushabatay y Agua Caliente): areniscas cuarzosas blancas con estratificación cruzada.",
                "certeza": "Media: sin química.",
                "definicion": "Kummel (1946); Cretácico inferior de la faja subandina y la llanura amazónica (Cushabatay, Esperanza, Agua Caliente).",
                "puntos": [("Ojo", "Incluye la Fm. Esperanza (lutitas y calizas): los niveles útiles son la base (Cushabatay) y el tope (Agua Caliente).")],
                "refs": ["GEOCATMIN"]},
    "labra": {"madurez": "Madura, no supermadura: areniscas cuarcíticas gris claras a parduzcas «con óxidos de hierro» (22-B).",
              "certeza": "Media: sin química publicada.",
              "definicion": "Grupo Yura, Jurásico superior; 807 m en la sección típica (quebrada Cachios y cerro Labra, Arequipa).",
              "puntos": [("Uso", "La cantera Oxana (Tacna) produjo sílice; en Yura (Arequipa) hay concesiones de sílice registradas en la Fm. Labra.")],
              "refs": ["GEOCATMIN"]},
    "oyon_chimu": {"madurez": "Mezcla: Oyón son cuarcitas con limoarenitas negras y carbón; Chimú es la ortocuarcita supermadura.",
                   "certeza": "Media.", "definicion": "Unidad de la carta 1:100 000 que junta las formaciones Oyón (Wilson, 1963) y Chimú.",
                   "puntos": [("Ojo", "Buscar los bancos de Chimú; los de Oyón traen carbón y lutitas negras.")], "refs": ["GEOCATMIN"]},
    "salto_fraile": {"madurez": "Madura: «areniscas cuarzosas gris verdosas con intercalaciones de areniscas arcillosas y limolitas» (14-B, Grupo Morro Solar).",
                     "certeza": "Baja: sin química y con una sola descripción.",
                     "definicion": "Base del Grupo Morro Solar (Lima), Berriasiano; localidad tipo en el Morro Solar de Chorrillos.",
                     "puntos": [("Cercanía", "Aflora junto a Marcavilca, en Lima, cerca de la fábrica.")], "refs": ["ALVAN2025", "GEOCATMIN"]},
    "naupe": {"madurez": "Supermadura según la tabla de madurez, con certeza baja (pocas descripciones).", "certeza": "Baja: sin boletín descargado.",
              "definicion": "Unidad cenozoica de la costa norte.", "puntos": [], "refs": ["GEOCATMIN"]},
    "yauca": {"madurez": "Supermadura según la tabla de madurez, con certeza baja.", "certeza": "Baja: sin boletín descargado.",
              "definicion": "Unidad de la costa sur.", "puntos": [], "refs": ["GEOCATMIN"]},
}
FICHA_META = {"madurez": "Metacuarcitas: el metamorfismo recristaliza el cuarzo, pero son sobre todo pizarras y filitas con bancos de cuarcita.",
              "certeza": "Media a baja: descripciones generales; sin química.",
              "definicion": "Rocas metamórficas paleozoicas (Ordovícico–Devónico) o más antiguas.",
              "puntos": [("Limitación", "Las cuarcitas suelen ser oscuras (grafito, pirita) y con micas (muscovita, sericita): hierro y alúmina las alejan del vidrio. Sirven mejor como fundente o ferrosilicio si el banco es potente.")],
              "refs": ["GEOCATMIN"]}
