// Utilidades geográficas del lado del cliente: fábrica, distancias y la
// cuadrícula de la Carta Nacional (100K → 50K → 25K).

// Cuadrículas con territorio peruano (generado por
// backend/scripts/generar_celdas_peru.py): hoja 50K → bits de sus 4
// cuadrículas 25K con tierra (NE=1, SE=2, SO=4, NO=8).
import celdasPeru from "./celdas_peru.json";

const TIERRA = celdasPeru as Record<string, number>;
const BIT_25K: Record<string, number> = { NE: 1, SE: 2, SO: 4, NO: 8 };

/** Planta de referencia: San Vicente de Cañete, Antigua Panamericana Sur
 *  (OpenStreetMap). El usuario puede moverla arrastrando el marcador. */
export const FABRICA_INICIAL: [number, number] = [-13.0808, -76.3877]; // [lat, lon]

/** Distancia en línea recta (km), fórmula de haversine. */
export function distanciaKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371.0088;
  const rad = Math.PI / 180;
  const dLat = (lat2 - lat1) * rad;
  const dLon = (lon2 - lon1) * rad;
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

export function formatoKm(km: number): string {
  return km < 10 ? `${km.toFixed(1)} km` : `${Math.round(km)} km`;
}

/*
 * Cuadrícula de la Carta Nacional, la misma que usa la geología de INGEMMET
 * (verificado en GEOCATMIN: hoja 100K "27-k Chincha" = 76°30'–76°00' O,
 * 13°00'–13°30' S; campo CODHOJA de la 50K = "27k1".."27k4").
 *   - Hoja 1:100 000: 30' × 30'. Fila = franjas de 30' desde 0° hacia el sur
 *     (1, 2, …); columna = letra desde 81°30' O (a, b, …).
 *   - Hoja 1:50 000: 4 cuadrantes de 15', numerados en sentido horario desde
 *     el NE como en INGEMMET: 1 = NE, 2 = SE, 3 = SO, 4 = NO.
 *   - Cuadrícula 1:25 000: cada hoja 50K dividida en 4 (7'30"), con el
 *     cuadrante indicado como NE/SE/SO/NO.
 */
const LADO_100K = 0.5;
const LON_ORIGEN = -81.5;
/** Columnas de la Carta Nacional: alfabeto español CON «ñ» y SIN «w»
 *  (verificado con las 501 hojas 1:100 000 de GEOCATMIN: 25-x Río Pariamanu,
 *  5-ñ Curaray, 32-v…). Con el alfabeto inglés, todo lo que está al este de
 *  74°30' O quedaría con la letra corrida. */
export const ALFABETO = "abcdefghijklmnñopqrstuvxyz";

export interface Celda {
  codigo: string;          // p. ej. "27k4-NE" (25K) o "27k4" (50K)
  hoja100: string;         // "27-k"
  escala: "50K" | "25K";
  sur: number; oeste: number; norte: number; este: number;
}

function hoja100(lat: number, lon: number) {
  const fila = Math.floor(-lat / LADO_100K) + 1;
  const col = Math.floor((lon - LON_ORIGEN) / LADO_100K);
  return { fila, letra: ALFABETO[col] ?? "?", norte: -(fila - 1) * LADO_100K, oeste: LON_ORIGEN + col * LADO_100K };
}

const NUM_CUADRANTE: Record<string, number> = { NE: 1, SE: 2, SO: 3, NO: 4 };

function cuadrante(norteSup: boolean, este: boolean): "NE" | "SE" | "SO" | "NO" {
  return norteSup ? (este ? "NE" : "NO") : (este ? "SE" : "SO");
}

