/**
 * APTITUD PARA VIDRIO FLOTADO según la DESCRIPCIÓN litológica de INGEMMET (pedido del usuario, 24/11/2026: «ordena
 * por la descripción: arena, arenisca cuarzosa, muy poco hierro; limolitas grises, lutitas negras… no deben
 * aparecer; y dime el estrato de la arenisca cuarzosa, arena cuarzosa o cuarcita, resaltado»).
 *
 * La descripción se corta en TRAMOS, uno por cada roca nombrada (en castellano los calificativos van después del
 * nombre: «Areniscas cuarzosas de grano medio, blanco amarillentos, intercaladas con limoarcillitas grises…»).
 * Cada tramo de roca SILÍCEA suma por tipo (arena > arenisca cuarzosa > cuarcita, prioridad del usuario), grano
 * (grueso/medio), color claro, madurez y estratos potentes, y resta por colores de hierro (rojizo, pardo,
 * amarillento…), ferromagnesianos, pirita, micas, materia orgánica, feldespato. Cada roca que NO sirve (limolita,
 * lutita, pizarra, caliza, volcánicas…) resta, más si es la roca principal. Es una lectura del texto, no un análisis
 * químico: ordena y resalta; el laboratorio decide.
 */

export type Tono = "bueno" | "malo" | "neutro";
export interface Tramo { texto: string; tono: Tono; roca?: string }
export interface Estrato { roca: string; texto: string; tipo: "potente" | "delgado" | "medio" }
export interface AptitudVidrio {
  puntaje: number;                       // 0–100
  nivel: "alta" | "media" | "baja" | "no";
  roca: string | null;                   // mejor roca silícea nombrada
  tramos: Tramo[];                       // la descripción completa, partida y con tono (para resaltar)
  a_favor: string[];
  en_contra: string[];
  estratos: Estrato[];                   // estratos/capas/bancos de la roca silícea
  espesor: string | null;                // espesor de la unidad, si lo dice
}

// minúsculas y sin tildes, MISMO largo que el original (para cortar el texto original con los mismos índices)
const TILDES: Record<string, string> = { á: "a", é: "e", í: "i", ó: "o", ú: "u", ü: "u", à: "a", è: "e", ì: "i", ò: "o", ù: "u" };
const plano = (s: string) => s.toLowerCase().replace(/[áéíóúüàèìòù]/g, (c) => TILDES[c] ?? c);

// Rocas: el orden importa (lo más largo primero). [regex, nombre, clase]
type ClaseRoca = "silice" | "neutra" | "mala";
const ROCAS: [RegExp, string, ClaseRoca, number][] = [
  [/arenas? (?:eolicas?,? )?(?:cuarzosas?|siliceas?|de cuarzo|blancas? cuarzosas?)/y, "arena cuarzosa", "silice", 46],
  [/(?:cuarzoarenitas?|ortocuarcitas?|cuarzo ?arenitas?)/y, "cuarzoarenita", "silice", 42],
  [/areniscas? (?:\w+ ){0,2}?(?:cuarzosas?|cuarciticas?|de cuarzo|siliceas?)/y, "arenisca cuarzosa", "silice", 38],
  [/(?:areniscas? arcosicas?|arcosas?|subarcosas?|grauvacas?|litarenitas?|areniscas? feldespaticas?|areniscas? tobaceas?|areniscas? calcareas?)/y, "arenisca arcósica o lítica", "mala", 0],
  [/(?:metareniscas?|metacuarcitas?|cuarcitas?)/y, "cuarcita", "silice", 28],
  [/(?:arenas?|areniscas?)/y, "arena o arenisca", "neutra", 12],
  [/(?:microconglomerados?|conglomerados?|gravas?|brechas?)/y, "conglomerado", "neutra", 0],
  [/(?:limoarcillitas?|limolitas?|lodolitas?|arcillitas?|lutitas?|pelitas?|argilitas?|arcillas?|limos?\b)/y, "limolita / lutita", "mala", 0],
  [/(?:pizarras?|filitas?|esquistos?|gneis\w*|micaesquistos?)/y, "pizarra / esquisto", "mala", 0],
  [/(?:calizas?|margas?|dolomitas?|dolomias?|yesos?|evaporitas?|travertinos?|carbon\b|carbones|mantos? de carbon)/y, "caliza / marga / yeso", "mala", 0],
  [/(?:lavas?|andesit\w*|basalt\w*|dacit\w*|riolit\w*|tobas?|piroclast\w*|volcan\w*|ignimbrit\w*|aglomerados?|granit\w*|granodiorit\w*|diorit\w*|tonalit\w*|intrusiv\w*)/y, "volcánica / ígnea", "mala", 0],
];
const INICIO = /[a-z]/;

