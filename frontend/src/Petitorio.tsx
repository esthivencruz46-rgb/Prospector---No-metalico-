// Expediente de PETITORIO MINERO (concesión ante INGEMMET), paso a paso y didáctico:
//  · pasos reales del procedimiento ordinario con check; «Observado» = REBOTE: desmarca ese paso y los
//    siguientes y deja constancia en el historial (hay que volver a presentar o subsanar);
//  · cuadrículas de 100 ha (1 km × 1 km UTM WGS84) elegidas tocando el mapa, validadas (1 a 10, misma zona,
//    colindantes por un lado) y sus vértices UTM para el formulario.
// Se guarda en este dispositivo (localStorage). Referencial: los requisitos, montos y plazos vigentes se
// confirman en INGEMMET (TUPA y Reglamento de Procedimientos Mineros) antes de presentar.
import { useEffect, useMemo, useState } from "react";
import { Check, ClipboardCheck, Copy, Download, Grid3x3, RotateCcw, X } from "lucide-react";
import { claveC100, utmAGeo, validarPetitorio, verticesPetitorio, type Cuadricula100 } from "./geo";

export interface EstadoPaso { hecho: boolean; fecha?: string; nota?: string }
export interface Expediente {
  id: string; nombre: string; creado: string; codigo?: string;
  sustancia: "no metálica" | "metálica"; regimen: "general" | "PPM" | "PMA";
  cuadriculas: Cuadricula100[];
  pasos: Record<string, EstadoPaso>;
  historial: { fecha: string; paso: string; tipo: "hecho" | "deshecho" | "observado"; nota?: string }[];
}

interface Paso { id: string; fase: string; titulo: string; que: string; docs?: string[]; quien?: string; plazo?: string; ojo?: string; herramienta?: boolean }

