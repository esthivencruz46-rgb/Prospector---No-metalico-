// Unidades supermaduras del Perú (informe con 51 boletines de INGEMMET): ficha por unidad, citas textuales con página,
// química de canteras, ocurrencias de sílice y área por cuadrícula 1:25 000. El mapa de calor reutiliza la capa del
// barrido; tocar una cuadrícula o una cantera lleva a esa cuadrícula. `SupermadurasCelda` = tira de la hoja de resultados.
import { useEffect, useMemo, useState } from "react";
import { BookOpen, Camera, ChevronLeft, ChevronRight, Download, FlaskConical, Gem, X } from "lucide-react";
import { API_URL } from "./api";
import { celda25 } from "./geo";
import type { CeldaCalor } from "./Ranking";
import Paginador, { usePaginas } from "./Paginador";

/** [código 25K, km² de la unidad, afloramientos, carta, km a la fábrica, departamento, provincia] */
export type CeldaSM = [string, number, number, string, number, string, string];
export interface CitaSM { bol: string; ref: string; pag: number | null; tema: string; texto: string; link: string }
export interface UnidadSM {
  id: string; nombre: string; tipo: "sed" | "meta"; prioridad: number; prioridad_txt: string;
  madurez: string; certeza: string; definicion: string; puntos: [string, string][];
  area_km2: number; n_hojas: number; n_celdas: number; celdas: CeldaSM[]; citas: CitaSM[];
}
export type GradoSM = "vidrio" | "refractario" | "fundente" | "no";
export interface QuimicaSM {
  nombre: string; lugar: string; hoja: string; celda: string; lat: number; lon: number; km: number; unidad: string; unidad_id: string | null;
  espesor: string; descripcion: string; nota: string; muestra: string; sio2: number; fe2o3: number; al2o3: number;
  sio2_txt: string; fe2o3_txt: string; al2o3_txt: string; grado: GradoSM; fuente: string; link: string;
}
export interface OcurrenciaSM { nombre: string; lugar: string; hoja: string; celda: string; lat: number; lon: number; km: number; unidad: string; estado: string; fuente: string; link: string }
/** Foto recortada de un boletín: dónde se ubica (cuadrícula exacta, hoja nombrada o cobertura del boletín). */
export interface FotoSM {
  archivo: string; unidad: string; leyenda: string; boletin: string; ref: string; pag: number; pag_foto: number; link: string;
  micro: boolean; cantera: boolean; nota: string; celda: string | null; hojas100: string[];
  precision: "cantera" | "utm_texto" | "hoja_nombrada" | "boletin" | "unidad"; motivo?: string;
}
export interface DatosSM {
  generado: string; n_boletines: number; unidades: UnidadSM[]; quimica: QuimicaSM[]; ocurrencias: OcurrenciaSM[];
  especificaciones: { uso: string; texto: string; fuente: string }[]; fotos?: FotoSM[];
}
export interface EnCeldaSM {
  codigo: string; disponible: boolean; quimica: QuimicaSM[]; ocurrencias: OcurrenciaSM[]; fotos?: FotoSM[];
  unidades: { id: string; nombre: string; tipo: "sed" | "meta"; prioridad: number; prioridad_txt: string; km2: number; afloramientos: number; carta: string }[];
}

let promesa: Promise<DatosSM> | null = null;
/** Descarga una sola vez por sesión (~240 KB). */
export function cargarSupermaduras(): Promise<DatosSM> {
  if (!promesa) {
    promesa = fetch(`${API_URL}/supermaduras`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.status === 503 ? "faltan los datos en el servidor" : `Error ${r.status}`))))
      .catch((e) => { promesa = null; throw e; });
  }
  return promesa;
}

// peso de cada unidad en el mapa de calor «todas» (1 = mejor evidencia de supermadurez)
const PESO: Record<number, number> = { 1: 1, 2: 0.7, 3: 0.45, 4: 0.25, 5: 0.15 };
export const GRADO_TXT: Record<GradoSM, string> = {
  vidrio: "Candidata a vidrio", refractario: "Refractario / vidrio de color", fundente: "Fundente / ferrosilicio", no: "No es sílice industrial",
};
const DIST = [100, 200, 400, 0] as const;
export const urlFoto = (archivo: string) => `${API_URL}/supermaduras/foto/${encodeURIComponent(archivo)}`;
const UBICACION_TXT: Record<FotoSM["precision"], string> = {
  cantera: "cantera con coordenadas", utm_texto: "coordenadas UTM del boletín", hoja_nombrada: "hoja 1:100 000 nombrada en la leyenda",
  boletin: "hojas que cubre el boletín", unidad: "sin ubicación (solo la unidad)",
};

