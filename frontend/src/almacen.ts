// Carpetas REALES en el dispositivo (además de la copia en el navegador):
//   - Laptop (Chrome / Edge): File System Access API. El usuario elige una vez
//     una carpeta (p. ej. Documentos); ahí se crea «Prospector RMI/». El permiso
//     se recuerda (IndexedDB) pero el navegador lo vuelve a pedir en cada sesión.
//   - Celular con la app instalada (APK, Capacitor): Documents/Prospector RMI/.
//   - Celular desde el navegador / Firefox / Safari: no se puede → «Descargar Excel».
// Nunca se borran archivos del dispositivo: si el usuario agrega fotos o
// documentos dentro de una carpeta, se respetan.

export const NOMBRE_RAIZ = "Prospector RMI";

export type Plataforma = "laptop" | "app" | "ninguna";

/** Escribe archivos dentro de la carpeta raíz «Prospector RMI». */
export interface Escritor {
  donde: string; // texto para el usuario
  texto(ruta: string[], nombre: string, contenido: string): Promise<void>;
  binario(ruta: string[], nombre: string, dataUrl: string): Promise<void>;
  /** Archivo adjunto (foto, PDF…) tal cual. */
  archivo(ruta: string[], nombre: string, datos: Blob): Promise<void>;
  /** Lee un archivo (para recuperar adjuntos si el navegador perdió su copia). */
  leerArchivo(ruta: string[], nombre: string, tipo: string): Promise<Blob | null>;
  /** Contenido de cada «<subcarpeta>/carpeta.json» que exista (para recuperar). */
  leerJsons(): Promise<string[]>;
}

type ConCapacitor = { Capacitor?: { isNativePlatform?: () => boolean } };

export function plataforma(): Plataforma {
  if ((window as unknown as ConCapacitor).Capacitor?.isNativePlatform?.()) return "app";
  if ("showDirectoryPicker" in window) return "laptop";
  return "ninguna";
}

