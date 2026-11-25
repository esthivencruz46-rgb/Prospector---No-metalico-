"""API de Prospector RMI.

Endpoints:
  GET  /health        → {"status": "ok"}   (GET y HEAD, para UptimeRobot)
  GET  /materiales    → catálogo para el buscador
  POST /buscar        → cascada RMI → geología 50K → 100K dentro del área
  POST /sentinel      → índices Sentinel-2 de limpieza sobre el área (una cuadrícula 1:25 000)
  GET  /formaciones   → catálogo de formaciones/depósitos silíceos (+ /{id}/hojas)

La app (navegador o APK) no puede leer GEOCATMIN directo porque INGEMMET no
envía cabeceras CORS; por eso estas consultas pasan por aquí (mismo
esquema que MineLINK: frontend en Vercel, backend en Render).
"""

import os


def _cargar_env_local() -> None:
    """Lee backend/.env (si existe) para correr en la PC sin exportar
    variables a mano. No pisa variables ya definidas (en Render se usan las
    del panel). .env está en .gitignore: nunca se sube a GitHub."""
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(ruta):
        return
    with open(ruta, encoding="utf-8-sig") as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            valor = valor.strip().strip('"').strip("'")
            if valor:
                os.environ.setdefault(clave.strip(), valor)


_cargar_env_local()

from fastapi import FastAPI, HTTPException, Response  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import barrido
import bibliografia
import concesiones_info
import geocatmin_rmi
import libres
import mapa_geologico
import materias_primas  # carga las materias primas creadas en la app (datos/materias_primas.json)
import relieve
import restricciones
import rutas
import sentinel_silice
from materiales import filtro_texto, formaciones_publicas, lista_publica

app = FastAPI(title="Prospector RMI API", version="1.0.0")

origenes = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    # APK con Capacitor
    "http://localhost",
    "https://localhost",
    "capacitor://localhost",
]
frontend_url = os.environ.get("FRONTEND_URL", "").strip().strip('"').strip("'").rstrip("/")
if frontend_url:
    origenes.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origenes,
    # dominios de Vercel del proyecto y sus previews
    allow_origin_regex=os.environ.get(
        "FRONTEND_REGEX", r"https://prospector-rmi[a-z0-9-]*\.vercel\.app"),
    allow_methods=["*"],
    allow_headers=["*"],
)


class Busqueda(BaseModel):
    material: str = "arena_silicea"
    # anillo [[lng, lat], ...] en WGS84
    poligono: list[list[float]] = Field(..., min_length=3, max_length=500)


class AnalisisSentinel(BaseModel):
    poligono: list[list[float]] = Field(..., min_length=3, max_length=500)
    afloramientos: list[dict] = Field(default_factory=list, max_length=300)
    # zonas de la 1:100 000 para los modos de prioridad «1:100 000» y «ambas» (opcional)
    afloramientos_100k: list[dict] = Field(default_factory=list, max_length=300)


@app.get("/health")
@app.head("/health")
def health():
    import geologia_local
    try:
        geo = {e: v["fecha"] for e, v in geologia_local.estado().items() if v["completo"]}
    except Exception:  # noqa: BLE001
        geo = {}
    # geologia_local: escalas con copia local (fecha de descarga); sin ella se consulta GEOCATMIN en vivo
    return {"status": "ok", "sentinel": sentinel_silice.disponible(), "geologia_local": geo}


_ESTADO: dict = {"t": 0.0, "geocatmin": None}


@app.get("/estado")
def estado_servicios():
    """¿Responde GEOCATMIN? (para el indicador de la app; se revisa como máximo cada 60 s)."""
    import time as _t
    if _t.time() - _ESTADO["t"] > 60:
        try:
            r = geocatmin_rmi._SES.get(f"{geocatmin_rmi.BASE}/SERV_GEOLOGIA_100K_INTEGRADA/MapServer",
                                       params={"f": "json"}, timeout=8)
            _ESTADO["geocatmin"] = r.status_code == 200
        except Exception:  # noqa: BLE001
            _ESTADO["geocatmin"] = False
        _ESTADO["t"] = _t.time()
    return {"geocatmin": _ESTADO["geocatmin"], "sentinel": sentinel_silice.disponible(), **health()}


