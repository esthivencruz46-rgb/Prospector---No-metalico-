/**
 * PRIORIDAD LIBRE (definición del usuario, 23/11/2026), en el navegador y sin créditos:
 * geología silícea de interés (zonas A y B) ∩ NDVI · BSI · ferruginosa · arcilla (máscara «silice_limpia» con los
 * cortes del usuario; sin satélite, solo las zonas) − áreas protegidas, pintada según el catastro y el uso del
 * suelo con la lámina `GET /libres/imagen?modo=prioridad` del MISMO recuadro y tamaño (Web Mercator vs. grilla
 * lineal: en una cuadrícula de 7,5′ la diferencia es < 0,1 %). Hectáreas totales y por zona.
 */
import { api, type Afloramiento } from "./api";

export interface PrioridadLibre {
  url: string;                 // data URL PNG en la grilla de `bbox`
  bbox: [number, number, number, number];
  haAlta: number;              // sílice limpia A/B en toda la cuadrícula (todas las categorías)
  haLibre: number;             // verde: libre y utilizable
  haExtinguido: number;        // celeste: sobre derechos extinguidos (libre con observación)
  haNegociable: number;        // azul: concesión titulada / en trámite (negociar con el titular)
  haNoApto: number;            // amarillo: libre pero chacra, poblado, vía o río
  sinSatelite: boolean;        // la zona no se pudo limpiar de hierro/arcilla (sin Sentinel-2)
  porZona: Record<string, { haAlta: number; haLibre: number; haExtinguido: number; haNegociable: number; haNoApto: number }>;
}

function cargar(src: string): Promise<HTMLImageElement> {
  return new Promise((ok, mal) => {
    const im = new Image();
    im.onload = () => ok(im);
    im.onerror = () => mal(new Error("no se pudo leer la imagen"));
    im.src = src;
  });
}

/** Colores de la PRIORIDAD LIBRE = backend/libres.py (PRIO_*): verde libre · azul concesión titulada/en trámite ·
 *  amarillo libre pero chacra/poblado/vía/río · celeste derecho extinguido. */
export const COLOR_PRIO = { verde: [22, 197, 94], azul: [37, 99, 235], amarillo: [250, 204, 21], celeste: [125, 211, 252] } as const;
const parecido = (d: Uint8ClampedArray, i: number, c: readonly number[]) =>
  d[i + 3] > 100 && Math.abs(d[i] - c[0]) < 16 && Math.abs(d[i + 1] - c[1]) < 16 && Math.abs(d[i + 2] - c[2]) < 16;

/** Máscara de las zonas dadas (las de las unidades elegidas) en la grilla de la cuadrícula (cuando no hay Sentinel-2). */
export function mascaraZonas(bbox: [number, number, number, number], zonas: Afloramiento[]): string {
  const [oeste, sur, este, norte] = bbox;
  const w = 640;
  const h = Math.max(64, Math.round(w * (norte - sur) / ((este - oeste) * Math.cos(((sur + norte) / 2) * Math.PI / 180))));
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  const x = c.getContext("2d")!;
  const px = (lon: number, lat: number): [number, number] => [((lon - oeste) / (este - oeste)) * w, ((norte - lat) / (norte - sur)) * h];
  x.fillStyle = "rgb(22,163,74)";
  // (24/11/2026) las zonas las elige el usuario por unidad; por defecto, las de clase A y B
  for (const z of zonas) {
    x.beginPath();
    const polis = z.geometria.type === "Polygon" ? [z.geometria.coordinates] : z.geometria.coordinates;
    for (const poli of polis) for (const anillo of poli) {
      anillo.forEach(([lon, lat], k) => { const [xx, yy] = px(lon, lat); if (k) x.lineTo(xx, yy); else x.moveTo(xx, yy); });
      x.closePath();
    }
    x.fill("evenodd");
  }
  return c.toDataURL("image/png");
}

/**
 * PRIORIDAD LIBRE (definición del 24/11/2026): zonas A/B ∩ los tres filtros de Sentinel-2 (la máscara
 * «silice_limpia» de Sentinel-2, o solo las zonas si no hay satélite) − áreas protegidas, pintada según el catastro y
 * el uso del suelo con la lámina `GET /libres/imagen?modo=prioridad` del mismo recuadro y tamaño.
 */
