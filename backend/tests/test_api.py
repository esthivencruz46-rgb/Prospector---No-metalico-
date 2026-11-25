"""Pruebas sin internet: GEOCATMIN simulado + Sentinel con bandas sintéticas.
Ejecutar desde backend/:  python -m pytest -q
"""
import os
import socket
import subprocess
import sys
import time

import numpy as np
import pytest

PUERTO = 8799
os.environ["GEOCATMIN_BASE"] = f"http://127.0.0.1:{PUERTO}/arcgis/rest/services"
# cobertura del suelo simulada (ver mock_geocatmin: cultivos en una franja de la zona de pruebas)
os.environ["COBERTURA_URL"] = f"http://127.0.0.1:{PUERTO}/arcgis/rest/services/Cobertura/ImageServer"
os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
os.environ.setdefault("no_proxy", "127.0.0.1,localhost")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

import sentinel_silice  # noqa: E402
from main import app  # noqa: E402
from materiales import clasificar  # noqa: E402

AREA = [[-76.52, -13.00], [-76.36, -13.00], [-76.36, -12.88], [-76.52, -12.88]]


@pytest.fixture(scope="module", autouse=True)
def servidor():
    p = subprocess.Popen([sys.executable, os.path.join(os.path.dirname(__file__), "mock_geocatmin.py"), str(PUERTO)])
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", PUERTO), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    yield
    p.terminate()


def test_clasificacion():
    # clases del usuario: A = depósitos de arena silícea/cuarzosa · B = rocas (arenisca cuarzosa/cuarcítica, cuarcita) y formaciones
    assert clasificar("arena_silicea", {"LITOLOGIA": "Cuarcitas grises"})[0] == "B"
    assert clasificar("arena_silicea", {"LITOLOGIA": "Areniscas cuarzosas blancas"})[0] == "B"
    assert clasificar("arena_silicea", {"UNIDAD": "Formación Chimú", "LITOLOGIA": "Cuarcitas, lutitas, carbón"})[0] == "B"
    assert clasificar("arena_silicea", {"UNIDAD": "Formación Chimú", "LITOLOGIA": "Areniscas y lutitas"})[0] == "B"
    # formación cuarzosa, pero el polígono solo dice lutitas → C (antes B)
    assert clasificar("arena_silicea", {"UNIDAD": "Formación Chimú", "LITOLOGIA": "Lutitas"})[0] == "C"
    assert clasificar("arena_silicea", {"LITOLOGIA": "Areniscas y lutitas"})[0] == "C"
    assert clasificar("arena_silicea", {"LITOLOGIA": "Granodiorita con cuarzo"}) is None
    assert clasificar("arena_silicea", {"LITOLOGIA": "Areniscas tobáceas"}) is None
    assert clasificar("arena_silicea", {"LITOLOGIA": "Calizas micríticas"}) is None
    # regla del usuario (23/11/2026): decide la descripción completa; la cuarcita cuenta aunque no sea la principal
    assert clasificar("arena_silicea", {"LITOLOGIA": "Lutitas con niveles de cuarcitas"})[0] == "B"
    assert clasificar("arena_silicea", {"LITOLOGIA": "Cuarcitas con intercalaciones de lutitas"})[0] == "B"
    assert clasificar("dolomia", {"LITOLOGIA": "Dolomías"}) is None  # aún inactivo
    # textos reales de GEOCATMIN que antes no se reconocían
    assert clasificar("arena_silicea", {"LITOLOGIA": "Arena cuarzosa"})[0] == "A"
    assert clasificar("arena_silicea", {"DESCRIP": "Arenas cuarzosas formando dunas y pampas amplias."})[0] == "A"
    assert clasificar("arena_silicea", {"LITOLOGIA": "Arenisca cuarcítica"})[0] == "B"
    assert clasificar("arena_silicea", {"LITOLOGIA": "Arena cuarzosa, limoarena, lutita."})[0] == "A"
    # ruido que NO debe subir a A
    assert clasificar("arena_silicea", {"LITOLOGIA": "Tonalita, diorita cuarzosa"}) is None
    assert clasificar("arena_silicea", {"LITOLOGIA": "Andesita, cuarcita"})[0] == "C"
    assert clasificar("arena_silicea", {"LITOLOGIA": "Arcosa, arenisca cuarzosa"})[0] == "C"
    assert clasificar("arena_silicea", {"LITOLOGIA": "Arenisca, Arenisca cuarzo-feldespática, limolita"})[0] == "C"


def test_clasificacion_con_lito1():
    c = lambda **t: clasificar("arena_silicea", t)  # noqa: E731
    # LITO1 = roca dominante (50K)
    r = c(LITOLOGIA="Lutita, cuarcita", LITO1="Lutita", LITO2="Cuarcita")      # secundaria: cuenta (B) con nota
    assert r[0] == "B" and "roca principal: lutita" in r[1]
    assert c(LITOLOGIA="Lutita", LITO1="Lutita", LITO2="Arenisca cuarzosa")[0] == "B"   # LITO2 también se lee
    assert c(LITOLOGIA="Arenisca cuarzosa, caliza, andesita", LITO1="Arenisca cuarzosa", LITO2="Caliza")[0] == "B"
    assert c(LITOLOGIA="Andesita, cuarcita", LITO1="Andesita", LITO2="Cuarcita")[0] == "C"
    assert c(LITOLOGIA="Andesita, arenisca", LITO1="Andesita", LITO2="Arenisca") is None
    assert c(LITOLOGIA="Cuarcita", LITO1="<Null>")[0] == "B"  # LITO1 vacío → regla anterior
    # Goyllarisquizga: las partes calcáreas/lutáceas del grupo NO son B
    assert c(UNIDAD="Grupo Goyllarisquizga - Formación Santa", LITOLOGIA="Caliza, lutita", LITO1="Caliza") is None
    assert c(UNIDAD="Grupo Goyllarisquizga", LITOLOGIA="Arenisca, lutita", LITO1="Arenisca")[0] == "B"
    # Huancané volcánico ≠ Formación Huancané
    assert c(UNIDAD="Centro Volcánico Huancane - Evento 1", LITOLOGIA="Andesita", LITO1="Andesita") is None
    # depósitos eólicos de la 50K cuya descripción dice que la arena es cuarzosa (20g1-SO / 20g2) → A
    eol = dict(UNIDAD="Depósito eólico", LITOLOGIA="Arena", LITO1="Arena")
    assert c(**eol, DESCRIP="Arenas eólicas, cuarzosas de color blanco, se acumulan formando dunas")[0] == "A"
    assert c(**eol, DESCRIP="Depósitos de arenas de cuarzosas de grano fino a medio de origen eólico")[0] == "A"
    assert c(**eol, DESCRIP="Campos de dunas compuesto de arena media bien seleccionada y de composición cuarzosa.")[0] == "A"
    assert c(**eol, DESCRIP="Arenas eólicas que forman dunas")[0] == "C"     # sin decir «cuarzosa»: verificar
    # «cuarzosa» en OTRA frase o de una roca ígnea no cuenta
    assert c(**eol, DESCRIP="Arenas eólicas. Cubren a la diorita cuarzosa")[0] == "C"
    assert c(UNIDAD="Formación Huancané", LITOLOGIA="Arenisca, lutita", LITO1="Arenisca")[0] == "B"


def test_catalogo_formaciones():
    from materiales import FORMACIONES, formaciones_de
    ids = {f["id"] for f in FORMACIONES["arena_silicea"]}
    assert {"chimu", "marcavilca", "hualhuani", "eolicos", "cuarcitas"} <= ids
    assert "marcavilca" in formaciones_de("arena_silicea", {"UNIDAD": "Grupo Morro Solar - Formación Marcavilca", "LITOLOGIA": "Arenisca cuarzosa"})
    assert "goyllarisquizga" not in formaciones_de("arena_silicea", {"UNIDAD": "Grupo Goyllarisquizga - Formación Santa"})
    c = TestClient(app)
    lista = c.get("/formaciones", params={"material": "arena_silicea"}).json()
    assert lista and all("sql50" in f and "patron" not in f for f in lista)


def test_buscar_cascada_50k():
    c = TestClient(app)
    r = c.post("/buscar", json={"material": "arena_silicea", "poligono": AREA})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["escala_usada"] == "50K"
    assert d["resumen"]["rmi"] == 0 and d["rmi"] == []   # las muestras RMI ya no se consultan
    clases = [a["clase"] for a in d["afloramientos"]]
    assert clases[0] == "B" and "C" in clases  # Marcavilca = arenisca cuarzosa → B (roca)
    unidades = {a["unidad"] for a in d["afloramientos"]}
    assert "KsP-gd" not in unidades  # granodiorita excluida
    assert all(a["area_ha"] > 0 and a["geometria"]["type"] in ("Polygon", "MultiPolygon") for a in d["afloramientos"])


def test_busqueda_texto_libre():
    from materiales import filtro_texto, palabras_busqueda, variantes_tilde
    assert variantes_tilde("CHIMU") == ["CHIMU", "CHÍMU", "CHIMÚ"]
    assert palabras_busqueda("Formación de Chimú") == ["FORMACION", "CHIMU"]  # sin tildes ni "de"
    f = filtro_texto("Chimu")
    assert "LIKE '%CHIMÚ%'" in f["sql50"] and f["palabras"] == ["CHIMU"]
    # dos palabras → ambas obligatorias
    assert " AND " in filtro_texto("arena cuarzosa")["sql50"]
    # "arena silícea" no existe en los mapas de INGEMMET → todas las unidades silíceas
    s = filtro_texto("Arena  silícea")
    assert s["id"] == "texto:SILICE" and "CUARCIT" in s["sql50"] and s["nota"]
    assert filtro_texto("de y") is None
    # sin comillas inyectables en el SQL
    assert "'" not in filtro_texto("chimú' OR 1=1 --")["palabras"][0]
    c = TestClient(app)
    assert c.get("/geologia/filtro", params={"texto": "cuarcita"}).json()["nombre"] == "«cuarcita»"
    assert c.get("/geologia/filtro", params={"texto": "x"}).status_code == 422


