/**
 * Guardar un archivo generado por la app (informe PDF, láminas, KMZ/shapefile, CSV).
 *   · Navegador / laptop: descarga normal (enlace con «download»).
 *   · Celular (APK, Capacitor): el WebView de Android IGNORA esas descargas, así que se escribe con
 *     @capacitor/filesystem en Documentos/Prospector RMI/Descargas/ y se avisa dónde quedó (24/11/2026).
 */
import { plataforma } from "./almacen";

const CARPETA = "Prospector RMI/Descargas";

function base64DeBlob(b: Blob): Promise<string> {
  return new Promise((ok, mal) => {
    const r = new FileReader();
    r.onload = () => ok(String(r.result).split(",", 2)[1] ?? "");
    r.onerror = () => mal(r.error);
    r.readAsDataURL(b);
  });
}

/** Guarda `datos` con el nombre dado. En el celular devuelve la ruta donde quedó (y la avisa). */
export async function guardarArchivo(datos: Blob, nombre: string): Promise<string | null> {
  const limpio = nombre.replace(/[\\/:*?"<>|]+/g, "_");
  if (plataforma() === "app") {
    try {
      const { Filesystem, Directory } = await import("@capacitor/filesystem");
      try { await Filesystem.requestPermissions(); } catch { /* Android ≥ 11 no lo necesita */ }
      await Filesystem.writeFile({ path: `${CARPETA}/${limpio}`, data: await base64DeBlob(datos), directory: Directory.Documents, recursive: true });
      const donde = `Documentos › Prospector RMI › Descargas › ${limpio}`;
      window.alert(`Guardado en el celular:\n${donde}\n\nÁbralo con la app «Archivos» (o «Mis archivos»).`);
      return donde;
    } catch (e) {
      window.alert(`No se pudo guardar ${limpio} en el celular: ${(e as Error).message}`);
      return null;
    }
  }
  const url = URL.createObjectURL(datos);
  const a = document.createElement("a");
  a.href = url;
  a.download = limpio;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
  return null;
}