@app.get("/materiales")
def materiales():
    return lista_publica()


# ---------------------------------------------------------------- editor de materias primas
class DefMateria(BaseModel):
    id: str | None = None
    nombre: str = ""
    sinonimos: list[str] = []
    clases: dict[str, list[str]] = {}
    formaciones: list[str] = []
    descartar: list[str] = []
    rmi: list[str] = []
    nota: str = ""


class PruebaMateria(BaseModel):
    definicion: DefMateria
    litologia: str = ""
    unidad: str = ""
    roca_dominante: str = ""


@app.get("/materias_primas/{mid}")
def materia_ver(mid: str):
    d = materias_primas.publica(mid)
    if not d:
        raise HTTPException(status_code=404, detail="No existe esa materia prima.")
    return d


@app.post("/materias_primas")
def materia_guardar(d: DefMateria):
    try:
        g = materias_primas.guardar(d.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return g


@app.delete("/materias_primas/{mid}")
def materia_borrar(mid: str):
    if mid in materias_primas.FABRICA:
        raise HTTPException(status_code=422, detail="Las materias primas de fábrica no se borran.")
    if not materias_primas.borrar(mid):
        raise HTTPException(status_code=404, detail="No existe esa materia prima.")
    return {"ok": True}


@app.post("/materias_primas/probar")
def materia_probar(p: PruebaMateria):
    """Clasifica un texto de ejemplo con la definición (sin guardarla)."""
    try:
        return materias_primas.probar(p.definicion.model_dump(), {
            "LITOLOGIA": p.litologia, "UNIDAD": p.unidad, "LITO1": p.roca_dominante or None})
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e




@app.get("/formaciones")
def formaciones(material: str = "arena_silicea"):
    """Catálogo de formaciones/depósitos con sus filtros SQL para el mapa."""
    return formaciones_publicas(material)


@app.get("/formaciones/{fid}/hojas")
def hojas_formacion(fid: str, material: str = "arena_silicea"):
    """Hojas 1:50 000 donde aparece la formación (para ir a ellas)."""
    try:
        return geocatmin_rmi.hojas_de_formacion(material, fid)
    except geocatmin_rmi.ErrorBusqueda as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"GEOCATMIN no respondió ({type(e).__name__}).") from e


@app.get("/geologia/filtro")
def geologia_filtro(texto: str):
    """Texto libre (p. ej. "Chimú", "cuarcita", "arena cuarzosa") → filtro de mapa."""
    f = filtro_texto(texto)
    if not f:
        raise HTTPException(status_code=422, detail="Escribe al menos una palabra de 3 letras.")
    return f


@app.get("/geologia/hojas")
def geologia_hojas(texto: str):
    """Hojas 1:50 000 donde aparece el texto buscado."""
    f = filtro_texto(texto)
    if not f:
        raise HTTPException(status_code=422, detail="Escribe al menos una palabra de 3 letras.")
    try:
        return geocatmin_rmi.hojas_por_sql(f["id"], f["sql50"])
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"GEOCATMIN no respondió ({type(e).__name__}).") from e


@app.get("/bibliografia")
def bibliografia_zona(sur: float, oeste: float, norte: float, este: float):
    """Boletines, memorias y mapas oficiales de INGEMMET que cubren la cuadrícula."""
    if not (-19 < sur < norte < 1 and -82 < oeste < este < -68) or norte - sur > 0.6 or este - oeste > 0.6:
        raise HTTPException(status_code=422, detail="Área fuera del Perú o demasiado grande.")
    try:
        return bibliografia.consultar(sur, oeste, norte, este)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"GEOCATMIN no respondió ({type(e).__name__}).") from e


