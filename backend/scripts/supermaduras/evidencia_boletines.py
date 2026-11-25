"""Evidencia curada de los boletines INGEMMET descargados (Serie A y B): autores, citas textuales y química de canteras.
Todas las citas y valores fueron leídos de los PDF de prospector-rmi/boletines (23/11/2026). Las páginas son del PDF."""

AUTORES = {
    "14-A": ("Marocco, R. & del Pino, M.", 1966, "Geología del cuadrángulo de Ichuña (33-u)"),
    "17-A": ("Cossío, A. & Jaén, H.", 1967, "Geología de los cuadrángulos de Puémape, Chocope, Otuzco, Trujillo, Salaverry y Santa"),
    "26-A": ("Cobbing, J.", 1973, "Geología de los cuadrángulos de Barranca, Ámbar, Oyón, Huacho, Huaral y Canta"),
    "27-A": ("Marocco, R.", 1975, "Geología de los cuadrángulos de Andahuaylas, Abancay y Cotabambas"),
    "31-A": ("Reyes, L.", 1980, "Geología de los cuadrángulos de Cajamarca, San Marcos y Cajabamba"),
    "35-A": ("Pecho, V.", 1981, "Geología de los cuadrángulos de Chalhuanca, Antabamba y Santo Tomás"),
    "38-A": ("Wilson, J.", 1984, "Geología de los cuadrángulos de Jayanca, Incahuasi, Cutervo, Chiclayo, Chongoyape, Chota, Celendín, Pacasmayo y Chepén"),
    "42-A": ("Palacios, O.; De La Cruz, J.; De La Cruz, N.; Klinck, B.; Allison, R. & Hawkins, M.", 1993, "Geología de la Cordillera Occidental y Altiplano al oeste del lago Titicaca – sur del Perú"),
    "44-A": ("Salazar, H. & Landa, C.", 1993, "Geología de los cuadrángulos de Mala, Lunahuaná, Tupe, Conayca, Chincha, Tantará y Castrovirreyna"),
    "46-A": ("INGEMMET (autores en portada escaneada)", None, "Geología de los cuadrángulos de Huambo y Orcopampa"),
    "47-A": ("Fernández Dávila, M.", 1993, "Geología de los cuadrángulos de Pisco, Guadalupe, Punta Grande, Ica y Córdova"),
    "51-A": ("Palacios, O.", 1994, "Geología de los cuadrángulos de Chulca y Cayarani"),
    "54-A": ("Palacios, O.", 1994, "Geología de los cuadrángulos de Paita, Piura, Talara, Sullana, Lobitos, Quebrada Seca, Zorritos, Tumbes y Zarumilla"),
    "56-A": ("Sánchez, A.", 1995, "Geología de los cuadrángulos de Bagua Grande, Jumbilla, Lonya Grande, Chachapoyas, Rioja, Leimebamba y Bolívar"),
    "58-A": ("De la Cruz, N.", 1995, "Geología de los cuadrángulos de Velille, Yauri, Ayaviri y Azángaro"),
    "59-A": ("Sánchez, A.; Molina, O. & Gutiérrez, R.", 1995, "Geología de los cuadrángulos de Chimbote, Casma y Culebras"),
    "60-A": ("Wilson, J.; Reyes, L. & Garayar, J. (actualizado por INGEMMET, 1995)", 1967, "Geología de los cuadrángulos de Pallasca, Tayabamba, Corongo, Pomabamba, Carhuaz y Huari"),
    "69-A": ("Mégard, F.; Caldas, J.; Paredes, J. & De La Cruz, N.", 1996, "Geología de los cuadrángulos de Tarma, La Oroya y Yauyos"),
    "70-A": ("Asociación LAGESA – C.F.G.S.", 1996, "Geología de los cuadrángulos de Huancapi, Chincheros, Querobamba y Chaviña"),
    "74-A": ("López, J. C.", 1996, "Geología del cuadrángulo de Nuñoa"),
    "76-A": ("Cobbing, J.; Sánchez, A.; Martínez, W. & Zárate, H.", 1996, "Geología de los cuadrángulos de Huaraz, Recuay, La Unión, Chiquián y Yanahuanca"),
    "78-A": ("Monge, R.; León, W. & Chacón, N.", 1996, "Geología de los cuadrángulos de Chuchurras, Ulcumayo, Oxapampa y La Merced"),
    "81-A": ("Palacios, O.; Molina, O.; Galloso, A. & Reyna, C.", 1996, "Geología de los cuadrángulos de Puerto Luz, Colorado, Laberinto, Puerto Maldonado…"),
    "83-A": ("Marocco, R.; Lipa, V. & Quispe, L.", 1996, "Geología del cuadrángulo de San Miguel"),
    "85-A": ("S&Z Consultores Asociados", 1997, "Geología de los cuadrángulos de Puerto Bermúdez y Bajo Pichanaqui"),
    "88-A": ("CGS Consultores Asociados (modificado por INGEMMET)", 1997, "Geología de los cuadrángulos de Codo del Pozuzo y Río Palcazu"),
    "92-A": ("Guzmán, A.; Zavala, B. & Aldana, M.", 1997, "Geología de los cuadrángulos de Dos de Mayo y Orellana"),
    "93-A": ("Martínez, W.; Valdivia, E. & Sánchez, J.", 1997, "Geología de los cuadrángulos de Nuevo Edén y Puerto Bolívar"),
    "94-A": ("Sánchez, A.; Chira, J. & Valencia, M.", 1997, "Geología de los cuadrángulos de Tarapoto, Papa Playa, Utcurarca y Yanayacu"),
    "96-A": ("Fídel, L. & Valenzuela, G.", 1997, "Geología de los cuadrángulos de Sungaro y Capanahua"),
    "97-A": ("Cerrón, F.; Atencio, A. & Quispe, L.", 1997, "Geología de los cuadrángulos de Río Biabo, Manco Cápac y Vencedor"),
    "99-A": ("Quispesivana, L.; Zuloaga, A. & Paz, M.", 1997, "Geología de los cuadrángulos de Teniente Pinglo, Santa María de Nieva…"),
    "100-A": ("Zárate, H.; Galdos, J. & Ticona, P.", 1997, "Geología de los cuadrángulos de San Rafael, Río Cushabatay e Inahuaya"),
    "101-A": ("Lipa, V.; Larico, W. & Cuyubamba, V.", 1997, "Geología de los cuadrángulos de Puerto Oriente, Ana María y Río Tapiche"),
    "102-A": ("De La Cruz, N.; Zedano, J. & Zapata, A.", 1997, "Geología de los cuadrángulos de San Roque, Río Callería, San Lucas…"),
    "103-A": ("Sánchez, J.; Álvarez, D.; Lagos, A. & Huamán, N. (UNMSM)", 1997, "Geología de los cuadrángulos de Balsapuerto y Yurimaguas"),
    "112-A": ("Martínez, W.; Valdivia, E. & Cuyubamba, V.", 1998, "Geología de los cuadrángulos de Aucayacu, Río Santa Ana…"),
    "115-A": ("De La Cruz, J.; Lara, M. & Raymundo, T.", 1998, "Geología de los cuadrángulos de Cahuapanas y Nueva Cajamarca"),
    "117-A": ("Cerrón, F.; Galloso, A. & Chumpitaz, M.", 1998, "Geología de los cuadrángulos de Uracusa y Cachiyacu"),
    "118-A": ("Barreda, J. & Cuba, A.", 1998, "Geología de los cuadrángulos de Quiteni y Canaire"),
    "122-A": ("INGEMMET (autores en portada escaneada)", None, "Geología de los cuadrángulos de Moyobamba, Saposoa y Juanjuí"),
    "8-B": ("INGEMMET – Dirección de Prospección Minera", 2000, "Estudio de los recursos minerales del Perú, Franja N.° 1"),
    "11-B": ("INGEMMET – Dirección de Geología Económica y Prospección Minera", 2002, "Estudio de los recursos minerales del Perú, Franja N.° 2"),
    "12-B": ("INGEMMET – Dirección de Geología Económica y Prospección Minera", 2003, "Estudio de los recursos minerales del Perú, Franja N.° 3"),
    "14-B": ("INGEMMET – Dirección de Geología Económica y Prospección Minera (rev. L. Chirif)", 2005, "Estudio de los recursos minerales del Perú, Franja N.° 4"),
    "22-B": ("Díaz, A. & Ramírez, J.", 2010, "Estudio geológico-económico de rocas y minerales industriales de Arequipa y alrededores"),
    "26-B": ("Díaz, A.; Carpio, M. & Ramírez, J.", 2011, "Estudio geológico económico de las rocas y minerales industriales en las regiones de Moquegua y Tacna"),
    "30-B": ("Díaz, A.; Carpio, M. & Ramírez, J.", 2012, "Estudio geológico económico de rocas y minerales industriales en la región Puno"),
    "32-B": ("INGEMMET – Dirección de Recursos Minerales y Energéticos (autores en portada escaneada)", None, "Estudio geológico económico de rocas y minerales industriales en la región Madre de Dios"),
    "33-B": ("INGEMMET – Dirección de Recursos Minerales y Energéticos (autores en portada escaneada)", None, "Estudio geológico económico de rocas y minerales industriales en la región Cajamarca"),
}
NO_LEIDOS = {"98-A": "El archivo descargado es la página de verificación del repositorio (7 KB), no el boletín: hay que volver a descargarlo."}