/** Nombre válido de carpeta/archivo en Windows, Android y macOS. */
export function nombreSeguro(s: string): string {
  return s.replace(/\s*[\\/:*?"<>|\u0000-\u001f]+\s*/g, " - ").replace(/\s+/g, " ").replace(/[. ]+$/, "").trim().slice(0, 80) || "carpeta";
}

// ------------------------------------------------------------------ IndexedDB
// «manijas»: FileSystemDirectoryHandle de la laptop (localStorage no puede guardarlo).
// «adjuntos»: fotos y PDF de las carpetas (localStorage solo aguanta ~5 MB).
const BD = "prospector-rmi";
const ALMACEN = "manijas";
const ADJUNTOS = "adjuntos";
// «analisis»: resultado completo por cuadrícula (geología + imágenes Sentinel-2/ASTER), para
// volver a verlo al instante y sin gastar créditos de Copernicus, aun después de cerrar la app.
const ANALISIS = "analisis";

function abrirBD(): Promise<IDBDatabase> {
  return new Promise((ok, mal) => {
    const r = indexedDB.open(BD, 3);
    r.onupgradeneeded = () => {
      for (const s of [ALMACEN, ADJUNTOS, ANALISIS]) if (!r.result.objectStoreNames.contains(s)) r.result.createObjectStore(s);
    };
    r.onsuccess = () => ok(r.result);
    r.onerror = () => mal(r.error);
  });
}

async function bd<T>(modo: IDBTransactionMode, f: (s: IDBObjectStore) => IDBRequest, almacen = ALMACEN): Promise<T> {
  const db = await abrirBD();
  return new Promise((ok, mal) => {
    const t = db.transaction(almacen, modo);
    const r = f(t.objectStore(almacen));
    r.onsuccess = () => ok(r.result as T);
    r.onerror = () => mal(r.error);
  });
}

export const guardarAdjunto = (id: string, datos: Blob) => bd("readwrite", (s) => s.put(datos, id), ADJUNTOS);
export const borrarAdjunto = (id: string) => bd("readwrite", (s) => s.delete(id), ADJUNTOS);
export async function leerAdjunto(id: string): Promise<Blob | null> {
  try {
    return (await bd<Blob | undefined>("readonly", (s) => s.get(id), ADJUNTOS)) ?? null;
  } catch {
    return null;
  }
}

export interface AnalisisGuardado<R = unknown, S = unknown> {
  res: R;
  s2: S | null;
  guardado: string; // ISO
}

// Cada materia prima guarda sus análisis aparte: la arena silícea con la clave de siempre (el código
// de la cuadrícula) y las demás con «<id>|<código>». App.tsx llama a usarMateria() al cambiarla.
let prefijo = "";
export function usarMateria(id: string) {
  prefijo = !id || id === "arena_silicea" ? "" : `${id}|`;
}
const clave = (codigo: string) => prefijo + codigo;

export async function guardarAnalisis(codigo: string, a: AnalisisGuardado): Promise<boolean> {
  try {
    await bd("readwrite", (s) => s.put(a, clave(codigo)), ANALISIS);
    return true;
  } catch {
    return false; // sin espacio o sin IndexedDB: queda solo en memoria
  }
}

export async function leerAnalisis<R, S>(codigo: string): Promise<AnalisisGuardado<R, S> | null> {
  try {
    return (await bd<AnalisisGuardado<R, S> | undefined>("readonly", (s) => s.get(clave(codigo)), ANALISIS)) ?? null;
  } catch {
    return null;
  }
}

export const borrarAnalisis = (codigo: string) => bd("readwrite", (s) => s.delete(clave(codigo)), ANALISIS).catch(() => undefined);

/** Borra TODOS los análisis guardados (no toca adjuntos ni carpetas). */
export const borrarTodosLosAnalisis = () => bd("readwrite", (s) => s.clear(), ANALISIS).catch(() => undefined);

/** Códigos de cuadrícula con análisis guardado (para marcar 🛰 en la lista). */
export async function codigosConAnalisis(): Promise<string[]> {
  try {
    const todas = ((await bd<IDBValidKey[]>("readonly", (s) => s.getAllKeys(), ANALISIS)) ?? []).map(String);
    // solo las de la materia prima elegida (sin prefijo = arena silícea)
    return prefijo ? todas.filter((k) => k.startsWith(prefijo)).map((k) => k.slice(prefijo.length))
      : todas.filter((k) => !k.includes("|"));
  } catch {
    return [];
  }
}

/** Espacio que usa la app en este navegador (MB), si el navegador lo informa. */
export async function espacioUsadoMB(): Promise<number | null> {
  try {
    const e = await navigator.storage?.estimate?.();
    return e?.usage != null ? Math.round(e.usage / 1024 / 1024) : null;
  } catch {
    return null;
  }
}

/** Miniatura JPEG (máx. 160 px) de una imagen, para mostrarla sin cargar el original. */
export async function miniatura(f: Blob): Promise<string | undefined> {
  if (!f.type.startsWith("image/")) return undefined;
  try {
    const img = await createImageBitmap(f);
    const k = 160 / Math.max(img.width, img.height, 1);
    const c = document.createElement("canvas");
    c.width = Math.max(1, Math.round(img.width * Math.min(k, 1)));
    c.height = Math.max(1, Math.round(img.height * Math.min(k, 1)));
    c.getContext("2d")!.drawImage(img, 0, 0, c.width, c.height);
    img.close();
    return c.toDataURL("image/jpeg", 0.6);
  } catch {
    return undefined; // formato que el navegador no sabe dibujar (p. ej. HEIC en Windows)
  }
}

function base64DeBlob(b: Blob): Promise<string> {
  return new Promise((ok, mal) => {
    const r = new FileReader();
    r.onload = () => ok(String(r.result).split(",", 2)[1] ?? "");
    r.onerror = () => mal(r.error);
    r.readAsDataURL(b);
  });
}

function blobDeBase64(b64: string, tipo: string): Blob {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Blob([bytes], { type: tipo });
}

export async function raizGuardada(): Promise<FileSystemDirectoryHandle | null> {
  try {
    return (await bd<FileSystemDirectoryHandle | undefined>("readonly", (s) => s.get("raiz"))) ?? null;
  } catch {
    return null;
  }
}

export async function olvidarRaiz(): Promise<void> {
  try { await bd("readwrite", (s) => s.delete("raiz")); } catch { /* sin IndexedDB */ }
}

type ConPermisos = FileSystemDirectoryHandle & {
  queryPermission(o: { mode: "readwrite" }): Promise<PermissionState>;
  requestPermission(o: { mode: "readwrite" }): Promise<PermissionState>;
};

/** ¿Hay permiso de escritura? Con `pedir` muestra el aviso del navegador (requiere un toque del usuario). */
export async function permiso(h: FileSystemDirectoryHandle, pedir: boolean): Promise<boolean> {
  const p = h as ConPermisos;
  if (typeof p.queryPermission !== "function") return true; // OPFS / navegadores sin la API de permisos
  if ((await p.queryPermission({ mode: "readwrite" })) === "granted") return true;
  return pedir && (await p.requestPermission({ mode: "readwrite" })) === "granted";
}

/** Abre el selector de carpetas; dentro de lo elegido crea «Prospector RMI» (salvo que ya se llame así). */
export async function elegirRaiz(): Promise<FileSystemDirectoryHandle> {
  const elegir = (window as unknown as {
    showDirectoryPicker(o: object): Promise<FileSystemDirectoryHandle>;
  }).showDirectoryPicker;
  const h = await elegir({ id: "prospector-rmi", mode: "readwrite", startIn: "documents" });
  const raiz = h.name === NOMBRE_RAIZ ? h : await h.getDirectoryHandle(NOMBRE_RAIZ, { create: true });
  try { await bd("readwrite", (s) => s.put(raiz, "raiz")); } catch { /* sin IndexedDB: dura esta sesión */ }
  return raiz;
}

async function dirDe(raiz: FileSystemDirectoryHandle, ruta: string[]) {
  let d = raiz;
  for (const parte of ruta) d = await d.getDirectoryHandle(nombreSeguro(parte), { create: true });
  return d;
}

async function escribirArchivo(d: FileSystemDirectoryHandle, nombre: string, datos: Blob | string) {
  const f = await d.getFileHandle(nombreSeguro(nombre), { create: true });
  const w = await f.createWritable();
  await w.write(datos);
  await w.close();
}

function blobDeDataUrl(dataUrl: string): Blob {
  const [cab, b64] = dataUrl.split(",", 2);
  return blobDeBase64(b64, /data:([^;]+)/.exec(cab)?.[1] ?? "application/octet-stream");
}

export function escritorLaptop(raiz: FileSystemDirectoryHandle): Escritor {
  return {
    donde: `${raiz.name} (en esta laptop)`,
    async texto(ruta, nombre, contenido) {
      await escribirArchivo(await dirDe(raiz, ruta), nombre, new Blob([contenido], { type: "text/plain;charset=utf-8" }));
    },
    async binario(ruta, nombre, dataUrl) {
      await escribirArchivo(await dirDe(raiz, ruta), nombre, blobDeDataUrl(dataUrl));
    },
    async archivo(ruta, nombre, datos) {
      await escribirArchivo(await dirDe(raiz, ruta), nombre, datos);
    },
    async leerArchivo(ruta, nombre) {
      try {
        let d = raiz;
        for (const parte of ruta) d = await d.getDirectoryHandle(nombreSeguro(parte));
        return await (await d.getFileHandle(nombreSeguro(nombre))).getFile();
      } catch {
        return null;
      }
    },
    async leerJsons() {
      const out: string[] = [];
      for await (const [, h] of (raiz as unknown as { entries(): AsyncIterable<[string, FileSystemHandle]> }).entries()) {
        if (h.kind !== "directory") continue;
        try {
          const f = await (h as FileSystemDirectoryHandle).getFileHandle("carpeta.json");
          out.push(await (await f.getFile()).text());
        } catch { /* subcarpeta sin carpeta.json */ }
      }
      return out;
    },
  };
}

// ------------------------------------------------------------------ app (APK)
export async function escritorApp(): Promise<Escritor> {
  const { Filesystem, Directory, Encoding } = await import("@capacitor/filesystem");
  try { await Filesystem.requestPermissions(); } catch { /* Android ≥ 11 no lo necesita */ }
  const ruta = (partes: string[], nombre: string) =>
    [NOMBRE_RAIZ, ...partes.map(nombreSeguro), nombreSeguro(nombre)].join("/");
  return {
    donde: `Documentos/${NOMBRE_RAIZ} (en este celular)`,
    async texto(partes, nombre, contenido) {
      await Filesystem.writeFile({ path: ruta(partes, nombre), data: contenido, directory: Directory.Documents,
        encoding: Encoding.UTF8, recursive: true });
    },
    async binario(partes, nombre, dataUrl) {
      await Filesystem.writeFile({ path: ruta(partes, nombre), data: dataUrl.split(",", 2)[1], directory: Directory.Documents,
        recursive: true });
    },
    async archivo(partes, nombre, datos) {
      await Filesystem.writeFile({ path: ruta(partes, nombre), data: await base64DeBlob(datos), directory: Directory.Documents,
        recursive: true });
    },
    async leerArchivo(partes, nombre, tipo) {
      try {
        const r = await Filesystem.readFile({ path: ruta(partes, nombre), directory: Directory.Documents });
        return typeof r.data === "string" ? blobDeBase64(r.data, tipo) : r.data;
      } catch {
        return null;
      }
    },
    async leerJsons() {
      const out: string[] = [];
      try {
        const { files } = await Filesystem.readdir({ path: NOMBRE_RAIZ, directory: Directory.Documents });
        for (const f of files.filter((x) => x.type === "directory")) {
          try {
            const r = await Filesystem.readFile({ path: `${NOMBRE_RAIZ}/${f.name}/carpeta.json`,
              directory: Directory.Documents, encoding: Encoding.UTF8 });
            out.push(String(r.data));
          } catch { /* sin carpeta.json */ }
        }
      } catch { /* aún no existe la carpeta raíz */ }
      return out;
    },
  };
}