interface Hallazgo { i: number; f: number; nombre: string; clase: ClaseRoca; base: number }
function hallarRocas(p: string): Hallazgo[] {
  const out: Hallazgo[] = [];
  let i = 0;
  while (i < p.length) {
    // solo al comienzo de una palabra
    if (INICIO.test(p[i]) && (i === 0 || !/[a-z]/.test(p[i - 1]))) {
      let hecho = false;
      for (const [re, nombre, clase, base] of ROCAS) {
        re.lastIndex = i;
        const m = re.exec(p);
        if (m && m.index === i) {
          out.push({ i, f: i + m[0].length, nombre, clase, base });
          i += m[0].length;
          hecho = true;
          break;
        }
      }
      if (hecho) continue;
    }
    i++;
  }
  return out;
}

// calificativos dentro del tramo de una roca silícea: [regex, puntos, texto]
const A_FAVOR: [RegExp, number, string][] = [
  [/blanc[oa]s?|blanquecin[oa]s?|hialin[oa]s?/, 9, "color blanco"],
  [/gris(?:es)? clar[oa]s?|crema|beige|bieges?/, 3, "color claro"],
  [/bien clasificad|buena seleccion|bien seleccionad/, 5, "bien clasificada"],
  [/redondead|subredondead/, 3, "granos redondeados"],
  [/supermadur|madur[oa]s?\b|limpi[oa]s?/, 5, "madura / limpia"],
  [/eolic/, 3, "eólica"],
  [/estratificacion (?:cruzada|sesgada|oblicua)|laminacion (?:oblicua|sesgada)/, 1, "estratificación cruzada"],
];
const EN_CONTRA: [RegExp, number, string][] = [
  [/rojiz|rojo|roja|rojas|rosad|rosace|ros[oa]s?\b|morad|violace/, -9, "color rojizo (hierro)"],
  [/pard[oa]|marron|amarill|ocre|naranj|anaranjad|abigarrad|limonit|hematit|goetit|ferrugin|oxidos? de hierro|ferrosos?|ferric/, -9, "color pardo-amarillento (óxidos de hierro)"],
  [/negr[oa]s?|oscur[oa]s?|carbonos|bitumin|materia organica/, -7, "oscura / materia orgánica"],
  [/verdos|glauconit|clorit/, -5, "verdosa (glauconita, clorita)"],
  [/ferromagnesian|mafic|biotit|anfibol|piroxen|magnetit|minerales pesados|minerales oscuros/, -8, "ferromagnesianos / minerales pesados"],
  [/pirit/, -7, "pirita"],
  [/micace|mica\b|micas\b|moscovit|sericit/, -4, "micácea"],
  [/feldesp|arcosic|litic/, -6, "feldespato o líticos"],
  [/calcare|calcit|carbonat/, -4, "cemento calcáreo"],
  [/arcillos|matriz/, -4, "matriz arcillosa"],
];