// Procedimiento ordinario (TUO de la Ley General de Minería, D.S. 014-92-EM, y Reglamento de Procedimientos
// Mineros, D.S. 020-2020-EM). Montos y plazos: verificar los vigentes en INGEMMET.
export const PASOS: Paso[] = [
  { id: "area", fase: "1 · Antes del petitorio", titulo: "Identificar el área de interés",
    que: "Elegir dónde pedir: geología favorable, prioridad en zona libre y acceso. Es lo que hace el análisis de cuadrículas de esta app.",
    quien: "Tú (geólogo)", ojo: "Pide donde está la roca, no toda la cuadrícula 1:25 000: la concesión se paga por hectárea cada año." },
  { id: "libre", fase: "1 · Antes del petitorio", titulo: "Verificar que esté libre en el catastro de INGEMMET",
    que: "Revisar en GEOCATMIN que las cuadrículas no tengan derechos mineros vigentes o en trámite, ni estén en áreas naturales protegidas, zonas arqueológicas, ANAP, defensa, urbanas u otras restringidas.",
    docs: ["Catastro minero (GEOCATMIN)", "Áreas restringidas", "Publicaciones de libre denunciabilidad"],
    ojo: "Un derecho EXTINGUIDO no se puede pedir hasta que INGEMMET publique su libre denunciabilidad. El catastro cambia a diario: revisa el mismo día de presentar." },
  { id: "cuadriculas", fase: "1 · Antes del petitorio", titulo: "Definir las cuadrículas de 100 ha (UTM WGS84)",
    que: "Elegir de 1 a 10 cuadrículas de 1 km × 1 km (100 a 1 000 ha en tierra), colindantes al menos por un lado, con vértices en múltiplos de 1 000 m de coordenadas UTM WGS84.",
    herramienta: true, ojo: "No contigüidad por un lado o exceso de área son causales de rechazo." },
  { id: "peticionario", fase: "1 · Antes del petitorio", titulo: "Definir el peticionario y su régimen",
    que: "Persona natural (DNI) o jurídica (RUC, representante con poder vigente). Régimen general, Pequeño Productor Minero (PPM) o Productor Minero Artesanal (PMA) con constancia de calificación vigente.",
    docs: ["DNI o ficha RUC", "Poder del representante (persona jurídica)", "Constancia de calificación PPM/PMA (si aplica)"],
    ojo: "El régimen define el derecho de vigencia y DÓNDE se presenta (PPM/PMA: Gobierno Regional, salvo Lima Metropolitana)." },
  { id: "pagos", fase: "1 · Antes del petitorio", titulo: "Pagar derecho de vigencia (1.er año) y derecho de trámite",
    que: "Derecho de vigencia: US$ 3/ha al año (régimen general), US$ 1/ha (PPM), US$ 0,50/ha (PMA). Derecho de trámite: según el TUPA vigente de INGEMMET (referencia: 10 % de la UIT). En los bancos y cuentas autorizados por INGEMMET.",
    docs: ["Comprobante ORIGINAL del derecho de vigencia", "Número de recibo del derecho de trámite"],
    quien: "Bancos autorizados por INGEMMET", ojo: "Sin los comprobantes al presentar, el petitorio se rechaza. Confirma montos y cuentas el mismo día." },
  { id: "formulario", fase: "1 · Antes del petitorio", titulo: "Llenar el formulario de petitorio",
    que: "Formato de INGEMMET: nombre del derecho minero, clase de sustancia (metálica / no metálica), datos y domicilio del peticionario, coordenadas UTM WGS84 de las cuadrículas, zona, hoja de la Carta Nacional, extensión en ha, datos de los pagos, autorización de notificación electrónica y declaraciones juradas.",
    docs: ["Formulario de petitorio firmado", "Declaración jurada de compromiso previo"] },
  { id: "presentar", fase: "2 · Presentación", titulo: "Presentar el petitorio",
    que: "En INGEMMET (mesa de partes / canal vigente) o, si eres PPM o PMA, en el Gobierno Regional donde está el área. Anota la fecha, la HORA y el código del expediente: la prioridad la tiene quien presenta primero.",
    quien: "INGEMMET o Gobierno Regional", ojo: "Pide el cargo de recepción con fecha y hora." },
  { id: "revision", fase: "2 · Presentación", titulo: "Revisión inicial (coordenadas, pagos, superposiciones)",
    que: "La autoridad revisa el petitorio y notifica los avisos para publicar o las observaciones. Si hay observación: subsanar en el plazo que indique (usa «Observado» para registrar el rebote).",
    plazo: "Referencia: ~7 días para revisar y notificar", quien: "INGEMMET" },
  { id: "avisos", fase: "3 · Publicación", titulo: "Publicar los avisos del petitorio",
    que: "Publicar el aviso UNA vez en el diario oficial El Peruano y en el diario de avisos judiciales de la capital del departamento.",
    plazo: "30 días hábiles desde la notificación", ojo: "Si no se publica a tiempo, INGEMMET declara el ABANDONO del petitorio." },
  { id: "paginas", fase: "3 · Publicación", titulo: "Entregar las páginas de ambos diarios",
    que: "Presentar las páginas completas de las dos publicaciones a la autoridad minera.",
    plazo: "60 días calendario", ojo: "Fuera de plazo también lleva al abandono." },
  { id: "evaluacion", fase: "4 · Evaluación y título", titulo: "Evaluación técnica y legal (y posibles oposiciones)",
    que: "Catastro minero (superposiciones, áreas restringidas) y evaluación legal. Un tercero puede presentar oposición: se te corre traslado para responder. Observaciones = rebote.",
    plazo: "Traslado de oposición: referencia 7 días", quien: "INGEMMET (Dirección de Catastro Minero y Dirección de Concesiones)" },
  { id: "titulo", fase: "4 · Evaluación y título", titulo: "Resolución de otorgamiento del título de concesión",
    que: "La Presidencia de INGEMMET emite la resolución que otorga el título y se notifica. Revisa que el área y las coordenadas coincidan con lo pedido.",
    quien: "Presidencia de INGEMMET" },
  { id: "consentido", fase: "4 · Evaluación y título", titulo: "Título consentido e inscrito en SUNARP",
    que: "El título queda consentido tras la publicación de la relación de títulos otorgados (referencia: 15 días después) y se inscribe en el Registro de Derechos Mineros de SUNARP.",
    quien: "INGEMMET · SUNARP" },
  { id: "vigencia", fase: "5 · Mantener la concesión", titulo: "Pagar el derecho de vigencia cada año",
    que: "Pagar cada año (vence el 30 de junio) el derecho de vigencia por hectárea; acreditar producción o inversión mínima o pagar la penalidad; presentar la Declaración Anual Consolidada (DAC).",
    ojo: "No pagar dos años lleva a la caducidad del derecho minero." },
  { id: "permisos", fase: "5 · Mantener la concesión", titulo: "Permisos antes de explorar o explotar",
    que: "La concesión NO autoriza a trabajar. Antes se necesita: certificación ambiental (DIA / EIA-sd / EIA), autorización del propietario del terreno superficial, CIRA (Ministerio de Cultura), consulta previa si corresponde y autorización de inicio de actividades.",
    quien: "MINEM / Gobierno Regional / SENACE / Ministerio de Cultura" },
];

