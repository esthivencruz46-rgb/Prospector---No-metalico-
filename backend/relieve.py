"""Relieve: curvas de nivel y TONELAJE estimado de una zona favorable.

Fuente: Copernicus DEM GLO-30 (30 m, ESA), copia pública en AWS Open Data (sin cuenta):
https://copernicus-dem-30m.s3.amazonaws.com — mosaicos de 1° × 1° (~19 MB) que se bajan la primera
vez y se guardan en `backend/cache_dem/` (después es instantáneo). Se usa el DEM y no las curvas de
nivel vectoriales del IGN (GEOCATMIN): las curvas se DIBUJAN desde el DEM, y para calcular volúmenes
hace falta la superficie continua.

Tonelaje (método de volumen sobre una superficie base, típico para dunas, mantos y cerros):
1. Se rasteriza la zona sobre la grilla del DEM (1″ ≈ 30 m).
2. Superficie BASE = plano ajustado (mínimos cuadrados) a la cota del BORDE de la zona: es el nivel
   del terreno que la rodea (sirve en laderas: el plano se inclina con el terreno).
3. Espesor por píxel = cota − base (≥ 0), limitado opcionalmente a una potencia máxima de minado.
4. Volumen = Σ espesor × área del píxel; tonelaje = volumen × densidad aparente.
Es una estimación de ORDEN DE MAGNITUD: el DEM es de 30 m (±4 m de error vertical), no sabe qué hay
bajo la base ni dónde termina el material. Confirmar con topografía, calicatas o sondajes.
"""

from __future__ import annotations

import os
import threading
from io import BytesIO
from math import cos, floor, radians

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from shapely.geometry import shape

import geocatmin_rmi as g

CARPETA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache_dem")
URL = "https://copernicus-dem-30m.s3.amazonaws.com/{n}/{n}.tif"
PX = 1 / 3600                     # 1 segundo de arco (en latitudes del Perú los mosaicos son 3600 × 3600)
DENSIDAD = {"arena": 1.6, "roca": 2.5, None: 2.0}   # t/m³: arena suelta · arenisca/cuarcita · sin dato
_candados: dict[str, threading.Lock] = {}
_candado = threading.Lock()


# ----------------------------------------------------------------- DEM
def _nombre(lat0: int, lon0: int) -> str:
    """Mosaico cuya esquina SO es (lat0, lon0)."""
    ns = f"{'N' if lat0 >= 0 else 'S'}{abs(lat0):02d}"
    ew = f"{'E' if lon0 >= 0 else 'W'}{abs(lon0):03d}"
    return f"Copernicus_DSM_COG_10_{ns}_00_{ew}_00_DEM"


def _mosaico(lat0: int, lon0: int) -> np.ndarray | None:
    """Mosaico 1° × 1° (float32, fila 0 = norte). Se baja una sola vez; None = sobre el mar."""
    n = _nombre(lat0, lon0)
    ruta = os.path.join(CARPETA, n + ".tif")
    with _candado:
        lk = _candados.setdefault(n, threading.Lock())
    with lk:
        if not os.path.exists(ruta):
            os.makedirs(CARPETA, exist_ok=True)
            r = g._SES.get(URL.format(n=n), timeout=300)
            if r.status_code in (403, 404):      # no existe: es océano
                open(ruta + ".vacio", "w").close()
                return None
            r.raise_for_status()
            tmp = ruta + ".part"
            with open(tmp, "wb") as f:
                f.write(r.content)
            os.replace(tmp, ruta)
        if os.path.exists(ruta + ".vacio"):
            return None
        return np.asarray(Image.open(ruta), dtype=np.float32)


def falta_descargar(sur: float, oeste: float, norte: float, este: float) -> list[str]:
    """Mosaicos que aún no están en el disco (para avisar «la primera vez tarda ~1 min»)."""
    out = []
    for la in range(floor(sur), floor(norte - 1e-9) + 1):
        for lo in range(floor(oeste), floor(este - 1e-9) + 1):
            n = _nombre(la, lo)
            if not os.path.exists(os.path.join(CARPETA, n + ".tif")) and not os.path.exists(os.path.join(CARPETA, n + ".tif.vacio")):
                out.append(n)
    return out


