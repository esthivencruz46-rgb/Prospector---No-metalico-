"""Lámina PNG del mapa geológico de INGEMMET (1:50 000 o 1:100 000) de una
cuadrícula, lista para guardar en una carpeta o imprimir:

  título · mapa en UTM (sombreado de relieve + geología + áreas restringidas +
  borde de la cuadrícula) · escala gráfica · norte · coordenadas ·
  leyenda de las unidades PRESENTES en la cuadrícula (colores oficiales de
  INGEMMET, ordenadas por área) · áreas protegidas/restringidas · fuente.

Colores: los mismos del servicio (renderer uniqueValue): 1:50 000 por CODI
(3 261 valores), 1:100 000 por NAME (1 340 valores).
"""

from __future__ import annotations

import os
import textwrap

import numpy as np
from datetime import date
from io import BytesIO

import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFont
from pyproj import Transformer
from shapely.geometry import box

import geocatmin_rmi as g
import restricciones as restr

CONFIG = {
    "50K": {"servicio": "SERV_GEOLOGIA_50K_INTEGRADA", "capa": 7, "color": "CODI",
            "campos": "CODI,ETIQUETA,UNIDAD,LITOLOGIA", "nombre": "1:50 000"},
    "100K": {"servicio": "SERV_GEOLOGIA_100K_INTEGRADA", "capa": 6, "color": "NAME",
             "campos": "NAME,UNIDAD,DESCRIP", "nombre": "1:100 000"},
}
_SOMBRA = "https://server.arcgisonline.com/ArcGIS/rest/services/Elevation/World_Hillshade/MapServer/export"
_COLORES: dict[str, dict[str, tuple]] = {}
ANCHO_MAPA = 1400


def colores(escala: str) -> dict[str, tuple]:
    """valor del campo de color → (r, g, b), del renderer oficial (en caché)."""
    if escala not in _COLORES:
        cfg = CONFIG[escala]
        d = g._get(f"{g.BASE}/{cfg['servicio']}/MapServer/{cfg['capa']}", {"f": "json"})
        vals = ((d.get("drawingInfo") or {}).get("renderer") or {}).get("uniqueValueInfos") or []
        _COLORES[escala] = {str(v.get("value")).strip(): tuple((v.get("symbol") or {}).get("color", [200, 200, 200])[:3])
                            for v in vals}
    return _COLORES[escala]


_FUENTES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")


def _fuente(tam: int, negrita: bool = False):
    """DejaVu Sans (incluida en backend/fonts, licencia libre): la fuente interna de Pillow
    no trae tildes ni ñ (salían como cuadros)."""
    for nombre in (("DejaVuSans-Bold.ttf",) if negrita else ()) + ("DejaVuSans.ttf",):
        try:
            return ImageFont.truetype(os.path.join(_FUENTES, nombre), tam)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=tam)
    except TypeError:  # Pillow sin FreeType
        return ImageFont.load_default()


def _exportar(url: str, bbox: tuple, epsg: int, tam: tuple[int, int], sesion=None, **extra) -> Image.Image | None:
    try:
        r = (sesion or g._SES).get(url, params={
            "bbox": ",".join(f"{v:.2f}" for v in bbox), "bboxSR": epsg, "imageSR": epsg,
            "size": f"{tam[0]},{tam[1]}", "format": "png32", "transparent": "true", "dpi": 96, "f": "image", **extra,
        }, timeout=60)
        r.raise_for_status()
        if not r.headers.get("Content-Type", "").startswith("image"):
            return None
        return Image.open(BytesIO(r.content)).convert("RGBA").resize(tam)
    except Exception:  # noqa: BLE001
        return None


def _opacidad(img: Image.Image, factor: float) -> Image.Image:
    a = img.getchannel("A").point(lambda v: int(v * factor))
    img = img.copy()
    img.putalpha(a)
    return img


def gms(v: float, lat: bool) -> str:
    a = abs(v)
    gr = int(a)
    mi = int((a - gr) * 60)
    se = round(((a - gr) * 60 - mi) * 60)
    if se == 60:
        se, mi = 0, mi + 1
    if mi == 60:
        mi, gr = 0, gr + 1
    return f"{gr}°{mi:02d}'{se:02d}\" {('S' if v < 0 else 'N') if lat else ('O' if v < 0 else 'E')}"


