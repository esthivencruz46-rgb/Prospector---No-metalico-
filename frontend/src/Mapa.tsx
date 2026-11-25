import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import L from "leaflet";
import { dynamicMapLayer } from "esri-leaflet";
import "leaflet/dist/leaflet.css";
import "./esriParche"; // evita errores al apagar capas GEOCATMIN mientras cargan
import { api, type Ruta, type Afloramiento, type Formacion, type ResultadoSentinel, type StatSentinel } from "./api";
import { celda25, celdasEnVista, distanciaKm, esquinasC100, formatoKm, gms, utm, utmAGeo, type Celda, type Cuadricula100 } from "./geo";

/** Cuadrícula ya analizada (se marca en el mapa). */
export interface MarcaCelda {
  codigo: string;
  clase: "A" | "B" | "C" | null; // mejor clase encontrada
  etiqueta: string; // p. ej. "✓ A1 C2" o "★ A1" (★ = guardada en carpeta)
}

const GEOCATMIN = "https://geocatmin.ingemmet.gob.pe/arcgis/rest/services";
export const COLOR_CLASE = { A: "#dc2626", B: "#f59e0b", C: "#facc15" } as const;
/** Opacidad por defecto de la geología de INGEMMET (24/11/2026: más transparente; el usuario la cambia con su deslizador). */
export const GEO_OPACIDAD: Partial<Record<IdCapa, number>> = { geo50: 0.3, geo100: 0.3, geo50_si: 0.4, geo100_si: 0.4 };
export type NivelVidrio = "alta" | "media" | "baja" | "no";
/** Estilo de una zona A/B/C: resaltada si es apta para vidrio, tenue si no; la elegida en celeste. */
function estiloZona(a: Afloramiento, nv: NivelVidrio | undefined, sel: string | null, soloBorde = false): L.PathOptions {
  const o = estiloZonaBase(a, nv, sel);
  // con un índice satelital a la vista (NDVI, BSI, ferruginosa, arcillas) las zonas van SIN relleno: el relleno
  // naranja/rojo de la clase teñía los colores del índice
  return soloBorde ? { ...o, fillOpacity: 0 } : o;
}
function estiloZonaBase(a: Afloramiento, nv: NivelVidrio | undefined, sel: string | null): L.PathOptions {
  const color = COLOR_CLASE[a.clase];
  if (sel === a.id) return { color: "#22d3ee", weight: 4.5, opacity: 1, fillColor: color, fillOpacity: 0.5, dashArray: undefined };
  const atenuar = sel ? 0.45 : 1;   // hay otra elegida: esta pasa a segundo plano
  if (!nv) return { color, weight: a.clase === "A" ? 2.5 : 1.8, opacity: atenuar, fillColor: color,
    fillOpacity: (a.clase === "C" ? 0.15 : 0.3) * atenuar, dashArray: a.clase === "C" ? "4 4" : undefined };
  if (nv === "alta") return { color, weight: 3.5, opacity: atenuar, fillColor: color, fillOpacity: 0.5 * atenuar, dashArray: undefined };
  if (nv === "media") return { color, weight: 2.8, opacity: atenuar, fillColor: color, fillOpacity: 0.36 * atenuar, dashArray: undefined };
  if (nv === "baja") return { color, weight: 1.2, opacity: 0.7 * atenuar, fillColor: color, fillOpacity: 0.1 * atenuar, dashArray: "3 4" };
  return { color: "#94a3b8", weight: 1, opacity: 0.55 * atenuar, fillColor: "#94a3b8", fillOpacity: 0.04 * atenuar, dashArray: "2 5" };
}

/** nombre corto para la etiqueta del mapa: «Grupo Goyllarisquizga - Formación Farrat» → «Fm. Farrat» */
const nombreCorto = (u: string) => u.replace(/^Grupo [^-]+ - /, "").replace(/^Formación /, "Fm. ").replace(/^Grupo /, "Gr. ")
  .replace(/^Depósitos? /, "Dep. ").replace(/ - Miembro /, " · Mb. ");

export type IdCapa =
  | "geo50" | "geo100" | "geo50_si" | "geo100_si" | "catastro" | "restringidas"
  | "areas_libres" | "catastro_nm"
  | "resultados" | "s2_arcillas"
  | "s2_prioridad_libre" | "s2_natural" | "s2_swir" | "s2_ndvi" | "s2_bsi" | "s2_ferruginosas"
  | "fabrica" | "cuadricula";

/** Capas con interruptor, agrupadas por la pregunta que responden (las de Sentinel-2 se eligen
 *  aparte: ver App.tsx VISTAS_S2). */
export const CAPAS: { id: IdCapa; nombre: string; nota?: string; grupo: "geo" | "ref" | "derechos" | "s2" }[] = [
  { id: "resultados", nombre: "Zonas favorables A/B/C", nota: "de la cuadrícula analizada", grupo: "geo" },
  { id: "geo50_si", nombre: "Rocas silíceas · 1:50 000", nota: "cuarcita, arenisca y arena cuarzosa", grupo: "geo" },
  { id: "geo100_si", nombre: "Rocas silíceas · 1:100 000", nota: "úsala donde la 1:50 000 no muestra nada", grupo: "geo" },
  { id: "geo50", nombre: "Mapa geológico completo · 1:50 000", nota: "todas las rocas (contexto)", grupo: "geo" },
  { id: "geo100", nombre: "Mapa geológico completo · 1:100 000", grupo: "geo" },
  { id: "areas_libres", nombre: "🟩 Áreas libres", nota: "verde = se puede pedir · celeste = extinguida, falta publicarse · ámbar = libre pero chacra, pueblo, vía o río", grupo: "derechos" },
  { id: "restringidas", nombre: "⛔ Áreas protegidas y restringidas", nota: "ANP, arqueológicas, urbanas, forestales…", grupo: "derechos" },
  { id: "catastro", nombre: "Concesiones mineras", nota: "toca una para ver su ficha", grupo: "derechos" },
  { id: "catastro_nm", nombre: "⛏ Solo concesiones NO metálicas", nota: "indicio de canteras de arena, sílice, caliza…", grupo: "derechos" },
  { id: "fabrica", nombre: "🏭 Fábrica", nota: "San Vicente de Cañete (fija)", grupo: "ref" },
  { id: "cuadricula", nombre: "Cuadrícula 1:25 000", nota: "tócala para analizarla · zoom ≥ 8", grupo: "ref" },
  { id: "s2_arcillas", nombre: "Arcillas", grupo: "s2" },
  { id: "s2_prioridad_libre", nombre: "Prioridad libre", grupo: "s2" },
  { id: "s2_ndvi", nombre: "NDVI", grupo: "s2" },
  { id: "s2_bsi", nombre: "BSI", grupo: "s2" },
  { id: "s2_ferruginosas", nombre: "Anomalías ferruginosas (férrico + ferroso)", grupo: "s2" },
  { id: "s2_natural", nombre: "Color natural", grupo: "s2" },
  { id: "s2_swir", nombre: "Geología SWIR", grupo: "s2" },
];

/** Capa satelital del mapa: claves posibles en ResultadoSentinel.capas (la primera que exista;
 *  así los análisis guardados antes de unir el hierro siguen mostrando sus óxidos), opacidad y
 *  orden de apilado (z): las fotos opacas abajo y lo pequeño y crítico (hierro, arcillas) arriba, para que al superponer nada importante quede tapado. */