def test_areas_protegidas_y_restringidas():
    c = TestClient(app)
    d = c.post("/buscar", json={"material": "arena_silicea", "poligono": AREA}).json()
    r = {a["nombre"]: a for a in d["restricciones"]}
    # ANP de uso indirecto (parque nacional) → no concesionable; amortiguamiento → restringido
    assert r["PARQUE DE PRUEBA"]["nivel"] == "prohibido" and r["AMORTIGUAMIENTO DE PRUEBA"]["nivel"] == "restringido"
    assert 0 < r["PARQUE DE PRUEBA"]["pct_cuadricula"] < 50 and "_geom" not in r["PARQUE DE PRUEBA"]
    # el afloramiento de Marcavilca (−76.50 a −76.44) queda en parte dentro del parque (−76.52 a −76.47)
    marca = next(a for a in d["afloramientos"] if "Marcavilca" in a["descripcion"] or "Ki-ma" == a["unidad"])
    assert marca["restriccion"]["nivel"] == "prohibido" and 40 < marca["restriccion"]["pct"] < 60
    assert marca["restriccion"]["nombres"] == ["PARQUE DE PRUEBA"]
    # endpoint suelto (para «solo satélite»)
    solo = c.post("/restricciones", json={"poligono": AREA}).json()
    assert {a["nombre"] for a in solo} == {"PARQUE DE PRUEBA", "AMORTIGUAMIENTO DE PRUEBA"}
    # ANP de uso directo (reserva nacional) → restringido
    import restricciones
    assert restricciones._nivel(None, "DIRECTO") == "restringido" and restricciones._nivel(None, "INDIRECTO") == "prohibido"
    # concesiones forestales (catastro forestal de SERFOR): cuentan como restringidas
    area_for = [[-75.32, -10.32], [-75.18, -10.32], [-75.18, -10.18], [-75.32, -10.18]]
    fr = c.post("/restricciones", json={"poligono": area_for}).json()
    assert fr[0]["tipo"].startswith("Concesión forestal") and fr[0]["nivel"] == "restringido"
    assert fr[0]["nombre"] == "FORESTAL DE PRUEBA S.A.C." and 45 < fr[0]["pct_cuadricula"] < 55


def test_areas_libres():
    c = TestClient(app)
    d = c.post("/buscar", json={"material": "arena_silicea", "poligono": AREA}).json()
    lib = d["libres"]
    # cuadrícula 16 × 12 (centésimas de grado): parque 5/16, amortiguamiento 4/16, concesión 3/16 × 1/2
    assert 33 < lib["libre_pct"] < 36 and 8 < lib["concesiones_pct"] < 11 and 54 < lib["protegido_pct"] < 58
    assert lib["n_concesiones"] == 2 and "_libre" not in lib
    # el extinguido NO resta: cuenta como libre «con observación» (falta la libre denunciabilidad)
    assert 3.8 < lib["por_liberarse_pct"] < 4.6 and lib["nota_por_liberarse"]
    ext = next(k for k in lib["concesiones"] if k["nombre"] == "EXTINTA DE PRUEBA")
    assert ext["indicio_pago"]["nivel"] == "na" and any("libre denunciabilidad" in x for x in ext["alertas"])
    con = lib["concesiones"][0]
    assert con["nombre"] == "CANTERA DE PRUEBA" and con["estado"] == "titulado" and con["sustancia"] == "no metálica"
    # ficha: régimen general (sin CALIFICA) → US$ 3/ha/año; REINFO, pasivo y certificación cruzados
    assert con["calificacion"].startswith("Régimen general") and con["vigencia_usd_anual"] == 6000
    assert con["reinfo"][0]["nombre"] == "MINERO DE PRUEBA" and con["pasivos"]["n"] == 1
    assert con["certificaciones"][0]["tipo"] == "EIA" and any("REINFO" in x for x in con["alertas"])
    assert "SIDEMCAT" in con["pago"] and con["enlaces"]
    # no metálica: «CANTERA DE PRUEBA» → material probable por el nombre; está sobre Marcavilca (B)
    # → indicio alto de sílice; REINFO declara explotación + EIA de explotación → actividad alta
    assert con["material_probable"]["material"].startswith("Cantera") and con["material_probable"]["fuente"] == "nombre del derecho"
    assert con["sobre_zonas"][0]["clase"] == "B" and con["indicio_silice"]["nivel"] == "alto"
    assert con["actividad"]["nivel"] == "alta"
    from concesiones_info import material_probable
    assert material_probable([("titular", "SILICES DEL NORTE S.A.C.")])["material"].startswith("Sílice")
    assert material_probable([("nombre", "BAYOVAR 12")])["material"] == "Fosfatos"
    assert material_probable([("nombre", "VIRGEN DE LA PUERTA")]) is None
    assert lib["catastro_actualizado"] and lib["consultado"] and lib["geometria"]["type"] in ("Polygon", "MultiPolygon")
    # Marcavilca: la mitad oeste en el parque, la parte baja del resto en la concesión → ~10 % libre
    marca = next(a for a in d["afloramientos"] if a["unidad"] == "Ki-ma")
    assert 8 < marca["libre_pct"] < 12
    # utilizable: se restan los cultivos (franja −76.44 a −76.42 = 2/16 de la cuadrícula, toda libre)
    assert 20 < lib["util_pct"] < 24 and lib["no_apto"][0]["motivo"] == "cultivo" and lib["cobertura_anio"] == 2024
    assert 8 < marca["util_pct"] < 12
    # derechos mineros que tocan la zona: la concesión cubre 0,03 × 0,04 de 0,06 × 0,05 → 40 %
    assert marca["concesiones"][0]["nombre"] == "CANTERA DE PRUEBA" and 38 < marca["concesiones"][0]["pct"] < 42
    herr = next(a for a in d["afloramientos"] if a["unidad"] == "Ki-he")   # Herradura: dentro de los cultivos
    assert herr["util_pct"] is not None and herr["util_pct"] < 5 and herr["libre_pct"] > 90
    # endpoint suelto (para «solo satélite» y para refrescar análisis guardados)
    solo = c.post("/libres", json={"poligono": AREA, "zonas": [{"id": marca["id"], "geometria": marca["geometria"]}]}).json()
    assert abs(solo["libres"]["libre_pct"] - lib["libre_pct"]) < 0.01 and len(solo["restricciones"]) == 2
    z = solo["zonas"][marca["id"]]
    assert z["libre_pct"] == marca["libre_pct"] and z["restriccion"]["nivel"] == "prohibido"


def test_50k_y_100k_combinadas():
    """Regla del usuario (23/11/2026): con hoja 1:50 000 se usa SOLO la 50K; la 100K (aunque diga «arenas
    cuarzosas») ni se anota ni viaja aparte."""
    c = TestClient(app)
    area = [[-75.11, -15.11], [-74.98, -15.11], [-74.98, -15.04], [-75.11, -15.04]]
    d = c.post("/buscar", json={"material": "arena_silicea", "poligono": area}).json()
    assert d["escala_usada"] == "50K"
    eol = next(a for a in d["afloramientos"] if a["unidad"] == "Depósito eólico")
    assert eol["clase"] == "C" and "respaldo_100k" not in eol
    assert d["afloramientos_100k"] == [] and all(a["escala"] == "50K" for a in d["afloramientos"])
    assert "no se usa la 1:100 000" in d["motivo_escala"]
    # el tipo de material lo decide la roca dominante: arcilla con arenas eólicas encima NO es «arena»
    import geocatmin_rmi as gr
    assert gr.tipo_material({"LITO1": "Arcilla", "DESCRIP": "Arcillas ... colmatación con arenas eólicas"}) is None
    assert gr.tipo_material({"roca_dominante": "Arena", "descripcion": "Arenas eólicas estabilizadas"}) == "arena"
    assert gr.tipo_material({"litologia": "Arenisca, lutita"}) == "roca"


def test_sin_capas_eliminadas_y_100k_ignorada():
    """24/11/2026: ya no hay pureza, prioridad combinada ni modos 1:100 000; las zonas 100K se ignoran."""
    bbox = (-76.52, -13.0, -76.36, -12.88)
    alto, ancho = 48, 64
    b = np.zeros((alto, ancho, 7), np.float32)
    b[..., 0:4] = [3000, 3100, 3200, 600]
    b[..., 4:6] = [3500, 3600]
    b[..., 6] = 5
    caja = lambda x0, x1: {"type": "Polygon", "coordinates": [[[x0, -13.0], [x1, -13.0], [x1, -12.88], [x0, -12.88], [x0, -13.0]]]}  # noqa: E731
    anillo = [[-76.52, -13.0], [-76.36, -13.0], [-76.36, -12.88], [-76.52, -12.88], [-76.52, -13.0]]
    z50 = [{"id": "50K-001", "clase": "A", "geometria": caja(-76.52, -76.44)}]        # mitad oeste
    z100 = [{"id": "100K-001", "clase": "A", "geometria": caja(-76.52, -76.36)}]      # toda la cuadrícula
    sin_corte = {"p_ferruginosa": 2, "arcilla": 2, "p_ndvi": 2}     # imagen constante: el percentil no significa nada
    r = sentinel_silice.calcular(b, anillo, z50, bbox, (ancho, alto), afloramientos_100k=z100, cortes=sin_corte)
    viejas = {"pureza", "prioridad", "prioridad_100k", "prioridad_ambas", "pureza_zonas", "pureza_zonas_100k"}
    assert not viejas & set(r["capas"]) and "silice_limpia" in r["capas"]
    assert r["cortes"]["p_ferruginosa"] == 2 and r["datos"]["rangos"].startswith("data:image/png") and r["datos"]["formato"] == 4
    assert sentinel_silice.CORTES == {"p_ferruginosa": 0.3, "arcilla": 0.3, "p_ndvi": 0.57}
    assert set(r["datos"]["hist"]) == {"ferruginosa", "arcilla", "ndvi", "bsi"}
    c = r["celda"]
    assert not any(k.startswith("pct_prioridad") for k in c)
    assert 45 < c["pct_interes"] < 55 and c["pct_silice_limpia"] == c["pct_interes"]   # solo la 50K, sin hierro
    assert all("pureza" not in z and "combinado" not in z for z in r["afloramientos"])
    assert r["afloramientos"][0]["limpia_pct"] == 100


