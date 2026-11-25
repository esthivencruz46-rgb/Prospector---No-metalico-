/**
 * Cortes de la PRIORIDAD LIBRE DEFINITIVA (definición del usuario, 24/11/2026).
 *
 * Un píxel de zona A/B pasa si cumple LOS TRES a la vez (intersección), cada uno por PERCENTIL dentro de la
 * cuadrícula y ajustable con su histograma (sin BSI: decisión del usuario tras comparar, 24/11/2026):
 *   NDVI < p_ndvi (P57 = «sin vegetación» + «vegetación escasa»)
 *   anomalía ferruginosa < p_ferruginosa (P30 = clases 1–3: índigo, azul, celeste)
 *   arcilla < arcilla (P30 = clases 1–3)
 * y suelo visible (sin nubes ni agua, NDVI < 0,30). Luego se cruza con las áreas libres (prioridadLibre.ts).
 *
 * El backend (`sentinel_silice.calcular`) manda en `s2.datos` los percentiles por píxel (formato 3) y los
 * histogramas reales. Aquí se recalcula, SIN volver a pedir la imagen ni gastar créditos, la Sílice limpia (base de
 * la Prioridad libre). MANTENER IGUAL que el backend:
 *   cumple = moda3×3( útil y NDVI < Pndvi y ferruginosa < Pfe y arcilla < Pcl )
 *   sílice limpia = zona A/B (peso ≥ 0,6) y cumple
 * Las capas Anomalías ferruginosas y Arcillas van en 10 CLASES FIJAS (deciles P0–P100): el corte decide cuántas
 * clases pasan, no cambia los colores.
 */
import type { Afloramiento, ResultadoSentinel } from "./api";

/** percentiles 0–1 (= backend CORTES) */
export interface Cortes { p_ferruginosa: number; arcilla: number; p_ndvi: number }
export const CORTES_DEFECTO: Cortes = { p_ferruginosa: 0.3, arcilla: 0.3, p_ndvi: 0.57 };
const CLAVE = "prospector-rmi:cortes";
const CLAVES = ["p_ferruginosa", "arcilla", "p_ndvi"] as const;
const val = (v: unknown, d: number) => (typeof v === "number" && Number.isFinite(v) && v >= 0 && v <= 1 ? v : d);

const limpiar = (x: Partial<Cortes> | null | undefined): Cortes => ({
  p_ferruginosa: val(x?.p_ferruginosa, CORTES_DEFECTO.p_ferruginosa),
  arcilla: val(x?.arcilla, CORTES_DEFECTO.arcilla),
  p_ndvi: val(x?.p_ndvi, CORTES_DEFECTO.p_ndvi),
});
/** Preferencia del usuario. Una preferencia anterior al 24/11/2026 (sin NDVI/BSI) tenía otro sentido: se ignora. */
export function cortesGuardados(): Cortes {
  try {
    const x = JSON.parse(localStorage.getItem(CLAVE) || "{}") as Partial<Cortes>;
    return typeof x.p_ndvi === "number" ? limpiar(x) : CORTES_DEFECTO;
  } catch { return CORTES_DEFECTO; }
}
export function guardarCortes(c: Cortes) {
  try { localStorage.setItem(CLAVE, JSON.stringify(limpiar(c))); } catch { /* sin almacenamiento */ }
}
export const mismosCortes = (a?: Partial<Cortes> | null, b?: Partial<Cortes> | null) =>
  !!a && !!b && CLAVES.every((k) => Math.abs((a[k] ?? -1) - (b[k] ?? -2)) < 0.004);
/** Cortes con los que se hicieron las imágenes; null = análisis anterior a la Prioridad libre definitiva. */
export const cortesDe = (s2: ResultadoSentinel): Cortes | null => {
  const c = s2.cortes as Partial<Cortes> | undefined;
  return c && typeof c.p_ferruginosa === "number" && typeof c.p_ndvi === "number" ? limpiar(c) : null;
};
/** ¿Se puede recalcular este análisis en el navegador? (necesita los percentiles por píxel) */
export const recalculable = (s2: ResultadoSentinel) => !!s2.datos?.rangos && !!s2.datos?.base;
/** ¿Trae el NDVI por píxel? (formato 3, desde el 24/11/2026). Si no, la intersección va sin ese filtro. */
export const conNdviBsi = (s2: ResultadoSentinel) => (s2.datos?.formato ?? 0) >= 3;