class ItemVigilado(BaseModel):
    id: str
    anillo: list[list[float]]
    previo: dict | None = None
    propio: bool = False


class PeticionVigilancia(BaseModel):
    items: list[ItemVigilado] = Field(..., min_length=1, max_length=60)


@app.post("/vigilancia/revisar")
def vigilancia_revisar(p: PeticionVigilancia):
    """Compara el catastro actual de INGEMMET con la foto anterior de cada área vigilada (ver vigilancia.py)."""
    import vigilancia
    return vigilancia.revisar([i.model_dump() for i in p.items])


@app.get("/ranking")
def ranking_nacional():
    """Ranking nacional de cuadrículas con geología A/B libre y utilizable (censos guardados; sin GEOCATMIN)."""
    import ranking
    return {**ranking.resumen(), "filas": ranking.filas(), "vidrio": ranking.vidrio(), "descripcion": ranking.descripcion()}


@app.get("/supermaduras")
def supermaduras_todo():
    """Unidades supermaduras (fichas, citas de boletines, cuadrículas 1:25 000), química de canteras y ocurrencias."""
    import supermaduras
    d = supermaduras.datos()
    if not d:
        raise HTTPException(503, "Falta datos/supermaduras.json (correr scripts/supermaduras/exportar_app.py)")
    return d