def test_buscar_cascada_100k_sin_cobertura_50k():
    c = TestClient(app)
    area = [[-78.62, -8.02], [-78.38, -8.02], [-78.38, -7.78], [-78.62, -7.78]]
    d = c.post("/buscar", json={"material": "arena_silicea", "poligono": area}).json()
    assert d["escala_usada"] == "100K" and not d["cobertura_50k"]
    assert d["afloramientos"][0]["clase"] == "B"   # Chimú = cuarcitas → B (roca)


def test_errores_de_area():
    c = TestClient(app)
    grande = [[-77, -13], [-75, -13], [-75, -11], [-77, -11]]
    assert c.post("/buscar", json={"poligono": grande}).status_code == 422
    fuera = [[-60, -13], [-59, -13], [-59, -12]]
    assert c.post("/buscar", json={"poligono": fuera}).status_code == 422
    assert c.post("/buscar", json={"material": "dolomia", "poligono": AREA}).status_code == 422


def test_sentinel_calculo_sintetico():
    bbox = (-76.52, -13.0, -76.36, -12.88)
    tam = (64, 48)
    alto, ancho = 48, 64
    b = np.zeros((alto, ancho, 7), np.float32)
    b[..., 0:4] = [800, 900, 1000, 600]    # suelo moderado, poca vegetación
    b[..., 4:6] = [2000, 1800]
    b[..., 6] = 5                           # SCL: suelo desnudo
    b[:, :20, 0:3] = [3000, 3100, 3200]     # franja clara y limpia
    b[:, :20, 4:6] = [3500, 3600]
    b[:, 40:, 2] = 2500                     # franja rojiza (óxidos)
    afl = [{"id": "limpio", "geometria": {"type": "Polygon", "coordinates": [[[-76.52, -13.0], [-76.475, -13.0], [-76.475, -12.88], [-76.52, -12.88], [-76.52, -13.0]]]}},
           {"id": "rojizo", "geometria": {"type": "Polygon", "coordinates": [[[-76.41, -13.0], [-76.36, -13.0], [-76.36, -12.88], [-76.41, -12.88], [-76.41, -13.0]]]}}]
    anillo = [[-76.52, -13.0], [-76.36, -13.0], [-76.36, -12.88], [-76.52, -12.88], [-76.52, -13.0]]
    r = sentinel_silice.calcular(b, anillo, afl, bbox, tam, cortes={"p_ferruginosa": 0.5, "arcilla": 0.9, "p_ndvi": 2})
    porid = {s["id"]: s for s in r["afloramientos"]}
    # la franja rojiza tiene más hierro y se excluye más que la limpia
    assert porid["rojizo"]["oxidos_hierro_pct"] > porid["limpio"]["oxidos_hierro_pct"]
    assert porid["rojizo"]["excluido_pct"] > porid["limpio"]["excluido_pct"]
    assert porid["limpio"]["limpia_pct"] > porid["rojizo"]["limpia_pct"]
    # combinaciones de bandas (sin costo extra); ASTER, cocientes, hierro final, férrico y ferroso ya no se dibujan
    assert r["capas"]["swir"].startswith("data:image/jpeg;base64,") and "natural" in r["capas"]
    assert not {"cuarzo_aster", "cocientes", "hierro", "ferrico", "ferroso"} & set(r["capas"]) and "aster" not in r
    assert "cuarzo_aster" not in porid["limpio"]


def test_solo_satelite_sin_zonas():
    """Análisis «solo satélite»: sin zonas no hay sílice limpia; sí hierro, arcillas y cuarzo ASTER."""
    bbox = (-76.52, -13.0, -76.36, -12.88)
    alto, ancho = 48, 64
    b = np.zeros((alto, ancho, 7), np.float32)
    b[..., 0:4] = [800, 900, 1000, 600]
    b[..., 4:6] = [2000, 1800]
    b[..., 6] = 5
    b[:, :20, 0:3] = [3000, 3100, 3200]
    b[:, :20, 4:6] = [3500, 3600]
    anillo = [[-76.52, -13.0], [-76.36, -13.0], [-76.36, -12.88], [-76.52, -12.88], [-76.52, -13.0]]
    r = sentinel_silice.calcular(b, anillo, [], bbox, (ancho, alto))
    assert r["solo_satelite"] is True and r["afloramientos"] == []
    c = r["celda"]
    assert c["pct_silice_limpia"] is None and "pct_cuarzo_alto" not in c
    assert "silice_limpia" not in r["capas"] and {"arcillas", "ndvi", "bsi", "ferruginosas"} <= set(r["capas"])


def test_hierro_ferroso():
    """B8A al final (índice 7): hierro ferroso (B11/B8A) unido al férrico en una sola capa."""
    bbox = (-76.52, -13.0, -76.36, -12.88)
    alto, ancho = 40, 80
    b = np.zeros((alto, ancho, 8), np.float32)
    #            B02   B03   B04   B08   B11   B12  SCL  B8A
    b[:] =      [1500, 1700, 2000, 2300, 3200, 2800, 5, 2400]   # roca clara desnuda
    b[:, 20:40] = [1500, 1700, 2000, 1700, 3200, 2800, 5, 1700]  # roca con Fe²⁺ (B8A bajo → B11/B8A alto)
    b[:, 40:60] = [400, 600, 400, 3500, 1500, 800, 4, 3600]      # vegetación (NDVI alto, BSI < 0)
    b[:, 60:80] = [900, 1200, 700, 500, 150, 100, 6, 450]        # agua (MNDWI > 0)
    anillo = [[-76.52, -13.0], [-76.36, -13.0], [-76.36, -12.88], [-76.52, -12.88], [-76.52, -13.0]]

    def zona(x0, x1, zid):
        lon0, lon1 = -76.52 + 0.16 * x0 / 80, -76.52 + 0.16 * x1 / 80
        return {"id": zid, "clase": "A", "geometria": {"type": "Polygon", "coordinates": [[[lon0, -13.0], [lon1, -13.0], [lon1, -12.88], [lon0, -12.88], [lon0, -13.0]]]}}

    r = sentinel_silice.calcular(b, anillo, [zona(1, 19, "limpia"), zona(21, 39, "ferrosa")], bbox, (ancho, alto))
    # el hierro (férrico + ferroso) se mide y se resta, pero ya no se dibuja como capa propia
    assert not {"hierro", "ferrico", "ferroso", "cocientes", "oxidos_hierro", "humedad", "infrarrojo"} & set(r["capas"])
    z = {s["id"]: s for s in r["afloramientos"]}
    assert z["ferrosa"]["ferroso_pct"] > z["limpia"]["ferroso_pct"]
    assert z["ferrosa"]["hierro_pct"] >= z["ferrosa"]["ferroso_pct"]          # el mayor de los dos rangos
    assert z["ferrosa"]["hierro_pct"] > z["limpia"]["hierro_pct"]
    assert r["celda"]["pct_hierro_alto"] >= r["celda"]["pct_oxidos_altos"]


def test_nubes_y_hora_de_la_toma():
    area = np.ones((10, 10), bool)
    scl = np.full((10, 10), 5)          # suelo desnudo
    assert sentinel_silice.medir_nubes(scl, area) == (0.0, 100.0)
    scl[0, :] = 9                       # una fila de nube alta = 10 %
    scl[1, :5] = 3                      # media fila de sombra de nube = 5 %
    scl[9, :] = 0                       # sin dato: no cuenta como nube, baja la cobertura
    nubes, cobertura = sentinel_silice.medir_nubes(scl, area)
    assert cobertura == 90.0 and abs(nubes - 15 / 90 * 100) < 0.01
    assert isinstance(nubes, float) and type(nubes) is float   # serializable a JSON
    # Perú = UTC−5 (sin horario de verano)
    assert sentinel_silice.hora_peru("2026-04-04T15:26:46.394Z") == "04/04/2026 10:26"
    assert sentinel_silice.hora_peru("2026-01-01T03:00:00Z") == "31/12/2025 22:00"


def test_sentinel_sin_credenciales(monkeypatch):
    """Sin claves de Copernicus y sin respaldo de AWS: «no disponible» (con AWS se usaría AWS)."""
    import sentinel_aws
    os.environ.pop("CDSE_CLIENT_ID", None)
    monkeypatch.setattr(sentinel_aws, "disponible", lambda: False)
    c = TestClient(app)
    d = c.post("/sentinel", json={"poligono": AREA, "afloramientos": []}).json()
    assert d["disponible"] is False


