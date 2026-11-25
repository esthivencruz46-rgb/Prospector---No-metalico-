// Cliente del backend (FastAPI en Render). GEOCATMIN no permite que el
// navegador lea su JSON (no envía CORS), por eso las búsquedas pasan por
// el backend; las IMÁGENES del mapa sí se piden directo (ver Mapa.tsx).

// Servidor (backend): el de la compilación (VITE_API_URL) o el que el usuario escribió en la app (APK: si Render le
// asigna otro nombre al servicio, se cambia sin volver a compilar). Clave `prospector-rmi:api`.
const API_DEFECTO = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const CLAVE_API = "prospector-rmi:api";
export const API_URL: string = (() => {
  try { return (localStorage.getItem(CLAVE_API) || API_DEFECTO).replace(/\/$/, ""); } catch { return API_DEFECTO; }
})();
/** Pide la dirección del servidor y recarga la app (vacío = volver a la de fábrica). */
export function cambiarServidor() {
  const v = window.prompt(`Dirección del servidor de la app (vacío = ${API_DEFECTO})`, API_URL);
  if (v === null) return;
  const limpio = v.trim().replace(/\/$/, "");
  try {
    if (!limpio || limpio === API_DEFECTO) localStorage.removeItem(CLAVE_API);
    else localStorage.setItem(CLAVE_API, /^https?:\/\//.test(limpio) ? limpio : `https://${limpio}`);
  } catch { /* sin almacenamiento */ }
  window.location.reload();
}

export type Clase = "A" | "B" | "C";

export interface Material {
  id: string;
  nombre: string;
  activo: boolean;
  sinonimos: string[];
  usuario?: boolean;  // creada en el editor (no de fábrica)
  sql50?: string;     // filtro del mapa «rocas de interés» (geología 1:50 000)
  sql100?: string;    // ídem 1:100 000
}

/** Definición de una materia prima en el editor (palabras por clase, formaciones, descartes, muestras). */
export interface DefMateria {
  id?: string;
  nombre: string;
  sinonimos: string[];
  clases: { A: string[]; B: string[]; C: string[] };
  formaciones: string[];
  descartar: string[];
  rmi: string[];
  nota: string;
  fabrica?: boolean;  // de fábrica: solo lectura (se puede duplicar)
}

/** Química de laboratorio de una muestra RMI ("Roca Total", %). */
export interface QuimicaRMI {
  SiO2?: number; Fe2O3?: number; Al2O3?: number; TiO2?: number; CaO?: number;
  MgO?: number; K2O?: number; Na2O?: number; LOI?: number;
  cuarzo_drx?: number;
}

/** Muestra del inventario RMI de INGEMMET (NO es una cantera: es un punto
 *  muestreado en un estudio regional, casi siempre con análisis químico). */
export interface RegistroRMI {
  tipo_capa: string; // "Arena Silícea" | "Sílice"
  nombre: string;
  lon: number;
  lat: number;
  codigo?: string;
  muestra?: string;
  ubicacion?: string;
  hoja?: string;
  proyecto?: string;
  quimica: QuimicaRMI;
  enlaces: { titulo: string; url: string }[];
  atributos: Record<string, unknown>;
}

export interface Formacion {
  id: string; // "chimu"… o "texto:…" para una búsqueda libre
  nombre: string;
  tipo: "Formación" | "Grupo" | "Roca" | "Depósito" | "Búsqueda";
  nota?: string; // aviso (p. ej. "arena silícea" no existe en los mapas de INGEMMET)
  palabras?: string[]; // búsqueda libre: palabras que deben aparecer (sin tildes)
  edad: string;
  region: string;
  descripcion: string;
  sql50: string;
  sql100: string | null;
}

export interface HojaFormacion {
  hoja: string; // CODHOJA, p. ej. "27k4" (a veces "08b3")
  poligonos: number;
}

/** Área protegida o restringida para concesiones (GEOCATMIN · SERV_AREA_RESERVADA). */
export interface Restriccion {
  tipo: string;        // «Área natural protegida (ANP)», «Zona arqueológica»…
  nivel: "prohibido" | "restringido";
  nombre: string;
  categoria: string;   // «RESERVA NACIONAL», «PARQUE NACIONAL»…
  uso: string;         // ANP: DIRECTO / INDIRECTO
  norma: string;
  ha_en_cuadricula: number;
  pct_cuadricula: number;
  nota: string;
}

/** Cuánto de una zona favorable cae en áreas prohibidas/restringidas. */
export interface RestriccionZona {
  nivel: "prohibido" | "restringido";
  pct: number;
  nombres: string[];
}

export interface Bibliografia {
  boletines: { tipo: string; serie: string; numero: string; titulo: string; url: string; cita: string }[];
  memorias: { cita: string; poligonos: number; buscar: string }[];
  hoja100k: { codigo: string; nombre: string; zip: string; png: string } | null;
  busquedas: { titulo: string; url: string }[];
  avisos: string[];
  nota: string;
}

export interface Afloramiento {
  id: string;
  clase: Clase;
  motivo: string;
  escala: "50K" | "100K";
  unidad: string;
  formaciones: string[]; // ids del catálogo
  roca_dominante: string; // LITO1 de la 50K ("" en 100K)
  rocas?: string[];        // LITO1–3 de la 50K: principal, secundaria, terciaria
  restriccion?: RestriccionZona | null; // parte de la zona en área protegida/restringida
  libre_pct?: number | null;            // % de la zona sin concesión y fuera de áreas restringidas
  util_pct?: number | null;             // % de la zona libre Y utilizable (sin chacras, pueblos, vías, ríos)
  negociable_pct?: number | null;       // % de la zona sobre concesión titulada / en trámite, apta (negociable)
  concesiones?: ConcesionEnZona[];      // derechos mineros que tocan la zona
  peso_geo?: number;                    // peso geológico (A 1 · B 0,7 · C 0,4): ≥ 0,6 entra en la Prioridad libre

  litologia: string;
  descripcion: string;
  area_ha: number;
  partes: number;
  centro: [number, number];
  geometria: GeoJSON.Polygon | GeoJSON.MultiPolygon;
}

export interface ResultadoBusqueda {
  material: string;
  material_nombre: string;
  area_km2: number;
  centro: [number, number];
  rmi: RegistroRMI[];
  escala_usada: "50K" | "100K" | null;
  motivo_escala: string;
  cobertura_50k: boolean;
  afloramientos: Afloramiento[];
  resumen: { rmi: number; clase_A: number; clase_B: number; clase_C: number; ha_favorables: number };
  avisos: string[];
  segundos: number;
  fuente: string;
  /** resultado vacío del análisis «solo satélite» (no se consultó la geología) */
  soloSatelite?: boolean;
  /** áreas protegidas/restringidas dentro del área (null = no se pudo consultar) */
  restricciones?: Restriccion[] | null;
  libres?: Libres | null;
}

/** Resumen de una cuadrícula en un barrido de región (backend/barrido.py). */
export interface FilaBarrido {
  codigo: string; ok: boolean; error?: string;
  puntaje?: number;
  ha?: Record<Clase, number>; ha_util?: Record<Clase, number>;
  util_pct_celda?: number | null; libre_pct_celda?: number | null; n_concesiones?: number | null;
  prohibido?: boolean; escala?: string | null; muestras?: number; zonas_100k_A_ha?: number;
  mejor_zona?: { clase: Clase; unidad: string; ha_util: number; centro: [number, number] } | null;
  resultado?: ResultadoBusqueda;
}
export interface EstadoBarrido { total: number; hechas: number; terminado: boolean; cancelado: boolean; segundos: number; resultados: FilaBarrido[] }

/** Cifras de tonelaje de un método (en toda la zona o solo en lo libre). */
export interface CifrasTonelaje { area_ha: number; volumen_m3: number; toneladas: number; espesor_medio_m: number; espesor_max_m: number }
export interface Tonelaje {
  metodos: Record<"cerro" | "dunas" | "manto", { metodo: string; explica: string; total: CifrasTonelaje; libre?: CifrasTonelaje }>;
  recomendado: "cerro" | "dunas" | "manto"; por_que: string; tipo: string | null;
  densidad_t_m3: number; potencia_max_m: number | null; potencia_manto_m: number;
  cota_min_m: number; cota_max_m: number; dem: string; nota: string;
}
export interface Curvas { png: string; sur: number; oeste: number; norte: number; este: number; intervalo_m: number; cota_min: number; cota_max: number }

/** Tipo de tramo de una ruta: pista asfaltada · trocha/afirmado (carro) · a pie (sin vía para carro). */
export type TipoTramo = "pista" | "trocha" | "a_pie";

/** Ruta de la fábrica a un punto, por bloques según el tipo de vía (Valhalla · OpenStreetMap). */
export interface Ruta {
  km_total: number; km_carro: number; km_linea_recta: number;
  resumen: Record<TipoTramo, number>;
  tipos: Record<TipoTramo, string>;
  bloques: { tipo: TipoTramo; nombre: string; km: number; vias: string[]; detalle?: string | null; geometria: GeoJSON.LineString }[];
  destino: [number, number];
  fuente: string; nota: string; avisos: string[];
}
/** Derecho minero (catastro de INGEMMET) dentro de la cuadrícula. */
export interface Concesion {
  codigo: string; nombre: string; titular: string;
  estado: string; sustancia: string;
  ha_total: number | null; ha_en_cuadricula: number; pct_cuadricula: number;
  fecha_petitorio: string | null;
  // ficha (análisis desde esta versión; los guardados antes no la traen hasta «↻ Actualizar»)
  estado_detalle?: string; vigente?: boolean; calificacion?: string;
  hora_petitorio?: string | null; carta?: string; ubicacion?: string; expediente_en?: string;
  resolucion_extincion?: string | null;
  vigencia_usd_anual?: number | null; tarifa_usd_ha?: number | null;
  pago?: string;
  indicio_pago?: { nivel: "ok" | "alerta" | "na"; texto: string };
  alertas?: string[];
  enlaces?: { titulo: string; url: string }[];
  reinfo?: { nombre: string; actividad: string; derecho_declarado: string; origen: string }[];
  uea?: { codigo: string; nombre: string | null; derechos?: number };
  pasivos?: { n: number; tipos: string[] };
  certificaciones?: { tipo: string; titular: string; proyecto: string; resolucion: string; fecha: string | null; etapa: string; url: string | null }[];
  // ¿qué extrae? (solo no metálicas: INGEMMET no registra el mineral)
  material_probable?: { material: string; fuente: string; texto: string } | null;
  sobre_zonas?: { clase: Clase; unidad: string; litologia: string; pct: number }[];
  indicio_silice?: { nivel: "alto" | "medio"; texto: string };
  actividad?: { nivel: "alta" | "posible" | "sin indicios"; senales: string[] };
}

/** Derecho minero que toca una zona favorable. */
export interface ConcesionEnZona { codigo: string; nombre: string; estado: string; titular: string; pct: number; extinguido?: boolean }

/** Tierra de la cuadrícula sin derecho minero y fuera de áreas protegidas/restringidas (en vivo). */
export interface Libres {
  consultado: string;                  // ISO UTC: cuándo se consultó GEOCATMIN
  catastro_actualizado: string | null; // fecha más reciente del catastro en la cuadrícula
  ha_tierra: number;
  libre_ha: number; libre_pct: number;
  concesiones_ha: number; concesiones_pct: number;
  protegido_ha: number; protegido_pct: number;
  n_concesiones: number;
  concesiones: Concesion[];
  util_pct?: number | null;            // libre Y utilizable para cantera
  util_ha?: number | null;
  no_apto?: { motivo: string; texto: string; ha: number }[] | null;  // libre en papel pero no apto
  cobertura_anio?: number | null;
  nota_uso?: string;
  por_liberarse_ha?: number;           // parte de lo libre que es derecho EXTINGUIDO (falta publicar la L.D.)
  por_liberarse_pct?: number;
  nota_por_liberarse?: string | null;
  /** titulados / en trámite fuera de áreas protegidas: no libres, pero negociables con el titular */
  negociable_ha?: number; negociable_pct?: number; negociable_util_ha?: number | null; negociable_util_pct?: number | null;
  nota_negociable?: string | null;
  geometria: GeoJSON.Geometry | null;
  nota: string;
}

export interface StatSentinel {
  id: string;
  pixeles: number;
  pct_validos: number;
  /** % de la zona que pasa los tres filtros (NDVI, ferruginosa, arcilla; lo que no se ve no pasa) */
  limpia_pct?: number;
  /** % de los píxeles útiles de la zona excluidos por hierro o arcilla */
  excluido_pct?: number | null;
  oxidos_hierro_pct: number | null;
  arcillas_pct: number | null;
  brillo_pct: number | null;
  ferroso_pct?: number | null;       // hierro ferroso (B11/B8A), rango en la cuadrícula: menos = mejor
  hierro_pct?: number | null;        // hierro total = máx(férrico, ferroso) por píxel: menos = mejor
  cuarzo_aster?: number | null;      // (análisis antiguos: ASTER ya no se usa)
  anomalia_hierro_pct?: number | null;   // % de lo útil con anomalía ferruginosa sobre el corte
  anomalia_arcilla_pct?: number | null;
  /** escala continua 0–100 (posición media de la zona en la cuadrícula): NDVI, BSI y férrico + ferroso */
  ndvi_pct?: number | null;
  bsi_pct?: number | null;
  ferruginosa_pct?: number | null;
}

export interface HistogramaS2 {
  min: number; max: number; cuentas: number[]; percentiles: number[];
}

export interface ResultadoSentinel {
  disponible: boolean;
  motivo?: string;
  bbox?: [number, number, number, number];
  /** imágenes (data URL): silice_limpia, arcillas, ndvi, bsi, ferruginosas, natural, swir */
  capas?: Record<string, string>;
  /** La toma usada: UNA fecha (la más despejada sobre la cuadrícula) o, si el catálogo falla, un mosaico. */
  fuente?: string;              // «Copernicus (Sentinel Hub)» o «AWS · Earth Search (motivo)»
  imagen?: {
    metodo: "una_fecha" | "mosaico";
    fuente?: string;
    fecha_utc?: string;
    fecha_peru?: string;        // "04/04/2026 10:26" (UTC−5)
    nubes_cuadricula: number | null; // % de nubes DENTRO de la cuadrícula
    nubes_escena?: number;      // % de nubes de toda la escena (~110 km)
    despejada?: boolean;        // nubes_cuadricula ≤ nubes_max
    nubes_max?: number;
    revisadas?: number;
    candidatas?: number | unknown[]; // fechas con < 30 % de nubes en 18 meses
    vegetacion_cuadricula?: number;  // % de vegetación (SCL) en la toma elegida (se prefiere la época seca)
    nota?: string;
  };
  /** true = análisis «solo satélite» (sin zonas geológicas) */
  solo_satelite?: boolean;
  /** resumen de toda la cuadrícula (% de área) */
  celda?: {
    /** % de la cuadrícula en zonas A/B y lo que pasa los tres filtros (null en «solo satélite») */
    pct_interes?: number | null; pct_silice_limpia?: number | null;
    pct_oxidos_altos: number;
    pct_vegetacion_nubes_agua: number;
    pct_excluido_hierro_arcilla?: number; pct_hierro_alto?: number; pct_arcilla_alta?: number;
    /** % de la cuadrícula que cumple los tres filtros (NDVI, ferruginosa, arcilla) */
    pct_cumple?: number;
    /** % de los píxeles útiles marcados (sobre el percentil de corte) */
    anomalia_hierro_pct?: number; anomalia_arcilla_pct?: number;
  };
  /** cortes (percentil 0–1) desde los que hierro y arcilla excluyen de la Prioridad libre */
  cortes?: { p_ferruginosa?: number; arcilla: number; p_ndvi?: number; p_ferrico?: number; p_ferroso?: number };   // p_ferrico/p_ferroso: antiguos
  /** para recalcular en la app con otros cortes (cortes.ts): percentiles por píxel + histogramas reales */
  datos?: { formato?: number; rangos: string; base: string;
    hist: Partial<Record<"ferruginosa" | "arcilla" | "ndvi" | "bsi" | "ferrico" | "ferroso", HistogramaS2 | null>> };
  afloramientos?: StatSentinel[];
  pct_area_valida?: number;
  periodo?: string;
  nota?: string;
}

async function pedir<T>(ruta: string, cuerpo?: unknown, ms = 120000): Promise<T> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), ms);
  try {
    const r = await fetch(`${API_URL}${ruta}`, {
      method: cuerpo ? "POST" : "GET",
      headers: cuerpo ? { "Content-Type": "application/json" } : undefined,
      body: cuerpo ? JSON.stringify(cuerpo) : undefined,
      signal: ctrl.signal,
    });
    const datos = await r.json().catch(() => ({}));
    if (!r.ok) {
      const det = (datos as { detail?: unknown }).detail;
      throw new Error(typeof det === "string" ? det : `Error ${r.status} del servidor`);
    }
    return datos as T;
  } catch (e) {
    if ((e as Error).name === "AbortError") {
      throw new Error("El servidor tardó demasiado. Si es la primera consulta del día, espera 1 minuto y reintenta (el servidor gratuito se despierta).");
    }
    if (e instanceof TypeError) {
      throw new Error("Sin conexión con el servidor. Revisa tu internet.");
    }
    throw e;
  } finally {
    clearTimeout(t);
  }
}

