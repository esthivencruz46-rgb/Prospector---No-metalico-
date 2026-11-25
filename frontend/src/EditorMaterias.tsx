// Editor de materias primas: el usuario elige con qué materia prima analiza y crea las suyas con
// PALABRAS por clase, formaciones de interés y palabras que descartan.
// El backend (materias_primas.py) las convierte en las mismas reglas que usa la arena silícea.
import { useState } from "react";
import { api, type DefMateria, type Material } from "./api";

const VACIA: DefMateria = { nombre: "", sinonimos: [], clases: { A: [], B: [], C: [] }, formaciones: [], descartar: [], rmi: [], nota: "" };
const COLOR = { A: "#dc2626", B: "#f59e0b", C: "#facc15" } as const;

const aTexto = (l: string[]) => l.join("\n");
const aLista = (t: string) => t.split(/[\n,;]+/).map((x) => x.trim()).filter((x) => x.length >= 3);

interface Props {
  materiales: Material[];
  materiaId: string;
  onElegir: (id: string) => void;
  onCambio: (lista: Material[], elegir?: string) => void;
  onCerrar: () => void;
}

export default function EditorMaterias({ materiales, materiaId, onElegir, onCambio, onCerrar }: Props) {
  const [def, setDef] = useState<DefMateria | null>(null);       // la que se ve/edita
  const [textos, setTextos] = useState<Record<string, string>>({});
  const [prueba, setPrueba] = useState({ litologia: "", unidad: "", roca: "" });
  const [resPrueba, setResPrueba] = useState<{ clase: string | null; motivo: string } | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);


  function abrir(d: DefMateria) {
    setDef(d);
    setTextos({ A: aTexto(d.clases.A), B: aTexto(d.clases.B), C: aTexto(d.clases.C), formaciones: aTexto(d.formaciones),
                descartar: aTexto(d.descartar), sinonimos: aTexto(d.sinonimos) });
    setResPrueba(null); setError(null);
  }
  async function ver(id: string, duplicar = false) {
    setError(null);
    try {
      const d = await api.materiaVer(id);
      if (duplicar) {
        // la de fábrica muestra «motivos» resumidos: al duplicar se empieza con palabras base editables
        const base = d.fabrica ? { A: ["arena silícea", "arena cuarzosa"], B: ["arenisca cuarzosa", "arenisca cuarcítica", "cuarcita"], C: ["arenisca", "arena eólica"] } : d.clases;
        abrir({ ...d, id: undefined, fabrica: false, nombre: `${d.nombre} (copia)`, clases: base,
                descartar: d.fabrica ? ["andesita", "granito", "granodiorita", "diorita", "toba", "volcánico", "arcosa"] : d.descartar });
      } else abrir(d);
    } catch (e) { setError((e as Error).message); }
  }

  const armada = (): DefMateria | null => def && ({
    ...def, clases: { A: aLista(textos.A ?? ""), B: aLista(textos.B ?? ""), C: aLista(textos.C ?? "") },
    formaciones: aLista(textos.formaciones ?? ""), descartar: aLista(textos.descartar ?? ""), sinonimos: aLista(textos.sinonimos ?? ""),
  });

  async function guardar() {
    const d = armada();
    if (!d) return;
    setOcupado(true); setError(null);
    try {
      const g = await api.materiaGuardar(d);
      onCambio(await api.materiales(), g.id);
      setDef(null);
    } catch (e) { setError((e as Error).message); } finally { setOcupado(false); }
  }
  async function borrar(m: Material) {
    if (!confirm(`¿Borrar la materia prima «${m.nombre}»? Sus análisis guardados quedan, pero ya no podrás abrirlos.`)) return;
    try {
      await api.materiaBorrar(m.id);
      onCambio(await api.materiales(), m.id === materiaId ? "arena_silicea" : undefined);
    } catch (e) { setError((e as Error).message); }
  }
  async function probar() {
    const d = armada();
    if (!d) return;
    try { setResPrueba(await api.materiaProbar(d, prueba.litologia, prueba.unidad, prueba.roca)); }
    catch (e) { setResPrueba({ clase: null, motivo: (e as Error).message }); }
  }

  const soloLectura = !!def?.fabrica;
  const campo = (k: string, titulo: string, ayuda: string, color?: string) => (
    <label className="campo-mp">
      <span>{color && <i className="punto" style={{ background: color }} />}<b>{titulo}</b><small>{ayuda}</small></span>
      <textarea rows={3} value={textos[k] ?? ""} disabled={soloLectura} placeholder="una por línea"
        onChange={(e) => setTextos((t) => ({ ...t, [k]: e.target.value }))} />
    </label>
  );

  return (
    <div className="fondo-modal" onClick={onCerrar}>
      <div className="modal editor-mp" onClick={(e) => e.stopPropagation()}>
        <div className="titulo-mp">
          <b>🧪 Materias primas</b>
          <button onClick={onCerrar} aria-label="Cerrar">×</button>
        </div>

        {!def ? (
          <>
            <small className="explica">Elige con cuál analizar. Cada una guarda aparte sus análisis, cuadrículas analizadas y barridos.</small>
            <ul className="lista-mp">
              {materiales.filter((m) => m.activo).map((m) => (
                <li key={m.id} className={m.id === materiaId ? "on" : ""}>
                  <label>
                    <input type="radio" name="materia" checked={m.id === materiaId} onChange={() => onElegir(m.id)} />
                    <span>{m.nombre}{!m.usuario && <small> · de fábrica</small>}</span>
                  </label>
                  <span className="acciones-mp">
                    <button onClick={() => ver(m.id)}>{m.usuario ? "✎ Editar" : "👁 Ver"}</button>
                    <button onClick={() => ver(m.id, true)} title="Crear una copia editable">⧉</button>
                    {m.usuario && <button onClick={() => borrar(m)} title="Borrar">🗑</button>}
                  </span>
                </li>
              ))}
            </ul>
            <button className="primario" onClick={() => abrir({ ...VACIA })}>+ Nueva materia prima</button>
          </>
        ) : (
          <div className="form-mp">
            <label className="campo-mp">
              <span><b>Nombre</b></span>
              <input value={def.nombre} disabled={soloLectura} placeholder="p. ej. Caliza para cemento"
                onChange={(e) => setDef({ ...def, nombre: e.target.value })} />
            </label>
            <small className="explica">
              Escribe las <b>palabras como aparecen en los mapas de INGEMMET</b> (litología o descripción). No importan las tildes
              ni el plural: «caliza» encuentra «Calizas», «arenisca cuarzosa» encuentra «Areniscas cuarzosas».
            </small>
            {campo("A", "Clase A · lo mejor", "lo que el mapa dice explícitamente", COLOR.A)}
            {campo("B", "Clase B · bueno", "rocas de interés (bajan a C si están subordinadas a otra roca)", COLOR.B)}
            {campo("formaciones", "Formaciones de interés → clase B", "nombre como en el mapa: «Formación Chulec», «Grupo Pucará»", COLOR.B)}
            {campo("C", "Clase C · verificar", "compatible, pero hay que verlo en campo", COLOR.C)}
            {campo("descartar", "Descartar si dice", "rocas que bajan a C o descartan (p. ej. andesita, granito)")}
            {campo("sinonimos", "Sinónimos (opcional)", "otras formas de llamarla, para el buscador")}

            <div className="probar-mp">
              <b>🔍 Probar una descripción</b>
              <small>Copia una litología de un polígono de GEOCATMIN y mira qué clase le daría.</small>
              <input placeholder="Litología o descripción, p. ej. «Calizas micríticas con margas»" value={prueba.litologia}
                onChange={(e) => setPrueba({ ...prueba, litologia: e.target.value })} />
              <div className="fila-mp">
                <input placeholder="Unidad (opcional)" value={prueba.unidad} onChange={(e) => setPrueba({ ...prueba, unidad: e.target.value })} />
                <input placeholder="Roca dominante (opcional)" value={prueba.roca} onChange={(e) => setPrueba({ ...prueba, roca: e.target.value })} />
                <button onClick={probar} disabled={!prueba.litologia && !prueba.unidad}>Probar</button>
              </div>
              {resPrueba && (
                <div className="resultado-mp">
                  {resPrueba.clase
                    ? <span className="chip-clase" style={{ background: COLOR[resPrueba.clase as "A" | "B" | "C"] }}>{resPrueba.clase}</span>
                    : <span className="chip-dato">sin clase</span>}
                  <small>{resPrueba.motivo}</small>
                </div>
              )}
            </div>

            <small className="explica nota-sat">
              🛰 El análisis satelital (Sentinel-2) todavía usa los criterios del vidrio (poco hierro y arcilla, roca clara).
              La fórmula satelital por materia prima vendrá después.
            </small>
            {error && <div className="error-mp">{error}</div>}
            <div className="botones-mp">
              {soloLectura
                ? <button className="primario" onClick={() => def.id && ver(def.id, true)}>⧉ Duplicar para editar</button>
                : <button className="primario" disabled={ocupado} onClick={guardar}>{ocupado ? "Guardando…" : "Guardar"}</button>}
              <button onClick={() => setDef(null)}>{soloLectura ? "Volver" : "Cancelar"}</button>
            </div>
          </div>
        )}
        {!def && error && <div className="error-mp">{error}</div>}
      </div>
    </div>
  );
}
