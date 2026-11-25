// Guía «¿para qué sirve cada capa?» — se muestra con ⓘ en el panel de capas y en
// la guía completa (📖). Escrita para un geólogo en campo: qué aporta, cómo
// usarla en la prospección de arena silícea y qué cuidar al interpretarla.

export interface Ayuda {
  para: string; // para qué sirve
  uso: string;  // cómo usarla en la prospección
  ojo?: string; // limitaciones / cuidado
}

export const AYUDA_CAPAS: Record<string, Ayuda> = {
  // ---------------------------------------------------------------- geología
  resultados: {
    para: "Te dice DÓNDE buscar dentro de la cuadrícula: los polígonos del mapa geológico que pueden tener arena silícea, ya clasificados en A, B o C.",
    uso: "A = DEPÓSITOS de arena silícea o cuarzosa (eólicos, dunas, mantos: arena suelta, la más fácil de extraer). B = ROCAS: arenisca cuarzosa o cuarcítica (sedimentaria) y cuarcita (metamórfica), incluidas las formaciones silíceas conocidas (Chimú, Marcavilca…). C = verificar: arenisca o arena eólica sin decir «cuarzosa». Empieza por las A, luego las B. Tócalas para ver unidad, litología, roca dominante, hectáreas y km a la fábrica: son tu lista de objetivos de campo.",
    ojo: "Es lo que dibujó INGEMMET a escala 1:50 000, no una medición: una zona puede mezclar capas de distinta calidad.",
  },
  geo50_si: {
    para: "Ver de un vistazo, en toda la región, dónde aflora roca silícea (cuarcita, arenisca o arena cuarzosa), ANTES de elegir qué cuadrícula analizar.",
    uso: "Aleja el zoom y busca manchas grandes cerca de la fábrica o de una vía; luego toca la cuadrícula que las contiene. Tócala para ver la unidad.",
    ojo: "Filtro amplio por texto: incluye unidades mixtas (p. ej. andesita con arenisca cuarzosa). Los colores son de INGEMMET, uno por unidad, no A/B/C.",
  },
  geo100_si: {
    para: "Lo mismo, a escala 1:100 000: cubre las zonas donde aún no hay carta 1:50 000.",
    uso: "Úsala si en una zona no aparece nada con la 50K.",
    ojo: "Menos detalle: los polígonos son más grandes y generalizados.",
  },
  geo50: {
    para: "El mapa geológico completo: qué rocas rodean a la arena silícea (intrusivos, calizas, volcánicos) y cómo se disponen.",
    uso: "Sirve para entender el contexto: si una cuarcita está cortada por intrusivos o cubierta por volcánicos, su calidad o acceso puede cambiar. Toca un polígono para ver su descripción.",
  },
  geo100: {
    para: "El mapa geológico completo a 1:100 000.",
    uso: "Contexto regional, o donde no hay carta 1:50 000.",
  },
  // ---------------------------------------------------------------- referencia
  fabrica: {
    para: "El punto desde el que se miden todas las distancias (km en línea recta) y se ordenan las zonas «más cercanas».",
    uso: "Está fija en San Vicente de Cañete (Antigua Panamericana Sur); no se puede mover.",
    ojo: "La distancia por carretera siempre será mayor.",
  },
  cuadricula: {
    para: "Divide el Perú en cuadrículas 1:25 000 (cada hoja 1:50 000 de INGEMMET en 4; unos 190 km² cada una) para analizar y guardar por partes.",
    uso: "Toca una para analizarla. En el mapa: ✓ = ya analizada, ★ = guardada en una carpeta; el color del borde es su mejor clase.",
  },
  // ---------------------------------------------------------------- derechos
  restringidas: {
    para: "Dónde NO se puede o es difícil tener una concesión: áreas naturales protegidas (ANP de SERNANP) y sus zonas de amortiguamiento, propuestas de ANP, zonas arqueológicas, áreas de no admisión de petitorios (ANAP), defensa nacional, zonas urbanas, puertos y aeropuertos, proyectos especiales, reservas indígenas, Ramsar, ecosistemas frágiles, fajas marginales y las concesiones forestales vigentes (trama verde oscuro, catastro forestal de SERFOR).",
    uso: "Revísala ANTES de ir a campo. ⛔ No concesionable: ANP de uso indirecto (parques y santuarios nacionales), ANAP, zonas arqueológicas, defensa nacional. ⚠ Restringido: se puede pedir, pero con autorización u opinión previa (p. ej. compatibilidad de SERNANP en ANP de uso directo —reservas nacionales— y en zonas de amortiguamiento). Al analizar una cuadrícula, la app calcula qué % de ella y de cada zona favorable cae dentro.",
    ojo: "Información referencial de GEOCATMIN: los límites y la norma vigente se confirman con INGEMMET y SERNANP antes del petitorio.",
  },
  catastro: {
    para: "Las concesiones mineras otorgadas o en trámite: dice si el terreno ya tiene titular.",
    uso: "Revísala ANTES de ir a campo o de negociar: una zona A dentro de una concesión ajena no está disponible (habría que tratar con el titular).",
    ojo: "Información referencial; se confirma en INGEMMET.",
  },
  areas_libres: {
    para: "En VERDE, la tierra de TODO el Perú que hoy no tiene derecho minero (titulado, en trámite, extinguido sin publicar, canteras del Estado…), está fuera de toda área protegida o restringida (ANP, amortiguamiento, arqueológicas, ANAP, urbanas, reservas indígenas, Ramsar, ecosistemas frágiles, fajas marginales, concesiones forestales…) y además sirve para una cantera. En CELESTE, lo mismo pero sobre un derecho minero EXTINGUIDO (gris en GEOCATMIN): ya no tiene titular, pero solo se puede pedir cuando INGEMMET publique su libre denunciabilidad. En ÍNDIGO, los derechos TITULADOS o EN TRÁMITE fuera de áreas protegidas y aptos para cantera: no son libres, pero se puede NEGOCIAR con el titular (compra, cesión, opción o contrato de explotación); canteras del Estado, bloqueados y lo que cae en áreas protegidas quedan sin color. En ÁMBAR, lo que está libre en papel pero no sirve: chacras, zonas construidas, agua o bofedales (cobertura del suelo Sentinel-2 10 m), franja de carreteras (50 m nacional, 25 m departamental, 15 m vecinal), faja de ríos y lagunas (25–50 m) o a menos de 300 m de un centro poblado.",
    uso: "Para buscar dónde se podría pedir un petitorio: lo ideal es roca buena (zona A/B limpia: ver «Prioridad libre») en verde y cerca de la fábrica. Al analizar una cuadrícula se calcula el % libre exacto de ella y de cada zona favorable, con la lista de concesiones (titular, estado).",
    ojo: "Se consulta EN VIVO al catastro de INGEMMET (se actualiza a diario); los análisis guardados se vuelven a consultar cada 7 días o con «↻ Actualizar». Con el mapa muy alejado el borde es aproximado. Referencial: confirmar en GEOCATMIN antes del petitorio.",
  },
  catastro_nm: {
    para: "Solo las concesiones NO metálicas vigentes (tituladas o en trámite), en naranja: donde alguien ya pidió o explota arena, sílice, caliza, arcilla, agregados…",
    uso: "Es un indicio de dónde hay material no metálico de interés: si una no metálica cae sobre roca cuarzosa (zona A/B), es probable que sea arena silícea. Al analizar la cuadrícula, cada derecho trae «¿Qué extrae?»: material probable (por su nombre, titular o proyecto ambiental), la geología debajo y si hay señales de explotación (REINFO, certificación ambiental, pasivos).",
    ojo: "INGEMMET solo registra «no metálica», no el mineral: el material es una inferencia. Muchas concesiones son solo petitorios especulativos sin actividad.",
  },
  // ---------------------------------------------------------------- vistas satelitales de la cuadrícula

  s2_prioridad_libre: {
    para: "PRIORIDAD LIBRE = la geología silícea de interés (zonas A —depósitos de arena silícea— y B —arenisca cuarzosa o cuarcita— de la carta; la C «verificar» no entra) donde se cumplen LOS TRES filtros a la vez: NDVI bajo (sin vegetación o escasa, < P57) · anomalía ferruginosa baja (clases índigo, azul, celeste, < P30) · arcilla baja (< P30). Cada corte se ajusta con su histograma. MENOS las áreas protegidas. Se pinta según lo que hay encima: VERDE = libre (se puede pedir) · AZUL = concesión titulada o en trámite (negociable) · AMARILLO = libre pero chacra, poblado, vía o río · CELESTE = derecho extinguido.",
    uso: "Es el mapa de «dónde ir»: lo verde se puede pedir; lo azul, negociar. Las hectáreas de cada color salen arriba en la pestaña Zonas y en cada zona; las zonas se ordenan por hectáreas libres.",
    ojo: "Los tres filtros son RELATIVOS a la cuadrícula (percentiles). Lo que Sentinel-2 no ve (vegetación densa, nubes, agua) no entra. Sin Sentinel-2 («Solo geología») se usa solo la geología. Las áreas libres son de la fecha de la consulta; confirmar en GEOCATMIN antes del petitorio.",
  },





  s2_ndvi: {
    para: "NDVI = (B8 − B4)/(B8 + B4): cuánta vegetación verde hay. Escala CONTINUA con el 100 % de los píxeles (sin corte ni histograma): pardo = sin vegetación (roca o suelo) → verde oscuro = vegetación densa. El color es la posición del píxel en la cuadrícula (0–100 %).",
    uso: "Lo pardo es donde se ve el terreno: ahí Sentinel-2 puede medir hierro y arcillas. Compárala con el BSI y bájale la transparencia sobre la foto RGB o SWIR.",
    ojo: "Relativa a la cuadrícula y a la fecha de la toma (en época de lluvias todo sale más verde). Solo quedan fuera las nubes y sus sombras.",
  },
  s2_bsi: {
    para: "BSI (índice de suelo desnudo) = ((B11 + B4) − (B8 + B2)) / ((B11 + B4) + (B8 + B2)). Escala CONTINUA con el 100 % de los píxeles: azul petróleo = cubierto o húmedo → BLANCO = suelo o roca desnuda.",
    uso: "Superponla a la Foto real (RGB 4-3-2) o a la Foto geológica (SWIR 12-11-2) y baja su transparencia: lo blanco continuo que sigue el rumbo de la formación es el afloramiento; los cortes en la continuidad son cobertura.",
    ojo: "Arena suelta, suelo arado, poblados y caminos también salen blancos: compara con la foto y con el NDVI.",
  },

  s2_ferruginosas: {
    para: "ANOMALÍAS FERRUGINOSAS = FÉRRICO + FERROSO. Férrico = B4/B2 + B4/B3 (Fe³⁺: hematita, goethita, limonita; lo rojizo-amarillento) y ferroso = B11/B8A (Fe²⁺: minerales oscuros, máficos, clorita, biotita); cada uno como percentil en la cuadrícula, sumados. En 10 CLASES fijas de igual número de píxeles: índigo = lo menos ferruginoso → granate = lo más.",
    uso: "Bájale la transparencia sobre la foto o sobre el BSI: un afloramiento blanco y continuo en las clases índigo, azul o celeste es el blanco ideal para arena de vidrio. Las 10 clases son fijas (deciles); el corte de su histograma decide cuántas pasan a la Prioridad libre (P30 = las tres primeras).",
    ojo: "Relativa a la cuadrícula: siempre hay un 10 % «más rojo», aunque toda sea limpia. Suelos rojizos, pátinas superficiales y arena muy clara del desierto (sube B11/B8A) también lo levantan.",
  },






  s2_arcillas: {
    para: "Cociente B11/B12 (arcillas, micas, sericita, sulfatos) en 10 CLASES fijas de igual número de píxeles: índigo = lo menos arcilloso → granate = lo más. La arcilla baja la calidad y obliga a lavar la arena.",
    uso: "A la Prioridad libre pasan las clases bajo tu corte (P30 = índigo, azul, celeste). Ajusta el corte con el histograma (botón junto a la capa).",
    ojo: "Relativo a la cuadrícula. La vegetación seca y algunos suelos también suben B11/B12: compárala con la Foto real.",
  },
  s2_natural: {
    para: "El terreno como lo verías desde un avión, en la toma más despejada sobre la cuadrícula de los últimos 18 meses (fecha, hora y % de nubes en la pestaña de satélite).",
    uso: "Planifica la visita: accesos, trochas, canteras existentes, poblados, cultivos y quebradas.",
  },
  s2_swir: {
    para: "La combinación clásica de los geólogos (bandas 12-11-2): cada tipo de roca toma un tono distinto.",
    uso: "Las cuarcitas y areniscas claras resaltan muy brillantes: ayuda a ver el límite REAL del afloramiento, que puede diferir del mapa geológico.",
  },
};

/** Orden de la guía completa: las 3 preguntas de la prospección (igual que el panel de capas). */
export const GUIA_PASOS: { titulo: string; ids: string[] }[] = [
  { titulo: "1 · ¿Dónde hay roca silícea?", ids: ["geo50_si", "geo100_si", "resultados", "geo50"] },
  { titulo: "2 · ¿Se puede pedir?", ids: ["areas_libres", "restringidas", "catastro", "catastro_nm"] },
  { titulo: "⭐ Resultado", ids: ["s2_prioridad_libre"] },
  { titulo: "3 · ¿Se ve limpia? (satélite)", ids: ["s2_ndvi", "s2_bsi", "s2_ferruginosas", "s2_arcillas", "s2_natural", "s2_swir"] },
  { titulo: "📍 Referencia", ids: ["cuadricula", "fabrica"] },
];
