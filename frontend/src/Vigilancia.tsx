// Vigilancia del catastro de INGEMMET sobre tus áreas: cuadrículas 1:25 000 y cuadrículas de 100 ha de tus
// petitorios. La app guarda una «foto» del catastro de cada una (en este dispositivo) y, al revisar, el servidor
// la compara con el catastro actual: petitorios nuevos, cambios de estado, derechos que desaparecen,
// publicaciones de libre denunciabilidad. Revisión automática una vez al día si INGEMMET responde.
import { useCallback, useEffect, useState } from "react";
import { Bell, Eye, RefreshCw, Trash2, X } from "lucide-react";
import { API_URL } from "./api";

export interface AlertaVig { fecha: string; tipo: string; nivel: "alta" | "media" | "info"; texto: string; codigo?: string; leida?: boolean }
export interface ItemVig {
  id: string; tipo: "cuadricula" | "petitorio"; nombre: string; anillo: number[][]; propio: boolean;
  foto?: { fecha: string; derechos: Record<string, { nombre: string; estado: string }>; ocupado_pct: number; ld: string[] | null };
  ultima?: string; error?: string; alertas: AlertaVig[];
}

const CLAVE = "prospector-rmi:vigilancia";
const leer = (): ItemVig[] => { try { return JSON.parse(localStorage.getItem(CLAVE) || "[]"); } catch { return []; } };
const DIA = 24 * 3600 * 1000;

export function useVigilancia() {
  const [items, setItems] = useState<ItemVig[]>(leer);
  const [revisando, setRevisando] = useState(false);
  useEffect(() => { try { localStorage.setItem(CLAVE, JSON.stringify(items)); } catch { /* lleno */ } }, [items]);
  const noLeidas = items.reduce((s, i) => s + i.alertas.filter((a) => !a.leida && a.nivel !== "info").length, 0);
  const vigila = (id: string) => items.some((i) => i.id === id);
  function agregar(it: Omit<ItemVig, "alertas">) {
    setItems((xs) => (xs.some((x) => x.id === it.id) ? xs : [...xs, { ...it, alertas: [] }]));
  }
  const quitar = (id: string) => setItems((xs) => xs.filter((x) => x.id !== id));
  const marcarLeidas = () => setItems((xs) => xs.map((x) => ({ ...x, alertas: x.alertas.map((a) => ({ ...a, leida: true })) })));
  const revisar = useCallback(async (soloViejas = false) => {
    const lista = leer().filter((i) => !soloViejas || !i.ultima || Date.now() - new Date(i.ultima).getTime() > DIA);
    if (!lista.length) return;
    setRevisando(true);
    try {
      for (let k = 0; k < lista.length; k += 20) {
        const lote = lista.slice(k, k + 20);
        const r = await fetch(`${API_URL}/vigilancia/revisar`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ items: lote.map((i) => ({ id: i.id, anillo: i.anillo, previo: i.foto ?? null, propio: i.propio })) }),
        });
        if (!r.ok) throw new Error(`Error ${r.status}`);
        const res: { id: string; ok: boolean; foto?: ItemVig["foto"]; alertas?: Omit<AlertaVig, "fecha">[]; error?: string }[] = await r.json();
        const ahora = new Date().toISOString();
        setItems((xs) => xs.map((x) => {
          const y = res.find((z) => z.id === x.id);
          if (!y) return x;
          if (!y.ok) return { ...x, error: y.error };
          return { ...x, foto: y.foto, ultima: ahora, error: undefined,
            alertas: [...(y.alertas ?? []).map((a) => ({ ...a, fecha: ahora, leida: a.nivel === "info" })), ...x.alertas].slice(0, 60) };
        }));
      }
    } finally {
      setRevisando(false);
    }
  }, []);
  return { items, agregar, quitar, revisar, revisando, noLeidas, vigila, marcarLeidas };
}
export type EstadoVig = ReturnType<typeof useVigilancia>;

const COLOR = { alta: "#f87171", media: "#fbbf24", info: "#94a3b8" };

export default function PanelVigilancia({ st, geocatmin, onIr, onAgregarCarpetas, onCerrar }: {
  st: EstadoVig; geocatmin: boolean | null; onIr: (anillo: number[][]) => void; onAgregarCarpetas: () => number; onCerrar: () => void;
}) {
  const [aviso, setAviso] = useState<string | null>(null);
  useEffect(() => () => st.marcarLeidas(), []); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="panel-vigilancia">
      <div className="cab-pet"><b><Bell size={17} /> Vigilancia del catastro</b><button onClick={onCerrar} aria-label="Cerrar"><X size={16} /></button></div>
      <small className="explica">La app compara el catastro de INGEMMET con la última revisión de cada área: petitorios nuevos, cambios de
        estado, derechos que desaparecen y publicaciones de libre denunciabilidad. Se revisa sola una vez al día si INGEMMET responde.</small>
      <div className="fila-exp">
        <button disabled={st.revisando || !st.items.length || geocatmin === false} onClick={() => st.revisar(false).catch((e) => setAviso((e as Error).message))}>
          <RefreshCw size={14} className={st.revisando ? "gira" : ""} /> {st.revisando ? "Revisando…" : "Revisar ahora"}
        </button>
        <button onClick={() => { const n = onAgregarCarpetas(); setAviso(n ? `Se agregaron ${n} cuadrícula(s) de tus carpetas.` : "Tus cuadrículas guardadas ya estaban vigiladas."); }}>
          <Eye size={14} /> Vigilar mis carpetas ★
        </button>
      </div>
      {geocatmin === false && <p className="error-mp">INGEMMET (GEOCATMIN) no responde ahora: la revisión se hará cuando vuelva.</p>}
      {aviso && <small className="ok-pet">{aviso}</small>}
      {!st.items.length && <p className="explica">Aún no vigilas nada. Usa <b>«Vigilar»</b> en una cuadrícula analizada, en tu expediente de petitorio,
        o agrega tus carpetas ★.</p>}
      <ul className="lista-vig">
        {st.items.map((i) => (
          <li key={i.id}>
            <div className="cab-vig">
              <b onClick={() => onIr(i.anillo)}>{i.tipo === "petitorio" ? "📋 " : ""}{i.nombre}</b>
              <button title="Dejar de vigilar" onClick={() => st.quitar(i.id)}><Trash2 size={13} /></button>
            </div>
            <small className="meta-vig">
              {i.ultima ? `Revisado ${new Date(i.ultima).toLocaleString("es-PE")}` : "Sin revisar todavía"}
              {i.foto && ` · ${Object.keys(i.foto.derechos).length} derecho(s) · ${i.foto.ocupado_pct} % ocupado`}
              {i.error && <span className="error-mp"> · {i.error}</span>}
            </small>
            {i.alertas.slice(0, 6).map((a, k) => (
              <div key={k} className={`alerta-vig ${a.leida ? "" : "nueva"}`} style={{ borderLeftColor: COLOR[a.nivel] }}>
                <small>{new Date(a.fecha).toLocaleDateString("es-PE")} · {a.nivel === "alta" ? "IMPORTANTE" : a.nivel === "media" ? "cambio" : "info"}</small>
                {a.texto}
              </div>
            ))}
          </li>
        ))}
      </ul>
      <p className="nota-pet">Referencial: confirma en INGEMMET (catastro, SIDEMCAT y publicaciones de libre denunciabilidad) antes de actuar.</p>
    </div>
  );
}