/** Visor a pantalla completa: foto, leyenda textual del boletín, fuente con enlace y ubicación. ← → para pasar. */
export function VisorFotos({ fotos, inicio, onCerrar }: { fotos: FotoSM[]; inicio: number; onCerrar: () => void }) {
  const [i, setI] = useState(inicio);
  const f = fotos[i];
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCerrar();
      if (e.key === "ArrowRight") setI((x) => Math.min(fotos.length - 1, x + 1));
      if (e.key === "ArrowLeft") setI((x) => Math.max(0, x - 1));
    };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [fotos.length, onCerrar]);
  if (!f) return null;
  return (
    <div className="visor-fotos" onClick={onCerrar}>
      <div className="visor-caja" onClick={(e) => e.stopPropagation()}>
        <div className="visor-cab">
          <b><Camera size={15} /> Foto {i + 1} de {fotos.length}</b>
          <button onClick={onCerrar} aria-label="Cerrar"><X size={16} /></button>
        </div>
        <div className="visor-img">
          <button className="visor-nav" disabled={i === 0} onClick={() => setI(i - 1)} aria-label="Anterior"><ChevronLeft size={22} /></button>
          <img src={urlFoto(f.archivo)} alt={f.leyenda} />
          <button className="visor-nav" disabled={i === fotos.length - 1} onClick={() => setI(i + 1)} aria-label="Siguiente"><ChevronRight size={22} /></button>
        </div>
        <q className="visor-ley">{f.leyenda}</q>
        <small className="visor-fuente">
          <a href={f.link} target="_blank" rel="noreferrer">{f.ref}</a>, pág. {f.pag}{f.pag_foto !== f.pag ? ` (foto en la pág. ${f.pag_foto})` : ""}
          {" · "}{f.motivo ?? `Ubicación: ${UBICACION_TXT[f.precision]}`}{f.celda ? ` · cuadrícula ${f.celda}` : ""}
          {f.nota ? ` · ${f.nota}` : ""}
        </small>
        <small className="visor-nota">Leyenda leída del PDF por OCR (puede tener letras erradas).</small>
      </div>
    </div>
  );
}

/** Miniaturas que abren el visor. */
function Galeria({ fotos, max = 99 }: { fotos: FotoSM[]; max?: number }) {
  const [abierta, setAbierta] = useState<number | null>(null);
  return (
    <>
      <div className="galeria-sm">
        {fotos.slice(0, max).map((f, k) => (
          <button key={f.archivo} className={f.micro ? "mini micro" : f.cantera ? "mini cant" : "mini"} onClick={() => setAbierta(k)}
            title={f.leyenda}>
            <img src={urlFoto(f.archivo)} alt="" />
            {f.micro && <i>lámina</i>}{f.cantera && <i>cantera</i>}
          </button>
        ))}
        {fotos.length > max && <button className="mini mas" onClick={() => setAbierta(max)}>+{fotos.length - max}</button>}
      </div>
      {abierta != null && <VisorFotos fotos={fotos} inicio={abierta} onCerrar={() => setAbierta(null)} />}
    </>
  );
}
const corto = (n: string) => n.replace(/\s*\(.*\)$/, "").replace(" – micaesquisto y cuarcita", "");
const num = (v: number, d = 1) => v.toLocaleString("es-PE", { maximumFractionDigits: d });

interface FilaCelda {
  codigo: string; valor: number; km2: number; afl: number; carta: string; km: number; dep: string; prov: string;
  unidades: { id: string; nombre: string; km2: number; prioridad: number }[];
}

