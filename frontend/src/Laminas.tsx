// Láminas cartográficas profesionales de una cuadrícula (y de la ruta): la app arma el contenido con lo
// que ya tiene del análisis y el servidor dibuja la lámina A3 (backend/laminas.py): marco UTM, norte,
// escalas, ubicación por departamento, leyenda, datos y membrete.
import { useState } from "react";
import { Download, FileImage, Loader2 } from "lucide-react";
import { CLASES_COLOR, conNdviBsi, cortesDe, cortesGuardados, recalculable, recalcular } from "./cortes";

/** Leyenda de 10 clases (tramos de percentil del rango mostrado). */
const leyendaClases = (p0: number, menos: string, mas: string) => CLASES_COLOR.map((color, i) => {
  const a = Math.round(100 * (p0 + ((1 - p0) * i) / 10)), b = Math.round(100 * (p0 + ((1 - p0) * (i + 1)) / 10));
  return { color, texto: `Clase ${i + 1} · P${a}–P${b}${i === 0 ? ` (${menos})` : i === 9 ? ` (${mas})` : ""}` };
});
import { api, type Afloramiento, type ResultadoBusqueda, type ResultadoSentinel, type Ruta } from "./api";
import { gms, type Celda } from "./geo";

type Tipo = "natural" | "swir" | "ndvi" | "bsi" | "ferruginosas" | "arcillas" | "protegidas" | "concesiones" | "libres"
  | "geologia_completa" | "geologia_desc" | "topografia" | "geologia_libre" | "prioridad" | "ruta" | "antecedentes" | "unidades" | "analisis" | "geologia";
interface Props {
  celda: Celda;
  res: ResultadoBusqueda;
  s2: ResultadoSentinel | null;
  materia: string;                          // nombre de la materia prima
  /** Prioridad libre ya compuesta (PNG en la grilla de `bbox`) y sus hectáreas por color. */
  prioridadLibre?: { url: string; bbox: number[]; libre: number; negociable: number; noApto: number; extinguido: number;
                     sinSatelite: boolean; unidades?: string[] } | null;
  /** las unidades elegidas recortadas a las zonas libres, SIN los filtros satelitales (lámina «geologia_libre») */
  geologiaLibre?: { url: string; bbox: number[]; libre: number; negociable: number; noApto: number; extinguido: number;
                    sinSatelite: boolean; unidades?: string[] } | null;
  ruta?: { ruta: Ruta; destino: { lat: number; lon: number; nombre: string } } | null;
  /** modo «Informe PDF»: todas las láminas en orden + portada, antecedentes y análisis, numeradas, en un solo PDF */
  informe?: boolean;
  /** NDVI, ferruginosa y arcillas solo dentro de estas unidades (percentiles de cada una); null = toda la cuadrícula */
  ambitoUnidades?: string[] | null;
  /** unidades elegidas para la Prioridad libre con su resultado (página «Análisis bibliográfico de las unidades elegidas») */
  unidadesPrio?: { nombre: string; libre: number | null; negociable: number | null; pasa: number | null }[];
  /** unidad con más hectáreas libres en la Prioridad libre (para la síntesis del informe) */
  mejorZona?: { unidad: string; ha: number } | null;
  /** opacidad elegida por el usuario en el mapa (0–1) para las capas continuas */
  opacidades?: Partial<Record<string, number>>;
  fabrica: [number, number];
  onCerrar: () => void;
}

const CLAVE_AUTOR = "prospector-rmi:autor";
const CLAVE_EMPRESA = "prospector-rmi:empresa";
const CLAVE_PROYECTO = "prospector-rmi:proyecto";
const PROYECTO_DEFECTO = "Prospección de arena silícea para vidrio flotado";
const EMPRESA_DEFECTO = "KEDA Perú Building Materials Company";
const FABRICA_NOMBRE = "Planta KEDA Perú · San Vicente de Cañete";
// ORDEN del informe (pedido del usuario, 24/11/2026)
// ORDEN del informe (pedido del usuario, 24/11/2026); «geologia» (zonas A/B/C) queda fuera del informe
const NOMBRES: Record<Tipo, string> = {
  natural: "Imagen real · Sentinel-2 (4-3-2): fecha, hora y nubosidad",
  swir: "Imagen geológica · Sentinel-2 (12-11-2): bandas y motivo",
  ndvi: "NDVI · vegetación", bsi: "BSI · suelo y roca desnuda",
  ferruginosas: "Anomalías ferruginosas (férrico + ferroso) al 100 %", arcillas: "Arcillas, micas y sulfatos (B11/B12) al 100 %",
  protegidas: "Áreas protegidas y restringidas", concesiones: "Concesiones mineras (catastro de INGEMMET)",
  libres: "Zonas libres para petitorio y aptas para cantera", geologia_completa: "Mapa geológico de la cuadrícula",
  geologia_desc: "Descripción de las unidades geológicas", topografia: "Mapa topográfico",
  geologia_libre: "Geología elegida en zonas libres (sin filtros satelitales)",
  prioridad: "Prioridad libre de la geología elegida (∩ NDVI · ferruginosa · arcilla)", ruta: "Ruta desde la planta KEDA",
  antecedentes: "Antecedentes bibliográficos (boletines de INGEMMET)",
  unidades: "Análisis bibliográfico de las unidades elegidas", analisis: "Análisis de las capas y síntesis",
  geologia: "Geología de interés (zonas A/B/C)",
};

