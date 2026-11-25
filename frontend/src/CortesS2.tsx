// Panel «Filtros de la Prioridad libre» (definición del usuario, 24/11/2026): histogramas REALES de la cuadrícula de
// los TRES índices que se intersecan (sin BSI desde el 24/11/2026): NDVI (pasa lo de abajo), anomalía ferruginosa y
// arcilla (pasan las clases bajas). Corte por PERCENTIL (P1–P100). La vista previa se recalcula en el navegador
// (cortes.ts) sin créditos; «Listo» la guarda.
import { useEffect, useRef, useState } from "react";
import { Check, Eye, Layers, RotateCcw, SlidersHorizontal, X } from "lucide-react";
import type { HistogramaS2, ResultadoSentinel } from "./api";
import { CLASES_COLOR, CORTES_DEFECTO, RAMPA_BSI, RAMPA_NDVI, colorRampa, aplicarCortes, conNdviBsi, cortesDe, cortesGuardados, recalculable, recalcular, type Cortes, type Recalculo } from "./cortes";

type Clave = keyof Cortes;
/** índice que se ajusta y capa del mapa que lo muestra */
export type FocoCorte = "ndvi" | "ferruginosa" | "arcilla";
export type CapaCorte = "s2_ndvi" | "s2_arcillas" | "s2_ferruginosas" | "todas";
const CAPA: Record<FocoCorte, CapaCorte> = { ndvi: "s2_ndvi", arcilla: "s2_arcillas", ferruginosa: "s2_ferruginosas" };
type Paleta = "clases" | "ndvi" | "bsi";
/** color de la barra = el MISMO que tiene en el mapa ese percentil (10 clases o la rampa de NDVI/BSI) */
const colorPaleta = (t: number, paleta: Paleta) => (paleta === "clases" ? CLASES_COLOR[Math.min(9, Math.max(0, Math.floor(t * 10)))]
  : colorRampa(t, paleta === "ndvi" ? RAMPA_NDVI : RAMPA_BSI));
const INDICES: { k: Clave; hist: FocoCorte; nombre: string; cociente: string; color: string; pasa: "abajo" | "arriba"; paleta: Paleta; nota: string }[] = [
  { k: "p_ndvi", hist: "ndvi", nombre: "NDVI", cociente: "(B8 − B4)/(B8 + B4)", color: "#a16207", pasa: "abajo", paleta: "ndvi",
    nota: "Pasa lo que queda BAJO el corte: sin vegetación y vegetación escasa (P57 por defecto)." },
  { k: "p_ferruginosa", hist: "ferruginosa", nombre: "Anomalía ferruginosa", cociente: "férrico + ferroso", color: "#dc2626", pasa: "abajo", paleta: "clases",
    nota: "Pasan las clases BAJO el corte: P30 = clases 1–3 (índigo, azul, celeste). Férrico B4/B2 + B4/B3 + ferroso B11/B8A, cada uno en percentil; eje = su suma (0–2)." },
  { k: "arcilla", hist: "arcilla", nombre: "Arcillas", cociente: "B11/B12", color: "#a21caf", pasa: "abajo", paleta: "clases",
    nota: "Pasan las clases BAJO el corte: P30 = clases 1–3 (índigo, azul, celeste). Absorción a 2,2 µm: arcillas, micas, sericita, sulfatos." },
];

const fmt = (x: number) => x.toLocaleString("es-PE", { maximumFractionDigits: 3 });

function Histograma({ h, umbral, pasa, paleta }: { h: HistogramaS2; umbral?: number; pasa?: "abajo" | "arriba"; paleta: Paleta }) {
  // percentil (0–1) del valor v según la tabla de percentiles del histograma
  const pctDe = (v: number) => {
    const ps = h.percentiles;
    let k = 0;
    while (k < 100 && ps[k + 1] <= v) k++;
    return k / 100;
  };
  // (24/11/2026, «histograma colorido para saber hasta qué intervalo colocar»): cada barra con el color que ese
  // percentil tiene en el mapa; lo que pasa el filtro, pleno; lo que no pasa, tenue. Debajo, la franja de colores.
  const W = 300, H = 74, FR = 6;
  const max = Math.max(...h.cuentas, 1);
  const nb = h.cuentas.length;
  const xDe = (v: number) => ((Math.min(Math.max(v, h.min), h.max) - h.min) / Math.max(h.max - h.min, 1e-9)) * W;
  const xc = umbral == null ? 0 : xDe(umbral);
  return (
    <svg viewBox={`0 0 ${W} ${H + FR + 15}`} className="histo" role="img" aria-label="Histograma">
      {h.cuentas.map((c, i) => {
        const x0 = (i / nb) * W, bw = W / nb;
        const centro = h.min + ((i + 0.5) / nb) * (h.max - h.min);
        const ok = umbral == null || (pasa === "abajo" ? centro < umbral : centro >= umbral);
        const color = colorPaleta(pctDe(centro), paleta);
        const alto = Math.max(1, (Math.sqrt(c) / Math.sqrt(max)) * H);   // raíz: se ven también las colas
        return (
          <g key={i}>
            <rect x={x0 + 0.3} y={H - alto} width={bw - 0.6} height={alto} fill={color} opacity={ok ? 0.95 : 0.28} />
            <rect x={x0} y={H + 1} width={bw + 0.2} height={FR} fill={color} opacity={ok ? 1 : 0.35} />
          </g>
        );
      })}
      {umbral != null && <line x1={xc} x2={xc} y1={0} y2={H + FR + 1} stroke="currentColor" strokeWidth={1.5} strokeDasharray="3 2" />}
      <text x={2} y={H + FR + 13} fontSize={10} fill="currentColor" opacity={0.7}>{fmt(h.min)}</text>
      <text x={W - 2} y={H + FR + 13} fontSize={10} fill="currentColor" opacity={0.7} textAnchor="end">{fmt(h.max)}</text>
      {umbral != null && <text x={Math.min(Math.max(xc, 40), W - 40)} y={H + FR + 13} fontSize={10} fill="currentColor" textAnchor="middle" fontWeight={600}>{fmt(umbral)}</text>}
    </svg>
  );
}