@app.get("/supermaduras/foto/{archivo}")
def supermaduras_foto(archivo: str):
    """Foto recortada de un boletín de INGEMMET (JPEG)."""
    import supermaduras
    from fastapi.responses import FileResponse
    ruta = supermaduras.ruta_foto(archivo)
    if not ruta:
        raise HTTPException(404, "No existe esa foto")
    return FileResponse(ruta, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=604800"})


@app.get("/supermaduras/celda/{codigo}")
def supermaduras_celda(codigo: str):
    """Unidades supermaduras, canteras y ocurrencias dentro de una cuadrícula 1:25 000."""
    import supermaduras
    try:
        return supermaduras.en_celda(codigo)
    except ValueError as ex:
        raise HTTPException(400, str(ex))


class PeticionLamina(BaseModel):
    tipo: str = "geologia"            # geologia · arcillas · hierro · libres · prioridad · ruta
    titulo: str = ""
    subtitulo: str = ""
    autor: str = ""
    empresa: str = ""                 # membrete (p. ej. KEDA Perú Building Materials Company)
    proyecto: str = ""                # cajetín
    lamina: str = ""                  # N.º de lámina («01»)
    total: str = ""                   # total de láminas del juego
    escala: str = "50K"               # geología completa: carta 1:50 000 o 1:100 000
    fuente: str = ""
    celda: dict | None = None         # {codigo, sur, oeste, norte, este}
    capas: list[dict] = []            # [{png (data URL), crs "4326"|"3857", bbox [o,s,e,n], opacidad}]
    zonas: list[dict] = []            # [{clase, unidad, geometria, relleno}]
    leyenda: list[dict] = []          # [{color, texto, forma}]
    datos: list[list] = []            # [[clave, valor]]
    ruta: dict | None = None          # {origen, destino, bloques, km_total, km_linea_recta}
    secciones: list[dict] = []        # páginas de texto (tipo «texto»)
    # informe PDF (portada · antecedentes · análisis): datos que ya tiene la app
    hoja100: str = ""
    materia: str = ""
    toma: str = ""
    contenido: list[str] = []
    zonas_s2: list[dict] = []
    imagen: dict = {}
    libres: dict = {}
    restricciones: list[dict] = []
    prioridad: dict = {}
    pct_valida: float = 0
    ha_celda: float = 0
    ruta_km: float = 0
    ruta_pista: float = 0
    ruta_trocha: float = 0
    unidades: list[dict] = []          # unidades elegidas para la Prioridad (página «unidades» del informe)


def _lamina_png(q: dict) -> bytes:
    """PNG de una página del informe según su tipo (lámina, descripción geológica, portada, texto…)."""
    import informe
    import laminas
    armar = {"geologia_desc": laminas.descripcion_geologica, "texto": laminas.pagina_texto, "portada": informe.portada,
             "antecedentes": informe.antecedentes, "unidades": informe.unidades,
             "analisis": informe.analisis}.get(q.get("tipo"), laminas.generar)
    return armar(q)


def _pdf_de_imagenes(imgs: list, titulo: str) -> bytes:
    """PDF A3 a 150 ppp con las páginas en JPEG calidad 70 (texto legible; ~40 % menos que antes)."""
    from io import BytesIO
    buf = BytesIO()
    imgs[0].save(buf, "PDF", save_all=True, append_images=imgs[1:], resolution=150, quality=70, subsampling=2,
                 title=titulo[:120], author="Prospector RMI")
    return buf.getvalue()


@app.post("/lamina")
def lamina(p: PeticionLamina):
    """Lámina cartográfica profesional (PNG A3 apaisado, 150 ppp): ver laminas.py."""
    if not p.celda and not p.ruta:
        raise HTTPException(status_code=422, detail="Falta la cuadrícula o la ruta.")
    try:
        png = _lamina_png(p.model_dump())
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return Response(content=png, media_type="image/png")


# ---------------------------------------------------------------- INFORME PDF en el servidor (24/11/2026)
# Todas las páginas se generan EN PARALELO (4 a la vez) en un hilo de fondo; la app consulta el avance y baja el PDF.
_INFORMES: dict[str, dict] = {}


class PeticionInforme(BaseModel):
    titulo: str = "Informe"
    nombre: str = "informe.pdf"
    paginas: list[PeticionLamina] = Field(..., min_length=1, max_length=24)


@app.post("/informe")
def informe_iniciar(p: PeticionInforme):
    import threading
    import uuid
    from concurrent.futures import ThreadPoolExecutor
    from io import BytesIO
    from PIL import Image
    for k in [k for k, v in _INFORMES.items() if v["estado"] != "trabajando"][:-5]:   # se guardan los 5 últimos
        _INFORMES.pop(k, None)
    iid = uuid.uuid4().hex[:12]
    job = {"estado": "trabajando", "total": len(p.paginas), "hechas": 0, "errores": [], "pdf": None,
           "titulo": p.titulo, "nombre": p.nombre}
    _INFORMES[iid] = job
    paginas = [x.model_dump() for x in p.paginas]

    def una(q):
        try:
            png = _lamina_png(q)
            return Image.open(BytesIO(png)).convert("RGB")
        except Exception as e:  # noqa: BLE001
            job["errores"].append(f"{q.get('titulo') or q.get('tipo')}: {e}")
            return None
        finally:
            job["hechas"] += 1

    def trabajar():
        try:
            with ThreadPoolExecutor(4) as ex:
                imgs = [i for i in ex.map(una, paginas) if i is not None]
            if not imgs:
                raise RuntimeError("no se pudo generar ninguna página")
            job["pdf"] = _pdf_de_imagenes(imgs, p.titulo)
            job["estado"] = "listo"
        except Exception as e:  # noqa: BLE001
            job["estado"] = "error"
            job["errores"].append(str(e))

    threading.Thread(target=trabajar, daemon=True).start()
    return {"id": iid, "total": job["total"]}


@app.get("/informe/{iid}")
def informe_estado(iid: str):
    j = _INFORMES.get(iid)
    if not j:
        raise HTTPException(404, "Informe no encontrado (¿se reinició el servidor?).")
    return {"estado": j["estado"], "total": j["total"], "hechas": j["hechas"], "errores": j["errores"],
            "mb": round(len(j["pdf"]) / 1e6, 1) if j["pdf"] else None}


@app.get("/informe/{iid}/pdf")
def informe_pdf(iid: str):
    j = _INFORMES.get(iid)
    if not j or not j["pdf"]:
        raise HTTPException(404, "El PDF todavía no está listo.")
    return Response(content=j["pdf"], media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{j["nombre"]}"'})


# ---------------------------------------------------------------- EXPORTACIÓN SIG (KMZ / shapefile)
class PeticionExportar(BaseModel):
    formato: str = "kmz"              # kmz · shp
    celda: dict
    zonas: list[dict] = Field(default_factory=list, max_length=300)
    prioridad: dict | None = None     # {png (data URL de la Prioridad libre), bbox [o, s, e, n]}


@app.post("/exportar")
def exportar(p: PeticionExportar):
    import exportar_sig
    try:
        datos, tipo, nombre = exportar_sig.exportar(p.model_dump())
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return Response(content=datos, media_type=tipo, headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


class PeticionPdf(BaseModel):
    paginas: list[str]                # láminas PNG (data URL), una por página
    titulo: str = "Láminas"


@app.post("/pdf")
def laminas_pdf(p: PeticionPdf):
    """Une las láminas (PNG A3 de /lamina) en UN PDF de varias páginas, A3 apaisado a 150 ppp."""
    import base64
    from io import BytesIO
    from PIL import Image
    if not 1 <= len(p.paginas) <= 20:
        raise HTTPException(status_code=422, detail="Entre 1 y 20 láminas por PDF.")
    imgs = []
    for d in p.paginas:
        try:
            imgs.append(Image.open(BytesIO(base64.b64decode(d.split(",", 1)[-1]))).convert("RGB"))
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=422, detail="Una de las láminas no es una imagen válida.") from e
    return Response(content=_pdf_de_imagenes(imgs, p.titulo), media_type="application/pdf")


@app.get("/mapa_geologico")
def mapa_geologico_png(sur: float, oeste: float, norte: float, este: float, escala: str = "50K", titulo: str = ""):
    """Lámina PNG del mapa geológico 1:50 000 o 1:100 000 de una cuadrícula (con leyenda)."""
    if escala not in mapa_geologico.CONFIG:
        raise HTTPException(status_code=422, detail="Escala: 50K o 100K.")
    if not (-19 < sur < norte < 1 and -82 < oeste < este < -68) or norte - sur > 0.6 or este - oeste > 0.6:
        raise HTTPException(status_code=422, detail="Área fuera del Perú o demasiado grande (máx. una hoja 1:50 000).")
    try:
        png = mapa_geologico.generar(sur, oeste, norte, este, escala, titulo[:40])
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"No se pudo armar el mapa: GEOCATMIN no respondió ({type(e).__name__}).") from e
    return Response(content=png, media_type="image/png")


class Poligono(BaseModel):
    poligono: list[list[float]] = Field(..., min_length=3, max_length=500)


@app.post("/restricciones")
def restricciones_area(p: Poligono):
    """Áreas protegidas y restringidas para concesiones dentro del polígono (para «solo satélite»)."""
    try:
        pol = geocatmin_rmi.validar_poligono(p.poligono)
        return restricciones.publicas(restricciones.consultar(pol))
    except geocatmin_rmi.ErrorBusqueda as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"GEOCATMIN no respondió ({type(e).__name__}).") from e