def test_rutas_sin_red():
    """Partes de backend/rutas.py que no necesitan internet."""
    import rutas
    assert abs(rutas.km_linea_recta(-13.0808, -76.3877, -14.0625, -75.8125) - 125.6) < 0.5
    # polyline de Valhalla (precisión 6) → [[lon, lat]]
    assert rutas.decodificar_polyline("_izlhA~rlgdF_{geC~ywl@") == [[-120.2, 38.5], [-120.95, 40.7]]
    assert rutas.tipo_de_tramo({"surface": "paved_smooth", "unpaved": False}) == "pista"
    assert rutas.tipo_de_tramo({"surface": "gravel"}) == "trocha" and rutas.tipo_de_tramo({"use": "track"}) == "trocha"
    L = lambda x0, x1: [[x0, -13.0], [x1, -13.0]]  # noqa: E731
    tramos = [{"tipo": "pista", "km": 50, "vias": ["PE-1S"], "coords": L(0, 1)},
              {"tipo": "trocha", "km": 0.03, "vias": [], "coords": L(1, 1.01)},            # retazo → se absorbe
              {"tipo": "pista", "km": 10, "vias": ["PE-24"], "coords": L(1.01, 2)},
              {"tipo": "trocha", "km": 5, "vias": ["LM-933"], "coords": L(2, 3)},
              {"tipo": "a_pie", "km": 1.2, "vias": [], "coords": L(3, 3.1), "detalle": "sin camino (línea recta)"}]
    b = rutas._agrupar(tramos)
    assert [x["tipo"] for x in b] == ["pista", "trocha", "a_pie"]
    assert abs(b[0]["km"] - 60.03) < 0.01 and b[0]["vias"][0] == "PE-1S" and b[1]["vias"] == ["LM-933"]
    assert b[2]["geometria"]["type"] == "LineString"
    c = TestClient(app)
    assert c.get("/ruta?lat1=-13.08&lon1=-76.39&lat2=40&lon2=-3").status_code == 422   # fuera del Perú

def test_barrido_region():
    """Barrido: varias cuadrículas en segundo plano, con puntaje (ha libres y utilizables × clase)."""
    import time as _t
    c = TestClient(app)
    celdas = [{"codigo": "PRUEBA-1", "sur": -13.00, "oeste": -76.52, "norte": -12.88, "este": -76.36},
              {"codigo": "PRUEBA-2", "sur": -8.02, "oeste": -78.62, "norte": -7.78, "este": -78.38}]
    r = c.post("/barrido", json={"celdas": celdas}).json()
    for _ in range(100):
        e = c.get(f"/barrido/{r['id']}").json()
        if e["terminado"]:
            break
        _t.sleep(0.2)
    assert e["terminado"] and e["hechas"] == 2
    por = {x["codigo"]: x for x in e["resultados"]}
    assert all(x["ok"] for x in por.values()) and "resultado" in por["PRUEBA-1"]
    p1 = por["PRUEBA-1"]
    # Marcavilca (B) está ~10 % libre y utilizable; el resto de zonas suma con su peso
    assert p1["puntaje"] > 0 and p1["ha_util"]["B"] < p1["ha"]["B"] and p1["mejor_zona"]["clase"] in "ABC"
    assert por["PRUEBA-2"]["escala"] == "100K"
    # «desde» devuelve solo lo nuevo; límite de cuadrículas
    assert c.get(f"/barrido/{r['id']}?desde=2").json()["resultados"] == []
    assert c.post("/barrido", json={"celdas": celdas * 40}).status_code == 422


def test_tonelaje_cono_sintetico(monkeypatch):
    """Un cono de arena de 20 m de alto y 300 m de radio sobre terreno plano: V = π r² h / 3 ≈ 1,88 Mm³."""
    import relieve
    from math import cos, pi, radians
    lat0, lon0 = -13.5, -76.0
    def dem_falso(sur, oeste, norte, este):
        n0, o0 = norte, oeste
        filas, cols = int((norte - sur) / relieve.PX), int((este - oeste) / relieve.PX)
        ff, cc = np.indices((filas, cols))
        lat = n0 - (ff + 0.5) * relieve.PX
        lon = o0 + (cc + 0.5) * relieve.PX
        dy = (lat - lat0) * 110540
        dx = (lon - lon0) * 111320 * cos(radians(lat0))
        d = np.hypot(dx, dy)
        return (100 + np.clip(20 * (1 - d / 300), 0, None)).astype(np.float32), (n0, o0)
    monkeypatch.setattr(relieve, "dem", dem_falso)
    r_deg = 400 / 110540   # zona: cuadrado de 800 m que contiene el cono
    zona = {"type": "Polygon", "coordinates": [[[lon0 - r_deg, lat0 - r_deg], [lon0 + r_deg, lat0 - r_deg],
                                                [lon0 + r_deg, lat0 + r_deg], [lon0 - r_deg, lat0 + r_deg], [lon0 - r_deg, lat0 - r_deg]]]}
    t = relieve.tonelaje(zona, tipo="arena")
    v = t["metodos"]["cerro"]["total"]["volumen_m3"]
    assert t["recomendado"] == "cerro" and abs(v - pi * 300 ** 2 * 20 / 3) / v < 0.1        # ±10 %
    assert t["metodos"]["cerro"]["total"]["toneladas"] == round(v * 1.6)
    assert t["metodos"]["manto"]["total"]["espesor_medio_m"] == 5.0
    # potencia máxima de minado: recorta el espesor
    t2 = relieve.tonelaje(zona, tipo="arena", potencia_max=5)
    assert t2["metodos"]["cerro"]["total"]["espesor_max_m"] <= 5.0

def test_geologia_local_igual_que_en_linea(monkeypatch, tmp_path):
    """La copia local de la geología (descargada entera) da EXACTAMENTE las mismas zonas que GEOCATMIN."""
    import geocatmin_rmi as gr
    import geologia_local as gl
    from shapely.geometry import box
    ruta = str(tmp_path / "geologia.sqlite")
    for e in ("50K", "100K"):
        assert gl.descargar(e, ruta=ruta, aviso=lambda m: None) > 0
        assert gl.disponible(e, ruta=ruta)          # con otra ruta no importa que sea el servidor simulado
    assert not gl.disponible("50K")                 # la ruta normal + servidor simulado: NO se usa
    pol = box(-76.52, -13.0, -76.36, -12.88)
    linea = {e: gr.buscar_geologia("arena_silicea", pol, e) for e in ("50K", "100K")}
    monkeypatch.setattr(gl, "disponible", lambda e, ruta=ruta: True)
    monkeypatch.setattr(gl, "features", lambda e, p, ruta=ruta: gl.__dict__["_features_orig"](e, p, ruta))
    for e in ("50K", "100K"):
        local = gr.buscar_geologia("arena_silicea", pol, e)
        clave = lambda r: sorted((a["clase"], a["unidad"], a["area_ha"]) for a in r["afloramientos"])  # noqa: E731
        assert clave(local) == clave(linea[e]) and local["cobertura"] == linea[e]["cobertura"]
    assert gl.estado(ruta)["50K"]["completo"]


def test_materia_prima_del_usuario(monkeypatch, tmp_path):
    """Editor de materias primas: palabras por clase, formaciones y descartes → mismas reglas que la sílice."""
    import materias_primas as mp
    monkeypatch.setattr(mp, "RUTA", str(tmp_path / "materias.json"))
    c = TestClient(app)
    caliza = {"nombre": "Caliza para cemento", "clases": {"A": ["caliza micrítica"], "B": ["caliza"], "C": ["marga"]},
              "formaciones": ["Formación Chulec"], "descartar": ["dolomía", "andesita"], "rmi": ["Caliza"]}
    # probar sin guardar
    p = c.post("/materias_primas/probar", json={"definicion": caliza, "litologia": "Calizas micríticas grises"}).json()
    assert p["clase"] == "A"
    r = c.post("/materias_primas", json=caliza)
    assert r.status_code == 200 and r.json()["id"] == "caliza_para_cemento"
    k = lambda **t: clasificar("caliza_para_cemento", t)  # noqa: E731
    assert k(LITOLOGIA="Calizas micríticas grises")[0] == "A"
    assert k(LITOLOGIA="Calizas grises en bancos")[0] == "B"                       # roca de clase B
    assert k(LITOLOGIA="Lutitas con niveles de calizas")[0] == "B"                 # secundaria: cuenta igual
    assert k(LITOLOGIA="Calizas con dolomías")[0] == "C"                           # roca descartada presente
    assert k(LITOLOGIA="Calizas", LITO1="Lutita")[0] == "B"                        # domina otra roca: solo se anota
    assert k(UNIDAD="Formación Chulec", LITOLOGIA="Margas y lutitas")[0] in "BC"
    assert k(UNIDAD="Formación Chulec", LITOLOGIA="Lutitas negras")[0] == "C"       # formación sin roca de interés
    assert k(LITOLOGIA="Arenisca cuarzosa") is None
    assert clasificar("arena_silicea", {"LITOLOGIA": "Cuarcitas grises"})[0] == "B"   # la sílice no cambia
    lista = {m["id"]: m for m in c.get("/materiales").json()}
    assert lista["caliza_para_cemento"]["usuario"] and "CALIZA" in lista["caliza_para_cemento"]["sql50"]
    assert not lista["arena_silicea"]["usuario"] and "CUARCIT" in lista["arena_silicea"]["sql50"]
    form = c.get("/formaciones", params={"material": "caliza_para_cemento"}).json()
    assert any(f["nombre"] == "Formación Chulec" and "CHULEC" in f["sql50"] for f in form)
    # búsqueda por cuadrícula con la materia prima nueva (servidor simulado)
    d = c.post("/buscar", json={"material": "caliza_para_cemento", "poligono": AREA})
    assert d.status_code == 200, d.text
    # la de fábrica se ve pero no se borra; la del usuario sí
    assert c.get("/materias_primas/arena_silicea").json()["fabrica"]
    assert c.delete("/materias_primas/arena_silicea").status_code == 422
    assert c.delete("/materias_primas/caliza_para_cemento").json()["ok"]
    assert "caliza_para_cemento" not in {m["id"] for m in c.get("/materiales").json()}
    assert c.post("/materias_primas", json={"nombre": "x"}).status_code == 422


def test_laminas_lugar_y_reproyeccion():
    """Láminas: provincia/departamento por punto (geoBoundaries) y reproyección de capas a la grilla UTM."""
    import laminas
    from PIL import Image
    assert laminas.lugar(-13.0808, -76.3877) == {"departamento": "Lima", "provincia": "Cañete"}
    assert laminas.lugar(-9.69, -78.19)["departamento"] == "Áncash"
    mr = laminas.Marco(-76.375, -13.125, -76.25, -13.0, 400, 300)
    assert mr.zona == 18 and mr.epsg == 32718
    img = Image.new("RGBA", (10, 10), (255, 0, 0, 255))      # capa roja que cubre justo la cuadrícula
    out = mr.reproyectar(img, "4326", (-76.375, -13.125, -76.25, -13.0))
    a = out.getchannel("A")
    assert a.getpixel((200, 150)) == 255 and a.getpixel((2, 2)) == 0   # centro pintado, margen vacío