/** Celda 1:50 000 o 1:25 000 que contiene el punto. */
export function celdaEn(lat: number, lon: number, escala: "50K" | "25K"): Celda {
  const h = hoja100(lat, lon);
  const m50 = LADO_100K / 2;
  const n50 = lat >= h.norte - m50;
  const e50 = lon >= h.oeste + m50;
  const norte50 = n50 ? h.norte : h.norte - m50;
  const oeste50 = e50 ? h.oeste + m50 : h.oeste;
  const cod50 = `${h.fila}${h.letra}${NUM_CUADRANTE[cuadrante(n50, e50)]}`;
  const hoja = `${h.fila}-${h.letra}`;
  if (escala === "50K") {
    return { codigo: cod50, hoja100: hoja, escala, norte: norte50, sur: norte50 - m50, oeste: oeste50, este: oeste50 + m50 };
  }
  const m25 = m50 / 2;
  const n25 = lat >= norte50 - m25;
  const e25 = lon >= oeste50 + m25;
  const norte = n25 ? norte50 : norte50 - m25;
  const oeste = e25 ? oeste50 + m25 : oeste50;
  return { codigo: `${cod50}-${cuadrante(n25, e25)}`, hoja100: hoja, escala, norte, sur: norte - m25, oeste, este: oeste + m25 };
}

/** true si la celda tiene algo de territorio peruano (aunque sea un pedazo de costa o una isla). */
export function tieneTierra(c: Celda): boolean {
  const [hoja50, q25] = c.codigo.split("-");
  const bits = TIERRA[hoja50] ?? 0;
  return c.escala === "50K" ? bits > 0 : (bits & BIT_25K[q25]) !== 0;
}

/** Celdas de la escala dada que tocan el rectángulo y tienen tierra (con límite de seguridad). */
export function celdasEnVista(sur: number, oeste: number, norte: number, este: number,
                              escala: "50K" | "25K", max = 400): Celda[] {
  const paso = escala === "50K" ? 0.25 : 0.125;
  const out: Celda[] = [];
  const lat0 = Math.ceil(norte / paso) * paso;
  const lon0 = Math.floor(oeste / paso) * paso;
  for (let lat = lat0; lat > sur; lat -= paso) {
    for (let lon = lon0; lon < este; lon += paso) {
      const c = celdaEn(lat - paso / 2, lon + paso / 2, escala);
      if (!tieneTierra(c)) continue;
      out.push(c);
      if (out.length >= max) return out;
    }
  }
  return out;
}

/** Hoja 1:50 000 a partir de su código INGEMMET ("27k4", también "08b3"). */
export function hoja50(codigo: string): Celda | null {
  const m = /^0*(\d+)([a-zñ])([1-4])$/i.exec(codigo.trim());
  if (!m) return null;
  const fila = Number(m[1]);
  const col = ALFABETO.indexOf(m[2].toLowerCase());
  if (col < 0) return null;
  const q = Number(m[3]); // 1 NE, 2 SE, 3 SO, 4 NO
  const norte100 = -(fila - 1) * LADO_100K;
  const oeste100 = LON_ORIGEN + col * LADO_100K;
  const m50 = LADO_100K / 2;
  const norte = q === 1 || q === 4 ? norte100 : norte100 - m50;
  const oeste = q === 1 || q === 2 ? oeste100 + m50 : oeste100;
  return { codigo: `${fila}${m[2].toLowerCase()}${q}`, hoja100: `${fila}-${m[2].toLowerCase()}`, escala: "50K",
    norte, sur: norte - m50, oeste, este: oeste + m50 };
}

/** Cuadrícula 1:25 000 a partir de su código ("27k4-NO"). */
export function celda25(codigo: string): Celda | null {
  const [h, q] = codigo.split("-");
  const c50 = hoja50(h ?? "");
  if (!c50 || !q) return null;
  const m25 = (c50.norte - c50.sur) / 2;
  const lat = q.startsWith("N") ? c50.norte - m25 / 2 : c50.sur + m25 / 2;
  const lon = q.endsWith("E") ? c50.este - m25 / 2 : c50.oeste + m25 / 2;
  return celdaEn(lat, lon, "25K");
}

export type Rumbo = "N" | "S" | "E" | "O";

/** Cuadrícula 1:25 000 vecina (null si es puro océano o fuera del Perú). */
export function vecina(c: Celda, rumbo: Rumbo): Celda | null {
  const paso = c.norte - c.sur;
  const lat = (c.norte + c.sur) / 2 + (rumbo === "N" ? paso : rumbo === "S" ? -paso : 0);
  const lon = (c.oeste + c.este) / 2 + (rumbo === "E" ? paso : rumbo === "O" ? -paso : 0);
  const v = celdaEn(lat, lon, "25K");
  return tieneTierra(v) ? v : null;
}