class PeticionLibres(BaseModel):
    poligono: list[list[float]] = Field(..., min_length=3, max_length=500)
    # zonas favorables ya calculadas ({id, geometria GeoJSON}) para recalcular su % libre
    zonas: list[dict] = Field(default_factory=list, max_length=300)


@app.post("/libres")
def libres_area(p: PeticionLibres):
    """Áreas libres (sin derecho minero y fuera de áreas protegidas/restringidas) dentro de
    una cuadrícula, más las restricciones y el % libre de cada zona. Siempre en vivo: sirve
    para «solo satélite» y para actualizar análisis guardados hace más de una semana."""
    from shapely.geometry import shape
    try:
        pol = geocatmin_rmi.validar_poligono(p.poligono)
        areas = restricciones.consultar(pol)
        cons = libres.concesiones(pol)
        r = libres.calcular(pol, cons, areas)
        por_zona = {}
        for z in p.zonas:
            try:
                geom = shape(z["geometria"])
                por_zona[str(z["id"])] = {"libre_pct": libres.libre_en_zona(r, geom),
                                          "util_pct": libres.util_en_zona(r, geom),
                                          "negociable_pct": libres.negociable_en_zona(r, geom),
                                          "concesiones": concesiones_info.en_zona(cons, geom),
                                          "restriccion": restricciones.en_zona(areas, geom)}
            except Exception:  # noqa: BLE001
                continue
        # geología favorable debajo de cada derecho (las zonas traen clase/unidad desde la app)
        zonas_geo = [z for z in p.zonas if z.get("clase") in ("A", "B", "C") and z.get("geometria")]
        if zonas_geo:
            try:
                concesiones_info.geologia_debajo(cons, [{"unidad": "", **z} for z in zonas_geo])
                r["concesiones"] = [{k: v for k, v in x.items() if not k.startswith("_")} for x in cons]
            except Exception:  # noqa: BLE001
                pass
        return {"restricciones": restricciones.publicas(areas), "libres": libres.publico(r), "zonas": por_zona}
    except geocatmin_rmi.ErrorBusqueda as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"GEOCATMIN no respondió ({type(e).__name__}).") from e