def dem(sur: float, oeste: float, norte: float, este: float) -> tuple[np.ndarray, tuple]:
    """Cotas (m) del recuadro en la grilla de 1″, armando los mosaicos que hagan falta.
    Devuelve (z, (norte_px, oeste_px)) con la esquina NO del primer píxel (NaN = mar/sin dato)."""
    n0, o0 = np.ceil(norte / PX) * PX, np.floor(oeste / PX) * PX
    filas = int(round((n0 - np.floor(sur / PX) * PX) / PX))
    cols = int(round((np.ceil(este / PX) * PX - o0) / PX))
    z = np.full((filas, cols), np.nan, dtype=np.float32)
    for la in range(floor(sur), floor(norte - 1e-9) + 1):
        for lo in range(floor(oeste), floor(este - 1e-9) + 1):
            m = _mosaico(la, lo)
            if m is None:
                continue
            # índices del mosaico (fila 0 = lat la+1) que caen en el recuadro
            f_ini = max(0, int(round((la + 1 - n0) / PX)))
            f_fin = min(m.shape[0], int(round((la + 1 - (n0 - filas * PX)) / PX)))
            c_ini = max(0, int(round((o0 - lo) / PX)))
            c_fin = min(m.shape[1], int(round((o0 + cols * PX - lo) / PX)))
            if f_fin <= f_ini or c_fin <= c_ini:
                continue
            zf = int(round((la + 1 - f_ini * PX - n0) / -PX))
            zc = int(round((lo + c_ini * PX - o0) / PX))
            z[zf:zf + (f_fin - f_ini), zc:zc + (c_fin - c_ini)] = m[f_ini:f_fin, c_ini:c_fin]
    z[z < -100] = np.nan
    return z, (float(n0), float(o0))


def _rasterizar(geom, forma: tuple[int, int], esquina: tuple[float, float]) -> np.ndarray:
    filas, cols = forma
    n0, o0 = esquina
    lienzo = Image.new("L", (cols, filas), 0)
    d = ImageDraw.Draw(lienzo)

    def px(x, y):
        return ((x - o0) / PX, (n0 - y) / PX)

    for p in getattr(geom, "geoms", [geom]):
        if p.geom_type != "Polygon":
            continue
        d.polygon([px(*c[:2]) for c in p.exterior.coords], fill=255)
        for h in p.interiors:
            d.polygon([px(*c[:2]) for c in h.coords], fill=0)
    return np.asarray(lienzo) > 0