export interface Ubicacion {
  nivel: "100K" | "50K" | "25K";
  codigo: string; // "27-k", "27k4", "27k4-NO"
  sur: number; oeste: number; norte: number; este: number;
  nota?: string;
}

const CARDINAL: Record<string, "NE" | "SE" | "SO" | "NO"> = { NE: "NE", SE: "SE", SO: "SO", NO: "NO", SW: "SO", NW: "NO" };
const NUM_DE: Record<string, number> = { NE: 1, SE: 2, SO: 3, NO: 4 };

/** Interpreta lo que el usuario escribe como cuadrángulo de la Carta Nacional:
 *  "27-k" / "27k" → hoja 1:100 000 · "27k4" → hoja 1:50 000 ·
 *  "27k4-NO" / "27k4 no" → cuadrícula 1:25 000 ·
 *  "27k-NO" (sin número) → el cuadrante NO de la hoja 100K = hoja 50K 27k4. */
export function parsearUbicacion(texto: string): Ubicacion | null {
  const t = texto.toUpperCase().replace(/[\s\-_.]+/g, "");
  const m = /^0*(\d{1,2})([A-ZÑ])([1-4])?(NE|SE|SO|NO|SW|NW)?$/.exec(t);
  if (!m) return null;
  const fila = Number(m[1]);
  const letra = m[2].toLowerCase();
  const col = ALFABETO.indexOf(letra);
  if (fila < 1 || fila > 40 || col < 0) return null;
  const norte100 = -(fila - 1) * LADO_100K, oeste100 = LON_ORIGEN + col * LADO_100K;
  if (!m[3] && !m[4]) {
    return { nivel: "100K", codigo: `${fila}-${letra}`, norte: norte100, sur: norte100 - LADO_100K, oeste: oeste100, este: oeste100 + LADO_100K };
  }
  const num = m[3] ? Number(m[3]) : NUM_DE[CARDINAL[m[4]!]];
  const q25 = m[3] && m[4] ? CARDINAL[m[4]] : undefined;
  const nota = m[3] ? undefined
    : `${fila}${letra}-${m[4]} = hoja 1:50 000 ${fila}${letra}${num} (cuadrante ${CARDINAL[m[4]!]} de la hoja ${fila}-${letra}). Toca una de sus 4 cuadrículas.`;
  const h = hoja50(`${fila}${letra}${num}`)!;
  if (!q25) return { nivel: "50K", codigo: h.codigo, sur: h.sur, oeste: h.oeste, norte: h.norte, este: h.este, nota };
  const c = celda25(`${h.codigo}-${q25}`)!;
  return { nivel: "25K", codigo: c.codigo, sur: c.sur, oeste: c.oeste, norte: c.norte, este: c.este };
}

/** Anillo [[lng, lat], …] de la celda, para usarla como área de búsqueda. */
export function celdaComoPoligono(c: Celda): number[][] {
  return [[c.oeste, c.sur], [c.este, c.sur], [c.este, c.norte], [c.oeste, c.norte]];
}

/** 13.0833 → 13°05'00" S */
export function gms(v: number, lat: boolean): string {
  const a = Math.abs(v);
  let g = Math.floor(a), m = Math.floor((a - g) * 60), s = Math.round(((a - g) * 60 - m) * 60);
  if (s === 60) { s = 0; m += 1; }
  if (m === 60) { m = 0; g += 1; }
  return `${g}°${String(m).padStart(2, "0")}'${String(s).padStart(2, "0")}" ${lat ? (v < 0 ? "S" : "N") : (v < 0 ? "O" : "E")}`;
}

/** Coordenadas UTM WGS84 (las de las cartas de INGEMMET y del GPS de campo). Fórmulas de Snyder
 *  (precisión < 1 m dentro de la zona). Perú: zonas 17, 18 y 19, hemisferio sur. */