/** Capas que ya no se usan (análisis guardados antes del 24/11/2026): se quitan al abrirlos para no ocupar memoria. */
const CAPAS_VIEJAS = ["pureza", "prioridad", "prioridad_100k", "prioridad_ambas", "pureza_zonas", "pureza_zonas_100k",
  "oxidos_hierro", "prioridad_libre", "prioridad_libre_100k", "pureza_libre", "pureza_libre_100k",
  "hierro", "ferrico", "ferroso", "cocientes", "cuarzo_aster", "afloramientos"];   // 24/11/2026: capas eliminadas por el usuario
export function sinCapasViejas(s2: ResultadoSentinel): ResultadoSentinel {
  if (!s2.capas || !CAPAS_VIEJAS.some((k) => k in s2.capas!)) return s2;
  const capas = { ...s2.capas };
  for (const k of CAPAS_VIEJAS) delete capas[k];
  return { ...s2, capas };
}

interface Pixeles { w: number; h: number; fe: Uint8ClampedArray; base: Uint8ClampedArray }
const cache = new Map<string, Promise<Pixeles>>();

async function leer(url: string): Promise<{ w: number; h: number; d: Uint8ClampedArray }> {
  const bmp = await createImageBitmap(await (await fetch(url)).blob(), { premultiplyAlpha: "none", colorSpaceConversion: "none" });
  const c = document.createElement("canvas");
  c.width = bmp.width; c.height = bmp.height;
  const x = c.getContext("2d", { willReadFrequently: true })!;
  x.drawImage(bmp, 0, 0);
  return { w: bmp.width, h: bmp.height, d: x.getImageData(0, 0, bmp.width, bmp.height).data };
}

function pixeles(s2: ResultadoSentinel): Promise<Pixeles> {
  const d = s2.datos!;
  const k = d.rangos.slice(-64) + d.base.slice(-64);
  let p = cache.get(k);
  if (!p) {
    p = Promise.all([leer(d.rangos), leer(d.base)]).then(([a, b]) => ({ w: a.w, h: a.h, fe: a.d, base: b.d }));
    cache.clear();          // solo la cuadrícula abierta
    cache.set(k, p);
  }
  return p;
}

/** Filtro de moda 3×3 sobre una máscara binaria (= mayoría de 9; bordes replicados), como PIL ModeFilter(3). */
function moda3(m: Uint8Array, w: number, h: number): Uint8Array {
  const out = new Uint8Array(m.length);
  for (let y = 0; y < h; y++) {
    const y0 = y > 0 ? y - 1 : 0, y2 = y < h - 1 ? y + 1 : h - 1;
    for (let x = 0; x < w; x++) {
      const x0 = x > 0 ? x - 1 : 0, x2 = x < w - 1 ? x + 1 : w - 1;
      const n = m[y0 * w + x0] + m[y0 * w + x] + m[y0 * w + x2] + m[y * w + x0] + m[y * w + x] + m[y * w + x2]
        + m[y2 * w + x0] + m[y2 * w + x] + m[y2 * w + x2];
      out[y * w + x] = n >= 5 ? 1 : 0;
    }
  }
  return out;
}

type RGB = [number, number, number];

/** 10 clases de colores distintos para anomalía ferruginosa y arcillas = backend `CLASES_COLOR` (mantener iguales). */
export const CLASES_COLOR: string[] = ["#3b2a98", "#3f6fe0", "#22a7f0", "#14d0c4", "#3ae57f", "#a3f03a", "#f2d93a", "#fb9a2a", "#e8461b", "#8f0d0d"];
const CLASES_RGB: RGB[] = CLASES_COLOR.map((h) => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)]);
function pintarClase(img: Uint8ClampedArray, p: number, t: number) {
  const [r, g, b] = CLASES_RGB[Math.min(9, Math.floor(Math.min(1, Math.max(0, t)) * 10))];
  const o = p * 4;
  img[o] = r; img[o + 1] = g; img[o + 2] = b; img[o + 3] = 255;
}
function aUrl(img: Uint8ClampedArray<ArrayBuffer>, w: number, h: number): string {
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  c.getContext("2d")!.putImageData(new ImageData(img, w, h), 0, 0);
  return c.toDataURL("image/png");
}
const lienzo = (n: number) => new Uint8ClampedArray(new ArrayBuffer(n * 4));

export interface Recalculo {
  capas: Record<string, string>;
  celda: Partial<NonNullable<ResultadoSentinel["celda"]>>;
  /** % de los píxeles útiles que pasa CADA filtro por separado y los tres juntos */
  pasa?: { p_ndvi: number | null; p_ferruginosa: number; arcilla: number; todos: number };
}

