// Ranking nacional: cuadrículas 1:25 000 ordenadas por SUPERMADURAS libres y utilizables (área de cada unidad del
// informe de supermaduras × su prioridad; censos guardados en el servidor, sin consultar a INGEMMET). Criterio
// anterior disponible: geología silícea A/B libre y utilizable. Filtros por prioridad, carta, selva, tipo y distancia;
// el mapa se pinta como mapa de calor (reutiliza la capa del barrido) y tocar una fila lleva a la cuadrícula.
import { useEffect, useMemo, useState } from "react";
import { Download, FlaskConical, Trophy, X } from "lucide-react";
import { API_URL } from "./api";
import { celda25 } from "./geo";
import { aptitudVidrio, NIVEL_TEXTO, type AptitudVidrio } from "./vidrio";
import Paginador, { usePaginas } from "./Paginador";

export interface UnidadRanking { id: string; nombre: string; prioridad: number; rango?: number; km2: number }
export interface FilaRanking {
  codigo: string; carta: "50K" | "100K"; km2: number; aprox: boolean; util_pct: number | null; libre_pct: number | null;
  n_concesiones: number | null; prohibido: boolean; bosque_pct: number | null; selva: boolean; km_fabrica: number;
  puesto: number; tipos_km2?: { arena: number; arenisca: number; cuarcita: number };
  sm?: UnidadRanking[]; sm_km2?: number; sm_puntaje?: number; sm_prioridad?: number;
}
/** Vidrio flotado: cuadrícula cuya carta describe la roca silícea blanca con grano medio a grueso (backend ranking.vidrio). */
export interface FilaVidrio {
  codigo: string; km2: number; km2_libre_aprox: number | null; unidad: string; rango: number; unidades: string;
  grano: "medio" | "medio a grueso" | "grueso"; granos: string; km2_casi_blanco: number; km2_fino_a_medio: number;
  frase: string; afloramientos: number; carta: string; lat: number; lon: number; km_fabrica: number; quimica: string;
  puesto: number; bosque_pct: number | null; selva: boolean;
}
/** POR DESCRIPCIÓN (24/11/2026): aptitud para vidrio de la descripción de INGEMMET de la mejor unidad libre (backend ranking.descripcion). */
export interface FilaDesc {
  codigo: string; carta: string; nivel: AptitudVidrio["nivel"]; puntaje: number; unidad: string; descripcion: string; roca: string | null;
  a_favor: string[]; en_contra: string[]; estratos: AptitudVidrio["estratos"]; espesor: string | null; km2_libre: number; km2: number;
  km2_nivel: Partial<Record<AptitudVidrio["nivel"], number>>; otras: { unidad: string; nivel: AptitudVidrio["nivel"]; puntaje: number; km2_libre: number }[];
  bosque_pct: number | null; selva: boolean; km_fabrica: number; puesto: number;
}
interface Datos {
  total: number; con_tipos: boolean; con_supermaduras?: boolean; con_vidrio?: boolean; vidrio?: FilaVidrio[];
  con_descripcion?: boolean; descripcion?: FilaDesc[];
  pesos_prioridad?: Record<string, number>;
  km2_total: number; filas: FilaRanking[]; min_km2_sm?: number;
  orden_supermadurez?: { id: string; rango: number; motivo: string }[];
}
export type CeldaCalor = { codigo: string; sur: number; oeste: number; norte: number; este: number; puntaje: number | null; puesto: number | null };

const DIST = [50, 100, 200, 400, 0] as const;
const MINIMOS = [0.1, 0.5, 1, 5] as const;