export const CAPAS_SATELITE: Partial<Record<IdCapa, { claves: string[]; opacidad: number; z: number }>> = {
  s2_natural: { claves: ["natural"], opacidad: 1, z: 1 },
  s2_swir: { claves: ["swir"], opacidad: 1, z: 1 },
  // escala continua al 100 % de los datos: encima de las fotos y debajo de los índices; transparencia a elección
  s2_ndvi: { claves: ["ndvi"], opacidad: 0.6, z: 2 },
  s2_bsi: { claves: ["bsi"], opacidad: 0.6, z: 2 },
  s2_ferruginosas: { claves: ["ferruginosas"], opacidad: 0.6, z: 3 },
  // Prioridad libre: la compone la app (prioridadLibre.ts), no viene del backend; va encima de todo
  s2_prioridad_libre: { claves: ["prioridad_libre"], opacidad: 0.95, z: 10 },
  s2_arcillas: { claves: ["arcillas"], opacidad: 0.9, z: 7 },
};

/** URL de la imagen de una capa satelital en un análisis (o undefined si no la trae). */
/** Colores de los tramos de ruta (iguales a COLOR_TRAMO de App.tsx). */
const COLOR_TRAMO_MAPA: Record<string, string> = { pista: "#3b82f6", trocha: "#b45309", a_pie: "#ec4899" };

export function urlSatelite(capas: Record<string, string> | undefined, id: IdCapa): string | undefined {
  for (const k of CAPAS_SATELITE[id]?.claves ?? []) if (capas?.[k]) return capas[k];
  return undefined;
}

export interface MapaHandle {
  irA: (afl: Afloramiento) => void;
  irAPunto: (lat: number, lon: number, zoom?: number) => void;
  vistaComoPoligono: () => number[][];
  encuadrar: (poligono: number[][]) => void;
  cerrarFichas: () => void;
}

/** Capa «Áreas libres»: pide al backend una imagen de la vista actual cada vez que el mapa
 *  se mueve (con espera de 400 ms) y la cambia solo cuando la nueva terminó de cargar. */
const LIMITES_PERU = L.latLngBounds([-18.6, -81.6], [0.2, -68.4]);
class CapaLibres extends L.Layer {
  private imagen: L.ImageOverlay | null = null;
  private espera: number | undefined;
  private pedido = 0;
  private limite: L.LatLngBounds | null = null;
  /** Con «solo esta cuadrícula» se pide solo ese recuadro (menos datos, más rápido). */
  setLimite(b: L.LatLngBounds | null) {
    this.limite = b;
    if (this._map) this.actualizar();
  }
  onAdd(m: L.Map) {
    m.on("moveend", this.programar, this);
    this.actualizar();
    return this;
  }
  onRemove(m: L.Map) {
    m.off("moveend", this.programar, this);
    window.clearTimeout(this.espera);
    this.pedido++;
    if (this.imagen) m.removeLayer(this.imagen);
    this.imagen = null;
    m.getContainer().classList.remove("cargando-libres");
    return this;
  }
  private programar() {
    window.clearTimeout(this.espera);
    this.espera = window.setTimeout(() => this.actualizar(), 400);
  }
  private actualizar() {
    const m = this._map;
    if (!m) return;
    const vista = m.getBounds();
    const tope = this.limite ?? LIMITES_PERU;
    if (!vista.intersects(tope)) {
      if (this.imagen) { m.removeLayer(this.imagen); this.imagen = null; }
      return;
    }
    const b = L.latLngBounds(
      [Math.max(vista.getSouth(), tope.getSouth()), Math.max(vista.getWest(), tope.getWest())],
      [Math.min(vista.getNorth(), tope.getNorth()), Math.min(vista.getEast(), tope.getEast())]);
    const a = m.latLngToContainerPoint(b.getNorthWest()), z = m.latLngToContainerPoint(b.getSouthEast());
    const ancho = Math.round(z.x - a.x), alto = Math.round(z.y - a.y);
    if (ancho < 8 || alto < 8) return;
    const url = api.urlLibres({ oeste: b.getWest(), sur: b.getSouth(), este: b.getEast(), norte: b.getNorth() },
      Math.min(ancho, 2048), Math.min(alto, 2048));
    const n = ++this.pedido;
    m.getContainer().classList.add("cargando-libres");
    const nueva = L.imageOverlay(url, b, { pane: "libres", opacity: 0.7, interactive: false });
    const listo = (ok: boolean) => {
      if (n !== this.pedido || !this._map) { m.removeLayer(nueva); return; }
      m.getContainer().classList.remove("cargando-libres");
      if (!ok) { m.removeLayer(nueva); return; }
      if (this.imagen) m.removeLayer(this.imagen);
      this.imagen = nueva;
    };
    nueva.once("load", () => listo(true)).once("error", () => listo(false)).addTo(m);
  }
}

interface Props {
  /** filtro SQL de las «rocas de interés» de la materia prima elegida (sin él: las silíceas) */
  sqlInteres?: { sql50?: string; sql100?: string };
  area: number[][] | null; // [lng, lat] cuadrícula analizada
  afloramientos: Afloramiento[];
  sentinel: ResultadoSentinel | null;
  statsPorId: Record<string, StatSentinel>;
  /** aptitud para vidrio de cada zona según su descripción (vidrio.ts): resalta las aptas, atenúa las demás */
  vidrio?: Record<string, NivelVidrio>;
  /** zona elegida en la lista: se resalta en celeste y las demás se atenúan */
  zonaSel?: string | null;
  /** zonas solo con borde (hay un índice satelital a la vista) */
  zonasSoloBorde?: boolean;
  capas: Record<IdCapa, boolean>;
  /** opacidad (0–1) elegida por el usuario para cada capa satelital; sin valor = la de CAPAS_SATELITE */
  opacidades?: Partial<Record<IdCapa, number>>;
  base: "satelite" | "mapa" | "relieve";
  /** posición del cursor (laptop) o centro del mapa (celular), para la barra de coordenadas */
  onCursor?: (lat: number, lon: number) => void;
  ubicacion: [number, number] | null;
  formacion: Formacion | null; // formación elegida en el catálogo
  fabrica: [number, number]; // [lat, lon]
  celdaSel: Celda | null;
  /** «Solo esta cuadrícula»: se oscurece todo lo que está fuera de ella. */
  foco: { codigo: string; sur: number; oeste: number; norte: number; este: number } | null;
  resaltado: { codigo: string; sur: number; oeste: number; norte: number; este: number } | null; // hoja buscada
  analizadas: MarcaCelda[];
  destino: { lat: number; lon: number } | null; // línea fábrica → destino
  ruta?: Ruta | null;                          // ruta fábrica → destino, por tramos (pista / trocha / a pie)
  /** barrido de región: cuadrículas pintadas por puntaje (1 = la mejor) */
  barrido?: { codigo: string; sur: number; oeste: number; norte: number; este: number; puntaje: number | null; puesto: number | null }[];
  /** petitorio: grilla de cuadrículas de 100 ha (1 km UTM WGS84) y las elegidas */
  petitorio?: { activo: boolean; celdas: Cuadricula100[] };
  /** curvas de nivel (Copernicus DEM) de la cuadrícula: imagen + límites */
  curvas?: { png: string; sur: number; oeste: number; norte: number; este: number } | null;
  // sobreResultado: el toque cayó sobre un afloramiento o cantera
  onClickMapa: (lat: number, lng: number, sobreResultado: boolean) => void;
  /** Clic derecho (laptop) o 1 toque (celular): ver solo la cuadrícula tocada. */
  onEnfocar: (lat: number, lng: number, sobreResultado: boolean) => void;
  /** Clic izquierdo (laptop) o 2 toques (celular): volver a ver todo el mapa. */
  onVerTodo: () => void;
}