/** Recalcula capas y porcentajes con otros cortes. `conImagenes` = false → solo los números (vista previa rápida). */
export async function recalcular(s2: ResultadoSentinel, c: Cortes, conImagenes = true, todasLasZonas = false): Promise<Recalculo> {
  // todasLasZonas (24/11/2026): la «sílice limpia» abarca también las zonas C; la app la recorta después a las
  // unidades que el usuario eligió para la Prioridad libre
  const { w, h, fe: R, base: B } = await pixeles(s2);
  const n = w * h;
  const valido = new Uint8Array(n), interes = new Uint8Array(n);
  const fe = new Uint8Array(n), cl = new Uint8Array(n), ok = new Uint8Array(n);
  // 1: R = férrico, G = ferroso (se aproxima con su promedio) · 2: R = ferruginosa · 3: + G = NDVI
  const formato = s2.datos?.formato ?? 1;
  const f3 = formato >= 3;
  const rcl = new Float32Array(n);
  let nArea = 0, nValidos = 0, pN = 0, pF = 0, pC = 0;
  for (let p = 0; p < n; p++) {
    const o = p * 4;
    if (B[o + 1] > 0) {
      nArea++;
      if ((B[o + 1] - 1) / 200 >= (todasLasZonas ? 0.3 : 0.6)) interes[p] = 1;      // zonas A (1) y B (0,7); la C (0,4) es «verificar»
    }
    if (B[o] === 0) continue;
    valido[p] = 1; nValidos++;
    const a = R[o + 2] / 255;
    const ferr = formato >= 2 ? R[o] / 255 : (R[o] + R[o + 1]) / 510;
    rcl[p] = a;
    fe[p] = ferr >= c.p_ferruginosa ? 1 : 0;
    cl[p] = a >= c.arcilla ? 1 : 0;
    const okN = !f3 || R[o + 1] / 255 < c.p_ndvi;
    if (okN) pN++;
    if (!fe[p]) pF++;
    if (!cl[p]) pC++;
    ok[p] = okN && !fe[p] && !cl[p] ? 1 : 0;
  }
  const cumple = moda3(ok, w, h);
  const fec = moda3(fe, w, h), clc = moda3(cl, w, h);
  const pct = (cuenta: number) => Math.round((1000 * cuenta) / Math.max(nArea, 1)) / 10;
  const util = (cuenta: number) => Math.round((1000 * cuenta) / Math.max(nValidos, 1)) / 10;
  const conZonas = !s2.solo_satelite;

  let nOk = 0, nFe = 0, nCl = 0, uFe = 0, uCl = 0, nInt = 0, nLimpia = 0, uOk = 0;
  for (let p = 0; p < n; p++) {
    if (cumple[p]) { nOk++; if (valido[p]) uOk++; }
    if (fec[p]) { nFe++; if (valido[p]) uFe++; }
    if (clc[p]) { nCl++; if (valido[p]) uCl++; }
    if (interes[p]) { nInt++; if (cumple[p]) nLimpia++; }
  }
  const celda: Recalculo["celda"] = {
    pct_cumple: pct(nOk), pct_excluido_hierro_arcilla: Math.round(10 * (100 - pct(nOk))) / 10,
    pct_hierro_alto: pct(nFe), pct_oxidos_altos: pct(nFe), pct_arcilla_alta: pct(nCl),
    anomalia_hierro_pct: util(uFe), anomalia_arcilla_pct: util(uCl),
    ...(conZonas ? { pct_interes: pct(nInt), pct_silice_limpia: pct(nLimpia) } : {}),
  };
  const pasa = { p_ndvi: f3 ? util(pN) : null, p_ferruginosa: util(pF), arcilla: util(pC), todos: util(uOk) };
  if (!conImagenes) return { capas: {}, celda, pasa };

  // ---- imágenes (mismos colores que el backend)
  const capas: Record<string, string> = {};
  if (conZonas) {
    const sl = lienzo(n);
    for (let p = 0; p < n; p++) {
      if (!interes[p] || !cumple[p]) continue;
      const o = p * 4; sl[o] = 22; sl[o + 1] = 163; sl[o + 2] = 74; sl[o + 3] = 255;
    }
    capas.silice_limpia = aUrl(sl, w, h);
  }
  // Arcillas y anomalía ferruginosa: 10 clases FIJAS (P0–P100). Solo se redibujan en análisis anteriores al
  // formato 3 (que las traían cortadas desde el percentil); en los nuevos el backend ya las manda así.
  if (!f3) {
    const arc = lienzo(n);
    for (let p = 0; p < n; p++) if (valido[p]) pintarClase(arc, p, rcl[p]);
    capas.arcillas = aUrl(arc, w, h);
    if (formato === 2) {
      const fr = lienzo(n);
      for (let p = 0; p < n; p++) if (B[p * 4 + 2] >= 2) pintarClase(fr, p, R[p * 4] / 255);
      capas.ferruginosas = aUrl(fr, w, h);
    }
  }
  return { capas, celda, pasa };
}