export function utm(lat: number, lon: number): { zona: number; hemisferio: "N" | "S"; este: number; norte: number } {
  const a = 6378137, f = 1 / 298.257223563, k0 = 0.9996;
  const e2 = f * (2 - f), ep2 = e2 / (1 - e2);
  const zona = Math.min(60, Math.max(1, Math.floor((lon + 180) / 6) + 1));
  const lon0 = ((zona - 1) * 6 - 180 + 3) * Math.PI / 180;
  const φ = lat * Math.PI / 180, λ = lon * Math.PI / 180;
  const N = a / Math.sqrt(1 - e2 * Math.sin(φ) ** 2);
  const T = Math.tan(φ) ** 2, C = ep2 * Math.cos(φ) ** 2, A = Math.cos(φ) * (λ - lon0);
  const M = a * ((1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256) * φ
    - (3 * e2 / 8 + 3 * e2 ** 2 / 32 + 45 * e2 ** 3 / 1024) * Math.sin(2 * φ)
    + (15 * e2 ** 2 / 256 + 45 * e2 ** 3 / 1024) * Math.sin(4 * φ)
    - (35 * e2 ** 3 / 3072) * Math.sin(6 * φ));
  const este = k0 * N * (A + (1 - T + C) * A ** 3 / 6 + (5 - 18 * T + T ** 2 + 72 * C - 58 * ep2) * A ** 5 / 120) + 500000;
  let norte = k0 * (M + N * Math.tan(φ) * (A ** 2 / 2 + (5 - T + 9 * C + 4 * C ** 2) * A ** 4 / 24
    + (61 - 58 * T + T ** 2 + 600 * C - 330 * ep2) * A ** 6 / 720));
  if (lat < 0) norte += 10000000;
  return { zona, hemisferio: lat < 0 ? "S" : "N", este, norte };
}

/** UTM WGS84 → geográficas (inversa de `utm`, Snyder). `sur` = hemisferio sur. */
export function utmAGeo(este: number, norte: number, zona: number, sur = true): [number, number] {
  const a = 6378137, f = 1 / 298.257223563, k0 = 0.9996;
  const e2 = f * (2 - f), ep2 = e2 / (1 - e2), e1 = (1 - Math.sqrt(1 - e2)) / (1 + Math.sqrt(1 - e2));
  const x = este - 500000, y = sur ? norte - 10000000 : norte;
  const M = y / k0, mu = M / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256));
  const φ1 = mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * Math.sin(2 * mu) + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * Math.sin(4 * mu)
    + (151 * e1 ** 3 / 96) * Math.sin(6 * mu) + (1097 * e1 ** 4 / 512) * Math.sin(8 * mu);
  const N1 = a / Math.sqrt(1 - e2 * Math.sin(φ1) ** 2), T1 = Math.tan(φ1) ** 2, C1 = ep2 * Math.cos(φ1) ** 2;
  const R1 = a * (1 - e2) / (1 - e2 * Math.sin(φ1) ** 2) ** 1.5, D = x / (N1 * k0);
  const lat = φ1 - (N1 * Math.tan(φ1) / R1) * (D ** 2 / 2 - (5 + 3 * T1 + 10 * C1 - 4 * C1 ** 2 - 9 * ep2) * D ** 4 / 24
    + (61 + 90 * T1 + 298 * C1 + 45 * T1 ** 2 - 252 * ep2 - 3 * C1 ** 2) * D ** 6 / 720);
  const lon0 = ((zona - 1) * 6 - 180 + 3) * Math.PI / 180;
  const lon = lon0 + (D - (1 + 2 * T1 + C1) * D ** 3 / 6 + (5 - 2 * C1 + 28 * T1 - 3 * C1 ** 2 + 8 * ep2 + 24 * T1 ** 2) * D ** 5 / 120) / Math.cos(φ1);
  return [lat * 180 / Math.PI, lon * 180 / Math.PI];
}

// ---------------------------------------------------------------- cuadrículas de petitorio (100 ha)
/** Cuadrícula del catastro minero: 1 km × 1 km = 100 ha, vértices en múltiplos de 1 000 m UTM WGS84.
 *  `e`, `n` = esquina SUROESTE en km (p. ej. e = 349, n = 8553 → E 349 000, N 8 553 000). */