export default function CortesS2({ s2, haCelda, onVista, onListo, onCerrar, foco, onVerCapa, capaVista, prioridad }: {
  s2: ResultadoSentinel;                         // análisis tal como está guardado (sin la vista previa)
  haCelda: number;
  onVista: (s: ResultadoSentinel) => void;       // vista previa en el mapa
  onListo: (s: ResultadoSentinel, c: Cortes) => void;
  onCerrar: () => void;
  foco?: FocoCorte | null;                       // índice con el que se abrió (se resalta y se lleva a la vista)
  onVerCapa?: (capa: CapaCorte) => void;         // dejar en el mapa esa capa y la Prioridad libre
  capaVista?: CapaCorte | null;                  // capa que se está viendo
  /** Prioridad libre con los cortes de la vista previa (null = recalculándose; undefined = no aplica) */
  prioridad?: { libre: number; negociable: number; total: number } | null;
}) {
  const refs = useRef<Partial<Record<FocoCorte, HTMLDivElement | null>>>({});
  useEffect(() => {
    if (foco) refs.current[foco]?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [foco]);
  const botonCapa = (f: FocoCorte) => onVerCapa && (
    <button className={capaVista === CAPA[f] ? "ver-capa on" : "ver-capa"} onClick={() => onVerCapa(CAPA[f])}
      title="Deja en el mapa esta capa y la Prioridad libre, para ver cómo cambia la prioridad al mover el corte">
      <Eye size={13} /> {capaVista === CAPA[f] ? "En el mapa" : "Ver en el mapa"}
    </button>
  );
  const original = useRef(s2);
  const [c, setC] = useState<Cortes>(() => cortesDe(s2) ?? cortesGuardados());
  const [num, setNum] = useState<Recalculo | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hist = s2.datos?.hist;
  const ok = recalculable(s2) && !!hist;
  const f3 = conNdviBsi(s2);

  // números al instante; imágenes del mapa con una pausa (mover el deslizador no debe trabar)
  useEffect(() => {
    if (!ok) return;
    let vigente = true;
    recalcular(original.current, c, false).then((r) => vigente && setNum(r)).catch((e) => setError((e as Error).message));
    const t = setTimeout(() => {
      aplicarCortes(original.current, c).then((s) => vigente && onVista(s)).catch(() => { /* la vista previa no es crítica */ });
    }, 450);
    return () => { vigente = false; clearTimeout(t); };
  }, [c]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!ok) {
    return (
      <div className="panel-cortes">
        <div className="cab-cortes"><b><SlidersHorizontal size={16} /> Filtros de la Prioridad libre</b><button onClick={onCerrar} aria-label="Cerrar"><X size={16} /></button></div>
        <p className="nota alerta">Este análisis no trae los percentiles por píxel (es muy antiguo). Usa «Nueva toma» (o AWS gratis si no hay créditos) para poder ajustarlo.</p>
      </div>
    );
  }

  const ha = (pct?: number | null) => (pct == null ? "—" : `${pct.toLocaleString("es-PE")} % · ${Math.round((pct / 100) * haCelda).toLocaleString("es-PE")} ha`);
  async function listo() {
    setOcupado(true);
    try {
      onListo(await aplicarCortes(original.current, c), c);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setOcupado(false);
    }
  }
  function cancelar() {
    onVista(original.current);
    onCerrar();
  }

  return (
    <div className="panel-cortes">
      <div className="cab-cortes"><b><SlidersHorizontal size={16} /> Filtros de la Prioridad libre</b><button onClick={cancelar} aria-label="Cerrar sin cambiar"><X size={16} /></button></div>
      <small className="explica">
        Queda como Prioridad libre lo de las unidades elegidas que pasa <b>los tres filtros a la vez</b> (NDVI, anomalía ferruginosa y arcilla) y además es área libre.
        Los percentiles se aplican <b>dentro de cada unidad</b> (formación o depósito aislado); los histogramas de abajo son de toda la cuadrícula, como referencia.
        Cada corte es un <b>percentil de esta cuadrícula</b> (P1–P100). En color, lo que pasa; en gris, lo que se descarta.
        El eje es el valor real del índice; la línea punteada, el valor en tu percentil.
      </small>
      {!f3 && <p className="nota alerta">Este análisis es anterior al filtro NDVI: por ahora solo se aplican la ferruginosa y la arcilla. Usa «Nueva toma» para tener los tres.</p>}
      {INDICES.map(({ k, hist: hk, nombre, cociente, color, pasa, paleta, nota }) => {
        const h = hist![hk] ?? null;
        if (!h && hk === "ndvi") return null;
        const P = Math.round(c[k] * 100);
        const umbral = h ? h.percentiles[Math.min(100, Math.max(0, P))] : 0;
        const pasaPct = num?.pasa?.[k];
        return (
          <div key={k} className={foco === hk ? "indice-corte foco" : "indice-corte"} ref={(el) => { refs.current[hk] = el; }}>
            <div className="fila-corte">
              <b style={{ color }}>{nombre}</b> <small>{cociente}</small>
              {botonCapa(hk)}
              <span className="valor-corte">
                {pasa === "abajo" ? "< " : "≥ "}P{P} <small>· {fmt(umbral)} · pasa {pasaPct ?? "—"} % de lo útil</small>
              </span>
            </div>
            {h ? <Histograma h={h} umbral={umbral} pasa={pasa} paleta={paleta} /> : <small>sin datos</small>}
            <div className="rango-p">
              <small>P1</small>
              <input type="range" min={1} max={100} step={1} value={Math.min(100, Math.max(1, P))} aria-label={`Percentil de corte ${nombre}`} disabled={ocupado}
                onChange={(e) => setC((x) => ({ ...x, [k]: Number(e.target.value) / 100 }))} />
              <small>P100</small>
              <input type="number" min={1} max={100} step={1} value={Math.min(100, Math.max(1, P))} aria-label={`Percentil ${nombre}`} disabled={ocupado}
                onChange={(e) => { const v = Math.round(Number(e.target.value)); if (v >= 1 && v <= 100) setC((x) => ({ ...x, [k]: v / 100 })); }} />
            </div>
            <small className="nota-corte">{nota}</small>
          </div>
        );
      })}
      {hist?.bsi && (
        <div className="indice-corte referencia">
          <div className="fila-corte"><b style={{ color: "#0f766e" }}>BSI</b> <small>suelo y roca desnuda · solo referencia</small></div>
          <Histograma h={hist.bsi} paleta="bsi" />
          <small className="nota-corte">No entra en la Prioridad libre. Colores = los del mapa: azul petróleo cubierto o húmedo → blanco suelo o roca desnuda.</small>
        </div>
      )}
      {prioridad !== undefined && (
        <div className="prio-corte">
          <span>Prioridad libre con estos filtros</span>
          {prioridad ? <b>{Math.round(prioridad.libre).toLocaleString("es-PE")} ha libres</b> : <b className="calc">calculando…</b>}
          {prioridad && <small>{Math.round(prioridad.negociable).toLocaleString("es-PE")} ha en concesión · de {Math.round(prioridad.total).toLocaleString("es-PE")} ha A/B que pasan los filtros</small>}
        </div>
      )}
      <div className="resumen-corte">
        <div><span>Pasan los tres filtros</span><b>{num?.pasa?.todos ?? "—"} % de lo útil</b></div>
        {onVerCapa && (
          <div className="ver-capas-corte">
            <button className={capaVista === "todas" ? "ver-capa on" : "ver-capa"} onClick={() => onVerCapa("todas")}
              title="Solo la Prioridad libre, sobre la foto real"><Layers size={13} /> Solo la Prioridad libre</button>
          </div>
        )}
        <div><span>Cumple en toda la cuadrícula</span><b>{ha(num?.celda.pct_cumple)}</b></div>
        {!s2.solo_satelite && num?.celda.pct_interes != null && <div><span>Zonas A y B → pasan los filtros</span><b>{ha(num.celda.pct_interes)} → {ha(num.celda.pct_silice_limpia)}</b></div>}
        <small>«% de lo útil» = de los píxeles sin nubes, agua ni vegetación densa. Hectáreas: de toda la cuadrícula, antes de cruzar con áreas libres.</small>
      </div>
      {error && <p className="error-mp">{error}</p>}
      <div className="botones-corte">
        <button onClick={() => setC(CORTES_DEFECTO)} disabled={ocupado} title="NDVI < P57 · ferruginosa < P30 · arcillas < P30"><RotateCcw size={14} /> Por defecto</button>
        <button onClick={cancelar} disabled={ocupado}>Cancelar</button>
        <button className="primario" onClick={listo} disabled={ocupado}><Check size={15} /> {ocupado ? "Aplicando…" : "Listo"}</button>
      </div>
    </div>
  );
}
