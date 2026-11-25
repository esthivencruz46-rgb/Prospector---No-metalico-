import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import Mapa, {
  CAPAS, CAPAS_SATELITE, COLOR_CLASE, GEO_OPACIDAD, urlSatelite, type IdCapa, type MapaHandle, type MarcaCelda,
} from "./Mapa";
import {
  api, MATERIALES_RESPALDO,
  type Afloramiento, type Bibliografia, type Concesion, type Curvas, type FilaBarrido, type Formacion, type Ruta, type TipoTramo, type Tonelaje, type HojaFormacion, type Material,
  type ResultadoBusqueda, type ResultadoSentinel, type StatSentinel, API_URL, cambiarServidor } from "./api";
import { AYUDA_CAPAS, GUIA_PASOS } from "./ayudaCapas";
import EditorMaterias from "./EditorMaterias";
import Laminas from "./Laminas";
import { aptitudVidrio, NIVEL_TEXTO, type AptitudVidrio } from "./vidrio";
import ExportarSIG from "./ExportarSIG";
import CortesS2, { type CapaCorte, type FocoCorte } from "./CortesS2";
import { aplicarCortes, conNdviBsi, siliceLimpiaPorUnidad, type ResultadoUnidad, cortesDe, cortesGuardados, guardarCortes, mismosCortes, recalculable, sinCapasViejas } from "./cortes";
import PanelPetitorio, { usePetitorio } from "./Petitorio";
import Ranking, { type CeldaCalor } from "./Ranking";
import Supermaduras, { SupermadurasCelda } from "./Supermaduras";
import PanelVigilancia, { useVigilancia } from "./Vigilancia";
import {
  Bell, BookOpen, ClipboardCheck, Eye, Factory, Gem, SlidersHorizontal, Trophy, FileImage, FlaskConical, Layers, Library, LocateFixed, Map as IconoMapa, Mountain, Radar, Route, Satellite,
  CalendarDays, Check, Cloud, FileText, Globe2, Leaf, MapPin, PanelLeftOpen, Pickaxe, RefreshCw, Save, Scan, Search, ShieldAlert, ShieldX, Star, Trash2, Truck, X, ChevronLeft, ChevronRight, MoreHorizontal } from "lucide-react";
import { componerPrioridadSilice, mascaraZonas, type PrioridadLibre } from "./prioridadLibre";
import {
  borrarAdjunto, borrarAnalisis, borrarTodosLosAnalisis, codigosConAnalisis, elegirRaiz, escritorApp, escritorLaptop,
  espacioUsadoMB, guardarAdjunto, guardarAnalisis, leerAdjunto, leerAnalisis, miniatura, nombreSeguro,
  olvidarRaiz, permiso, plataforma, raizGuardada, usarMateria, type Escritor,
} from "./almacen";

/** Clases nuevas (21/11/2026: A = depósitos de arena · B = rocas): los análisis guardados con la
 *  división anterior ya no sirven. Se borran UNA vez por dispositivo, antes de que la app lea nada:
 *  análisis guardados (IndexedDB), lista de cuadrículas analizadas y resultados del barrido.
 *  Las carpetas ★ (notas, fotos, adjuntos) NO se tocan. */
const VERSION_CLASES = "2026-11-23";   // 23/11: clasificación por descripción completa + solo 50K donde hay hoja
const migracionClases: Promise<void> = (() => {
  try {
    if (localStorage.getItem("prospector-rmi:version-clases") === VERSION_CLASES) return Promise.resolve();
    localStorage.removeItem("prospector-rmi:cuadriculas");
    localStorage.removeItem("prospector-rmi:barrido");
  } catch {
    return Promise.resolve();
  }
  return borrarTodosLosAnalisis().then(() => {
    try { localStorage.setItem("prospector-rmi:version-clases", VERSION_CLASES); } catch { /* sin almacenamiento */ }
  });
})();
import {
  FABRICA_INICIAL, celda25, celdaComoPoligono, celdaEn, celdasEnVista, distanciaKm, formatoKm, gms, hoja50, parsearUbicacion, utm, cuadricula100En,
  tieneTierra, vecina, type Celda, type Rumbo, type Ubicacion,
} from "./geo";
import { guardarArchivo } from "./guardar";

type Fase = "inicio" | "area" | "buscando" | "resultado";
type Pestana = "afloramientos" | "sentinel" | "biblio";
type PestanaCatalogo = "carpetas" | "formaciones" | "mias";

/** Días tras los cuales un análisis guardado vuelve a consultar concesiones y áreas protegidas. */
const DIAS_LIBRES = 7;

/** Máximo de cuadrículas por barrido (= backend/barrido.MAX_CELDAS). */
const MAX_BARRIDO = 64;

/** Toneladas legibles: «725 Mt», «38 kt», «900 t». */
const fmtT = (t: number) => (t >= 1e9 ? `${(t / 1e9).toLocaleString("es-PE", { maximumFractionDigits: 1 })} Gt`
  : t >= 1e6 ? `${(t / 1e6).toLocaleString("es-PE", { maximumFractionDigits: 1 })} Mt`
    : t >= 1e3 ? `${Math.round(t / 1e3).toLocaleString("es-PE")} kt` : `${Math.round(t)} t`);
const fmtM3 = (v: number) => (v >= 1e6 ? `${(v / 1e6).toLocaleString("es-PE", { maximumFractionDigits: 1 })} Mm³`
  : `${Math.round(v).toLocaleString("es-PE")} m³`);

/** Colores de los tramos de una ruta (los mismos en el mapa, Mapa.tsx COLOR_TRAMO_MAPA). */
const COLOR_TRAMO: Record<TipoTramo, string> = { pista: "#3b82f6", trocha: "#b45309", a_pie: "#ec4899" };
const CORTO_TRAMO: Record<TipoTramo, string> = { pista: "pista", trocha: "trocha", a_pie: "a pie" };

const CAPAS_INICIALES: Record<IdCapa, boolean> = {
  resultados: true, geo50: false, geo100: false, geo50_si: true, geo100_si: false, catastro: false,
  areas_libres: false, catastro_nm: false, restringidas: true, s2_arcillas: false,
  s2_prioridad_libre: true, s2_natural: false, s2_swir: false, s2_ndvi: false, s2_bsi: false, s2_ferruginosas: false,
  fabrica: true, cuadricula: true,
};

const TIPOS_FORMACION: { tipo: Formacion["tipo"][]; titulo: string }[] = [
  { tipo: ["Formación", "Grupo"], titulo: "Formaciones geológicas silíceas" },
  { tipo: ["Roca"], titulo: "Tipos de roca (en cualquier formación)" },
  { tipo: ["Depósito"], titulo: "Depósitos de arena" },
];

const CLAVE_HISTORIAL = "prospector-rmi:cuadriculas";

/** Materia prima elegida (se recuerda en el dispositivo). Cada una tiene sus propios análisis
 *  guardados, lista de analizadas y barrido: la arena silícea con las claves de siempre, las demás
 *  con «:<id>» (localStorage) o «<id>|» (IndexedDB, almacen.ts). */
const CLAVE_MATERIA = "prospector-rmi:materia";
const SILICE = "arena_silicea";
function materiaGuardada(): string {
  try { return localStorage.getItem(CLAVE_MATERIA) || SILICE; } catch { return SILICE; }
}
const sufijoMateria = (id: string) => (id === SILICE ? "" : `:${id}`);
const claveHistorial = (id: string) => CLAVE_HISTORIAL + sufijoMateria(id);
const claveBarrido = (id: string) => "prospector-rmi:barrido" + sufijoMateria(id);
function leerBarrido(id: string): { celdas: Celda[]; res: Record<string, FilaBarrido> } {
  try {
    const v = JSON.parse(localStorage.getItem(claveBarrido(id)) || "{}");
    return { celdas: v.celdas ?? [], res: v.res ?? {} };
  } catch { return { celdas: [], res: {} }; }
}
usarMateria(materiaGuardada());

/** Resumen de una cuadrícula ya analizada (se guarda en el navegador). */
interface ResumenCelda {
  codigo: string;
  fecha: string; // ISO
  A: number; B: number; C: number;
  muestras?: number;          // (antiguos)
  mejorSiO2?: number | null;  // (antiguos)
  mejorPureza?: number | null; // (antiguos: índice combinado, ya no se usa)
  haAB?: number;              // ha de zonas A + B
  haLibre?: number | null;    // Prioridad libre: ha verdes (libres)
  haNeg?: number | null;      // Prioridad libre: ha azules (concesión titulada / en trámite)
  sentinel: boolean;
  formaciones: string[];
}

function leerHistorial(id: string = materiaGuardada()): ResumenCelda[] {
  try {
    const v = JSON.parse(localStorage.getItem(claveHistorial(id)) || "[]");
    return Array.isArray(v) ? v.filter((x) => x && typeof x.codigo === "string") : [];
  } catch {
    return [];
  }
}

/** Vistas satelitales de la cuadrícula analizada. Colores = backend/sentinel_silice.py (`calcular`). */
// (24/11/2026, pedido del usuario) fuera: cuarzo ASTER, cocientes, hierro final, férrico y ferroso
type IdVista = "s2_prioridad_libre" | "s2_arcillas" | "s2_natural" | "s2_swir" | "s2_ndvi" | "s2_bsi" | "s2_ferruginosas";
const VISTAS_S2: { id: IdVista; grupo: "resultado" | "continua" | "indice" | "bandas"; nombre: string; muestra: string; explica: string }[] = [
  { id: "s2_prioridad_libre", grupo: "resultado", nombre: "Prioridad libre", muestra: "linear-gradient(90deg, #16c55e 0 40%, #2563eb 40% 70%, #facc15 70%)",
    explica: "Zonas A y B que pasan los TRES filtros a la vez (NDVI bajo · anomalía ferruginosa baja · arcilla baja; cortes por percentil en el histograma) − áreas protegidas. Verde = libre · azul = concesión titulada o en trámite · amarillo = chacra, poblado, vía o río · celeste = derecho extinguido." },
  { id: "s2_ndvi", grupo: "continua", nombre: "NDVI (vegetación)", muestra: "linear-gradient(90deg, #784824, #d6c7a1, #86be5a, #14532d)",
    explica: "NDVI = (B8 − B4)/(B8 + B4), escala continua con el 100 % de los datos: pardo = sin vegetación (roca o suelo) → verde oscuro = vegetación densa." },
  { id: "s2_bsi", grupo: "continua", nombre: "BSI (suelo y roca desnuda)", muestra: "linear-gradient(90deg, #0f3c46, #96967d, #e2d6b4, #fffcf0)",
    explica: "BSI = ((B11 + B4) − (B8 + B2)) / ((B11 + B4) + (B8 + B2)), escala continua con el 100 % de los datos: azul petróleo = cubierto o húmedo → blanco = suelo o roca desnuda (afloramiento)." },
  { id: "s2_ferruginosas", grupo: "continua", nombre: "Anomalías ferruginosas (férrico + ferroso)", muestra: "linear-gradient(90deg, #3b2a98 0% 10%, #3f6fe0 10% 20%, #22a7f0 20% 30%, #14d0c4 30% 40%, #3ae57f 40% 50%, #a3f03a 50% 60%, #f2d93a 60% 70%, #fb9a2a 70% 80%, #e8461b 80% 90%, #8f0d0d 90% 100%)",
    explica: "Férrico (B4/B2 + B4/B3) + ferroso (B11/B8A) en 10 CLASES fijas de igual número de píxeles (deciles P0–P100), cada una de un color: índigo = lo menos ferruginoso → granate = lo más. A la Prioridad libre pasan las clases bajo tu corte (P30 = índigo, azul, celeste)." },
  { id: "s2_arcillas", grupo: "indice", nombre: "Arcillas", muestra: "linear-gradient(90deg, #3b2a98 0% 10%, #3f6fe0 10% 20%, #22a7f0 20% 30%, #14d0c4 30% 40%, #3ae57f 40% 50%, #a3f03a 50% 60%, #f2d93a 60% 70%, #fb9a2a 70% 80%, #e8461b 80% 90%, #8f0d0d 90% 100%)",
    explica: "B11/B12 (arcillas, micas, sulfatos) en 10 CLASES fijas de igual número de píxeles (deciles P0–P100): índigo = lo menos arcilloso → granate = lo más. A la Prioridad libre pasan las clases bajo tu corte (P30 = índigo, azul, celeste)." },
  { id: "s2_natural", grupo: "bandas", nombre: "Foto real (4-3-2)", muestra: "linear-gradient(90deg, #a8a29e, #78716c, #57534e)",
    explica: "Color natural: la toma más despejada de los últimos 18 meses." },
  { id: "s2_swir", grupo: "bandas", nombre: "Foto geológica (12-11-2)", muestra: "linear-gradient(90deg, #f9a8d4, #fde68a, #93c5fd)",
    explica: "SWIR: cada roca toma un tono distinto; areniscas y cuarcitas claras brillan." },
];

// ---------------------------------------------------------------- carpetas
const CLAVE_CARPETAS = "prospector-rmi:carpetas";

/** Lo que se recopila de una cuadrícula al guardarla (sin geometrías, para que pese poco). */
interface DatosCelda {
  fecha: string;
  escala: string | null;
  zonas: { clase: string; unidad: string; litologia: string; roca_dominante: string; area_ha: number;
           lat: number; lon: number; oxidos: number | null; arcillas: number | null;
           limpia?: number | null; cuarzo_aster?: number | null /* (antiguos) */ }[];
  muestras?: unknown[];   // (ya no se usa: análisis antiguos)
  sentinel: { periodo: string; pct_area_valida: number } | null;
  restricciones?: { nivel: "prohibido" | "restringido"; tipo: string; nombre: string; categoria: string; pct: number }[];
  libres?: { pct: number; ha: number; concesiones_pct: number; protegido_pct: number; consultado: string;
             util_pct?: number | null; util_ha?: number | null; no_apto?: { texto: string; ha: number }[];
             concesiones: { codigo: string; nombre: string; titular: string; estado: string; sustancia: string; ha: number }[] };
}

/** Foto, PDF u otro archivo adjunto. El archivo va en IndexedDB (clave `id`) y,
 *  si hay carpeta en el dispositivo, también como archivo real en …/adjuntos/. */
interface Adjunto {
  id: string;
  nombre: string;   // nombre del archivo en el dispositivo (único dentro de su carpeta)
  tipo: string;     // MIME
  tamano: number;   // bytes
  fecha: string;    // ISO
  miniatura?: string; // data URL JPEG pequeña (solo imágenes)
  copiadoEn?: string; // «donde» del Escritor al que ya se copió
}

interface CeldaGuardada {
  codigo: string;
  agregada: string; // ISO
  nota: string;
  datos: DatosCelda | null; // null = aún sin analizar
  adjuntos?: Adjunto[];
  biblio?: Bibliografia; // boletines y memorias de la zona (se recopila al guardar)
}

interface Carpeta {
  id: string;
  nombre: string;
  creada: string;
  celdas: CeldaGuardada[];
  adjuntos?: Adjunto[]; // documentos generales de la carpeta
}

const MAX_ADJUNTO = 30 * 1024 * 1024; // 30 MB

/** Nº de tomas candidatas (Copernicus da un número; el respaldo AWS, la lista). */
const nCandidatas = (c: unknown) => (Array.isArray(c) ? c.length : c ?? "—");

/** Superficie de una cuadrícula en hectáreas (rectángulo en grados). */
function haCelda(c: Celda): number {
  const lat = ((c.norte + c.sur) / 2) * Math.PI / 180;
  return (c.norte - c.sur) * 111.32 * (c.este - c.oeste) * 111.32 * Math.cos(lat) * 100;
}

function pesoLegible(b: number): string {
  return b < 1024 * 1024 ? `${Math.max(1, Math.round(b / 1024))} KB` : `${(b / 1024 / 1024).toFixed(1)} MB`;
}

/** Ruta del adjunto dentro de «Prospector RMI»: <carpeta>/<cuadrícula>/adjuntos o <carpeta>/adjuntos. */
const rutaAdjuntos = (k: Carpeta, codigo: string | null) => (codigo ? [k.nombre, codigo, "adjuntos"] : [k.nombre, "adjuntos"]);

function leerCarpetas(): Carpeta[] {
  try {
    const v = JSON.parse(localStorage.getItem(CLAVE_CARPETAS) || "[]");
    return Array.isArray(v) ? v.filter((x) => x && typeof x.id === "string" && Array.isArray(x.celdas)) : [];
  } catch {
    return [];
  }
}

function datosDeAnalisis(r: ResultadoBusqueda, s: ResultadoSentinel | null): DatosCelda {
  const st = new Map((s?.afloramientos ?? []).map((x) => [x.id, x]));
  return {
    fecha: new Date().toISOString(),
    escala: r.escala_usada,
    zonas: r.afloramientos.map((a) => ({
      clase: a.clase, unidad: a.unidad, litologia: a.litologia || a.descripcion,
      roca_dominante: a.roca_dominante ?? "", area_ha: a.area_ha, lon: a.centro[0], lat: a.centro[1],
      // «oxidos» guarda el HIERRO total (férrico + ferroso); en análisis antiguos, solo el férrico
      oxidos: st.get(a.id)?.hierro_pct ?? st.get(a.id)?.oxidos_hierro_pct ?? null,
      arcillas: st.get(a.id)?.arcillas_pct ?? null,
      limpia: st.get(a.id)?.limpia_pct ?? null,
    })),
    sentinel: s?.disponible ? { periodo: s.periodo ?? "", pct_area_valida: s.pct_area_valida ?? 0 } : null,
    restricciones: (r.restricciones ?? []).map((x) => ({
      nivel: x.nivel, tipo: x.tipo, nombre: x.nombre, categoria: x.categoria, pct: x.pct_cuadricula,
    })),
    libres: r.libres ? {
      pct: r.libres.libre_pct, ha: r.libres.libre_ha, concesiones_pct: r.libres.concesiones_pct,
      protegido_pct: r.libres.protegido_pct, consultado: r.libres.consultado,
      util_pct: r.libres.util_pct ?? null, util_ha: r.libres.util_ha ?? null, no_apto: r.libres.no_apto ?? [],
      concesiones: r.libres.concesiones.map((k) => ({ codigo: k.codigo, nombre: k.nombre, titular: k.titular,
        estado: k.estado, sustancia: k.sustancia, ha: k.ha_en_cuadricula })),
    } : undefined,
  };
}

/** CSV (Excel en español: separador «;») con todo lo recopilado en una carpeta. */
function csvCarpeta(c: Carpeta, fabrica: [number, number]): string {
  const q = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const n = (v: number | null | undefined) => (v == null ? "" : String(v).replace(".", ","));
  const filas = [["cuadricula", "nota", "tipo", "clase", "nombre_o_unidad", "litologia", "roca_dominante",
    "area_ha", "limpia_S2_pct", "hierro_S2", "arcillas_S2",
    "lat", "lon", "km_fabrica"].join(";")];
  for (const g of c.celdas) {
    const d = g.datos;
    if (!d || !d.zonas.length) {
      filas.push([q(g.codigo), q(g.nota), q(d ? "sin hallazgos" : "sin analizar"), ...Array(11).fill("")].join(";"));
      continue;
    }
    for (const z of d.zonas) {
      filas.push([q(g.codigo), q(g.nota), q("zona favorable"), q(z.clase), q(z.unidad), q(z.litologia), q(z.roca_dominante),
        n(z.area_ha), n(z.limpia), n(z.oxidos), n(z.arcillas),
        n(+z.lat.toFixed(6)), n(+z.lon.toFixed(6)),
        n(+distanciaKm(fabrica[0], fabrica[1], z.lat, z.lon).toFixed(1))].join(";"));
    }
  }
  return "﻿" + filas.join("\r\n"); // BOM: Excel abre las tildes bien
}

/** «ficha.txt» de una cuadrícula guardada: todo lo recopilado, legible sin la app. */
function fichaCelda(k: Carpeta, g: CeldaGuardada, fabrica: [number, number]): string {
  const c = celda25(g.codigo);
  const L: string[] = [`PROSPECTOR RMI · ${g.codigo}`, `Carpeta: ${k.nombre}`, ""];
  if (c) {
    L.push(`Cuadrícula 1:25 000 ${c.codigo} · hoja 1:50 000 ${c.codigo.split("-")[0]} · hoja 1:100 000 ${c.hoja100}`);
    L.push(`Límites: ${gms(c.norte, true)} a ${gms(c.sur, true)} · ${gms(c.oeste, false)} a ${gms(c.este, false)}`);
    L.push(`Centro a ${formatoKm(distanciaKm(fabrica[0], fabrica[1], (c.norte + c.sur) / 2, (c.oeste + c.este) / 2))} de la fábrica (línea recta)`);
  }
  L.push(`Guardada: ${new Date(g.agregada).toLocaleString("es-PE")}`, "", "NOTAS", g.nota || "(sin notas)", "");
  const d = g.datos;
  if (!d) {
    L.push("Aún sin analizar.");
    return L.join("\r\n");
  }
  L.push(`ANÁLISIS ${new Date(d.fecha).toLocaleString("es-PE")} · geología ${d.escala ?? "—"}`
    + (d.sentinel ? ` · Sentinel-2 ${d.sentinel.periodo} (${d.sentinel.pct_area_valida}% útil)` : " · sin Sentinel-2"), "");
  L.push(`ZONAS FAVORABLES (${d.zonas.length})`);
  for (const z of [...d.zonas].sort((a, b) => a.clase.localeCompare(b.clase) || b.area_ha - a.area_ha)) {
    L.push(`- [${z.clase}] ${z.unidad} · ${z.area_ha} ha · ${z.litologia}`
      + (z.roca_dominante ? ` · dominante: ${z.roca_dominante}` : ""));
    const m = [z.limpia != null && `${z.limpia} % limpia (S2)`, z.oxidos != null && `hierro ${z.oxidos}`,
      z.arcillas != null && `arcillas ${z.arcillas}`].filter(Boolean).join(" · ");
    L.push(`    ${m ? `${m} · ` : ""}${z.lat.toFixed(5)}, ${z.lon.toFixed(5)} · ${formatoKm(distanciaKm(fabrica[0], fabrica[1], z.lat, z.lon))} de la fábrica`);
  }
  L.push("", "ÁREAS PROTEGIDAS / RESTRINGIDAS PARA CONCESIONES (GEOCATMIN · referencial)");
  if (!d.restricciones?.length) L.push("Ninguna registrada dentro de la cuadrícula.");
  for (const r of d.restricciones ?? []) {
    L.push(`- [${r.nivel === "prohibido" ? "NO CONCESIONABLE" : "RESTRINGIDO"}] ${r.tipo}: ${r.nombre}`
      + `${r.categoria ? ` (${r.categoria.toLowerCase()})` : ""} · ${r.pct} % de la cuadrícula`);
  }
  if (d.libres) {
    L.push("", `ÁREAS LIBRES PARA CONCESIÓN (consultado el ${new Date(d.libres.consultado).toLocaleDateString("es-PE")} · referencial)`);
    L.push(`Libre: ${d.libres.pct} % (${d.libres.ha} ha) · con derecho minero: ${d.libres.concesiones_pct} % · protegida/restringida: ${d.libres.protegido_pct} %`);
    if (d.libres.util_pct != null) {
      L.push(`Libre y utilizable para cantera: ${d.libres.util_pct} % (${d.libres.util_ha} ha)`
        + (d.libres.no_apto?.length ? ` · no apto aunque libre: ${d.libres.no_apto.map((x) => `${x.texto} ${x.ha} ha`).join(", ")}` : ""));
    }
    for (const k of d.libres.concesiones) {
      L.push(`- ${k.nombre} (${k.codigo}) · ${k.titular || "—"} · ${k.estado} · ${k.sustancia || "—"} · ${k.ha} ha en la cuadrícula`);
    }
  }
  if (g.biblio) {
    L.push("", "BIBLIOGRAFÍA DE LA ZONA (INGEMMET)");
    for (const b of g.biblio.boletines) L.push(`- ${b.cita}: ${b.titulo}`, `    ${b.url}`);
    if (g.biblio.hoja100k) {
      L.push(`- Mapa geológico integrado de la hoja ${g.biblio.hoja100k.codigo} ${g.biblio.hoja100k.nombre}: ${g.biblio.hoja100k.png}`,
        `    paquete completo (ZIP): ${g.biblio.hoja100k.zip}`);
    }
    for (const m of g.biblio.memorias) L.push(`- ${m.cita}`);
  }
  if (g.adjuntos?.length) {
    L.push("", `ADJUNTOS (${g.adjuntos.length}) · en la subcarpeta «adjuntos»`);
    for (const a of g.adjuntos) L.push(`- ${a.nombre} · ${pesoLegible(a.tamano)} · ${new Date(a.fecha).toLocaleString("es-PE")}`);
  }
  L.push("", "Imágenes satelitales en esta carpeta: satelite_*.png / .jpg (si se analizó con Sentinel-2 en esta sesión).",
    "Fuente: GEOCATMIN · INGEMMET (referencial) · Copernicus Sentinel-2.");
  return L.join("\r\n");
}

function descargar(nombre: string, contenido: string, tipo = "text/csv;charset=utf-8") {
  void guardarArchivo(new Blob([contenido], { type: tipo }), nombre);   // en el celular: Documentos/Prospector RMI
}

function etiquetaResumen(h: ResumenCelda): string {
  const p = [h.A && `A${h.A}`, h.B && `B${h.B}`, h.C && `C${h.C}`].filter(Boolean).join(" ");
  return p || "sin zonas";
}