export interface Cuadricula100 { zona: number; e: number; n: number }
export const claveC100 = (c: Cuadricula100) => `${c.zona}:${c.e}:${c.n}`;

export function cuadricula100En(lat: number, lon: number): Cuadricula100 {
  const u = utm(lat, lon);
  return { zona: u.zona, e: Math.floor(u.este / 1000), n: Math.floor(u.norte / 1000) };
}

/** Las 4 esquinas en geográficas ([lat, lon]), para dibujar. */
export function esquinasC100(c: Cuadricula100): [number, number][] {
  return [[c.e, c.n], [c.e + 1, c.n], [c.e + 1, c.n + 1], [c.e, c.n + 1]].map(([e, n]) => utmAGeo(e * 1000, n * 1000, c.zona));
}

/** Validación de un petitorio: 1 a 10 cuadrículas (100–1 000 ha), misma zona, colindantes al menos por un lado. */
export function validarPetitorio(cs: Cuadricula100[]): { ok: boolean; errores: string[] } {
  const errores: string[] = [];
  if (!cs.length) errores.push("Elige al menos 1 cuadrícula (100 ha).");
  if (cs.length > 10) errores.push(`Máximo 10 cuadrículas (1 000 ha) por petitorio en tierra: tienes ${cs.length}.`);
  if (new Set(cs.map((c) => c.zona)).size > 1) errores.push("Todas las cuadrículas deben estar en la misma zona UTM.");
  if (cs.length > 1) {
    const hay = new Set(cs.map(claveC100));
    const vistos = new Set<string>([claveC100(cs[0])]);
    const cola = [cs[0]];
    while (cola.length) {
      const c = cola.pop()!;
      for (const [de, dn] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        const k = claveC100({ zona: c.zona, e: c.e + de, n: c.n + dn });
        if (hay.has(k) && !vistos.has(k)) { vistos.add(k); cola.push({ zona: c.zona, e: c.e + de, n: c.n + dn }); }
      }
    }
    if (vistos.size < cs.length) errores.push("Las cuadrículas deben ser colindantes al menos por un lado (no basta tocarse por una esquina).");
  }
  return { ok: !errores.length, errores };
}

/** Vértices UTM (m) del contorno del conjunto, en orden horario empezando por el vértice más al noroeste.
 *  Es lo que se escribe en el formulario de petitorio. */
export function verticesPetitorio(cs: Cuadricula100[]): { este: number; norte: number }[] {
  if (!cs.length) return [];
  // aristas de cada cuadrado; las compartidas se anulan → queda el contorno
  const aristas = new Map<string, [[number, number], [number, number]]>();
  const k = (p: [number, number], q: [number, number]) => `${p}|${q}`;
  for (const c of cs) {
    const v: [number, number][] = [[c.e, c.n + 1], [c.e + 1, c.n + 1], [c.e + 1, c.n], [c.e, c.n]]; // horario
    for (let i = 0; i < 4; i++) {
      const p = v[i], q = v[(i + 1) % 4];
      if (aristas.has(k(q, p))) aristas.delete(k(q, p)); else aristas.set(k(p, q), [p, q]);
    }
  }
  const sig = new Map<string, [number, number]>();
  for (const [p, q] of aristas.values()) sig.set(String(p), q);
  const inicio = [...aristas.values()].map(([p]) => p).sort((a, b) => b[1] - a[1] || a[0] - b[0])[0];
  const out: [number, number][] = [inicio];
  let act = sig.get(String(inicio))!;
  while (act && String(act) !== String(inicio) && out.length <= aristas.size) { out.push(act); act = sig.get(String(act))!; }
  // se quitan los vértices intermedios de lados rectos
  const lim = out.filter((p, i) => {
    const a = out[(i - 1 + out.length) % out.length], b = out[(i + 1) % out.length];
    return !((a[0] === p[0] && p[0] === b[0]) || (a[1] === p[1] && p[1] === b[1]));
  });
  return lim.map(([e, n]) => ({ este: e * 1000, norte: n * 1000 }));
}