def test_sentinel_respaldo_aws_si_se_acaba_el_cupo(monkeypatch):
    """Copernicus primero; con el cupo agotado (o sin claves, o caído) pasa al archivo público de AWS."""
    import sentinel_aws
    anillo = [[-76.52, -13.0], [-76.36, -13.0], [-76.36, -12.88], [-76.52, -12.88], [-76.52, -13.0]]
    llamadas = []

    def aws_falso(an, bbox, tam, area):
        llamadas.append(tam)
        b = np.zeros((tam[1], tam[0], 8), np.float32)
        b[:] = [1500, 1700, 2000, 2300, 3200, 2800, 5, 2400]
        return b, {"dia": "2026-06-28", "datetime": "2026-06-28T15:21:00Z", "nubes_escena": 0.5,
                   "revisadas": 1, "candidatas": []}

    monkeypatch.setattr(sentinel_aws, "descargar", aws_falso)
    monkeypatch.setattr(sentinel_aws, "disponible", lambda: True)
    monkeypatch.setattr(sentinel_silice, "disponible", lambda: True)
    monkeypatch.setattr(sentinel_silice, "_config", lambda: object())

    def sin_unidades(*a, **k):
        raise RuntimeError('403 {"code":"ACCESS_INSUFFICIENT_PROCESSING_UNITS","message":"insufficient processing units"}')
    monkeypatch.setattr(sentinel_silice, "elegir_fecha", sin_unidades)
    r = sentinel_silice.analizar(anillo, [])
    assert r["disponible"] and "AWS" in r["fuente"] and "cupo" in r["fuente"] and llamadas
    assert r["imagen"]["fecha_peru"] == "28/06/2026 10:21" and {"ndvi", "bsi"} <= set(r["capas"])

    def caido(*a, **k):
        raise ConnectionError("timeout")
    monkeypatch.setattr(sentinel_silice, "elegir_fecha", caido)
    assert "no respondió" in sentinel_silice.analizar(anillo, [])["fuente"]
    monkeypatch.setattr(sentinel_silice, "disponible", lambda: False)          # sin claves de Copernicus
    assert "sin claves" in sentinel_silice.analizar(anillo, [])["fuente"]
    assert sentinel_silice.sin_cupo(RuntimeError("HTTP 429 Too Many Requests"))
    assert not sentinel_silice.sin_cupo(RuntimeError("timeout"))


def test_ranking_nacional(monkeypatch, tmp_path):
    """Ranking: una carta por cuadrícula (50K si tiene A/B), km² A/B libres y utilizables, selva y tipos."""
    import json as _json
    import ranking
    def escribir(nombre, celdas):
        (tmp_path / nombre).write_text(_json.dumps({"celdas": celdas}), encoding="utf-8")
    escribir("censo_silice.json", {"27k1-SO": {"50K": {"A": 10}}, "12c4-SO": {"50K": {"C": 5}, "100K": {"A": 900}}})
    escribir("censo_libres.json", {
        "27k1-SO": {"ok": True, "escala": "50K", "ha_util": {"A": 3000, "B": 1670}, "util_pct_celda": 40, "zonas_100k_A_ha": 0},
        "12c4-SO": {"ok": True, "escala": "50K", "ha_util": {"A": 0, "B": 0, "C": 10}, "util_pct_celda": 80, "zonas_100k_A_ha": 10000},
        "99z9-NE": {"ok": False}})
    escribir("censo_bosque.json", {"27k1-SO": {"bosque_pct": 2}, "12c4-SO": {"bosque_pct": 0}})
    monkeypatch.setattr(ranking, "DATOS", str(tmp_path))
    ranking._cache.update(firma=None, filas=None)
    f = {x["codigo"]: x for x in ranking.filas()}
    assert f["27k1-SO"]["carta"] == "50K" and f["27k1-SO"]["km2"] == 46.7 and not f["27k1-SO"]["aprox"]
    assert f["12c4-SO"]["carta"] == "100K" and f["12c4-SO"]["aprox"] and f["12c4-SO"]["km2"] == 80.0
    assert f["12c4-SO"]["puesto"] == 1 and f["27k1-SO"]["km_fabrica"] < 40 and "99z9-NE" not in f
    # con el censo por tipo: hectáreas por material de la carta usada
    (tmp_path / "censo_tipos.json").write_text(_json.dumps({"celdas": {"27k1-SO": {"ok": True, "zonas": [
        {"escala": "50K", "clase": "A", "tipo": "arena", "ha": 2000, "util_pct": 50},
        {"escala": "50K", "clase": "B", "tipo": "cuarcita", "ha": 1000, "util_pct": 10},
        {"escala": "100K", "clase": "A", "tipo": "arena", "ha": 5000, "util_pct": 90}]}}}), encoding="utf-8")
    ranking._cache.update(firma=None, filas=None)
    t = {x["codigo"]: x for x in ranking.filas()}["27k1-SO"]
    assert t["tipos_km2"] == {"arena": 10.0, "arenisca": 0.0, "cuarcita": 1.0} and t["km2"] == 11.0
    ranking._cache.update(firma=None, filas=None)


def test_vigilancia_catastro():
    """Vigilancia: la 1.ª revisión es la línea base; después avisa petitorios nuevos, cambios de estado,
    derechos que desaparecen y publicaciones de libre denunciabilidad."""
    import vigilancia
    c = TestClient(app)
    r = c.post("/vigilancia/revisar", json={"items": [{"id": "x", "anillo": AREA}]}).json()[0]
    assert r["ok"] and r["alertas"][0]["tipo"] == "base"
    f = r["foto"]
    assert set(f["derechos"]) == {"010000123", "010000999"} and f["ld"] == ["010000999"] and 8 < f["ocupado_pct"] < 11
    # simular el pasado: no estaba la cantera, el extinguido estaba titulado, había otro derecho y sin LD
    previo = {"derechos": {"010000999": {**f["derechos"]["010000999"], "leyenda": "TITULADO", "estado": "titulado"},
                           "010777777": {"nombre": "VIEJA", "leyenda": "TITULADO"}},
              "ocupado_pct": 30.0, "ld": []}
    al = vigilancia.comparar(previo, f, propio=True)
    tipos = {a["tipo"]: a for a in al}
    assert tipos["nuevo"]["nivel"] == "alta" and tipos["nuevo"]["codigo"] == "010000123"
    assert tipos["estado"]["nivel"] == "alta" and "Ya no tiene titular" in tipos["estado"]["texto"]
    assert tipos["desaparecio"]["codigo"] == "010777777" and tipos["ld"]["codigo"] == "010000999" and "ocupado" in tipos
    assert vigilancia.comparar(f, f) == []      # sin cambios, sin alertas


def test_silice_limpia_excluye_hierro_y_arcilla():
    """Lo que la app marca como hierro (férrico o ferroso) o arcilla NO puede quedar en la sílice limpia (base de la Prioridad libre)."""
    import base64 as b64
    from io import BytesIO
    from PIL import Image
    alto, ancho = 60, 120
    bbox = (-76.52, -13.0, -76.36, -12.88)
    rng = np.random.default_rng(1)
    b = np.zeros((alto, ancho, 8), np.float32)
    b[:] = [1500, 1700, 2000, 2300, 3200, 2800, 5, 2400]
    b[..., :6] *= rng.uniform(0.97, 1.03, (alto, ancho, 1))          # algo de variación
    b[:, 30:38, 2] = 3600; b[:, 30:38, 7] = 1500                       # franja ferruginosa (férrico y ferroso altos, 6,7 %)
    b[:, 70:78, 4] = 4200; b[:, 70:78, 5] = 2600                       # franja arcillosa (B11/B12 alto, 6,7 %)
    anillo = [[-76.52, -13.0], [-76.36, -13.0], [-76.36, -12.88], [-76.52, -12.88], [-76.52, -13.0]]
    zona = {"id": "z", "clase": "A", "geometria": {"type": "Polygon", "coordinates": [anillo]}}
    r = sentinel_silice.calcular(b, anillo, [zona], bbox, (ancho, alto), cortes={"p_ferruginosa": 0.5, "arcilla": 0.9, "p_ndvi": 2})
    alfa = lambda k: np.asarray(Image.open(BytesIO(b64.b64decode(r["capas"][k].split(",")[1]))).convert("RGBA"))[..., 3] > 0  # noqa: E731
    prio, arc = alfa("silice_limpia"), alfa("arcillas")
    clase_arc = np.asarray(Image.open(BytesIO(b64.b64decode(r["capas"]["arcillas"].split(",")[1]))))
    assert arc.mean() > 0.95 and (clase_arc[:, 71:77] == 10).mean() > 0.9   # 10 clases fijas: la franja en la más alta
    assert prio[:, 71:77].mean() < 0.1                                       # la arcilla se excluye
    assert prio[:, 31:37].mean() < 0.1                                       # la franja férrica también se excluye
    assert prio.any() and r["celda"]["pct_excluido_hierro_arcilla"] > 10
    # el usuario mueve los cortes: más alto = se excluye menos; histograma del cociente real
    r3 = sentinel_silice.calcular(b, anillo, [zona], bbox, (ancho, alto), cortes={"p_ferruginosa": 0.95, "arcilla": 0.95, "p_ndvi": 2})
    assert r3["celda"]["pct_excluido_hierro_arcilla"] < r["celda"]["pct_excluido_hierro_arcilla"]
    h = r["datos"]["hist"]["ferruginosa"]
    assert len(h["percentiles"]) == 101 and len(h["cuentas"]) == 60 and h["percentiles"][99] > h["percentiles"][50]