export const api = {
  materiales: () => pedir<Material[]>("/materiales", undefined, 60000),
  estado: () => pedir<{ geocatmin: boolean | null; sentinel: boolean; geologia_local: Record<string, string> }>("/estado", undefined, 20000),
  buscar: (material: string, poligono: number[][]) =>
    pedir<ResultadoBusqueda>("/buscar", { material, poligono }),
  sentinel: (poligono: number[][], afloramientos: Afloramiento[]) =>
    pedir<ResultadoSentinel>("/sentinel", {
      poligono,
      afloramientos: afloramientos.map((a) => ({ id: a.id, clase: a.clase, geometria: a.geometria })),
    }, 180000),
  materiaVer: (id: string) => pedir<DefMateria>(`/materias_primas/${encodeURIComponent(id)}`),
  materiaGuardar: (d: DefMateria) => pedir<DefMateria>("/materias_primas", d),
  materiaBorrar: (id: string) => fetch(`${API_URL}/materias_primas/${encodeURIComponent(id)}`, { method: "DELETE" })
    .then(async (r) => { if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? `Error ${r.status}`); }),
  materiaProbar: (definicion: DefMateria, litologia: string, unidad = "", roca_dominante = "") =>
    pedir<{ clase: Clase | null; motivo: string }>("/materias_primas/probar", { definicion, litologia, unidad, roca_dominante }),
  formaciones: (material = "arena_silicea") =>
    pedir<Formacion[]>(`/formaciones?material=${encodeURIComponent(material)}`, undefined, 60000),
  hojasFormacion: (id: string, material = "arena_silicea") =>
    pedir<HojaFormacion[]>(`/formaciones/${encodeURIComponent(id)}/hojas?material=${encodeURIComponent(material)}`),
  filtroTexto: (texto: string) =>
    pedir<Formacion>(`/geologia/filtro?texto=${encodeURIComponent(texto)}`, undefined, 30000),
  hojasTexto: (texto: string) =>
    pedir<HojaFormacion[]>(`/geologia/hojas?texto=${encodeURIComponent(texto)}`),
  hojas100: () => pedir<{ codigo: string; nombre: string }[]>("/hojas100", undefined, 60000),
  restricciones: (poligono: number[][]) => pedir<Restriccion[]>("/restricciones", { poligono }, 90000),
  barridoIniciar: (celdas: { codigo: string; sur: number; oeste: number; norte: number; este: number }[], material = "arena_silicea") =>
    pedir<{ id: string; total: number }>("/barrido", { celdas, material }, 30000),
  barridoEstado: (id: string, desde: number) => pedir<EstadoBarrido>(`/barrido/${id}?desde=${desde}`, undefined, 30000),
  barridoCancelar: (id: string) => fetch(`${API_URL}/barrido/${id}`, { method: "DELETE" }).catch(() => undefined),
  curvas: (b: { sur: number; oeste: number; norte: number; este: number }, intervalo = 0) =>
    pedir<Curvas>(`/curvas?sur=${b.sur}&oeste=${b.oeste}&norte=${b.norte}&este=${b.este}&intervalo=${intervalo}`, undefined, 300000),
  tonelaje: (a: Afloramiento, opciones: { libre?: unknown; densidad?: number; potencia_manto?: number; potencia_max?: number } = {}) =>
    pedir<Tonelaje>("/tonelaje", {
      geometria: a.geometria, libre: opciones.libre ?? null, densidad: opciones.densidad ?? null,
      potencia_manto: opciones.potencia_manto ?? null, potencia_max: opciones.potencia_max ?? null,
      zona: { unidad: a.unidad, litologia: a.litologia, descripcion: a.descripcion, roca_dominante: a.roca_dominante },
    }, 300000),
  ruta: (fabrica: [number, number], lat: number, lon: number) =>
    pedir<Ruta>(`/ruta?lat1=${fabrica[0]}&lon1=${fabrica[1]}&lat2=${lat}&lon2=${lon}`, undefined, 60000),
  libres: (poligono: number[][], zonas: { id: string; geometria: unknown; clase?: string; unidad?: string; litologia?: string }[] = []) =>
    pedir<{
      restricciones: Restriccion[]; libres: Libres;
      zonas: Record<string, { libre_pct: number | null; util_pct: number | null; negociable_pct?: number | null; concesiones: ConcesionEnZona[]; restriccion: RestriccionZona | null }>;
    }>("/libres", { poligono, zonas }, 120000),
  /** URL de la lámina de áreas libres de una vista del mapa (PNG transparente). */
  urlLibres: (b: { oeste: number; sur: number; este: number; norte: number }, ancho: number, alto: number, modo: "mapa" | "prioridad" = "mapa") =>
    `${API_URL}/libres/imagen?oeste=${b.oeste.toFixed(4)}&sur=${b.sur.toFixed(4)}&este=${b.este.toFixed(4)}&norte=${b.norte.toFixed(4)}&ancho=${ancho}&alto=${alto}${modo === "prioridad" ? "&modo=prioridad" : ""}`,
  bibliografia: (b: { sur: number; oeste: number; norte: number; este: number }) =>
    pedir<Bibliografia>(`/bibliografia?sur=${b.sur}&oeste=${b.oeste}&norte=${b.norte}&este=${b.este}`, undefined, 90000),
  /** Lámina PNG del mapa geológico de la cuadrícula (con leyenda). */
  /** Lámina cartográfica profesional (PNG A3): ver backend/laminas.py. */
  async lamina(p: Record<string, unknown>): Promise<Blob> {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 240000);
    try {
      const r = await fetch(`${API_URL}/lamina`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(p), signal: ctrl.signal,
      });
      if (!r.ok) {
        const det = (await r.json().catch(() => ({}))) as { detail?: string };
        throw new Error(det.detail ?? `Error ${r.status} del servidor`);
      }
      return await r.blob();
    } catch (e) {
      if ((e as Error).name === "AbortError") throw new Error("La lámina tardó demasiado. Intenta de nuevo.");
      throw e;
    } finally {
      clearTimeout(t);
    }
  },
  /** INFORME en el servidor: todas las páginas en paralelo; se consulta el avance y se baja el PDF. */
  informeIniciar: (cuerpo: { titulo: string; nombre: string; paginas: Record<string, unknown>[] }) =>
    pedir<{ id: string; total: number }>("/informe", cuerpo, 180000),
  informeEstado: (id: string) =>
    pedir<{ estado: "trabajando" | "listo" | "error"; total: number; hechas: number; errores: string[]; mb: number | null }>(`/informe/${id}`, undefined, 30000),
  async informePdf(id: string): Promise<Blob> {
    const r = await fetch(`${API_URL}/informe/${id}/pdf`);
    if (!r.ok) throw new Error(`Error ${r.status} al bajar el PDF`);
    return r.blob();
  },
  /** Capas SIG de la cuadrícula (KMZ o shapefile en ZIP): ver backend/exportar_sig.py. */
  async exportar(cuerpo: Record<string, unknown>): Promise<Blob> {
    const r = await fetch(`${API_URL}/exportar`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo) });
    if (!r.ok) {
      const det = (await r.json().catch(() => ({}))) as { detail?: string };
      throw new Error(det.detail ?? `Error ${r.status} del servidor`);
    }
    return r.blob();
  },
  /** Une láminas PNG (data URL) en un PDF de varias páginas. */
  async pdf(paginas: string[], titulo: string): Promise<Blob> {
    const r = await fetch(`${API_URL}/pdf`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ paginas, titulo }) });
    if (!r.ok) {
      const det = (await r.json().catch(() => ({}))) as { detail?: string };
      throw new Error(det.detail ?? `Error ${r.status} del servidor`);
    }
    return r.blob();
  },
  async mapaGeologico(b: { sur: number; oeste: number; norte: number; este: number }, escala: "50K" | "100K", titulo: string): Promise<Blob> {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 180000);
    try {
      const r = await fetch(`${API_URL}/mapa_geologico?sur=${b.sur}&oeste=${b.oeste}&norte=${b.norte}&este=${b.este}`
        + `&escala=${escala}&titulo=${encodeURIComponent(titulo)}`, { signal: ctrl.signal });
      if (!r.ok) {
        const det = (await r.json().catch(() => ({}))) as { detail?: string };
        throw new Error(det.detail ?? `Error ${r.status} del servidor`);
      }
      return await r.blob();
    } catch (e) {
      if ((e as Error).name === "AbortError") throw new Error("GEOCATMIN tardó demasiado en entregar el mapa. Intenta de nuevo.");
      throw e;
    } finally {
      clearTimeout(t);
    }
  },
};

export const MATERIALES_RESPALDO: Material[] = [
  { id: "arena_silicea", nombre: "Arena silícea", activo: true, sinonimos: ["silice", "sílice", "cuarzo", "cuarcita", "arenisca cuarzosa", "vidrio"] },
];