# Citas textuales por unidad: (boletín, texto exacto o con corrección OCR entre corchetes, tema)
CITAS = {
    "eolico": [
        ("47-A", "Los más antiguos, conforman extensos mantos de arena de escaso espesor, que no pasan de un metro en las áreas de mayor acumulación. Las arenas son de grano grueso y color gris oscuro, debido a su alto contenido de ferromagnesianos.", "Composición (arenas oscuras)"),
        ("47-A", "Los mantos, de arena más fina y clara compuesta mayormente de cuarzo, acusan una mayor movilidad y cubren igualmente grandes extensiones, invadiendo incluso las zonas de arenas oscuras", "Composición (arenas claras)"),
        ("47-A", "La primera ocurrencia mencionada es impresionante, constituye un depósito de 63 Km. de longitud, en dirección Norte-Sur, y un ancho promedio de 1[0] Km. Para estos depósitos se estima, un grosor máximo de 100 a 150 m.", "Volumen: dunas de Guadalupe (margen derecha del río Ica)"),
        ("44-A", "constituyen medianos del tipo barjana como los observados al Este del cerro La Bruja en Chilca y en la pampa Clarita al sureste de Cañete", "Localidades cerca de la fábrica"),
        ("59-A", "consisten de arenas semiconsolidadas con estratificación sesgada, cuyos componentes son cuarzo de 1 a 3 mm. granos oscuros de rocas volcánicas finas", "Depósitos marinos (Chimbote–Casma)"),
        ("17-A", "constituyen médanos del tipo barcana, tal como se observa entre Puémape y puerto Chicama y en las pampas que se hallan al Norte del valle Virú.", "Localidades (La Libertad)"),
        ("54-A", "La principal fuente de sedimentos se encuentra al Suroeste, en el\" Desierto de Sechura, de donde fluyen corrientes eólicas, formando en partes corredores de dunas en movimiento.", "Fuente de las arenas (Piura)"),
    ],
    "marcavilca": [
        ("44-A", "Esta secuencia originalmente fue descrita por C. Lisson (1907) con el nombre de “Serie Arenosa”, posteriormente la Comisión del Instituto Geológico del Perú, en informe inédito la diferenció en las formaciones Salto del Fraile, La Herradura y Marcavilca", "Definición"),
        ("44-A", "Cuarcitas y areniscas cuarzosas gris blanquecinas, en capas medianas; intercaladas en la base y techo con lutitas color plomizo amarillento y negruzco; cerca al tope una capa de caliza.", "Litología (Fm. Marcavilca, hojas de Mala–Chincha)"),
        ("44-A", "Esta formación está parcialmente cubierta por depósitos eólicos pero se estima un espesor de 200 m.", "Espesor"),
        ("14-B", "El Grupo Morro Solar está conformado por las formaciones Salto del Fraile, La Herradura y Marcavilca, que tienen su localidad tipo en el Morro Solar de Chorrillos.", "Localidad tipo"),
    ],
    "chimu": [
        ("26-A", "Generalmente tiene entre 500 y 700 m. de espesor y dentro del área de estudio se presenta invariablemente en anticlinales", "Espesor"),
        ("26-A", "Litológicamente la formación consiste de una ortocuarcita de grano medio, la que sin embargo ha sido recristalizada, teniendo en muestra de mano el aspecto general de una cuarcita metamórfica.", "Petrografía: ortocuarcita"),
        ("17-A", "Regionalmente la formación Chimú está constituída por paquetes generalmente gruesos de areniscas y cuarcitas blancas, grises hasta pardas, de grano fino a grueso y formas subredondeadas", "Textura"),
        ("17-A", "Cuarcita blanca, grano redondeado fino a grueso, estratificación gruesa y a veces entrecruzada, con intercalaciones de lutitas negras que contienen restos mal conservados de plantas", "Columna medida"),
        ("33-B", "Consiste de arenas silíceas de grano fino, de color blanco, disgregables.", "Cantera Santa Rosa de Matara II (Jesús, Cajamarca)"),
        ("33-B", "Afloramientos de arenisca cuarzosa, de grano medio, de color blanco grisáceo, muy compacta, se presentan en estratos que varían de 0.15 a 0.30 m de espesor", "Ocurrencia Huaca Corral (San Marcos)"),
    ],
    "farrat": [
        ("17-A", "Ortocuarcitas blancas de grano fino en capas hasta de 100 cm., con estratificación cruzada", "Petrografía: ortocuarcita"),
        ("31-A", "Consta de cuarcitas y areniscas blancas de grano medio a grueso, tiene un grosor promedio de 500 m. aumentando en el sector suroeste. En algunos lugares se observa estratificación cruzada y marcas de oleaje.", "Litología y espesor"),
        ("59-A", "la litología de la Formación Farrat incluye aproximadamente 135 m. de arenisca cuarzosa o cuarcitas en el caso que hayan sufrido los efectos de alteración hidrotermal o metamorfismo de contacto; su color es blanco rosáceo a rojizo", "Chimbote–Casma"),
        ("33-B", "El material se explota a tajo abierto, de forma artesanal y es tratado mediante lavado insitu para disminuir el contenido alto de óxidos que tiene.", "Cantera Lavasil 1 (Namora): óxidos"),
        ("33-B", "consiste en cuarcitas blancas masivas y areniscas generalmente de grano medio y color blanquecino, en la parte inferior, con intercalaciones delgadas de lutitas marrones y grises en la parte superior, su grosor oscila entre los 200 y 500 m", "Grupo Goyllarisquizga indiviso (Cajamarca)"),
    ],
    "hualhuani": [
        ("46-A", "la Formación Hualhuani revela cierta emersión, cuya limpieza de sus elementos, selección, madurez y la frecuencia de marcas de oleaje acompañados con estratificación cruzada, muestran vigorosa acumulación en condiciones playeras y agitada.", "Madurez y ambiente"),
        ("30-B", "Compuesta por areniscas cuarzosas blancas sacaroideas de grano fino a medio.", "Litología (Puno)"),
        ("30-B", "En términos regionales la potencia está entre 100 y 500 m.", "Espesor"),
        ("58-A", "Esta Formación descrita por primera vez por Jenks W. F. (1948) al Oeste de Arequipa", "Definición"),
        ("58-A", "secuencia monótona de cuarcitas de color blanco amarillento, grano medio a fino", "Litología (Velille–Azángaro)"),
        ("22-B", "Se caracteriza por estar constituido por areniscas cuarzosas de grano fino, de color blanco, que por intemperismo se torna de color rojo amarillento.", "Litología (Arequipa)"),
        ("26-B", "Cuarcitas blanco grisáceas a grisáceo rojizas por la presencia de óxidos de hierro, de grano medio y alto grado de compactación.", "Cantera Concepción (Pachía, Tacna)"),
        ("26-B", "Las cuarcitas son trasladadas hacia la fundición de Ilo para su procesamiento posterior.", "Uso actual: fundente"),
    ],
    "huancane": [
        ("74-A", "para referirse a una secuencia de areniscas cuarzosas del Cretáceo inferior que, teniendo su localidad típica en el pueblo del mismo nombre, aflora preferente y conspícuamente en el sinclinorium de Putina.", "Definición (Newell, 1949)"),
        ("74-A", "Las facies de estas areniscas pueden variar de sublitarenitas a cuarzoarenitas.", "Petrografía: variable"),
        ("58-A", "Arenisca gris blanquecina algo rosada muy feldespática resistente a la erosión.", "Niveles feldespáticos (columna)"),
        ("58-A", "Arenisca arcósica blanquecina de grano fino.", "Niveles arcósicos (columna)"),
        ("30-B", "El depósito consiste de areniscas cuarzosas de color rosado, grano medio, con alto grado de compactación.", "Ocurrencia Choquisani (Azángaro)"),
    ],
    "cushabatay": [
        ("100-A", "fue reportada como una secuencia monótona de areniscas cuarzosas blanco amarillentas, de grano grueso a medio, granos subredondeados y ligeramente friables, en bancos medianos a muy gruesos y con fuerte estratificación sesgada", "Textura"),
        ("100-A", "se considera un grosor más o menos de 750 metros", "Espesor (sección de Kummel)"),
        ("115-A", "Está constituida por una gruesa secuencia de areniscas cuarzosas de color blanco a gris amarillentas de grano grueso a medio en paquetes gruesos, con estratificación cruzada", "Litología"),
        ("122-A", "fue descrita como areniscas macizas blancas y amarillo brunáceas de grano fino a grueso con estratificación cruzada", "Definición (Kummel; Zegarra y Olaechea, 1970)"),
    ],
    "vivian": [
        ("94-A", "La Formación Vivían se compone de areniscas cuarzosas blancas de grano fino a grueso, bien seleccionadas, friables, con poca matriz arcillosa", "Petrografía"),
        ("32-B", "Se trata de areniscas bien seleccionadas, ocasionalmente cuarcitas, cuyos granos son subredondeados a redondeados, e indican transporte eólico.", "Madurez textural"),
        ("99-A", "describió esta unidad en la quebrada Vivían, en los cerros de Contamana, la misma que fue descrita como Areniscas de Azúcar en la región del Bajo Pachitea", "Definición (Kummel, 1946)"),
        ("100-A", "El grosor de la Formación Vivian en el pozo Maquía es de 70 metros (cuadrángulo de Puerto Oriente), en Santa Clara y en el río Sarayaquillo es de 170 y 137 respectivamente", "Espesor"),
        ("14-B", "Consiste de areniscas cuarzosas blanquecinas de grano fino a grueso bien seleccionados.", "Litología"),
    ],
    "agua_caliente": [
        ("32-B", "Se trata de areniscas cuarzosas bien seleccionadas, de grano fino a medio, blancas a amarillentas, en capas medianas a gruesas que toma aspecto de cuarcita en partes con buena porosidad y permeabilidad", "Petrografía"),
        ("115-A", "la define como miembro Agua Caliente en la quebrada del mismo nombre, ubicada en las montañas de Contamana, donde midió una sección de 270 m de grosor.", "Definición y espesor"),
        ("92-A", "Arenisca cuarzosa, compuesta por abundantes granos de cuarzo (cz), de formas subredondeadas y escasamente subangutosas [subangulosas].", "Lámina delgada (150X)"),
    ],
}