function lineaKm(fabrica: [number, number], lat: number, lon: number): string {
  return `<br/><b>Fábrica:</b> ${formatoKm(distanciaKm(fabrica[0], fabrica[1], lat, lon))} en línea recta`;
}

// GEOCATMIN no envía cabeceras CORS: f:"image" + useCors:false son
// OBLIGATORIOS (lección de MineLINK, errores_aprendidos.md 14/07/2026).
// Sin eso la capa desaparece en silencio.
const opcionesImagen = { f: "image", useCors: false, attribution: "GEOCATMIN · INGEMMET" };

// Filtro SQL que GEOCATMIN aplica en su servidor (layerDefs): solo polígonos
// cuya litología/descripción nombra una roca sedimentaria silícea. Términos
// sueltos como "cuarzo" o "sílice" NO entran: traerían "diorita cuarzosa",
// "andesita con cristales de cuarzo", "calizas silicificadas"… (verificado
// en los datos: 50K ≈ 16 mil de 157 mil polígonos; 100K ≈ 9.8 mil de 113 mil).
// Es un filtro VISUAL amplio; la clase A/B/C la decide materiales.py al buscar.
function sqlSilice(campos: string[]): string {
  // «ARENA%CUARZOS»: «arenas eólicas, cuarzosas…», «arenas de cuarzosas…» (depósitos eólicos de la 50K)
  const terminos = ["ARENISCA CUARZOSA", "ARENISCAS CUARZOSAS", "ARENA CUARZOSA", "ARENAS CUARZOSAS", "ARENA%CUARZOS",
    "CUARCIT", "CUARCÍT", "CUARZOARENIT", "ARENA SIL", "ARENAS SIL"];
  return campos.flatMap((c) => terminos.map((t) => `UPPER(${c}) LIKE '%${t}%'`)).join(" OR ");
}

function escapar(s: unknown): string {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]!));
}

export function popupAfloramiento(a: Afloramiento, st: StatSentinel | undefined, fabrica: [number, number]): string {
  const satelite = (st?.anomalia_hierro_pct != null ? `<br/><b>Sentinel-2:</b> hierro ${st.anomalia_hierro_pct} % · arcilla ${st.anomalia_arcilla_pct ?? "—"} % de lo visible` : "")
    + (st?.limpia_pct != null ? ` · <b>${st.limpia_pct} % limpia</b>` : "")
    + (st?.ndvi_pct != null ? `<br/><b>NDVI</b> ${st.ndvi_pct} · <b>BSI</b> ${st.bsi_pct ?? "—"} · <b>ferruginosa</b> ${st.ferruginosa_pct ?? "—"} <small>(0–100 en la cuadrícula)</small>` : "")
;
  return `<div class="pop">
    <span class="badge" style="background:${COLOR_CLASE[a.clase]}">${a.clase}</span>
    <b>${escapar(a.unidad)}</b> <small>(${a.escala})</small><br/>
    ${a.litologia ? `<small>Litología:</small> <b>${escapar(a.litologia)}</b><br/>` : ""}
    ${((a.rocas?.length ? a.rocas : a.roca_dominante ? [a.roca_dominante] : []) as string[])
      .map((r, k) => `<small>${["Roca principal", "Roca secundaria", "Roca terciaria"][k]}:</small> <b>${escapar(r)}</b><br/>`).join("")}
    ${a.descripcion && a.descripcion !== a.litologia ? `<small>Descripción:</small> ${escapar(a.descripcion)}<br/>` : ""}
    <i>${escapar(a.motivo)}</i><br/>
    <b>Área en tu zona:</b> ${a.area_ha.toLocaleString("es-PE")} ha${satelite}${lineaKm(fabrica, a.centro[1], a.centro[0])}
  </div>`;
}

// fábrica: marcador sobrio (cobre) con el ícono de planta industrial
const ICONO_FABRICA = L.divIcon({
  className: "icono-fabrica", iconSize: [30, 38], iconAnchor: [15, 36],
  html: '<svg viewBox="0 0 30 38" width="30" height="38"><path d="M15 37 C15 37 2 22 2 14 a13 13 0 0 1 26 0 c0 8-13 23-13 23z" fill="#c08a4a" stroke="#1a1208" stroke-width="1.5"/>'
    + '<path d="M8 19 v-6 l4 2.5 v-2.5 l4 2.5 v-2.5 l4 2.5 v-5 h2 v8.5 z" fill="#1a1208"/></svg>',
});