/**
 * SÍLICE LIMPIA POR UNIDAD (pedido del usuario, 24/11/2026: «cada litología se analiza diferente: se aíslan y se
 * determinan anomalías ferruginosas, arcilla y NDVI para cada una; es mucho mejor que un general»).
 * Cada unidad elegida (formación o depósito) se aísla y sus percentiles se calculan SOLO con sus píxeles:
 *   NDVI y ferruginosa → entre los píxeles con dato de la unidad · arcilla → entre los útiles de la unidad.
 * Pasa el píxel útil cuyo rango DENTRO de su unidad (fracción de píxeles de la unidad con valor menor) queda bajo
 * los cortes del usuario (los mismos percentiles para todas). Como los datos traen el rango de la cuadrícula
 * (función monótona del valor), ordenar por él dentro de la unidad = ordenar por el valor real (resolución 1/255).
 * Luego moda 3×3, igual que el cálculo general.
 */
export interface ResultadoUnidad { nombre: string; pixeles: number; utiles: number; pasa: number; pctPasa: number }
/** Rampas = backend `_RAMPA_NDVI` (pardo sin vegetación → verde oscuro vegetación densa) y `_RAMPA_BSI` (azul petróleo
 *  cubierto → blanco suelo/roca desnuda). Mantener iguales. */
export const RAMPA_NDVI: [number, RGB][] = [[0, [120, 72, 36]], [0.45, [214, 199, 161]], [0.7, [134, 190, 90]], [1, [20, 83, 45]]];
export const RAMPA_BSI: [number, RGB][] = [[0, [15, 60, 70]], [0.5, [150, 150, 125]], [0.8, [226, 214, 180]], [1, [255, 252, 240]]];
/** color CSS de una rampa en t (0–1): para pintar los histogramas igual que el mapa */
export function colorRampa(t: number, rampa: [number, RGB][]): string {
  let k = 0;
  while (k < rampa.length - 2 && t > rampa[k + 1][0]) k++;
  const [t0, a] = rampa[k], [t1, b] = rampa[k + 1];
  const f = Math.min(1, Math.max(0, (t - t0) / Math.max(t1 - t0, 1e-6)));
  return `rgb(${Math.round(a[0] + (b[0] - a[0]) * f)}, ${Math.round(a[1] + (b[1] - a[1]) * f)}, ${Math.round(a[2] + (b[2] - a[2]) * f)})`;
}
function pintarRampa(img: Uint8ClampedArray, p: number, t: number, rampa: [number, RGB][]) {
  let k = 0;
  while (k < rampa.length - 2 && t > rampa[k + 1][0]) k++;
  const [t0, a] = rampa[k], [t1, b] = rampa[k + 1];
  const f = Math.min(1, Math.max(0, (t - t0) / Math.max(t1 - t0, 1e-6)));
  const o = p * 4;
  img[o] = a[0] + (b[0] - a[0]) * f; img[o + 1] = a[1] + (b[1] - a[1]) * f; img[o + 2] = a[2] + (b[2] - a[2]) * f; img[o + 3] = 255;
}
/** (24/11/2026, «si se analiza por capas geológicas, las anomalías deben ser solo de esas capas») además de la
 *  sílice limpia, devuelve las capas Anomalías ferruginosas, Arcillas y NDVI SOLO dentro de las unidades elegidas, con
 *  colores por percentil DENTRO de cada unidad (10 clases fijas / rampa NDVI): el color coincide con el corte. */