# ----------------------------------------------------------------- CURVAS DE NIVEL
def curvas_png(sur: float, oeste: float, norte: float, este: float, intervalo: float = 0) -> tuple[bytes, dict]:
    """PNG transparente con curvas de nivel (cada `intervalo` m; maestras cada 5) del recuadro, en la
    grilla lineal lat/lon (se superpone con L.imageOverlay sobre esos límites)."""
    z, (n0, o0) = dem(sur, oeste, norte, este)
    if not np.isfinite(z).any():
        raise ValueError("Sin datos de elevación (¿mar?).")
    zmin, zmax = float(np.nanmin(z)), float(np.nanmax(z))
    if not intervalo:   # ~25 curvas en la vista, redondeado a 5/10/20/25/50/100 m
        bruto = max((zmax - zmin) / 25, 1)
        intervalo = next(v for v in (5, 10, 20, 25, 50, 100, 200) if v >= bruto)
    # se dibuja al doble de resolución para que las líneas salgan suaves
    zz = np.asarray(Image.fromarray(np.nan_to_num(z, nan=zmin)).resize((z.shape[1] * 2, z.shape[0] * 2), Image.BILINEAR))
    lv = np.floor(zz / intervalo)
    borde = np.zeros(zz.shape, dtype=bool)
    borde[:, 1:] |= lv[:, 1:] != lv[:, :-1]
    borde[1:, :] |= lv[1:, :] != lv[:-1, :]
    maestra = borde & (np.floor(zz / (5 * intervalo)) != np.floor(np.roll(zz, 1, axis=1) / (5 * intervalo)))
    maestra |= borde & (np.floor(zz / (5 * intervalo)) != np.floor(np.roll(zz, 1, axis=0) / (5 * intervalo)))
    rgba = np.zeros(zz.shape + (4,), dtype=np.uint8)
    rgba[borde] = (120, 72, 20, 170)
    mm = np.asarray(Image.fromarray((maestra * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))) > 0
    rgba[mm] = (92, 45, 10, 235)
    out = BytesIO()
    Image.fromarray(rgba, "RGBA").save(out, "PNG", optimize=True)
    # límites EXACTOS de la imagen (múltiplos de 1″)
    lim = {"norte": n0, "oeste": o0, "sur": n0 - z.shape[0] * PX, "este": o0 + z.shape[1] * PX,
           "intervalo_m": intervalo, "cota_min": round(zmin), "cota_max": round(zmax)}
    return out.getvalue(), lim


# ----------------------------------------------------------------- TONELAJE
# Tres métodos, porque no hay uno que sirva para todo (un manto de arena eólica que tapiza cerros de
# roca NO es un cerro de arena):
#  «cerro»: volumen sobre el plano del borde de la zona → cerro o duna aislada (zonas chicas).
#  «dunas»: solo el relieve LOCAL (DEM − su «apertura» morfológica de ~300 m) → campos de dunas:
#           cuenta la arena de las dunas sobre el piso interdunar, no los cerros de roca de abajo.
#  «manto»: área × potencia (dato) → mantos, bancos y capas extensas (la cifra más conservadora).
POTENCIA_MANTO = {"arena": 5.0, "roca": 10.0, None: 5.0}   # m, por defecto
VENTANA_DUNAS_M = 300
AREA_MAX_CERRO_HA = 300