export default function Supermaduras({ onIr, onMapa, onCerrar, unidadInicial }: {
  onIr: (codigo: string) => void; onMapa: (celdas: CeldaCalor[]) => void; onCerrar: () => void; unidadInicial?: string | null;
}) {
  const [datos, setDatos] = useState<DatosSM | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pestana, setPestana] = useState<"unidades" | "canteras">("unidades");
  const [tipo, setTipo] = useState<"sed" | "meta" | "todas">("sed");
  const [dist, setDist] = useState<(typeof DIST)[number]>(0);
  const [abierta, setAbierta] = useState<string | null>(unidadInicial ?? null);
  const [orden, setOrden] = useState<"km2" | "dist">("km2");
  const [verCitas, setVerCitas] = useState(false);
  const [verSpec, setVerSpec] = useState(false);

  useEffect(() => { cargarSupermaduras().then(setDatos).catch((e) => setError((e as Error).message)); }, []);
  useEffect(() => {
    if (!unidadInicial) return;
    setAbierta(unidadInicial); setPestana("unidades"); setVerCitas(false);
  }, [unidadInicial]);

  const unidades = useMemo(() => (datos ? datos.unidades.filter((u) => tipo === "todas" || u.tipo === tipo) : []), [datos, tipo]);
  const uAbierta = datos?.unidades.find((u) => u.id === abierta) ?? null;

  const celdas: FilaCelda[] = useMemo(() => {
    if (!datos) return [];
    const ok = (km: number) => !dist || km <= dist;
    const m = new Map<string, FilaCelda>();
    for (const u of uAbierta ? [uAbierta] : unidades) {
      for (const [cod, km2, afl, carta, km, dep, prov] of u.celdas) {
        if (!ok(km)) continue;
        let x = m.get(cod);
        if (!x) { x = { codigo: cod, valor: 0, km2: 0, afl: 0, carta, km, dep, prov, unidades: [] }; m.set(cod, x); }
        x.valor += uAbierta ? km2 : km2 * PESO[u.prioridad];
        x.km2 += km2; x.afl += afl;
        if (x.carta !== carta) x.carta = "50K/100K";
        x.unidades.push({ id: u.id, nombre: corto(u.nombre), km2, prioridad: u.prioridad });
      }
    }
    const arr = [...m.values()];
    for (const x of arr) x.unidades.sort((a, b) => a.prioridad - b.prioridad || b.km2 - a.km2);
    return arr.sort(orden === "km2" ? (a, b) => b.valor - a.valor : (a, b) => a.km - b.km || b.valor - a.valor);
  }, [datos, unidades, uAbierta, dist, orden]);
  const pagC = usePaginas(celdas);   // páginas de 100 con flechas (antes solo 150)

  useEffect(() => {
    // el mapa pinta las 400 de más km² y, además, las de la página que se está viendo
    const vistas = new Set(pagC.items.map((f) => f.codigo));
    const porValor = [...celdas].sort((a, b) => b.valor - a.valor).filter((f, i) => i < 400 || vistas.has(f.codigo));
    onMapa(porValor.flatMap((f, i) => {
      const c = celda25(f.codigo);
      return c ? [{ codigo: f.codigo, sur: c.sur, oeste: c.oeste, norte: c.norte, este: c.este, puntaje: f.valor, puesto: i + 1 }] : [];
    }));
  }, [celdas, pagC.items]); // eslint-disable-line react-hooks/exhaustive-deps

  function csv() {
    const cab = "cuadricula;km2;km2_ponderado;afloramientos;carta;unidades;departamento;provincia;km_fabrica";
    const filas = celdas.map((f) => [f.codigo, num(f.km2, 2), num(f.valor, 2), f.afl, f.carta,
      f.unidades.map((u) => `${u.nombre} (${num(u.km2, 2)})`).join(" | "), f.dep, f.prov, f.km].join(";"));
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["﻿" + [cab, ...filas].join("\r\n")], { type: "text/csv" }));
    a.download = `supermaduras_${uAbierta ? uAbierta.id : tipo}.csv`;
    a.click();
  }

  const seg = <T extends string | number>(val: T, set: (v: T) => void, ops: [T, string][]) => (
    <div className="seg-rk seg-sm">{ops.map(([v, t]) => <button key={String(v)} className={val === v ? "on" : ""} onClick={() => set(v)}>{t}</button>)}</div>
  );

  const listaCeldas = (
    <>
      <div className="resumen-rk resumen-sm">
        <span><b>{celdas.length.toLocaleString("es-PE")}</b><small>cuadrículas</small></span>
        <span><b>{num(celdas.reduce((s, f) => s + f.km2, 0), 0)}</b><small>km² cartografiados</small></span>
        <button onClick={csv} title="Descargar la lista"><Download size={14} /> CSV</button>
      </div>
      <div className="filtros-rk">
        <label>Ordenar</label>{seg(orden, setOrden, [["km2", uAbierta ? "Más km²" : "Más km² (ponderado)"], ["dist", "Más cerca de la fábrica"]])}
      </div>
      <Paginador p={pagC} />
      <ol className="lista-rk lista-sm" ref={pagC.ref} start={pagC.inicio + 1}>
        {pagC.items.map((f, i) => (
          <li key={f.codigo} onClick={() => onIr(f.codigo)} title="Ir a la cuadrícula">
            <span className="puesto-rk">{pagC.inicio + i + 1}</span>
            <span className="cod-rk">{f.codigo}</span>
            <span className="km2-rk">{num(f.km2, 2)} km²</span>
            <span className="tags-rk">
              {!uAbierta && f.unidades.slice(0, 3).map((u) => <i key={u.id} className={`p${u.prioridad}`}>{u.nombre}</i>)}
              {!uAbierta && f.unidades.length > 3 && <i>+{f.unidades.length - 3}</i>}
              <i className={f.carta === "50K" ? "t50" : "t100"}>{f.carta === "50K" ? "1:50 000" : f.carta === "100K" ? "1:100 000" : "1:50 000/100 000"}</i>
              {uAbierta && <i>{f.afl} afl.</i>}
              <i className="tkm">{f.km} km</i>
              <i>{f.prov}</i>
            </span>
          </li>
        ))}
      </ol>
      <Paginador p={pagC} />
    </>
  );

  const fichaQuimica = (q: QuimicaSM) => (
    <li key={q.nombre} onClick={() => onIr(q.celda)} title="Ir a la cuadrícula">
      <div className="fila-q">
        <b>{q.nombre}</b>
        <span className={`grado-sm g-${q.grado}`}>{GRADO_TXT[q.grado]}</span>
      </div>
      <div className="ox-sm">
        <span>SiO₂ <b>{q.sio2_txt}</b> %</span><span>Fe₂O₃ <b>{q.fe2o3_txt}</b> %</span><span>Al₂O₃ <b>{q.al2o3_txt}</b> %</span>
      </div>
      <small>{q.unidad}{q.espesor && q.espesor !== "—" ? ` · ${q.espesor}` : ""} · {q.lugar} · <b className="cod-rk">{q.celda}</b> · {q.km} km</small>
      <small className="fuente-sm">{q.descripcion}{q.nota ? `. ${q.nota}` : ""} — <a href={q.link} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>{q.fuente}</a></small>
    </li>
  );

  return (
    <div className="panel-ranking panel-super">
      <div className="cab-pet"><b><Gem size={17} /> Unidades supermaduras</b><button onClick={onCerrar} aria-label="Cerrar"><X size={16} /></button></div>
      <small className="explica">Arenas y areniscas casi solo de cuarzo, según {datos ? datos.n_boletines : 51} boletines de INGEMMET
        (citas textuales con página) y la geología 1:50 000 (1:100 000 solo donde no hay 1:50 000). <b>Prioridad</b> = lectura del
        informe (1 = mejor evidencia); es una guía, no el ranking definitivo.</small>
      {error && <p className="error-mp">No se pudieron leer los datos: {error}</p>}
      {!datos && !error && <p className="explica">Cargando…</p>}
      {datos && (
        <>
          {seg(pestana, setPestana, [["unidades", `Unidades (${datos.unidades.length})`], ["canteras", `Canteras (${datos.quimica.length + datos.ocurrencias.length})`]])}

          {pestana === "unidades" && !uAbierta && (
            <>
              <div className="filtros-rk">
                <label>Tipo</label>{seg(tipo, setTipo, [["sed", "Sedimentarias"], ["meta", "Metamórficas"], ["todas", "Todas"]])}
                <label>Fábrica</label>{seg(dist, setDist, DIST.map((d) => [d, d ? `≤ ${d} km` : "Todo"] as [typeof d, string]))}
              </div>
              <ul className="unidades-sm">
                {unidades.map((u) => (
                  <li key={u.id} onClick={() => { setAbierta(u.id); setVerCitas(false); setOrden("km2"); }}>
                    <div className="fila-q"><b>{corto(u.nombre)}</b><span className={`prio-sm p${u.prioridad}`} title={u.prioridad_txt}>{u.prioridad} · {u.prioridad_txt}</span></div>
                    <small>{num(u.area_km2, 0)} km² · {u.n_celdas} cuadrículas · {u.citas.length} citas</small>
                  </li>
                ))}
              </ul>
              <small className="sub-grupo">Cuadrículas con más supermadura (km² ponderados por prioridad)</small>
              {listaCeldas}
            </>
          )}

          {pestana === "unidades" && uAbierta && (
            <>
              <button className="volver-sm" onClick={() => setAbierta(null)}><ChevronLeft size={15} /> Todas las unidades</button>
              <div className="ficha-sm">
                <div className="fila-q"><b>{uAbierta.nombre}</b><span className={`prio-sm p${uAbierta.prioridad}`}>{uAbierta.prioridad} · {uAbierta.prioridad_txt}</span></div>
                <p><span className="k-sm">Madurez.</span> {uAbierta.madurez}</p>
                <p><span className="k-sm">Certeza.</span> {uAbierta.certeza}</p>
                <p><span className="k-sm">Definición y edad.</span> {uAbierta.definicion}</p>
                {uAbierta.puntos.map(([t, x]) => <p key={t}><span className="k-sm">{t}.</span> {x}</p>)}
                <small>{num(uAbierta.area_km2, 0)} km² en {uAbierta.n_hojas} cuadrantes/hojas · {uAbierta.n_celdas} cuadrículas 1:25 000</small>
              </div>
              {(() => {
                const qs = datos.quimica.filter((q) => q.unidad_id === uAbierta.id);
                return qs.length > 0 && (
                  <>
                    <small className="sub-grupo"><FlaskConical size={13} /> Química de canteras ({qs.length})</small>
                    <ul className="quimica-sm">{qs.map(fichaQuimica)}</ul>
                  </>
                );
              })()}
              {(() => {
                const fs = (datos.fotos ?? []).filter((f) => f.unidad === uAbierta.id)
                  .sort((a, b) => Number(b.micro) - Number(a.micro) || Number(b.cantera) - Number(a.cantera));
                return fs.length > 0 && (
                  <>
                    <small className="sub-grupo"><Camera size={13} /> Fotos de los boletines ({fs.length}) · láminas delgadas, canteras y afloramientos</small>
                    <Galeria fotos={fs} />
                  </>
                );
              })()}
              {uAbierta.citas.length > 0 && (
                <>
                  <button className="volver-sm" onClick={() => setVerCitas((v) => !v)}>
                    <BookOpen size={14} /> {verCitas ? "Ocultar" : "Ver"} lo que dicen los boletines ({uAbierta.citas.length} citas)
                  </button>
                  {verCitas && (
                    <ul className="citas-sm">
                      {uAbierta.citas.map((c, i) => (
                        <li key={i}>
                          <small><a href={c.link} target="_blank" rel="noreferrer">{c.ref}</a>{c.pag ? `, pág. ${c.pag}` : ""} · {c.tema}</small>
                          <q>{c.texto}</q>
                        </li>
                      ))}
                    </ul>
                  )}
                </>
              )}
              {uAbierta.citas.length === 0 && <small className="nota-pet">Sin boletín descargado con descripción propia: solo la carta geológica.</small>}
              <div className="filtros-rk">
                <label>Fábrica</label>{seg(dist, setDist, DIST.map((d) => [d, d ? `≤ ${d} km` : "Todo"] as [typeof d, string]))}
              </div>
              {listaCeldas}
            </>
          )}

          {pestana === "canteras" && (
            <>
              <small className="sub-grupo"><FlaskConical size={13} /> Con análisis químico (laboratorio de INGEMMET, una muestra por cantera)</small>
              <ul className="quimica-sm">{datos.quimica.map(fichaQuimica)}</ul>
              <small className="sub-grupo">Registradas sin análisis químico</small>
              <ul className="quimica-sm">
                {datos.ocurrencias.map((o) => (
                  <li key={o.nombre} onClick={() => onIr(o.celda)} title="Ir a la cuadrícula">
                    <div className="fila-q"><b>{o.nombre}</b><span className="grado-sm">{o.estado}</span></div>
                    <small>{o.unidad} · {o.lugar} · <b className="cod-rk">{o.celda}</b> · {o.km} km</small>
                    <small className="fuente-sm"><a href={o.link} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>{o.fuente}</a></small>
                  </li>
                ))}
              </ul>
              <button className="volver-sm" onClick={() => setVerSpec((v) => !v)}>{verSpec ? "Ocultar" : "Ver"} especificaciones y precios (INGEMMET)</button>
              {verSpec && (
                <ul className="citas-sm">
                  {datos.especificaciones.map((s) => <li key={s.uso}><small><b>{s.uso}</b> · {s.fuente}</small><span>{s.texto}</span></li>)}
                </ul>
              )}
              <small className="nota-pet">«Uso posible» es un tamizado de este informe: vidrio = SiO₂ ≥ 95 % y Fe₂O₃ ≤ 0,10 %; refractario = SiO₂ ≥ 95 % y
                Fe₂O₃ ≤ 0,5 %; fundente = SiO₂ ≥ 90 % y Fe₂O₃ ≤ 1,5 %. No reemplaza los ensayos.</small>
            </>
          )}
        </>
      )}
    </div>
  );
}