@app.get("/libres/imagen")
def libres_imagen(oeste: float, sur: float, este: float, norte: float, ancho: int = 1024, alto: int = 768, modo: str = "mapa"):
    """PNG transparente de la vista del mapa con las áreas libres en verde (todo el Perú)."""
    if not (-25 < sur < norte < 5 and -90 < oeste < este < -60):
        raise HTTPException(status_code=422, detail="Vista fuera del Perú.")
    try:
        png = libres.imagen(oeste, sur, este, norte, ancho, alto, modo)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"GEOCATMIN no respondió ({type(e).__name__}).") from e
    # una hora en caché del navegador: INGEMMET actualiza el catastro a diario
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})


class CeldaBarrido(BaseModel):
    codigo: str
    sur: float
    oeste: float
    norte: float
    este: float


class PeticionBarrido(BaseModel):
    celdas: list[CeldaBarrido] = Field(..., min_length=1, max_length=barrido.MAX_CELDAS)
    material: str = "arena_silicea"


@app.post("/barrido")
def barrido_iniciar(p: PeticionBarrido):
    """Barrido de una región (varias cuadrículas, sin Sentinel-2): trabajo en segundo plano."""
    try:
        return {"id": barrido.iniciar([c.model_dump() for c in p.celdas], p.material), "total": len(p.celdas)}
    except geocatmin_rmi.ErrorBusqueda as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.get("/barrido/{tid}")
def barrido_estado(tid: str, desde: int = 0):
    try:
        return barrido.estado(tid, desde)
    except KeyError as e:
        raise HTTPException(status_code=404, detail="Ese barrido ya no existe (¿se reinició el servidor?).") from e


@app.delete("/barrido/{tid}")
def barrido_cancelar(tid: str):
    barrido.cancelar(tid)
    return {"ok": True}


@app.get("/curvas")
def curvas(sur: float, oeste: float, norte: float, este: float, intervalo: float = 0):
    """Curvas de nivel (Copernicus DEM 30 m) del recuadro, como PNG en data URL + sus límites."""
    if not (-19 < sur < norte < 1 and -82 < oeste < este < -68) or norte - sur > 0.6 or este - oeste > 0.6:
        raise HTTPException(status_code=422, detail="Área fuera del Perú o demasiado grande (máx. una hoja 1:50 000).")
    try:
        png, lim = relieve.curvas_png(sur, oeste, norte, este, intervalo)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"No se pudo leer el relieve ({type(e).__name__}).") from e
    import base64
    return {"png": "data:image/png;base64," + base64.b64encode(png).decode(), **lim}


