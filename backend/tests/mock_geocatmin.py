"""Servidor ArcGIS REST simulado (solo para pruebas locales)."""
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from shapely.geometry import Point, Polygon, box, shape
from shapely.geometry.polygon import orient


def esri(g):
    if g.geom_type == "Point":
        return {"x": g.x, "y": g.y}
    g = orient(g, sign=-1.0)
    return {"rings": [list(map(list, g.exterior.coords))] + [list(map(list, h.coords)) for h in g.interiors]}


F = lambda n: {"name": n, "type": "esriFieldTypeString"}  # noqa: E731
CAPAS = {
    "SERV_GEOLOGIA_50K_INTEGRADA": {7: [
        ({"UNIDAD": "Ki-ma", "LITOLOGIA": "Areniscas cuarzosas blancas", "DESCRIP": "Formación Marcavilca"}, box(-76.50, -12.98, -76.44, -12.93)),
        ({"UNIDAD": "Ki-he", "LITOLOGIA": "Lutitas con niveles de cuarcitas", "DESCRIP": "Formación Herradura"}, box(-76.44, -12.98, -76.42, -12.93)),
        ({"UNIDAD": "KsP-gd", "LITOLOGIA": "Granodiorita con cuarzo", "DESCRIP": "Superunidad Tiabaya"}, box(-76.42, -12.98, -76.38, -12.93)),
        ({"UNIDAD": "Q-e", "LITOLOGIA": "Arenas eólicas", "DESCRIP": "Depósito eólico"}, box(-76.50, -12.93, -76.45, -12.90)),
        # 50K vs 100K (zona −75.11…−74.98): la 50K no dice «cuarzosa»; la 100K sí (ver CAPAS 100K)
        ({"UNIDAD": "Depósito eólico", "LITOLOGIA": "Arenas eólicas", "LITO1": "Arena", "DESCRIP": "Arenas eólicas que forman dunas"},
         box(-75.10, -15.10, -75.05, -15.05)),
        ({"UNIDAD": "Depósito marino", "LITOLOGIA": "Arenas y limos", "LITO1": "Arena", "DESCRIP": "Depósito marino"},
         box(-75.05, -15.10, -75.02, -15.05)),
        ({"UNIDAD": "Superunidad de prueba", "LITOLOGIA": "Granito", "LITO1": "Granito", "DESCRIP": "Granito rosado"},
         box(-75.02, -15.10, -74.99, -15.05)),
    ]},
    "SERV_GEOLOGIA_100K_INTEGRADA": {6: [
        ({"UNIDAD": "Ki-chim", "DESCRIP": "Cuarcitas blancas", "NAME": "Formación Chimú"}, box(-78.6, -8.0, -78.4, -7.8)),
        ({"UNIDAD": "Ki-ma", "DESCRIP": "Areniscas", "NAME": "Fm Marcavilca"}, box(-76.51, -12.99, -76.37, -12.89)),
        ({"UNIDAD": "Q-eo", "DESCRIP": "Depósitos eólicos de arenas cuarzosas de color blanco", "NAME": "Q-eo"},
         box(-75.10, -15.10, -74.99, -15.05)),
    ]},
    "SERV_ROCAS_MINERALES_INDUSTRIALES": {
        # mismo formato que GEOCATMIN real (muestra RMI con análisis en HTML)
        9: [({"A_ITS": "Quilmaná", "COD_UNICO": "LI4N001", "CD_MTRA": "26j-RNM-001",
              "UBI_GEOGRAFICA": "Lima / Cañete / Quilmaná", "HOJA": "26-j", "SUST_COM": "Arena Silícea",
              "NOM_PROYECTO": "GE34 (2014): Estudio de Rocas y Minerales Industriales en la Región Lima",
              "URL_BOLETIN": "https://repositorio.ingemmet.gob.pe/handle/20.500.12544/0",
              "ESTUDIO_LAB": '<a href = "https://geocatminapp.ingemmet.gob.pe/estudio.xlsx"> Estudio Químico</a><br>',
              "ANA_LABORATORIO": "<strong>Analisis Mineralógico-DRX</strong>cz 91.5 %<br>ab 3 %<br><br>"
                                 "<strong> Roca Total</strong>Al2O3 0.5 %<br>Fe2O3 0.1 %<br>SiO2 96.69 %<br>LOI 0.4 %<br><br>"},
             Point(-76.47, -12.95))],
        # GEOCATMIN real NO devuelve la geometría de esta capa: solo ESTE/NORTE/ZONA (UTM 18S)
        43: [({"A_ITS": "Pan de Azúcar", "SUST_COM": "Sílice", "ANA_LABORATORIO": None,
               "ESTE": 475393.0, "NORTE": 8866602.0, "ZONA": 18, "_sin_geometria": True}, Point(-75.2247, -10.2530))],
    },
}
# Áreas restringidas: un parque nacional (ANP de uso INDIRECTO → no concesionable) que tapa
# la mitad oeste del afloramiento «Marcavilca» de prueba, y una zona de amortiguamiento.
CAPAS["SERV_AREA_RESERVADA"] = {
    10: [({"NOMBRE": "PARQUE DE PRUEBA", "CATEGORI": "PARQUE NACIONAL", "CLASE": "ANP", "USO": "INDIRECTO",
           "NORMA": "DS 000-0000", "HAS": 1000.0}, box(-76.52, -13.00, -76.47, -12.88))],
    11: [({"NOMBRE": "AMORTIGUAMIENTO DE PRUEBA", "CATEGORI": "ZONA DE AMORTIGUAMIENTO", "CLASE": "ZA", "USO": " ",
           "NORMA": "RJ 000", "HAS": 500.0}, box(-76.40, -13.00, -76.36, -12.88))],
}
# Catastro minero: una concesión al este del parque (tapa la parte baja del resto de Marcavilca)
CAPAS["SERV_CATASTRO_MINERO_WGS84"] = {
    0: [({"CODIGOU": "010000123", "CONCESION": "CANTERA DE PRUEBA", "TIT_CONCES": "MINERA PRUEBA S.A.C.",
          "LEYENDA": "TITULADO", "SUSTANCIA": "N", "HECTAGIS": 2000.0, "FEC_DENU": 1577836800000,
          "FECHA_ACTUALIZACION": 1795046400000}, box(-76.47, -13.00, -76.44, -12.94)),
        # extinguido (por liberarse) en la esquina NE libre: 0,02 × 0,04 de la cuadrícula 0,16 × 0,12 ≈ 4,2 %
        ({"CODIGOU": "010000999", "CONCESION": "EXTINTA DE PRUEBA", "TIT_CONCES": "EX TITULAR",
          "LEYENDA": "EXTINGUIDO", "D_ESTADO": "D.M. Exting. a publicar de L.D.", "SUSTANCIA": "N", "HECTAGIS": 800.0,
          "RESOL_EXTI": "000001-2026-INGEMMET/PE", "FECHA_RESOL_EXTI": 1780000000000},
         box(-76.44, -12.92, -76.42, -12.88))],
    1: [],
}
# Libre denunciabilidad: el derecho extinguido de prueba ya figura como publicado
CAPAS["SERV_LIBREDENUNCIABILIDAD"] = {0: [({"CODIGOU": "010000999", "CONCESION": "EXTINTA DE PRUEBA"}, box(-76.44, -12.92, -76.42, -12.88))]}
# Lo que se cruza con cada concesión: un minero REINFO declarado en ella, un pasivo ambiental
# con su código y una certificación ambiental (punto dentro de la concesión)
CAPAS["SERV_REINFO"] = {0: [({"NOMBRE_MIN": "MINERO DE PRUEBA", "ID_UNIDAD": "010000123", "NOMBRE_DM": "CANTERA DE PRUEBA",
                              "TIPO_ACT": "EXPLOTACION", "ORIGEN": "RS"}, Point(-76.455, -12.97))]}