// estratos, capas, bancos… de una roca: «en estratos centimétricos a métricos», «capas medias a gruesas»
const ESTRATO = /(?:en |de |con )?(?:estratos?|capas?|bancos?|paquetes?|horizontes?|lentes?|niveles?|secuencias?|estratificad[oa]s?|laminad[oa]s?|masiv[oa]s?)(?: (?:de|en|muy|poco|bien))?[^,;.()]{0,48}/g;
const POTENTE = /grues|metric|potent|masiv|\d+(?:[.,]\d+)? ?m\b|\d+ ?a ?\d+ ?m\b|decametric|bancos?/;
const DELGADO = /delgad|centimetric|laminad|finos? estratos|milimetric|lajos/;
const ESPESOR = /(?:espesor|potencia|grosor)[^.;]{0,40}?(?:de |aprox\w*\.? |aproximad[oa] de |entre )?(\d[\d.,]*(?: ?a ?\d[\d.,]*)? ?(?:m|metros|km)\b)|[±+-]\s?(\d[\d.,]*) ?m\b/;

const GRANO = /grano (?:muy )?(grueso|medio|fino)(?: (?:a|y) (?:muy )?(grueso|medio|fino))?/;
function puntosGrano(t: string): [number, string] | null {
  const m = GRANO.exec(t);
  if (!m) return null;
  const set = new Set([m[1], m[2]].filter(Boolean));
  // rango con fino (p. ej. «medio a fino», «fino a grueso»): vale menos que medio solo (regla de vidrio_flotado.py)
  if (set.has("grueso") && !set.has("fino")) return [10, `grano ${m[2] ? `${m[1]} a ${m[2]}` : m[1]}`];
  if (set.has("medio") && !set.has("fino")) return [8, "grano medio"];
  if (set.has("fino") && set.size > 1) return [2, `grano ${m[1]} a ${m[2]}`];
  return [-4, "grano fino"];
}