export async function componerPrioridadSilice(urlMascara: string, bbox: [number, number, number, number], zonas: Afloramiento[],
  sinSatelite = false, recorte?: Afloramiento[]): Promise<PrioridadLibre> {
  const masc = await cargar(urlMascara);
  const w = masc.naturalWidth, h = masc.naturalHeight;
  const [oeste, sur, este, norte] = bbox;
  const resp = await fetch(api.urlLibres({ oeste, sur, este, norte }, w, h, "prioridad"));
  if (!resp.ok) throw new Error(`áreas libres: ${resp.status}`);
  const libres = await createImageBitmap(await resp.blob());
  const lienzo = (): [HTMLCanvasElement, CanvasRenderingContext2D] => {
    const c = document.createElement("canvas");
    c.width = w; c.height = h;
    return [c, c.getContext("2d", { willReadFrequently: true })!];
  };
  const [, xM] = lienzo();
  xM.drawImage(masc, 0, 0);
  const M = xM.getImageData(0, 0, w, h).data;
  // RECORTE a las unidades elegidas por el usuario (formación, formaciones o formación y depósito)
  if (recorte) {
    const [, xR] = lienzo();
    const pxR = (lon: number, lat: number): [number, number] => [((lon - oeste) / (este - oeste)) * w, ((norte - lat) / (norte - sur)) * h];
    xR.fillStyle = "#000";
    for (const z of recorte) {
      xR.beginPath();
      const polis = z.geometria.type === "Polygon" ? [z.geometria.coordinates] : z.geometria.coordinates;
      for (const poli of polis) for (const anillo of poli) {
        anillo.forEach(([lon, lat], k) => { const [xx, yy] = pxR(lon, lat); if (k) xR.lineTo(xx, yy); else xR.moveTo(xx, yy); });
        xR.closePath();
      }
      xR.fill("evenodd");
    }
    const Rc = xR.getImageData(0, 0, w, h).data;
    for (let i = 3; i < M.length; i += 4) if (Rc[i] < 128) M[i] = 0;
  }
  const [, xL] = lienzo();
  xL.drawImage(libres, 0, 0);
  const L = xL.getImageData(0, 0, w, h).data;
  const [cO, xO] = lienzo();
  const O = xO.createImageData(w, h);
  const latMed = ((sur + norte) / 2) * Math.PI / 180;
  const haPx = ((este - oeste) * 111320 * Math.cos(latMed) / w) * ((norte - sur) * 110540 / h) / 10000;
  // tipo: 0 nada · 1 sílice limpia pero protegida u otra concesión (oculta) · 2 libre · 3 extinguido · 4 concesión · 5 chacra…
  const tipo = new Uint8Array(w * h);
  let tot = 0, v = 0, ce = 0, az = 0, am = 0;
  for (let p = 0, i = 0; p < w * h; p++, i += 4) {
    if (M[i + 3] < 128) continue;
    tot++;
    const c = parecido(L, i, COLOR_PRIO.verde) ? (v++, tipo[p] = 2, COLOR_PRIO.verde)
      : parecido(L, i, COLOR_PRIO.celeste) ? (ce++, tipo[p] = 3, COLOR_PRIO.celeste)
        : parecido(L, i, COLOR_PRIO.azul) ? (az++, tipo[p] = 4, COLOR_PRIO.azul)
          : parecido(L, i, COLOR_PRIO.amarillo) ? (am++, tipo[p] = 5, COLOR_PRIO.amarillo) : (tipo[p] = 1, null);
    if (!c) continue;
    O.data[i] = c[0]; O.data[i + 1] = c[1]; O.data[i + 2] = c[2]; O.data[i + 3] = 215;
  }
  xO.putImageData(O, 0, 0);
  const porZona: PrioridadLibre["porZona"] = {};
  const [, xZ] = lienzo();
  const px = (lon: number, lat: number): [number, number] => [((lon - oeste) / (este - oeste)) * w, ((norte - lat) / (norte - sur)) * h];
  for (const z of zonas) {
    xZ.clearRect(0, 0, w, h);
    xZ.beginPath();
    const polis = z.geometria.type === "Polygon" ? [z.geometria.coordinates] : z.geometria.coordinates;
    for (const poli of polis) for (const anillo of poli) {
      anillo.forEach(([lon, lat], k) => { const [xx, yy] = px(lon, lat); if (k) xZ.lineTo(xx, yy); else xZ.moveTo(xx, yy); });
      xZ.closePath();
    }
    xZ.fillStyle = "#000";
    xZ.fill("evenodd");
    const Z = xZ.getImageData(0, 0, w, h).data;
    const n = [0, 0, 0, 0, 0, 0];
    for (let p = 0, i = 3; p < w * h; p++, i += 4) if (Z[i] >= 128 && tipo[p]) n[tipo[p]]++;
    const ha = (k: number) => +(k * haPx).toFixed(1);
    porZona[z.id] = { haAlta: ha(n[1] + n[2] + n[3] + n[4] + n[5]), haLibre: ha(n[2]), haExtinguido: ha(n[3]), haNegociable: ha(n[4]), haNoApto: ha(n[5]) };
  }
  const ha = (k: number) => +(k * haPx).toFixed(1);
  return { url: cO.toDataURL("image/png"), bbox, haAlta: ha(tot), haLibre: ha(v), haExtinguido: ha(ce), haNegociable: ha(az), haNoApto: ha(am),
    sinSatelite, porZona };
}