export default function Ranking({ onIr, onMapa, onCerrar }: {
  onIr: (codigo: string) => void; onMapa: (celdas: CeldaCalor[]) => void; onCerrar: () => void;
}) {
  const [datos, setDatos] = useState<Datos | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [criterio, setCriterio] = useState<"desc" | "sm" | "vf" | "ab">("desc");
  const [nivelMin, setNivelMin] = useState<"alta" | "media" | "baja" | "todas">("alta");
  const [soloSinMezcla, setSoloSinMezcla] = useState(false);
  const [soloEstrato, setSoloEstrato] = useState(false);
  const [grano, setGrano] = useState<"todos" | "medio" | "medio a grueso" | "grueso">("todos");
  const [soloQuimica, setSoloQuimica] = useState(false);
  const [soloLibre, setSoloLibre] = useState(false);
  const [prio, setPrio] = useState<1 | 2 | 3 | 5>(5);
  const [minKm2, setMinKm2] = useState<(typeof MINIMOS)[number]>(0.5);
  const [verOrden, setVerOrden] = useState(false);
  const [carta, setCarta] = useState<"todas" | "50K" | "100K">("todas");
  const [selva, setSelva] = useState<"sin" | "con" | "todas">("sin");
  const [tipo, setTipo] = useState<"todos" | "arena" | "arenisca" | "cuarcita">("todos");
  const [dist, setDist] = useState<(typeof DIST)[number]>(0);
  const [exactas, setExactas] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/ranking`).then((r) => (r.ok ? r.json() : Promise.reject(new Error(`Error ${r.status}`))))
      .then((d: Datos) => { setDatos(d); if (!d.con_descripcion) setCriterio(d.con_supermaduras ? "sm" : "ab"); })
      .catch((e) => setError((e as Error).message));
  }, []);

  const rango = useMemo(() => new Map((datos?.orden_supermadurez ?? []).map((o) => [o.id, o.rango])), [datos]);
  const lista = useMemo(() => {
    if (!datos) return [];
    const r = (u: UnidadRanking) => u.rango ?? rango.get(u.id) ?? 99;
    const base = datos.filas
      .filter((f) => (carta === "todas" || f.carta === carta) && (selva === "todas" || (selva === "con") === f.selva)
        && (!dist || f.km_fabrica <= dist) && (criterio === "sm" || !exactas || !f.aprox));
    if (criterio === "sm") {
      // supermadurez primero (rango de la mejor unidad libre y utilizable); el área solo desempata
      return base.flatMap((f) => {
        const uds = (f.sm ?? []).filter((u) => u.prioridad <= prio && u.km2 >= minKm2).sort((a, b) => r(a) - r(b) || b.km2 - a.km2);
        return uds.length ? [{ ...f, uds, mejor: uds[0] as UnidadRanking | null, rangoMejor: r(uds[0]), valor: uds[0].km2, kmSm: uds.reduce((s, u) => s + u.km2, 0) }] : [];
      }).sort((a, b) => a.rangoMejor - b.rangoMejor || b.valor - a.valor);
    }
    const valor = (f: FilaRanking) => (tipo === "todos" || !f.tipos_km2 ? f.km2 : f.tipos_km2[tipo]);
    return base.map((f) => ({ ...f, uds: [] as UnidadRanking[], mejor: null as UnidadRanking | null, rangoMejor: 0, valor: valor(f), kmSm: 0 }))
      .filter((f) => f.valor > 0).sort((a, b) => b.valor - a.valor);
  }, [datos, criterio, prio, minKm2, carta, selva, tipo, dist, exactas, rango]);

  // VIDRIO FLOTADO: ya viene ordenado (supermadurez → km² libres ≈ → grano); aquí solo se filtra
  const listaVf = useMemo(() => (datos?.vidrio ?? []).filter((f) => (grano === "todos" || f.grano === grano)
    && (selva === "todas" || (selva === "con") === f.selva) && (!dist || f.km_fabrica <= dist)
    && (!soloQuimica || !!f.quimica) && (!soloLibre || (f.km2_libre_aprox ?? 0) > 0)), [datos, grano, selva, dist, soloQuimica, soloLibre]);

  // POR DESCRIPCIÓN: ya viene ordenado (nivel → puntaje → km² libres); aquí solo se filtra
  const R_NIVEL = { alta: 0, media: 1, baja: 2, no: 3 } as const;
  const listaDesc = useMemo(() => (datos?.descripcion ?? []).filter((f) =>
    (nivelMin === "todas" || R_NIVEL[f.nivel] <= R_NIVEL[nivelMin]) && (selva === "todas" || (selva === "con") === f.selva)
    && (!dist || f.km_fabrica <= dist) && (!soloEstrato || f.estratos.length > 0)
    && (!soloSinMezcla || !aptitudVidrio(f.descripcion).tramos.some((t) => t.tono === "malo"))), // eslint-disable-line react-hooks/exhaustive-deps
  [datos, nivelMin, selva, dist, soloEstrato, soloSinMezcla]);

  // páginas de 100 con flechas: se recorren TODAS las cuadrículas (antes solo las 150 primeras)
  const pag = usePaginas(lista);
  const pagVf = usePaginas(listaVf);
  const pagDesc = usePaginas(listaDesc);

  useEffect(() => {
    if (criterio === "desc") {   // más fuerte = mejor puntaje de la descripción
      onMapa(listaDesc.slice(0, Math.max(400, pagDesc.fin)).flatMap((f, i) => {
        const c = celda25(f.codigo);
        return c ? [{ codigo: f.codigo, sur: c.sur, oeste: c.oeste, norte: c.norte, este: c.este, puntaje: Math.max(f.puntaje, 1), puesto: i + 1 }] : [];
      }));
      return;
    }
    if (criterio === "vf") {   // más fuerte = más arriba en el orden
      onMapa(listaVf.slice(0, Math.max(400, pagVf.fin)).flatMap((f, i) => {
        const c = celda25(f.codigo);
        return c ? [{ codigo: f.codigo, sur: c.sur, oeste: c.oeste, norte: c.norte, este: c.este, puntaje: 1 / (i + 1) ** 0.5, puesto: i + 1 }] : [];
      }));
      return;
    }
    onMapa(lista.slice(0, Math.max(400, pag.fin)).flatMap((f, i) => {
      const c = celda25(f.codigo);
      const puntaje = criterio === "sm" ? 1 / f.rangoMejor : f.valor;   // en «sm» pinta más fuerte la más supermadura
      return c ? [{ codigo: f.codigo, sur: c.sur, oeste: c.oeste, norte: c.norte, este: c.este, puntaje, puesto: i + 1 }] : [];
    }));
  }, [lista, listaVf, listaDesc, criterio, pag.fin, pagVf.fin, pagDesc.fin]); // eslint-disable-line react-hooks/exhaustive-deps

  function csv() {
    if (criterio === "desc") {
      const n = (v: number | null) => (v == null ? "" : String(Math.round(v * 100) / 100).replace(".", ","));
      const q = (t: string) => `"${(t ?? "").replace(/"/g, "'")}"`;
      const cab = "puesto;cuadricula;aptitud;puntaje;unidad;roca;km2_libres_utilizables;km2_unidad;a_favor;en_contra;estratos;espesor_unidad;selva;km_fabrica;carta;descripcion_INGEMMET";
      const filas = listaDesc.map((f, i) => [i + 1, f.codigo, NIVEL_TEXTO[f.nivel], f.puntaje, q(f.unidad), f.roca ?? "", n(f.km2_libre), n(f.km2),
        q(f.a_favor.slice(1).join(" · ")), q(f.en_contra.join(" · ")), q(f.estratos.map((e) => e.texto).join(" · ")), f.espesor ?? "",
        f.selva ? "sí" : "no", f.km_fabrica, f.carta === "50K" ? "1:50 000" : "1:100 000", q(f.descripcion)].join(";"));
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob(["\ufeff" + [cab, ...filas].join("\r\n")], { type: "text/csv" }));
      a.download = "ranking_por_descripcion_vidrio.csv";
      a.click();
      return;
    }
    if (criterio === "vf") {
      const n = (v: number | null) => (v == null ? "" : String(Math.round(v * 100) / 100).replace(".", ","));
      const q = (t: string) => `"${t.replace(/"/g, "'")}"`;
      const cab = "puesto;cuadricula;mejor_unidad;rango_supermadurez;grano;km2_blanco_grano_medio_grueso;km2_libres_utilizables_aprox;km2_casi_blanco;km2_blanco_fino_a_medio;selva;km_fabrica;descripcion_carta;quimica;unidades";
      const filas = listaVf.map((f, i) => [i + 1, f.codigo, f.unidad, f.rango, f.grano, n(f.km2), n(f.km2_libre_aprox), n(f.km2_casi_blanco),
        n(f.km2_fino_a_medio), f.selva ? "sí" : "no", f.km_fabrica, q(f.frase), q(f.quimica), q(f.unidades)].join(";"));
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob(["﻿" + [cab, ...filas].join("\r\n")], { type: "text/csv" }));
      a.download = "ranking_vidrio_flotado.csv";
      a.click();
      return;
    }
    const sm = criterio === "sm";
    const cab = sm
      ? "puesto;cuadricula;mejor_unidad;rango_supermadurez;km2_mejor_unidad_libre_utilizable;km2_supermaduras_libres_utilizables;unidades;carta_AB;selva;bosque_pct;utilizable_pct;concesiones;km_fabrica"
      : "puesto;cuadricula;carta;km2_AB_libre_utilizable;aproximado;selva;bosque_pct;utilizable_pct;concesiones;km_fabrica";
    const n = (v: number) => String(Math.round(v * 100) / 100).replace(".", ",");
    const filas = lista.map((f, i) => (sm
      ? [i + 1, f.codigo, f.mejor?.nombre ?? "", f.rangoMejor, n(f.valor), n(f.kmSm), f.uds.map((u) => `${u.nombre} [#${u.rango ?? ""}] ${n(u.km2)}`).join(" | "),
        f.carta === "50K" ? "1:50 000" : "1:100 000", f.selva ? "sí" : "no", f.bosque_pct ?? "", f.util_pct ?? "", f.n_concesiones ?? "", f.km_fabrica]
      : [i + 1, f.codigo, f.carta === "50K" ? "1:50 000" : "1:100 000", n(f.valor), f.aprox ? "sí" : "no", f.selva ? "sí" : "no",
        f.bosque_pct ?? "", f.util_pct ?? "", f.n_concesiones ?? "", f.km_fabrica]).join(";"));
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["﻿" + [cab, ...filas].join("\r\n")], { type: "text/csv" }));
    a.download = sm ? "ranking_supermaduras.csv" : "ranking_nacional_AB.csv";
    a.click();
  }

  const seg = <T extends string | number>(val: T, set: (v: T) => void, ops: [T, string][]) => (
    <div className="seg-rk">{ops.map(([v, t]) => <button key={String(v)} className={val === v ? "on" : ""} onClick={() => set(v)}>{t}</button>)}</div>
  );
  const num = (v: number) => v.toLocaleString("es-PE", { maximumFractionDigits: 1 });

  return (
    <div className="panel-ranking">
      <div className="cab-pet"><b><Trophy size={17} /> Ranking nacional</b><button onClick={onCerrar} aria-label="Cerrar"><X size={16} /></button></div>
      {criterio === "desc" ? (
        <small className="explica"><b>Por descripción</b>: cada cuadrícula según lo que dice INGEMMET de su mejor unidad con área
          libre y utilizable (≥ 0,5 km²). Sube la <b>arena o arenisca cuarzosa</b> blanca, de grano medio a grueso, en estratos potentes;
          baja si está <b>mezclada con limoarcillitas, lutitas o limolitas</b> (más si son negras, pardas o rojizas), si tiene colores de
          hierro o si la roca principal no es silícea. Verde = roca silícea · rojo = lo que malogra.</small>
      ) : criterio === "vf" ? (
        <small className="explica"><b>Vidrio flotado</b>: cuadrículas donde la carta describe la arenisca, cuarcita o arena de una unidad supermadura
          con color <b>cercano al blanco</b> (blanco, blanquecino, blanco grisáceo, gris blanquecino; ningún otro color en esa roca) y
          <b> grano medio a grueso</b>. Orden: supermadurez → km² libres y utilizables (≈) → grano. El flotado usa arena de ~0,1–0,5 mm
          (el grano grueso hay que molerlo) y pide SiO₂ ≥ 98,5–99 % y Fe₂O₃ ≤ 0,05–0,10 %: la química de las canteras dice cuánto falta.</small>
      ) : criterio === "sm" ? (
        <small className="explica">Cuadrículas 1:25 000 ordenadas por <b>criterio de supermadurez</b>: primero la que tiene la unidad más
          supermadura (ver el orden) <b>libre y utilizable</b> (fuera de derechos mineros, áreas protegidas, cultivos, poblados y vías);
          el área solo desempata entre cuadrículas con la misma unidad. Carta de cada unidad = la del informe (1:50 000; la 1:100 000
          solo sin 1:50 000). Censo guardado: no consulta a INGEMMET.</small>
      ) : (
        <small className="explica">Cuadrículas 1:25 000 con geología silícea A/B <b>libre y utilizable</b> (censo nacional; no consulta a INGEMMET).
          Una carta por cuadrícula: la 1:50 000 si tiene A/B; si no, la 1:100 000.</small>
      )}
      {error && <p className="error-mp">No se pudo leer el ranking: {error}</p>}
      {!datos && !error && <p className="explica">Cargando…</p>}
      {datos && (
        <>
          <div className="filtros-rk">
            {datos.con_supermaduras && <><label>Criterio</label>{seg(criterio, setCriterio, [
              ...(datos.con_descripcion ? [["desc", "Descripción (vidrio)"] as ["desc", string]] : []), ["sm", "Supermaduras"],
              ...(datos.con_vidrio ? [["vf", "Vidrio flotado"] as ["vf", string]] : []), ["ab", "A/B silícea (anterior)"]])}</>}
            {criterio === "desc" && <><label>Aptitud</label>{seg(nivelMin, setNivelMin, [["alta", "Solo apta"], ["media", "Apta + media"], ["baja", "+ baja"], ["todas", "Todas"]])}</>}
            {criterio === "vf" && <><label>Grano</label>{seg(grano, setGrano, [["todos", "Todos"], ["medio", "Medio"], ["medio a grueso", "Medio a grueso"], ["grueso", "Grueso"]])}</>}
            {criterio === "sm" && <><label>Prioridad</label>{seg(prio, setPrio, [[1, "Solo 1"], [2, "1–2"], [3, "1–3"], [5, "Todas"]])}</>}
            {criterio === "sm" && <><label>Mínimo</label>{seg(minKm2, setMinKm2, MINIMOS.map((m) => [m, `≥ ${String(m).replace(".", ",")} km²`] as [typeof m, string]))}</>}
            {criterio !== "vf" && criterio !== "desc" && <><label>Carta A/B</label>{seg(carta, setCarta, [["todas", "Todas"], ["50K", "1:50 000"], ["100K", "1:100 000"]])}</>}
            <label>Selva</label>{seg(selva, setSelva, [["sin", "Sin selva"], ["con", "Con selva"], ["todas", "Todas"]])}
            {criterio === "ab" && datos.con_tipos && <><label>Material</label>{seg(tipo, setTipo, [["todos", "Todos"], ["arena", "Arena"], ["arenisca", "Arenisca"], ["cuarcita", "Cuarcita"]])}</>}
            <label>Fábrica</label>{seg(dist, setDist, DIST.map((d) => [d, d ? `≤ ${d} km` : "Todo"] as [typeof d, string]))}
          </div>
          {criterio === "sm" && datos.orden_supermadurez && (
            <>
              <button className="volver-sm" onClick={() => setVerOrden((v) => !v)}>{verOrden ? "Ocultar" : "Ver"} el orden de supermadurez ({datos.orden_supermadurez.length} unidades)</button>
              {verOrden && (
                <ol className="orden-sm">
                  {datos.orden_supermadurez.map((o) => {
                    const u = datos.filas.flatMap((f) => f.sm ?? []).find((x) => x.id === o.id);
                    return <li key={o.id}><b>{u?.nombre ?? o.id.replace(/^m_/, "").replace(/_/g, " ")}</b><small>{o.motivo}</small></li>;
                  })}
                </ol>
              )}
            </>
          )}
          {criterio === "vf" && (
            <div className="checks-vf">
              <label className="exactas-rk"><input type="checkbox" checked={soloQuimica} onChange={(e) => setSoloQuimica(e.target.checked)} />
                Solo con química de canteras (INGEMMET)</label>
              <label className="exactas-rk"><input type="checkbox" checked={soloLibre} onChange={(e) => setSoloLibre(e.target.checked)} />
                Solo con área libre y utilizable</label>
            </div>
          )}
          {criterio === "ab" && (
            <label className="exactas-rk"><input type="checkbox" checked={exactas} onChange={(e) => setExactas(e.target.checked)} />
              Solo cifras exactas (sin las estimadas con la 1:100 000, «≈»)</label>
          )}
          {criterio === "desc" ? (
            <>
              <div className="checks-vf">
                <label className="exactas-rk"><input type="checkbox" checked={soloSinMezcla} onChange={(e) => setSoloSinMezcla(e.target.checked)} />
                  Solo sin rocas finas intercaladas (sin limolitas, lutitas, limoarcillitas…)</label>
                <label className="exactas-rk"><input type="checkbox" checked={soloEstrato} onChange={(e) => setSoloEstrato(e.target.checked)} />
                  Solo si la descripción indica el estrato</label>
              </div>
              <div className="resumen-rk">
                <span><b>{listaDesc.length.toLocaleString("es-PE")}</b><small>cuadrículas</small></span>
                <span><b>{Math.round(listaDesc.reduce((s, f) => s + f.km2_libre, 0)).toLocaleString("es-PE")}</b><small>km² libres de la mejor unidad</small></span>
                <button onClick={csv} title="Descargar la lista filtrada"><Download size={14} /> CSV</button>
              </div>
              <Paginador p={pagDesc} />
              <ol className="lista-rk lista-desc" ref={pagDesc.ref} start={pagDesc.inicio + 1}>
                {pagDesc.items.map((f, i) => {
                  const ap = aptitudVidrio(f.descripcion);
                  return (
                    <li key={f.codigo} onClick={() => onIr(f.codigo)}>
                      <span className="puesto-rk">{pagDesc.inicio + i + 1}</span>
                      <span className="cod-rk">{f.codigo}</span>
                      <span className="km2-rk">{f.unidad.replace(/^Grupo [^-]+ - /, "").replace(/^(Formación|Grupo)\s+/, "")}</span>
                      <span className="tags-rk">
                        <i className={`nv-${f.nivel}`} title={`Puntaje ${f.puntaje}/100`}>{NIVEL_TEXTO[f.nivel]}</i>
                        <i>{num(f.km2_libre)} km² libres</i>
                        {f.selva && <i className="tselva">selva</i>}
                        <i className="tkm">{f.km_fabrica} km</i>
                      </span>
                      <small className="desc-rk">{ap.tramos.map((t, k) => <span key={k} className={`tramo ${t.tono}`}>{t.texto}</span>)}</small>
                      {!!f.en_contra.length && <small className="contra-rk">En contra: {f.en_contra.join(" · ")}</small>}
                      {f.estratos.length > 0
                        ? <small className="estr-rk">Estrato: {f.estratos.map((e, k) => <mark key={k} className={e.tipo}>{e.texto}</mark>)}{f.espesor ? ` · unidad ≈ ${f.espesor}` : ""}</small>
                        : <small className="estr-rk sin">Estrato: no lo indica{f.espesor ? ` · unidad ≈ ${f.espesor}` : ""}</small>}
                    </li>
                  );
                })}
              </ol>
              <Paginador p={pagDesc} />
              <small className="nota-pet">Lectura del texto de la carta de INGEMMET (1:50 000; la 1:100 000 solo sin 1:50 000), no análisis químico:
                confirmar en campo y laboratorio. km² libres y utilizables del censo del 21–22/11/2026, repartidos por el área de cada descripción.</small>
            </>
          ) : criterio === "vf" ? (
            <>
              <div className="resumen-rk">
                <span><b>{listaVf.length.toLocaleString("es-PE")}</b><small>cuadrículas</small></span>
                <span><b>{Math.round(listaVf.reduce((s, f) => s + (f.km2_libre_aprox ?? 0), 0)).toLocaleString("es-PE")}</b><small>km² libres (≈)</small></span>
                <button onClick={csv} title="Descargar la lista filtrada"><Download size={14} /> CSV</button>
              </div>
              <Paginador p={pagVf} />
              <ol className="lista-rk lista-vf" ref={pagVf.ref} start={pagVf.inicio + 1}>
                {pagVf.items.map((f, i) => (
                  <li key={f.codigo} onClick={() => onIr(f.codigo)} title={f.frase}>
                    <span className="puesto-rk">{pagVf.inicio + i + 1}</span>
                    <span className="cod-rk">{f.codigo}</span>
                    <span className="km2-rk">#{f.rango} {f.unidad.replace(/\s*\(.*\)$/, "").replace(/^(Formación|Grupo|Depósitos)\s+/, "")}</span>
                    <span className="tags-rk">
                      <i className={`g-vf ${f.grano === "medio" ? "g1" : f.grano === "medio a grueso" ? "g2" : "g3"}`}>grano {f.grano}</i>
                      <i>{num(f.km2)} km²{f.km2_libre_aprox != null ? ` · ${num(f.km2_libre_aprox)} libres` : ""}</i>
                      {!!f.quimica && <i className="tq" title={f.quimica}><FlaskConical size={10} /> química</i>}
                      {f.selva && <i className="tselva">selva</i>}
                      <i className="tkm">{f.km_fabrica} km</i>
                    </span>
                    <small className="frase-vf">{f.frase}</small>
                  </li>
                ))}
              </ol>
              <Paginador p={pagVf} />
              <small className="nota-pet">Según la descripción de la carta (generaliza por polígono): confirmar color, grano y química en campo y laboratorio.
                «Libres (≈)» se estima con el % libre y utilizable de la misma unidad en la cuadrícula (censo del 21–22/11/2026).</small>
            </>
          ) : (<>
          <div className="resumen-rk">
            <span><b>{lista.length.toLocaleString("es-PE")}</b><small>cuadrículas</small></span>
            <span><b>{Math.round(lista.reduce((s, f) => s + (criterio === "sm" ? f.kmSm : f.valor), 0)).toLocaleString("es-PE")}</b>
              <small>{criterio === "sm" ? "km² supermaduras libres" : "km² A/B libres"}</small></span>
            <button onClick={csv} title="Descargar la lista filtrada"><Download size={14} /> CSV</button>
          </div>
          <Paginador p={pag} />
          <ol className="lista-rk" ref={pag.ref} start={pag.inicio + 1}>
            {pag.items.map((f, i) => (
              <li key={f.codigo} onClick={() => onIr(f.codigo)}>
                <span className="puesto-rk">{pag.inicio + i + 1}</span>
                <span className="cod-rk">{f.codigo}</span>
                <span className="km2-rk" title={criterio === "sm" ? "Rango de supermadurez de la mejor unidad libre y utilizable" : undefined}>
                  {criterio === "sm" ? `#${f.rangoMejor} ${(f.mejor?.nombre ?? "").replace(/^(Formación|Grupo|Depósitos)\s+/, "")}` : `${f.aprox ? "≈ " : ""}${num(f.valor)} km²`}
                </span>
                <span className="tags-rk">
                  {criterio === "sm" && f.uds.slice(0, 3).map((u) => (
                    <i key={u.id} className={`p${u.prioridad}`} title={`Rango de supermadurez #${u.rango ?? "?"} · prioridad ${u.prioridad} · libre y utilizable`}>{u.nombre} · {num(u.km2)} km²</i>
                  ))}
                  {criterio === "ab" && <i className={f.carta === "50K" ? "t50" : "t100"}>{f.carta === "50K" ? "1:50 000" : "1:100 000"}</i>}
                  {f.selva && <i className="tselva">selva</i>}
                  <i className="tkm">{f.km_fabrica} km</i>
                </span>
              </li>
            ))}
          </ol>
          <Paginador p={pag} />
          {criterio === "sm" && <small className="nota-pet">Solo entran las cuadrículas del censo de áreas libres (las que tenían geología A/B y al menos 1 %
            utilizable). El orden de supermadurez es la lectura del informe; si quieres otro, dime el orden y lo cambio.</small>}
          </>)}
        </>
      )}
    </div>
  );
}