export function aptitudVidrio(descripcion: string, litologia = "", rocaPrincipal = ""): AptitudVidrio {
  const texto = (descripcion && descripcion !== "<Null>" ? descripcion : litologia || "").replace(/<Null>/g, "").trim();
  const p = plano(texto);
  const rocas = hallarRocas(p);
  const tramos: Tramo[] = [];
  const a_favor: string[] = [], conMejor: string[] = [], malas: string[] = [];   // malas = rocas que no sirven y avisos
  const estratos: Estrato[] = [];
  let mejor = -1, mejorRoca: string | null = null, castigo = 0, nMalas = 0, principalMala = false;
  if (rocas.length && rocas[0].i > 0) tramos.push({ texto: texto.slice(0, rocas[0].i), tono: "neutro" });
  rocas.forEach((r, k) => {
    const fin = k + 1 < rocas.length ? rocas[k + 1].i : texto.length;
    const t = p.slice(r.i, fin);
    const tono: Tono = r.clase === "silice" ? "bueno" : r.clase === "mala" ? "malo" : "neutro";
    tramos.push({ texto: texto.slice(r.i, fin), tono, roca: r.nombre });
    // roca nombrada como CLASTO de otra («conglomerados con clastos de areniscas cuarzosas»): no es un estrato aprovechable
    const esClasto = /(?:clastos?|fragmentos?|cantos?|guijarros?|rodados?|bloques?) (?:\w+ ){0,2}de $/.test(p.slice(Math.max(0, r.i - 40), r.i));
    if (esClasto) {
      tramos[tramos.length - 1].tono = "neutro";
      malas.push(`${r.nombre} solo como clastos`);
      return;
    }
    if (k === 0 && r.nombre === "conglomerado") { castigo += 15; principalMala = true; malas.push("conglomerado como roca principal"); }
    if (r.clase === "silice" || (r.clase === "neutra" && r.base > 0)) {
      let pts = r.base;
      const fav: string[] = [], con: string[] = [];
      const g = puntosGrano(t);
      if (g) { pts += g[0]; (g[0] > 0 ? fav : con).push(g[1]); }
      for (const [re, v, txt] of A_FAVOR) if (re.test(t)) { pts += v; fav.push(txt); }
      for (const [re, v, txt] of EN_CONTRA) if (re.test(t)) { pts += v; con.push(txt); }
      ESTRATO.lastIndex = 0;
      for (let m = ESTRATO.exec(t); m; m = ESTRATO.exec(t)) {
        const frase = texto.slice(r.i + m.index, r.i + m.index + m[0].length).trim();
        if (frase.length < 6) continue;
        const tipo = POTENTE.test(m[0]) ? "potente" : DELGADO.test(m[0]) ? "delgado" : "medio";
        if (r.clase === "silice") {
          estratos.push({ roca: r.nombre, texto: frase, tipo });
          pts += tipo === "potente" ? 5 : tipo === "delgado" ? -3 : 0;
        }
      }
      if (pts > mejor) {
        mejor = pts; mejorRoca = r.nombre;
        a_favor.splice(0, a_favor.length, `${r.nombre}`, ...fav);
        conMejor.splice(0, conMejor.length, ...con);
      }
    } else if (r.clase === "mala") {
      // roca que no sirve (pedido del usuario: limolitas, lutitas… «no deben aparecer»): resta fuerte; más si es la
      // primera nombrada (la principal) o tiene colores de hierro u oscuros
      let v = k === 0 ? 30 : nMalas === 0 ? 18 : 6;
      if (k === 0) principalMala = true;
      nMalas++;
      if (/rojiz|pard|amarill|marron|negr|oscur|bitumin|carbonos|morad|verdos/.test(t)) v += 5;
      castigo += v;
      // la roca y sus calificativos inmediatos («lutitas negras», «limoarcillitas pardo amarillentas»)
      const PARAR = new Set(["con", "de", "del", "y", "e", "en", "a", "o", "que", "hacia", "para", "fisible", "fisibles"]);
      const palabras: string[] = [];
      for (const w of texto.slice(r.i, fin).split(/[\s]+/)) {
        const limpio = w.replace(/[,;.:()]+$/, "");
        if (palabras.length && (PARAR.has(plano(limpio)) || /^(intercal|interestrat|altern)/.test(plano(limpio)))) break;
        if (limpio) palabras.push(limpio);
        if (palabras.length >= 4 || limpio !== w) break;
      }
      const nom = palabras.join(" ");
      if (!malas.includes(nom)) malas.push(nom);
    }
  });
  if (!rocas.length && texto) tramos.push({ texto, tono: "neutro" });
  // la roca principal de la 50K (LITO1) manda si no es silícea
  if (rocaPrincipal && !/cuarz|cuarcit|silice|arena/.test(plano(rocaPrincipal)) && rocas[0]?.clase !== "mala") castigo += 8;
  const puntaje = mejor < 0 ? 0 : Math.max(0, Math.min(100, Math.round(mejor + 30 - castigo)));
  let nivel: AptitudVidrio["nivel"] = mejor < 0 ? "no" : puntaje >= 62 ? "alta" : puntaje >= 42 ? "media" : puntaje >= 20 ? "baja" : "no";
  // «arenisca» sin decir que es cuarzosa, o intercalada con rocas que no sirven: como mucho media;
  // si la roca PRINCIPAL no sirve (p. ej. «Limolitas grises con intercalación de areniscas cuarzosas»): como mucho baja
  if ((mejorRoca === "arena o arenisca" || nMalas > 0) && nivel === "alta") nivel = "media";
  if (principalMala && nivel === "media") nivel = "baja";
  const e = ESPESOR.exec(p);
  const espesor = e ? (e[1] ?? `±${e[2]}`).replace(/metros/, "m") : null;
  return { puntaje, nivel, roca: mejorRoca, tramos, a_favor, en_contra: [...conMejor, ...malas], estratos, espesor };
}

export const NIVEL_TEXTO: Record<AptitudVidrio["nivel"], string> = {
  alta: "Apta para vidrio", media: "Aptitud media", baja: "Aptitud baja", no: "No apta",
};