export async function siliceLimpiaPorUnidad(s2: ResultadoSentinel, c: Cortes,
  unidades: { nombre: string; zonas: Afloramiento[] }[]): Promise<{ url: string; unidades: ResultadoUnidad[]; capas: Record<string, string> }> {
  const { w, h, fe: R, base: B } = await pixeles(s2);
  const n = w * h;
  const formato = s2.datos?.formato ?? 1;
  const f3 = formato >= 3;
  const [oeste, sur, este, norte] = s2.bbox!;
  const cv = document.createElement("canvas");
  cv.width = w; cv.height = h;
  const x = cv.getContext("2d", { willReadFrequently: true })!;
  const px = (lon: number, lat: number): [number, number] => [((lon - oeste) / (este - oeste)) * w, ((norte - lat) / (norte - sur)) * h];
  const ok = new Uint8Array(n);
  const res: ResultadoUnidad[] = [];
  const imFe = lienzo(n), imCl = lienzo(n), imNd = lienzo(n), imBs = lienzo(n);
  const f4 = formato >= 4;   // base B = 2 + 253·percentil de BSI en los píxeles con dato
  const ferr = (o: number) => (formato >= 2 ? R[o] : (R[o] + R[o + 1]) >> 1);   // 0–255
  // rango dentro de la unidad: fracción de sus píxeles con nivel MENOR (empates = mismo rango)
  const rangoDe = (hist: Uint32Array, total: number) => {
    const r = new Float32Array(256);
    let acu = 0;
    for (let v = 0; v < 256; v++) { r[v] = total ? acu / total : 0; acu += hist[v]; }
    return r;
  };
  for (const u of unidades) {
    x.clearRect(0, 0, w, h);
    x.fillStyle = "#000";
    for (const z of u.zonas) {
      x.beginPath();
      const polis = z.geometria.type === "Polygon" ? [z.geometria.coordinates] : z.geometria.coordinates;
      for (const poli of polis) for (const anillo of poli) {
        anillo.forEach(([lon, lat], k) => { const [xx, yy] = px(lon, lat); if (k) x.lineTo(xx, yy); else x.moveTo(xx, yy); });
        x.closePath();
      }
      x.fill("evenodd");
    }
    const M = x.getImageData(0, 0, w, h).data;
    const hFe = new Uint32Array(256), hNd = new Uint32Array(256), hCl = new Uint32Array(256), hBs = new Uint32Array(256);
    let nDato = 0, nUtil = 0, nPix = 0;
    for (let p = 0, o = 0; p < n; p++, o += 4) {
      if (M[o + 3] < 128) continue;
      nPix++;
      if (B[o + 2] >= 2) { nDato++; hFe[ferr(o)]++; if (f3) hNd[R[o + 1]]++; if (f4) hBs[B[o + 2] - 2]++; }
      if (B[o] > 0) { nUtil++; hCl[R[o + 2]]++; }
    }
    const rFe = rangoDe(hFe, nDato), rNd = rangoDe(hNd, nDato), rCl = rangoDe(hCl, nUtil), rBs = rangoDe(hBs, nDato);
    let nPasa = 0;
    for (let p = 0, o = 0; p < n; p++, o += 4) {
      if (M[o + 3] < 128) continue;
      // capas de la unidad (percentil dentro de ella): ferruginosa y NDVI donde hay dato, arcilla donde el suelo es útil
      if (B[o + 2] >= 2) {
        pintarClase(imFe, p, rFe[ferr(o)]);
        if (f3) pintarRampa(imNd, p, rNd[R[o + 1]], RAMPA_NDVI);
        if (f4) pintarRampa(imBs, p, rBs[B[o + 2] - 2], RAMPA_BSI);
      }
      if (B[o] > 0) pintarClase(imCl, p, rCl[R[o + 2]]);
      if (B[o] === 0) continue;        // solo píxeles útiles de la unidad
      if (rFe[ferr(o)] < c.p_ferruginosa && rCl[R[o + 2]] < c.arcilla && (!f3 || rNd[R[o + 1]] < c.p_ndvi)) { ok[p] = 1; nPasa++; }
    }
    res.push({ nombre: u.nombre, pixeles: nPix, utiles: nUtil, pasa: nPasa, pctPasa: nUtil ? Math.round((1000 * nPasa) / nUtil) / 10 : 0 });
  }
  const limpia = moda3(ok, w, h);
  const img = lienzo(n);
  for (let p = 0; p < n; p++) {
    if (!limpia[p]) continue;
    const o = p * 4; img[o] = 22; img[o + 1] = 163; img[o + 2] = 74; img[o + 3] = 255;
  }
  const capas: Record<string, string> = { ferruginosas: aUrl(imFe, w, h), arcillas: aUrl(imCl, w, h) };
  if (f3) capas.ndvi = aUrl(imNd, w, h);
  if (f4) capas.bsi = aUrl(imBs, w, h);
  return { url: aUrl(img, w, h), unidades: res, capas };
}

/** s2 con los cortes aplicados (capas, porcentajes y `cortes`). */
export async function aplicarCortes(s2: ResultadoSentinel, c: Cortes): Promise<ResultadoSentinel> {
  if (!recalculable(s2)) return s2;
  const r = await recalcular(s2, c);
  const base = sinCapasViejas(s2);
  return { ...base, cortes: c, capas: { ...base.capas, ...r.capas }, celda: base.celda ? { ...base.celda, ...r.celda } : base.celda };
}