CAPAS["SERV_UEAs"] = {0: [], 1: []}
CAPAS["SERV_PASIVO_AMBIENTAL"] = {0: [({"CODIGODM": "010000123; 010999999", "NOMBREDM": "CANTERA DE PRUEBA", "TIPO": "LABOR MINERA",
                                        "SUBTIPO": "TAJO"}, Point(-76.46, -12.99))]}
CAPAS["SERV_CERTIFICADO_AMBIENTAL"] = {0: [], 1: [], 2: [({"NOMBRE": "MINERA PRUEBA S.A.C.", "PROYECTO": "CANTERA DE ARENA",
    "TIPO_CERTIFICACION": "EIA", "RD_NUMERO": "001-2020", "RD_FECHA": 1577836800000, "TC_ESTCER": "Explotación",
    "LINK": " "}, Point(-76.45, -12.98))]}
# Catastro forestal: fuera de la zona de pruebas (no cambia los % de las otras pruebas)
CAPAS["SERV_CATASTRO_FORESTAL"] = {0: [({"NOMTIT": "FORESTAL DE PRUEBA S.A.C.", "CONTRA": "17-TAH/C-J-000-00",
                                         "TP_CONCE": "CONSERVACIÓN", "ESTCON_DES": "VIGENTE", "SUPSIG": 1000.0},
                                        box(-75.30, -10.30, -75.20, -10.20))]}