function sinTildes(s: string) {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

export default function App() {
  const mapaRef = useRef<MapaHandle>(null);
  const [materiales, setMateriales] = useState<Material[]>(MATERIALES_RESPALDO);
  const [texto, setTexto] = useState("");
  const [sugerir, setSugerir] = useState(false);
  const [hojas100, setHojas100] = useState<{ codigo: string; nombre: string }[]>([]);
  const [resaltado, setResaltado] = useState<Ubicacion | null>(null); // hoja 50K/100K buscada
  const [materiaId, setMateriaId] = useState<string>(materiaGuardada);
  const materiaSel: Material = materiales.find((x) => x.id === materiaId) ?? materiales.find((x) => x.id === SILICE) ?? materiales[0];
  const esSilice = materiaSel.id === SILICE;
  const [verMaterias, setVerMaterias] = useState(false);
  const [verLaminas, setVerLaminas] = useState<false | "laminas" | "informe">(false);
  const [verSIG, setVerSIG] = useState(false);
  // expediente de petitorio minero (pasos con check + cuadrículas de 100 ha)
  const pet = usePetitorio();
  const [verPetitorio, setVerPetitorio] = useState(false);
  // ranking nacional (censos guardados): mapa de calor reutiliza la capa del barrido
  const [verRanking, setVerRanking] = useState(false);
  // vigilancia del catastro de INGEMMET (cuadrículas y petitorios propios)
  const vig = useVigilancia();
  const [verVig, setVerVig] = useState(false);
  const [rankingMapa, setRankingMapa] = useState<CeldaCalor[]>([]);
  // unidades supermaduras (informe de boletines): mismo mecanismo que el ranking (mapa de calor = capa del barrido)
  const [verSuper, setVerSuper] = useState(false);
  const [superMapa, setSuperMapa] = useState<CeldaCalor[]>([]);
  const [superUnidad, setSuperUnidad] = useState<string | null>(null);
  const petitorioMapa = useMemo(() => (verPetitorio && pet.activo ? { activo: pet.eligiendo, celdas: pet.activo.cuadriculas } : undefined),
    [verPetitorio, pet.activo, pet.eligiendo]);
  const [fase, setFase] = useState<Fase>("inicio");
  const [area, setArea] = useState<number[][] | null>(null);
  const [res, setRes] = useState<ResultadoBusqueda | null>(null);
  const [s2, setS2] = useState<ResultadoSentinel | null>(null);
  const [cargandoS2, setCargandoS2] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [capas, setCapas] = useState(CAPAS_INICIALES);
  const [verCapas, setVerCapas] = useState(false);
  const [base, setBase] = useState<"satelite" | "mapa" | "relieve">("satelite");
  // barra inferior: coordenadas del cursor (laptop) o del centro del mapa (celular)
  const [cursor, setCursor] = useState<[number, number] | null>(null);
  // indicadores de servicios (INGEMMET / Sentinel-2), revisados cada minuto
  const [servicios, setServicios] = useState<{ geocatmin: boolean | null; sentinel: boolean | null }>({ geocatmin: null, sentinel: null });
  // vigilancia: revisión automática (una vez al día por área) cuando INGEMMET responde
  useEffect(() => { if (servicios.geocatmin) vig.revisar(true).catch(() => { /* se reintenta otro día */ }); }, [servicios.geocatmin]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    let vivo = true;
    const revisar = () => api.estado().then((e) => { if (vivo) setServicios({ geocatmin: e.geocatmin, sentinel: e.sentinel }); })
      .catch(() => { if (vivo) setServicios({ geocatmin: null, sentinel: null }); });
    revisar();
    const t = window.setInterval(revisar, 60000);
    return () => { vivo = false; window.clearInterval(t); };
  }, []);
  const [hoja, setHoja] = useState<"cerrada" | "media" | "abierta">("cerrada");
  // Cuadro de resultados: se puede cerrar (✕) y arrastrar por el tirador
  const [hojaOculta, setHojaOculta] = useState(false);
  const [actualizandoLibres, setActualizandoLibres] = useState<string | null>(null);
  // Cuadrícula enfocada: todo lo de afuera se oscurece (áreas protegidas, libres, geología…).
  // Laptop: clic derecho = enfocar, clic izquierdo = ver todo. Celular: 1 toque / 2 toques.
  const [focoCelda, setFocoCelda] = useState<Celda | null>(null);
  const tactil = useMemo(() => window.matchMedia?.("(pointer: coarse)").matches ?? false, []);
  const [verConcesiones, setVerConcesiones] = useState(false);
  const [verCatastro, setVerCatastro] = useState(false);      // bloque «Catastro y áreas libres» (plegado)
  const [concesionAbierta, setConcesionAbierta] = useState<string | null>(null);
  /** Desde una zona A/B/C: abre la ficha del derecho minero en la lista de la cuadrícula. */
  function abrirConcesion(codigo: string) {
    setPestana("afloramientos");
    setVerCatastro(true);
    setVerConcesiones(true);
    setConcesionAbierta(codigo);
    setHoja((h) => (h === "cerrada" ? "media" : h));
    setTimeout(() => document.getElementById(`con-${codigo}`)?.scrollIntoView({ behavior: "smooth", block: "start" }), 80);
  }

  /** Ficha completa de un derecho minero (lo que publica INGEMMET + cruces). */
  const fichaConcesion = (k: Concesion) => (
    <div className="ficha-con" onClick={(e) => e.stopPropagation()}>
      {k.estado_detalle == null ? (
        <p className="nota">Análisis guardado antes de las fichas: toca «↻ Actualizar» para traer el detalle.</p>
      ) : (
        <>
          <table>
            <tbody>
              <tr><td>Estado</td><td><b>{k.estado}</b>{k.estado_detalle ? <small> · {k.estado_detalle}</small> : null}</td></tr>
              <tr><td>Titular</td><td>{k.titular || "—"}</td></tr>
              <tr><td>Hectáreas</td><td>{k.ha_total?.toLocaleString("es-PE") ?? "—"} ha en total · {k.ha_en_cuadricula.toLocaleString("es-PE")} ha en esta cuadrícula</td></tr>
              <tr><td>Uso / sustancia</td><td>{k.sustancia || "—"}</td></tr>
              <tr><td>Calificación</td><td>{k.calificacion}</td></tr>
              <tr><td>Petitorio</td><td>{k.fecha_petitorio ?? "—"}{k.hora_petitorio ? ` · ${k.hora_petitorio} h` : ""}{k.carta ? ` · carta ${k.carta}` : ""}</td></tr>
              {k.ubicacion && <tr><td>Ubicación</td><td>{k.ubicacion}</td></tr>}
              {k.expediente_en && <tr><td>Expediente en</td><td>{k.expediente_en}</td></tr>}
              <tr><td>Derecho de Vigencia</td><td>{k.vigencia_usd_anual != null
                ? <><b>≈ US$ {k.vigencia_usd_anual.toLocaleString("es-PE")} al año</b> <small>({k.tarifa_usd_ha} US$/ha; más penalidad si no acredita producción mínima)</small></>
                : "no aplica"}</td></tr>
            </tbody>
          </table>
          {k.sustancia === "no metálica" && (
            <div className={`que-extrae ${k.indicio_silice?.nivel ?? ""}`}>
              <b>¿Qué extrae?</b>
              <small>INGEMMET solo registra «no metálica», no el mineral. Indicios:</small>
              {k.material_probable
                ? <span>🔎 Probable: <b>{k.material_probable.material}</b> <small>(por {k.material_probable.fuente}: «{k.material_probable.texto}»)</small></span>
                : <span><small>Sin pista en el nombre, titular ni proyectos.</small></span>}
              {k.indicio_silice && <span>{k.indicio_silice.nivel === "alto" ? "🟢" : "🟡"} {k.indicio_silice.texto}</span>}
              {!!k.sobre_zonas?.length && (
                <small>Geología debajo: {k.sobre_zonas.map((z) => `${z.clase} ${z.unidad} (${z.pct} %)`).join(" · ")}</small>
              )}
              {k.actividad && (
                <small>Actividad: <b>{k.actividad.nivel}</b>{k.actividad.senales.length ? ` — ${k.actividad.senales.join("; ")}` : " (puede ser solo un petitorio especulativo)"}</small>
              )}
            </div>
          )}
          {k.indicio_pago && (
            <div className={`indicio ${k.indicio_pago.nivel}`}>
              {k.indicio_pago.nivel === "alerta" ? "⚠ " : k.indicio_pago.nivel === "ok" ? "✓ " : ""}<b>¿Al día con el pago?</b> {k.indicio_pago.texto}
            </div>
          )}
          {!!k.alertas?.length && <ul className="alertas-con">{k.alertas.map((x) => <li key={x}>{x}</li>)}</ul>}
          {!!k.reinfo?.length && (
            <div className="sub-con"><b>Mineros en formalización (REINFO) declarados aquí</b>
              {k.reinfo.map((r, i) => <small key={i}>· {r.nombre} — {r.actividad}{r.origen ? ` (${r.origen})` : ""}</small>)}
            </div>
          )}
          {k.uea && <div className="sub-con"><b>UEA</b><small>{k.uea.nombre ?? k.uea.codigo}{k.uea.derechos ? ` · ${k.uea.derechos} derechos` : ""}</small></div>}
          {k.pasivos && <div className="sub-con"><b>Pasivos ambientales</b><small>{k.pasivos.n}: {k.pasivos.tipos.join(", ")}</small></div>}
          {!!k.certificaciones?.length && (
            <div className="sub-con"><b>Certificación ambiental</b>
              {k.certificaciones.map((c, i) => (
                <small key={i}>· {c.tipo} {c.etapa ? `(${c.etapa.toLowerCase()})` : ""} — {c.proyecto || c.titular} · {c.resolucion}{c.fecha ? ` · ${c.fecha}` : ""}
                  {c.url && <> · <a href={c.url} target="_blank" rel="noopener">ver</a></>}</small>
              ))}
            </div>
          )}
          <div className="enlaces-con">
            {k.enlaces?.map((e) => <a key={e.url} href={e.url} target="_blank" rel="noopener">{e.titulo} ↗</a>)}
          </div>
          {k.pago && <small className="nota-pago">{k.pago}</small>}
        </>
      )}
    </div>
  );
  const [posHoja, setPosHoja] = useState({ x: 0, y: 0 });
  const arrastre = useRef<{ px: number; py: number; x: number; y: number; movido: boolean } | null>(null);
  const hojaRef = useRef<HTMLDivElement>(null);
  useEffect(() => { setHojaOculta(false); }, [res]);   // un análisis nuevo vuelve a mostrar el cuadro
  const empezarArrastre = (e: React.PointerEvent) => {
    arrastre.current = { px: e.clientX, py: e.clientY, x: posHoja.x, y: posHoja.y, movido: false };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  };
  const moverArrastre = (e: React.PointerEvent) => {
    const a = arrastre.current;
    if (!a) return;
    const dx = e.clientX - a.px, dy = e.clientY - a.py;
    if (!a.movido && Math.hypot(dx, dy) < 5) return;
    a.movido = true;
    // que el tirador nunca salga de la pantalla
    const r = hojaRef.current?.getBoundingClientRect();
    let x = a.x + dx, y = a.y + dy;
    if (r) {
      const baseX = r.left - posHoja.x, baseY = r.top - posHoja.y;
      x = Math.min(Math.max(x, -baseX - r.width + 80), window.innerWidth - baseX - 80);
      y = Math.min(Math.max(y, -baseY), window.innerHeight - baseY - 40);
    }
    setPosHoja({ x, y });
  };
  const terminarArrastre = () => {
    const a = arrastre.current;
    arrastre.current = null;
    if (a && !a.movido) setHoja((h) => (h === "cerrada" ? "media" : h === "media" ? "abierta" : "cerrada"));
  };
  const [pestana, setPestana] = useState<Pestana>("afloramientos");
  const [verCortes, setVerCortes] = useState(false);
  const [cortesFoco, setCortesFoco] = useState<FocoCorte | null>(null);   // índice con el que se abrió el histograma
  const [capaCorte, setCapaCorte] = useState<CapaCorte | null>(null);     // capa que se ve sola mientras se ajusta
  const [ubicacion, setUbicacion] = useState<[number, number] | null>(null);
  // la fábrica es FIJA (San Vicente de Cañete): no se mueve ni se guarda otra ubicación
  const fabrica = FABRICA_INICIAL;
  useEffect(() => { try { localStorage.removeItem("prospector-rmi:fabrica"); } catch { /* sin almacenamiento */ } }, []);
  const [celdaSel, setCeldaSel] = useState<Celda | null>(null);
  const [destino, setDestino] = useState<{ lat: number; lon: number } | null>(null);
  // (24/11/2026) por defecto: aptitud para vidrio flotado según la descripción litológica (vidrio.ts)
  const [orden, setOrden] = useState<"clase" | "distancia" | "oportunidad" | "vidrio">("vidrio");
  const [verNoAptas, setVerNoAptas] = useState(false);   // zonas «no aptas» para vidrio: ocultas en la lista
  // cuadrícula 1:25 000 que es el área actual (Sentinel-2 solo se analiza por cuadrícula)
  const [celdaArea, setCeldaArea] = useState<Celda | null>(null);
  // catálogo: formaciones de interés
  const [verCatalogo, setVerCatalogo] = useState(false);
  const [pestanaCat, setPestanaCat] = useState<PestanaCatalogo>("carpetas");
  const [formaciones, setFormaciones] = useState<Formacion[]>([]);
  const [formacionSel, setFormacionSel] = useState<Formacion | null>(null);
  const [hojasForm, setHojasForm] = useState<HojaFormacion[] | null>(null);
  const [cargandoHojas, setCargandoHojas] = useState(false);

  // memoria de cuadrículas analizadas: resultados completos (esta sesión) + resumen (guardado)
  const cacheCeldas = useRef(new Map<string, { res: ResultadoBusqueda; s2: ResultadoSentinel | null }>());
  const [historial, setHistorial] = useState<ResumenCelda[]>(leerHistorial);
  const [modoS2, setModoS2] = useState(true); // al pasar a la vecina, ¿también Sentinel-2?
  // carpetas de cuadrículas de interés
  const [carpetas, setCarpetas] = useState<Carpeta[]>(leerCarpetas);
  const [guardando, setGuardando] = useState<Celda | null>(null); // selector «Guardar en carpeta»
  const [carpetaAbierta, setCarpetaAbierta] = useState<string | null>(null);
  const [nombreNueva, setNombreNueva] = useState("");

  function guardarCarpetas(f: (cs: Carpeta[]) => Carpeta[]) {
    setCarpetas((cs) => {
      const n = f(cs);
      try { localStorage.setItem(CLAVE_CARPETAS, JSON.stringify(n)); } catch { setError("No se pudo guardar la carpeta en este navegador."); }
      return n;
    });
  }

  function datosActuales(codigo: string): DatosCelda | null {
    const x = cacheCeldas.current.get(codigo);
    return x ? datosDeAnalisis(x.res, x.s2) : null;
  }

  function crearCarpeta(nombre: string, conCelda?: Celda) {
    const id = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
    const ahora = new Date().toISOString();
    guardarCarpetas((cs) => [...cs, {
      id, nombre: nombre.trim() || `Carpeta ${cs.length + 1}`, creada: ahora,
      celdas: conCelda ? [{ codigo: conCelda.codigo, agregada: ahora, nota: "", datos: datosActuales(conCelda.codigo) }] : [],
    }]);
    setNombreNueva("");
    if (conCelda) {
      setAviso(`${conCelda.codigo} guardada en «${nombre.trim() || "carpeta nueva"}».`);
      alGuardarEnCarpeta(id, conCelda);
    }
    return id;
  }

  function alternarEnCarpeta(id: string, c: Celda) {
    const agregando = !carpetas.find((k) => k.id === id)?.celdas.some((g) => g.codigo === c.codigo);
    guardarCarpetas((cs) => cs.map((k) => {
      if (k.id !== id) return k;
      if (k.celdas.some((g) => g.codigo === c.codigo)) return { ...k, celdas: k.celdas.filter((g) => g.codigo !== c.codigo) };
      return { ...k, celdas: [...k.celdas, { codigo: c.codigo, agregada: new Date().toISOString(), nota: "", datos: datosActuales(c.codigo) }] };
    }));
    if (agregando) alGuardarEnCarpeta(id, c);
  }

  /** Al guardar una cuadrícula en una carpeta: se recopila su bibliografía y se OFRECE
   *  (no se impone) descargar el mapa geológico como imagen. */
  function alGuardarEnCarpeta(carpetaId: string, c: Celda) {
    setOfertaMapa({ carpetaId, celda: c });
    obtenerBiblio(c).then((b) => {
      if (!b) return;
      guardarCarpetas((cs) => cs.map((k) => (k.id !== carpetaId ? k
        : { ...k, celdas: k.celdas.map((g) => (g.codigo === c.codigo ? { ...g, biblio: b } : g)) })));
    });
  }

  // ---- mapa geológico de la cuadrícula como imagen (lámina PNG con leyenda) → adjunto de la carpeta
  const [ofertaMapa, setOfertaMapa] = useState<{ carpetaId: string; celda: Celda } | null>(null);
  const [generandoMapa, setGenerandoMapa] = useState(false);

  async function generarMapa(carpetaId: string, c: Celda, escala: "50K" | "100K") {
    setGenerandoMapa(true);
    try {
      const png = await api.mapaGeologico(c, escala, c.codigo);
      const archivo = new File([png], `Mapa geológico ${escala === "50K" ? "1-50000" : "1-100000"} ${c.codigo}.png`, { type: "image/png" });
      const k = carpetasRef.current.find((x) => x.id === carpetaId);
      if (k) await adjuntar(k, c.codigo, [archivo]);
      setOfertaMapa(null);
      setAviso(`Mapa geológico ${escala === "50K" ? "1:50 000" : "1:100 000"} de ${c.codigo} guardado en la carpeta (📎 adjuntos).`);
    } catch (e) {
      setError(`No se pudo armar el mapa geológico: ${(e as Error).message}`);
    } finally {
      setGenerandoMapa(false);
    }
  }

  function quitarDeCarpeta(id: string, codigo: string) {
    guardarCarpetas((cs) => cs.map((k) => (k.id !== id ? k : { ...k, celdas: k.celdas.filter((g) => g.codigo !== codigo) })));
  }

  function notaDeCelda(id: string, codigo: string, nota: string) {
    guardarCarpetas((cs) => cs.map((k) => (k.id !== id ? k
      : { ...k, celdas: k.celdas.map((g) => (g.codigo === codigo ? { ...g, nota } : g)) })));
  }

  function renombrarCarpeta(id: string, nombre: string) {
    if (!nombre.trim()) return;
    guardarCarpetas((cs) => cs.map((k) => (k.id === id ? { ...k, nombre: nombre.trim() } : k)));
  }

  function borrarCarpeta(id: string) {
    guardarCarpetas((cs) => cs.filter((k) => k.id !== id));
    setCarpetaAbierta(null);
  }

  // ---- carpetas REALES en el dispositivo (laptop: carpeta elegida · APK: Documentos)
  const plat = useMemo(plataforma, []);
  const [disp, setDisp] = useState<{ estado: "sin" | "pedir" | "listo" | "error"; donde?: string; msg?: string; hora?: string }>({ estado: "sin" });
  const escritor = useRef<Escritor | null>(null);
  const raizPendiente = useRef<FileSystemDirectoryHandle | null>(null);
  const imagenesEscritas = useRef(new Set<string>());

  async function activarEscritor(e: Escritor) {
    escritor.current = e;
    setDisp({ estado: "listo", donde: e.donde });
    // recuperar carpetas que existan en el dispositivo y no en este navegador
    try {
      const recuperadas: Carpeta[] = [];
      for (const txt of await e.leerJsons()) {
        try {
          const k = JSON.parse(txt) as Carpeta;
          if (k && typeof k.id === "string" && Array.isArray(k.celdas)) recuperadas.push(k);
        } catch { /* json dañado */ }
      }
      if (recuperadas.length) {
        let n = 0;
        guardarCarpetas((cs) => {
          const ids = new Set(cs.map((k) => k.id));
          const nuevas = recuperadas.filter((k) => !ids.has(k.id));
          n = nuevas.length;
          return [...cs, ...nuevas];
        });
        setTimeout(() => n && setAviso(`Se recuperaron ${n} carpeta(s) desde ${e.donde}.`), 0);
      }
    } catch { /* sin lectura: igual se escribe */ }
    sincronizarAhora();
  }

  useEffect(() => {
    (async () => {
      if (plat === "app") {
        try { await activarEscritor(await escritorApp()); } catch (e) { setDisp({ estado: "error", msg: (e as Error).message }); }
      } else if (plat === "laptop") {
        const h = await raizGuardada();
        if (!h) return;
        if (await permiso(h, false)) await activarEscritor(escritorLaptop(h));
        else { raizPendiente.current = h; setDisp({ estado: "pedir", donde: h.name }); }
      }
    })();
  }, []);

  async function conectarLaptop(cambiar = false) {
    try {
      let h = cambiar ? null : raizPendiente.current;
      if (h && !(await permiso(h, true))) h = null;
      if (!h) h = await elegirRaiz();
      raizPendiente.current = null;
      imagenesEscritas.current.clear();
      await activarEscritor(escritorLaptop(h));
    } catch (e) {
      if ((e as Error).name !== "AbortError") setDisp({ estado: "error", msg: (e as Error).message });
    }
  }

  async function desconectarLaptop() {
    await olvidarRaiz();
    escritor.current = null;
    setDisp({ estado: "sin" });
  }

  const carpetasRef = useRef(carpetas);
  carpetasRef.current = carpetas;
  const fabricaRef = useRef(fabrica);
  fabricaRef.current = fabrica;

  /** Escribe todas las carpetas en el dispositivo. Nunca borra nada allí. */
  async function sincronizarAhora() {
    const e = escritor.current;
    if (!e) return;
    try {
      // adjuntos que aún no están en este dispositivo (p. ej. se conectó la laptop después)
      const copiados = new Set<string>();
      for (const k of carpetasRef.current) {
        const grupos: [string | null, Adjunto[]][] = [[null, k.adjuntos ?? []], ...k.celdas.map((g) => [g.codigo, g.adjuntos ?? []] as [string, Adjunto[]])];
        for (const [codigo, lista] of grupos) {
          for (const a of lista.filter((x) => x.copiadoEn !== e.donde)) {
            const b = await leerAdjunto(a.id);
            if (!b) continue;
            await e.archivo(rutaAdjuntos(k, codigo), a.nombre, b);
            copiados.add(a.id);
          }
        }
      }
      if (copiados.size) {
        const marcar = (as?: Adjunto[]) => as?.map((a) => (copiados.has(a.id) ? { ...a, copiadoEn: e.donde } : a));
        guardarCarpetas((cs) => cs.map((k) => ({ ...k, adjuntos: marcar(k.adjuntos), celdas: k.celdas.map((g) => ({ ...g, adjuntos: marcar(g.adjuntos) })) })));
      }
      for (const k of carpetasRef.current) {
        const dir = [k.nombre];
        await e.texto(dir, "carpeta.json", JSON.stringify(k, null, 1));
        await e.texto(dir, "Resumen (Excel).csv", csvCarpeta(k, fabricaRef.current));
        for (const g of k.celdas) {
          await e.texto([...dir, g.codigo], "ficha.txt", fichaCelda(k, g, fabricaRef.current));
          const s = cacheCeldas.current.get(g.codigo)?.s2;
          for (const [clave, url] of Object.entries(s?.capas ?? {})) {
            const marca = `${k.nombre}/${g.codigo}/${s?.periodo}/${clave}`;
            if (imagenesEscritas.current.has(marca)) continue;
            const ext = url.startsWith("data:image/jpeg") ? "jpg" : "png";
            await e.binario([...dir, g.codigo], `satelite_${clave}.${ext}`, url);
            imagenesEscritas.current.add(marca);
          }
        }
      }
      setDisp({ estado: "listo", donde: e.donde, hora: new Date().toLocaleTimeString("es-PE", { hour: "2-digit", minute: "2-digit" }) });
    } catch (err) {
      const nombre = (err as Error).name;
      if (nombre === "NotAllowedError" || nombre === "SecurityError") {
        setDisp({ estado: "pedir", donde: e.donde, msg: "El navegador retiró el permiso." });
      } else {
        setDisp({ estado: "error", donde: e.donde, msg: (err as Error).message });
      }
    }
  }

  // cada cambio en las carpetas se copia al dispositivo (agrupado cada 1,2 s)
  useEffect(() => {
    if (!escritor.current) return;
    const t = setTimeout(sincronizarAhora, 1200);
    return () => clearTimeout(t);
  }, [carpetas]);

  // ---- adjuntos (fotos, PDF…) de una cuadrícula guardada o de la carpeta en general
  const [visor, setVisor] = useState<{ url: string; tipo: string; nombre: string } | null>(null);
  const [subiendo, setSubiendo] = useState<string | null>(null);

  function cambiarAdjuntos(id: string, codigo: string | null, f: (as: Adjunto[]) => Adjunto[]) {
    guardarCarpetas((cs) => cs.map((k) => (k.id !== id ? k
      : codigo == null ? { ...k, adjuntos: f(k.adjuntos ?? []) }
        : { ...k, celdas: k.celdas.map((g) => (g.codigo === codigo ? { ...g, adjuntos: f(g.adjuntos ?? []) } : g)) })));
  }

  function nombreUnico(nombre: string, existentes: Adjunto[]): string {
    const n = nombreSeguro(nombre);
    if (!existentes.some((a) => a.nombre === n)) return n;
    const i = n.lastIndexOf(".");
    const base = i > 0 ? n.slice(0, i) : n;
    const ext = i > 0 ? n.slice(i) : "";
    let k = 2;
    while (existentes.some((a) => a.nombre === `${base} (${k})${ext}`)) k++;
    return `${base} (${k})${ext}`;
  }

  async function adjuntar(k: Carpeta, codigo: string | null, archivos: FileList | File[] | null) {
    if (!archivos?.length) return;
    setSubiendo(`${k.id}/${codigo ?? ""}`);
    const previos = (codigo == null ? k.adjuntos : k.celdas.find((g) => g.codigo === codigo)?.adjuntos) ?? [];
    const nuevos: Adjunto[] = [];
    try {
      for (const f of Array.from(archivos)) {
        if (f.size > MAX_ADJUNTO) {
          setAviso(`«${f.name}» pesa ${pesoLegible(f.size)}; el máximo es 30 MB.`);
          continue;
        }
        const ahora = new Date();
        const a: Adjunto = {
          id: `${ahora.getTime().toString(36)}${Math.random().toString(36).slice(2, 7)}`,
          nombre: nombreUnico(f.name || `foto ${ahora.toISOString().slice(0, 19).replace(/:/g, "-")}.jpg`, [...previos, ...nuevos]),
          tipo: f.type || "application/octet-stream", tamano: f.size, fecha: ahora.toISOString(),
          miniatura: await miniatura(f),
        };
        await guardarAdjunto(a.id, f);
        const e = escritor.current;
        if (e) {
          try { await e.archivo(rutaAdjuntos(k, codigo), a.nombre, f); a.copiadoEn = e.donde; } catch { /* se reintenta al sincronizar */ }
        }
        nuevos.push(a);
      }
      if (nuevos.length) {
        cambiarAdjuntos(k.id, codigo, (as) => [...as, ...nuevos]);
        setAviso(`${nuevos.length} archivo(s) adjuntado(s)${nuevos.every((a) => a.copiadoEn) ? ` y copiado(s) a ${escritor.current?.donde}` : ""}.`);
      }
    } catch (err) {
      setError(`No se pudo adjuntar: ${(err as Error).message}`);
    } finally {
      setSubiendo(null);
    }
  }

  async function abrirAdjunto(k: Carpeta, codigo: string | null, a: Adjunto) {
    let b = await leerAdjunto(a.id);
    if (!b && escritor.current) {
      // el navegador perdió su copia: se recupera desde la carpeta del dispositivo
      b = await escritor.current.leerArchivo(rutaAdjuntos(k, codigo), a.nombre, a.tipo);
      if (b) await guardarAdjunto(a.id, b).catch(() => undefined);
    }
    if (!b) {
      setError(`No se encuentra «${a.nombre}» en este dispositivo.${plat === "laptop" && !escritor.current ? " Conecta la carpeta de la laptop para recuperarlo." : ""}`);
      return;
    }
    setVisor({ url: URL.createObjectURL(b), tipo: a.tipo || b.type, nombre: a.nombre });
  }

  function cerrarVisor() {
    if (visor) URL.revokeObjectURL(visor.url);
    setVisor(null);
  }

  async function quitarAdjunto(k: Carpeta, codigo: string | null, a: Adjunto) {
    if (!confirm(`¿Quitar «${a.nombre}» de la app?${a.copiadoEn ? " (la copia en la carpeta del dispositivo se conserva)" : ""}`)) return;
    cambiarAdjuntos(k.id, codigo, (as) => as.filter((x) => x.id !== a.id));
    await borrarAdjunto(a.id).catch(() => undefined);
  }

  const listaAdjuntos = (k: Carpeta, codigo: string | null, adjuntos: Adjunto[] = []) => (
    <div className="adjuntos">
      {adjuntos.map((a) => (
        <div key={a.id} className="adj" role="button" tabIndex={0} title={`${a.nombre} · ${pesoLegible(a.tamano)}`}
          onClick={() => abrirAdjunto(k, codigo, a)}>
          {a.miniatura ? <img src={a.miniatura} alt="" />
            : <span className="icono-adj">{a.tipo === "application/pdf" ? "📄" : a.tipo.startsWith("image/") ? "🖼" : "📎"}</span>}
          <small>{a.nombre}</small>
          <button className="quitar" title="Quitar" onClick={(e) => { e.stopPropagation(); quitarAdjunto(k, codigo, a); }}>×</button>
        </div>
      ))}
      <label className="adj agregar" title="Fotos (también desde la cámara del celular), PDF, Word, Excel, KML…">
        <input type="file" multiple hidden
          accept="image/*,application/pdf,.pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.kml,.kmz"
          onChange={(e) => { adjuntar(k, codigo, e.target.files); e.target.value = ""; }} />
        <span className="icono-adj">{subiendo === `${k.id}/${codigo ?? ""}` ? "⏳" : "📎"}</span>
        <small>Adjuntar foto o PDF</small>
      </label>
    </div>
  );

  const carpetasDe = (codigo: string) => carpetas.filter((k) => k.celdas.some((g) => g.codigo === codigo));
  const enCarpeta = useMemo(() => new Set(carpetas.flatMap((k) => k.celdas.map((g) => g.codigo))), [carpetas]);

  const km = (lat: number, lon: number) => distanciaKm(fabrica[0], fabrica[1], lat, lon);

  // ---- distancia POR CARRETERA fábrica → punto (OSRM · OpenStreetMap, vía backend /ruta).
  // Se guarda en el dispositivo (las vías cambian poco): no se vuelve a pedir la misma ruta.
  const claveRuta = (lat: number, lon: number) => `${fabrica[0].toFixed(4)},${fabrica[1].toFixed(4)}>${lat.toFixed(4)},${lon.toFixed(4)}`;
  const [rutas, setRutas] = useState<Record<string, Ruta | "cargando" | { error: string }>>(() => {
    try { return JSON.parse(localStorage.getItem("prospector-rmi:rutas2") || "{}"); } catch { return {}; }
  });
  const [verRuta, setVerRuta] = useState(false);      // panel de la ruta abierto
  const [modoRuta, setModoRuta] = useState(false);    // el próximo toque en el mapa = destino de la ruta
  async function calcularRuta(lat: number, lon: number, forzar = false) {
    const k = claveRuta(lat, lon);
    const ya = rutas[k];
    setVerRuta(true);
    if (!forzar && ya && ya !== "cargando" && !("error" in ya) && "bloques" in ya) { setDestino({ lat, lon }); return; }
    setRutas((r) => ({ ...r, [k]: "cargando" }));
    try {
      const x = await api.ruta(fabrica, lat, lon);
      setRutas((r) => {
        const n = { ...r, [k]: x };
        // en el dispositivo: solo las rutas ya calculadas (las 150 más recientes)
        const listas = Object.entries(n).filter(([, v]) => v !== "cargando" && !("error" in v)).slice(-150);
        try { localStorage.setItem("prospector-rmi:rutas2", JSON.stringify(Object.fromEntries(listas))); } catch { /* lleno */ }
        return n;
      });
      setDestino({ lat, lon });
    } catch (e) {
      setDestino({ lat, lon });
      setRutas((r) => ({ ...r, [k]: { error: (e as Error).message } }));
    }
  }
  /** «🚚 por carretera» → «🚚 164,6 km · 🔵 164,4 pista · 🟤 0,2 trocha · 🩷 1,7 a pie» (sin tiempos) */
  const botonRuta = (lat: number, lon: number) => {
    const r = rutas[claveRuta(lat, lon)];
    if (!r || (r !== "cargando" && "error" in r)) {
      return (
        <button className="enlace ruta-btn" onClick={(e) => { e.stopPropagation(); calcularRuta(lat, lon); }}
          title="Ruta desde la fábrica por tramos: pista asfaltada, trocha y a pie (OpenStreetMap)">
          <Truck size={13} /> {r ? "Reintentar ruta" : "Ruta por carretera"}
        </button>
      );
    }
    if (r === "cargando") return <span className="ruta-dato"><Truck size={13} /> Trazando la ruta…</span>;
    if (!("bloques" in r)) {   // ruta guardada con el formato anterior: se vuelve a pedir
      return <button className="enlace ruta-btn" onClick={(e) => { e.stopPropagation(); calcularRuta(lat, lon, true); }}><Truck size={13} /> Ruta por tramos</button>;
    }
    return (
      <span className="ruta-dato" onClick={(e) => { e.stopPropagation(); setDestino({ lat, lon }); setVerRuta(true); }}
        title="Ver la ruta en el mapa">
        <Truck size={13} /> <b>{r.km_total.toLocaleString("es-PE")} km</b>
        {(Object.keys(COLOR_TRAMO) as TipoTramo[]).filter((t) => r.resumen[t] >= 0.05).map((t) => (
          <span key={t} className="tramo-mini"> · <i style={{ background: COLOR_TRAMO[t] }} />{r.resumen[t].toLocaleString("es-PE")} {CORTO_TRAMO[t]}</span>
        ))}
      </span>
    );
  };
  // ---- BARRIDO DE REGIÓN: muchas cuadrículas de una vez (geología + áreas libres, sin Sentinel-2).
  // Cada cuadrícula terminada queda como análisis «Solo geología» guardado (abrirla es instantáneo).
  const [verBarrido, setVerBarrido] = useState(false);
  const [hojaBarrido, setHojaBarrido] = useState("");
  const [barridoCeldas, setBarridoCeldas] = useState<Celda[]>(() => {
    return leerBarrido(materiaGuardada()).celdas;
  });
  const [barridoRes, setBarridoRes] = useState<Record<string, FilaBarrido>>(() => {
    return leerBarrido(materiaGuardada()).res;
  });
  const [barridoTrabajo, setBarridoTrabajo] = useState<{ id: string; total: number; hechas: number; terminado: boolean; segundos: number } | null>(null);
  const sondeo = useRef<number | null>(null);
  useEffect(() => {
    try { localStorage.setItem(claveBarrido(materiaId), JSON.stringify({ celdas: barridoCeldas, res: barridoRes })); } catch { /* lleno */ }
  }, [barridoCeldas, barridoRes]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => { if (sondeo.current) window.clearInterval(sondeo.current); }, []);

  /** Cuadrículas 1:25 000 con tierra de la vista actual o de una hoja (100K/50K) escrita. */
  function celdasDeRegion(modo: "vista" | "hoja"): Celda[] | string {
    let b: { sur: number; oeste: number; norte: number; este: number } | null = null;
    if (modo === "hoja") {
      const u = parsearUbicacion(hojaBarrido);
      if (!u) return "Escribe una hoja: 1:100 000 (27-k) o 1:50 000 (27k4).";
      b = u;
    } else {
      const v = mapaRef.current?.vistaComoPoligono();
      if (!v) return "El mapa aún no está listo.";
      b = { sur: Math.min(...v.map((x) => x[1])), norte: Math.max(...v.map((x) => x[1])),
            oeste: Math.min(...v.map((x) => x[0])), este: Math.max(...v.map((x) => x[0])) };
    }
    const e = 1e-6;
    const cs = celdasEnVista(b.sur + e, b.oeste + e, b.norte - e, b.este - e, "25K", 200);
    if (!cs.length) return "No hay cuadrículas con tierra en esa región.";
    if (cs.length > MAX_BARRIDO) return `Son ${cs.length} cuadrículas; el máximo por barrido es ${MAX_BARRIDO}: acerca el mapa o usa una hoja 1:100 000 (16).`;
    return cs;
  }

  async function iniciarBarrido(celdas: Celda[]) {
    if (sondeo.current) window.clearInterval(sondeo.current);
    try {
      const { id, total } = await api.barridoIniciar(celdas.map((c) => ({ codigo: c.codigo, sur: c.sur, oeste: c.oeste, norte: c.norte, este: c.este })), materiaId);
      setBarridoCeldas(celdas);
      setBarridoRes({});
      setBarridoTrabajo({ id, total, hechas: 0, terminado: false, segundos: 0 });
      let desde = 0;
      let ocupado = false;
      sondeo.current = window.setInterval(async () => {
        if (ocupado) return;
        ocupado = true;
        try {
          const e = await api.barridoEstado(id, desde);
          desde += e.resultados.length;
          const nuevos: Record<string, FilaBarrido> = {};
          for (const fila of e.resultados) {
            const { resultado, ...resumen } = fila;
            const c = celda25(fila.codigo);
            // queda como análisis guardado, salvo que ya hubiera uno (p. ej. con Sentinel-2): ese no se pisa
            if (fila.ok && resultado && c && !(await obtenerAnalisis(fila.codigo))) registrarCelda(c, resultado, null);
            nuevos[fila.codigo] = resumen;
          }
          if (e.resultados.length) setBarridoRes((r) => ({ ...r, ...nuevos }));
          setBarridoTrabajo({ id, total: e.total, hechas: e.hechas, terminado: e.terminado, segundos: e.segundos });
          if (e.terminado && sondeo.current) { window.clearInterval(sondeo.current); sondeo.current = null; }
        } catch (err) {
          setError(`Barrido: ${(err as Error).message}`);
          if (sondeo.current) { window.clearInterval(sondeo.current); sondeo.current = null; }
          setBarridoTrabajo((t) => (t ? { ...t, terminado: true } : t));
        } finally {
          ocupado = false;
        }
      }, 2000);
    } catch (e) {
      setError(`No se pudo iniciar el barrido: ${(e as Error).message}`);
    }
  }

  function cancelarBarrido() {
    if (barridoTrabajo && !barridoTrabajo.terminado) api.barridoCancelar(barridoTrabajo.id);
    if (sondeo.current) { window.clearInterval(sondeo.current); sondeo.current = null; }
    setBarridoTrabajo((t) => (t ? { ...t, terminado: true } : t));
  }

  const rankingBarrido = useMemo(() => Object.values(barridoRes)
    .filter((f) => f.ok && f.puntaje != null)
    .sort((a, b) => (b.puntaje ?? 0) - (a.puntaje ?? 0)), [barridoRes]);
  const puestoBarrido = useMemo(() => new Map(rankingBarrido.map((f, i) => [f.codigo, i + 1])), [rankingBarrido]);
  const barridoMapa = useMemo(() => barridoCeldas.map((c) => ({
    codigo: c.codigo, sur: c.sur, oeste: c.oeste, norte: c.norte, este: c.este,
    puntaje: barridoRes[c.codigo]?.ok ? barridoRes[c.codigo].puntaje ?? 0 : null,
    puesto: puestoBarrido.get(c.codigo) ?? null,
  })), [barridoCeldas, barridoRes, puestoBarrido]);

  // ---- TONELAJE por zona y CURVAS DE NIVEL de la cuadrícula (Copernicus DEM 30 m)
  const [tonelajes, setTonelajes] = useState<Record<string, Tonelaje | "cargando" | { error: string }>>({});
  const [paramTon, setParamTon] = useState<Record<string, { potencia_manto?: string; densidad?: string }>>({});
  const claveTon = (a: Afloramiento) => `${celdaArea?.codigo ?? ""}|${a.id}`;
  async function calcularTonelaje(a: Afloramiento) {
    const k = claveTon(a);
    const p = paramTon[k] ?? {};
    const num = (s?: string) => (s && Number(s.replace(",", ".")) > 0 ? Number(s.replace(",", ".")) : undefined);
    setTonelajes((t) => ({ ...t, [k]: "cargando" }));
    try {
      const x = await api.tonelaje(a, { libre: res?.libres?.geometria, potencia_manto: num(p.potencia_manto), densidad: num(p.densidad) });
      setTonelajes((t) => ({ ...t, [k]: x }));
    } catch (e) {
      setTonelajes((t) => ({ ...t, [k]: { error: (e as Error).message } }));
    }
  }
  const [curvas, setCurvas] = useState<Curvas | "cargando" | null>(null);
  const [curvasDe, setCurvasDe] = useState<string | null>(null);
  async function alternarCurvas() {
    if (curvas && curvasDe === celdaArea?.codigo) { setCurvas(null); setCurvasDe(null); return; }
    if (!celdaArea) return;
    setCurvas("cargando"); setCurvasDe(celdaArea.codigo);
    try {
      setCurvas(await api.curvas(celdaArea));
    } catch (e) {
      setCurvas(null); setCurvasDe(null);
      setError(`Curvas de nivel: ${(e as Error).message}`);
    }
  }
  // al cambiar de cuadrícula, las curvas de la anterior se quitan
  useEffect(() => { if (curvasDe && curvasDe !== celdaArea?.codigo) { setCurvas(null); setCurvasDe(null); } }, [celdaArea?.codigo]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---- análisis guardados en este dispositivo (IndexedDB): sobreviven a cerrar la app
  const [guardados, setGuardados] = useState<Set<string>>(new Set());
  const [espacioMB, setEspacioMB] = useState<number | null>(null);
  useEffect(() => {
    migracionClases.then(() => codigosConAnalisis()).then((cs) => setGuardados(new Set(cs)));
    espacioUsadoMB().then(setEspacioMB);
  }, []);

  /** Guarda el análisis en memoria y en el dispositivo. */
  function recordar(codigo: string, r: ResultadoBusqueda, s: ResultadoSentinel | null) {
    cacheCeldas.current.set(codigo, { res: r, s2: s });
    guardarAnalisis(codigo, { res: r, s2: s, guardado: new Date().toISOString() }).then((ok) => {
      if (ok) {
        setGuardados((g) => new Set(g).add(codigo));
        espacioUsadoMB().then(setEspacioMB);
      } else {
        setAviso("No queda espacio en este navegador para guardar el análisis: solo durará esta sesión.");
      }
    });
  }

  /** Análisis de la cuadrícula: de la memoria o, si se cerró la app, del dispositivo. */
  async function obtenerAnalisis(codigo: string) {
    const enMemoria = cacheCeldas.current.get(codigo);
    if (enMemoria) return enMemoria;
    await migracionClases;
    const g = await leerAnalisis<ResultadoBusqueda, ResultadoSentinel>(codigo);
    if (!g) return undefined;
    // análisis guardados antes del 24/11/2026: se quitan las capas que ya no se usan (pureza, prioridad combinada)
    const a = { res: g.res, s2: g.s2 ? sinCapasViejas(g.s2) : g.s2 };
    cacheCeldas.current.set(codigo, a);
    return a;
  }

  async function olvidarAnalisis(codigo: string) {
    cacheCeldas.current.delete(codigo);
    await borrarAnalisis(codigo);
    setGuardados((g) => { const n = new Set(g); n.delete(codigo); return n; });
    espacioUsadoMB().then(setEspacioMB);
  }

  function registrarCelda(c: Celda, r: ResultadoBusqueda, s: ResultadoSentinel | null) {
    recordar(c.codigo, r, s);
    const resumen: ResumenCelda = {
      codigo: c.codigo, fecha: new Date().toISOString(),
      A: r.resumen.clase_A, B: r.resumen.clase_B, C: r.resumen.clase_C,
      haAB: Math.round(r.afloramientos.filter((a) => a.clase !== "C").reduce((t, a) => t + a.area_ha, 0)),
      // la Prioridad libre se calcula después (en el navegador) y la completa el efecto de prioLibre
      haLibre: historialPorCodigo.get(c.codigo)?.haLibre ?? null, haNeg: historialPorCodigo.get(c.codigo)?.haNeg ?? null,
      sentinel: !!s,
      formaciones: [...new Set(r.afloramientos.flatMap((a) => a.formaciones ?? []))],
    };
    setHistorial((h) => {
      const nuevo = [resumen, ...h.filter((x) => x.codigo !== c.codigo)].slice(0, 300);
      try { localStorage.setItem(claveHistorial(materiaId), JSON.stringify(nuevo)); } catch { /* sin almacenamiento */ }
      return nuevo;
    });
    // si la cuadrícula está en alguna carpeta, se actualiza lo recopilado. Se mira el estado
    // ACTUAL de las carpetas (no el del inicio del análisis): el usuario puede haberla guardado
    // con ★ mientras el análisis seguía en curso.
    const datos = datosDeAnalisis(r, s);
    guardarCarpetas((cs) => (cs.some((k) => k.celdas.some((g) => g.codigo === c.codigo))
      ? cs.map((k) => ({ ...k, celdas: k.celdas.map((g) => (g.codigo === c.codigo ? { ...g, datos } : g)) }))
      : cs));
  }

  function borrarHistorial() {
    setHistorial([]);
    cacheCeldas.current.clear();
    try { localStorage.removeItem(claveHistorial(materiaId)); } catch { /* sin almacenamiento */ }
  }

  // marcas del mapa: analizadas (✓ resumen) y guardadas en carpeta (★)
  const marcasAnalizadas: MarcaCelda[] = useMemo(() => {
    const marcas: MarcaCelda[] = historial.map((h) => ({
      codigo: h.codigo,
      clase: h.A ? "A" : h.B ? "B" : h.C ? "C" : null,
      etiqueta: `${enCarpeta.has(h.codigo) ? "★" : "✓"} ${etiquetaResumen(h)}`,
    }));
    const vistos = new Set(historial.map((h) => h.codigo));
    for (const codigo of enCarpeta) if (!vistos.has(codigo)) marcas.push({ codigo, clase: null, etiqueta: "★ sin analizar" });
    return marcas;
  }, [historial, enCarpeta]);

  const historialPorCodigo = useMemo(() => new Map(historial.map((h) => [h.codigo, h])), [historial]);

  /** Cambia la materia prima: cada una con sus análisis, analizadas, barrido y catálogo. */
  function cambiarMateria(id: string) {
    if (id === materiaId) return;
    usarMateria(id);
    try { localStorage.setItem(CLAVE_MATERIA, id); } catch { /* sin almacenamiento */ }
    setMateriaId(id);
    cacheCeldas.current.clear();
    setRes(null); setS2(null); setArea(null); setCeldaArea(null); setCeldaSel(null); setFase("inicio");
    setFormacionSel(null); setHojasForm(null);
    setHistorial(leerHistorial(id));
    const b = leerBarrido(id);
    setBarridoCeldas(b.celdas); setBarridoRes(b.res);
    codigosConAnalisis().then((cs) => setGuardados(new Set(cs)));
    setFormaciones([]);
    api.formaciones(id).then(setFormaciones).catch(() => { /* se reintenta al abrir el catálogo */ });
    setCapas((c) => ({ ...c, geo50_si: true, geo100_si: false }));
  }

  async function elegirFormacion(f: Formacion | null) {
    setFormacionSel(f);
    setHojasForm(null);
    setResaltado(null);
    if (!f) {
      setCapas((c) => ({ ...c, geo50_si: true }));
      return;
    }
    // se ve SOLO la formación elegida (la capa silícea general se apaga)
    setCapas((c) => ({ ...c, geo50_si: false, geo100_si: false, geo50: false, geo100: false }));
    if (f.nota) setAviso(f.nota);
    setCargandoHojas(true);
    try {
      setHojasForm(await (f.id.startsWith("texto:") ? api.hojasTexto(f.id.slice(6)) : api.hojasFormacion(f.id, materiaId)));
    } catch (e) {
      setError(`No se pudieron cargar las hojas de ${f.nombre}: ${(e as Error).message}`);
    } finally {
      setCargandoHojas(false);
    }
  }

  function irAHoja(codigo: string) {
    const h = hoja50(codigo);
    if (!h) return;
    setVerCatalogo(false);
    mapaRef.current?.encuadrar(celdaComoPoligono(h));
  }

  // hojas de la formación: de la más cercana a la más lejana de la fábrica
  const hojasOrdenadas = useMemo(() => (hojasForm ?? [])
    .map((h) => {
      const c = hoja50(h.hoja);
      return { ...h, celda: c, km: c ? distanciaKm(fabrica[0], fabrica[1], (c.norte + c.sur) / 2, (c.oeste + c.este) / 2) : Infinity };
    })
    .sort((a, b) => a.km - b.km), [hojasForm, fabrica]);


  useEffect(() => {
    api.materiales().then(setMateriales).catch(() => { /* respaldo local */ });
    api.formaciones(materiaId).then(setFormaciones).catch(() => { /* se reintenta al abrir el catálogo */ });
    api.hojas100().then(setHojas100).catch(() => { /* el buscador igual acepta códigos */ });
  }, []);

  useEffect(() => {
    if (!aviso) return;
    const t = setTimeout(() => setAviso(null), 3500);
    return () => clearTimeout(t);
  }, [aviso]);

  // ---- buscador universal: cuadrángulos (código o nombre de hoja) y geología (formación, roca)
  type Sugerencia = { clave: string; icono: string; titulo: string; sub: string; accion: () => void };

  function irAUbicacion(u: Ubicacion) {
    setSugerir(false);
    setTexto(u.codigo);
    setVerCatalogo(false);
    mapaRef.current?.encuadrar([[u.oeste, u.sur], [u.este, u.sur], [u.este, u.norte], [u.oeste, u.norte]]);
    if (u.nivel === "25K") {
      const c = celda25(u.codigo);
      setResaltado(null);
      if (c && tieneTierra(c)) setCeldaSel(c);
      else { setCeldaSel(null); setAviso(`${u.codigo} es solo mar o está fuera del Perú.`); }
    } else {
      setCeldaSel(null);
      setResaltado(u);
      setAviso(u.nota ?? `Hoja ${u.nivel === "100K" ? "1:100 000" : "1:50 000"} ${u.codigo}: toca una de sus cuadrículas para analizarla.`);
    }
  }

  async function filtrarPorTexto(t: string) {
    setSugerir(false);
    try {
      const f = await api.filtroTexto(t);
      setTexto(f.nombre.replace(/[«»]/g, ""));
      await elegirFormacion(f);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const sugerencias: Sugerencia[] = useMemo(() => {
    const q = texto.trim();
    if (!q) return [];
    const out: Sugerencia[] = [];
    const u = parsearUbicacion(q);
    if (u) {
      const nombre100 = hojas100.find((h) => h.codigo === (u.nivel === "100K" ? u.codigo : `${u.codigo.match(/^\d+/)?.[0]}-${u.codigo.match(/^\d+([a-zñ])/)?.[1]}`))?.nombre;
      out.push({ clave: `u:${u.codigo}`, icono: "📍", titulo: `Ir a ${u.codigo}`,
        sub: `${u.nivel === "25K" ? "Cuadrícula 1:25 000" : u.nivel === "50K" ? "Hoja 1:50 000" : "Hoja 1:100 000"}${nombre100 ? ` · ${nombre100}` : ""}`,
        accion: () => irAUbicacion(u) });
    }
    const qs = sinTildes(q);
    if (qs.length >= 3) {
      for (const h of hojas100.filter((h) => sinTildes(h.nombre).includes(qs)).slice(0, 4)) {
        const uh = parsearUbicacion(h.codigo);
        if (uh) out.push({ clave: `h:${h.codigo}`, icono: "📍", titulo: `${h.nombre} (${h.codigo})`, sub: "Hoja 1:100 000", accion: () => irAUbicacion(uh) });
      }
      for (const f of formaciones.filter((f) => sinTildes(f.nombre).includes(qs)).slice(0, 4)) {
        out.push({ clave: `f:${f.id}`, icono: "🪨", titulo: f.nombre, sub: `Mostrar solo esto en el mapa · ${f.region}`,
          accion: () => { setSugerir(false); setTexto(f.nombre); elegirFormacion(f); } });
      }
      if (!u) {
        out.push({ clave: "t", icono: "🔎", titulo: `Mostrar en el mapa todo lo que diga «${q}»`,
          sub: "Busca en unidad, litología y descripción de la geología 50K y 100K (sin importar tildes)",
          accion: () => filtrarPorTexto(q) });
      }
    }
    return out;
  }, [texto, hojas100, formaciones]);

  // ---- PRIORIDAD LIBRE (definición del usuario, 24/11/2026): geología silícea de interés (zonas A y B; la C es
  // «verificar») ∩ NDVI bajo ∩ ferruginosa baja ∩ arcilla baja (con SUS cortes, cortes.ts) − áreas
  // protegidas, pintada según el catastro y el suelo:
  // verde libre · azul concesión titulada o en trámite · amarillo chacra, poblado, vía o río · celeste extinguido.
  // Sin Sentinel-2: solo las zonas (sin limpiar). Se compone en el navegador (sin créditos), con caché.
  const [prioLibre, setPrioLibre] = useState<PrioridadLibre | null>(null);
  // % de cada unidad elegida que pasa los filtros calculados DENTRO de ella (siliceLimpiaPorUnidad)
  const [prioUnidades, setPrioUnidades] = useState<Record<string, ResultadoUnidad>>({});
  // capas Anomalías ferruginosas, Arcillas y NDVI SOLO de las unidades elegidas (percentiles dentro de cada una)
  const [capasUnidad, setCapasUnidad] = useState<Record<string, string> | null>(null);
  const cacheCapasUnidad = useRef(new Map<string, { capas: Record<string, string>; unidades: Record<string, ResultadoUnidad> }>());
  const [indicesPorUnidad, setIndicesPorUnidad] = useState<boolean>(() => {
    try { return localStorage.getItem("prospector-rmi:indices-ambito") !== "cuadricula"; } catch { return true; }
  });
  function cambiarAmbito(porUnidad: boolean) {
    setIndicesPorUnidad(porUnidad);
    try { localStorage.setItem("prospector-rmi:indices-ambito", porUnidad ? "unidades" : "cuadricula"); } catch { /* sin almacenamiento */ }
  }
  const [errorPrioLibre, setErrorPrioLibre] = useState<string | null>(null);
  const cachePrioLibre = useRef(new Map<string, PrioridadLibre>());
  const zonasPrio = res && !res.soloSatelite ? res.afloramientos : [];
  // UNIDADES DE LA PRIORIDAD (pedido del usuario, 24/11/2026: «decidir qué formación, formaciones o formación y
  // depósito vamos a usar en prioridad»): por cuadrícula; por defecto, las unidades con alguna zona A o B.
  const [unidadesElegidas, setUnidadesElegidas] = useState<Record<string, string[]>>(() => {
    try { return JSON.parse(localStorage.getItem("prospector-rmi:unidades-prio") || "{}"); } catch { return {}; }
  });
  const unidadesPorDefecto = useMemo(() => [...new Set(zonasPrio.filter((a) => a.clase !== "C").map((a) => a.unidad))], [zonasPrio]);
  const unidadesPrio = useMemo(() => {
    const g = celdaArea ? unidadesElegidas[celdaArea.codigo] : undefined;
    const presentes = new Set(zonasPrio.map((a) => a.unidad));
    return new Set((g ?? unidadesPorDefecto).filter((u) => presentes.has(u)));
  }, [unidadesElegidas, celdaArea, zonasPrio, unidadesPorDefecto]);
  function elegirUnidades(lista: string[] | null) {
    if (!celdaArea) return;
    const cod = celdaArea.codigo;
    setUnidadesElegidas((x) => {
      const n = { ...x };
      if (lista === null) delete n[cod]; else n[cod] = lista;
      try { localStorage.setItem("prospector-rmi:unidades-prio", JSON.stringify(n)); } catch { /* sin almacenamiento */ }
      return n;
    });
  }
  const zonasElegidas = zonasPrio.filter((a) => unidadesPrio.has(a.unidad));
  const clavePrioLibre = res?.libres && celdaArea && zonasElegidas.length
    ? `${celdaArea.codigo}|${res.libres.consultado}|${zonasElegidas.map((a) => a.id + a.clase).join(",")}|`
      + (s2?.disponible ? `${s2.imagen?.fecha_utc ?? s2.periodo ?? ""}|${s2.cortes ? Object.values(s2.cortes).join(",") : ""}` : "sin-s2")
    : null;
  useEffect(() => {
    setErrorPrioLibre(null);
    if (!clavePrioLibre || !celdaArea) { setPrioLibre(null); setPrioUnidades({}); setCapasUnidad(null); return; }
    const enCache = cachePrioLibre.current.get(clavePrioLibre);
    if (enCache) {
      setPrioLibre(enCache);
      const cu = cacheCapasUnidad.current.get(clavePrioLibre);
      setCapasUnidad(cu?.capas ?? null);
      setPrioUnidades(cu?.unidades ?? {});
      return;
    }
    let vigente = true;
    setPrioLibre(null);
    (async () => {
      let bbox: [number, number, number, number] = [celdaArea.oeste, celdaArea.sur, celdaArea.este, celdaArea.norte];
      let url: string | undefined;
      if (s2?.disponible && s2.bbox) {
        // se recalcula en el navegador cuando se puede (así los análisis guardados siguen la regla vigente)
        // POR UNIDAD (24/11/2026): cada formación o depósito elegido se aísla y sus percentiles de NDVI, ferruginosa y
        // arcilla se calculan solo con sus píxeles (cortes.ts siliceLimpiaPorUnidad)
        if (recalculable(s2)) {
          const grupos = [...new Set(zonasElegidas.map((a) => a.unidad))].map((nombre) => ({ nombre, zonas: zonasElegidas.filter((a) => a.unidad === nombre) }));
          const pu = await siliceLimpiaPorUnidad(s2, cortesDe(s2) ?? cortesGuardados(), grupos);
          url = pu.url;
          const porNombre = Object.fromEntries(pu.unidades.map((u) => [u.nombre, u]));
          cacheCapasUnidad.current.set(clavePrioLibre, { capas: pu.capas, unidades: porNombre });
          if (vigente) { setPrioUnidades(porNombre); setCapasUnidad(pu.capas); }
        } else { url = s2.capas?.silice_limpia; if (vigente) setCapasUnidad(null); }
        if (url) bbox = s2.bbox as [number, number, number, number];
      }
      const x = await componerPrioridadSilice(url ?? mascaraZonas(bbox, zonasElegidas), bbox, zonasElegidas, !url, zonasElegidas);
      cachePrioLibre.current.set(clavePrioLibre, x);
      if (vigente) setPrioLibre(x);
    })().catch((e) => { if (vigente) setErrorPrioLibre((e as Error).message); });
    return () => { vigente = false; };
  }, [clavePrioLibre]); // eslint-disable-line react-hooks/exhaustive-deps

  // GEOLOGÍA ELEGIDA ∩ ZONAS LIBRES (pedido del usuario, 24/11/2026: lámina aparte de la Prioridad libre, solo con las
  // unidades elegidas y SIN los filtros satelitales): misma lámina de libres, recortada a las zonas de esas unidades
  const [geoLibre, setGeoLibre] = useState<PrioridadLibre | null>(null);
  const cacheGeoLibre = useRef(new Map<string, PrioridadLibre>());
  const claveGeoLibre = res?.libres && celdaArea && zonasElegidas.length
    ? `${celdaArea.codigo}|${res.libres.consultado}|${zonasElegidas.map((a) => a.id).join(",")}` : null;
  useEffect(() => {
    if (!claveGeoLibre || !celdaArea) { setGeoLibre(null); return; }
    const c = cacheGeoLibre.current.get(claveGeoLibre);
    if (c) { setGeoLibre(c); return; }
    let vigente = true;
    setGeoLibre(null);
    const bbox: [number, number, number, number] = [celdaArea.oeste, celdaArea.sur, celdaArea.este, celdaArea.norte];
    componerPrioridadSilice(mascaraZonas(bbox, zonasElegidas), bbox, zonasElegidas, true, zonasElegidas)
      .then((x) => { cacheGeoLibre.current.set(claveGeoLibre, x); if (vigente) setGeoLibre(x); })
      .catch(() => { /* la lámina queda no disponible */ });
    return () => { vigente = false; };
  }, [claveGeoLibre]); // eslint-disable-line react-hooks/exhaustive-deps
  // ---- transparencia de cada capa satelital (la elige el usuario; se recuerda en el dispositivo)
  const [opac, setOpac] = useState<Partial<Record<IdCapa, number>>>(() => {
    try { return JSON.parse(localStorage.getItem("prospector-rmi:opacidad") || "{}"); } catch { return {}; }
  });
  function cambiarOpac(id: IdCapa, v: number) {
    setOpac((o) => {
      const n = { ...o, [id]: v };
      try { localStorage.setItem("prospector-rmi:opacidad", JSON.stringify(n)); } catch { /* sin almacenamiento */ }
      return n;
    });
  }
  const deslizador = (id: IdCapa) => {
    const v = opac[id] ?? CAPAS_SATELITE[id]?.opacidad ?? GEO_OPACIDAD[id] ?? 1;
    return (
      <label className="opac" onClick={(e) => e.stopPropagation()} title="Opacidad de la capa (a la izquierda = más transparente)">
        <span>Opacidad</span>
        <input type="range" min={0} max={100} step={5} value={Math.round(v * 100)} onChange={(e) => cambiarOpac(id, Number(e.target.value) / 100)} />
        <b>{Math.round(v * 100)} %</b>
      </label>
    );
  };
  // las ha de la Prioridad libre quedan en «Mis cuadrículas» (para ordenarlas por lo que importa)
  useEffect(() => {
    if (!prioLibre || !celdaArea) return;
    const cod = celdaArea.codigo;
    setHistorial((h) => {
      const i = h.findIndex((x) => x.codigo === cod);
      if (i < 0 || (h[i].haLibre === prioLibre.haLibre && h[i].haNeg === prioLibre.haNegociable)) return h;
      const nuevo = [...h];
      nuevo[i] = { ...h[i], haLibre: prioLibre.haLibre, haNeg: prioLibre.haNegociable };
      try { localStorage.setItem(claveHistorial(materiaId), JSON.stringify(nuevo)); } catch { /* sin almacenamiento */ }
      return nuevo;
    });
  }, [prioLibre]); // eslint-disable-line react-hooks/exhaustive-deps
  // lo que ve el mapa: el análisis Sentinel-2 + la Prioridad libre compuesta (sin Sentinel-2: solo ella, en la grilla de la cuadrícula)
  const s2Mapa = useMemo(() => {
    if (!s2?.disponible) {
      return prioLibre
        ? ({ disponible: true, bbox: prioLibre.bbox, capas: { prioridad_libre: prioLibre.url } } as unknown as ResultadoSentinel)
        : s2;
    }
    // ámbito de los índices: solo las unidades elegidas (por defecto) o toda la cuadrícula
    const capasS2 = { ...s2.capas, ...(indicesPorUnidad && capasUnidad ? capasUnidad : {}) };
    return { ...s2, capas: prioLibre ? { ...capasS2, prioridad_libre: prioLibre.url } : capasS2 };
  }, [s2, prioLibre, capasUnidad, indicesPorUnidad]);
  // lo mismo para las láminas (sin la Prioridad libre, que va aparte)
  const s2Laminas = useMemo(() => (s2?.disponible && indicesPorUnidad && capasUnidad
    ? { ...s2, capas: { ...s2.capas, ...capasUnidad } } : s2), [s2, capasUnidad, indicesPorUnidad]);

  const statsPorId = useMemo(() => {
    const o: Record<string, StatSentinel> = {};
    for (const s of s2?.afloramientos ?? []) o[s.id] = s;
    return o;
  }, [s2]);

  // con una formación elegida, solo se ven sus afloramientos (lista y mapa)
  const afloramientosVisibles = useMemo(() => (res?.afloramientos ?? []).filter((a) => {
    if (!formacionSel) return true;
    if (!formacionSel.id.startsWith("texto:")) return (a.formaciones ?? []).includes(formacionSel.id);
    // búsqueda libre: todas las palabras deben aparecer (sin tildes)
    const txt = sinTildes(`${a.unidad} ${a.litologia} ${a.descripcion}`).toUpperCase();
    return (formacionSel.palabras ?? []).every((w) => txt.includes(w));
  }), [res, formacionSel]);

  const vidrioPorId = useMemo(() => Object.fromEntries((res?.afloramientos ?? []).map((a) =>
    [a.id, aptitudVidrio(a.descripcion, a.litologia, a.roca_dominante)])) as Record<string, AptitudVidrio>, [res]);
  const nNoAptas = afloramientosVisibles.filter((a) => vidrioPorId[a.id]?.nivel === "no").length;
  // para el mapa: aptitud de cada zona (resalta las aptas) y la zona elegida en la lista
  const nivelesVidrio = useMemo(() => Object.fromEntries(Object.entries(vidrioPorId).map(([k, v]) => [k, v.nivel])), [vidrioPorId]);
  const [zonaSel, setZonaSel] = useState<string | null>(null);
  // «Unidades en la Prioridad» plegado por defecto (menos carga visual; el resumen se ve en la línea del título)
  const [unidadesAbiertas, setUnidadesAbiertas] = useState(false);
  // barra de herramientas de la derecha: se puede plegar para ver más mapa (se recuerda en el dispositivo)
  // leyenda flotante («qué estás viendo»): en el celular empieza PLEGADA como un botón chico (pedido del usuario,
  // 25/11/2026: «es molestoso, abarca espacio que queremos maximizar»); se recuerda en el dispositivo
  const [leyendaPlegada, setLeyendaPlegada] = useState<boolean>(() => {
    try { const v = localStorage.getItem("prospector-rmi:leyenda-plegada"); return v === null ? tactil : v === "1"; } catch { return tactil; }
  });
  function plegarLeyenda(v: boolean) {
    setLeyendaPlegada(v);
    try { localStorage.setItem("prospector-rmi:leyenda-plegada", v ? "1" : "0"); } catch { /* sin almacenamiento */ }
  }
  // celular: en la barra derecha solo van las herramientas de uso diario; el resto en «Más» (25/11/2026, «más sencillo»)
  const [masAbierto, setMasAbierto] = useState(false);
  // aviso de bienvenida: se puede cerrar y no vuelve a salir
  const [bienvenidaVista, setBienvenidaVista] = useState<boolean>(() => {
    try { return localStorage.getItem("prospector-rmi:bienvenida-vista") === "1"; } catch { return false; }
  });
  const [barraPlegada, setBarraPlegada] = useState<boolean>(() => {
    try { return localStorage.getItem("prospector-rmi:barra-plegada") === "1"; } catch { return false; }
  });
  function plegarBarra(v: boolean) {
    setBarraPlegada(v);
    try { localStorage.setItem("prospector-rmi:barra-plegada", v ? "1" : "0"); } catch { /* sin almacenamiento */ }
  }
  useEffect(() => { setZonaSel(null); }, [res]);

  const afloramientosOrdenados = useMemo(() => {
    const lista = afloramientosVisibles.filter((a) => verNoAptas || vidrioPorId[a.id]?.nivel !== "no");
    if (orden === "vidrio") {
      // aptitud de la descripción (alta → no); a igualdad de nivel, el puntaje y luego las ha libres
      const R = { alta: 0, media: 1, baja: 2, no: 3 };
      const libre = (a: Afloramiento) => prioLibre?.porZona[a.id]?.haLibre ?? 0;
      lista.sort((a, b) => R[vidrioPorId[a.id].nivel] - R[vidrioPorId[b.id].nivel]
        || vidrioPorId[b.id].puntaje - vidrioPorId[a.id].puntaje || libre(b) - libre(a) || b.area_ha - a.area_ha);
    } else if (orden === "distancia") {
      const d = (a: Afloramiento) => distanciaKm(fabrica[0], fabrica[1], a.centro[1], a.centro[0]);
      lista.sort((a, b) => d(a) - d(b));
    } else if (orden === "oportunidad" && prioLibre) {
      // ha libres (verde); a igualdad, en concesión negociable y sobre extinguidos; la C al final
      const v = (a: Afloramiento) => {
        const z = prioLibre.porZona[a.id];
        return z ? z.haLibre + 0.1 * z.haNegociable + 0.01 * z.haExtinguido : -1;
      };
      lista.sort((a, b) => v(b) - v(a) || a.clase.localeCompare(b.clase) || b.area_ha - a.area_ha);
    }
    return lista;
  }, [afloramientosVisibles, orden, fabrica, prioLibre, vidrioPorId, verNoAptas]);

  // ---- áreas protegidas/restringidas: resumen para la cabecera
  const resumenRestr = useMemo(() => {
    const rs = res?.restricciones ?? [];
    if (!rs.length) return null;
    const pctProhibido = rs.filter((r) => r.nivel === "prohibido").reduce((s, r) => s + r.pct_cuadricula, 0);
    const mayor = [...rs].sort((a, b) => b.pct_cuadricula - a.pct_cuadricula)[0];
    return {
      prohibido: pctProhibido >= 0.5,
      texto: `${mayor.nombre.length > 18 ? mayor.nombre.slice(0, 17) + "…" : mayor.nombre} ${mayor.pct_cuadricula < 0.1 ? "<0,1" : mayor.pct_cuadricula} %`
        + (rs.length > 1 ? ` +${rs.length - 1}` : ""),
    };
  }, [res]);

  // ---- bibliografía por cuadrícula (boletines, memorias, mapa oficial), en memoria
  const [biblio, setBiblio] = useState<Record<string, Bibliografia>>({});
  async function obtenerBiblio(c: Celda): Promise<Bibliografia | null> {
    if (biblio[c.codigo]) return biblio[c.codigo];
    try {
      const b = await api.bibliografia(c);
      setBiblio((x) => ({ ...x, [c.codigo]: b }));
      return b;
    } catch (e) {
      setError(`No se pudo consultar la bibliografía: ${(e as Error).message}`);
      return null;
    }
  }
  function cargarBiblio() {
    if (celdaArea) obtenerBiblio(celdaArea);
  }

  // ---- qué se ve: geología (mapas de INGEMMET) y/o capas satelitales, que se SUPERPONEN:
  // varios índices a la vez (casillas) sobre, como máximo, una foto de fondo (natural/SWIR/infrarrojo)
  const hayVista = (id: IdVista, s = s2Mapa) => !!urlSatelite(s?.capas, id);
  const vistasActivas = s2Mapa?.disponible ? VISTAS_S2.filter((v) => capas[v.id] && hayVista(v.id)) : [];
  const geologiaVisible = capas.resultados || capas.geo50_si || capas.geo100_si || capas.geo50 || capas.geo100;
  const sentinelVisible = vistasActivas.length > 0;

  // ---- ayuda: ⓘ por capa + guía completa
  const [ayudaAbierta, setAyudaAbierta] = useState<string | null>(null);
  const [verGuia, setVerGuia] = useState(false);
  const nombreCapa = (id: string) => VISTAS_S2.find((v) => v.id === id)?.nombre ?? CAPAS.find((c) => c.id === id)?.nombre ?? id;
  const botonAyuda = (id: string) => AYUDA_CAPAS[id] && (
    <button className={ayudaAbierta === id ? "info on" : "info"} title="¿Para qué sirve?" aria-expanded={ayudaAbierta === id}
      onClick={() => setAyudaAbierta((a) => (a === id ? null : id))}>ⓘ</button>
  );
  const textoAyuda = (id: string) => {
    const a = AYUDA_CAPAS[id];
    return a && (
      <>
        <p><b>Para qué sirve:</b> {a.para}</p>
        <p><b>Cómo usarla:</b> {a.uso}</p>
        {a.ojo && <p className="ojo"><b>Cuidado:</b> {a.ojo}</p>}
      </>
    );
  };
  const bloqueAyuda = (id: string) => ayudaAbierta === id && <div className="ayuda-capa">{textoAyuda(id)}</div>;

  const explicaVista = (id: IdVista) => VISTAS_S2.find((v) => v.id === id)!.explica;
  // Vista por defecto: la Prioridad libre (hay geología); en «solo satélite», el hierro.
  const vistaPorDefecto = (s?: ResultadoSentinel | null): IdVista => (s?.solo_satelite ? "s2_bsi" : "s2_prioridad_libre");

  /** Deja encendida solo esa vista (o ninguna): para los valores por defecto. */
  const soloVista = (id: IdVista | null) =>
    Object.fromEntries(VISTAS_S2.map((v) => [v.id, v.id === id])) as Record<IdVista, boolean>;

  /** Histograma de hierro/arcillas: «todas» = hierro final + arcillas + Prioridad libre; si no, SOLO esa capa en el mapa. */
  function verCapaCorte(capa: CapaCorte) {
    setCapaCorte(capa);
    // la Prioridad libre queda SIEMPRE encendida mientras se ajusta: se ve cómo cambia con los cortes
    setCapas((x) => (capa === "todas" ? { ...x, ...soloVista("s2_natural"), resultados: false, s2_prioridad_libre: true }
      : { ...x, ...soloVista(capa), s2_prioridad_libre: !s2?.solo_satelite, resultados: false }));
  }
  function abrirCortes(foco: FocoCorte | null) {
    setVerCortes(true); setCortesFoco(foco);
    verCapaCorte(foco === "arcilla" ? "s2_arcillas" : foco === "ferruginosa" ? "s2_ferruginosas" : foco ? `s2_${foco}` : "todas");
  }

  /** Prende/apaga una vista. Los índices se suman; las fotos (grupo «bandas») son opacas,
   *  así que solo puede haber una de fondo a la vez. */
  function alternarVista(id: IdVista) {
    const esFoto = VISTAS_S2.find((v) => v.id === id)?.grupo === "bandas";
    setCapas((c) => {
      const prender = !c[id];
      const fotos = esFoto && prender
        ? Object.fromEntries(VISTAS_S2.filter((v) => v.grupo === "bandas").map((v) => [v.id, false]))
        : {};
      return { ...c, ...fotos, [id]: prender };
    });
  }

  function elegirFondo(id: IdVista | null) {
    setCapas((c) => ({
      ...c, ...Object.fromEntries(VISTAS_S2.filter((v) => v.grupo === "bandas").map((v) => [v.id, v.id === id])),
    }));
  }

  function vistaRapida(modo: "geo" | "s2" | "ambos") {
    const geo = modo !== "s2";
    const sat = modo !== "geo";
    setCapas((c) => ({
      ...c, resultados: geo, geo50: false, geo100: false,
      geo50_si: geo && !formacionSel && res?.escala_usada !== "100K",
      geo100_si: geo && !formacionSel && res?.escala_usada === "100K",
      // satélite: se respeta lo que ya estaba superpuesto; si no había nada, la vista por defecto
      ...(!sat ? soloVista(null) : vistasActivas.length ? {} : soloVista(vistaPorDefecto(s2))),
    }));
    if (sat && !s2?.disponible) {
      setAviso("Aún no hay imagen Sentinel-2: toca una cuadrícula → «Analizar cuadrícula» (geología + Sentinel-2).");
    }
  }

  function mostrarResultado(r: ResultadoBusqueda) {
    setRes(r);
    setFase("resultado");
    setHoja("media");
    setPestana("afloramientos");
    // se ve la geología silícea de la escala usada (no todas las unidades: menos ruido);
    // con una formación elegida en el catálogo se deja solo esa
    setCapas((c) => ({ ...c, resultados: true, geo50: false, geo100: false,
      geo50_si: !formacionSel && r.escala_usada !== "100K", geo100_si: !formacionSel && r.escala_usada === "100K" }));
  }

  async function buscar(areaBusqueda: number[][] | null = area): Promise<ResultadoBusqueda | null> {
    if (!areaBusqueda) return null;
    const m = materiaSel;
    setFase("buscando"); setError(null); setS2(null); setDestino(null);
    try {
      const r = await api.buscar(m.id, areaBusqueda);
      mostrarResultado(r);
      return r;
    } catch (e) {
      setError((e as Error).message);
      setFase("area");
      return null;
    }
  }

  async function correrSentinel(pol: number[][], r: ResultadoBusqueda): Promise<ResultadoSentinel | null> {
    setCargandoS2(true);
    try {
      let s = await api.sentinel(pol, r.afloramientos);
      // los cortes de hierro/arcillas que el usuario eligió la última vez (el servidor usa P50/P50/P90)
      const preferidos = cortesGuardados();
      if (recalculable(s) && !mismosCortes(cortesDe(s), preferidos)) s = await aplicarCortes(s, preferidos).catch(() => s);
      setS2(s);
      // si no había ninguna vista satelital elegida, se muestra la Prioridad libre (o el hierro en «solo satélite»)
      if (s.disponible) {
        setCapas((x) => (VISTAS_S2.some((v) => x[v.id] && v.id !== "s2_prioridad_libre" && hayVista(v.id, s))
          ? x : { ...x, ...soloVista(vistaPorDefecto(s)) }));
      }
      else setAviso(`Sentinel-2 no está activo: ${s.motivo ?? ""}`);
      return s.disponible ? s : null;
    } catch (e) {
      setError(`Geología lista, pero Sentinel-2 falló: ${(e as Error).message}`);
      return null;
    } finally {
      setCargandoS2(false);
    }
  }

  /** Flujo principal: analizar UNA cuadrícula 1:25 000 (geología
   *  y, si `conSentinel`, Sentinel-2). Lo ya analizado se reutiliza de la
   *  memoria: volver a una cuadrícula es instantáneo y no gasta créditos. */
  async function analizarCelda(c: Celda, conSentinel: boolean) {
    const pol = celdaComoPoligono(c);
    setModoS2(conSentinel); setVerCortes(false);
    setCeldaSel(null); setError(null); setDestino(null);
    setArea(pol); setCeldaArea(c);
    setFocoCelda((f) => (f ? c : f));   // con el enfoque puesto, las flechas lo pasan a la vecina
    mapaRef.current?.encuadrar(pol);
    const previo = await obtenerAnalisis(c.codigo);
    // un análisis «solo satélite» no tiene geología: se rehace completo (Sentinel por zonas incluido)
    const completo = previo && !previo.res.soloSatelite ? previo : null;
    let r = completo?.res ?? null;
    let s = completo?.s2 ?? null;
    if (r) {
      mostrarResultado(r);
      setS2(s);
    } else {
      r = await buscar(pol);
      if (!r) return;
    }
    if (conSentinel && !s) s = await correrSentinel(pol, r);
    registrarCelda(c, r, s);
    // concesiones y áreas protegidas cambian con el tiempo: lo guardado hace más de una semana se
    // vuelve a consultar en segundo plano (no gasta créditos de Copernicus)
    if (completo && libresViejos(r)) refrescarLibres(c);
  }

  const libresViejos = (r: ResultadoBusqueda) => {
    const t = r.libres?.consultado ? Date.parse(r.libres.consultado) : NaN;
    return !(t > Date.now() - DIAS_LIBRES * 86400000);
  };

  /** Vuelve a consultar en vivo concesiones, áreas protegidas y % libre (cuadrícula y zonas)
   *  y lo guarda en el análisis de esa cuadrícula. */
  async function refrescarLibres(c: Celda) {
    setActualizandoLibres(c.codigo);
    try {
      const antes = cacheCeldas.current.get(c.codigo);
      const zonas = (antes?.res.afloramientos ?? []).map((a) => ({
        id: a.id, geometria: a.geometria, clase: a.clase, unidad: a.unidad, litologia: a.litologia || a.descripcion }));
      const x = await api.libres(celdaComoPoligono(c), zonas);
      const act = cacheCeldas.current.get(c.codigo);   // lo más reciente (Sentinel pudo terminar mientras tanto)
      if (!act) return;
      const nuevo: ResultadoBusqueda = {
        ...act.res, restricciones: x.restricciones, libres: x.libres,
        afloramientos: act.res.afloramientos.map((a) => x.zonas[a.id]
          ? { ...a, libre_pct: x.zonas[a.id].libre_pct, util_pct: x.zonas[a.id].util_pct, negociable_pct: x.zonas[a.id].negociable_pct ?? null,
              concesiones: x.zonas[a.id].concesiones, restriccion: x.zonas[a.id].restriccion } : a),
      };
      setRes((r) => (r === act.res || r === antes?.res ? nuevo : r));
      if (nuevo.soloSatelite) recordar(c.codigo, nuevo, act.s2);
      else registrarCelda(c, nuevo, act.s2);
    } catch (e) {
      setAviso(`No se pudo actualizar las áreas libres: ${(e as Error).message}`);
    } finally {
      setActualizandoLibres(null);
    }
  }

  /** Solo satélite: Sentinel-2 + ASTER (QICIMI de INGEMMET) de toda la cuadrícula, SIN consultar
   *  la geología. Útil para mirar rápido una cuadrícula o donde GEOCATMIN está lento. */
  async function analizarSoloSatelite(c: Celda) {
    const pol = celdaComoPoligono(c);
    setCeldaSel(null); setError(null); setDestino(null);
    setArea(pol); setCeldaArea(c);
    mapaRef.current?.encuadrar(pol);
    const previo = await obtenerAnalisis(c.codigo);
    const ancho = distanciaKm(c.sur, c.oeste, c.sur, c.este), alto = distanciaKm(c.sur, c.oeste, c.norte, c.oeste);
    const vacio: ResultadoBusqueda = previo?.res ?? {
      material: "arena_silicea", material_nombre: "Arena silícea", area_km2: Math.round(ancho * alto * 100) / 100,
      centro: [(c.oeste + c.este) / 2, (c.norte + c.sur) / 2], rmi: [], escala_usada: null,
      motivo_escala: "Solo satélite: no se consultó la geología de INGEMMET (sin zonas A/B/C).",
      cobertura_50k: false, afloramientos: [],
      resumen: { rmi: 0, clase_A: 0, clase_B: 0, clase_C: 0, ha_favorables: 0 },
      avisos: [], segundos: 0, fuente: "Copernicus Sentinel-2", soloSatelite: true,
    };
    mostrarResultado(vacio);
    setPestana("sentinel");
    // sin geología no hay /buscar: áreas protegidas/restringidas y áreas libres se consultan aparte, en paralelo
    const pRestr = vacio.soloSatelite && (vacio.libres === undefined || libresViejos(vacio))
      ? api.libres(pol)
        .then((x) => {
          vacio.restricciones = x.restricciones; vacio.libres = x.libres;
          setRes((r) => (r?.soloSatelite ? { ...vacio } : r));
          if (previo?.s2) recordar(c.codigo, { ...vacio }, previo.s2);
        })
        .catch(() => { vacio.restricciones = vacio.restricciones ?? null; })
      : Promise.resolve();
    if (previo?.s2) {
      setS2(previo.s2);
    } else {
      setS2(null);
      const s = await correrSentinel(pol, vacio);
      if (!s) return;
      await pRestr;
      if (vacio.soloSatelite) recordar(c.codigo, vacio, s);
      else registrarCelda(c, vacio, s); // ya tenía geología: queda como análisis completo
    }
    // se ve el satélite limpio, sin los colores de la geología
    setCapas((x) => ({ ...x, resultados: !vacio.soloSatelite, geo50_si: false, geo100_si: false, geo50: false, geo100: false,
      ...soloVista(vistaPorDefecto(cacheCeldas.current.get(c.codigo)?.s2)) }));
  }

  /** Reemplaza la imagen guardada por una toma nueva (gasta créditos de Copernicus). */
  async function nuevaToma() {
    if (!celdaArea || !res) return;
    const c = celdaArea;
    setS2(null); setVerCortes(false);
    const s = await correrSentinel(celdaComoPoligono(c), res);
    if (!s) return;
    if (res.soloSatelite) recordar(c.codigo, res, s);
    else registrarCelda(c, res, s);
  }

  function irAVecina(rumbo: Rumbo) {
    if (!celdaArea) return;
    const v = vecina(celdaArea, rumbo);
    if (!v) return setAviso("Hacia ese lado solo hay mar o ya no es Perú.");
    analizarCelda(v, modoS2);
  }

  function miUbicacion() {
    if (!navigator.geolocation) return setAviso("Tu dispositivo no da la ubicación.");
    navigator.geolocation.getCurrentPosition(
      (p) => {
        setUbicacion([p.coords.latitude, p.coords.longitude]);
        mapaRef.current?.irAPunto(p.coords.latitude, p.coords.longitude, 13);
      },
      () => setAviso("No se pudo obtener tu ubicación (revisa el permiso de GPS)."),
      { enableHighAccuracy: true, timeout: 15000 },
    );
  }

  function irA(a: Afloramiento) {
    setZonaSel(a.id);
    setHoja("cerrada");
    setDestino({ lat: a.centro[1], lon: a.centro[0] });
    mapaRef.current?.irA(a);
  }

  function clicMapa(lat: number, lng: number, sobreResultado: boolean) {
    if (!sobreResultado) setZonaSel(null);   // clic fuera de las zonas: se suelta la zona elegida
    if (verPetitorio && pet.eligiendo && pet.activo) { pet.alternarCuadricula(cuadricula100En(lat, lng)); return; }
    if (modoRuta) {
      setModoRuta(false);
      calcularRuta(lat, lng);
      return;
    }
    if (sobreResultado || !capas.cuadricula) return;
    const c = celdaEn(lat, lng, "25K");
    if (!tieneTierra(c)) {
      setCeldaSel(null);
      return;
    }
    setResaltado(null);
    setCeldaSel((actual) => (actual?.codigo === c.codigo ? null : c));
  }

  /** Clic derecho / 1 toque: ver solo la cuadrícula tocada (y abrir su tarjeta). */
  function enfocarEn(lat: number, lng: number, sobreResultado: boolean) {
    if (verPetitorio && pet.eligiendo && pet.activo) { if (tactil) pet.alternarCuadricula(cuadricula100En(lat, lng)); return; }
    if (modoRuta) {   // en el celular el toque simple llega aquí
      setModoRuta(false);
      calcularRuta(lat, lng);
      return;
    }
    if (!capas.cuadricula) return;
    const c = celdaEn(lat, lng, "25K");
    if (!tieneTierra(c)) return;
    setFocoCelda(c);
    if (sobreResultado) return;   // tocó una zona o muestra: se abre su ficha, sin tarjeta encima
    setResaltado(null);
    mapaRef.current?.encuadrar(celdaComoPoligono(c));
    // si es la cuadrícula ya analizada, sus resultados siguen abiertos: no hace falta la tarjeta
    setCeldaSel(celdaArea?.codigo === c.codigo && res ? null : c);
  }


  // ruta del destino actual (la que se dibuja y se muestra en el panel)
  const rutaEstado = destino ? rutas[claveRuta(destino.lat, destino.lon)] : undefined;
  const rutaDestino = rutaEstado && rutaEstado !== "cargando" && !("error" in rutaEstado) && "bloques" in rutaEstado ? rutaEstado : null;

  const foco = focoCelda;

  return (
    <div className={res ? "app con-hoja" : "app"}>
      <Mapa
        ref={mapaRef}
        sqlInteres={{ sql50: materiaSel.sql50, sql100: materiaSel.sql100 }}
        onCursor={(la, lo) => setCursor([la, lo])}
        petitorio={petitorioMapa}
        area={area}
        afloramientos={afloramientosVisibles}
        sentinel={s2Mapa}
        opacidades={opac}
        statsPorId={statsPorId}
        vidrio={esSilice ? nivelesVidrio : undefined}
        zonaSel={zonaSel}
        zonasSoloBorde={vistasActivas.some((v) => v.id === "s2_ndvi" || v.id === "s2_bsi" || v.id === "s2_ferruginosas" || v.id === "s2_arcillas")}
        capas={capas}
        base={base}
        ubicacion={ubicacion}
        formacion={formacionSel}
        fabrica={fabrica}
        celdaSel={celdaSel}
        foco={foco}
        resaltado={resaltado}
        analizadas={marcasAnalizadas}
        destino={destino}
        ruta={rutaDestino}
        barrido={verRanking ? rankingMapa : verSuper ? superMapa : verBarrido ? barridoMapa : undefined}
        curvas={curvas && curvas !== "cargando" && curvasDe === celdaArea?.codigo ? curvas : null}
        onClickMapa={clicMapa}
        onEnfocar={enfocarEn}
        onVerTodo={() => { if (!modoRuta) setFocoCelda(null); }}
      />

      {foco && !celdaSel && !sugerir && (
        <div className="banda-foco">
          <span><Scan size={14} /> Viendo solo <b>{foco.codigo}</b> <small>· {tactil ? "2 toques" : "clic izquierdo"} = ver todo</small></span>
          <button onClick={() => setFocoCelda(null)}>Ver todo</button>
        </div>
      )}

      {/* ---------- cuadrícula 1:25 000 seleccionada ---------- */}
      {celdaSel && (
        <div className="tarjeta-celda">
          <button className="cerrar" aria-label="Cerrar" onClick={() => setCeldaSel(null)}><X size={16} /></button>
          <div className="eti">Cuadrícula 1:25 000</div>
          <div className="cod">{celdaSel.codigo}</div>
          <dl className="datos-celda">
            <div><dt>Hojas</dt><dd>50K {celdaSel.codigo.split("-")[0]} · 100K {celdaSel.hoja100}</dd></div>
            <div><dt>Latitud</dt><dd>{gms(celdaSel.norte, true)} – {gms(celdaSel.sur, true)}</dd></div>
            <div><dt>Longitud</dt><dd>{gms(celdaSel.oeste, false)} – {gms(celdaSel.este, false)}</dd></div>
            <div><dt>Fábrica</dt><dd>{formatoKm(km((celdaSel.norte + celdaSel.sur) / 2, (celdaSel.oeste + celdaSel.este) / 2))} en línea recta
              <span className="sep" />{botonRuta((celdaSel.norte + celdaSel.sur) / 2, (celdaSel.oeste + celdaSel.este) / 2)}</dd></div>
          </dl>
          {historialPorCodigo.get(celdaSel.codigo) && (() => {
            const h = historialPorCodigo.get(celdaSel.codigo)!;
            return (
              <div className="ya-analizada">
                <Check size={13} /> Ya analizada · {etiquetaResumen(h)}
                {h.haLibre != null && <> · <b>{Math.round(h.haLibre).toLocaleString("es-PE")} ha libres</b></>}
              </div>
            );
          })()}
          <div className="botones">
            <button className="primario" disabled={fase === "buscando" || cargandoS2} onClick={() => analizarCelda(celdaSel, true)}>
              {guardados.has(celdaSel.codigo) ? "Ver análisis guardado" : "Analizar cuadrícula"}
              <small>{guardados.has(celdaSel.codigo) ? "al instante, sin créditos" : "geología + Sentinel-2"}</small>
            </button>
            <button disabled={fase === "buscando" || cargandoS2} onClick={() => analizarCelda(celdaSel, false)}>
              Solo geología <small>sin créditos</small>
            </button>
            <button disabled={fase === "buscando" || cargandoS2} onClick={() => analizarSoloSatelite(celdaSel)}>
              Solo satélite <small>sin geología</small>
            </button>
          </div>
          <div className="acciones-celda">
            <button className="enlace" onClick={() => setFocoCelda(focoCelda?.codigo === celdaSel.codigo ? null : celdaSel)}
              title={tactil ? "1 toque en una cuadrícula = ver solo ella; 2 toques = ver todo" : "Clic derecho = ver solo esa cuadrícula; clic izquierdo = ver todo"}>
              <Scan size={13} /> {focoCelda?.codigo === celdaSel.codigo ? "Ver todo el mapa" : "Ver solo esta"}
            </button>
            <button className="enlace guardar" onClick={() => setGuardando(celdaSel)}>
              <Star size={13} /> {carpetasDe(celdaSel.codigo).length ? `En: ${carpetasDe(celdaSel.codigo).map((k) => k.nombre).join(", ")}` : "Guardar en carpeta"}
            </button>
          </div>
        </div>
      )}

      {/* ---------- ¿descargar el mapa geológico de la cuadrícula guardada? ---------- */}
      {ofertaMapa && !guardando && (() => {
        const previo = cacheCeldas.current.get(ofertaMapa.celda.codigo)?.res;
        const recomendada: "50K" | "100K" = previo?.escala_usada === "100K" || previo?.cobertura_50k === false ? "100K" : "50K";
        const carpeta = carpetas.find((k) => k.id === ofertaMapa.carpetaId);
        return (
          <div className="fondo-modal" onClick={() => !generandoMapa && setOfertaMapa(null)}>
            <div className="modal" onClick={(e) => e.stopPropagation()}>
              <div className="titulo">🗺 ¿Guardar también el mapa geológico? <button disabled={generandoMapa} onClick={() => setOfertaMapa(null)}>×</button></div>
              <p className="nota">
                Arma una lámina (imagen PNG) de <b>{ofertaMapa.celda.codigo}</b> con la geología de INGEMMET, su leyenda
                (unidades presentes, ordenadas por área), áreas protegidas, escala, norte y coordenadas, y la guarda en
                {carpeta ? <> «<b>{carpeta.nombre}</b>»</> : " la carpeta"} (📎 adjuntos{disp.estado === "listo" ? " y en tu dispositivo" : ""}).
              </p>
              <div className="botones-celda">
                {(["50K", "100K"] as const).map((e) => (
                  <button key={e} className={e === recomendada ? "primario" : ""} disabled={generandoMapa}
                    onClick={() => generarMapa(ofertaMapa.carpetaId, ofertaMapa.celda, e)}>
                    {e === "50K" ? "1:50 000" : "1:100 000"}{e === recomendada ? " (recomendado)" : ""}
                  </button>
                ))}
                <button disabled={generandoMapa} onClick={() => setOfertaMapa(null)}>Ahora no</button>
              </div>
              {generandoMapa && <p className="nota">⏳ Pidiendo la geología a GEOCATMIN y armando la lámina (10–30 s)…</p>}
              <small className="explica">También puedes hacerlo después desde 📚 → ★ Carpetas → «🗺 Mapa geológico».</small>
            </div>
          </div>
        );
      })()}

      {/* ---------- guía: para qué sirve cada capa ---------- */}
      {verGuia && (
        <div className="fondo-modal" onClick={() => setVerGuia(false)}>
          <div className="modal guia-capas" onClick={(e) => e.stopPropagation()}>
            <div className="titulo">📖 Para qué sirve cada capa <button onClick={() => setVerGuia(false)}>×</button></div>
            <p className="nota">
              Ordenadas según el trabajo de prospección. <b>Geología</b> = lo que dibujó INGEMMET (qué roca hay).
              <b>Satélite</b> = lo que se ve desde el espacio (vegetación, suelo desnudo, hierro y arcillas).
              Ninguna mide SiO₂: eso solo lo da el laboratorio.
            </p>
            {GUIA_PASOS.map((paso) => (
              <section key={paso.titulo}>
                <h3>{paso.titulo}</h3>
                {paso.ids.map((id) => (
                  <div key={id} className="entrada-guia">
                    <b>{nombreCapa(id)}</b>
                    {textoAyuda(id)}
                  </div>
                ))}
              </section>
            ))}
          </div>
        </div>
      )}

      {/* ---------- visor de adjuntos (fotos y PDF) ---------- */}
      {visor && (
        <div className="fondo-modal" onClick={cerrarVisor}>
          <div className="modal visor" onClick={(e) => e.stopPropagation()}>
            <div className="titulo"><span>{visor.nombre}</span> <button onClick={cerrarVisor}>×</button></div>
            {visor.tipo.startsWith("image/") ? <img src={visor.url} alt={visor.nombre} />
              : visor.tipo === "application/pdf" ? <iframe src={visor.url} title={visor.nombre} />
                : <p className="nota">Este tipo de archivo no se puede mostrar aquí.</p>}
            <a className="boton-enlace" href={visor.url} download={visor.nombre}>⬇ Descargar / abrir con otra app</a>
          </div>
        </div>
      )}

      {/* ---------- selector «Guardar en carpeta» ---------- */}
      {guardando && (
        <div className="fondo-modal" onClick={() => setGuardando(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="titulo">★ Guardar {guardando.codigo} en… <button onClick={() => setGuardando(null)}>×</button></div>
            {!carpetas.length && <p className="nota">Aún no tienes carpetas. Crea la primera:</p>}
            {carpetas.map((k) => {
              const dentro = k.celdas.some((g) => g.codigo === guardando.codigo);
              return (
                <label key={k.id} className="opcion-carpeta">
                  <input type="checkbox" checked={dentro} onChange={() => alternarEnCarpeta(k.id, guardando)} />
                  <span><b>{k.nombre}</b> <small>{k.celdas.length} cuadrícula(s)</small></span>
                </label>
              );
            })}
            <form className="nueva-carpeta" onSubmit={(e) => { e.preventDefault(); crearCarpeta(nombreNueva, guardando); }}>
              <input value={nombreNueva} onChange={(e) => setNombreNueva(e.target.value)}
                placeholder="Nueva carpeta (ej. Marcavilca – Cañete)" maxLength={60} />
              <button className="primario" type="submit">Crear y guardar</button>
            </form>
            {!datosActuales(guardando.codigo) && (
              <p className="nota">Esta cuadrícula aún no está analizada: se guarda vacía y se llena sola cuando la analices.</p>
            )}
            <button className="ancho" onClick={() => setGuardando(null)}>Listo</button>
          </div>
        </div>
      )}

      {/* ---------- formación elegida en el catálogo ---------- */}
      {formacionSel && !celdaSel && (
        <div className="franja-formacion">
          <span>Mostrando solo: <b>{formacionSel.nombre}</b></span>
          <button onClick={() => { setPestanaCat("formaciones"); setVerCatalogo(true); }}>Dónde aparece</button>
          <button onClick={() => elegirFormacion(null)}>Quitar</button>
        </div>
      )}

      {/* ---------- catálogo: carpetas y formaciones ---------- */}
      {verCatalogo && (
        <div className="panel-catalogo">
          <div className="titulo">
            Explorar arena silícea <button onClick={() => setVerCatalogo(false)}>×</button>
          </div>
          <div className="pestanas">
            <button className={pestanaCat === "carpetas" ? "on" : ""} onClick={() => setPestanaCat("carpetas")}>
              ★ Carpetas ({carpetas.length})
            </button>
            <button className={pestanaCat === "mias" ? "on" : ""} onClick={() => setPestanaCat("mias")}>
              Analizadas ({historial.length})
            </button>
            <button className={pestanaCat === "formaciones" ? "on" : ""} onClick={() => setPestanaCat("formaciones")}>
              Formaciones
            </button>
          </div>
          <div className="contenido-cat">
            {pestanaCat === "carpetas" && (
              <>
                <p className="nota">
                  Guarda aquí tus cuadrículas de interés: cada una recopila sus zonas favorables, derechos mineros, imágenes
                  satelitales y tus notas de campo.
                </p>
                <div className={`dispositivo ${disp.estado}`}>
                  {plat === "ninguna" ? (
                    <>
                      <b>📁 Carpetas en este dispositivo: no disponible aquí</b>
                      <small>
                        Este navegador no permite crear carpetas. En el <b>celular</b>, instala la app (APK) y se crearán en
                        Documentos/Prospector RMI. En la <b>laptop</b>, abre la app con Chrome o Edge.
                        Mientras tanto, usa «⬇ Descargar Excel» en cada carpeta.
                      </small>
                    </>
                  ) : disp.estado === "listo" ? (
                    <>
                      <b>✅ Guardando también en: {disp.donde}</b>
                      <small>
                        Cada carpeta de la app es una carpeta real con «Resumen (Excel).csv», «carpeta.json» y una subcarpeta por
                        cuadrícula (ficha.txt + imágenes satelitales). Se actualiza sola. Puedes poner tus fotos de campo
                        ahí: la app nunca borra nada.
                      </small>
                      {disp.hora && <small>Última copia: {disp.hora}</small>}
                      {plat === "laptop" && (
                        <div className="botones-celda">
                          <button onClick={() => sincronizarAhora()}>↻ Guardar ahora</button>
                          <button onClick={() => conectarLaptop(true)}>Cambiar ubicación</button>
                          <button onClick={desconectarLaptop}>Dejar de guardar aquí</button>
                        </div>
                      )}
                    </>
                  ) : disp.estado === "pedir" ? (
                    <>
                      <b>📁 Falta tu permiso para seguir guardando en «{disp.donde}»</b>
                      <small>Por seguridad, el navegador lo pide de nuevo cada vez que abres la app. {disp.msg ?? ""}</small>
                      <button className="primario" onClick={() => conectarLaptop()}>Dar permiso y guardar</button>
                    </>
                  ) : disp.estado === "error" ? (
                    <>
                      <b>⚠ No se pudo guardar en el dispositivo</b>
                      <small>{disp.msg}</small>
                      {plat === "laptop" && <button onClick={() => conectarLaptop(true)}>Elegir otra ubicación</button>}
                    </>
                  ) : plat === "laptop" ? (
                    <>
                      <b>📁 Crear las carpetas también en esta laptop</b>
                      <small>
                        Elige dónde (por ejemplo <b>Documentos</b>): se creará la carpeta «Prospector RMI» y dentro, una carpeta
                        por cada carpeta de la app, que se actualiza sola.
                      </small>
                      <button className="primario" onClick={() => conectarLaptop()}>Elegir ubicación en la laptop</button>
                    </>
                  ) : (
                    <small>Preparando Documentos/Prospector RMI en este celular…</small>
                  )}
                </div>
                <form className="nueva-carpeta" onSubmit={(e) => { e.preventDefault(); setCarpetaAbierta(crearCarpeta(nombreNueva)); }}>
                  <input value={nombreNueva} onChange={(e) => setNombreNueva(e.target.value)}
                    placeholder="Nombre de la carpeta nueva" maxLength={60} />
                  <button className="primario" type="submit">Crear</button>
                </form>
                {!carpetas.length && (
                  <p className="vacio">Aún no hay carpetas. También puedes crearlas desde una cuadrícula con «★ Guardar en carpeta».</p>
                )}
                {carpetas.map((k) => {
                  const abierta = carpetaAbierta === k.id;
                  const zonas = k.celdas.flatMap((g) => g.datos?.zonas ?? []);
                  return (
                    <div key={k.id} className={`carpeta ${abierta ? "abierta" : ""}`}>
                      <div className="cab" onClick={() => setCarpetaAbierta(abierta ? null : k.id)}>
                        <span className="icono">{abierta ? "📂" : "📁"}</span>
                        <div className="cuerpo">
                          <b>{k.nombre}</b>
                          <div className="meta">
                            {k.celdas.length} cuadrícula(s) · {zonas.filter((z) => z.clase === "A").length} zonas A · {zonas.filter((z) => z.clase === "B").length} zonas B
                            {(() => {
                              const n = (k.adjuntos?.length ?? 0) + k.celdas.reduce((s, g) => s + (g.adjuntos?.length ?? 0), 0);
                              return n ? ` · 📎 ${n}` : "";
                            })()}
                          </div>
                        </div>
                      </div>
                      {abierta && (
                        <div className="interior">
                          <div className="acciones-carpeta">
                            <button disabled={!k.celdas.length} onClick={() => descargar(`${k.nombre.replace(/[\\/:*?"<>|]+/g, "-").replace(/\s+/g, " ").trim() || "carpeta"}.csv`, csvCarpeta(k, fabrica))}>
                              ⬇ Descargar Excel
                            </button>
                            <button onClick={() => { const n = prompt("Nuevo nombre de la carpeta:", k.nombre); if (n) renombrarCarpeta(k.id, n); }}>✎ Renombrar</button>
                            <button onClick={() => { if (confirm(`¿Borrar la carpeta «${k.nombre}»? (las cuadrículas no se borran del mapa)`)) borrarCarpeta(k.id); }}>🗑 Borrar</button>
                          </div>
                          <div className="generales">
                            <small>📂 Documentos generales de la carpeta (boletines, informes, contratos…)</small>
                            {listaAdjuntos(k, null, k.adjuntos)}
                          </div>
                          {!k.celdas.length && <p className="vacio">Vacía. Toca una cuadrícula del mapa → «★ Guardar en carpeta».</p>}
                          {k.celdas.map((g) => {
                            const c = celda25(g.codigo);
                            const d = g.datos;
                            const cuenta = (cl: string) => d?.zonas.filter((z) => z.clase === cl).length ?? 0;
                            return (
                              <div key={g.codigo} className="celda-guardada">
                                <div className="fila">
                                  <b>{g.codigo}</b>
                                  {c && <span className="km">{formatoKm(km((c.norte + c.sur) / 2, (c.oeste + c.este) / 2))}</span>}
                                </div>
                                <div className="meta">
                                  {!d ? "Sin analizar todavía"
                                    : `A${cuenta("A")} B${cuenta("B")} C${cuenta("C")}`
                                      + (d.sentinel ? "" : " · sin Sentinel-2")
                                      + (d.libres?.util_pct != null ? ` · ${d.libres.util_pct} % utilizable` : "")}
                                </div>
                                {d && d.zonas.filter((z) => z.clase !== "C").slice(0, 4).map((z, i) => (
                                  <div key={i} className="meta">
                                    <span className="btn-libres" style={{ background: COLOR_CLASE[z.clase as "A" | "B" | "C"] }}>{z.clase}</span>
                                    {z.unidad} · {z.area_ha} ha{z.limpia != null ? ` · ${z.limpia} % limpia` : ""}
                                  </div>
                                ))}
                                <textarea
                                  defaultValue={g.nota}
                                  placeholder="Notas: acceso, propietario, observaciones de campo, muestras tomadas…"
                                  onBlur={(e) => { if (e.target.value !== g.nota) notaDeCelda(k.id, g.codigo, e.target.value); }}
                                />
                                {d?.restricciones && d.restricciones.length > 0 && (
                                  <div className={`restr-zona ${d.restricciones.some((r) => r.nivel === "prohibido" && r.pct >= 0.5) ? "prohibido" : "restringido"}`}>
                                    {d.restricciones.slice(0, 2).map((r) => `${r.nivel === "prohibido" ? "⛔" : "⚠"} ${r.nombre} ${r.pct} %`).join(" · ")}
                                    {d.restricciones.length > 2 ? ` · +${d.restricciones.length - 2}` : ""}
                                  </div>
                                )}
                                {g.biblio && g.biblio.boletines.length > 0 && (
                                  <div className="meta">
                                    📘 {g.biblio.boletines.slice(0, 2).map((b, i) => (
                                      <a key={i} href={b.url} target="_blank" rel="noopener noreferrer">{b.cita}</a>
                                    )).reduce<ReactNode[]>((acc, el, i) => (i ? [...acc, " · ", el] : [el]), [])}
                                    {g.biblio.memorias.length ? ` · ${g.biblio.memorias.length} memoria(s)` : ""}
                                  </div>
                                )}
                                {listaAdjuntos(k, g.codigo, g.adjuntos)}
                                <div className="botones-celda">
                                  <button className="primario" disabled={!c || fase === "buscando" || cargandoS2}
                                    onClick={() => { if (c) { setVerCatalogo(false); analizarCelda(c, d ? !!d.sentinel : modoS2); } }}>
                                    {d ? "Abrir" : "Analizar"}
                                  </button>
                                  <button disabled={!c} onClick={() => c && setOfertaMapa({ carpetaId: k.id, celda: c })}>🗺 Mapa geológico</button>
                                  <button onClick={() => quitarDeCarpeta(k.id, g.codigo)}>Quitar</button>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })}
              </>
            )}
            {pestanaCat === "mias" && (
              <>
                <p className="nota">
                  Cuadrículas que ya analizaste, de la mejor a la peor: más hectáreas de Prioridad libre (verde), luego más zonas A y B.
                  En el mapa quedan marcadas con ✓. Las que dicen <b>💾 guardado</b> se abren al instante y sin gastar créditos,
                  aunque cierres la app.
                </p>
                {guardados.size > 0 && (
                  <div className="guardado-s2">
                    <span>💾 {guardados.size} análisis guardado(s) en este dispositivo{espacioMB != null ? ` · la app usa ~${espacioMB} MB` : ""}.</span>
                    <div className="botones-celda">
                      <button onClick={() => {
                        if (confirm(`¿Borrar los ${guardados.size} análisis guardados (imágenes satelitales incluidas)? El historial y las carpetas se conservan.`)) {
                          [...guardados].forEach((c) => { olvidarAnalisis(c); });
                        }
                      }}>🗑 Borrar todos los análisis guardados</button>
                    </div>
                  </div>
                )}
                {!historial.length && <p className="vacio">Aún no analizas ninguna. Toca una cuadrícula del mapa.</p>}
                {[...historial]
                  .sort((a, b) => ((b.haLibre ?? -1) - (a.haLibre ?? -1)) || (b.A - a.A) || (b.B - a.B) || ((b.haAB ?? 0) - (a.haAB ?? 0)))
                  .map((h) => {
                    const c = celda25(h.codigo);
                    const mejor = h.A ? "A" : h.B ? "B" : h.C ? "C" : null;
                    return (
                      <div key={h.codigo} className="item" onClick={() => { if (c) { setVerCatalogo(false); analizarCelda(c, h.sentinel); } }}>
                        <span className="badge" style={{ background: mejor ? COLOR_CLASE[mejor] : "#94a3b8" }}>{mejor ?? "–"}</span>
                        <div className="cuerpo">
                          <b>{h.codigo}</b> <small>{etiquetaResumen(h)}</small>
                          {c && <span className="km">{formatoKm(km((c.norte + c.sur) / 2, (c.oeste + c.este) / 2))}</span>}
                          <div className="meta">
                            {h.haLibre != null ? `⭐ ${Math.round(h.haLibre).toLocaleString("es-PE")} ha libres · ${Math.round(h.haNeg ?? 0).toLocaleString("es-PE")} ha en concesión` : "Prioridad libre: abre la cuadrícula para calcularla"}
                            {h.sentinel ? " · con Sentinel-2" : " · sin Sentinel-2 (sin descontar hierro ni arcilla)"}
                          </div>
                          {guardados.has(h.codigo) && (
                            <div className="meta">
                              <span className="chip-dato ok">💾 guardado</span>{" "}
                              <button className="enlace" onClick={(e) => {
                                e.stopPropagation();
                                if (confirm(`¿Borrar el análisis guardado de ${h.codigo}?`)) olvidarAnalisis(h.codigo);
                              }}>borrar</button>
                            </div>
                          )}
                          {h.formaciones.length > 0 && (
                            <div className="meta">{h.formaciones.map((id) => formaciones.find((f) => f.id === id)?.nombre ?? id).join(" · ")}</div>
                          )}
                          <div className="meta">{new Date(h.fecha).toLocaleString("es-PE", { dateStyle: "short", timeStyle: "short" })}</div>
                        </div>
                      </div>
                    );
                  })}
                {historial.length > 0 && (
                  <button className="enlace" onClick={() => { if (confirm("¿Borrar el historial de cuadrículas analizadas?")) borrarHistorial(); }}>
                    Borrar historial
                  </button>
                )}
              </>
            )}
            {pestanaCat === "formaciones" && (
              <>
                <p className="nota">
                  Elige una: el mapa muestra <b>solo sus afloramientos</b> en todo el Perú (geología 1:50 000 de INGEMMET)
                  y, si ya buscaste, la lista de resultados se filtra a ella.
                </p>
                {formacionSel?.id.startsWith("texto:") && (
                  <div className="item formacion on">
                    <span className="check">✓</span>
                    <div className="cuerpo">
                      <b>Búsqueda: {formacionSel.nombre}</b>
                      <div className="lito">{formacionSel.descripcion}</div>
                      {formacionSel.nota && <div className="meta alerta">{formacionSel.nota}</div>}
                      <div className="hojas">
                        {cargandoHojas && <span className="meta">Buscando dónde aparece…</span>}
                        {hojasForm && (
                          <>
                            <div className="meta">Aparece en <b>{hojasForm.length}</b> hojas 1:50 000 · de la más cercana a la fábrica:</div>
                            <div className="chips">
                              {hojasOrdenadas.slice(0, 40).map((h) => (
                                <button key={h.hoja} onClick={() => irAHoja(h.hoja)} title={`${h.poligonos} polígonos`}>
                                  {h.celda?.codigo ?? h.hoja} <small>{formatoKm(h.km)}</small>
                                </button>
                              ))}
                            </div>
                          </>
                        )}
                        <button className="enlace" onClick={() => elegirFormacion(null)}>Quitar búsqueda</button>
                      </div>
                    </div>
                  </div>
                )}
                {!formaciones.length && <p className="vacio">Cargando catálogo…</p>}
                {TIPOS_FORMACION.map(({ tipo, titulo }) => (
                  <div key={titulo}>
                    <div className="grupo">{titulo}</div>
                    {formaciones.filter((f) => tipo.includes(f.tipo)).map((f) => {
                      const on = formacionSel?.id === f.id;
                      return (
                        <div key={f.id} className={`item formacion ${on ? "on" : ""}`} onClick={() => elegirFormacion(on ? null : f)}>
                          <span className="check">{on ? "✓" : ""}</span>
                          <div className="cuerpo">
                            <b>{f.nombre}</b>
                            <div className="meta">{[f.edad, f.region].filter(Boolean).join(" · ")}</div>
                            <div className="lito">{f.descripcion}</div>
                            {on && (
                              <div className="hojas" onClick={(e) => e.stopPropagation()}>
                                {cargandoHojas && <span className="meta">Buscando dónde aparece…</span>}
                                {hojasForm && (
                                  <>
                                    <div className="meta">
                                      Aparece en <b>{hojasForm.length}</b> hojas 1:50 000 · de la más cercana a la fábrica:
                                    </div>
                                    <div className="chips">
                                      {hojasOrdenadas.slice(0, 40).map((h) => (
                                        <button key={h.hoja} onClick={() => irAHoja(h.hoja)} title={`${h.poligonos} polígonos`}>
                                          {h.celda?.codigo ?? h.hoja} <small>{formatoKm(h.km)}</small>
                                        </button>
                                      ))}
                                    </div>
                                    {hojasOrdenadas.length > 40 && <div className="meta">…y {hojasOrdenadas.length - 40} más lejos.</div>}
                                  </>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ))}
              </>
            )}

          </div>
        </div>
      )}

      {verLaminas && celdaArea && res && (
        <Laminas key={verLaminas} informe={verLaminas === "informe"} celda={celdaArea} res={res} s2={s2Laminas} materia={materiaSel.nombre}
          ambitoUnidades={indicesPorUnidad && capasUnidad ? [...unidadesPrio] : null} fabrica={fabrica} opacidades={opac}
          mejorZona={(() => {
            if (!prioLibre) return null;
            const m = res.afloramientos.filter((a) => a.clase !== "C").map((a) => ({ unidad: a.unidad, ha: prioLibre.porZona[a.id]?.haLibre ?? 0 }))
              .sort((x, y) => y.ha - x.ha)[0];
            return m && m.ha > 0 ? m : null;
          })()}
          unidadesPrio={[...unidadesPrio].map((nombre) => {
            const zs = zonasElegidas.filter((a) => a.unidad === nombre);
            const suma = (k: "haLibre" | "haNegociable") => (prioLibre ? zs.reduce((s, a) => s + (prioLibre.porZona[a.id]?.[k] ?? 0), 0) : null);
            return { nombre, libre: suma("haLibre"), negociable: suma("haNegociable"), pasa: prioUnidades[nombre]?.pctPasa ?? null };
          })}
          geologiaLibre={geoLibre ? { url: geoLibre.url, bbox: geoLibre.bbox, libre: geoLibre.haLibre, negociable: geoLibre.haNegociable,
            noApto: geoLibre.haNoApto, extinguido: geoLibre.haExtinguido, sinSatelite: true, unidades: [...unidadesPrio] } : null}
          prioridadLibre={prioLibre ? { url: prioLibre.url, bbox: prioLibre.bbox, libre: prioLibre.haLibre, negociable: prioLibre.haNegociable,
            noApto: prioLibre.haNoApto, extinguido: prioLibre.haExtinguido, sinSatelite: prioLibre.sinSatelite, unidades: [...unidadesPrio] } : null}
          ruta={rutaDestino && destino ? { ruta: rutaDestino, destino: { lat: destino.lat, lon: destino.lon,
            nombre: (() => { const c = celdaEn(destino.lat, destino.lon, "25K"); return `Punto en ${c.codigo}`; })() } } : null}
          onCerrar={() => setVerLaminas(false)} />
      )}

      {verSIG && celdaArea && res && (
        <ExportarSIG celda={celdaArea} zonas={res.afloramientos} prioridad={prioLibre ? { url: prioLibre.url, bbox: prioLibre.bbox } : null}
          onCerrar={() => setVerSIG(false)} />
      )}

      {verVig && (
        <PanelVigilancia st={vig} geocatmin={servicios.geocatmin} onCerrar={() => setVerVig(false)}
          onIr={(anillo) => mapaRef.current?.encuadrar(anillo)}
          onAgregarCarpetas={() => {
            let n = 0;
            for (const k of carpetas) for (const g of k.celdas) {
              const c = celda25(g.codigo);
              if (c && !vig.vigila(`c:${c.codigo}`)) { vig.agregar({ id: `c:${c.codigo}`, tipo: "cuadricula", nombre: c.codigo, anillo: celdaComoPoligono(c), propio: false }); n++; }
            }
            return n;
          }} />
      )}

      {verRanking && (
        <Ranking onCerrar={() => setVerRanking(false)} onMapa={setRankingMapa}
          onIr={(codigo) => {
            const c = celda25(codigo);
            if (!c) return;
            setResaltado(null);
            mapaRef.current?.encuadrar(celdaComoPoligono(c));
            setCeldaSel(c);
            if (tactil) setVerRanking(false);
          }} />
      )}

      {verSuper && (
        <Supermaduras onCerrar={() => setVerSuper(false)} onMapa={setSuperMapa} unidadInicial={superUnidad}
          onIr={(codigo) => {
            const c = celda25(codigo);
            if (!c) return;
            setResaltado(null);
            mapaRef.current?.encuadrar(celdaComoPoligono(c));
            setCeldaSel(c);
            if (tactil) setVerSuper(false);
          }} />
      )}

      {verPetitorio && (
        <PanelPetitorio st={pet} onCerrar={() => { setVerPetitorio(false); pet.setEligiendo(false); }}
          vigilado={pet.activo ? vig.vigila(`p:${pet.activo.id}`) : false}
          onVigilar={(nombre, anillo) => { if (pet.activo) vig.agregar({ id: `p:${pet.activo.id}`, tipo: "petitorio", nombre, anillo, propio: true }); }}
          onVerCatastro={() => setCapas((c) => ({ ...c, catastro: true, areas_libres: true, restringidas: true }))} />
      )}

      {verMaterias && (
        <EditorMaterias materiales={materiales} materiaId={materiaId}
          onElegir={(id) => { cambiarMateria(id); }}
          onCambio={(lista, elegir) => { setMateriales(lista); if (elegir) cambiarMateria(elegir); }}
          onCerrar={() => setVerMaterias(false)} />
      )}

      {/* ---------- buscador ---------- */}
      <div className={sugerir ? "buscador abierto" : "buscador"}>
        <div className="marca" title="Prospector RMI · exploración de rocas y minerales industriales">
          <svg viewBox="0 0 32 32" width="30" height="30" aria-hidden="true">
            <rect x="1" y="1" width="30" height="30" rx="7" fill="#1e293b" stroke="#334155" />
            <path d="M5 21 L11 13 L15 18 L20 9 L27 21 Z" fill="#c08a4a" />
            <path d="M5 21 L27 21 L27 24 L5 24 Z" fill="#8a5a2b" />
            <path d="M5 24 L27 24 L27 27 L5 27 Z" fill="#5b3b1d" />
            <circle cx="20" cy="9" r="2" fill="#e9d5b3" />
          </svg>
          <span className="marca-txt"><b>PROSPECTOR</b><small>RMI · No metálicos</small></span>
        </div>
        <div className="busqueda">
        <div className="caja">
          <span className="lupa" aria-hidden="true"><svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg></span>
          <input
            value={texto}
            placeholder="Formación, roca o cuadrícula (Chimú, cuarcita, 25i1-NO)"
            onFocus={() => setSugerir(true)}
            onChange={(e) => { setTexto(e.target.value); setSugerir(true); }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && sugerencias[0]) sugerencias[0].accion();
              if (e.key === "Escape") setSugerir(false);
            }}
          />
          {(texto || formacionSel || resaltado) && (
            <button className="limpiar" title="Limpiar búsqueda y filtro" onClick={() => {
              setTexto(""); setSugerir(true); setResaltado(null);
              if (formacionSel) elegirFormacion(null);
            }}>×</button>
          )}
          <button className="chip-materia" title="Materia prima: elegir o crear" onClick={() => { setSugerir(false); setVerMaterias(true); }}>
            <FlaskConical size={15} /> <span>{materiaSel.nombre}</span>
          </button>
        </div>
        {sugerir && (
          <div className="sugerencias">
            {sugerencias.map((s) => (
              <div key={s.clave} className="sug" onClick={s.accion}>
                <span className="ico">{s.icono}</span>
                <div><b>{s.titulo}</b><small>{s.sub}</small></div>
              </div>
            ))}
            {!texto.trim() && (
              <div className="tabla-rapida">
                <div className="grupo">Mostrar solo esto en el mapa</div>
                {TIPOS_FORMACION.map(({ tipo, titulo }) => (
                  <div key={titulo} className="fila-rapida">
                    <small>{titulo}</small>
                    <div className="chips">
                      {[...(tipo.includes("Roca") ? [{ id: "_silice", nombre: "Arena silícea (todo lo silíceo)" } as Formacion] : []),
                        ...formaciones.filter((f) => tipo.includes(f.tipo))].map((f) => (
                        <button key={f.id} className={formacionSel?.id === f.id ? "on" : ""} onClick={() => {
                          if (f.id === "_silice") { filtrarPorTexto("arena silícea"); return; }
                          setSugerir(false); setTexto(f.nombre); elegirFormacion(f);
                        }}>
                          {f.nombre.replace(/ \(.*\)$/, "")}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
                <div className="grupo">Ir a un cuadrángulo</div>
                <small className="ayuda-cod">
                  Escribe el código: <b>27-k</b> (hoja 1:100 000), <b>27k4</b> (1:50 000), <b>27k4-NO</b> (cuadrícula 1:25 000),
                  {" "}<b>25i-NO</b> (cuadrante NO de 25-i) o el nombre de la hoja (<b>Chincha</b>, <b>Lima</b>…).
                </small>
              </div>
            )}
            <div className="cerrar-sug" onClick={() => setSugerir(false)}>cerrar</div>
          </div>
        )}
        </div>
        <div className="servicios" aria-label="Estado de los servicios" role="button" style={{ cursor: "pointer" }}
          title={`Servidor: ${API_URL} · tocar para cambiarlo`} onClick={cambiarServidor}>
          {([["INGEMMET", servicios.geocatmin, "GEOCATMIN de INGEMMET (geología, concesiones, áreas protegidas)"],
             ["Sentinel-2", servicios.sentinel, "Imágenes Sentinel-2 (Copernicus)"]] as const).map(([n, ok, d]) => (
            <span key={n} className={`servicio ${ok === null ? "dudoso" : ok ? "ok" : "caido"}`}
              title={`${d}: ${ok === null ? "sin datos" : ok ? "en línea" : "NO responde"}`}>
              <i /> <span>{n}</span>
            </span>
          ))}
        </div>
      </div>

      {/* ---------- botones flotantes ---------- */}
      <div className={`flotantes${barraPlegada ? " plegada" : ""}${masAbierto ? " mas-abierto" : ""}`}
        onClick={(e) => { if ((e.target as HTMLElement).closest(".secundario")) setMasAbierto(false); }}>
        <button className="plegar-barra" title={barraPlegada ? "Mostrar herramientas" : "Plegar herramientas (más mapa a la vista)"}
          aria-label={barraPlegada ? "Mostrar herramientas" : "Plegar herramientas"} onClick={() => plegarBarra(!barraPlegada)}>
          {barraPlegada ? <ChevronLeft size={20} /> : <ChevronRight size={18} />}
        </button>
        {!barraPlegada && <>
        <button title="Capas" aria-label="Capas" className={verCapas ? "activo" : ""} onClick={() => setVerCapas((v) => !v)}><Layers size={20} /></button>
        <button title="Carpetas y formaciones" aria-label="Carpetas y formaciones" className={verCatalogo ? "secundario activo" : "secundario"}
          onClick={() => { setVerCatalogo((v) => !v); setVerCapas(false); }}><Library size={20} /></button>
        <button title="Vigilancia del catastro de INGEMMET" aria-label="Vigilancia del catastro" className={verVig ? "secundario activo campana" : "secundario campana"}
          onClick={() => { setVerVig((v) => !v); setVerCapas(false); setVerRanking(false); setVerSuper(false); setVerPetitorio(false); setVerBarrido(false); }}>
          <Bell size={20} />{vig.noLeidas > 0 && <span className="insignia">{vig.noLeidas}</span>}
        </button>
        <button title="Ranking nacional: cuadrículas con geología silícea libre y utilizable" aria-label="Ranking nacional"
          className={verRanking ? "activo" : ""}
          onClick={() => { setVerRanking((v) => !v); setVerSuper(false); setVerCapas(false); setVerBarrido(false); setVerPetitorio(false); }}><Trophy size={20} /></button>
        <button title="Unidades supermaduras: arenas y areniscas casi solo de cuarzo (51 boletines de INGEMMET)" aria-label="Unidades supermaduras"
          className={verSuper ? "activo" : ""}
          onClick={() => { setVerSuper((v) => !v); setSuperUnidad(null); setVerRanking(false); setVerCapas(false); setVerBarrido(false); setVerPetitorio(false); }}><Gem size={20} /></button>
        <button title="Barrido de una región: puntúa muchas cuadrículas a la vez" aria-label="Barrido de región" className={verBarrido ? "secundario activo-barrido" : "secundario"}
          onClick={() => { setVerBarrido((v) => !v); setVerSuper(false); setVerCapas(false); }}><Radar size={20} /></button>
        <button title="Ruta por carretera: toca un punto del mapa" aria-label="Ruta por carretera" className={modoRuta ? "activo-ruta" : ""}
          onClick={() => { setModoRuta((v) => !v); setCeldaSel(null); }}><Route size={20} /></button>
        <button title="Petitorio minero: pasos y cuadrículas de 100 ha" aria-label="Petitorio minero" className={verPetitorio ? "secundario activo" : "secundario"}
          onClick={() => { setVerPetitorio((v) => !v); setVerSuper(false); setVerCapas(false); setVerBarrido(false); }}><ClipboardCheck size={20} /></button>
        <span className="sep secundario" />
        <button className="secundario" title={`Mapa base: ${base === "satelite" ? "satélite" : base === "relieve" ? "relieve" : "topográfico"} (tocar para cambiar)`} aria-label="Cambiar mapa base"
          onClick={() => {
            const sig = base === "satelite" ? "relieve" : base === "relieve" ? "mapa" : "satelite";
            setBase(sig);
            setAviso(`Mapa base: ${sig === "satelite" ? "satélite" : sig === "relieve" ? "relieve sombreado" : "topográfico"}`);
          }}>
          {base === "satelite" ? <Satellite size={20} /> : base === "relieve" ? <Mountain size={20} /> : <IconoMapa size={20} />}
        </button>
        <button title="Mi ubicación" aria-label="Mi ubicación" onClick={miUbicacion}><LocateFixed size={20} /></button>
        <button className="secundario" title="Ir a la fábrica" aria-label="Ir a la fábrica" onClick={() => {
          setCapas((c) => ({ ...c, fabrica: true }));
          mapaRef.current?.irAPunto(fabrica[0], fabrica[1], 12);
        }}><Factory size={20} /></button>
        <button className={masAbierto ? "solo-cel activo" : "solo-cel"} title="Más herramientas" aria-label="Más herramientas"
          onClick={() => setMasAbierto((v) => !v)}>
          {masAbierto ? <X size={20} /> : <MoreHorizontal size={20} />}
          {!masAbierto && vig.noLeidas > 0 && <span className="insignia">{vig.noLeidas}</span>}
        </button>
        </>}
      </div>

      {/* ---------- barrido de región ---------- */}
      {verBarrido && (() => {
        const enCurso = barridoTrabajo && !barridoTrabajo.terminado;
        const elegir = (modo: "vista" | "hoja") => {
          const cs = celdasDeRegion(modo);
          if (typeof cs === "string") { setAviso(cs); return; }
          if (confirm(`¿Barrer ${cs.length} cuadrícula(s)? Tarda ~${Math.max(1, Math.round(cs.length * 2 / 60))} min y no gasta créditos de Copernicus.`)) iniciarBarrido(cs);
        };
        return (
          <div className="panel-barrido">
            <button className="cerrar" onClick={() => setVerBarrido(false)} aria-label="Cerrar">×</button>
            <b className="tit">🔥 Barrido de región</b>
            <small className="sub">Puntúa muchas cuadrículas de una vez: geología 1:50 000 / 1:100 000 + áreas libres y utilizables. Sin Sentinel-2 (no gasta créditos).</small>
            {!enCurso && (
              <div className="elegir-region">
                <button onClick={() => elegir("vista")}>🗺 La vista actual del mapa</button>
                <div className="fila-hoja">
                  <input value={hojaBarrido} placeholder="hoja: 27-k o 27k4" onChange={(e) => setHojaBarrido(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") elegir("hoja"); }} />
                  <button onClick={() => elegir("hoja")}>Barrer hoja</button>
                </div>
                <small>Máximo {MAX_BARRIDO} cuadrículas (una hoja 1:100 000 = 16). Cada una queda guardada como análisis «Solo geología».</small>
              </div>
            )}
            {barridoTrabajo && (
              <div className="avance-barrido">
                <div className="barra"><i style={{ width: `${100 * barridoTrabajo.hechas / Math.max(1, barridoTrabajo.total)}%` }} /></div>
                <small>{barridoTrabajo.hechas} de {barridoTrabajo.total} cuadrículas · {barridoTrabajo.segundos} s
                  {enCurso ? " · analizando…" : barridoTrabajo.hechas < barridoTrabajo.total ? " · detenido" : " · terminado"}</small>
                {enCurso && <button className="btn-libres" onClick={cancelarBarrido}>Detener</button>}
              </div>
            )}
            {rankingBarrido.length > 0 && (
              <>
                <small className="sub-grupo">Ranking (puntaje = ha libres y utilizables · A×1 + B×0,7 + C×0,4)</small>
                <ol className="ranking-barrido">
                  {rankingBarrido.slice(0, 20).map((f, i) => {
                    const c = barridoCeldas.find((x) => x.codigo === f.codigo) ?? celda25(f.codigo);
                    return (
                      <li key={f.codigo} onClick={() => { if (c) { setVerBarrido(false); analizarCelda(c, false); } }} title="Abrir esta cuadrícula">
                        <span className="puesto">{i + 1}</span>
                        <span className="cuerpo">
                          <b>{f.codigo}</b> <small>puntaje {(f.puntaje ?? 0).toLocaleString("es-PE")}</small>
                          <small>
                            A {f.ha_util?.A ?? 0} · B {f.ha_util?.B ?? 0} · C {f.ha_util?.C ?? 0} ha libres
                            {c ? ` · ${formatoKm(km((c.norte + c.sur) / 2, (c.oeste + c.este) / 2))}` : ""}
                            {f.prohibido ? " · ⛔ mayormente protegida" : ""}
                          </small>
                          {f.mejor_zona && <small>mejor: {f.mejor_zona.clase} {f.mejor_zona.unidad} ({f.mejor_zona.ha_util} ha)</small>}
                          {!!f.zonas_100k_A_ha && f.escala === "50K" && <small>+ {f.zonas_100k_A_ha} ha de arena cuarzosa según la 1:100 000</small>}
                        </span>
                      </li>
                    );
                  })}
                </ol>
                {Object.values(barridoRes).some((f) => !f.ok) && (
                  <small className="nota alerta">{Object.values(barridoRes).filter((f) => !f.ok).length} cuadrícula(s) no respondieron (GEOCATMIN); vuelve a barrer para reintentar.</small>
                )}
              </>
            )}
            {barridoCeldas.length > 0 && !enCurso && (
              <button className="btn-libres" onClick={() => { setBarridoCeldas([]); setBarridoRes({}); setBarridoTrabajo(null); }}>Quitar el barrido del mapa</button>
            )}
          </div>
        );
      })()}

      {/* ---------- modo ruta: el próximo toque es el destino ---------- */}
      {modoRuta && (
        <div className="banda-ruta">
          🚚 <b>Toca en el mapa el punto de destino</b> <small>(ruta desde la fábrica)</small>
          <button onClick={() => setModoRuta(false)}>Cancelar</button>
        </div>
      )}

      {/* ---------- panel de la ruta: tramos por tipo de vía ---------- */}
      {verRuta && destino && rutaEstado && (
        <div className="panel-ruta">
          <button className="cerrar" onClick={() => { setVerRuta(false); setDestino(null); }} aria-label="Cerrar ruta">×</button>
          <b className="tit">🚚 Ruta desde la fábrica</b>
          <small className="sub">a {destino.lat.toFixed(5)}, {destino.lon.toFixed(5)}</small>
          {rutaEstado === "cargando" ? <p className="nota">Trazando la ruta…</p>
            : "error" in rutaEstado ? (
              <p className="nota alerta">No se pudo trazar: {rutaEstado.error}{" "}
                <button className="enlace" onClick={() => calcularRuta(destino.lat, destino.lon, true)}>Reintentar</button></p>
            ) : rutaDestino ? (
              <>
                <div className="total-ruta">
                  <b>{rutaDestino.km_total.toLocaleString("es-PE")} km</b>
                  <small>en total · {rutaDestino.km_carro.toLocaleString("es-PE")} km en carro · {rutaDestino.km_linea_recta.toLocaleString("es-PE")} km en línea recta</small>
                </div>
                <div className="barra-ruta">
                  {(Object.keys(COLOR_TRAMO) as TipoTramo[]).map((t) => rutaDestino.resumen[t] > 0 && (
                    <i key={t} style={{ background: COLOR_TRAMO[t], width: `${100 * rutaDestino.resumen[t] / rutaDestino.km_total}%` }} />
                  ))}
                </div>
                <div className="leyenda-ruta">
                  {(Object.keys(COLOR_TRAMO) as TipoTramo[]).map((t) => (
                    <span key={t}><i className={t} style={{ background: COLOR_TRAMO[t] }} />{rutaDestino.tipos[t]}: <b>{rutaDestino.resumen[t].toLocaleString("es-PE")} km</b></span>
                  ))}
                </div>
                <small className="sub-grupo">Tramos (de la fábrica al punto)</small>
                <ol className="tramos">
                  {rutaDestino.bloques.map((b, i) => (
                    <li key={i}>
                      <i style={{ background: COLOR_TRAMO[b.tipo] }} className={b.tipo} />
                      <span><b>{b.km.toLocaleString("es-PE")} km</b> · {CORTO_TRAMO[b.tipo]}
                        {b.vias.length ? <small> — {b.vias.slice(0, 2).join(", ")}</small> : b.detalle ? <small> — {b.detalle}</small> : null}</span>
                    </li>
                  ))}
                </ol>
                {rutaDestino.avisos.map((a) => <p key={a} className="nota alerta">{a}</p>)}
                <small className="nota-ruta">{rutaDestino.nota} Fuente: {rutaDestino.fuente}.</small>
                <button className="btn-libres" onClick={() => setModoRuta(true)}>📍 Elegir otro punto</button>
                {celdaArea && res && !res.soloSatelite && (
                  <button className="btn-libres" onClick={() => setVerLaminas("laminas")}><FileImage size={14} /> Lámina de la ruta</button>
                )}
              </>
            ) : null}
        </div>
      )}

      {verCapas && (
        <div className="panel-capas">
          <div className="titulo">Capas <span className="acciones-titulo"><button className="guia" onClick={() => setVerGuia(true)}><BookOpen size={15} /> Guía de capas</button><button onClick={() => setVerCapas(false)}>×</button></span></div>

          {/* vista rápida */}
          <div className="vista-rapida">
            <button className={geologiaVisible && !sentinelVisible ? "on" : ""} onClick={() => vistaRapida("geo")}><Mountain size={20} /><span>Geología</span></button>
            <button className={sentinelVisible && !geologiaVisible ? "on" : ""} onClick={() => vistaRapida("s2")}><Satellite size={20} /><span>Satélite</span></button>
            <button className={sentinelVisible && geologiaVisible ? "on" : ""} onClick={() => vistaRapida("ambos")}><Layers size={20} /><span>Ambos</span></button>
          </div>

          {/* resultado: lo que decide */}
          {hayVista("s2_prioridad_libre") && (
            <div className="seccion-capa resultado">
              <div className="grupo"><span className="paso estrella-paso"><Star size={11} /></span> Resultado: dónde ir</div>
              <div className="fila-capa">
                <label className={capas.s2_prioridad_libre ? "radio on" : "radio"}>
                  <input type="checkbox" checked={capas.s2_prioridad_libre} onChange={() => alternarVista("s2_prioridad_libre")} />
                  <i className="muestra" style={{ background: VISTAS_S2[0].muestra }} />
                  <span><b>Prioridad libre{celdaArea ? ` · ${celdaArea.codigo}` : ""}</b><small>verde libre · azul concesión · amarillo chacra/vía · celeste extinguido</small></span>
                </label>
                {botonAyuda("s2_prioridad_libre")}
              </div>
              {capas.s2_prioridad_libre && deslizador("s2_prioridad_libre")}
              {bloqueAyuda("s2_prioridad_libre")}
            </div>
          )}

          {/* geología */}
          <div className="seccion-capa">
            <div className="grupo"><span className="paso">1</span> {esSilice ? "¿Dónde hay roca silícea?" : `¿Dónde hay ${materiaSel.nombre.toLowerCase()}?`}</div>
            {CAPAS.filter((c) => c.grupo === "geo").map((c) => (
              <div key={c.id}>
                <div className="fila-capa">
                  <label>
                    <input type="checkbox" checked={capas[c.id]} onChange={(e) => setCapas((x) => ({ ...x, [c.id]: e.target.checked }))} />
                    <span>{!esSilice && (c.id === "geo50_si" || c.id === "geo100_si")
                      ? <>Rocas de interés · {c.id === "geo50_si" ? "1:50 000" : "1:100 000"}<small>{materiaSel.nombre}</small></>
                      : <>{c.nombre}{c.nota && <small>{c.nota}</small>}</>}</span>
                  </label>
                  {botonAyuda(c.id)}
                </div>
                {bloqueAyuda(c.id)}
                {capas[c.id] && c.id in GEO_OPACIDAD && <div className="opac-geo">{deslizador(c.id)}</div>}
              </div>
            ))}
            <div className="leyenda-mini">
              <span><i style={{ background: COLOR_CLASE.A }} />A · depósito de arena silícea o cuarzosa</span>
              <span><i style={{ background: COLOR_CLASE.B }} />B · roca: arenisca cuarzosa/cuarcítica o cuarcita</span>
              <span><i style={{ background: COLOR_CLASE.C, opacity: 0.6 }} />C · verificar (arenisca o eólico sin decir «cuarzoso»)</span>
            </div>
          </div>

          {/* 2 · ¿está libre? */}
          <div className="seccion-capa">
            <div className="grupo"><span className="paso">2</span> ¿Se puede pedir? (libre o concesionado)</div>
            {CAPAS.filter((c) => c.grupo === "derechos").map((c) => (
              <div key={c.id}>
                <div className="fila-capa">
                  <label>
                    <input type="checkbox" checked={capas[c.id]} onChange={(e) => setCapas((x) => ({ ...x, [c.id]: e.target.checked }))} />
                    <span>{c.nombre}{c.nota && <small>{c.nota}</small>}</span>
                  </label>
                  {botonAyuda(c.id)}
                </div>
                {bloqueAyuda(c.id)}
              </div>
            ))}
          </div>

          {/* Sentinel-2 */}
          <div className="seccion-capa s2">
            <div className="grupo"><span className="paso">3</span> ¿Se ve limpia? (satélite)</div>
            {!s2?.disponible ? (
              <div className="s2-vacio">
                Aún no hay imagen. Toca una cuadrícula → <b>«Analizar cuadrícula»</b>.
                {celdaArea && !s2 && (
                  <button className="primario" disabled={cargandoS2} onClick={() => { setVerCapas(false); analizarCelda(celdaArea, true); }}>
                    {cargandoS2 ? "Procesando…" : `Agregar Sentinel-2 a ${celdaArea.codigo}`}
                  </button>
                )}
              </div>
            ) : (
              <>
                <small className="explica">Cuadrícula {celdaArea?.codigo ?? ""} · {s2.periodo}{s2.imagen?.nubes_cuadricula != null ? ` · ${s2.imagen.nubes_cuadricula.toLocaleString("es-PE")} % nubes` : ""}</small>
                {s2?.disponible && !s2.solo_satelite && !s2.capas?.ndvi && (
                      <div className="aviso-capas">
                        <span><b>NDVI</b>, <b>BSI</b> y <b>Anomalías ferruginosas</b> no están en este análisis (es anterior a esas capas).</span>
                        <button disabled={cargandoS2} onClick={() => { if (confirm("¿Buscar una toma nueva para generar NDVI, BSI y Anomalías ferruginosas? Reemplaza la imagen guardada y gasta créditos de Copernicus (o usa AWS gratis si no hay cupo).")) nuevaToma(); }}>
                          <RefreshCw size={13} /> Nueva toma</button>
                      </div>
                    )}
                {([["continua", "NDVI y BSI (escala continua, 100 % de los datos) · anomalías ferruginosas (con tu corte)"], ["indice", "Índices con tu corte (puedes marcar varios a la vez)"]] as const).map(([g, titulo]) => (
                  <div key={g}>
                    <small className="sub-grupo">{titulo}</small>
                    {VISTAS_S2.filter((v) => v.grupo === g && hayVista(v.id)).map((v) => (
                      <div key={v.id}>
                        <div className="fila-capa">
                          <label className={capas[v.id] ? "radio on" : "radio"}>
                            <input type="checkbox" checked={capas[v.id]} onChange={() => alternarVista(v.id)} />
                            <i className="muestra" style={{ background: v.muestra }} />
                            <span><b>{v.nombre}</b></span>
                          </label>
                          {botonAyuda(v.id)}
                        </div>
                        {capas[v.id] && deslizador(v.id)}
                        {bloqueAyuda(v.id)}
                      </div>
                    ))}
                  </div>
                ))}
                <small className="sub-grupo">Foto de fondo (una a la vez)</small>
                {[...VISTAS_S2.filter((v) => v.grupo === "bandas" && hayVista(v.id)), null].map((v) => (
                  <div key={v?.id ?? "sin-foto"}>
                    <div className="fila-capa">
                      <label className={(v ? capas[v.id] : !VISTAS_S2.some((x) => x.grupo === "bandas" && capas[x.id])) ? "radio on" : "radio"}>
                        <input type="radio" name="fondo-s2"
                          checked={v ? capas[v.id] : !VISTAS_S2.some((x) => x.grupo === "bandas" && capas[x.id])}
                          onChange={() => elegirFondo(v?.id ?? null)} />
                        {v && <i className="muestra" style={{ background: v.muestra }} />}
                        <span><b>{v ? v.nombre : "Sin foto (mapa base)"}</b></span>
                      </label>
                      {v && botonAyuda(v.id)}
                    </div>
                    {v && capas[v.id] && deslizador(v.id)}
                    {v && bloqueAyuda(v.id)}
                  </div>
                ))}
                <button className="enlace" onClick={() => setCapas((c) => ({ ...c, ...soloVista(null) }))}>Ocultar todas las capas satelitales</button>
              </>
            )}
          </div>

          {/* referencia */}
          <div className="seccion-capa">
            <div className="grupo"><MapPin size={13} /> Referencia</div>
            {CAPAS.filter((c) => c.grupo === "ref").map((c) => (
              <div key={c.id}>
                <div className="fila-capa">
                  <label>
                    <input type="checkbox" checked={capas[c.id]} onChange={(e) => setCapas((x) => ({ ...x, [c.id]: e.target.checked }))} />
                    <span>{c.nombre}{c.nota && <small>{c.nota}</small>}</span>
                  </label>
                  {botonAyuda(c.id)}
                </div>
                {bloqueAyuda(c.id)}
              </div>
            ))}
          </div>

          <div className="leyenda">
            <span><i style={{ background: "transparent", border: `2px solid ${COLOR_CLASE.A}` }} />✓ / ★ Cuadrícula analizada / guardada (color = mejor clase)</span>
            <b>Cuadrícula</b>
            <span><i className="linea gruesa" />Hoja 1:50 000 (p. ej. 27k4)</span>
            <span><i className="linea fina" />Cuadrícula 1:25 000 (27k4-NE…): tócala para analizarla</span>
            <small>Cuadrantes 50K como INGEMMET: 1 NE · 2 SE · 3 SO · 4 NO</small>
          </div>
        </div>
      )}

      {fase === "buscando" && (
        <div className="cargando">
          <div className="spinner" />
          Consultando INGEMMET: geología 1:50 000 y 1:100 000, concesiones y áreas protegidas…
          <small>La carta 50K puede tardar hasta 40 s.</small>
        </div>
      )}
      {error && <div className="error" onClick={() => setError(null)}>{error}<small>tocar para cerrar</small></div>}
      {aviso && <div className="aviso">{aviso}</div>}

      {/* ---------- leyenda flotante: qué estás viendo ahora ---------- */}
      {(geologiaVisible || sentinelVisible || formacionSel) && !verCapas && !verCatalogo && !sugerir
        && (!res || hoja === "cerrada") && (leyendaPlegada ? (
        <button className="viendo-mini" onClick={() => plegarLeyenda(false)} title="Mostrar la leyenda de lo que se ve en el mapa">
          <Layers size={14} /> Leyenda
        </button>
      ) : (
        <div className="viendo" onClick={() => setVerCapas(true)} title="Tocar para cambiar las capas">
          <button className="plegar-leyenda" aria-label="Plegar la leyenda" title="Plegar la leyenda"
            onClick={(e) => { e.stopPropagation(); plegarLeyenda(true); }}><X size={13} /></button>
          {sentinelVisible && (
            <>
              {/* de arriba hacia abajo, en el mismo orden en que se apilan en el mapa */}
              {[...vistasActivas].sort((a, b) => (CAPAS_SATELITE[b.id]?.z ?? 0) - (CAPAS_SATELITE[a.id]?.z ?? 0)).map((v) => (
                <div key={v.id} className="fila-viendo">
                  <i className="muestra" style={{ background: v.muestra }} />
                  <span>
                    <b>{v.nombre}</b>
                    {vistasActivas.length === 1 && <small>{explicaVista(v.id).split(".")[0]}.</small>}
                  </span>
                </div>
              ))}
              {s2?.imagen?.fecha_peru && vistasActivas.some((v) => v.id !== "s2_prioridad_libre") && (
                <small className="fecha-viendo"><CalendarDays size={12} /> Sentinel-2 {s2.imagen.fecha_peru} · <Cloud size={12} /> {s2.imagen.nubes_cuadricula?.toLocaleString("es-PE")} %</small>
              )}
            </>
          )}
          {formacionSel && (
            <div className="fila-viendo">
              <i className="muestra" style={{ background: "#94a3b8" }} />
              <span><b>Solo: {formacionSel.nombre}</b><small>colores de INGEMMET por unidad</small></span>
            </div>
          )}
          {capas.resultados && res && afloramientosVisibles.length > 0 && (
            <div className="fila-viendo">
              <span className="abc">
                <i style={{ background: COLOR_CLASE.A }}>A</i><i style={{ background: COLOR_CLASE.B }}>B</i><i style={{ background: COLOR_CLASE.C }}>C</i>
              </span>
              <span><b>Zonas favorables</b><small>{esSilice ? "gruesas y con nombre = aptas para vidrio · tenues = no aptas" : "de la geología de INGEMMET"}</small></span>
            </div>
          )}
          {!formacionSel && (capas.geo50_si || capas.geo100_si) && (
            <div className="fila-viendo">
              <i className="muestra" style={{ background: "linear-gradient(90deg,#86efac,#fdba74,#93c5fd)" }} />
              <span><b>{esSilice ? "Geología silícea" : `Rocas de interés · ${materiaSel.nombre}`}</b><small>un color por unidad (INGEMMET)</small></span>
            </div>
          )}
          <small className="cambiar">▤ cambiar capas</small>
        </div>
      ))}

      {/* ---------- hoja de resultados ---------- */}
      {res && hojaOculta && (
        <button className="reabrir-hoja" onClick={() => setHojaOculta(false)} title="Mostrar los resultados">
          <PanelLeftOpen size={15} /> {celdaArea?.codigo ?? "Resultados"}
        </button>
      )}
      {res && !hojaOculta && (
        <div ref={hojaRef} className={`hoja ${hoja}`}
          style={posHoja.x || posHoja.y ? { transform: `translate(${posHoja.x}px, ${posHoja.y}px)`, transition: "none" } : undefined}>
          <div className="cabecera-hoja">
            <div className="barra-hoja">
              <button className="tirador" title="Arrastra para mover · toca para agrandar o achicar"
                aria-label={hoja === "cerrada" ? "Abrir resultados" : "Cerrar resultados"}
                onPointerDown={empezarArrastre} onPointerMove={moverArrastre}
                onPointerUp={terminarArrastre} onPointerCancel={() => { arrastre.current = null; }}><span /></button>
              {(posHoja.x !== 0 || posHoja.y !== 0) && (
                <button className="btn-hoja" title="Volver a su lugar" onClick={() => setPosHoja({ x: 0, y: 0 })}>⤢</button>
              )}
              <button className="btn-hoja" title="Ocultar los resultados" aria-label="Cerrar resultados"
                onClick={() => setHojaOculta(true)}><X size={15} /></button>
            </div>
            {celdaArea && (
              <div className="nav-celda">
                <span className="cod">{celdaArea.codigo}</span>
                <div className="flechas" role="group" aria-label="Ir a la cuadrícula vecina">
                  {([["O", "◀", "oeste"], ["N", "▲", "norte"], ["S", "▼", "sur"], ["E", "▶", "este"]] as const).map(([r, f, nombre]) => (
                    <button key={r} title={`Cuadrícula al ${nombre}`}
                      disabled={fase === "buscando" || cargandoS2 || !vecina(celdaArea, r)} onClick={() => irAVecina(r)}>{f}</button>
                  ))}
                </div>
                <button title="Guardar en carpeta" className={enCarpeta.has(celdaArea.codigo) ? "estrella on" : "estrella"}
                  onClick={() => setGuardando(celdaArea)}><Star size={15} /></button>
              </div>
            )}
            {celdaArea && (
              <div className="acciones-hoja" role="toolbar" aria-label="Acciones de la cuadrícula">
                <button title={vig.vigila(`c:${celdaArea.codigo}`) ? "Vigilada: avisos si cambia el catastro (tocar para dejar de vigilar)" : "Vigilar el catastro de esta cuadrícula"}
                  className={vig.vigila(`c:${celdaArea.codigo}`) ? "interruptor on" : "interruptor"}
                  onClick={() => (vig.vigila(`c:${celdaArea.codigo}`) ? vig.quitar(`c:${celdaArea.codigo}`)
                    : vig.agregar({ id: `c:${celdaArea.codigo}`, tipo: "cuadricula", nombre: celdaArea.codigo, anillo: celdaComoPoligono(celdaArea), propio: false }))}>
                  <Eye size={15} /> <span>Vigilar</span>
                </button>
                {!res.soloSatelite && (
                  <button title="Láminas para informe (A3): geología, Prioridad libre, áreas libres, imágenes, NDVI, BSI, anomalías ferruginosas, arcillas y ruta"
                    className="interruptor" onClick={() => setVerLaminas("laminas")}><FileImage size={15} /> <span>Láminas</span></button>
                )}
                {!res.soloSatelite && (
                  <button title="Informe PDF de la cuadrícula: portada, todas las láminas numeradas, antecedentes de boletines y análisis de las capas"
                    className="interruptor informe" onClick={() => setVerLaminas("informe")}><FileText size={15} /> <span>Informe PDF</span></button>
                )}
                {!res.soloSatelite && (
                  <button title="Exportar capas SIG (KMZ para Google Earth / GPS o shapefile para QGIS)" className="interruptor"
                    onClick={() => setVerSIG(true)}><Globe2 size={15} /> <span>SIG</span></button>
                )}
                {(() => {
                  const on = focoCelda?.codigo === celdaArea.codigo;
                  return (
                    <button className={on ? "interruptor on" : "interruptor"} onClick={() => setFocoCelda(on ? null : celdaArea)}
                      title={on ? "Volver a ver todo el mapa" : "Oscurecer todo lo que está fuera de esta cuadrícula"}>
                      <Scan size={15} /> <span>{on ? "Solo esta" : "Todo"}</span>
                    </button>
                  );
                })()}
                <button className={modoS2 ? "interruptor on" : "interruptor"} onClick={() => setModoS2((v) => !v)}
                  title="Al pasar a la vecina, analizar también con Sentinel-2 (gasta créditos de Copernicus)">
                  <Satellite size={15} /> <span>{modoS2 ? "S2 sí" : "S2 no"}</span>
                </button>
              </div>
            )}
            {celdaArea && (
              <SupermadurasCelda codigo={celdaArea.codigo}
                onAbrir={(u) => { setSuperUnidad(u); setVerSuper(true); setVerRanking(false); setVerBarrido(false); setVerPetitorio(false); setVerCapas(false); }} />
            )}
            <div className="resumen" onClick={() => setHoja((h) => (h === "cerrada" ? "media" : "cerrada"))}>
              {res.soloSatelite ? <span className="chip-dato ok"><Satellite size={12} /> Solo satélite · sin geología</span> : <>
                {(["A", "B", "C"] as const).map((cl) => (
                  <span key={cl} className="chip-clase" style={{ background: COLOR_CLASE[cl] }}
                    title={cl === "A" ? "A · depósitos de arena silícea o cuarzosa" : cl === "B" ? "B · rocas: arenisca cuarzosa/cuarcítica o cuarcita" : "C · verificar"}>
                    {cl} {afloramientosVisibles.filter((a) => a.clase === cl).length}
                  </span>
                ))}
              </>}
              {res.escala_usada && <span className="chip-dato">{res.escala_usada}</span>}
              {cargandoS2 ? <span className="chip-dato vivo"><Satellite size={12} /> Buscando la toma más despejada…</span>
                : s2?.disponible ? (
                  <span className={s2.imagen?.despejada === false ? "chip-dato alerta" : "chip-dato ok"}
                    title={s2.imagen?.fecha_peru ? `Toma Sentinel-2 del ${s2.imagen.fecha_peru} (hora Perú)` : "Mosaico de varias fechas"}>
                    <CalendarDays size={12} /> {s2.imagen?.fecha_peru?.slice(0, 10) ?? "mosaico"}
                    {s2.imagen?.nubes_cuadricula != null && <> <Cloud size={12} /> {s2.imagen.nubes_cuadricula.toLocaleString("es-PE")} %</>}
                  </span>
                ) : null}
              {!celdaArea && <span className="chip-dato">{res.area_km2.toLocaleString("es-PE")} km²</span>}
              {resumenRestr?.prohibido && (
                <span className="chip-dato prohibido"
                  title="Áreas protegidas / restringidas para concesiones en la cuadrícula">
                  <ShieldX size={12} /> {resumenRestr.texto}
                </span>
              )}
            </div>
          </div>
          <div className="pestanas">
            <button className={pestana === "afloramientos" ? "on" : ""} onClick={() => setPestana("afloramientos")}>
              Zonas ({afloramientosVisibles.length})
            </button>
            <button className={pestana === "sentinel" ? "on" : ""} onClick={() => setPestana("sentinel")}>Satélite</button>
            <button className={pestana === "biblio" ? "on" : ""} onClick={() => { setPestana("biblio"); cargarBiblio(); }}>Bibliografía</button>
          </div>
          <div className="contenido">
            {pestana === "biblio" && (
              <>
                <p className="nota">
                  Boletines, memorias y mapas oficiales de INGEMMET que cubren {celdaArea ? `la cuadrícula ${celdaArea.codigo}` : "el área"}.
                  Los enlaces se abren en tu navegador (el repositorio de INGEMMET verifica que seas una persona).
                </p>
                {!celdaArea && <p className="vacio">La bibliografía se busca por cuadrícula: toca una en el mapa.</p>}
                {celdaArea && !biblio[celdaArea.codigo] && <p className="vacio">Buscando en el índice de boletines de INGEMMET…</p>}
                {celdaArea && biblio[celdaArea.codigo] && (() => {
                  const b = biblio[celdaArea.codigo];
                  return (
                    <div className="biblio">
                      {b.avisos.map((a) => <p key={a} className="nota alerta">{a}</p>)}
                      <h4>📘 Boletines de INGEMMET ({b.boletines.length})</h4>
                      {!b.boletines.length && <p className="nota">El índice no tiene boletines para esta zona.</p>}
                      {b.boletines.map((x) => (
                        <a key={x.url || x.titulo} className="ref" href={x.url} target="_blank" rel="noopener noreferrer">
                          <b>{x.titulo}</b>
                          <small>{x.cita} · {x.tipo}</small>
                        </a>
                      ))}
                      {b.hoja100k && (
                        <>
                          <h4>🗺 Mapa geológico integrado oficial · hoja {b.hoja100k.codigo} {b.hoja100k.nombre}</h4>
                          <div className="botones-celda">
                            {b.hoja100k.png && <a className="boton-enlace" href={b.hoja100k.png} target="_blank" rel="noopener noreferrer">Ver imagen (PNG)</a>}
                            {b.hoja100k.zip && <a className="boton-enlace" href={b.hoja100k.zip} target="_blank" rel="noopener noreferrer">Descargar paquete completo (ZIP, ~60 MB)</a>}
                          </div>
                        </>
                      )}
                      <h4>📄 Memorias citadas en la geología 1:50 000 ({b.memorias.length})</h4>
                      <p className="nota">Son las fuentes de los polígonos que ves en el mapa de esta cuadrícula.</p>
                      {b.memorias.map((m) => (
                        <a key={m.cita} className="ref" href={m.buscar} target="_blank" rel="noopener noreferrer">
                          <b>{m.cita}</b>
                          <small>{m.poligonos} polígono(s) · buscar en el repositorio ↗</small>
                        </a>
                      ))}
                      <h4>🔎 Búsquedas listas</h4>
                      {b.busquedas.map((x) => (
                        <a key={x.url} className="ref" href={x.url} target="_blank" rel="noopener noreferrer">
                          <b>{x.titulo}</b><small>en el repositorio de INGEMMET ↗</small>
                        </a>
                      ))}

                    </div>
                  );
                })()}
              </>
            )}
            {pestana === "afloramientos" && (
              <>
                {!res.soloSatelite && res.libres && zonasPrio.length > 0 && (() => {
                  // unidades presentes: mejor clase, ha y aptitud para vidrio de su descripción
                  const R = { alta: 0, media: 1, baja: 2, no: 3 } as const;
                  const uds = new Map<string, { clase: "A" | "B" | "C"; ha: number; nivel: AptitudVidrio["nivel"] }>();
                  for (const a of zonasPrio) {
                    const u = uds.get(a.unidad);
                    const nv = vidrioPorId[a.id]?.nivel ?? "no";
                    if (!u) uds.set(a.unidad, { clase: a.clase, ha: a.area_ha, nivel: nv });
                    else { u.ha += a.area_ha; if (a.clase < u.clase) u.clase = a.clase; if (R[nv] < R[u.nivel]) u.nivel = nv; }
                  }
                  const lista = [...uds.entries()].sort((a, b) => a[1].clase.localeCompare(b[1].clase) || R[a[1].nivel] - R[b[1].nivel] || b[1].ha - a[1].ha);
                  const propia = !!(celdaArea && unidadesElegidas[celdaArea.codigo]);
                  const aptas = lista.filter(([, u]) => u.nivel === "alta" || u.nivel === "media").map(([n]) => n);
                  return (
                    <details className="unidades-prio" open={unidadesAbiertas} onToggle={(e) => setUnidadesAbiertas((e.target as HTMLDetailsElement).open)}>
                      <summary className="up-cab"><span className="eti">Unidades en la Prioridad</span>
                        <small>{unidadesPrio.size} de {lista.length}{propia ? " · tu elección" : " · A y B (por defecto)"}</small></summary>
                      {s2?.disponible && <small className="up-nota">Cada unidad se analiza aislada: NDVI, anomalía ferruginosa y arcilla con percentiles de SUS píxeles.</small>}
                      <div className="up-chips">
                        {lista.map(([nombre, u]) => {
                          const on = unidadesPrio.has(nombre);
                          return (
                            <button key={nombre} className={on ? "up-chip on" : "up-chip"} aria-pressed={on}
                              title={`${nombre} · clase ${u.clase} · ${NIVEL_TEXTO[u.nivel]} · ${Math.round(u.ha).toLocaleString("es-PE")} ha en la cuadrícula`
                                + (on && prioUnidades[nombre] ? ` · pasa el ${prioUnidades[nombre].pctPasa} % de su parte visible (percentiles dentro de la unidad)` : "")}
                              onClick={() => {
                                const n = new Set(unidadesPrio);
                                if (on) n.delete(nombre); else n.add(nombre);
                                elegirUnidades([...n]);
                              }}>
                              <span className="badge" style={{ background: COLOR_CLASE[u.clase] }}>{u.clase}</span>
                              <span className="up-nom">{nombre.replace(/^Grupo [^-]+ - /, "").replace(/^Formación /, "Fm. ")}</span>
                              <i className={`up-nv ${u.nivel}`} title={NIVEL_TEXTO[u.nivel]} />
                              <small>{Math.round(u.ha).toLocaleString("es-PE")} ha{on && prioUnidades[nombre] ? ` · pasa ${prioUnidades[nombre].pctPasa} %` : ""}</small>
                            </button>
                          );
                        })}
                      </div>
                      <div className="up-atajos">
                        <button className="enlace" onClick={() => elegirUnidades(null)}>A y B</button>
                        {esSilice && aptas.length > 0 && <button className="enlace" onClick={() => elegirUnidades(aptas)}>Solo aptas para vidrio</button>}
                        <button className="enlace" onClick={() => elegirUnidades(lista.map(([n]) => n))}>Todas</button>
                        <button className="enlace" onClick={() => elegirUnidades([])}>Ninguna</button>
                      </div>
                    </details>
                  );
                })()}
                {prioLibre ? (() => {
                  const pl = prioLibre;
                  const resto = Math.max(0, pl.haAlta - pl.haLibre - pl.haNegociable - pl.haNoApto - pl.haExtinguido);
                  const tot = Math.max(pl.haAlta, 1e-9);
                  const ct = s2?.disponible ? cortesDe(s2) : null;
                  const cats: [string, string, number][] = [["verde", "Libre", pl.haLibre], ["azul", "Concesión titulada / en trámite", pl.haNegociable],
                    ["amarillo", "Chacra, poblado, vía o río", pl.haNoApto], ["celeste", "Derecho extinguido", pl.haExtinguido],
                    ["gris", "Área protegida u otra concesión", resto]];
                  return (
                    <div className="prio-libre principal">
                      <div className="fila-prio-tit">
                        <span><b className="eti-kpi">Prioridad libre</b><small>{pl.haAlta.toLocaleString("es-PE")} ha de {unidadesPrio.size === 1 ? "la unidad elegida" : `las ${unidadesPrio.size} unidades elegidas`}{pl.sinSatelite ? " (sin limpiar)" : " que pasan los filtros"}</small></span>
                        <span className="cifra-prio"><b>{Math.round(pl.haLibre).toLocaleString("es-PE")}</b><small>ha libres</small></span>
                        <button className={capas.s2_prioridad_libre ? "btn-libres on" : "btn-libres"} onClick={() => alternarVista("s2_prioridad_libre")}>
                          {capas.s2_prioridad_libre ? "Ocultar" : "Ver en el mapa"}</button>
                      </div>
                      <div className="barra-prio" aria-hidden>
                        {cats.map(([c, , v]) => v > 0 && <i key={c} className={c} style={{ width: `${(100 * v) / tot}%` }} />)}
                      </div>
                      <div className="cats-prio">
                        {cats.map(([c, t, v]) => (v >= 0.5 || c === "verde" || c === "azul") && (
                          <span key={c} className={`cat-p ${c}`}><i /> {t} <b>{(Math.round(v * 10) / 10).toLocaleString("es-PE")} ha</b></span>
                        ))}
                      </div>
                      <small className="criterio-prio">
                        {pl.sinSatelite
                          ? <>Sin Sentinel-2: <b>no descuenta hierro ni arcillas</b>. Activa «S2 sí» y vuelve a analizar para limpiarla.</>
                          : <>Filtros: NDVI &lt; P{Math.round((ct?.p_ndvi ?? 0.57) * 100)}
                            {" "}· ferruginosa &lt; P{Math.round((ct?.p_ferruginosa ?? 0.3) * 100)} · arcilla &lt; P{Math.round((ct?.arcilla ?? 0.3) * 100)}
                            {" "}(<button className="enlace" onClick={() => { setPestana("sentinel"); abrirCortes(null); }}>ajustar</button>).</>}
                        {" "}Carta {res.escala_usada === "100K" ? "1:100 000" : "1:50 000"}; solo las unidades marcadas arriba.
                      </small>
                      {s2?.disponible && (s2.pct_area_valida ?? 100) < 30 && (
                        <small className="nota alerta"><Leaf size={12} /> Sentinel-2 solo ve el <b>{s2.pct_area_valida} %</b> de la cuadrícula (vegetación, nubes o agua):
                          lo que no se ve (vegetación densa, nubes, agua) no entra en la Prioridad libre.</small>
                      )}
                    </div>
                  );
                })() : clavePrioLibre ? (
                  <small className="nota">{errorPrioLibre ? `No se pudo cruzar la geología con las áreas libres (${errorPrioLibre}).` : "Calculando la Prioridad libre…"}</small>
                ) : !res.soloSatelite && res.libres && zonasPrio.length > 0 && !zonasElegidas.length ? (
                  <p className="nota">Ninguna unidad elegida: marca arriba la formación o el depósito que quieres en la Prioridad libre.</p>
                ) : null}
                {res.libres ? (() => {
                  const L_ = res.libres;
                  const fecha = new Date(L_.consultado).toLocaleDateString("es-PE", { day: "2-digit", month: "short", year: "numeric" });
                  return (
                    <details className="libres-celda plegable" open={verCatastro} onToggle={(e) => setVerCatastro((e.target as HTMLDetailsElement).open)}>
                      <summary>
                        <b>Catastro de la cuadrícula</b>
                        <small>{(L_.util_pct ?? L_.libre_pct).toLocaleString("es-PE")} % utilizable · {L_.n_concesiones} derecho{L_.n_concesiones === 1 ? "" : "s"}
                          {L_.concesiones.some((k) => k.indicio_silice?.nivel === "alto") ? " · no metálica sobre roca cuarzosa" : ""}</small>
                      </summary>
                      {(() => {
                        const util = L_.util_pct ?? L_.libre_pct;
                        const noApto = Math.max(0, L_.libre_pct - util);
                        return (
                          <>
                            <div className="barra-libres" aria-hidden>
                              <i className="libre" style={{ width: `${util}%` }} />
                              <i className="noapto" style={{ width: `${noApto}%` }} />
                              <i className="neg" style={{ width: `${L_.negociable_util_pct ?? 0}%` }} />
                              <i className="con" style={{ width: `${Math.max(0, L_.concesiones_pct - (L_.negociable_util_pct ?? 0))}%` }} />
                              <i className="pro" style={{ width: `${Math.max(0, 100 - L_.libre_pct - L_.concesiones_pct)}%` }} />
                            </div>
                            <div className="leyenda-libres">
                              <span><i className="libre" />utilizable {util} %</span>
                              {L_.util_pct != null && <span><i className="noapto" />libre pero no apto {Math.round(noApto * 10) / 10} %</span>}
                              {L_.negociable_util_pct != null && <span><i className="neg" />concesionado negociable {L_.negociable_util_pct} %</span>}
                              <span><i className="con" />concesiones (resto) {Math.round(Math.max(0, L_.concesiones_pct - (L_.negociable_util_pct ?? 0)) * 10) / 10} %</span>
                              <span><i className="pro" />protegida/restringida {L_.protegido_pct} %</span>
                            </div>
                          </>
                        );
                      })()}
                      {!!L_.por_liberarse_pct && L_.por_liberarse_pct >= 0.1 && (
                        <div className="por-liberarse">
                          <b>{L_.por_liberarse_pct} % ({(L_.por_liberarse_ha ?? 0).toLocaleString("es-PE")} ha) de lo libre es derecho EXTINGUIDO</b>
                          <small>Observación: falta que INGEMMET publique su libre denunciabilidad; recién entonces se puede pedir. En el mapa se ve celeste.</small>
                        </div>
                      )}
                      {!!L_.no_apto?.length && (
                        <small className="no-apto">
                          No apto aunque libre: {L_.no_apto.map((x) => `${x.texto} ${x.ha.toLocaleString("es-PE")} ha`).join(" · ")}
                        </small>
                      )}
                      {(() => {
                        const sil = L_.concesiones.filter((k) => k.indicio_silice?.nivel === "alto");
                        return sil.length > 0 && (
                          <div className="nm-silice">
                            <Search size={13} /> <b>{sil.length} concesión(es) NO metálica(s) sobre roca cuarzosa</b>
                            <small>Indicio de que ya se busca o explota arena silícea aquí: {sil.slice(0, 3).map((k) => k.nombre).join(", ")}{sil.length > 3 ? "…" : ""}. Toca un derecho para ver la evidencia.</small>
                          </div>
                        );
                      })()}
                      {L_.n_concesiones > 0 && (
                        <button className="enlace" onClick={() => setVerConcesiones((v) => !v)}>
                          {verConcesiones ? "▾" : "▸"} {L_.n_concesiones} derecho{L_.n_concesiones === 1 ? "" : "s"} minero{L_.n_concesiones === 1 ? "" : "s"} en la cuadrícula
                        </button>
                      )}
                      {verConcesiones && (
                        <div className="lista-concesiones">
                          <small className="ayuda-con">Toca un derecho para ver su ficha (estado, pago, REINFO…).</small>
                          {L_.concesiones.slice(0, 40).map((k) => (
                            <div key={k.codigo} id={`con-${k.codigo}`}
                              className={`fila-con ${concesionAbierta === k.codigo ? "abierta" : ""} ${k.indicio_pago?.nivel === "alerta" ? "con-alerta" : ""}`}
                              onClick={() => setConcesionAbierta((c) => (c === k.codigo ? null : k.codigo))}>
                              <b>{k.nombre}</b> <small>{k.codigo}</small>
                              <span>{k.titular || "—"}</span>
                              <small>{k.estado} · {k.sustancia || "—"} · {k.ha_en_cuadricula.toLocaleString("es-PE")} ha aquí
                                {k.fecha_petitorio ? ` · petitorio ${k.fecha_petitorio}` : ""}
                                {k.indicio_pago?.nivel === "alerta" ? " · ⚠ posible caducidad" : ""}
                                {k.reinfo?.length ? ` · ${k.reinfo.length} REINFO` : ""}</small>
                              {k.sustancia === "no metálica" && (k.material_probable || k.indicio_silice) && (
                                <small className={`chip-nm ${k.indicio_silice?.nivel ?? ""}`}>
                                  {k.indicio_silice?.nivel === "alto" ? "probable sílice / arena silícea" : k.material_probable?.material ?? "posible arena"}
                                  {k.actividad?.nivel === "alta" ? " · en explotación" : ""}
                                </small>
                              )}
                              {concesionAbierta === k.codigo && fichaConcesion(k)}
                            </div>
                          ))}
                          {L_.concesiones.length > 40 && <small>…y {L_.concesiones.length - 40} más (ver capa «Catastro minero»).</small>}
                        </div>
                      )}
                      <div className="pie-libres">
                        <small title={L_.nota_uso ?? ""}>INGEMMET, {fecha}{L_.catastro_actualizado ? ` (catastro al ${L_.catastro_actualizado})` : ""} · se renueva cada {DIAS_LIBRES} días</small>
                        {celdaArea && (
                          <button className="btn-libres" disabled={actualizandoLibres === celdaArea.codigo}
                            onClick={() => refrescarLibres(celdaArea)}>
                            {actualizandoLibres === celdaArea.codigo ? "Actualizando…" : <><RefreshCw size={12} /> Actualizar</>}
                          </button>
                        )}
                        <button className="btn-libres" onClick={() => setCapas((x) => ({ ...x, areas_libres: !x.areas_libres }))}>
                          {capas.areas_libres ? "Ocultar en el mapa" : "Ver en el mapa"}
                        </button>
                      </div>
                    </details>
                  );
                })() : celdaArea && res.libres === undefined && !res.soloSatelite && (
                  <div className="libres-celda">
                    <small>Este análisis es anterior a las áreas libres.</small>
                    <button className="btn-libres" disabled={actualizandoLibres === celdaArea.codigo} onClick={() => refrescarLibres(celdaArea)}>
                      {actualizandoLibres === celdaArea.codigo ? "Consultando…" : "Calcular áreas libres"}
                    </button>
                  </div>
                )}
                {res.restricciones && res.restricciones.length > 0 && (
                  <details className={`restricciones plegable ${res.restricciones.some((r) => r.nivel === "prohibido") ? "prohibido" : ""}`}>
                    <summary>
                      <b>{res.restricciones.some((r) => r.nivel === "prohibido") ? <ShieldX size={13} /> : <ShieldAlert size={13} />} Áreas protegidas o restringidas ({res.restricciones.length})</b>
                      <small>{res.restricciones.reduce((t, r) => t + r.pct_cuadricula, 0).toLocaleString("es-PE", { maximumFractionDigits: 1 })} % de la cuadrícula · ya descontadas de la Prioridad libre</small>
                    </summary>
                    {res.restricciones.filter((r) => r.pct_cuadricula >= 1 || r.nivel === "prohibido").slice(0, 8).map((r) => (
                      <div key={r.tipo + r.nombre} className="fila-restr">
                        <span className={r.nivel === "prohibido" ? "nivel prohibido" : "nivel restringido"}>
                          {r.nivel === "prohibido" ? "No concesionable" : "Restringido"}
                        </span>
                        <span>
                          <b>{r.nombre}</b> · {r.tipo}{r.categoria ? ` (${r.categoria.toLowerCase()})` : ""}
                          <small>{r.pct_cuadricula < 0.1 ? "<0,1" : r.pct_cuadricula} % de la cuadrícula{r.norma ? ` · ${r.norma}` : ""}</small>
                        </span>
                      </div>
                    ))}
                    {res.restricciones.filter((r) => !(r.pct_cuadricula >= 1 || r.nivel === "prohibido")).length > 0 && (
                      <small>…y {res.restricciones.filter((r) => !(r.pct_cuadricula >= 1 || r.nivel === "prohibido")).length} áreas restringidas menores (ver capa en el mapa).</small>
                    )}
                    <small className="nota-legal">
                      No concesionable: no se otorgan derechos. Restringido: requiere opinión previa (SERNANP u otra). Referencial: confirmar con INGEMMET y SERNANP.
                    </small>
                  </details>
                )}
                {res.soloSatelite && celdaArea && (
                  <button className="primario ancho" disabled={fase === "buscando" || cargandoS2}
                    onClick={() => analizarCelda(celdaArea, true)}>
                    Agregar la geología (zonas A/B/C) a {celdaArea.codigo}
                  </button>
                )}
                {res.avisos.map((a) => <p key={a} className="nota alerta">{a}</p>)}
                {formacionSel && (
                  <p className="nota alerta">
                    Filtrado a <b>{formacionSel.nombre}</b>: {afloramientosVisibles.length} de {res.afloramientos.length} zonas.{" "}
                    <button className="enlace" onClick={() => elegirFormacion(null)}>Ver todas</button>
                  </p>
                )}
                {!afloramientosVisibles.length && <p className="vacio">Sin zonas favorables{formacionSel ? " de esta formación" : ""} en esta área.</p>}
                {(afloramientosVisibles.length > 1 || celdaArea) && (
                  <div className="orden">
                    {afloramientosVisibles.length > 1 && <>Ordenar:
                    <button className={orden === "vidrio" ? "on" : ""} onClick={() => setOrden("vidrio")}
                      title="Aptitud para vidrio flotado según la descripción: arena o arenisca cuarzosa, grano medio-grueso, clara, sin hierro ni rocas finas intercaladas">Vidrio</button>
                    {prioLibre && (
                      <button className={orden === "oportunidad" ? "on" : ""} onClick={() => setOrden("oportunidad")}>Ha libres</button>
                    )}
                    <button className={orden === "clase" || (orden === "oportunidad" && !prioLibre) ? "on" : ""} onClick={() => setOrden("clase")}>Clase</button>
                    <button className={orden === "distancia" ? "on" : ""} onClick={() => setOrden("distancia")}>Más cerca</button></>}
                    {celdaArea && (
                      <button className={curvas && curvasDe === celdaArea.codigo ? "curvas on" : "curvas"} onClick={alternarCurvas} disabled={curvas === "cargando"}
                        title={curvas && curvas !== "cargando" && curvasDe === celdaArea.codigo
                          ? `Curvas cada ${curvas.intervalo_m} m (gruesas cada ${curvas.intervalo_m * 5} m) · ${curvas.cota_min}–${curvas.cota_max} m s. n. m. · Copernicus DEM 30 m`
                          : "Curvas de nivel (Copernicus DEM 30 m; la 1.ª vez en una zona tarda ~1 min)"}>
                        <Mountain size={13} /> {curvas === "cargando" ? "…" : "Curvas"}
                      </button>
                    )}
                  </div>
                )}
                {nNoAptas > 0 && (
                  <p className="nota no-aptas">{verNoAptas
                    ? <>Se muestran también {nNoAptas} zona{nNoAptas > 1 ? "s" : ""} no apta{nNoAptas > 1 ? "s" : ""} para vidrio. <button className="enlace" onClick={() => setVerNoAptas(false)}>Ocultarlas</button></>
                    : <>{nNoAptas} zona{nNoAptas > 1 ? "s" : ""} no apta{nNoAptas > 1 ? "s" : ""} para vidrio por su descripción (limolitas, lutitas, calizas o rocas con hierro como roca principal) oculta{nNoAptas > 1 ? "s" : ""}. <button className="enlace" onClick={() => setVerNoAptas(true)}>Ver</button></>}
                  </p>
                )}
                {afloramientosOrdenados.map((a) => {
                  const st = statsPorId[a.id];
                  const vd = vidrioPorId[a.id];
                  return (
                    <div key={a.id} className={zonaSel === a.id ? "item sel" : "item"} onClick={() => irA(a)}>
                      <span className="badge" style={{ background: COLOR_CLASE[a.clase] }}>{a.clase}</span>
                      <div className="cuerpo">
                        <b>{a.unidad}</b> <small>{a.area_ha.toLocaleString("es-PE")} ha</small>
                        <span className="km">{formatoKm(km(a.centro[1], a.centro[0]))}</span>
                        {(() => {
                          const k = claveTon(a);
                          const tn = tonelajes[k];
                          if (!tn) return null;
                          if (tn === "cargando") return <small className="ton-dato">Midiendo el relieve… (la 1.ª vez en una zona baja el DEM, ~1 min)</small>;
                          if ("error" in tn) {
                            return <button className="enlace ton-btn" onClick={(e) => { e.stopPropagation(); calcularTonelaje(a); }}><Mountain size={13} /> Reintentar tonelaje ({tn.error})</button>;
                          }
                          const rec = tn.metodos[tn.recomendado];
                          const p = paramTon[k] ?? {};
                          return (
                            <div className="tonelaje" onClick={(e) => e.stopPropagation()}>
                              <div className="ton-principal">
                                <Mountain size={13} /> <b>≈ {fmtT(rec.total.toneladas)}</b> <small>({fmtM3(rec.total.volumen_m3)} · espesor medio {rec.total.espesor_medio_m} m)</small>
                                {rec.libre && <div>en área libre: <b>≈ {fmtT(rec.libre.toneladas)}</b> <small>({rec.libre.area_ha.toLocaleString("es-PE")} ha)</small></div>}
                                <small>método: <b>{rec.metodo}</b> — {tn.por_que}</small>
                              </div>
                              <table className="ton-tabla">
                                <thead><tr><th>Método</th><th>Toda la zona</th>{rec.libre && <th>Solo libre</th>}<th>Esp. medio</th></tr></thead>
                                <tbody>
                                  {(["cerro", "dunas", "manto"] as const).map((m) => {
                                    const x = tn.metodos[m];
                                    return (
                                      <tr key={m} className={m === tn.recomendado ? "rec" : ""} title={x.explica}>
                                        <td>{m === tn.recomendado ? "★ " : ""}{x.metodo}</td>
                                        <td>{fmtT(x.total.toneladas)}</td>
                                        {rec.libre && <td>{x.libre ? fmtT(x.libre.toneladas) : "—"}</td>}
                                        <td>{x.total.espesor_medio_m} m</td>
                                      </tr>
                                    );
                                  })}
                                </tbody>
                              </table>
                              <div className="ton-params">
                                <label>Potencia del manto (m)
                                  <input inputMode="decimal" placeholder={String(tn.potencia_manto_m)} value={p.potencia_manto ?? ""}
                                    onChange={(e) => setParamTon((x) => ({ ...x, [k]: { ...x[k], potencia_manto: e.target.value } }))} /></label>
                                <label>Densidad (t/m³)
                                  <input inputMode="decimal" placeholder={String(tn.densidad_t_m3)} value={p.densidad ?? ""}
                                    onChange={(e) => setParamTon((x) => ({ ...x, [k]: { ...x[k], densidad: e.target.value } }))} /></label>
                                <button className="btn-libres" onClick={() => calcularTonelaje(a)}>Recalcular</button>
                              </div>
                              <small className="ton-nota">Cotas {tn.cota_min_m}–{tn.cota_max_m} m s. n. m. · {tn.dem}. {tn.nota}</small>
                            </div>
                          );
                        })()}
                        {vd && (
                          <div className={`vidrio-zona ${vd.nivel}`} title={`Lectura de la descripción de INGEMMET (no es análisis químico) · puntaje ${vd.puntaje}/100`}>
                            <div className="vz-cab"><span className="vz-nivel">{NIVEL_TEXTO[vd.nivel]}</span>
                              {vd.roca && <b>{vd.roca}</b>}
                              {vd.a_favor.length > 1 && <small className="vz-mas">{vd.a_favor.slice(1).join(" · ")}</small>}</div>
                            {!!vd.en_contra.length && <small className="vz-menos">En contra: {vd.en_contra.join(" · ")}</small>}
                            {vd.estratos.length
                              ? <div className="vz-estrato"><span className="eti">Estrato</span>{vd.estratos.map((e, i) => (
                                  <mark key={i} className={e.tipo} title={`${e.roca} · ${e.tipo === "potente" ? "estratos potentes: favorable para cantera" : e.tipo === "delgado" ? "estratos delgados: más mezcla con otras rocas" : "espesor medio"}`}>{e.texto}</mark>))}
                                  {vd.espesor && <small> · unidad ≈ {vd.espesor}</small>}</div>
                              : vd.roca && <small className="vz-sin">Estrato: la descripción no lo indica{vd.espesor ? ` · unidad ≈ ${vd.espesor}` : ""}</small>}
                          </div>
                        )}
                        {a.restriccion?.nivel === "prohibido" && (
                          <div className="restr-zona prohibido"><ShieldX size={12} /> {a.restriccion.pct} % en área NO concesionable: {a.restriccion.nombres.slice(0, 2).join(", ")}</div>
                        )}
                        {(() => {
                          const z = prioLibre?.porZona[a.id];
                          if (!z || z.haAlta <= 0) return null;
                          const t = Math.max(z.haAlta, 1e-9);
                          return (
                            <div className={`prio-zona ${z.haLibre > 0 ? "si" : "no"}`}>
                              <div title={`De ${z.haAlta.toLocaleString("es-PE")} ha${prioLibre?.sinSatelite ? "" : " limpias"} de la zona`}><b className="ha-libre">{Math.round(z.haLibre).toLocaleString("es-PE")} ha libres</b>
                                <small> · {Math.round(z.haNegociable).toLocaleString("es-PE")} concesión · {Math.round(z.haNoApto).toLocaleString("es-PE")} chacra/vía
                                  {z.haExtinguido >= 1 ? ` · ${Math.round(z.haExtinguido).toLocaleString("es-PE")} extinguidas` : ""}</small></div>
                              <div className="barra-prio mini" aria-hidden>
                                <i className="verde" style={{ width: `${(100 * z.haLibre) / t}%` }} />
                                <i className="azul" style={{ width: `${(100 * z.haNegociable) / t}%` }} />
                                <i className="amarillo" style={{ width: `${(100 * z.haNoApto) / t}%` }} />
                                <i className="celeste" style={{ width: `${(100 * z.haExtinguido) / t}%` }} />
                              </div>
                            </div>
                          );
                        })()}
                        {st && (
                          <div className="s2-zona" title={`De lo visible para Sentinel-2 (${st.pct_validos} % de la zona)`}>
                            <Satellite size={12} /> <b>{st.limpia_pct != null ? Math.round(st.limpia_pct) : "—"} % limpia</b>
                            <small> · Fe {st.anomalia_hierro_pct != null ? Math.round(st.anomalia_hierro_pct) : "—"} % · arcilla {st.anomalia_arcilla_pct != null ? Math.round(st.anomalia_arcilla_pct) : "—"} %
                              {st.ndvi_pct != null ? ` · NDVI ${Math.round(st.ndvi_pct)} · BSI ${Math.round(st.bsi_pct ?? 0)} · ferrug. ${Math.round(st.ferruginosa_pct ?? 0)}` : ""}</small>
                          </div>
                        )}
                        {!!a.concesiones?.length && (
                          <div className="con-zona" onClick={(e) => e.stopPropagation()}>
                            {(() => {
                              const act = a.concesiones.filter((k) => !k.extinguido);
                              const ext = a.concesiones.filter((k) => k.extinguido);
                              const lista = (ks: typeof act) => ks.slice(0, 2).map((k, i) => (
                                <span key={k.codigo}>{i > 0 && " · "}
                                  <button className="enlace" title={`${k.estado} · ${k.pct} % de la zona`} onClick={() => abrirConcesion(k.codigo)}>{k.nombre}</button>
                                </span>
                              ));
                              return (
                                <>
                                  {!!act.length && <div><Pickaxe size={12} /> {lista(act)}{act.length > 2 && <small> +{act.length - 2}</small>}</div>}
                                  {!!ext.length && <div className="ext-zona" title="Extinguido: libre con observación (falta publicar la libre denunciabilidad)">Extinguido: {lista(ext)}</div>}
                                </>
                              );
                            })()}
                          </div>
                        )}
                        <div className="acciones-zona" onClick={(e) => e.stopPropagation()}>
                          {botonRuta(a.centro[1], a.centro[0])}
                          {!tonelajes[claveTon(a)] && (
                            <button className="enlace" onClick={() => calcularTonelaje(a)} title="Volumen y toneladas con el relieve (Copernicus DEM 30 m)"><Mountain size={13} /> Tonelaje</button>
                          )}
                        </div>
                        <details className="geo-zona" onClick={(e) => e.stopPropagation()}>
                          <summary>{a.litologia || a.roca_dominante || "Geología"} <small>· {a.escala === "50K" ? "1:50 000" : "1:100 000"}</small></summary>
                          <div className="ficha-geo">
                            {((a.rocas?.length ? a.rocas : a.roca_dominante ? [a.roca_dominante] : []) as string[]).map((r, k) => (
                              <div key={k}><span>{["Roca principal", "Roca secundaria", "Roca terciaria"][k]}</span><b>{r}</b></div>
                            ))}
                            {a.descripcion && a.descripcion !== a.litologia && (
                              <div className="desc"><span>Descripción <small>(verde = roca silícea · rojo = no sirve para vidrio)</small></span>
                                {(vd?.tramos.length ? vd.tramos : [{ texto: a.descripcion, tono: "neutro" as const }]).map((t, i) => (
                                  <span key={i} className={`tramo ${t.tono}`} title={t.roca}>{t.texto}</span>
                                ))}
                              </div>
                            )}
                            <div className="desc"><span>Por qué es {a.clase}</span>{a.motivo}</div>
                          </div>
                        </details>
                      </div>
                    </div>
                  );
                })}
              </>
            )}
            {pestana === "sentinel" && (
              <>
                {res.soloSatelite ? (
                  <p className="nota">
                    <b>Solo satélite:</b> NDVI, BSI, anomalías ferruginosas, arcillas y fotos de toda la cuadrícula, sin la geología (no hay Prioridad libre).
                    Para saber qué formación es y dónde está libre, agrega la geología en la pestaña «Zonas». No mide SiO₂.
                  </p>
                ) : null}
                {!s2 && (celdaArea ? (
                  <button className="primario ancho" disabled={cargandoS2} onClick={() => analizarCelda(celdaArea, true)}>
                    {cargandoS2 ? "Procesando Sentinel-2…" : `Agregar Sentinel-2 a la cuadrícula ${celdaArea.codigo}`}
                  </button>
                ) : (
                  <p className="nota alerta">
                    Sentinel-2 se analiza por <b>cuadrícula 1:25 000</b> (~190 km², para cuidar los créditos de Copernicus).
                    Toca una cuadrícula en el mapa y usa «Analizar cuadrícula».
                  </p>
                ))}
                {cargandoS2 && s2 === null && celdaArea && <p className="nota">Buscando la toma Sentinel-2 más despejada sobre la cuadrícula (últimos 18 meses) y descargándola…</p>}
                {s2 && !s2.disponible && <p className="nota alerta">Sentinel-2 no está activo en el servidor: {s2.motivo}</p>}
                {s2?.disponible && (
                  <>
                    {capasUnidad && !res.soloSatelite && (
                      <div className="ambito-s2" role="radiogroup" aria-label="Ámbito de los índices">
                        <span className="eti">NDVI, BSI, ferruginosa y arcillas en</span>
                        <button className={indicesPorUnidad ? "on" : ""} onClick={() => cambiarAmbito(true)}
                          title="Solo dentro de las unidades elegidas para la Prioridad, con percentiles de cada unidad (coinciden con el corte)">Unidades elegidas ({unidadesPrio.size})</button>
                        <button className={!indicesPorUnidad ? "on" : ""} onClick={() => cambiarAmbito(false)}
                          title="Toda la cuadrícula, con percentiles de la cuadrícula (referencia)">Toda la cuadrícula</button>
                      </div>
                    )}
                    <div className="ver-s2">

                      {VISTAS_S2.filter((v) => hayVista(v.id)).map((v) => {
                        const foco = ({ s2_arcillas: "arcilla", s2_ferruginosas: "ferruginosa", s2_ndvi: "ndvi" } as Partial<Record<IdVista, FocoCorte>>)[v.id];
                        return (
                          <span key={v.id} className="grupo-btn">
                            <button className={capas[v.id] ? "on" : ""} aria-pressed={capas[v.id]}
                              title={v.grupo === "bandas" ? "Foto de fondo (una a la vez)" : "Se suma a las demás"}
                              onClick={() => alternarVista(v.id)}>
                              <i className="muestra" style={{ background: v.muestra }} />{v.nombre.replace(/ \(.*\)$/, "")}
                              {v.grupo === "bandas" && <small> 📷</small>}
                            </button>
                            {foco && recalculable(s2) && (
                              <button className="histo-capa" title={`Histograma de ${v.nombre.replace(/ \(.*\)$/, "").toLowerCase()}: mover el corte y ver la capa sola`}
                                onClick={() => abrirCortes(foco)} aria-label={`Histograma de ${v.nombre}`}><SlidersHorizontal size={14} /></button>
                            )}
                          </span>
                        );
                      })}
                      <button className={!sentinelVisible ? "on" : ""} onClick={() => setCapas((c) => ({ ...c, ...soloVista(null) }))}>Ninguna</button>
                    </div>
                    {s2?.disponible && !s2.solo_satelite && !s2.capas?.ndvi && (
                      <div className="aviso-capas">
                        <span><b>NDVI</b>, <b>BSI</b> y <b>Anomalías ferruginosas</b> no están en este análisis (es anterior a esas capas).</span>
                        <button disabled={cargandoS2} onClick={() => { if (confirm("¿Buscar una toma nueva para generar NDVI, BSI y Anomalías ferruginosas? Reemplaza la imagen guardada y gasta créditos de Copernicus (o usa AWS gratis si no hay cupo).")) nuevaToma(); }}>
                          <RefreshCw size={13} /> Nueva toma</button>
                      </div>
                    )}
                    {vistasActivas.length > 0 && (
                      <div className="opacidades">
                        <small className="eti">Opacidad</small>
                        {vistasActivas.map((v) => (
                          <div key={v.id} className="fila-opac"><i className="muestra" style={{ background: v.muestra }} /><span>{v.nombre.replace(/ \(.*\)$/, "")}</span>{deslizador(v.id)}</div>
                        ))}
                      </div>
                    )}
                    {verCortes && celdaArea ? (
                      <CortesS2 key={celdaArea.codigo} s2={s2} haCelda={haCelda(celdaArea)}
                        onVista={(x) => setS2(x)}
                        onListo={(x, c) => {
                          setS2(x); guardarCortes(c); setVerCortes(false);
                          if (res.soloSatelite) recordar(celdaArea.codigo, res, x); else registrarCelda(celdaArea, res, x);
                        }}
                        onCerrar={() => setVerCortes(false)}
                        foco={cortesFoco} capaVista={capaCorte} onVerCapa={verCapaCorte}
                        prioridad={res.soloSatelite ? undefined : prioLibre ? { libre: prioLibre.haLibre, negociable: prioLibre.haNegociable, total: prioLibre.haAlta } : null} />
                    ) : (
                      <div className="corte-actual">
                        {(() => {
                          const ct = cortesDe(s2);
                          const ce = s2.celda;
                          const c4 = ct ?? cortesGuardados();
                          const P = (x: number) => `P${Math.round(x * 100)}`;
                          return (
                            <span>
                              <b>Filtros de la Prioridad libre</b>: NDVI &lt; {P(c4.p_ndvi)} · ferruginosa &lt; {P(c4.p_ferruginosa)} · arcilla &lt; {P(c4.arcilla)}
                              <br /><small>Pasa los tres el <b>{ce?.pct_cumple ?? "—"} %</b> de la cuadrícula
                                {!conNdviBsi(s2) && " (análisis anterior: sin NDVI; «Nueva toma» para los tres)"}</small>
                            </span>
                          );
                        })()}
                        <button onClick={() => abrirCortes(null)}>Ajustar con histograma</button>
                      </div>
                    )}
                    {s2.imagen && celdaArea && (
                      <details className={`toma plegable ${s2.imagen.despejada === false || s2.imagen.metodo === "mosaico" ? "alerta" : "ok"}`}>
                        <summary>
                          <b><CalendarDays size={13} /> Toma {s2.imagen.metodo === "una_fecha" ? s2.imagen.fecha_peru : "mosaico de varias fechas"}</b>
                          <small>{s2.imagen.nubes_cuadricula != null ? `nubes ${s2.imagen.nubes_cuadricula.toLocaleString("es-PE")} %` : ""}
                            {s2.imagen.vegetacion_cuadricula != null ? ` · vegetación ${s2.imagen.vegetacion_cuadricula.toLocaleString("es-PE")} %` : ""}
                            {guardados.has(celdaArea.codigo) ? " · guardado" : cacheCeldas.current.has(celdaArea.codigo) ? " · guardando…" : " · sin guardar"}</small>
                        </summary>
                        <small>
                          {s2.imagen.metodo === "una_fecha"
                            ? <>Sentinel-2 L2A, hora de Perú (UTC {s2.imagen.fecha_utc?.slice(0, 16).replace("T", " ")}). {s2.imagen.despejada
                              ? `La despejada con menos vegetación (época seca primero) entre ${nCandidatas(s2.imagen.candidatas)} tomas de 18 meses.`
                              : `Ninguna de las ${nCandidatas(s2.imagen.candidatas)} tomas estuvo despejada: se usó la de menos nubes (las nubes se excluyen).`}
                              {s2.fuente ? ` Fuente: ${s2.fuente}.` : ""}</>
                            : s2.imagen.nota}
                          {" "}Guardado en este dispositivo: se vuelve a abrir sin gastar créditos.
                        </small>
                        <div className="botones-celda">
                          {!guardados.has(celdaArea.codigo) && !cacheCeldas.current.has(celdaArea.codigo) && (
                            <button className="primario" onClick={() => recordar(celdaArea.codigo, res, s2)}><Save size={13} /> Guardar</button>
                          )}
                          <button disabled={cargandoS2} onClick={() => {
                            if (confirm("¿Buscar una toma nueva? Reemplaza la imagen guardada y gasta créditos de Copernicus.")) nuevaToma();
                          }}><RefreshCw size={13} /> Nueva toma</button>
                          <button disabled={!guardados.has(celdaArea.codigo)} onClick={() => {
                            if (confirm(`¿Borrar el análisis guardado de ${celdaArea.codigo}? Seguirás viéndolo hasta salir de la cuadrícula; después habría que analizarla de nuevo.`)) {
                              olvidarAnalisis(celdaArea.codigo);
                            }
                          }}><Trash2 size={13} /> Borrar</button>
                        </div>
                      </details>
                    )}
                    {s2.celda && (
                      <div className="resumen-celda">
                        <div className="cifras">
                          {s2.celda.pct_interes != null && <span><b>{s2.celda.pct_interes}% → {s2.celda.pct_silice_limpia}%</b><small>zonas A y B → pasan los filtros</small></span>}
                          <span><b>{s2.celda.pct_cumple ?? "—"}%</b><small>pasa los tres filtros</small></span>
                          <span><b>{s2.celda.pct_vegetacion_nubes_agua}%</b><small>no visible (vegetación, nubes, agua)</small></span>
                        </div>
                      </div>
                    )}
                    {!!s2.afloramientos?.length && (
                      <table className="tabla-s2">
                        <thead><tr><th /><th>Zona</th><th title="% de la zona que pasa los tres filtros (NDVI, ferruginosa, arcilla)">Pasa</th><th title="% de lo visible con hierro sobre el corte">Fe</th>
                          <th title="% de lo visible con arcilla sobre el corte">Arc.</th><th title="NDVI: vegetación (0–100 en la cuadrícula)">NDVI</th><th title="BSI: suelo o roca desnuda (0–100 en la cuadrícula)">BSI</th>
                          <th title="Ferruginosa B4/B2 + B4/B3 (0–100 en la cuadrícula)">Ferr.</th></tr></thead>
                        <tbody>
                          {(s2.afloramientos ?? []).map((st) => {
                            const a = res.afloramientos.find((x) => x.id === st.id);
                            if (!a) return null;
                            const n = (v?: number | null) => (v == null ? "—" : Math.round(v));
                            return (
                              <tr key={st.id} onClick={() => irA(a)} title={`${a.unidad} · ${a.area_ha.toLocaleString("es-PE")} ha · ${st.pct_validos} % visible`}>
                                <td><span className="badge" style={{ background: COLOR_CLASE[a.clase] }}>{a.clase}</span></td>
                                <td className="nom">{a.unidad.replace(/^Grupo [^-]+ - /, "")}</td>
                                <td className="bueno">{n(st.limpia_pct)}</td><td>{n(st.anomalia_hierro_pct)}</td><td>{n(st.anomalia_arcilla_pct)}</td>
                                <td>{n(st.ndvi_pct)}</td><td>{n(st.bsi_pct)}</td><td>{n(st.ferruginosa_pct)}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    )}
                  </>
                )}
              </>
            )}
            <p className="fuente">{res.fuente} · {res.segundos}s</p>
          </div>
        </div>
      )}

      {cursor && (() => {
        const [la, lo] = cursor;
        const u = utm(la, lo);
        const c = celdaEn(la, lo, "25K");
        return (
          <div className="barra-coord" aria-label="Coordenadas">
            <span title="Coordenadas geográficas (WGS84)">{gms(la, true)} · {gms(lo, false)}</span>
            <span title="UTM WGS84 (como en las cartas de INGEMMET y el GPS)">UTM {u.zona}{u.hemisferio} · E {Math.round(u.este).toLocaleString("es-PE")} · N {Math.round(u.norte).toLocaleString("es-PE")}</span>
            {tieneTierra(c) && <span className="cod" title="Cuadrícula 1:25 000 bajo el cursor">{c.codigo}</span>}
          </div>
        );
      })()}

      {fase === "inicio" && !res && !area && !celdaSel && !formacionSel && !verCatalogo && !sugerir && !resaltado && !bienvenidaVista && (
        <div className="bienvenida">
          <button className="cerrar-bienvenida" aria-label="Cerrar" onClick={() => {
            setBienvenidaVista(true);
            try { localStorage.setItem("prospector-rmi:bienvenida-vista", "1"); } catch { /* sin almacenamiento */ }
          }}><X size={14} /></button>
          <span><b>Toca una cuadrícula</b> del mapa o escribe su código arriba, y elige <b>«Analizar cuadrícula»</b>.</span>
          <small>Clic derecho (o un toque) enfoca la cuadrícula · ★ guarda en carpetas · la biblioteca reúne tus carpetas y las formaciones de interés.</small>
        </div>
      )}
    </div>
  );
}