# Química de canteras/ocurrencias de sílice (valores en bruto del laboratorio; tabla y página del PDF)
# (boletín, tabla, pág, nombre, distrito/provincia, hoja, zona UTM, norte, este, unidad, espesor, descripción, muestra, SiO2, Fe2O3, Al2O3, nota)
QUIMICA = [
    ("33-B", 226, 260, "Cantera Alisuco", "Celendín / Celendín", "14-g", 17, 9237736, 814277, "Grupo Goyllarisquizga", "40 m", "Arenisca cuarzosa de grano medio a grueso, deleznable, rosada", "14G-RNM-081", 95.29, 0.15, 2.41, "Explotación artesanal, 8 m³/semana"),
    ("33-B", 227, 262, "Ocurrencia Santa Rosa de Matara II", "Jesús / Cajamarca", "15-g", 17, 9193680, 797945, "Formación Chimú", "8,5 m", "Arenas silíceas de grano fino, blancas, disgregables", "15G-RNM-109", 94.00, 0.06, 1.17, ""),
    ("33-B", 228, 263, "Ocurrencia Hualqui", "Jesús / Cajamarca", "15-g", 17, 9193825, 795815, "Formación Chimú", "10 m", "Arenas silíceas de grano fino, blancas, disgregables", "15G-RNM-110", 95.27, 0.09, 0.92, ""),
    ("33-B", 229, 264, "Cantera Casa Blanca", "Namora / Cajamarca", "15-g", 17, 9204048, 798610, "Formación Chimú", "20 m", "Arenas silíceas de grano medio, blancas, fácilmente disgregables", "15G-RNM-113", 92.33, 0.07, 1.68, "Explotación artesanal (construcción)"),
    ("33-B", 230, 265, "Cantera Cabracabra", "Namora / Cajamarca", "15-g", 17, 9205282, 797043, "— (no indicada)", "10 m", "Arenas silíceas de grano medio a grueso, blanco amarillento", "15G-RNM-114", 96.44, 0.13, 0.82, "Explotación artesanal"),
    ("33-B", 231, 266, "Cantera Lavasil 1", "Namora / Cajamarca", "15-g", 17, 9202994, 797050, "Formación Farrat", "5 m", "Arenas silíceas de grano medio, blanco rosáceo", "15G-RNM-115", 92.16, 0.66, 3.10, "Se lava in situ por óxidos"),
    ("33-B", 232, 268, "Cantera Bellavista", "Namora / Cajamarca", "15-g", 17, 9203620, 792561, "Grupo Goyllarisquizga", "—", "Arena silícea de grano medio bajo diatomitas", "15G-RNM-117", 62.76, 0.38, 15.68, "Arcillosa: no es sílice"),
    ("33-B", 233, 269, "Cantera Comunidad de Sirac", "Cospán / Cajamarca", "15-f", 17, 9182119, 766595, "Formación Chimú", "25 m", "Arena silícea de grano medio, blanca a rosácea", "15F-RNM-134", 95.47, 0.11, 1.52, "Explotación artesanal"),
    ("33-B", 234, 269, "Ocurrencia Black Star 10", "Contumazá / Contumazá", "15-f", 17, 9188165, 747583, "Formación Chimú", "—", "Arenisca de grano medio, blanca a violácea, disgregable", "15F-RNM-152", 96.06, 0.21, 1.01, ""),
    ("33-B", 235, 270, "Cantera Gracias Padre Eterno", "Namora / Cajamarca", "15-g", 17, 9206511, 794477, "— (no indicada)", "20 m", "Arena silícea de grano medio con caolín y óxidos", "15G-RNM-173", 74.29, 0.45, 9.44, "Caolinítica: no es sílice"),
    ("33-B", 236, 272, "Ocurrencia Carbonífera Chicama 31", "José M. Quiroz / San Marcos", "15-g", 17, 9187372, 824109, "— (no indicada)", "—", "Arenas silíceas", "15F-RNM-177", 95.74, 0.06, 1.96, ""),
    ("33-B", 237, 272, "Ocurrencia ATIMMSA 31", "José M. Quiroz / San Marcos", "15-g", 17, 9183606, 823879, "Formación Farrat", "—", "Arena silícea de grano medio, blanca, disgregable", "15G-RNM-178", 95.14, 0.13, 1.94, ""),
    ("33-B", 238, 275, "Ocurrencia Siangos", "Bellavista / Jaén", "11-f", 17, 9394914, 734451, "Grupo Goyllarisquizga", "40 m", "Arenisca de grano medio, blanco rosácea, óxidos en fracturas", "11F-RNM-008", 92.41, 1.26, 2.89, ""),
    ("33-B", 239, 275, "Ocurrencia cerro La Poza", "Llama / Chota", "14-e", 17, 9279115, 699519, "Grupo Goyllarisquizga", "300 m", "Areniscas silicificadas grisáceas, muy compactas", "14E-RNM-032", 97.76, 0.97, 0.98, ""),
    ("33-B", 240, 276, "Ocurrencia Utco", "Utco / Celendín", "14-g", 17, 9241312, 824633, "Grupo Goyllarisquizga", "80 m", "Arenisca cuarzosa de grano medio, blanco rosácea, disgregable", "14G-RNM-71", 98.60, 0.18, 0.44, ""),
    ("33-B", 241, 276, "Ocurrencia Colpa", "Cachachi / Cajabamba", "16-g", 17, 9152734, 811830, "Grupo Goyllarisquizga", "—", "Areniscas de grano grueso, blancas a rosáceas", "16G-RNM-95", 91.29, 1.65, 1.84, ""),
    ("33-B", 242, 277, "Ocurrencia cerro Sumiate", "Cospán / Cajamarca", "15-g", 17, 9173500, 775560, "Grupo Goyllarisquizga", "—", "Areniscas de grano grueso, blanco grisáceas", "15G-RNM-97", 96.88, 0.36, 0.61, ""),
    ("33-B", 243, 278, "Ocurrencia ATIMMSA 40", "Cachachi / Cajabamba", "16-g", 17, 9165560, 807848, "Grupo Goyllarisquizga", "—", "Areniscas de grano medio, blanco grisáceas, muy compactas", "15G-RNM-98", 93.45, 0.26, 0.99, ""),
    ("33-B", 244, 280, "Ocurrencia Huaca Corral", "E. Villanueva / San Marcos", "15-g", 17, 9174517, 814082, "Formación Chimú", "—", "Arenisca cuarzosa de grano medio, blanco grisácea, muy compacta", "15G-RNM-102", 98.28, 0.10, 0.92, ""),
    ("33-B", 245, 280, "Ocurrencia Santa Rosa de Matara I", "Jesús / Cajamarca", "15-g", 17, 9194041, 798042, "Formación Farrat", "—", "Areniscas de grano medio, gris a rojizas, compactas", "15G-RNM-108", 92.84, 1.02, 2.28, ""),
    ("33-B", 246, 281, "Ocurrencia cerro San Antonio", "Chilete / Contumazá", "15-f", 17, 9201182, 743710, "Formación Farrat", "—", "Areniscas cuarzosas de grano medio, blancas, muy compactas", "15F-RNM-129", 95.53, 0.26, 1.19, ""),
    ("33-B", 247, 282, "Ocurrencia El Algarrobal", "San Benito / Contumazá", "15-f", 17, 9170965, 725130, "— (no indicada)", "—", "Arenisca silicificada blanca, muy compacta", "16F-RNM-158", 80.98, 0.71, 2.65, ""),
    ("26-B", None, 113, "Cantera Cristóbal", "Pachía / Tacna", "36-v", 19, 8031956, 381630, "Formación Hualhuani", "15 m", "Cuarcitas gris blanquecinas a rojizas, muy compactas", "—", 91.10, 0.52, 2.96, "Uso: fundente (SiO₂ < 95 %)"),
    ("26-B", None, 112, "Canteras Fátima 1 · Virgen de las Peñas III · Mercedes II (3 análisis sin rótulo)", "Pachía y Palca / Tacna", "36-v / 36-x", 19, 8030435, 382093, "Fm. Hualhuani (Fátima 1); Fm. Labra (V. de las Peñas III)", "hasta 50 m", "Cuarcitas y areniscas cuarzosas con óxidos de hierro en fracturas", "—", 92.8, 1.07, 2.88, "Rango de los 3 análisis: SiO₂ 92,8–93,0 %; Fe₂O₃ 0,70–1,07 %; Al₂O₃ 2,78–2,88 %. Fundente para la fundición de Ilo (Southern)"),
    ("30-B", None, 178, "Cantera Multicolor I", "Pichacani / Puno", "33-v", 19, 8199516, 372484, "Formación Hualhuani", "50 m", "Areniscas cuarzosas blancas con tonos rojizos, muy compactas", "2 muestras", 90.0, 0.96, 1.78, "SiO₂ «> 90» (dos análisis); Fe₂O₃ 0,53 y 0,96 %; Al₂O₃ 1,78 y 1,00 %. Apta como fundente"),
    ("30-B", None, 178, "Ocurrencia Choquisani", "San Antón / Azángaro", "30-v", 19, 8396812, 364127, "Formación Huancané", "40 m", "Areniscas cuarzosas rosadas, grano medio, muy compactas", "—", 90.0, 1.5, 1.5, "Texto: SiO₂ > 90; Fe₂O₃ < 1,5; Al₂O₃ y CaO por encima del límite para fundente"),
]