const CLAVE = "prospector-rmi:expedientes";
const leer = (): Expediente[] => { try { return JSON.parse(localStorage.getItem(CLAVE) || "[]"); } catch { return []; } };
const hoy = () => new Date().toISOString();
const TARIFA = { general: 3, PPM: 1, PMA: 0.5 } as const;

/** Estado de los expedientes (lo usa App para el mapa y el panel). */
export function usePetitorio() {
  const [expedientes, setExpedientes] = useState<Expediente[]>(leer);
  const [activoId, setActivoId] = useState<string | null>(() => leer()[0]?.id ?? null);
  const [eligiendo, setEligiendo] = useState(false);   // modo «tocar el mapa para elegir cuadrículas»
  useEffect(() => { try { localStorage.setItem(CLAVE, JSON.stringify(expedientes)); } catch { /* lleno */ } }, [expedientes]);
  const activo = expedientes.find((x) => x.id === activoId) ?? null;
  const cambiar = (f: (e: Expediente) => Expediente) =>
    setExpedientes((xs) => xs.map((x) => (x.id === activoId ? f(x) : x)));
  function nuevo(nombre: string) {
    const e: Expediente = { id: Math.random().toString(36).slice(2, 10), nombre: nombre || "Petitorio sin nombre", creado: hoy(),
      sustancia: "no metálica", regimen: "general", cuadriculas: [], pasos: {}, historial: [] };
    setExpedientes((xs) => [e, ...xs]);
    setActivoId(e.id);
  }
  function alternarCuadricula(c: Cuadricula100) {
    cambiar((e) => {
      const k = claveC100(c);
      const ya = e.cuadriculas.some((x) => claveC100(x) === k);
      return { ...e, cuadriculas: ya ? e.cuadriculas.filter((x) => claveC100(x) !== k) : [...e.cuadriculas, c] };
    });
  }
  return { expedientes, setExpedientes, activo, activoId, setActivoId, eligiendo, setEligiendo, cambiar, nuevo, alternarCuadricula };
}
export type EstadoPetitorio = ReturnType<typeof usePetitorio>;