# Contorno del Perú (toda la zona de pruebas es tierra)
CAPAS["SERV_CARTOGRAFIA_BASE_WGS84"] = {23: [({"NOMBRE": "PERU"}, box(-82.0, -18.5, -68.0, 0.0))]}
NOMBRES = {9: "Arena Silícea", 43: "Sílice", 22: "Dolomia"}


def where_ok(w, a):
    return w.strip() in ("", "1=1")


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def out(self, o):
        b = json.dumps(o).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b)

    def png(self, im):
        from io import BytesIO
        b = BytesIO()
        im.save(b, "PNG")
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.end_headers()
        self.wfile.write(b.getvalue())

    def route(self, q):
        p = urlparse(self.path).path.strip("/").split("/")
        # arcgis/rest/services/<svc>/MapServer[/<id>/query]
        svc = p[3]
        if svc == "Cobertura":   # cobertura del suelo: clase 5 (cultivos) entre −76.44 y −76.42, 8 (suelo desnudo) el resto
            if len(p) == 5:
                return self.out({"timeInfo": {"timeExtent": [1704067200000, 1735689599000]}})
            from math import atan, exp, pi
            import numpy as np
            from PIL import Image
            x0, y0, x1, y1 = map(float, q["bbox"].split(","))
            w, h = map(int, q["size"].split(","))
            lon = (x0 + (np.arange(w) + 0.5) * (x1 - x0) / w) * 180 / (pi * 6378137.0)
            fila = np.where((lon > -76.44) & (lon < -76.42), 5, 8).astype(np.uint8)
            return self.png(Image.fromarray(np.tile(fila, (h, 1)), "L"))
        if len(p) >= 6 and p[5] == "export":   # exports de mapa: transparentes (sin vías, ríos ni poblados)
            from PIL import Image
            w, h = map(int, q["size"].split(","))
            return self.png(Image.new("RGBA", (w, h), (0, 0, 0, 0)))
        if len(p) == 5:
            return self.out({"layers": [{"id": i, "name": NOMBRES.get(i, f"capa{i}")} for i in CAPAS[svc]]})
        lid = int(p[5])
        feats = [dict(a, OBJECTID=i + 1, _g=g) for i, (a, g) in enumerate(CAPAS[svc].get(lid, []))]
        if q.get("objectIds"):
            ids = set(map(int, q["objectIds"].split(",")))
            feats = [f for f in feats if f["OBJECTID"] in ids]
        else:
            g = q.get("geometry")
            if g:
                d = json.loads(g)
                sg = Polygon(d["rings"][0])
                feats = [f for f in feats if sg.intersects(f["_g"])]
        if q.get("returnIdsOnly") == "true":
            return self.out({"objectIds": [f["OBJECTID"] for f in feats]})
        return self.out({"features": [{"attributes": {k: v for k, v in f.items() if not k.startswith("_")},
                                       "geometry": None if f.get("_sin_geometria") else esri(f["_g"])}
                                      for f in feats]})

    def do_GET(self):
        self.route({k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        self.route({k: v[0] for k, v in parse_qs(self.rfile.read(n).decode()).items()})


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