def generar(sur: float, oeste: float, norte: float, este: float, escala: str = "50K", titulo: str = "") -> bytes:
    cfg = CONFIG[escala]
    zona = int((((oeste + este) / 2) + 180) // 6) + 1
    epsg = 32700 + zona                      # UTM sur (Perú: 17–19)
    a_utm = Transformer.from_crs(4326, epsg, always_xy=True)

    # contorno de la cuadrícula en UTM (con puntos intermedios: en UTM no es un rectángulo exacto)
    paso = 12
    borde_geo = ([(oeste + (este - oeste) * i / paso, sur) for i in range(paso)]
                 + [(este, sur + (norte - sur) * i / paso) for i in range(paso)]
                 + [(este - (este - oeste) * i / paso, norte) for i in range(paso)]
                 + [(oeste, norte - (norte - sur) * i / paso) for i in range(paso)])
    borde = [a_utm.transform(x, y) for x, y in borde_geo]
    xs, ys = [p[0] for p in borde], [p[1] for p in borde]
    m = 0.06 * max(max(xs) - min(xs), max(ys) - min(ys))
    X0, X1, Y0, Y1 = min(xs) - m, max(xs) + m, min(ys) - m, max(ys) + m
    W = ANCHO_MAPA
    H = round(W * (Y1 - Y0) / (X1 - X0))
    bbox = (X0, Y0, X1, Y1)

    # --- imagen del mapa: relieve + geología + áreas restringidas
    mapa = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    sombra = _exportar(_SOMBRA, bbox, epsg, (W, H), sesion=requests)
    if sombra is not None:
        mapa = Image.alpha_composite(mapa, _opacidad(sombra, 0.45))
    geo = _exportar(f"{g.BASE}/{cfg['servicio']}/MapServer/export", bbox, epsg, (W, H), layers=f"show:{cfg['capa']}")
    if geo is None:
        raise RuntimeError("GEOCATMIN no entregó la imagen de la geología.")
    mapa = Image.alpha_composite(mapa, _opacidad(geo, 0.85))
    restringidas = _exportar(f"{g.BASE}/{restr.SERVICIO}/MapServer/export", bbox, epsg, (W, H),
                             layers="show:" + ",".join(map(str, restr.CAPAS_MAPA)))
    if restringidas is not None:
        # INGEMMET usa colores muy claros: se oscurecen (más saturación, menos brillo) para que se vean
        alfa = restringidas.getchannel("A")
        rgb = ImageEnhance.Brightness(ImageEnhance.Color(restringidas.convert("RGB")).enhance(2.4)).enhance(0.62)
        restringidas = rgb.convert("RGBA")
        restringidas.putalpha(alfa)
        mapa = Image.alpha_composite(mapa, _opacidad(restringidas, 0.75))

    # --- unidades presentes en la cuadrícula (para la leyenda), por área
    pol = box(oeste, sur, este, norte)
    feats = g.query_en_poligono(cfg["servicio"], cfg["capa"], g._anillo_esri(pol), cfg["campos"],
                                timeout=g.GEOLOGIA[escala]["timeout"])
    tabla_color = colores(escala)
    unidades: dict[str, dict] = {}
    piezas: list = []          # (polígono completo, parte en la cuadrícula, etiqueta) para contactos y rótulos
    for f in feats:
        a = f.get("attributes") or {}
        geom = g.esri_a_shapely(f.get("geometry"))
        if geom is None:
            continue
        inter = geom.intersection(pol)
        if inter.is_empty:
            continue
        clave = str(a.get(cfg["color"]) or "").strip()
        piezas.append((geom, inter, str(a.get("ETIQUETA") or a.get("NAME") or "").strip()))
        if clave not in unidades or g.area_ha(inter) > unidades[clave].get("_mayor_ha", 0):
            mayor = (inter, g.area_ha(inter))
        else:
            mayor = None
        u = unidades.setdefault(clave, {
            "color": tabla_color.get(clave, (200, 200, 200)),
            "etiqueta": str(a.get("ETIQUETA") or a.get("NAME") or "").strip(),
            "nombre": str(a.get("UNIDAD") or "").strip() if escala == "50K" else "",
            "lito": str(a.get("LITOLOGIA") or a.get("DESCRIP") or "").strip(),
            "ha": 0.0,
        })
        u["ha"] += g.area_ha(inter)
        if mayor:
            u["_mayor"], u["_mayor_ha"] = mayor
    # COLOR DE LA LEYENDA = el que GEOCATMIN DIBUJÓ (24/11/2026): el renderer del servicio no trae todas las unidades
    # (p. ej. Chimú 2486, Santa 2512, Pariatambo 2507) y la leyenda salía gris mientras el mapa las pinta de otro color.
    # Se toma la mediana de los píxeles opacos de la imagen de geología alrededor de un punto interior del polígono.
    ga = np.asarray(geo.convert("RGBA"))
    for u in unidades.values():
        if "_mayor" not in u:
            continue
        pt = u.pop("_mayor").representative_point()
        u.pop("_mayor_ha", None)
        x, y = a_utm.transform(pt.x, pt.y)
        cx, cy = int((x - X0) / (X1 - X0) * W), int((Y1 - y) / (Y1 - Y0) * H)
        ven = ga[max(0, cy - 7):cy + 8, max(0, cx - 7):cx + 8].reshape(-1, 4)
        ven = ven[ven[:, 3] > 200]
        if len(ven) >= 10:
            u["color"] = tuple(int(v) for v in np.median(ven[:, :3], axis=0))
    leyenda = sorted(unidades.values(), key=lambda u: -u["ha"])
    try:
        areas = restr.publicas(restr.consultar(pol))
    except Exception:  # noqa: BLE001
        areas = []

    # --- lámina
    MI, MS, GAP, LW, MB = 80, 130, 36, 620, 150
    CW = MI + W + GAP + LW + 30
    CH = max(MS + H + MB, MS + 1100)
    lam = Image.new("RGB", (CW, CH), (255, 255, 255))
    lam.paste(mapa.convert("RGB"), (MI, MS))
    d = ImageDraw.Draw(lam)
    negro, gris, rojo = (17, 24, 39), (100, 116, 139), (220, 38, 38)
    f_tit, f_sub, f_txt, f_peq, f_mini = _fuente(32, True), _fuente(18), _fuente(16), _fuente(13), _fuente(12)
    f_sub_n = _fuente(18, True)

    def a_px(x, y):
        return MI + (x - X0) / (X1 - X0) * W, MS + (Y1 - y) / (Y1 - Y0) * H

    # CONTACTOS GEOLÓGICOS y RÓTULOS de unidad (24/11/2026): INGEMMET pinta varias formaciones casi del mismo verde
    # (Farrat, Chimú, Carhuaz, Santa…); sin límites ni símbolos el mapa no se lee. Contactos en gris oscuro fino y el
    # símbolo de la unidad (ETIQUETA) en cada polígono de ≥ 12 ha, con halo blanco y sin solaparse.
    caja_mapa = box(*a_utm.transform(X0, Y0, direction="INVERSE"), *a_utm.transform(X1, Y1, direction="INVERSE"))
    mapa_d = ImageDraw.Draw(lam)
    for geom, _, _ in piezas:
        gg = geom.intersection(caja_mapa)
        for poli in getattr(gg, "geoms", [gg]):
            for anillo in [getattr(poli, "exterior", None), *getattr(poli, "interiors", [])]:
                if anillo is None or anillo.is_empty:
                    continue
                pts = [a_px(*a_utm.transform(x, y)) for x, y in anillo.coords]
                if len(pts) > 1:
                    mapa_d.line(pts, fill=(55, 65, 81), width=1)
    f_rot = _fuente(15, True)
    ocupado: list = []
    for _, inter, etq in sorted(piezas, key=lambda t: -g.area_ha(t[1])):
        if not etq:
            continue
        for parte in getattr(inter, "geoms", [inter]):
            if parte.is_empty or g.area_ha(parte) < 12:
                continue
            pt = parte.representative_point()
            x, y = a_px(*a_utm.transform(pt.x, pt.y))
            bb = mapa_d.textbbox((x, y), etq, font=f_rot, anchor="mm")
            bb = (bb[0] - 4, bb[1] - 3, bb[2] + 4, bb[3] + 3)
            if any(not (bb[2] < o[0] or bb[0] > o[2] or bb[3] < o[1] or bb[1] > o[3]) for o in ocupado):
                continue
            ocupado.append(bb)
            mapa_d.text((x, y), etq, font=f_rot, fill=(17, 24, 39), anchor="mm", stroke_width=3, stroke_fill=(255, 255, 255))

    # lo que los contactos dibujaron fuera del marco se borra (el recuadro geográfico no coincide exacto con el UTM)
    blanco = (255, 255, 255)
    for r_ in ([0, 0, CW, MS - 1], [0, MS + H + 1, MI + W + GAP - 2, CH], [0, 0, MI - 1, CH], [MI + W + 1, 0, MI + W + GAP - 2, CH]):
        mapa_d.rectangle(r_, fill=blanco)

    # borde de la cuadrícula y marco del mapa
    d.line([a_px(*p) for p in borde] + [a_px(*borde[0])], fill=rojo, width=4)
    d.rectangle([MI, MS, MI + W, MS + H], outline=negro, width=2)

    # coordenadas de las esquinas de la cuadrícula: FUERA del marco (no tapan el mapa)
    d.text((MI, MS - 6), f"↖ NO: {gms(norte, True)} · {gms(oeste, False)}", fill=negro, font=f_mini, anchor="ld")
    d.text((MI + W, MS - 6), f"NE: {gms(norte, True)} · {gms(este, False)} ↗", fill=negro, font=f_mini, anchor="rd")
    d.text((MI, MS + H + 8), f"↙ SO: {gms(sur, True)} · {gms(oeste, False)}", fill=negro, font=f_mini, anchor="la")
    d.text((MI + W, MS + H + 8), f"SE: {gms(sur, True)} · {gms(este, False)} ↘", fill=negro, font=f_mini, anchor="ra")

    # norte, sobre un círculo blanco
    nx, ny = MI + W - 50, MS + 22
    d.ellipse([nx - 30, ny - 8, nx + 30, ny + 78], fill=(255, 255, 255), outline=gris)
    d.polygon([(nx, ny), (nx - 14, ny + 40), (nx, ny + 30), (nx + 14, ny + 40)], fill=negro)
    d.text((nx, ny + 46), "N", fill=negro, font=f_sub_n, anchor="mt")

    # escala gráfica (≈ 20 % del ancho, en km redondos), sobre un recuadro blanco
    km_px = W / ((X1 - X0) / 1000)
    largo_km = next(k for k in (1, 2, 5, 10, 20, 50) if k * km_px >= W * 0.18)
    seg = largo_km * km_px / 4
    ex, ey = MI + 24, MS + H - 46
    d.rectangle([ex - 14, ey - 34, ex + 4 * seg + 70, ey + 38], fill=(255, 255, 255), outline=gris)
    for i in range(4):
        d.rectangle([ex + i * seg, ey, ex + (i + 1) * seg, ey + 10], fill=negro if i % 2 == 0 else (255, 255, 255), outline=negro)
    for i in range(5):
        d.text((ex + i * seg, ey + 14), f"{largo_km * i / 4:g}", fill=negro, font=f_mini, anchor="mt")
    d.text((ex + 4 * seg + 12, ey + 14), "km", fill=negro, font=f_mini, anchor="lt")
    escala_num = round((X1 - X0) / (W / 96 * 0.0254) / 1000) * 1000
    d.text((ex, ey - 26), f"1:{escala_num:,} aprox. (a 96 ppp) · WGS84 / UTM {zona}S".replace(",", " "), fill=negro, font=f_mini)

    # título
    d.text((MI, 26), f"Mapa geológico {cfg['nombre']}" + (f" · Cuadrícula {titulo}" if titulo else ""), fill=negro, font=f_tit)
    d.text((MI, 74), f"{gms(norte, True)} – {gms(sur, True)}  ·  {gms(oeste, False)} – {gms(este, False)}  ·  "
                     f"Geología integrada de INGEMMET (GEOCATMIN)", fill=gris, font=f_sub)

    # leyenda
    lx, ly = MI + W + GAP, MS
    limite = CH - MB - 40
    d.text((lx, ly), "Leyenda · unidades en la cuadrícula", fill=negro, font=f_sub_n)
    d.text((lx, ly + 26), "(colores y símbolos de INGEMMET, de mayor a menor área; líneas = contactos)", fill=gris, font=f_peq)
    ly += 60
    mostradas = 0
    for u in leyenda:
        lineas = textwrap.wrap(u["lito"], 62)[:2]
        alto = 26 + 18 * len(lineas) + 10
        if ly + alto > limite - 160:
            break
        d.rectangle([lx, ly + 2, lx + 44, ly + 26], fill=u["color"], outline=gris)
        cab = " · ".join(x for x in (u["etiqueta"], u["nombre"]) if x)[:60] or "(sin nombre)"
        d.text((lx + 56, ly + 2), cab, fill=negro, font=f_txt)
        d.text((lx + LW - 10, ly + 4), f"{u['ha']:,.0f} ha".replace(",", " "), fill=gris, font=f_peq, anchor="ra")
        for i, l in enumerate(lineas):
            d.text((lx + 56, ly + 26 + 18 * i), l, fill=gris, font=f_peq)
        ly += alto
        mostradas += 1
    if mostradas < len(leyenda):
        d.text((lx, ly), f"… y {len(leyenda) - mostradas} unidades más (menores): ver GEOCATMIN.", fill=gris, font=f_peq)
        ly += 26

    # símbolos y áreas restringidas
    ly += 14
    d.line([(lx, ly + 12), (lx + 44, ly + 12)], fill=rojo, width=4)
    d.text((lx + 56, ly + 2), "Cuadrícula 1:25 000 analizada", fill=negro, font=f_txt)
    ly += 40
    d.text((lx, ly), "Áreas protegidas / restringidas (INGEMMET)", fill=negro, font=f_sub_n)
    ly += 30
    if not areas:
        d.text((lx, ly), "Ninguna dentro de la cuadrícula.", fill=(22, 128, 61), font=f_txt)
    # las grandes de a una; las diminutas (p. ej. decenas de sitios arqueológicos) agrupadas por tipo
    grandes = [a for a in areas if a["pct_cuadricula"] >= 1]
    chicas = [a for a in areas if a["pct_cuadricula"] < 1]
    for a in grandes[:5]:
        etiqueta = "NO CONCESIONABLE" if a["nivel"] == "prohibido" else "RESTRINGIDO"
        col = rojo if a["nivel"] == "prohibido" else (180, 83, 9)
        lineas = textwrap.wrap(f"[{etiqueta}] {a['tipo']}: {a['nombre']}", 66)[:3]
        for i, l in enumerate(lineas):
            d.text((lx, ly + 18 * i), l, fill=col, font=f_peq)
        ly += 18 * len(lineas)
        d.text((lx, ly), f"{a['categoria']} · {a['pct_cuadricula']} % de la cuadrícula"[:80], fill=gris, font=f_mini)
        ly += 24
    por_tipo: dict[tuple, list] = {}
    for a in chicas:
        por_tipo.setdefault((a["tipo"], a["nivel"]), []).append(a)
    for (tipo, nivel), lista in por_tipo.items():
        etiqueta = "NO CONCESIONABLE" if nivel == "prohibido" else "RESTRINGIDO"
        col = rojo if nivel == "prohibido" else (180, 83, 9)
        suma = sum(a["pct_cuadricula"] for a in lista)
        lineas = textwrap.wrap(f"[{etiqueta}] {len(lista)} × {tipo} (pequeñas, {suma:.1f} % en total)", 66)[:2]
        for i, l in enumerate(lineas):
            d.text((lx, ly + 18 * i), l, fill=col, font=f_peq)
        ly += 18 * len(lineas)
        nombres = ", ".join(sorted({a["nombre"] for a in lista}))
        nl = textwrap.wrap(nombres, 80)[:2]
        for i, l in enumerate(nl):
            d.text((lx, ly + 15 * i), l, fill=gris, font=f_mini)
        ly += 15 * len(nl) + 14

    # fuente
    d.text((MI, CH - 70), "Fuente: GEOCATMIN – INGEMMET (geología integrada; áreas restringidas). Relieve: Esri World Hillshade. "
                          "Información referencial: verificar en campo.", fill=gris, font=f_peq)
    d.text((MI, CH - 44), f"Generado por Prospector RMI el {date.today():%d/%m/%Y}.", fill=gris, font=f_peq)

    buf = BytesIO()
    lam.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
