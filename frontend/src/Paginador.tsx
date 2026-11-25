// Paginación de listas largas (ranking, supermaduras): flechas ◀ ▶ y saltos al inicio y al final, para recorrer
// TODAS las cuadrículas de interés y no solo las primeras (pedido del usuario, 24/11/2026).
import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronFirst, ChevronLast, ChevronLeft, ChevronRight } from "lucide-react";

export const POR_PAGINA = 100;

export interface Paginas<T> {
  items: T[];          // los de la página actual
  inicio: number;      // índice (0) del primero de la página: el puesto es inicio + i + 1
  fin: number;         // índice siguiente al último de la página
  total: number;
  pagina: number;
  paginas: number;
  ir: (p: number) => void;
  /** ref para la lista: al cambiar de página se vuelve a su comienzo */
  ref: React.RefObject<HTMLOListElement>;
}

/** Página actual de `lista`; vuelve a la primera cuando la lista cambia (otro filtro u orden). */
export function usePaginas<T>(lista: T[], tam = POR_PAGINA): Paginas<T> {
  const [pagina, setPagina] = useState(0);
  const ref = useRef<HTMLOListElement>(null);
  useEffect(() => { setPagina(0); }, [lista]);
  const paginas = Math.max(1, Math.ceil(lista.length / tam));
  const p = Math.min(pagina, paginas - 1);
  const items = useMemo(() => lista.slice(p * tam, (p + 1) * tam), [lista, p, tam]);
  return {
    items, inicio: p * tam, fin: Math.min(lista.length, (p + 1) * tam), total: lista.length, pagina: p, paginas,
    ref,
    ir: (n: number) => {
      setPagina(Math.max(0, Math.min(paginas - 1, n)));
      requestAnimationFrame(() => (ref.current?.previousElementSibling ?? ref.current)?.scrollIntoView({ block: "start", behavior: "smooth" }));
    },
  };
}

export default function Paginador<T>({ p }: { p: Paginas<T> }) {
  if (p.total <= POR_PAGINA) return null;
  const n = (v: number) => v.toLocaleString("es-PE");
  return (
    <div className="paginador" role="navigation" aria-label="Páginas de la lista">
      <button onClick={() => p.ir(0)} disabled={p.pagina === 0} title="Primeras" aria-label="Primera página"><ChevronFirst size={15} /></button>
      <button onClick={() => p.ir(p.pagina - 1)} disabled={p.pagina === 0} title="Anteriores" aria-label="Página anterior"><ChevronLeft size={15} /></button>
      <span><b>{n(p.inicio + 1)}–{n(p.fin)}</b> de {n(p.total)}</span>
      <button onClick={() => p.ir(p.pagina + 1)} disabled={p.pagina >= p.paginas - 1} title="Siguientes" aria-label="Página siguiente"><ChevronRight size={15} /></button>
      <button onClick={() => p.ir(p.paginas - 1)} disabled={p.pagina >= p.paginas - 1} title="Últimas" aria-label="Última página"><ChevronLast size={15} /></button>
    </div>
  );
}