export default function Laminas({ celda, res, s2, materia, prioridadLibre, geologiaLibre, ruta, fabrica, opacidades, informe, mejorZona, unidadesPrio, ambitoUnidades, onCerrar }: Props) {
  const porUnidad = !!ambitoUnidades?.length;
  const listaUds = (ambitoUnidades ?? []).map((u) => u.replace(/^Grupo [^-]+ - /, "")).join(", ");
  const [autor, setAutor] = useState(() => { try { return localStorage.getItem(CLAVE_AUTOR) ?? ""; } catch { return ""; } });
  const [proyecto, setProyecto] = useState(() => { try { return localStorage.getItem(CLAVE_PROYECTO) ?? PROYECTO_DEFECTO; } catch { return PROYECTO_DEFECTO; } });
  const [empresa, setEmpresa] = useState(() => { try { return localStorage.getItem(CLAVE_EMPRESA) ?? EMPRESA_DEFECTO; } catch { return EMPRESA_DEFECTO; } });
  const [estado, setEstado] = useState<Partial<Record<Tipo | "pdf" | "portada", "generando" | "listo" | string>>>({});
  const [avance, setAvance] = useState<{ hechas: number; total: number; mb?: number | null; errores?: string[] } | null>(null);
  const bbox = s2?.bbox;
  const disponible: Record<Tipo, string | null> = {
    geologia: res.afloramientos.length ? null : "sin zonas favorables en esta cuadrícula",
    arcillas: s2?.capas?.arcillas && bbox ? null : "necesita el análisis Sentinel-2",
    libres: res.libres ? null : "necesita las áreas libres (INGEMMET)",
    prioridad: prioridadLibre ? null : "necesita zonas A/B y las áreas libres (INGEMMET)",
    geologia_libre: geologiaLibre ? null : "elige unidades y espera las áreas libres (INGEMMET)",
    natural: s2?.capas?.natural && bbox ? null : "necesita el análisis Sentinel-2",
    swir: s2?.capas?.swir && bbox ? null : "necesita el análisis Sentinel-2",
    ndvi: s2?.capas?.ndvi && bbox ? null : "necesita un análisis Sentinel-2 nuevo («Nueva toma»)",
    bsi: s2?.capas?.bsi && bbox ? null : "necesita un análisis Sentinel-2 nuevo («Nueva toma»)",
    ferruginosas: s2?.capas?.ferruginosas && bbox ? null : "necesita un análisis Sentinel-2 nuevo («Nueva toma»)",
    ruta: ruta ? null : "primero traza una ruta (botón de ruta)",
    protegidas: null, concesiones: null,          // los consulta el servidor en GEOCATMIN
    geologia_completa: res.soloSatelite ? "necesita la geología" : null,
    geologia_desc: res.soloSatelite ? "necesita la geología" : null,
    topografia: null,
    antecedentes: res.soloSatelite ? "necesita la geología" : null,
    unidades: res.soloSatelite ? "necesita la geología" : !unidadesPrio?.length ? "elige unidades para la Prioridad libre" : null,
    analisis: s2?.disponible && !res.soloSatelite ? null : "necesita geología + Sentinel-2",
  };
  const [formato, setFormato] = useState<"pdf" | "png">(() => { try { return localStorage.getItem("prospector-rmi:formato-lamina") === "png" ? "png" : "pdf"; } catch { return "pdf"; } });
  const [elegidas, setElegidas] = useState<Set<Tipo>>(() => new Set((Object.keys(NOMBRES) as Tipo[])
    .filter((t) => !disponible[t] && !(informe && t === "geologia"))));

  const zonas = (relleno: number) => res.afloramientos.map((a: Afloramiento) => ({ clase: a.clase, unidad: a.unidad, geometria: a.geometria, relleno }));
  const leyendaZonas = [
    { color: "#dc2626", texto: "Zona A · depósito (lo mejor)" },
    { color: "#f59e0b", texto: "Zona B · roca / formación de interés" },
    { color: "#facc15", texto: "Zona C · verificar en campo" },
  ].filter((_, i) => res.afloramientos.some((a) => a.clase === "ABC"[i]));
  // SOLO las unidades elegidas para la Prioridad (pedido del usuario: «solo debe estar la geología que selecciono»)
  const selUds = new Set(unidadesPrio?.map((u) => u.nombre) ?? []);
  const zonasElegidas = (relleno: number) => res.afloramientos.filter((a) => !selUds.size || selUds.has(a.unidad))
    .map((a: Afloramiento) => ({ clase: a.clase, unidad: a.unidad, geometria: a.geometria, relleno }));
  const leyendaElegidas = [...new Map(res.afloramientos.filter((a) => selUds.has(a.unidad)).map((a) => [a.unidad, a])).values()]
    .map((a) => ({ color: a.clase === "A" ? "#dc2626" : a.clase === "B" ? "#f59e0b" : "#facc15", forma: "borde",
      texto: `Unidad analizada: ${a.unidad.replace(/^Grupo [^-]+ - /, "")}` }));
  const ha = (cl: string) => Math.round(res.afloramientos.filter((a) => a.clase === cl).reduce((s, a) => s + a.area_ha, 0));
  const kmFab = Math.round(Math.hypot((celda.norte + celda.sur) / 2 - fabrica[0], ((celda.oeste + celda.este) / 2 - fabrica[1]) * Math.cos(fabrica[0] * Math.PI / 180)) * 111.2);
  const datosBase: [string, string][] = [
    ["Cuadrícula 1:25 000", celda.codigo],
    ["Hoja 1:50 000 · 1:100 000", `${celda.codigo.split("-")[0]} · ${celda.hoja100}`],
    ["Límite norte · sur", `${gms(celda.norte, true)} · ${gms(celda.sur, true)}`],
    ["Límite oeste · este", `${gms(celda.oeste, false)} · ${gms(celda.este, false)}`],
    ["Materia prima", materia],
    ["Carta geológica usada", res.escala_usada ? `1:${res.escala_usada === "50K" ? "50 000" : "100 000"}` : "—"],
    ["Zonas A · B · C (ha)", `${ha("A")} · ${ha("B")} · ${ha("C")}`],
    ["Distancia a la fábrica", `≈ ${kmFab} km en línea recta`],
  ];
  const toma = s2?.imagen?.fecha_peru ? `${s2.imagen.fecha_peru} (hora de Perú)` : s2?.periodo ?? "—";
  const capa = (png: string, opacidad = 0.9) => ({ png, crs: "4326", bbox, opacidad });
  const ct = s2 ? cortesDe(s2) : null;
  const P = (x?: number) => `P${Math.round((x ?? 0) * 100)}`;
  const c4 = ct ?? cortesGuardados();
  const filtros = `NDVI < ${P(c4.p_ndvi)} · ferruginosa < ${P(c4.p_ferruginosa)} · arcilla < ${P(c4.arcilla)}`;

  async function peticion(t: Tipo): Promise<Record<string, unknown>> {
    const base = { tipo: t, autor, empresa, proyecto, celda: { codigo: celda.codigo, sur: celda.sur, oeste: celda.oeste, norte: celda.norte, este: celda.este },
      subtitulo: `Cuadrícula ${celda.codigo}` };
    switch (t) {
      case "geologia":
        return { ...base, titulo: `Mapa de geología de interés · ${materia}`, zonas: zonas(95), leyenda: leyendaZonas,
          datos: datosBase, fuente: "INGEMMET · geología integrada (GEOCATMIN)" };
      case "arcillas": {
        // AL 100 % (pedido del usuario): se dibuja con el corte en 0, todo el suelo visible
        // 10 clases fijas: en los análisis nuevos ya viene así; en los anteriores se redibuja en el navegador
        const img = (!porUnidad && recalculable(s2!) && !conNdviBsi(s2!) ? (await recalcular(s2!, c4)).capas.arcillas : undefined) ?? s2!.capas!.arcillas;
        const op = opacidades?.s2_arcillas ?? 0.8;
        return { ...base, titulo: porUnidad ? "Arcillas, micas y sulfatos en las unidades elegidas (Sentinel-2 B11/B12)"
            : "Arcillas, micas y sulfatos al 100 % (Sentinel-2 B11/B12)", capas: [capa(s2!.capas!.natural, 1), capa(img, op)],
          leyenda: leyendaClases(0, "menos arcilla", "máxima absorción a 2,2 µm"),
          datos: [...datosBase.slice(0, 2), ["Toma Sentinel-2", toma], ["Cociente", "B11 / B12 (absorción a 2,2 µm: arcillas, micas, sericita, sulfatos)"],
            ["Escala", porUnidad ? "10 clases (deciles) dentro de cada unidad elegida, de su suelo visible" : "10 clases de igual número de píxeles (deciles), 100 % del suelo visible"],
            ...(porUnidad ? [["Unidades", listaUds] as [string, string]] : []),
            ["Filtro de la Prioridad libre", `Pasan las clases bajo ${P(c4.arcilla)}`],
            ["Presentación", `Sobre la imagen real 4-3-2, opacidad ${Math.round(op * 100)} %`], ["Excluido", "Vegetación, nubes y agua (no se mide)"]],
          fuente: "Sentinel-2 L2A (ESA Copernicus) · INGEMMET" };
      }
      case "natural": {
        const im = s2?.imagen;
        const [fecha, hora] = (im?.fecha_peru ?? "").split(" ");
        return { ...base, titulo: "Imagen real · Sentinel-2 (bandas 4-3-2)",
          capas: [capa(s2!.capas!.natural, 1)],
          datos: [...datosBase.slice(0, 2),
            ["Fecha de la toma", fecha || (s2?.periodo ?? "—")], ["Hora de la toma", hora ? `${hora} (hora de Perú, UTC−5)` : "—"],
            ["Hora UTC", im?.fecha_utc ? im.fecha_utc.slice(11, 16) : "—"],
            ["Nubosidad en la cuadrícula", im?.nubes_cuadricula != null ? `${im.nubes_cuadricula} %` : "—"],
            ["Nubosidad de la escena (~110 km)", im?.nubes_escena != null ? `${im.nubes_escena} %` : "—"],
            ["Vegetación en la toma", im?.vegetacion_cuadricula != null ? `${im.vegetacion_cuadricula} %` : "—"],
            ["Combinación", "R = B4 (rojo) · G = B3 (verde) · B = B2 (azul): color natural"],
            ["Satélite · resolución", "Sentinel-2 L2A · 10 m"], ["Fuente de la imagen", (s2?.fuente ?? "Copernicus").replace(/ \(.*\)$/, "")]],
          fuente: "Sentinel-2 L2A (ESA Copernicus) · INGEMMET" };
      }
      case "swir":
        return { ...base, titulo: "Imagen geológica · Sentinel-2 (bandas 12-11-2)",
          capas: [capa(s2!.capas!.swir, 1)],
          datos: [...datosBase.slice(0, 2), ["Toma Sentinel-2", toma],
            ["Rojo = B12", "SWIR 2 · 2,19 µm (20 m)"], ["Verde = B11", "SWIR 1 · 1,61 µm (20 m)"], ["Azul = B2", "Azul · 0,49 µm (10 m)"],
            ["Motivo", "El infrarrojo de onda corta separa las rocas por su mineralogía mejor que el color visible"],
            ["Arenisca, cuarcita, arena", "Reflejan alto y parejo en B11 y B12: tonos claros"],
            ["Arcillas, micas, carbonatos", "Absorben a 2,2 µm (B12): cambian de tono frente a la roca cuarzosa"],
            ["Vegetación · agua", "Vegetación en verde (B11 > B12); agua y humedad oscuras"],
            ["Ventaja", "El SWIR atraviesa mejor la bruma que el visible"]],
          fuente: "Sentinel-2 L2A (ESA Copernicus) · INGEMMET" };
      case "ndvi":
      case "bsi":
      case "ferruginosas": {
        const op = opacidades?.[`s2_${t}`] ?? 0.6;
        // anomalía ferruginosa AL 100 % (pedido del usuario): se dibuja con el corte en 0
        const img = t === "ferruginosas" && !porUnidad && recalculable(s2!) && s2!.datos?.formato === 2
          ? (await recalcular(s2!, c4)).capas.ferruginosas ?? s2!.capas!.ferruginosas
          : s2!.capas![t];
        const T = {
          ndvi: { titulo: "NDVI · vegetación (Sentinel-2)", indice: "NDVI = (B8 − B4) / (B8 + B4)",
            ley: [["#784824", "Sin vegetación: roca o suelo (percentil 0)"], ["#d6c7a1", "Vegetación escasa"], ["#86be5a", "Vegetación media"], ["#14532d", "Vegetación densa (percentil 100)"]] },
          bsi: { titulo: "BSI · suelo y roca desnuda (Sentinel-2)", indice: "BSI = ((B11 + B4) − (B8 + B2)) / ((B11 + B4) + (B8 + B2))",
            ley: [["#0f3c46", "Cubierto o húmedo (percentil 0)"], ["#96967d", "Cobertura parcial"], ["#e2d6b4", "Suelo o roca poco cubierta"], ["#fffcf0", "Suelo o roca desnuda (percentil 100)"]] },
          ferruginosas: { titulo: "Anomalías ferruginosas al 100 % (férrico + ferroso)",
            indice: "Férrico (B4/B2 + B4/B3: hematita, goethita, limonita) + ferroso (B11/B8A: máficos, clorita, biotita)",
            ley: leyendaClases(0, "menos hierro", "lo más ferruginoso").map((x) => [x.color, x.texto]) },
        }[t];
        const enUds = porUnidad && (t !== "bsi" || (s2?.datos?.formato ?? 0) >= 4);   // BSI por unidad desde el formato 4
        return { ...base, titulo: enUds ? T.titulo.replace(" al 100 %", "").replace(/ \(Sentinel-2\)$/, "") + " · unidades elegidas" : T.titulo,
          capas: [capa(s2!.capas!.natural, 1), capa(img, op)],
          leyenda: T.ley.map(([color, texto]) => ({ color, texto })),
          datos: [...datosBase.slice(0, 2), ["Toma Sentinel-2", toma], ["Índice", T.indice],
            ["Escala", enUds ? (t === "ferruginosas" ? "10 clases (deciles) dentro de cada unidad elegida" : "Continua: percentil de cada píxel dentro de su unidad")
              : t === "ferruginosas" ? "10 clases de igual número de píxeles (deciles), 100 % de los datos"
              : "Continua, 100 % de los datos: percentil de cada píxel en la cuadrícula (sin corte)"],
            ...(enUds ? [["Unidades", listaUds] as [string, string]] : []),
            ["Filtro de la Prioridad libre", t === "ferruginosas" ? `Pasan las clases bajo ${P(c4.p_ferruginosa)}`
              : t === "ndvi" ? `Pasa lo que está bajo ${P(c4.p_ndvi)} (sin vegetación y escasa)` : "No entra en la Prioridad libre (solo referencia)"],
            ["Presentación", `Sobre la imagen real 4-3-2, opacidad ${Math.round(op * 100)} %`],
            ["Excluido", "Solo nubes y sombras de nube"]],
          fuente: "Sentinel-2 L2A (ESA Copernicus) · INGEMMET" };
      }
      case "topografia":
        return { ...base, titulo: "Mapa topográfico de la cuadrícula", fuente: "Copernicus DEM GLO-30 (ESA) · INGEMMET",
          datos: datosBase.slice(0, 2) };
      case "antecedentes":
        return { ...base };
      case "unidades":
        // análisis bibliográfico de las unidades elegidas para la Prioridad libre (informe.unidades en el servidor)
        return { ...base, escala: res.escala_usada === "100K" ? "1:100 000" : "1:50 000",
          unidades: (unidadesPrio ?? []).map((u) => {
            const zs = res.afloramientos.filter((a) => a.unidad === u.nombre);
            const porTexto = new Map<string, { texto: string; litologia: string; roca: string; ha: number }>();
            for (const a of zs) {
              const k = a.descripcion || a.litologia;
              const x = porTexto.get(k);
              if (x) x.ha += a.area_ha; else porTexto.set(k, { texto: a.descripcion, litologia: a.litologia, roca: a.roca_dominante, ha: a.area_ha });
            }
            return { nombre: u.nombre, clase: zs.reduce((m, a) => (a.clase < m ? a.clase : m), "C"), ha: zs.reduce((s, a) => s + a.area_ha, 0),
              descripciones: [...porTexto.values()], libre: u.libre, negociable: u.negociable, pasa: u.pasa };
          }) };
      case "analisis": {
        const st = new Map((s2?.afloramientos ?? []).map((x) => [x.id, x]));
        const r_ = ruta?.ruta;
        return { ...base,
          zonas_s2: res.afloramientos.filter((a) => st.get(a.id)?.ndvi_pct != null).map((a) => {
            const x = st.get(a.id)!;
            return { unidad: a.unidad, clase: a.clase, ha: a.area_ha, ndvi: x.ndvi_pct, bsi: x.bsi_pct, ferr: x.ferruginosa_pct, arcilla: x.anomalia_arcilla_pct ?? 0 };
          }),
          imagen: { fecha: s2?.imagen?.fecha_peru ?? s2?.periodo ?? "", nubes: s2?.imagen?.nubes_cuadricula ?? null, vegetacion: s2?.imagen?.vegetacion_cuadricula ?? null },
          libres: res.libres ? { n_concesiones: res.libres.n_concesiones, concesiones_pct: res.libres.concesiones_pct, util_pct: res.libres.util_pct,
            libre_pct: res.libres.libre_pct, no_apto: res.libres.no_apto ?? [] } : {},
          restricciones: (res.restricciones ?? []).map((r) => ({ nombre: r.nombre, tipo: r.tipo, nivel: r.nivel, pct: r.pct_cuadricula })),
          prioridad: prioridadLibre ? { libre: prioridadLibre.libre, negociable: prioridadLibre.negociable, mejor: mejorZona ?? null } : {},
          pct_valida: s2?.pct_area_valida ?? 0,
          ha_celda: (celda.norte - celda.sur) * 111.32 * (celda.este - celda.oeste) * 111.32 * Math.cos(((celda.norte + celda.sur) / 2) * Math.PI / 180) * 100,
          ...(r_ ? { ruta_km: r_.km_total, ruta_pista: r_.resumen.pista, ruta_trocha: r_.resumen.trocha } : {}) };
      }
      case "protegidas":
        return { ...base, titulo: "Áreas protegidas y restringidas para concesiones",
          datos: datosBase.slice(0, 2), fuente: "INGEMMET · áreas reservadas (GEOCATMIN) · SERNANP" };
      case "concesiones":
        return { ...base, titulo: "Concesiones mineras (catastro de INGEMMET)",
          datos: datosBase.slice(0, 1), fuente: "INGEMMET · catastro minero (GEOCATMIN)" };
      case "geologia_completa":
        return { ...base, titulo: `Mapa geológico de la cuadrícula (1:${res.escala_usada === "100K" ? "100 000" : "50 000"})`,
          escala: res.escala_usada === "100K" ? "100K" : "50K", fuente: "INGEMMET · geología integrada (GEOCATMIN)" };
      case "geologia_desc":
        return { ...base, escala: res.escala_usada === "100K" ? "100K" : "50K" };
      case "libres":
        // leyenda y datos los arma el servidor (mismas áreas protegidas que su lámina y cada motivo de «no apto»)
        return { ...base, titulo: "Zonas libres para petitorio y aptas para cantera", datos: datosBase.slice(0, 2),
          fuente: "INGEMMET (catastro, áreas reservadas) · SERFOR · cobertura del suelo Sentinel-2" };
      case "geologia_libre": {
        const gl = geologiaLibre!;
        const fha = (x: number) => `${Math.round(x).toLocaleString("es-PE")} ha`;
        return { ...base, titulo: "Geología elegida en zonas libres",
          capas: [{ png: gl.url, crs: "4326", bbox: gl.bbox, opacidad: 0.95 }], zonas: zonasElegidas(0),
          leyenda: [{ color: "#16c55e", texto: "Unidad elegida LIBRE y utilizable" },
            { color: "#2563eb", texto: "En concesión titulada o en trámite (negociable)" },
            { color: "#facc15", texto: "Libre, pero chacra, poblado, vía o río" },
            { color: "#7dd3fc", texto: "Sobre derecho extinguido" }, ...leyendaElegidas],
          datos: [...datosBase.slice(0, 2),
            ["Criterio", "Unidades elegidas ∩ áreas libres − áreas protegidas (sin filtros satelitales)"],
            ...(gl.unidades?.length ? [["Unidades usadas", gl.unidades.map((u) => u.replace(/^Grupo [^-]+ - /, "")).join(", ")] as [string, string]] : []),
            ["Libre (verde)", fha(gl.libre)], ["En concesión (azul)", fha(gl.negociable)],
            ["Chacra, poblado, vía (amarillo)", fha(gl.noApto)], ["Derecho extinguido (celeste)", fha(gl.extinguido)],
            ["Distancia a la fábrica", `≈ ${kmFab} km en línea recta`]],
          fuente: "INGEMMET (geología, catastro, áreas reservadas) · ESA WorldCover" };
      }
      case "prioridad": {
        const pl = prioridadLibre!;
        const fha = (x: number) => `${Math.round(x).toLocaleString("es-PE")} ha`;
        return { ...base, titulo: "Mapa de prioridad libre",
          capas: [{ png: pl.url, crs: "4326", bbox: pl.bbox, opacidad: 0.95 }], zonas: zonasElegidas(0),
          leyenda: [{ color: "#16c55e", texto: pl.sinSatelite ? "Unidad elegida LIBRE" : "Unidad elegida que pasa los 3 filtros y está LIBRE" },
            { color: "#2563eb", texto: "En concesión titulada o en trámite (negociable)" },
            { color: "#facc15", texto: "Libre, pero chacra, poblado, vía o río" },
            { color: "#7dd3fc", texto: "Sobre derecho extinguido" }, ...leyendaElegidas],
          datos: [...datosBase.slice(0, 2),
            ["Criterio", pl.sinSatelite ? "Unidades elegidas − áreas protegidas (sin Sentinel-2: no descuenta hierro ni arcillas)"
              : "Unidades elegidas ∩ NDVI bajo ∩ ferruginosa baja ∩ arcilla baja − áreas protegidas"],
            ...(pl.unidades?.length ? [["Unidades usadas", pl.unidades.map((u) => u.replace(/^Grupo [^-]+ - /, "")).join(", ")] as [string, string]] : []),
            ...(!pl.sinSatelite ? [["Filtros (percentil dentro de cada unidad)", filtros] as [string, string]] : []),
            ["Libre (verde)", fha(pl.libre)], ["En concesión (azul)", fha(pl.negociable)],
            ["Chacra, poblado, vía (amarillo)", fha(pl.noApto)], ["Derecho extinguido (celeste)", fha(pl.extinguido)],
            ...(pl.sinSatelite ? [] : [["Toma Sentinel-2", toma] as [string, string]]),
            ["Distancia a la fábrica", `≈ ${kmFab} km en línea recta`]],
          fuente: pl.sinSatelite ? "INGEMMET (geología, catastro, áreas reservadas) · ESA WorldCover"
            : "INGEMMET · Sentinel-2 L2A (ESA Copernicus) · ESA WorldCover" };
      }
      case "ruta": {
        const r = ruta!;
        return { tipo: "ruta", autor, empresa, proyecto, titulo: "Mapa de ruta y distancias", subtitulo: `Planta KEDA → ${r.destino.nombre}`,
          ruta: { origen: { lat: fabrica[0], lon: fabrica[1], nombre: FABRICA_NOMBRE },
            destino: r.destino, bloques: r.ruta.bloques, km_total: r.ruta.km_total, km_linea_recta: r.ruta.km_linea_recta },
          fuente: `${r.ruta.fuente} · Esri World Imagery` };
      }
    }
  }

  const bajar = (blob: Blob, nombre: string) => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = nombre;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  };
  const aDataUrl = (b: Blob) => new Promise<string>((ok, mal) => {
    const r = new FileReader(); r.onload = () => ok(r.result as string); r.onerror = () => mal(r.error); r.readAsDataURL(b);
  });

  async function generar() {
    try { localStorage.setItem(CLAVE_AUTOR, autor); localStorage.setItem(CLAVE_EMPRESA, empresa); localStorage.setItem(CLAVE_PROYECTO, proyecto); localStorage.setItem("prospector-rmi:formato-lamina", formato); } catch { /* sin almacenamiento */ }
    const paginas: string[] = [];
    const juego = (Object.keys(NOMBRES) as Tipo[]).filter((x) => elegidas.has(x) && !disponible[x]);
    if (informe) {
      // INFORME EN EL SERVIDOR (24/11/2026): se arman las peticiones aquí y el servidor genera todas las páginas en paralelo
      setEstado({ pdf: "generando" });
      setAvance({ hechas: 0, total: juego.length + 1 });
      try {
        const lista: Record<string, unknown>[] = [{ tipo: "portada", autor, empresa, proyecto, materia, hoja100: celda.hoja100,
          celda: { codigo: celda.codigo, sur: celda.sur, oeste: celda.oeste, norte: celda.norte, este: celda.este },
          toma: s2?.imagen?.fecha_peru ? `del ${s2.imagen.fecha_peru} (hora de Perú), ${s2.imagen.nubes_cuadricula ?? "—"} % de nubes` : "—",
          contenido: juego.map((t) => NOMBRES[t]), total: String(juego.length).padStart(2, "0") }];
        for (const [k, t] of juego.entries()) {
          lista.push({ ...(await peticion(t)), lamina: String(k + 1).padStart(2, "0"), total: String(juego.length).padStart(2, "0") });
        }
        const { id } = await api.informeIniciar({ titulo: `Informe de prospección · cuadrícula ${celda.codigo}`, nombre: `Informe_${celda.codigo}.pdf`, paginas: lista });
        for (;;) {
          await new Promise((ok) => setTimeout(ok, 2000));
          const st = await api.informeEstado(id);
          setAvance({ hechas: st.hechas, total: st.total, mb: st.mb, errores: st.errores });
          if (st.estado === "error") throw new Error(st.errores.join(" · ") || "no se pudo armar el informe");
          if (st.estado === "listo") break;
        }
        bajar(await api.informePdf(id), `Informe_${celda.codigo}.pdf`);
        setEstado({ pdf: "listo" });
      } catch (err) {
        setEstado({ pdf: (err as Error).message });
      }
      return;
    }
    if (informe) {   // PORTADA con el índice (sin número)
      setEstado((e) => ({ ...e, portada: "generando" }));
      try {
        const blob = await api.lamina({ tipo: "portada", autor, empresa, proyecto, materia, hoja100: celda.hoja100,
          celda: { codigo: celda.codigo, sur: celda.sur, oeste: celda.oeste, norte: celda.norte, este: celda.este },
          toma: s2?.imagen?.fecha_peru ? `del ${s2.imagen.fecha_peru} (hora de Perú), ${s2.imagen.nubes_cuadricula ?? "—"} % de nubes` : "—",
          contenido: juego.map((t) => NOMBRES[t]), total: String(juego.length).padStart(2, "0") });
        paginas.push(await aDataUrl(blob));
        setEstado((e) => ({ ...e, portada: "listo" }));
      } catch (err) {
        setEstado((e) => ({ ...e, portada: (err as Error).message }));
      }
    }
    for (const [k, t] of juego.entries()) {
      setEstado((e) => ({ ...e, [t]: "generando" }));
      try {
        const blob = await api.lamina({ ...(await peticion(t)), lamina: String(k + 1).padStart(2, "0"), total: String(juego.length).padStart(2, "0") });
        if (formato === "png" && !informe) bajar(blob, `${celda.codigo}_${t}.png`);
        else paginas.push(await aDataUrl(blob));
        setEstado((e) => ({ ...e, [t]: "listo" }));
      } catch (err) {
        setEstado((e) => ({ ...e, [t]: (err as Error).message }));
      }
    }
    if ((formato === "pdf" || informe) && paginas.length) {
      setEstado((e) => ({ ...e, pdf: "generando" }));
      try {
        bajar(await api.pdf(paginas, informe ? `Informe de prospección · cuadrícula ${celda.codigo}` : `Láminas · cuadrícula ${celda.codigo}`),
          informe ? `Informe_${celda.codigo}.pdf` : `${celda.codigo}_laminas.pdf`);
        setEstado((e) => ({ ...e, pdf: "listo" }));
      } catch (err) {
        setEstado((e) => ({ ...e, pdf: (err as Error).message }));
      }
    }
  }

  const ocupado = Object.values(estado).includes("generando");
  return (
    <div className="fondo-modal" onClick={() => !ocupado && onCerrar()}>
      <div className="modal laminas" onClick={(e) => e.stopPropagation()}>
        <div className="titulo-mp"><b><FileImage size={18} /> {informe ? "Informe PDF" : "Láminas"} · {celda.codigo}</b><button onClick={onCerrar} disabled={ocupado}>×</button></div>
        <small className="explica">{informe
          ? "Un solo PDF A3: portada con índice, todas las láminas en orden y numeradas, antecedentes de los boletines y análisis de las capas con las cifras de esta cuadrícula. El servidor genera las páginas en paralelo: ≈ 2–3 min."
          : "Láminas A3 listas para informe: cuadrícula UTM, norte, escalas, ubicación por departamento, leyenda, datos y membrete."}</small>
        <label className="campo-mp">
          <span><b>Proyecto</b><small>aparece en el cajetín</small></span>
          <input value={proyecto} onChange={(e) => setProyecto(e.target.value)} />
        </label>
        <label className="campo-mp">
          <span><b>Empresa</b><small>aparece en el cajetín</small></span>
          <input value={empresa} onChange={(e) => setEmpresa(e.target.value)} />
        </label>
        <label className="campo-mp">
          <span><b>Elaborado por</b><small>aparece en el membrete</small></span>
          <input value={autor} placeholder="Nombre del profesional o empresa" onChange={(e) => setAutor(e.target.value)} />
        </label>
        <ul className="lista-laminas">
          {(Object.keys(NOMBRES) as Tipo[]).filter((t) => !(informe && t === "geologia")).map((t) => {
            const no = disponible[t];
            const st = estado[t];
            return (
              <li key={t} className={no ? "no" : ""}>
                <label>
                  <input type="checkbox" disabled={!!no || ocupado} checked={!no && elegidas.has(t)}
                    onChange={() => setElegidas((s) => { const n = new Set(s); if (n.has(t)) n.delete(t); else n.add(t); return n; })} />
                  <span><b>{NOMBRES[t]}</b>{no && <small>{no}</small>}</span>
                </label>
                <span className="estado-lam">
                  {st === "generando" ? <Loader2 size={16} className="gira" /> : st === "listo" ? "✓ descargada" : st ? <small className="error-mp">{st}</small> : null}
                </span>
              </li>
            );
          })}
        </ul>
        {!informe && <div className="formato-lam" role="radiogroup" aria-label="Formato">
          <span>Formato:</span>
          <label><input type="radio" checked={formato === "pdf"} disabled={ocupado} onChange={() => setFormato("pdf")} /> PDF <small>(un archivo, una lámina por página)</small></label>
          <label><input type="radio" checked={formato === "png"} disabled={ocupado} onChange={() => setFormato("png")} /> PNG <small>(una imagen por lámina)</small></label>
        </div>}
        {estado.pdf && estado.pdf !== "generando" && estado.pdf !== "listo" && <p className="error-mp">PDF: {estado.pdf}</p>}
        {informe && avance && estado.pdf === "generando" && (
          <div className="avance-informe">
            <div className="barra"><i style={{ width: `${(100 * avance.hechas) / Math.max(avance.total, 1)}%` }} /></div>
            <small>{avance.hechas} de {avance.total} páginas · el servidor las genera de a 4 a la vez</small>
          </div>
        )}
        {informe && !!avance?.errores?.length && <small className="error-mp">Páginas con problema: {avance.errores.join(" · ")}</small>}
        {estado.pdf === "listo" && <small className="ok-pet">✓ PDF descargado: {informe ? `Informe_${celda.codigo}.pdf` : `${celda.codigo}_laminas.pdf`}
          {informe && avance?.mb ? ` · ${String(avance.mb).replace(".", ",")} MB` : ""}</small>}
        <button className="primario" disabled={ocupado || ![...elegidas].some((t) => !disponible[t])} onClick={generar}>
          <Download size={16} /> {ocupado ? (estado.pdf === "generando" ? "Armando el PDF…" : "Generando… (≈ 15–25 s cada una)")
            : informe ? "Generar y descargar el informe PDF" : `Generar y descargar ${formato.toUpperCase()}`}
        </button>
      </div>
    </div>
  );
}