# Especificaciones citadas por INGEMMET (30-B)
ESPECIFICACIONES = [
    ("Vidrio", "Arenas con 95 % a 99,8 % de SiO₂; alúmina < 4 % (vidrio común); el óxido de hierro da tintes verde y amarillo y solo en el vidrio ámbar puede llegar a 1 %; granos entre las mallas 20 y 100.", "30-B", 181),
    ("Refractarios", "> 95 % de SiO₂ y < 0,5 % de Fe₂O₃.", "30-B", 182),
    ("Ferrosilicio", "Grava de cuarzo con ≥ 95 % de SiO₂ y ≤ 0,02 % de P₂O₅, tamaño entre +½\" y −2\".", "30-B", 182),
    ("Recurso silíceo", "Se consideran recursos silíceos los materiales con más de 95 % de SiO₂ (Lorenz y Gwosdz, 2004).", "33-B", 258),
    ("Precios en cantera", "Sílice para fundición: US$ 10–15/t (centro) y 15–19/t (sur); para vidrio: US$ 15–20/t; para ladrillos: 7–15; para cemento: 10–15 (Tabla 75).", "30-B", 183),
    ("Ocurrencias en el Perú", "153 ocurrencias y canteras de sílice en 17 regiones; las de mayor potencial: Tacna (50), Junín (31) y Cajamarca (27) (Tabla 248).", "33-B", 283),
]

