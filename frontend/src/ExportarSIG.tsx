// Exportación SIG de la cuadrícula (24/11/2026): KMZ (Google Earth, GPS) o shapefile (QGIS, ArcGIS) en WGS 84, con
// límite, zonas A/B/C, Prioridad libre, zonas libres, áreas protegidas y concesiones (backend/exportar_sig.py).
import { useState } from "react";
import { Download, Globe2, Loader2, X } from "lucide-react";
import { api, type Afloramiento } from "./api";
import type { Celda } from "./geo";

const CAPAS_TXT = [
  ["Límite de la cuadrícula", "1:25 000"],
  ["Zonas geológicas A/B/C", "unidad, litología, área"],
  ["Prioridad libre", "libre · concesión · chacra/poblado/vía · extinguido"],
  ["Zonas libres", "libre y utilizable, extinguido y cada motivo de «no apto»"],
  ["Áreas protegidas y restringidas", "nombre, tipo, nivel, norma"],
  ["Concesiones mineras", "código, nombre, titular, estado, hectáreas"],
];

export default function ExportarSIG({ celda, zonas, prioridad, onCerrar }: {
  celda: Celda;
  zonas: Afloramiento[];
  prioridad: { url: string; bbox: number[] } | null;
  onCerrar: () => void;
}) {
  const [formato, setFormato] = useState<"kmz" | "shp">(() => {
    try { return localStorage.getItem("prospector-rmi:formato-sig") === "shp" ? "shp" : "kmz"; } catch { return "kmz"; }
  });
  const [estado, setEstado] = useState<"" | "trabajando" | "listo" | string>("");

  async function bajar() {
    setEstado("trabajando");
    try { localStorage.setItem("prospector-rmi:formato-sig", formato); } catch { /* sin almacenamiento */ }
    try {
      const blob = await api.exportar({
        formato,
        celda: { codigo: celda.codigo, sur: celda.sur, oeste: celda.oeste, norte: celda.norte, este: celda.este },
        zonas: zonas.map((a) => ({ clase: a.clase, unidad: a.unidad, litologia: a.litologia || a.descripcion, geometria: a.geometria })),
        prioridad: prioridad ? { png: prioridad.url, bbox: prioridad.bbox } : null,
      });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = formato === "shp" ? `${celda.codigo}_capas_shp.zip` : `${celda.codigo}_capas.kmz`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 4000);
      setEstado("listo");
    } catch (e) {
      setEstado((e as Error).message);
    }
  }

  const ocupado = estado === "trabajando";
  return (
    <div className="fondo-modal" onClick={() => !ocupado && onCerrar()}>
      <div className="modal laminas" onClick={(e) => e.stopPropagation()}>
        <div className="titulo-mp"><b><Globe2 size={18} /> Exportar SIG · {celda.codigo}</b>
          <button onClick={onCerrar} disabled={ocupado} aria-label="Cerrar"><X size={16} /></button></div>
        <small className="explica">Capas vectoriales de la cuadrícula en WGS 84 (EPSG:4326), para llevar al GPS, Google Earth o QGIS.
          Las áreas protegidas y las concesiones se consultan en vivo a INGEMMET.</small>
        <ul className="lista-laminas">
          {CAPAS_TXT.map(([n, d]) => (
            <li key={n}><span><b>{n}</b><small>{d}</small></span></li>
          ))}
        </ul>
        {!prioridad && <p className="nota alerta">Sin Prioridad libre calculada: el archivo sale sin esa capa.</p>}
        <div className="formato-lam" role="radiogroup" aria-label="Formato">
          <span>Formato:</span>
          <label><input type="radio" checked={formato === "kmz"} disabled={ocupado} onChange={() => setFormato("kmz")} /> KMZ
            <small>(Google Earth, GPS, celular)</small></label>
          <label><input type="radio" checked={formato === "shp"} disabled={ocupado} onChange={() => setFormato("shp")} /> Shapefile
            <small>(QGIS, ArcGIS: un ZIP con una capa por tema)</small></label>
        </div>
        {estado && estado !== "trabajando" && estado !== "listo" && <p className="error-mp">{estado}</p>}
        {estado === "listo" && <small className="ok-pet">✓ Descargado</small>}
        <button className="primario" disabled={ocupado} onClick={bajar}>
          {ocupado ? <><Loader2 size={16} className="gira" /> Preparando las capas…</> : <><Download size={16} /> Descargar {formato === "shp" ? "shapefile (ZIP)" : "KMZ"}</>}
        </button>
      </div>
    </div>
  );
}
