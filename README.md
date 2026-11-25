# Prospector RMI

App móvil (web instalable + APK Android) para que un geólogo encuentre **arena silícea** (y más adelante otros no metálicos) en el Perú, cuadrícula por cuadrícula, con distancias a la planta de San Vicente de Cañete.

```
Tocas una cuadrícula 1:25 000 (hoja 50K de INGEMMET ÷ 4) → «Analizar cuadrícula»
   │
   ├─ 1. Muestras RMI de INGEMMET en la cuadrícula (con SiO2, Fe2O3, Al2O3 de laboratorio)
   ├─ 2. Geología 1:50 000  → zonas favorables A/B/C (usa LITO1 = roca dominante)
   ├─ 3. Geología 1:100 000 → solo si la 50K no cubre o no tiene nada
   └─ 4. Sentinel-2 → "pureza" relativa de cada zona (poco Fe, poca arcilla, claro)
   ◀ ▲ ▼ ▶  pasar a la cuadrícula vecina · ✓ las analizadas quedan marcadas
```

- **Fábrica 🏭**: San Vicente de Cañete (Antigua Panamericana Sur). Ubicación fija (no se puede mover); todas las distancias (km en línea recta) salen de ahí.
- **★ Carpetas**: guarda las cuadrículas de interés en carpetas con nombre; cada una recopila zonas, muestras, Sentinel-2 y tus notas de campo, y se descarga como Excel (CSV). Se guardan en el dispositivo (navegador), no en un servidor.
- **📚 Explorar**: catálogo de formaciones silíceas (Chimú, Marcavilca, Hualhuani…) y depósitos — al elegir una, el mapa muestra solo esa en todo el Perú y las hojas donde aparece —, las ~209 muestras de INGEMMET ordenables por SiO2 o cercanía, y el historial «Mis cuadrículas».
- **Áreas protegidas y restringidas**: al analizar una cuadrícula se indica qué % de ella y de cada zona favorable cae en ANP (SERNANP), zonas de amortiguamiento, zonas arqueológicas, ANAP, zonas urbanas, etc., separando ⛔ no concesionable de ⚠ restringido (referencial: confirmar con INGEMMET y SERNANP).
- **🟩 Áreas libres**: capa para todo el Perú con la tierra sin derecho minero (catastro de INGEMMET) y fuera de áreas protegidas o restringidas. Al analizar una cuadrícula se da el % libre de ella y de cada zona favorable, con la lista de concesiones (titular, estado, sustancia). Se consulta en vivo; los análisis guardados se actualizan solos cada 7 días (o con «↻ Actualizar»).
- **Bibliografía** (pestaña de resultados): boletines de INGEMMET que cubren la zona (con enlace al repositorio), memorias citadas en la geología 1:50 000 y el mapa geológico integrado oficial de la hoja.
- **Mapa geológico descargable**: al guardar una cuadrícula en una carpeta, la app ofrece armar una lámina PNG 1:50 000 o 1:100 000 con leyenda y la guarda como adjunto.
- Los puntos RMI de INGEMMET **no son canteras**: son sitios muestreados en sus estudios regionales (en GEOCATMIN, hexágonos crema = arena silícea, azul = sílice).

Clases de zona favorable:

| Clase | Significado | Ejemplo de litología |
|---|---|---|
| **A** | La litología dice explícitamente que es cuarzosa (y es la roca dominante) | "Cuarcitas", "Areniscas cuarzosas blancas", "Arena cuarzosa" |
| **B** | Formación conocida como fuente de sílice, con alguna roca cuarzosa | Chimú, Farrat, Marcavilca, Goyllarisquizga (sin dividir), Hualhuani… |
| **C** | Compatible, verificar en campo | "Areniscas" sin más detalle, depósitos eólicos, cuarcitas subordinadas a lutitas |

Las reglas están en `backend/materiales.py`. Para activar **dolomía, caliza, etc.**, se agregan sus reglas ahí y se pone `"activo": True`.

## Por qué hay backend

GEOCATMIN **no envía cabeceras CORS**: el navegador puede mostrar sus imágenes, pero no leer sus datos (JSON). Es el mismo motivo por el que MineLINK usa FastAPI en Render (ver `errores_aprendidos.md` de MineLINK, 14/07/2026).

```
Celular ── Frontend (Vercel / APK) ──► imágenes de GEOCATMIN (directo)
                 │
                 └──► Backend FastAPI (Render) ──► GEOCATMIN /query
                                               └──► Copernicus (Sentinel-2)
```

## Probar en tu PC (10 minutos)

Requisitos: Python 3.11+ y Node 20+.

```bash
# Terminal 1: backend
cd backend
python -m venv venv
venv\Scripts\activate          # Windows (en Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Terminal 2: frontend
cd frontend
npm install
npm run dev                    # abre http://127.0.0.1:5173
```

