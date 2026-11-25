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

// ---------------------------------------------------------------- informe largo en el celular (25/11/2026)
// El informe lo arma el SERVIDOR: sigue aunque el celular se apague. La app (1) pide mantener la pantalla encendida
// mientras espera, (2) no se rinde si se corta la conexión un rato y (3) recuerda el informe pendiente para bajarlo
// al volver a abrir la app.

type Bloqueo = { release: () => Promise<void> };
let bloqueo: Bloqueo | null = null;
let quiereBloqueo = false;
async function pedirBloqueo() {
  try {
    const wl = (navigator as unknown as { wakeLock?: { request: (t: "screen") => Promise<Bloqueo> } }).wakeLock;
    if (wl && quiereBloqueo && !bloqueo) bloqueo = await wl.request("screen");
  } catch { bloqueo = null; }
}
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") { bloqueo = null; void pedirBloqueo(); }   // el sistema lo suelta al ocultarse
});
/** Mantener la pantalla encendida (true) o soltarla (false). */
export async function pantallaEncendida(si: boolean) {
  quiereBloqueo = si;
  if (si) await pedirBloqueo();
  else { try { await bloqueo?.release(); } catch { /* ya suelto */ } bloqueo = null; }
}

const CLAVE_PENDIENTE = "prospector-rmi:informe-pendiente";
export interface InformePendiente { id: string; nombre: string; codigo: string; t: number }
export function recordarInforme(x: InformePendiente | null) {
  try { if (x) localStorage.setItem(CLAVE_PENDIENTE, JSON.stringify(x)); else localStorage.removeItem(CLAVE_PENDIENTE); } catch { /* sin almacenamiento */ }
}
export function informePendiente(): InformePendiente | null {
  try {
    const x = JSON.parse(localStorage.getItem(CLAVE_PENDIENTE) || "null") as InformePendiente | null;
    return x && Date.now() - x.t < 6 * 3600e3 ? x : null;   // el servidor guarda los últimos informes unas horas
  } catch { return null; }
}
/** Evita bajar dos veces el mismo informe (la ventana del informe y la revisión automática de App lo ven listo a la vez). */
const tomados = new Set<string>();
export function tomarInforme(id: string): boolean {
  if (tomados.has(id)) return false;
  tomados.add(id);
  return true;
}