# v3
from evidencia_v3 import CITAS_V3, OCURRENCIAS, FICHAS_NUEVAS, FICHA_META  # noqa: E402
CITAS.update(CITAS_V3)

# 98-A (descargado de nuevo el 23/11/2026)
AUTORES["98-A"] = ("De La Cruz, J.; Lara, M. & Raymundo, T.", 1997, "Geología de los cuadrángulos de San Alejandro, Santa Rosa, Río Nova y Puerto Inca")
NO_LEIDOS.pop("98-A", None)
CITAS["vivian"] += [
    ("98-A", "Las areniscas están bien clasificadas compuestas por cuarzos y algunos fragmentos líticos.", "Selección y composición (Puerto Inca)"),
    ("98-A", "Se les puede clasificar como cuarzo-arenitas y areniscas cuarzosas de grano medio a fino, deleznables con un aspecto sacaroide.", "Clasificación: cuarzoarenita"),
    ("98-A", "Presentan estratificación cruzada (Foto N° 8), el grosor aproximado es de 160 m.", "Espesor (montaña del Sira)"),
]
CITAS["oriente"] += [
    ("98-A", "Litológicamente consiste de areniscas cuarzosas blancas de grano grueso (Foto N° 4), en estratos gruesos, que debido a su resistencia forma escarpas muy empinadas, con estratificación cruzada", "Litología (Sira y Ganso Azul)"),
    ("98-A", "Ocasionalmente presenta abundantes concreciones de fierro que se presentan en forma de capitas en los planos de estratificación", "Hierro: concreciones"),
]
CITAS["agua_caliente"] += [
    ("98-A", "En el reservorío Agua Caliente, se han estimado reservas por 2.3 millones de metros cúbicos de petróleo (14.6 millones de barriles).", "Reservorio de petróleo (Ganso Azul, Huánuco)"),
]