/** Tira de la hoja de resultados: unidades supermaduras, canteras y ocurrencias dentro de la cuadrícula analizada. */
export function SupermadurasCelda({ codigo, onAbrir }: { codigo: string; onAbrir: (unidad: string | null) => void }) {
  const [d, setD] = useState<EnCeldaSM | null>(null);
  const [verFotos, setVerFotos] = useState(false);
  useEffect(() => {
    let vivo = true;
    setD(null); setVerFotos(false);
    fetch(`${API_URL}/supermaduras/celda/${encodeURIComponent(codigo)}`)
      .then((r) => (r.ok ? r.json() : null)).then((x) => { if (vivo) setD(x); }).catch(() => { /* sin datos: no se muestra */ });
    return () => { vivo = false; };
  }, [codigo]);
  if (!d || (!d.unidades.length && !d.quimica.length && !d.ocurrencias.length && !d.fotos?.length)) return null;
  // UNA línea (24/11/2026, «se ve muy cargado»): unidades, química y un botón de fotos; la galería se abre a pedido
  return (
    <>
    <div className="sm-celda">
      <span className="tit-sm" title="Unidades supermaduras (arenas y areniscas casi solo de cuarzo) en esta cuadrícula"><Gem size={13} /></span>
      {d.unidades.map((u) => (
        <button key={u.id} className={`chip-sm p${u.prioridad}`} title={`${u.nombre} · prioridad ${u.prioridad}: ${u.prioridad_txt} · ${u.afloramientos} afloramientos (${u.carta})`}
          onClick={() => onAbrir(u.id)}>{corto(u.nombre)} · {num(u.km2, 1)} km²</button>
      ))}
      {d.quimica.map((q) => (
        <button key={q.nombre} className={`chip-sm g-${q.grado}`} onClick={() => onAbrir(null)}
          title={`${q.nombre}: SiO₂ ${q.sio2_txt} %, Fe₂O₃ ${q.fe2o3_txt} %, Al₂O₃ ${q.al2o3_txt} % · ${GRADO_TXT[q.grado]} · ${q.fuente}`}>
          ⚗ SiO₂ {q.sio2_txt} %
        </button>
      ))}
      {d.ocurrencias.map((o) => (
        <span key={o.nombre} className="chip-sm" title={`${o.nombre} · ${o.unidad} · ${o.estado} · ${o.fuente}`}>⛏</span>
      ))}
      {!!d.fotos?.length && (
        <button className={verFotos ? "chip-sm fotos on" : "chip-sm fotos"} onClick={() => setVerFotos((v) => !v)}
          title={`Fotos de los boletines de INGEMMET (${d.fotos.filter((f) => f.motivo === "Tomada en esta cuadrícula").length} tomadas en esta cuadrícula)`}>
          <Camera size={12} /> {d.fotos.length}
        </button>
      )}
    </div>
    {verFotos && !!d.fotos?.length && (
      <div className="sm-fotos">
        <Galeria fotos={d.fotos} max={6} />
      </div>
    )}
    </>
  );
}