export default function PanelPetitorio({ st, onCerrar, onVerCatastro, onVigilar, vigilado }: {
  st: EstadoPetitorio; onCerrar: () => void; onVerCatastro: () => void;
  onVigilar?: (nombre: string, anillo: number[][]) => void; vigilado?: boolean;
}) {
  const { expedientes, activo, setActivoId, eligiendo, setEligiendo, cambiar, nuevo, setExpedientes } = st;
  const [pestana, setPestana] = useState<"pasos" | "cuadriculas">("pasos");
  const [nota, setNota] = useState<Record<string, string>>({});
  const [abierto, setAbierto] = useState<string | null>(null);
  const val = useMemo(() => validarPetitorio(activo?.cuadriculas ?? []), [activo?.cuadriculas]);
  const vert = useMemo(() => (val.ok && activo ? verticesPetitorio(activo.cuadriculas) : []), [val.ok, activo]);

  if (!activo) {
    return (
      <div className="panel-petitorio">
        <div className="cab-pet"><b><ClipboardCheck size={17} /> Petitorio minero</b><button onClick={onCerrar}><X size={16} /></button></div>
        <p className="explica">Arma tu expediente de concesión paso a paso: cada paso se marca con ✓ y, si INGEMMET observa, se registra el rebote.
          Incluye la herramienta de cuadrículas de 100 ha.</p>
        <button className="primario" onClick={() => nuevo(prompt("Nombre del derecho minero (como irá en el petitorio):", "") ?? "")}>+ Nuevo expediente</button>
      </div>
    );
  }

  const hechos = PASOS.filter((p) => activo.pasos[p.id]?.hecho).length;
  const siguiente = PASOS.find((p) => !activo.pasos[p.id]?.hecho);
  function marcar(id: string, hecho: boolean) {
    cambiar((e) => ({ ...e, pasos: { ...e.pasos, [id]: { ...e.pasos[id], hecho, fecha: hecho ? hoy() : undefined } },
      historial: [...e.historial, { fecha: hoy(), paso: id, tipo: hecho ? "hecho" : "deshecho" }] }));
  }
  function observar(id: string) {
    const texto = nota[id]?.trim() || prompt("¿Qué observaron? (se guarda en el historial)") || "";
    const i = PASOS.findIndex((p) => p.id === id);
    cambiar((e) => {
      const pasos = { ...e.pasos };
      for (const p of PASOS.slice(i)) if (pasos[p.id]?.hecho) pasos[p.id] = { ...pasos[p.id], hecho: false, fecha: undefined };
      return { ...e, pasos, historial: [...e.historial, { fecha: hoy(), paso: id, tipo: "observado", nota: texto }] };
    });
    setNota((n) => ({ ...n, [id]: "" }));
  }
  const ha = activo.cuadriculas.length * 100;
  const zona = activo.cuadriculas[0]?.zona;
  const textoVertices = vert.map((v, i) => `${i + 1}\t${v.este}\t${v.norte}`).join("\n");
  function descargarCsv() {
    const filas = ["vertice;este_m;norte_m;zona_utm", ...vert.map((v, i) => `${i + 1};${v.este};${v.norte};${zona}S`)];
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["﻿" + filas.join("\r\n")], { type: "text/csv" }));
    a.download = `${activo!.nombre.replace(/[^\w-]+/g, "_")}_vertices_WGS84.csv`;
    a.click();
  }

  return (
    <div className="panel-petitorio">
      <div className="cab-pet">
        <b><ClipboardCheck size={17} /> Petitorio minero</b>
        <button onClick={onCerrar} aria-label="Cerrar"><X size={16} /></button>
      </div>
      <div className="fila-exp">
        <select value={activo.id} onChange={(e) => setActivoId(e.target.value)}>
          {expedientes.map((x) => <option key={x.id} value={x.id}>{x.nombre}</option>)}
        </select>
        <button title="Nuevo expediente" onClick={() => nuevo(prompt("Nombre del derecho minero:", "") ?? "")}>+</button>
        <button title="Borrar este expediente" onClick={() => { if (confirm(`¿Borrar el expediente «${activo.nombre}»?`)) { setExpedientes((xs) => xs.filter((x) => x.id !== activo.id)); setActivoId(expedientes.find((x) => x.id !== activo.id)?.id ?? null); } }}>🗑</button>
      </div>
      <div className="progreso-pet"><i style={{ width: `${(100 * hechos) / PASOS.length}%` }} /><span>{hechos} de {PASOS.length} pasos</span></div>
      {siguiente && <small className="siguiente-pet">Siguiente: <b>{siguiente.titulo}</b></small>}
      <div className="pestanas-pet">
        <button className={pestana === "pasos" ? "on" : ""} onClick={() => setPestana("pasos")}><ClipboardCheck size={14} /> Pasos</button>
        <button className={pestana === "cuadriculas" ? "on" : ""} onClick={() => setPestana("cuadriculas")}><Grid3x3 size={14} /> Cuadrículas 100 ha ({activo.cuadriculas.length})</button>
      </div>

      {pestana === "pasos" ? (
        <div className="pasos-pet">
          {PASOS.map((p, i) => {
            const e = activo.pasos[p.id];
            const obs = activo.historial.filter((h) => h.paso === p.id && h.tipo === "observado");
            const nuevaFase = i === 0 || PASOS[i - 1].fase !== p.fase;
            return (
              <div key={p.id}>
                {nuevaFase && <div className="fase-pet">{p.fase}</div>}
                <div className={`paso-pet ${e?.hecho ? "hecho" : ""} ${siguiente?.id === p.id ? "actual" : ""}`}>
                  <button className="check-pet" aria-label={e?.hecho ? "Desmarcar" : "Marcar como hecho"} onClick={() => marcar(p.id, !e?.hecho)}>
                    {e?.hecho ? <Check size={16} /> : i + 1}
                  </button>
                  <div className="cuerpo-pet">
                    <div className="tit-pet" onClick={() => setAbierto((a) => (a === p.id ? null : p.id))}>
                      {p.titulo}
                      {obs.length > 0 && <span className="rebote" title="Veces observado">↺ {obs.length}</span>}
                      {e?.fecha && <small> · {new Date(e.fecha).toLocaleDateString("es-PE")}</small>}
                    </div>
                    {abierto === p.id && (
                      <div className="detalle-pet">
                        <p>{p.que}</p>
                        {p.docs && <ul>{p.docs.map((d) => <li key={d}>{d}</li>)}</ul>}
                        {(p.quien || p.plazo) && <p className="meta-pet">{p.quien && <>Ante: <b>{p.quien}</b></>}{p.quien && p.plazo && " · "}{p.plazo && <>Plazo: <b>{p.plazo}</b></>}</p>}
                        {p.ojo && <p className="ojo-pet">⚠ {p.ojo}</p>}
                        {p.herramienta && <button onClick={() => setPestana("cuadriculas")}><Grid3x3 size={14} /> Abrir la herramienta de cuadrículas</button>}
                        {obs.map((h, k) => <p key={k} className="obs-pet">↺ {new Date(h.fecha).toLocaleDateString("es-PE")}: {h.nota || "observado"}</p>)}
                        <div className="observar-pet">
                          <input placeholder="Observación de INGEMMET (si la hubo)" value={nota[p.id] ?? ""} onChange={(ev) => setNota((n) => ({ ...n, [p.id]: ev.target.value }))} />
                          <button title="Rebote: desmarca este paso y los siguientes" onClick={() => observar(p.id)}><RotateCcw size={14} /> Observado</button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
          <p className="nota-pet">Referencial: TUO de la Ley General de Minería (D.S. 014-92-EM) y Reglamento de Procedimientos Mineros (D.S. 020-2020-EM).
            Confirma requisitos, montos y plazos vigentes en INGEMMET antes de presentar.</p>
        </div>
      ) : (
        <div className="cuad-pet">
          <div className="fila-exp">
            <label>Sustancia <select value={activo.sustancia} onChange={(e) => cambiar((x) => ({ ...x, sustancia: e.target.value as Expediente["sustancia"] }))}>
              <option value="no metálica">no metálica</option><option value="metálica">metálica</option></select></label>
            <label>Régimen <select value={activo.regimen} onChange={(e) => cambiar((x) => ({ ...x, regimen: e.target.value as Expediente["regimen"] }))}>
              <option value="general">general</option><option value="PPM">PPM</option><option value="PMA">PMA</option></select></label>
          </div>
          <button className={eligiendo ? "primario" : ""} onClick={() => setEligiendo((v) => !v)}>
            <Grid3x3 size={15} /> {eligiendo ? "Eligiendo: toca cuadrículas en el mapa (tocar de nuevo = quitar)" : "Elegir cuadrículas en el mapa"}
          </button>
          <small className="explica">Acércate (zoom ≥ 12): aparece la grilla de 1 km UTM WGS84. Cada cuadrado = 100 ha. <button className="enlace" onClick={onVerCatastro}>Ver concesiones y áreas libres</button> para no pisar derechos.</small>
          <div className="cifras-pet">
            <span><b>{activo.cuadriculas.length}</b><small>cuadrículas</small></span>
            <span><b>{ha.toLocaleString("es-PE")}</b><small>hectáreas</small></span>
            <span><b>US$ {(ha * TARIFA[activo.regimen]).toLocaleString("es-PE")}</b><small>vigencia / año ({activo.regimen})</small></span>
          </div>
          {val.errores.map((x) => <p key={x} className="error-mp">✗ {x}</p>)}
          {val.ok && (
            <>
              <p className="ok-pet">✓ Válido: {activo.cuadriculas.length} cuadrícula(s) colindantes, zona UTM {zona} S.</p>
              <table className="tabla-pet">
                <thead><tr><th>Vértice</th><th>Este (m)</th><th>Norte (m)</th></tr></thead>
                <tbody>{vert.map((v, i) => <tr key={i}><td>{i + 1}</td><td>{v.este}</td><td>{v.norte}</td></tr>)}</tbody>
              </table>
              <small className="explica">Datum WGS 84 · UTM zona {zona} S · vértices en sentido horario desde el noroeste.
                Centro aprox.: {(() => { const c = activo.cuadriculas; const e = (Math.min(...c.map((x) => x.e)) + Math.max(...c.map((x) => x.e)) + 1) / 2, n = (Math.min(...c.map((x) => x.n)) + Math.max(...c.map((x) => x.n)) + 1) / 2; const [la, lo] = utmAGeo(e * 1000, n * 1000, zona!); return `${la.toFixed(5)}, ${lo.toFixed(5)}`; })()}</small>
              <div className="fila-exp">
                <button onClick={() => navigator.clipboard?.writeText(`Vértice\tEste\tNorte\n${textoVertices}`)}><Copy size={14} /> Copiar</button>
                <button onClick={descargarCsv}><Download size={14} /> Excel (CSV)</button>
                <button onClick={() => cambiar((x) => ({ ...x, cuadriculas: [] }))}>Vaciar</button>
                {onVigilar && (
                  <button disabled={vigilado} title="Avisar si aparece un petitorio o cambia el catastro sobre estas cuadrículas"
                    onClick={() => onVigilar(activo!.nombre, vert.map((v) => { const [la, lo] = utmAGeo(v.este, v.norte, zona!); return [lo, la]; }))}>
                    {vigilado ? "✓ Vigilado" : "Vigilar estas cuadrículas"}
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