def tonelaje(geometria: dict, tipo: str | None = None, densidad: float | None = None,
             potencia_max: float | None = None, libre: dict | None = None, potencia_manto: float | None = None) -> dict:
    """Volumen y tonelaje del material de una zona por los tres métodos, con uno recomendado.
    `libre` (GeoJSON) = área libre de la cuadrícula: se da además cada cifra solo en lo libre."""
    zona = g._limpiar(shape(geometria))
    if zona is None or zona.is_empty:
        raise ValueError("Zona vacía.")
    oeste, sur, este, norte = zona.bounds
    lat = (sur + norte) / 2
    m_px = PX * 110540
    k = max(3, int(round(VENTANA_DUNAS_M / m_px)) | 1)          # ventana impar en píxeles
    mg = (k + 3) * PX                                           # margen: el borde y la ventana completos
    z, esq = dem(sur - mg, oeste - mg, norte + mg, este + mg)
    dentro = _rasterizar(zona, z.shape, esq) & np.isfinite(z)
    if dentro.sum() < 4:
        raise ValueError("La zona es demasiado pequeña para el DEM de 30 m.")
    a_px = (PX * 111320 * cos(radians(lat))) * m_px              # m² por píxel
    dens = float(densidad or DENSIDAD.get(tipo, DENSIDAD[None]))
    zr = np.nan_to_num(z, nan=float(np.nanmin(z)))

    # «cerro»: plano ajustado a la cota del borde (sin el 10 % más alto, que suele trepar laderas)
    erosion = np.asarray(Image.fromarray((dentro * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3))) > 0
    borde = dentro & ~erosion
    if borde.sum() < 3:
        borde = dentro
    filas, cols = np.nonzero(borde)
    zb = z[filas, cols]
    ok = zb <= np.percentile(zb, 90)
    coef, *_ = np.linalg.lstsq(np.column_stack([np.ones(ok.sum()), cols[ok], filas[ok]]), zb[ok], rcond=None)
    ff, cc = np.indices(z.shape)
    esp_cerro = np.clip(z - (coef[0] + coef[1] * cc + coef[2] * ff), 0, None)

    # «dunas»: relieve local = DEM − apertura morfológica (mínimo y luego máximo en la ventana)
    piso = np.asarray(Image.fromarray(zr.astype(np.float32), "F").filter(ImageFilter.MinFilter(k)).filter(ImageFilter.MaxFilter(k)))
    esp_dunas = np.clip(zr - piso, 0, None)

    pot = float(potencia_manto or POTENCIA_MANTO.get(tipo, POTENCIA_MANTO[None]))
    esp_manto = np.full(z.shape, pot, dtype=np.float32)
    if potencia_max:
        esp_cerro = np.minimum(esp_cerro, potencia_max)
        esp_dunas = np.minimum(esp_dunas, potencia_max)

    lib = None
    if libre:
        try:
            lg = g._limpiar(shape(libre))
            if lg is not None and not lg.is_empty:
                lib = dentro & _rasterizar(lg, z.shape, esq)
        except Exception:  # noqa: BLE001
            lib = None

    def cifras(esp, mascara):
        e = np.where(mascara, esp, 0)[mascara]
        vol = float(e.sum() * a_px)
        return {"area_ha": round(float(mascara.sum()) * a_px / 1e4, 1), "volumen_m3": round(vol),
                "toneladas": round(vol * dens), "espesor_medio_m": round(float(e.mean()), 1) if e.size else 0,
                "espesor_max_m": round(float(e.max()), 1) if e.size else 0}

    def metodo(nombre, esp, explica):
        out = {"metodo": nombre, "explica": explica, "total": cifras(esp, dentro)}
        if lib is not None:
            out["libre"] = cifras(esp, lib)
        return out

    area_ha = float(dentro.sum()) * a_px / 1e4
    recomendado = "cerro" if area_ha <= AREA_MAX_CERRO_HA else "dunas" if tipo == "arena" else "manto"
    metodos = {
        "cerro": metodo("Cerro o duna aislada", esp_cerro,
                        "Volumen por encima del terreno que rodea la zona (plano ajustado a la cota de su borde). "
                        "Bueno para zonas chicas que sobresalen; en zonas grandes cuenta también los cerros de roca de abajo."),
        "dunas": metodo("Dunas (relieve local)", esp_dunas,
                        f"Solo el relieve local sobre el piso interdunar (ventana de {VENTANA_DUNAS_M} m): la arena de las dunas, "
                        "sin los cerros de roca que el manto tapiza. Subestima si la arena también rellena el piso."),
        "manto": metodo(f"Manto (área × {pot:g} m)", esp_manto,
                        f"Área × potencia supuesta de {pot:g} m (cámbiala con tu dato de campo). La cifra más conservadora "
                        "para mantos y capas extensas."),
    }
    return {
        "metodos": metodos, "recomendado": recomendado,
        "por_que": ("zona chica (≤ 300 ha): se mide sobre su base" if recomendado == "cerro"
                    else "zona grande de arena: se mide solo el relieve de las dunas" if recomendado == "dunas"
                    else "zona grande de roca: área × potencia"),
        "densidad_t_m3": dens, "potencia_max_m": potencia_max, "potencia_manto_m": pot,
        "cota_min_m": round(float(np.nanmin(z[dentro]))), "cota_max_m": round(float(np.nanmax(z[dentro]))),
        "dem": "Copernicus DEM GLO-30 (30 m, ESA) · AWS Open Data",
        "nota": ("Estimación de orden de magnitud con un DEM de 30 m (error vertical de unos ±4 m). No sabe qué hay bajo "
                 "la superficie ni dónde termina el material: confirmar con topografía, calicatas o sondajes."),
    }