Para Sentinel-2, crea `backend/.env` (copia de `backend/.env.example`; está en `.gitignore`, no se sube) con un cliente OAuth de Copernicus Data Space (https://shapps.dataspace.copernicus.eu/dashboard/ → User settings → OAuth clients → Create; el secret se ve una sola vez y los clientes pueden vencer):

```
CDSE_CLIENT_ID=sh-...
CDSE_CLIENT_SECRET=...
```

El backend lo lee al arrancar; `http://127.0.0.1:8000/health` debe decir `"sentinel": true`.

## Publicar para usarla en el celular

### 1. Backend en Render
1. Sube esta carpeta a un repositorio de GitHub nuevo (por ejemplo, `prospector-rmi`).
2. En Render: **New → Blueprint** y elige el repo. Usa `render.yaml`.
   (O bien: **New → Web Service**, raíz `backend`, build `pip install -r requirements.txt`, start `uvicorn main:app --host 0.0.0.0 --port $PORT`).
3. En **Environment**, agrega `CDSE_CLIENT_ID` y `CDSE_CLIENT_SECRET`.
4. Prueba `https://TU-BACKEND.onrender.com/health`: debe responder `{"status":"ok","sentinel":true}`.

### 2. Frontend en Vercel
1. **New Project** → el mismo repo → **Root Directory: `frontend`**.
2. Variable de entorno `VITE_API_URL` = la URL de Render (sin barra final).
3. Si el proyecto de Vercel no se llama `prospector-rmi`, agrega en Render `FRONTEND_URL=https://tu-app.vercel.app`.

### 3. Instalar en el celular
- **Android / iPhone (web instalable):** abre la URL de Vercel → menú del navegador → **"Agregar a pantalla de inicio"**.
- **APK Android (opcional):** necesitas Android Studio, igual que con MineLINK:
  ```bash
  cd frontend
  npm run android:add      # solo la primera vez
  npm run android:sync
  npm run android:open     # Build → Build APK(s)
  ```
  Para que las ★ Carpetas se creen en **Documentos/Prospector RMI** del celular (plugin `@capacitor/filesystem`), después de `android:add` agrega en `android/app/src/main/AndroidManifest.xml`:
  ```xml
  <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" />
  <uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" />
  <!-- y en <application ...>: android:requestLegacyExternalStorage="true"  (solo lo usa Android 10) -->
  ```

### Carpetas en el dispositivo
- **Laptop (Chrome o Edge):** 📚 → ★ Carpetas → «Elegir ubicación en la laptop» (p. ej. Documentos). Se crea `Prospector RMI\<carpeta>\` con `Resumen (Excel).csv`, `carpeta.json` y una subcarpeta por cuadrícula (`ficha.txt` + imágenes satelitales). El navegador pide el permiso otra vez en cada sesión («Dar permiso y guardar»). Firefox y Safari no lo permiten.
- **Celular con la APK:** automático en `Documentos/Prospector RMI/`.
- **Celular en el navegador:** no se pueden crear carpetas; usar «Descargar Excel».
- **Adjuntos:** en cada cuadrícula guardada (y en «Documentos generales» de la carpeta) se pueden adjuntar fotos (en el celular, también desde la cámara), PDF, Word, Excel o KML, hasta 30 MB cada uno. Se ven con miniatura y visor, y se copian a la subcarpeta `adjuntos` del dispositivo.
- La app nunca borra archivos del dispositivo (renombrar una carpeta crea otra con el nombre nuevo). Si se borran los datos del navegador, las carpetas se recuperan de los `carpeta.json`.

## Límites
- Área máxima por búsqueda: 2 500 km² (`AREA_MAX_KM2`). Sentinel-2 se lanza solo por cuadrícula 1:25 000 (~190 km², ~18 m/píxel, una petición de ~30 s); el backend además rechaza más de 600 km² (`SENTINEL_MAX_KM2`).
- Las distancias son en línea recta, no por carretera.
- En Lima e Ica INGEMMET casi no tiene muestras RMI con química: ahí pesa más la geología + Sentinel-2.
- La carta 50K puede tardar hasta 40 s.
- En Render gratis, la primera consulta del día tarda unos 50 s mientras el servidor despierta.
- Sentinel-2 usa **una sola toma**: la más despejada sobre la cuadrícula en 18 meses (se aceptan hasta 0,5 % de nubes dentro de la cuadrícula; si ninguna lo cumple, la de menos nubes, con aviso). La app muestra fecha y hora de la toma (hora Perú) y el % de nubes medido; los píxeles con nube o sombra se excluyen del cálculo.
- Cada análisis queda **guardado en el dispositivo**: volver a una cuadrícula analizada es instantáneo y no gasta créditos («🔄 Nueva toma» para actualizarla, «🗑 Borrar lo guardado» para liberar espacio).
- **Sentinel-2 no mide SiO₂.** La "pureza" es relativa a la cuadrícula analizada. El cuarzo se ve mejor en ASTER QICIMI, y lo definitivo es el muestreo.
- GEOCATMIN es información referencial de INGEMMET.

## Pruebas
```bash
cd backend && pip install -r requirements-dev.txt && python -m pytest -q    # GEOCATMIN simulado, sin internet
```

## Fase 2 (siguiente)
Análisis de concesiones dentro del área, reutilizando lo de MineLINK: catastro `SERV_CATASTRO_MINERO_WGS84/0` (titular, estado, hectáreas), `SERV_AREA_RESERVADA` (ANAP, zonas arqueológicas y urbanas), ANP de SERNANP, libre denunciabilidad y cuadrículas libres de 100 ha.