const Mapa = forwardRef<MapaHandle, Props>(function Mapa(p, ref) {
  const divRef = useRef<HTMLDivElement>(null);
  const mapa = useRef<L.Map | null>(null);
  const bases = useRef<Record<string, L.Layer>>({});
  const capasRef = useRef<Partial<Record<IdCapa, L.Layer>>>({});
  const dibujo = useRef<L.LayerGroup | null>(null);
  const resultados = useRef<L.LayerGroup | null>(null);
  const capasAfl = useRef<Record<string, L.GeoJSON>>({});
  const marcaUbicacion = useRef<L.CircleMarker | null>(null);
  const grilla = useRef<L.LayerGroup | null>(null);
  const seleccion = useRef<L.LayerGroup | null>(null);
  const marcaFabrica = useRef<L.Marker | null>(null);
  const capaFormacion = useRef<L.LayerGroup | null>(null);
  const capaAnalizadas = useRef<L.LayerGroup | null>(null);
  const fabricaRef = useRef(p.fabrica);
  fabricaRef.current = p.fabrica;
  const clicEnResultado = useRef(false);
  const onClickRef = useRef(p.onClickMapa);
  const verGrillaRef = useRef(p.capas.cuadricula);
  onClickRef.current = p.onClickMapa;
  const onEnfocarRef = useRef(p.onEnfocar);
  const onVerTodoRef = useRef(p.onVerTodo);
  onEnfocarRef.current = p.onEnfocar;
  onVerTodoRef.current = p.onVerTodo;
  verGrillaRef.current = p.capas.cuadricula;
  const onCursorRef = useRef(p.onCursor);
  onCursorRef.current = p.onCursor;

  // ---- cuadrícula 50K (gruesa) / 25K (fina), solo lo visible
  function dibujarGrilla() {
    const m = mapa.current, g = grilla.current;
    if (!m || !g) return;
    g.clearLayers();
    const z = m.getZoom();
    if (!verGrillaRef.current || z < 8) return;
    const b = m.getBounds().pad(0.1);
    const s = b.getSouth(), o = b.getWest(), n = b.getNorth(), e = b.getEast();
    const rect = (c: Celda) => [[c.sur, c.oeste], [c.norte, c.este]] as L.LatLngBoundsExpression;
    const etiqueta = (c: Celda, clase: string) =>
      L.marker([c.norte, c.oeste], {
        pane: "cuadricula", interactive: false, keyboard: false,
        icon: L.divIcon({ className: `etq-celda ${clase}`, html: c.codigo, iconSize: undefined as any, iconAnchor: [-4, -4] }),
      }).addTo(g);
    if (z >= 10) {
      for (const c of celdasEnVista(s, o, n, e, "25K")) {
        L.rectangle(rect(c), { pane: "cuadricula", color: "#f8fafc", weight: 1, dashArray: "5 5", fill: false, interactive: false }).addTo(g);
        if (z >= 11) etiqueta(c, "e25");
      }
    }
    for (const c of celdasEnVista(s, o, n, e, "50K")) {
      L.rectangle(rect(c), { pane: "cuadricula", color: "#f8fafc", weight: 2.5, fill: false, interactive: false }).addTo(g);
      if (z >= 9 && z < 11) etiqueta(c, "e50");
    }
  }

  // ---- creación del mapa (una vez)
  useEffect(() => {
    if (!divRef.current || mapa.current) return;
    const m = L.map(divRef.current, { zoomControl: false, attributionControl: true, minZoom: 4 })
      .setView(p.fabrica, 10);
    L.control.zoom({ position: "bottomright" }).addTo(m);
    L.control.scale({ imperial: false, position: "bottomleft" }).addTo(m);
    m.createPane("geologia").style.zIndex = "350";
    const paneGrilla = m.createPane("cuadricula");
    paneGrilla.style.zIndex = "360";
    paneGrilla.style.pointerEvents = "none";
    m.createPane("sentinel").style.zIndex = "370";
    m.createPane("catastro").style.zIndex = "380";

    bases.current.satelite = L.layerGroup([
      L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", { maxZoom: 19, attribution: "Esri World Imagery" }),
      L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}", { maxZoom: 19 }),
    ]);
    bases.current.mapa = L.tileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", { maxZoom: 17, attribution: "OpenTopoMap · OSM" });
    // relieve sombreado (lectura geomorfológica) + límites y poblados
    bases.current.relieve = L.layerGroup([
      L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Elevation/World_Hillshade/MapServer/tile/{z}/{y}/{x}", { maxZoom: 19, attribution: "Esri World Hillshade" }),
      L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}", { maxZoom: 19 }),
    ]);

    const op = (id: IdCapa) => p.opacidades?.[id] ?? GEO_OPACIDAD[id] ?? 0.5;
    const geo100 = dynamicMapLayer({ url: `${GEOCATMIN}/SERV_GEOLOGIA_100K_INTEGRADA/MapServer`, layers: [6], opacity: op("geo100"), pane: "geologia", zIndex: 10, ...opcionesImagen } as any);
    const geo50 = dynamicMapLayer({ url: `${GEOCATMIN}/SERV_GEOLOGIA_50K_INTEGRADA/MapServer`, layers: [7], opacity: op("geo50"), pane: "geologia", zIndex: 11, ...opcionesImagen } as any);
    const geo100_si = dynamicMapLayer({ url: `${GEOCATMIN}/SERV_GEOLOGIA_100K_INTEGRADA/MapServer`, layers: [6], layerDefs: { 6: sqlSilice(["DESCRIP"]) }, opacity: op("geo100_si"), pane: "geologia", zIndex: 12, ...opcionesImagen } as any);
    const geo50_si = dynamicMapLayer({ url: `${GEOCATMIN}/SERV_GEOLOGIA_50K_INTEGRADA/MapServer`, layers: [7], layerDefs: { 7: sqlSilice(["LITOLOGIA", "DESCRIP"]) }, opacity: op("geo50_si"), pane: "geologia", zIndex: 13, ...opcionesImagen } as any);
    // Clic en la geología → unidad y litología (identify por JSONP gracias a useCors:false)
    for (const [capa, escala] of [[geo50, "50K"], [geo100, "100K"], [geo50_si, "50K"], [geo100_si, "100K"]] as const) {
      (capa as any).bindPopup((err: unknown, fc: any) => {
        if (err) return false;
        const a = fc?.features?.[0]?.properties;
        if (!a) return false;
        // el «identify» puede traer los campos por nombre o por alias: se buscan sin importar mayúsculas/espacios
        const campo = (...nombres: string[]) => {
          for (const [k, v] of Object.entries(a)) {
            const kk = k.toUpperCase().replace(/[^A-Z0-9]/g, "");
            if (nombres.includes(kk)) {
              const t = String(v ?? "").trim();
              if (t && !["NULL", "<NULL>", "-"].includes(t.toUpperCase())) return t;
            }
          }
          return "";
        };
        const lito = campo("LITOLOGIA"), desc = campo("DESCRIP", "DESCRIPCION"), nombre = campo("NAME");
        const rocas = [campo("LITO1"), campo("LITO2"), campo("LITO3")];
        const fila = (t: string, v: string) => (v ? `<small>${t}:</small> <b>${escapar(v)}</b><br/>` : "");
        return `<div class="pop"><b>${escapar(campo("UNIDAD") || nombre)}</b> <small>(${escala === "50K" ? "1:50 000" : "1:100 000"})</small><br/>`
          + fila("Litología", lito) + fila("Roca principal", rocas[0]) + fila("Roca secundaria", rocas[1]) + fila("Roca terciaria", rocas[2])
          + (desc && desc !== lito ? `<small>Descripción:</small> ${escapar(desc)}<br/>` : "")
          + (escala === "100K" && nombre ? fila("Código", nombre) : "")
          + `<small>GEOCATMIN · INGEMMET</small></div>`;
      });
    }
    // Áreas protegidas y restringidas para concesiones (mismas capas que consulta backend/restricciones.py).
    // INGEMMET las dibuja en colores muy claros (verde lima, menta, lila) y su servicio NO admite cambiar
    // la simbología (supportsDynamicLayers = false): se oscurecen en el navegador con un filtro CSS en
    // su propio panel, encima de la geología y del catastro.
    const panelRestr = m.createPane("restringidas");
    panelRestr.style.zIndex = "385";
    panelRestr.style.filter = "saturate(2.6) brightness(0.62) contrast(1.35)";
    const restringidas = dynamicMapLayer({
      url: `${GEOCATMIN}/SERV_AREA_RESERVADA/MapServer`,
      layers: [10, 11, 7, 1, 3, 4, 0, 6, 5, 8, 9, 19, 20, 13, 17, 14, 16, 12, 21, 18],
      opacity: 0.82, pane: "restringidas", ...opcionesImagen,
    } as any);
    (restringidas as any).bindPopup((err: unknown, fc: any) => {
      if (err) return false;
      const a = fc?.features?.[0]?.properties;
      if (!a) return false;
      const indirecto = String(a.USO ?? "").toUpperCase().includes("INDIRECTO");
      return `<div class="pop"><b>${escapar(a.NOMBRE)}</b><br/>${escapar(a.CATEGORI)}${a.USO ? ` · uso ${escapar(a.USO)}` : ""}`
        + `${indirecto ? "<br/><b style='color:#f87171'>⛔ ANP de uso indirecto: no se permite minería</b>" : ""}`
        + `<br/><small>${escapar(a.NORMA)}</small><br/><small>Área restringida · GEOCATMIN · INGEMMET</small></div>`;
    });
    // Concesiones forestales vigentes o suspendidas (catastro forestal; igual que backend/restricciones.FORESTAL).
    // Este servicio sí admite simbología propia: verde bosque con trama, para distinguirlas de las ANP.
    const forestales = dynamicMapLayer({
      url: `${GEOCATMIN}/SERV_CATASTRO_FORESTAL/MapServer`, opacity: 0.85, pane: "restringidas", ...opcionesImagen,
      // esri-leaflet 3 pasa dynamicLayers tal cual a la URL: debe ir ya como texto JSON
      dynamicLayers: JSON.stringify([{
        id: 0, source: { type: "mapLayer", mapLayerId: 0 }, definitionExpression: "ESTCON_DES <> 'EXTINGUIDO'",
        drawingInfo: { showLabels: false, renderer: { type: "simple", symbol: {
          type: "esriSFS", style: "esriSFSBackwardDiagonal", color: [22, 101, 52, 255],
          outline: { type: "esriSLS", style: "esriSLSSolid", color: [22, 101, 52, 255], width: 1.6 } } } },
      }]),
    } as any);
    (forestales as any).bindPopup((err: unknown, fc: any) => {
      if (err) return false;
      const a = fc?.features?.[0]?.properties;
      if (!a) return false;
      return `<div class="pop"><b>🌳 Concesión forestal</b> <small>${escapar(a.ESTCON_DES)}</small><br/>`
        + `${escapar(a.NOMTIT)}<br/>${escapar(a.TP_CONCE)} · contrato ${escapar(a.CONTRA)}`
        + `<br/>${Number(a.SUPSIG || 0).toLocaleString("es-PE", { maximumFractionDigits: 0 })} ha`
        + `<br/><small>Se puede pedir concesión minera encima, pero para operar hay que respetar el derecho forestal y obtener la opinión de SERFOR / autoridad regional.</small></div>`;
    });
    const restringidasYForestales = L.layerGroup([restringidas, forestales]);
    // Áreas libres: lámina del backend (catastro + áreas reservadas restados píxel a píxel), debajo
    // del catastro y de las restringidas para que sus bordes se sigan viendo encima
    m.createPane("libres").style.zIndex = "375";
    function popupCatastro(err: unknown, fc: any) {
          if (err) return false;
          const a = fc?.features?.[0]?.properties;
          if (!a) return false;
          // Derecho de Vigencia: US$ 3/ha régimen general, 1 PPM (CALIFICA «M»), 0,5 PMA («A»)
          const tarifa = a.CALIFICA === "M" ? 1 : a.CALIFICA === "A" ? 0.5 : 3;
          const vigente = ["TITULADO", "TRAMITE"].includes(String(a.LEYENDA ?? "").toUpperCase());
          const ha = Number(a.HECTAGIS) || 0;
          const fecha = (ms: unknown) => (ms ? new Date(Number(ms)).toISOString().slice(0, 10) : "");
          return `<div class="pop"><b>⛏ ${escapar(a.CONCESION)}</b> <small>${escapar(a.CODIGOU)}</small><br/>`
            + `${escapar(a.TIT_CONCES)}<br/><b>${escapar(a.D_ESTADO || a.LEYENDA)}</b><br/>`
            + `${ha.toLocaleString("es-PE")} ha · ${a.SUSTANCIA === "N" ? "no metálica" : a.SUSTANCIA === "M" ? "metálica" : escapar(a.SUSTANCIA)}`
            + ` · ${a.CALIFICA === "M" ? "PPM" : a.CALIFICA === "A" ? "PMA" : "régimen general"}<br/>`
            + `Petitorio: ${fecha(a.FEC_DENU)} ${escapar(a.HOR_DENU ?? "")}`
            + (vigente && ha ? `<br/>Derecho de Vigencia ≈ <b>US$ ${(ha * tarifa).toLocaleString("es-PE")}/año</b>` : "")
            + (a.RESOL_EXTI ? `<br/><b style="color:#f59e0b">⚠ Resolución de extinción ${escapar(a.RESOL_EXTI)} ${fecha(a.FECHA_RESOL_EXTI)}</b>` : "")
            + `<br/><small>El pago se verifica en SIDEMCAT (INGEMMET). Ficha completa: analiza la cuadrícula → Zonas → derechos mineros.</small></div>`;
    }
    capasRef.current = {
      geo100, geo50, geo100_si, geo50_si, restringidas: restringidasYForestales,
      areas_libres: new CapaLibres(),
      catastro: (dynamicMapLayer({ url: `${GEOCATMIN}/SERV_CATASTRO_MINERO_WGS84/MapServer`, layers: [0], opacity: 0.7, pane: "catastro", ...opcionesImagen } as any) as any)
        .bindPopup(popupCatastro),
      // Solo NO metálicas vigentes: relleno naranja (el catastro de INGEMMET solo dibuja bordes)
      catastro_nm: (dynamicMapLayer({
        url: `${GEOCATMIN}/SERV_CATASTRO_MINERO_WGS84/MapServer`, opacity: 0.8, pane: "catastro", ...opcionesImagen,
        dynamicLayers: JSON.stringify([{
          id: 0, source: { type: "mapLayer", mapLayerId: 0 },
          definitionExpression: "SUSTANCIA = 'N' AND LEYENDA IN ('TITULADO','TRAMITE')",
          drawingInfo: { showLabels: false, renderer: { type: "simple", symbol: {
            type: "esriSFS", style: "esriSFSSolid", color: [249, 115, 22, 90],
            outline: { type: "esriSLS", style: "esriSLSSolid", color: [234, 88, 12, 255], width: 1.5 } } } },
        }]),
      } as any) as any).bindPopup(popupCatastro),
    };

    grilla.current = L.layerGroup().addTo(m);
    seleccion.current = L.layerGroup().addTo(m);
    capaFormacion.current = L.layerGroup().addTo(m);
    capaAnalizadas.current = L.layerGroup().addTo(m);
    dibujo.current = L.layerGroup().addTo(m);
    resultados.current = L.layerGroup().addTo(m);
    marcaFabrica.current = L.marker(p.fabrica, { icon: ICONO_FABRICA, draggable: false, zIndexOffset: 1000, title: "Fábrica" });
    // Laptop: clic izquierdo = ver todo (y elegir la cuadrícula) · clic derecho = ver solo esa cuadrícula.
    // Celular: 1 toque = ver solo esa cuadrícula · 2 toques seguidos = ver todo (sin zoom con doble toque).
    const tactil = window.matchMedia?.("(pointer: coarse)").matches ?? false;
    if (tactil) m.doubleClickZoom.disable();
    // barra de coordenadas: cursor en la laptop (máx. ~20 veces por segundo); centro del mapa en el celular
    let ultimoCursor = 0;
    if (!tactil) {
      m.on("mousemove", (e: L.LeafletMouseEvent) => {
        const t = performance.now();
        if (t - ultimoCursor < 50) return;
        ultimoCursor = t;
        onCursorRef.current?.(e.latlng.lat, e.latlng.lng);
      });
    }
    // (solo si este mapa sigue vivo: en desarrollo React lo monta y desmonta una vez)
    const alCentro = () => { if (mapa.current !== m) return; const c = m.getCenter(); onCursorRef.current?.(c.lat, c.lng); };
    m.on("moveend", () => { if (tactil) alCentro(); });
    m.whenReady(() => setTimeout(alCentro, 0));
    let espera: number | undefined;
    let ultimoToque = 0;
    m.on("contextmenu", (e: L.LeafletMouseEvent) => {
      if (tactil) return;
      e.originalEvent?.preventDefault();
      onEnfocarRef.current(e.latlng.lat, e.latlng.lng, false);
    });
    m.on("click", (e: L.LeafletMouseEvent) => {
      const sobre = clicEnResultado.current;
      clicEnResultado.current = false;
      if (!tactil) {
        // tocar una zona A/B/C solo abre su ficha: no cambia el enfoque
        if (!sobre) onVerTodoRef.current();
        onClickRef.current(e.latlng.lat, e.latlng.lng, sobre);
        return;
      }
      const ahora = Date.now();
      window.clearTimeout(espera);
      if (ahora - ultimoToque < 320) {      // segundo toque: ver todo
        ultimoToque = 0;
        onVerTodoRef.current();
        return;
      }
      ultimoToque = ahora;
      const { lat, lng } = e.latlng;
      espera = window.setTimeout(() => onEnfocarRef.current(lat, lng, sobre), 320);
    });
    m.on("moveend", dibujarGrilla);
    mapa.current = m;
    dibujarGrilla();
    setTimeout(() => m.invalidateSize(), 100);
    return () => {
      m.remove();
      mapa.current = null;
    };
  }, []);

  // ---- mapa base
  useEffect(() => {
    const m = mapa.current;
    if (!m) return;
    for (const [k, l] of Object.entries(bases.current)) {
      if (k === p.base) l.addTo(m);
      else m.removeLayer(l);
    }
  }, [p.base]);

  // ---- capas GEOCATMIN encendidas/apagadas
  useEffect(() => {
    const m = mapa.current;
    if (!m) return;
    for (const [id, capa] of Object.entries(capasRef.current) as [IdCapa, L.Layer][]) {
      if (p.capas[id] && !m.hasLayer(capa)) capa.addTo(m);
      if (!p.capas[id] && m.hasLayer(capa)) m.removeLayer(capa);
    }
    const f = marcaFabrica.current;
    if (f && p.capas.fabrica && !m.hasLayer(f)) f.addTo(m);
    if (f && !p.capas.fabrica && m.hasLayer(f)) m.removeLayer(f);
    dibujarGrilla();
  }, [p.capas]);

  // ---- formación elegida en el catálogo: solo sus polígonos (filtro en GEOCATMIN)
  useEffect(() => {
    const g = capaFormacion.current;
    if (!g) return;
    g.clearLayers();
    const f = p.formacion;
    if (!f) return;
    const capas = [
      dynamicMapLayer({ url: `${GEOCATMIN}/SERV_GEOLOGIA_50K_INTEGRADA/MapServer`, layers: [7], layerDefs: { 7: f.sql50 }, opacity: 0.85, pane: "geologia", zIndex: 20, ...opcionesImagen } as any),
    ];
    if (f.sql100) {
      capas.unshift(dynamicMapLayer({ url: `${GEOCATMIN}/SERV_GEOLOGIA_100K_INTEGRADA/MapServer`, layers: [6], layerDefs: { 6: f.sql100 }, opacity: 0.6, pane: "geologia", zIndex: 19, ...opcionesImagen } as any));
    }
    for (const c of capas) {
      (c as any).bindPopup((err: unknown, fc: any) => {
        if (err) return false;
        const a = fc?.features?.[0]?.properties;
        if (!a) return false;
        return `<div class="pop"><b>${escapar(a.UNIDAD)}</b><br/>${escapar(a.LITOLOGIA || a.DESCRIP || a.NAME)}${a.LITO1 && a.LITO1 !== "<Null>" ? `<br/><small>Roca dominante: ${escapar(a.LITO1)}</small>` : ""}<br/><small>${escapar(f.nombre)} · GEOCATMIN</small></div>`;
      });
      c.addTo(g);
    }
  }, [p.formacion]);

  // ---- fábrica: posición y ficha
  useEffect(() => {
    const f = marcaFabrica.current;
    if (!f) return;
    f.setLatLng(p.fabrica);
    f.bindPopup(`<div class="pop"><b>🏭 Fábrica</b><br/>San Vicente de Cañete · Antigua Panamericana Sur<br/>
      ${gms(p.fabrica[0], true)} · ${gms(p.fabrica[1], false)}<br/>
      <small>${p.fabrica[0].toFixed(5)}, ${p.fabrica[1].toFixed(5)} · arrastra el ícono para corregirla</small></div>`);
  }, [p.fabrica]);

  // ---- cuadrículas ya analizadas: borde del color de la mejor clase + resumen
  useEffect(() => {
    const g = capaAnalizadas.current;
    if (!g) return;
    g.clearLayers();
    if (!p.capas.cuadricula) return;
    for (const a of p.analizadas) {
      const c = celda25(a.codigo);
      if (!c) continue;
      const color = a.clase ? COLOR_CLASE[a.clase] : "#94a3b8";
      L.rectangle([[c.sur, c.oeste], [c.norte, c.este]], {
        pane: "cuadricula", color, weight: 2, fillColor: color, fillOpacity: 0.07, interactive: false,
      }).addTo(g);
      L.marker([c.sur, c.este], {
        pane: "cuadricula", interactive: false, keyboard: false,
        // ancla de tamaño 0 en la esquina SE; el texto se dibuja hacia arriba-izquierda (dentro de la celda)
        icon: L.divIcon({ className: "etq-analizada", html: `<span>${escapar(a.etiqueta)}</span>`, iconSize: [0, 0], iconAnchor: [0, 0] }),
      }).addTo(g);
    }
  }, [p.analizadas, p.capas.cuadricula]);

  // ---- cuadrícula seleccionada + línea a la fábrica
  useEffect(() => {
    const g = seleccion.current;
    if (!g) return;
    g.clearLayers();
    const c = p.celdaSel;
    if (c) {
      L.rectangle([[c.sur, c.oeste], [c.norte, c.este]], {
        pane: "cuadricula", color: "#22d3ee", weight: 3, fillColor: "#22d3ee", fillOpacity: 0.12, interactive: false,
      }).addTo(g);
    }
    const h = p.resaltado;
    if (h) {
      L.rectangle([[h.sur, h.oeste], [h.norte, h.este]], {
        pane: "cuadricula", color: "#fde047", weight: 4, dashArray: "10 6", fill: false, interactive: false,
      }).addTo(g);
    }
    const d = p.destino;
    if (d && p.ruta?.bloques?.length) {
      // ruta por tramos: azul = pista asfaltada · café = trocha/afirmado · rosado punteado = a pie
      for (const b of p.ruta.bloques) {
        const pts = b.geometria.coordinates.map(([lon, lat]) => [lat, lon] as [number, number]);
        L.polyline(pts, { color: "#0f172a", weight: 8, opacity: 0.55, interactive: false }).addTo(g);
        L.polyline(pts, {
          color: COLOR_TRAMO_MAPA[b.tipo], weight: b.tipo === "a_pie" ? 4 : 5,
          dashArray: b.tipo === "a_pie" ? "6 8" : undefined,
        }).bindTooltip(`${b.km.toLocaleString("es-PE")} km · ${b.nombre}${b.vias.length ? ` — ${b.vias.slice(0, 2).join(", ")}` : ""}`, { sticky: true })
          .addTo(g);
      }
      L.circleMarker([d.lat, d.lon], { radius: 7, color: "#0f172a", weight: 2, fillColor: "#ec4899", fillOpacity: 1 })
        .bindTooltip(`Destino · ${p.ruta.km_total.toLocaleString("es-PE")} km desde la fábrica`).addTo(g);
    } else if (d && p.capas.fabrica) {
      L.polyline([p.fabrica, [d.lat, d.lon]], { color: "#fde047", weight: 3, dashArray: "8 6", interactive: false })
        .bindTooltip(formatoKm(distanciaKm(p.fabrica[0], p.fabrica[1], d.lat, d.lon)), { permanent: true, direction: "center", className: "etq-km" })
        .addTo(g);
    }
  }, [p.celdaSel, p.resaltado, p.destino, p.fabrica, p.capas.fabrica, p.ruta]);

  // ---- barrido de región: rectángulos coloreados por puntaje (violeta claro → oscuro) y puesto 1–10
  const capaBarrido = useRef<L.LayerGroup | null>(null);
  useEffect(() => {
    const m = mapa.current;
    if (!m) return;
    if (!m.getPane("barrido")) m.createPane("barrido").style.zIndex = "366";
    capaBarrido.current?.remove();
    const celdas = p.barrido ?? [];
    if (!celdas.length) { capaBarrido.current = null; return; }
    const max = Math.max(1, ...celdas.map((c) => c.puntaje ?? 0));
    const g = L.layerGroup();
    for (const c of celdas) {
      const t = c.puntaje == null ? -1 : Math.sqrt(c.puntaje / max);   // raíz: que se distingan también las bajas
      const color = t < 0 ? "#94a3b8" : `rgb(${Math.round(245 - 111 * t)},${Math.round(208 - 183 * t)},${Math.round(254 - 111 * t)})`;
      L.rectangle([[c.sur, c.oeste], [c.norte, c.este]], {
        pane: "barrido", color: t < 0 ? "#94a3b8" : "#701a75", weight: 1, dashArray: c.puntaje == null ? "4 4" : undefined,
        fillColor: color, fillOpacity: t < 0 ? 0.1 : 0.25 + 0.45 * t, interactive: false,
      }).addTo(g);
      if (c.puesto != null && c.puesto <= 10) {
        L.marker([(c.sur + c.norte) / 2, (c.oeste + c.este) / 2], {
          pane: "barrido", interactive: false, keyboard: false,
          icon: L.divIcon({ className: "puesto-barrido", html: `<span>${c.puesto}</span>`, iconSize: [26, 26], iconAnchor: [13, 13] }),
        }).addTo(g);
      }
    }
    g.addTo(m);
    capaBarrido.current = g;
  }, [p.barrido]);

  // ---- curvas de nivel de la cuadrícula (encima del satélite, debajo de las áreas libres)
  const capaCurvas = useRef<L.ImageOverlay | null>(null);
  useEffect(() => {
    const m = mapa.current;
    if (!m) return;
    if (!m.getPane("curvas")) {
      const pc = m.createPane("curvas");
      pc.style.zIndex = "372";
      pc.style.pointerEvents = "none";
    }
    capaCurvas.current?.remove();
    capaCurvas.current = null;
    const c = p.curvas;
    if (!c) return;
    capaCurvas.current = L.imageOverlay(c.png, [[c.sur, c.oeste], [c.norte, c.este]], { pane: "curvas", opacity: 0.95, interactive: false }).addTo(m);
  }, [p.curvas]);

  // al trazar una ruta nueva, se encuadra completa (fábrica → destino)
  const ultimaRuta = useRef<Ruta | null>(null);
  useEffect(() => {
    const m = mapa.current;
    if (!m || !p.ruta || p.ruta === ultimaRuta.current) return;
    ultimaRuta.current = p.ruta;
    const pts = p.ruta.bloques.flatMap((b) => b.geometria.coordinates.map(([lon, lat]) => [lat, lon] as [number, number]));
    // se deja libre el espacio del panel de la ruta (a la derecha en la laptop, abajo en el celular)
    const ancho = m.getContainer().clientWidth, alto = m.getContainer().clientHeight;
    const abajoDerecha: [number, number] = ancho > 700 ? [400, 40] : [20, Math.round(alto * 0.58)];
    if (pts.length > 1) m.fitBounds(L.latLngBounds(pts), { paddingTopLeft: [40, 80], paddingBottomRight: abajoDerecha, maxZoom: 14 });
  }, [p.ruta]);

  // ---- «solo esta cuadrícula»: velo oscuro con un hueco en la cuadrícula, por encima de la
  // geología, el catastro, las áreas protegidas y la grilla, y por debajo de las zonas A/B/C
  const velo = useRef<L.LayerGroup | null>(null);
  useEffect(() => {
    const m = mapa.current;
    if (!m) return;
    if (!m.getPane("foco")) {
      const panel = m.createPane("foco");
      panel.style.zIndex = "395";
      panel.style.pointerEvents = "none";
    }
    velo.current?.remove();
    velo.current = null;
    const f = p.foco;
    const libres = capasRef.current.areas_libres as CapaLibres | undefined;
    libres?.setLimite(f ? L.latLngBounds([f.sur, f.oeste], [f.norte, f.este]) : null);
    if (!f) return;
    const hueco: L.LatLngExpression[] = [[f.sur, f.oeste], [f.sur, f.este], [f.norte, f.este], [f.norte, f.oeste]];
    const mundo: L.LatLngExpression[] = [[-60, -150], [-60, -10], [30, -10], [30, -150]];
    velo.current = L.layerGroup([
      L.polygon([mundo, hueco], { pane: "foco", stroke: false, fillColor: "#0b1220", fillOpacity: 0.86, interactive: false }),
      L.rectangle([[f.sur, f.oeste], [f.norte, f.este]], { pane: "foco", color: "#22d3ee", weight: 3, fill: false, interactive: false }),
    ]).addTo(m);
  }, [p.foco?.codigo]);

  // ---- capas «rocas de interés»: siguen a la materia prima elegida
  useEffect(() => {
    const c = capasRef.current as Record<string, any> | null;
    if (!c) return;
    c.geo50_si?.setLayerDefs?.({ 7: p.sqlInteres?.sql50 || sqlSilice(["LITOLOGIA", "DESCRIP"]) });
    c.geo100_si?.setLayerDefs?.({ 6: p.sqlInteres?.sql100 || sqlSilice(["DESCRIP"]) });
  }, [p.sqlInteres?.sql50, p.sqlInteres?.sql100]);

  // ---- cuadrículas de petitorio (100 ha = 1 km × 1 km, vértices en múltiplos de 1 000 m UTM WGS84)
  const capaPetitorio = useRef<L.LayerGroup | null>(null);
  useEffect(() => {
    const m = mapa.current;
    if (!m) return;
    if (!m.getPane("petitorio")) m.createPane("petitorio").style.zIndex = "397";
    // (si quedó enganchada a un mapa anterior —React monta y desmonta en desarrollo— se crea de nuevo)
    if (!capaPetitorio.current || !m.hasLayer(capaPetitorio.current)) capaPetitorio.current = L.layerGroup().addTo(m);
    const g = capaPetitorio.current;
    const dibujar = () => {
      g.clearLayers();
      const pt = p.petitorio;
      if (!pt || (!pt.activo && !pt.celdas.length)) return;
      // grilla de 1 km en la zona UTM del centro (solo con zoom suficiente)
      if (pt.activo && m.getZoom() >= 12) {
        const b = m.getBounds(), c = m.getCenter();
        const z = utm(c.lat, c.lng).zona;
        const esq = [utm(b.getSouth(), b.getWest()), utm(b.getNorth(), b.getEast()), utm(b.getSouth(), b.getEast()), utm(b.getNorth(), b.getWest())]
          .filter((u) => u.zona === z);
        if (esq.length) {
          const e0 = Math.floor(Math.min(...esq.map((u) => u.este)) / 1000) - 1, e1 = Math.ceil(Math.max(...esq.map((u) => u.este)) / 1000) + 1;
          const n0 = Math.floor(Math.min(...esq.map((u) => u.norte)) / 1000) - 1, n1 = Math.ceil(Math.max(...esq.map((u) => u.norte)) / 1000) + 1;
          if ((e1 - e0) * (n1 - n0) < 9000) {
            const estilo = { pane: "petitorio", color: "#e9c99c", weight: 1, opacity: 0.75, interactive: false };
            for (let e = e0; e <= e1; e++) L.polyline([utmAGeo(e * 1000, n0 * 1000, z), utmAGeo(e * 1000, n1 * 1000, z)], estilo).addTo(g);
            for (let n = n0; n <= n1; n++) L.polyline([utmAGeo(e0 * 1000, n * 1000, z), utmAGeo(e1 * 1000, n * 1000, z)], estilo).addTo(g);
          }
        }
      }
      for (const cd of pt.celdas) {
        L.polygon(esquinasC100(cd), { pane: "petitorio", color: "#c08a4a", weight: 2.5, fillColor: "#c08a4a", fillOpacity: 0.35, interactive: false })
          .bindTooltip(`E ${cd.e * 1000} · N ${cd.n * 1000}`, { direction: "center" })
          .addTo(g);
      }
    };
    dibujar();
    m.on("moveend", dibujar);
    return () => { m.off("moveend", dibujar); };
  }, [p.petitorio]);

  // ---- borde de la cuadrícula analizada
  useEffect(() => {
    const g = dibujo.current;
    if (!g) return;
    g.clearLayers();
    if (p.area) {
      L.polygon(p.area.map(([lng, lat]) => [lat, lng] as [number, number]), {
        color: "#22d3ee", weight: 2, dashArray: "6 4", fill: false, interactive: false,
      }).addTo(g);
    }
  }, [p.area]);

  // ---- resultados (afloramientos + RMI)
  useEffect(() => {
    const g = resultados.current;
    const m = mapa.current;
    if (!g || !m) return;
    g.clearLayers();
    capasAfl.current = {};
    if (!p.capas.resultados) return;
    // (24/11/2026, «resáltalas, me pierdo»): las APTAS para vidrio por su descripción van encima, gruesas, con halo
    // oscuro y etiqueta con el nombre de la formación; las no aptas, tenues y punteadas. Sin lectura: por clase.
    const R = { alta: 0, media: 1, baja: 2, no: 3 } as const;
    const nivel = (a: Afloramiento) => p.vidrio?.[a.id];
    const orden = [...p.afloramientos].sort((x, y) => (p.vidrio ? R[nivel(y) ?? "no"] - R[nivel(x) ?? "no"] : 0) || (x.clase < y.clase ? 1 : -1));
    for (const a of orden) {
      const nv = nivel(a);
      const apta = nv === "alta" || nv === "media";
      if (apta) {   // halo oscuro debajo del borde: separa la zona de la geología y de la foto
        L.geoJSON(a.geometria as any, { style: { color: "#0b1118", weight: nv === "alta" ? 7 : 6, opacity: 0.8, fill: false }, interactive: false }).addTo(g);
      }
      const capa = L.geoJSON(a.geometria as any, { style: estiloZona(a, nv, null, p.zonasSoloBorde) })
        .bindPopup(popupAfloramiento(a, p.statsPorId[a.id], p.fabrica));
      capa.on("click", () => { clicEnResultado.current = true; });
      capa.addTo(g);
      capasAfl.current[a.id] = capa;
      if (apta) {
        L.marker([a.centro[1], a.centro[0]], {
          interactive: false, keyboard: false,
          icon: L.divIcon({ className: `etq-zona ${nv}`, html: `<span>${escapar(nombreCorto(a.unidad))}</span>`, iconSize: undefined as any }),
        }).addTo(g);
      }
    }
  }, [p.afloramientos, p.statsPorId, p.capas.resultados, p.fabrica, p.vidrio]);

  // zona elegida en la lista: celeste y gruesa; las demás se atenúan (sin volver a crear las capas)
  useEffect(() => {
    for (const a of p.afloramientos) {
      capasAfl.current[a.id]?.setStyle(estiloZona(a, p.vidrio?.[a.id], p.zonaSel ?? null, p.zonasSoloBorde));
    }
    if (p.zonaSel) capasAfl.current[p.zonaSel]?.bringToFront();
  }, [p.zonaSel, p.afloramientos, p.vidrio, p.zonasSoloBorde]);

  // ---- capas satelitales de la cuadrícula (Sentinel-2).
  // Se crean una vez por análisis; el efecto de capas las prende/apaga.
  useEffect(() => {
    const m = mapa.current;
    if (!m) return;
    for (const id of Object.keys(CAPAS_SATELITE) as IdCapa[]) {
      const vieja = capasRef.current[id];
      if (vieja) m.removeLayer(vieja);
      delete capasRef.current[id];
    }
    const s = p.sentinel;
    if (!s?.disponible || !s.bbox || !s.capas) return;
    const [x0, y0, x1, y1] = s.bbox;
    const limites: L.LatLngBoundsExpression = [[y0, x0], [y1, x1]];
    for (const [id, def] of Object.entries(CAPAS_SATELITE) as [IdCapa, { opacidad: number; z: number }][]) {
      const url = urlSatelite(s.capas, id);
      if (!url) continue;
      // zIndex: orden fijo al superponer (fotos abajo, hierro y arcillas arriba)
      const capa = L.imageOverlay(url, limites, { pane: "sentinel", opacity: p.opacidades?.[id] ?? def.opacidad, zIndex: def.z, interactive: false });
      capasRef.current[id] = capa;
      if (p.capas[id]) capa.addTo(m);
    }
  }, [p.sentinel]);

  // ---- transparencia elegida por el usuario (sin volver a crear las capas)
  useEffect(() => {
    for (const id of Object.keys(GEO_OPACIDAD) as IdCapa[]) {
      (capasRef.current[id] as any)?.setOpacity?.(p.opacidades?.[id] ?? GEO_OPACIDAD[id]);
    }
    for (const [id, def] of Object.entries(CAPAS_SATELITE) as [IdCapa, { opacidad: number }][]) {
      const c = capasRef.current[id] as L.ImageOverlay | undefined;
      c?.setOpacity?.(p.opacidades?.[id] ?? def.opacidad);
    }
  }, [p.opacidades]);

  // ---- mi ubicación
  useEffect(() => {
    const m = mapa.current;
    if (!m) return;
    marcaUbicacion.current?.remove();
    if (p.ubicacion) {
      marcaUbicacion.current = L.circleMarker(p.ubicacion, { radius: 8, color: "#fff", weight: 3, fillColor: "#2563eb", fillOpacity: 1 }).addTo(m);
    }
  }, [p.ubicacion]);

  useImperativeHandle(ref, () => ({
    irA(a) {
      const m = mapa.current;
      const capa = capasAfl.current[a.id] ?? L.geoJSON(a.geometria as any);
      if (!m) return;
      m.fitBounds(capa.getBounds(), { padding: [30, 30], maxZoom: 15 });
      if (capasAfl.current[a.id]) setTimeout(() => capasAfl.current[a.id]?.openPopup(L.latLng(a.centro[1], a.centro[0])), 400);
    },
    irAPunto(lat, lon, zoom = 14) {
      mapa.current?.flyTo([lat, lon], zoom, { duration: 1.2 });
    },
    vistaComoPoligono() {
      const b = mapa.current!.getBounds();
      const o = Math.max(b.getWest(), -81.5), e = Math.min(b.getEast(), -68.5);
      const s = Math.max(b.getSouth(), -18.5), n = Math.min(b.getNorth(), 0.2);
      return [[o, s], [e, s], [e, n], [o, n]];
    },
    encuadrar(poligono) {
      mapa.current?.fitBounds(L.latLngBounds(poligono.map(([lng, lat]) => [lat, lng] as [number, number])), { padding: [20, 20] });
    },
    cerrarFichas() {
      mapa.current?.closePopup();
    },
  }), []);

  return <div ref={divRef} className="mapa" />;
});

export default Mapa;