class PeticionTonelaje(BaseModel):
    geometria: dict
    tipo: str | None = None              # «arena» | «roca» (geocatmin_rmi.tipo_material)
    densidad: float | None = Field(None, gt=0.5, lt=4)
    potencia_max: float | None = Field(None, gt=0, lt=500)
    potencia_manto: float | None = Field(None, gt=0, lt=500)
    libre: dict | None = None            # GeoJSON del área libre de la cuadrícula
    zona: dict | None = None             # unidad/litologia/descripcion/roca_dominante → tipo, si no viene


@app.post("/tonelaje")
def tonelaje(p: PeticionTonelaje):
    """Volumen y tonelaje estimados de una zona con el relieve (3 métodos, uno recomendado)."""
    tipo = p.tipo or (geocatmin_rmi.tipo_material(p.zona) if p.zona else None)
    try:
        r = relieve.tonelaje(p.geometria, tipo, p.densidad, p.potencia_max, p.libre, p.potencia_manto)
        return {**r, "tipo": tipo}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"No se pudo calcular el tonelaje ({type(e).__name__}).") from e


@app.get("/ruta")
def ruta(lat1: float, lon1: float, lat2: float, lon2: float):
    """Distancia y tiempo POR CARRETERA de la fábrica (lat1, lon1) a un punto (lat2, lon2)."""
    for lat, lon in ((lat1, lon1), (lat2, lon2)):
        if not (-19 < lat < 1 and -82 < lon < -68):
            raise HTTPException(status_code=422, detail="Punto fuera del Perú.")
    try:
        return rutas.ruta(lat1, lon1, lat2, lon2)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"El servicio de rutas no respondió ({type(e).__name__}).") from e


@app.get("/hojas100")
def hojas100():
    """Hojas 1:100 000 (código y nombre) para el buscador de cuadrángulos."""
    try:
        return geocatmin_rmi.hojas_100k()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"GEOCATMIN no respondió ({type(e).__name__}).") from e




@app.post("/buscar")
def buscar(b: Busqueda):
    try:
        return geocatmin_rmi.buscar(b.material, b.poligono)
    except geocatmin_rmi.ErrorBusqueda as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=502,
            detail=f"GEOCATMIN no respondió a tiempo. Intenta de nuevo en un momento. ({type(e).__name__})",
        ) from e


@app.post("/sentinel")
def sentinel(a: AnalisisSentinel):
    try:
        pol = geocatmin_rmi.validar_poligono(a.poligono)
    except geocatmin_rmi.ErrorBusqueda as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    if geocatmin_rmi.area_ha(pol) / 100 > float(os.environ.get("SENTINEL_MAX_KM2", "600")):
        raise HTTPException(
            status_code=422,
            detail="Para Sentinel-2 dibuja un área de hasta 600 km² (cuida tus créditos de Copernicus).")
    anillo = [list(p) for p in pol.exterior.coords]
    try:
        return sentinel_silice.analizar(anillo, a.afloramientos, a.afloramientos_100k)
    except Exception as e:  # noqa: BLE001
        if "InvalidClient" in type(e).__name__ or "invalid_client" in str(e):
            raise HTTPException(
                status_code=502,
                detail="Copernicus rechazó las credenciales (CDSE_CLIENT_ID / CDSE_CLIENT_SECRET). "
                       "Revisa que estén bien copiadas o crea un cliente OAuth nuevo.") from e
        raise HTTPException(
            status_code=502,
            detail=f"Copernicus no respondió ({type(e).__name__}). Intenta de nuevo.") from e