def test_pdf_de_laminas():
    """Varias láminas PNG → un PDF de varias páginas."""
    import base64 as b64
    from io import BytesIO
    from PIL import Image
    def png(color):
        buf = BytesIO(); Image.new("RGB", (300, 212), color).save(buf, "PNG")
        return "data:image/png;base64," + b64.b64encode(buf.getvalue()).decode()
    r = TestClient(app).post("/pdf", json={"paginas": [png("white"), png("red")], "titulo": "27k1-SO"})
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF") and r.content.count(b"/Type /Page\n") + r.content.count(b"/Type /Page ") + r.content.count(b"/Type /Page>") >= 1
    assert TestClient(app).post("/pdf", json={"paginas": []}).status_code == 422


def test_silice_limpia_solo_en_zonas_y_sin_hierro():
    """«silice_limpia»: solo dentro de las zonas A/B y nunca sobre hierro/arcilla excluidos."""
    import base64 as b64
    from io import BytesIO
    from PIL import Image
    alto, ancho = 60, 120
    bbox = (-76.52, -13.0, -76.36, -12.88)
    rng = np.random.default_rng(2)
    b = np.zeros((alto, ancho, 8), np.float32)
    b[:] = [1500, 1700, 2000, 2300, 3200, 2800, 5, 2400]
    b[..., :6] *= rng.uniform(0.9, 1.1, (alto, ancho, 1))
    b[:, 30:38, 2] = 3600; b[:, 30:38, 7] = 1500
    anillo = [[-76.52, -13.0], [-76.36, -13.0], [-76.36, -12.88], [-76.52, -12.88], [-76.52, -13.0]]
    mitad = [[-76.52, -13.0], [-76.44, -13.0], [-76.44, -12.88], [-76.52, -12.88], [-76.52, -13.0]]
    zona = {"id": "z", "clase": "B", "geometria": {"type": "Polygon", "coordinates": [mitad]}}
    r = sentinel_silice.calcular(b, anillo, [zona], bbox, (ancho, alto), cortes={"p_ferruginosa": 0.5, "arcilla": 0.9, "p_ndvi": 2})
    alfa = lambda k: np.asarray(Image.open(BytesIO(b64.b64decode(r["capas"][k].split(",")[1]))).convert("RGBA"))[..., 3] > 0  # noqa: E731
    sl = alfa("silice_limpia")
    assert sl.any() and not sl[:, ancho // 2 + 2:].any()      # solo en la mitad oeste (la zona)
    assert sl[:, 31:37].mean() < 0.1                          # la franja férrica no queda limpia


def test_hierro_por_percentil_del_usuario():
    """Hierro por PERCENTIL (sin k): se marca lo que queda en o sobre el percentil elegido de cada cociente."""
    alto, ancho = 60, 120
    bbox = (-76.52, -13.0, -76.36, -12.88)
    anillo = [[-76.52, -13.0], [-76.36, -13.0], [-76.36, -12.88], [-76.52, -12.88], [-76.52, -13.0]]
    rng = np.random.default_rng(3)
    b = np.zeros((alto, ancho, 8), np.float32)
    b[:] = [1500, 1700, 2000, 2300, 3200, 2800, 5, 2400]
    b[..., :6] *= rng.normal(1, 0.01, (alto, ancho, 6))               # ruido independiente por banda
    b[:, 0:24, 2] = 3400; b[:, 0:24, 7] = 1600                         # 20 % ferruginoso (férrico y ferroso altos)
    p80 = sentinel_silice.calcular(b, anillo, [], bbox, (ancho, alto), cortes={"p_ferruginosa": 0.80})["celda"]
    assert 17 < p80["anomalia_hierro_pct"] < 23                        # sobre P80 = el 20 % más alto (la franja)
    p95 = sentinel_silice.calcular(b, anillo, [], bbox, (ancho, alto), cortes={"p_ferruginosa": 0.95})["celda"]
    assert p95["anomalia_hierro_pct"] < p80["anomalia_hierro_pct"]     # subir el percentil marca menos
    viejo = sentinel_silice.calcular(b, anillo, [], bbox, (ancho, alto), cortes={"z_ferrico": 2})   # cortes antiguos: se ignoran
    assert viejo["cortes"] == sentinel_silice.CORTES


def test_concesionado_negociable():
    """Titulados / en trámite fuera de áreas protegidas = «negociable» (no libre); extinguidos no cuentan."""
    import libres as lib
    from shapely.geometry import box
    pol = box(-76.52, -13.0, -76.40, -12.90)
    cons = [
        {"_geom": box(-76.52, -13.0, -76.46, -12.90), "_negociable": True, "_extinguido": False, "_actualizado": None},
        {"_geom": box(-76.46, -13.0, -76.43, -12.90), "_negociable": False, "_extinguido": True, "_actualizado": None},
    ]
    reserva = {"_geom": box(-76.52, -13.0, -76.49, -12.90)}           # mitad de la concesión dentro de un área protegida
    r = lib.calcular(pol, cons, [reserva])
    assert 20 < r["negociable_pct"] < 30                               # 3/12 de la cuadrícula
    assert r["concesiones_pct"] > r["negociable_pct"]                  # lo protegido no es negociable
    assert r["libre_pct"] + r["concesiones_pct"] <= 100.5
    z = lib.negociable_en_zona(r, box(-76.49, -13.0, -76.46, -12.90))
    assert z is None or z >= 0


def test_supermaduras(monkeypatch, tmp_path):
    """Supermaduras: datos del informe servidos tal cual y consulta por cuadrícula 1:25 000 (con validación del código)."""
    import json as _json
    import supermaduras
    d = {"generado": "2026-11-23", "fabrica": [-13.0808, -76.3877], "n_boletines": 51,
         "unidades": [{"id": "chimu", "nombre": "Formación Chimú", "tipo": "sed", "prioridad": 1, "prioridad_txt": "Supermadura con química",
                       "madurez": "x", "certeza": "x", "definicion": "x", "puntos": [], "area_km2": 30.5, "n_hojas": 1, "n_celdas": 2,
                       "celdas": [["15g3-NE", 21.7, 3, "50K", 678, "Cajamarca", "Cajamarca"], ["15g3-NO", 8.8, 1, "50K", 680, "Cajamarca", "Cajamarca"]],
                       "citas": []},
                      {"id": "m_sandia", "nombre": "Formación Sandia", "tipo": "meta", "prioridad": 5, "prioridad_txt": "Cuarcita metamórfica",
                       "madurez": "x", "certeza": "x", "definicion": "x", "puntos": [], "area_km2": 40, "n_hojas": 1, "n_celdas": 1,
                       "celdas": [["15g3-NE", 40.0, 2, "100K", 678, "Cajamarca", "Cajamarca"]], "citas": []}],
         "quimica": [{"nombre": "Ocurrencia Hualqui", "celda": "15g3-NE", "sio2": 95.27, "fe2o3": 0.09, "grado": "vidrio"}],
         "ocurrencias": [], "especificaciones": [], "boletines": {}}
    ruta = tmp_path / "supermaduras.json"
    ruta.write_text(_json.dumps(d), encoding="utf-8")
    monkeypatch.setattr(supermaduras, "RUTA", str(ruta))
    monkeypatch.setitem(supermaduras._cache, "mtime", None)
    c = TestClient(app)
    r = c.get("/supermaduras")
    assert r.status_code == 200 and r.json()["n_boletines"] == 51 and len(r.json()["unidades"]) == 2
    r = c.get("/supermaduras/celda/15g3-NE").json()
    # ordenadas por prioridad (la sedimentaria primero aunque la metamórfica tenga más km²)
    assert [u["id"] for u in r["unidades"]] == ["chimu", "m_sandia"] and r["unidades"][0]["km2"] == 21.7
    assert r["quimica"][0]["grado"] == "vidrio"
    assert c.get("/supermaduras/celda/15g3-NO").json()["unidades"][0]["km2"] == 8.8
    assert c.get("/supermaduras/celda/27k4-NE").json()["unidades"] == []
    assert c.get("/supermaduras/celda/15g9-XX").status_code == 400


def test_supermaduras_datos_reales():
    """El archivo generado trae las unidades del informe y la cantera de Hualqui en su cuadrícula (15g3-NE)."""
    import supermaduras
    d = supermaduras.datos()
    if not d:
        pytest.skip("sin datos/supermaduras.json")
    ids = {u["id"] for u in d["unidades"]}
    assert {"chimu", "farrat", "goyllarisquizga", "vivian", "eolico", "m_sandia"} <= ids
    q = next(x for x in d["quimica"] if "Hualqui" in x["nombre"])
    assert q["celda"] == "15g3-NE" and q["grado"] == "vidrio"
    for u in d["unidades"]:
        assert abs(sum(c[1] for c in u["celdas"]) - u["area_km2"]) <= max(0.5, 0.01 * u["area_km2"])


def test_ranking_orden_supermadurez():
    """El ranking va por supermadurez (rango de la unidad), no por área; las zonas se asignan a su unidad por nombre."""
    import ranking
    assert ranking.unidad_sm("Grupo Goyllarisquizga - Formación Chimú") == "chimu"
    assert ranking.unidad_sm("Grupo Goyllarisquizga") == "goyllarisquizga"
    assert ranking.unidad_sm("Formaciones Oyón, Chimú") is None
    assert ranking.unidad_sm("Depósito eólico") == "eolico" and ranking.unidad_sm("Grupo Talara") is None
    assert ranking.RANGO_SM["chimu"] < ranking.RANGO_SM["eolico"] < ranking.RANGO_SM["hualhuani"] < ranking.RANGO_SM["m_sandia"]
    fs = [f for f in ranking.filas() if f.get("sm_rango")]
    if not fs:
        pytest.skip("sin censos")
    rangos = [f["sm_rango"] for f in fs]
    assert rangos == sorted(rangos)   # nunca una unidad menos supermadura antes que una más supermadura


def test_silice_limpia_y_lamina_de_prioridad(monkeypatch):
    """Prioridad libre = zonas silíceas − hierro − arcillas (capa «silice_limpia») × lámina en modo «prioridad»:
    verde libre · azul concesión titulada/en trámite (también sobre chacras) · amarillo chacra · protegido transparente."""
    import base64 as b64
    from io import BytesIO
    from PIL import Image
    import libres as lib
    alto, ancho = 60, 120
    bbox = (-76.52, -13.0, -76.36, -12.88)
    rng = np.random.default_rng(5)
    b = np.zeros((alto, ancho, 8), np.float32)
    b[:] = [1500, 1700, 2000, 2300, 3200, 2800, 5, 2400]
    b[..., :6] *= rng.uniform(0.97, 1.03, (alto, ancho, 1))
    b[:, 30:38, 2] = 3600; b[:, 30:38, 7] = 1500                        # franja ferruginosa dentro de la zona
    anillo = [[-76.52, -13.0], [-76.36, -13.0], [-76.36, -12.88], [-76.52, -12.88], [-76.52, -13.0]]
    mitad = [[-76.52, -13.0], [-76.44, -13.0], [-76.44, -12.88], [-76.52, -12.88], [-76.52, -13.0]]
    zona = {"id": "z", "clase": "B", "geometria": {"type": "Polygon", "coordinates": [mitad]}}
    r = sentinel_silice.calcular(b, anillo, [zona], bbox, (ancho, alto), cortes={"p_ferruginosa": 0.9, "arcilla": 2, "p_ndvi": 2})
    a = np.asarray(Image.open(BytesIO(b64.b64decode(r["capas"]["silice_limpia"].split(",")[1]))).convert("RGBA"))[..., 3] > 0
    assert a[:, 2:26].mean() > 0.9                    # zona limpia: entra aunque sea clase B
    assert not a[:, 31:37].any()                      # la franja de hierro sale
    assert not a[:, ancho // 2 + 2:].any()            # fuera de la zona silícea no hay nada
    # lámina «prioridad»: columnas = libre · chacra libre · concesión en chacra · concesión apta · protegido
    h, w = 16, 20                                    # 5 franjas de 4 columnas (la lámina mide al menos 16 px)
    z = lambda: np.zeros((h, w), bool)  # noqa: E731
    m = {k: z() for k in ("ocupado", "extinguido", "negociable", *lib.MOTIVOS)}
    m["tierra"] = np.ones((h, w), bool)
    m["cultivo"][:, 4:12] = True
    m["ocupado"][:, 8:20] = True
    m["negociable"][:, 8:16] = True                   # titulado / en trámite (la 5.ª columna es área protegida)
    monkeypatch.setattr(lib, "mascaras", lambda *x, **k: m)
    monkeypatch.setattr(lib, "contorno_peru", lambda: None)
    img = np.asarray(Image.open(BytesIO(lib._imagen(-76.5, -13.0, -76.4, -12.9, w, h, "prioridad"))).convert("RGBA"))
    assert tuple(img[0, 1]) == lib.PRIO_VERDE and tuple(img[0, 5]) == lib.PRIO_AMARILLO
    assert tuple(img[0, 9]) == lib.PRIO_AZUL and tuple(img[0, 13]) == lib.PRIO_AZUL and img[0, 17, 3] == 0
    mapa = np.asarray(Image.open(BytesIO(lib._imagen(-76.5, -13.0, -76.4, -12.9, w, h))).convert("RGBA"))
    assert mapa[0, 9, 3] == 0                         # en la capa del mapa, la concesión sobre chacra no se pinta (como antes)


def test_fotos_de_boletines_por_cuadricula():
    """Fotos de los boletines: la de la cantera Hualqui sale en SU cuadrícula; la imagen se sirve y no hay rutas raras."""
    import supermaduras
    d = supermaduras.datos()
    if not d or not d.get("fotos"):
        pytest.skip("sin fotos")
    r = supermaduras.en_celda("15g3-NE")
    hualqui = [f for f in r["fotos"] if "Hualqui" in f["leyenda"]]
    assert hualqui and hualqui[0]["motivo"] == "Tomada en esta cuadrícula"
    assert r["fotos"][0]["motivo"] == "Tomada en esta cuadrícula"          # primero las de la propia cuadrícula
    assert all(f["unidad"] in {u["id"] for u in r["unidades"]} or f.get("celda") == "15g3-NE" for f in r["fotos"])
    c = TestClient(app)
    ok = c.get(f"/supermaduras/foto/{hualqui[0]['archivo']}")
    assert ok.status_code == 200 and ok.headers["content-type"] == "image/jpeg" and ok.content[:2] == b"\xff\xd8"
    assert supermaduras.ruta_foto("../main.py") is None and supermaduras.ruta_foto("x.jpg") is None
    assert c.get("/supermaduras/foto/..%2Fmain.py").status_code == 404


def test_ranking_vidrio_flotado():
    """Vidrio flotado: solo roca blanca con grano medio a grueso; ordenado por supermadurez; /ranking lo entrega."""
    import ranking
    vf = ranking.vidrio()
    if not vf:
        pytest.skip("sin datos/vidrio_flotado.json")
    assert all(f["grano"] in ("medio", "medio a grueso", "grueso") for f in vf)
    assert [f["rango"] for f in vf] == sorted(f["rango"] for f in vf)
    assert vf[0]["unidad"].startswith("Formación Chimú") and "blan" in vf[0]["frase"].lower()
    r = TestClient(app).get("/ranking").json()
    assert r["con_vidrio"] and len(r["vidrio"]) == len(vf) and "selva" in r["vidrio"][0]


def test_silice_limpia_solo_zonas_A_y_B():
    """La Prioridad libre parte SOLO de zonas A y B: una zona C («verificar») no entra aunque esté limpia."""
    import base64 as b64
    from io import BytesIO
    from PIL import Image
    alto, ancho = 60, 120
    bbox = (-76.52, -13.0, -76.36, -12.88)
    b = np.zeros((alto, ancho, 8), np.float32)
    b[:] = [1500, 1700, 2000, 2300, 3200, 2800, 5, 2400]
    anillo = [[-76.52, -13.0], [-76.36, -13.0], [-76.36, -12.88], [-76.52, -12.88], [-76.52, -13.0]]
    oeste = [[-76.52, -13.0], [-76.44, -13.0], [-76.44, -12.88], [-76.52, -12.88], [-76.52, -13.0]]
    este = [[-76.44, -13.0], [-76.36, -13.0], [-76.36, -12.88], [-76.44, -12.88], [-76.44, -13.0]]
    zonas = [{"id": "b", "clase": "B", "geometria": {"type": "Polygon", "coordinates": [oeste]}},
             {"id": "c", "clase": "C", "geometria": {"type": "Polygon", "coordinates": [este]}}]
    r = sentinel_silice.calcular(b, anillo, zonas, bbox, (ancho, alto), cortes={"p_ferruginosa": 2, "arcilla": 2, "p_ndvi": 2})
    a = np.asarray(Image.open(BytesIO(b64.b64decode(r["capas"]["silice_limpia"].split(",")[1]))).convert("RGBA"))[..., 3] > 0
    assert a[:, 2:56].mean() > 0.95 and not a[:, 64:].any()


def test_fecha_epoca_seca_y_menos_vegetacion():
    """Entre las tomas despejadas gana la de MENOS vegetación (SCL 4); se miden fechas de época seca primero."""
    import numpy as np
    cands = [{"dia": f"2026-{m:02d}-10", "nubes_escena": n} for m, n in ((1, 0.1), (3, 0.2), (5, 0.3), (7, 2.0), (8, 4.0), (12, 0.5))]
    orden = [c["dia"][5:7] for c in sentinel_silice.ordenar_candidatas(cands, 4)]
    assert orden[:2] == ["07", "08"] and set(orden[2:]) <= {"01", "03"}
    medidas = [{"dia": "2026-05-25", "nubes_cuadricula": 0.0, "cobertura": 100, "vegetacion": 97.0},
               {"dia": "2026-08-10", "nubes_cuadricula": 0.3, "cobertura": 100, "vegetacion": 12.0},
               {"dia": "2026-01-10", "nubes_cuadricula": 9.0, "cobertura": 100, "vegetacion": 2.0}]
    assert sentinel_silice.escoger(medidas)["dia"] == "2026-08-10"        # despejada y menos verde
    assert sentinel_silice.escoger([medidas[2]])["dia"] == "2026-01-10"   # sin despejadas: la de menos nubes
    scl = np.full((10, 10), 5); scl[:3] = 4; scl[9] = 9
    assert sentinel_silice.medir_vegetacion(scl, np.ones((10, 10), bool)) == round(100 * 30 / 90, 1)


def test_afloramientos_y_ferruginosas_escala_continua():
    """NDVI + BSI (afloramientos) y B4/B2 + B4/B3 (ferruginosas): escala continua sobre el 100 % de los píxeles con
    dato (sin corte); las nubes quedan transparentes."""
    import base64 as b64
    from io import BytesIO
    from PIL import Image
    alto, ancho = 40, 80
    bbox = (-76.52, -13.0, -76.36, -12.88)
    anillo = [[-76.52, -13.0], [-76.36, -13.0], [-76.36, -12.88], [-76.52, -12.88], [-76.52, -13.0]]
    b = np.zeros((alto, ancho, 8), np.float32)
    b[:] = [1500, 1700, 2000, 2300, 3200, 2800, 5, 2400]
    b[:, :20] = [400, 700, 500, 4000, 1800, 900, 4, 3900]       # vegetación (oeste)
    b[:, 60:, 2] = 3400                                           # ferruginoso (este): B4 alto
    b[:5, :, 6] = 9                                               # nubes arriba
    zonas = [{"id": "veg", "clase": "B", "geometria": {"type": "Polygon", "coordinates": [[[-76.52, -13.0], [-76.49, -13.0], [-76.49, -12.88], [-76.52, -12.88], [-76.52, -13.0]]]}},
             {"id": "fe", "clase": "B", "geometria": {"type": "Polygon", "coordinates": [[[-76.39, -13.0], [-76.36, -13.0], [-76.36, -12.88], [-76.39, -12.88], [-76.39, -13.0]]]}}]
    r = sentinel_silice.calcular(b, anillo, zonas, bbox, (ancho, alto))
    st = {z["id"]: z for z in r["afloramientos"]}
    assert st["veg"]["ndvi_pct"] > st["fe"]["ndvi_pct"] and st["veg"]["bsi_pct"] < st["fe"]["bsi_pct"]   # NDVI y BSI aparte
    assert "afloramientos" not in r["capas"]
    assert st["fe"]["ferruginosa_pct"] > st["veg"]["ferruginosa_pct"]       # férrico + ferroso
    alfa = lambda r_, k: np.asarray(Image.open(BytesIO(b64.b64decode(r_["capas"][k].split(",")[1]))).convert("RGBA"))[..., 3]  # noqa: E731
    for k in ("ndvi", "bsi"):
        im = Image.open(BytesIO(b64.b64decode(r["capas"][k].split(",")[1])))
        a = alfa(r, k)
        assert im.mode == "P" and (a[:5] == 0).all() and (a[8:] > 0).all()    # 100 % pintado salvo la nube
    # anomalía ferruginosa en 10 CLASES FIJAS (P0–P100) sobre todo lo que tiene dato; el corte no cambia los colores
    clase = lambda r_: np.asarray(Image.open(BytesIO(b64.b64decode(r_["capas"]["ferruginosas"].split(",")[1]))))  # noqa: E731
    assert (alfa(r, "ferruginosas")[5:] > 0).all() and (alfa(r, "ferruginosas")[:5] == 0).all()
    assert clase(r)[5:, 61:].mean() > clase(r)[5:, 21:59].mean() + 2   # la franja ferruginosa en clases más altas
    r1 = sentinel_silice.calcular(b, anillo, zonas, bbox, (ancho, alto), cortes={"p_ferruginosa": 0.01})
    assert (clase(r1) == clase(r)).all()


def test_exportar_sig_kmz_y_shapefile():
    """Vectorización de una grilla + KMZ válido + shapefile legible (sin red)."""
    import io
    import zipfile
    import xml.dom.minidom
    import shapefile
    import exportar_sig as ex
    from shapely.geometry import box
    cl = np.zeros((40, 80), np.uint8)
    cl[5:20, 10:30] = 1
    cl[25:35, 50:70] = 2
    polis = ex._vectorizar(cl, -76.52, -13.0, -76.36, -12.88)
    assert set(polis) == {1, 2}
    a1 = polis[1].area / ((0.16 / 80) * (0.12 / 40))
    assert abs(a1 - 15 * 20) < 15                                       # 300 píxeles
    capas = [{"id": "zonas", "nombre": "Zonas", "features": [
        {"geom": polis[1], "estilo": "B", "props": {"clase": "B", "unidad": "Fm. Farrat", "area_ha": 12.5}},
        {"geom": box(-76.5, -12.99, -76.45, -12.95), "estilo": "A", "props": {"clase": "A", "unidad": "Depósito eólico", "area_ha": 3.0}}]}]
    k = ex.kmz(capas, "prueba")
    xml.dom.minidom.parseString(zipfile.ZipFile(io.BytesIO(k)).read("doc.kml"))
    z = zipfile.ZipFile(io.BytesIO(ex.shp_zip(capas, "t")))
    assert {"t_zonas.shp", "t_zonas.shx", "t_zonas.dbf", "t_zonas.prj", "t_zonas.cpg"} <= set(z.namelist())
    r = shapefile.Reader(shp=io.BytesIO(z.read("t_zonas.shp")), shx=io.BytesIO(z.read("t_zonas.shx")),
                         dbf=io.BytesIO(z.read("t_zonas.dbf")), encoding="utf-8")
    assert len(r) == 2 and r.record(1)["unidad"] == "Depósito eólico" and r.shapeType == shapefile.POLYGON


def test_pdf_comprimido():
    """El PDF de las láminas usa JPEG calidad 70: bastante más liviano que a calidad 92."""
    import main
    from io import BytesIO
    from PIL import Image
    rng = np.random.default_rng(0)
    im = Image.fromarray((rng.random((600, 800, 3)) * 255).astype(np.uint8))
    nuevo = main._pdf_de_imagenes([im, im], "prueba")
    viejo = BytesIO()
    im.save(viejo, "PDF", save_all=True, append_images=[im], resolution=150, quality=92)
    assert nuevo.startswith(b"%PDF") and len(nuevo) < 0.8 * len(viejo.getvalue())


def test_prioridad_definitiva_interseccion():
    """24/11/2026: sílice limpia = zona A/B ∩ NDVI < P57 ∩ ferruginosa < P30 ∩ arcilla < P30 (por defecto; sin BSI)."""
    import base64 as b64
    from io import BytesIO
    from PIL import Image
    alto, ancho = 40, 80
    bbox = (-76.52, -13.0, -76.36, -12.88)
    anillo = [[-76.52, -13.0], [-76.36, -13.0], [-76.36, -12.88], [-76.52, -12.88], [-76.52, -13.0]]
    rng = np.random.default_rng(7)
    b = np.zeros((alto, ancho, 8), np.float32)
    b[:] = [1500, 1700, 2000, 2300, 3000, 2600, 5, 2300]                # suelo común
    b[:, :20] = [400, 700, 500, 4000, 1800, 900, 4, 3900]                # vegetación
    b[:, 20:40] = [2400, 2600, 2700, 1900, 5200, 5300, 5, 5200]          # roca clara, desnuda, sin hierro ni arcilla
    b[:, 60:, 2] = 3600; b[:, 60:, 7] = 1500                             # ferruginoso
    b[..., :6] *= rng.normal(1, 0.004, (alto, ancho, 6))
    b[..., 7] *= rng.normal(1, 0.004, (alto, ancho))
    zona = {"id": "z", "clase": "A", "geometria": {"type": "Polygon", "coordinates": [anillo]}}
    # NDVI y BSI con los cortes por defecto; ferruginosa y arcilla más permisivos (el percentil de la ferruginosa
    # incluye la vegetación, que en esta imagen sintética ocupa las clases más bajas)
    r = sentinel_silice.calcular(b, anillo, [zona], bbox, (ancho, alto), cortes={"p_ferruginosa": 0.7, "arcilla": 0.6})
    a = np.asarray(Image.open(BytesIO(b64.b64decode(r["capas"]["silice_limpia"].split(",")[1]))).convert("RGBA"))[..., 3] > 0
    assert a[:, 22:38].mean() > 0.6                    # la roca clara y desnuda pasa los cuatro filtros
    assert not a[:, :18].any() and not a[:, 62:].any()  # ni la vegetación ni lo ferruginoso
    assert r["celda"]["pct_cumple"] == r["celda"]["pct_silice_limpia"]
    # el BSI ya no entra: un corte de BSI se ignora
    r2 = sentinel_silice.calcular(b, anillo, [zona], bbox, (ancho, alto), cortes={"p_ferruginosa": 0.7, "arcilla": 0.6, "p_bsi": 0.99})
    assert r2["celda"]["pct_cumple"] == r["celda"]["pct_cumple"] and "p_bsi" not in r2["cortes"]
    assert {"ndvi", "bsi"} <= set(r["datos"]["hist"]) and r["datos"]["formato"] == 4


def test_aptitud_vidrio_por_descripcion():
    """24/11/2026: la descripción ordena para vidrio; las rocas finas intercaladas (limoarcillitas, lutitas) malogran."""
    import vidrio_desc as v
    limpia = v.aptitud("Areniscas cuarzosas blancas de grano grueso, estratos de 1 a 2 m.")
    mezclada = v.aptitud("Areniscas cuarzosas gris blanquecinas de grano medio a grueso intercaladas con limoarcillitas pardo amarillentas.")
    principal_mala = v.aptitud("Lutitas negras bituminosas con niveles de areniscas cuarzosas de grano fino a medio en estratos delgados")
    clastos = v.aptitud("Conglomerados con clasto de areniscas cuarzosas intercalados con areniscas rojizas de grano fino y lodolitas.")
    assert limpia["nivel"] == "alta" and limpia["estratos"][0]["tipo"] == "potente"
    assert mezclada["nivel"] == "media" and "limoarcillitas pardo amarillentas" in mezclada["en_contra"]
    assert principal_mala["nivel"] in ("baja", "no") and principal_mala["estratos"][0]["tipo"] == "delgado"
    assert clastos["nivel"] == "no"
    assert v.aptitud("Areniscas cuarzosas blanquecino a rosácea de grano medio")["puntaje"] < v.aptitud("Areniscas cuarzosas blanquecinas de grano medio")["puntaje"]


def test_informe_unidades_elegidas():
    """24/11/2026: página del informe con el análisis bibliográfico de las unidades elegidas para la Prioridad libre."""
    import informe
    celda = {"codigo": "15f2-NO", "sur": -7.25, "norte": -7.125, "oeste": -78.875, "este": -78.75}
    uds = [{"nombre": "Grupo Goyllarisquizga - Formación Farrat", "clase": "B", "ha": 7178,
            "descripciones": [{"texto": "Areniscas cuarzosas gris blanquecinas de grano medio a grueso intercaladas con limoarcillitas pardo amarillentas.",
                               "litologia": "Arenisca cuarzosa", "roca": "Arenisca cuarzosa", "ha": 7178}],
            "libre": 60, "negociable": 18, "pasa": 7.0}]
    png = informe.unidades({"tipo": "unidades", "celda": celda, "unidades": uds, "lamina": "01", "total": "01"})
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 50000
    assert TestClient(app).post("/lamina", json={"tipo": "unidades", "celda": celda, "unidades": uds}).status_code == 200
