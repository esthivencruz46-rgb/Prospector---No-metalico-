"""Catálogo de materiales (rocas y minerales industriales) que la app sabe
buscar. Cada material define:

- `rmi`: capas del inventario de Rocas y Minerales Industriales de INGEMMET
  (servicio SERV_ROCAS_MINERALES_INDUSTRIALES) con canteras/ocurrencias
  ya registradas. Se buscan por NOMBRE de capa (el id es solo respaldo).
- `litologia`: reglas para reconocer, en la geología 50K/100K, las unidades
  que pueden contener el material. Cada regla da una clase:
    A = la litología lo dice explícito (p. ej. "cuarcita", "arenisca cuarzosa")
    B = formación conocida como fuente del material (criterio estratigráfico)
    C = litología compatible pero a verificar en campo
- `excluir`: términos que descartan un polígono aunque coincida (p. ej.
  intrusivos con "cuarzo" en el nombre: cuarzomonzonita, diorita cuarcífera).

Hoy solo `arena_silicea` está activa; las demás quedan listadas como
"próximamente" para el buscador y se activan agregando sus reglas aquí.
"""

import re

MATERIALES = {
    "arena_silicea": {
        "nombre": "Arena silícea",
        "activo": True,
        "sinonimos": ["arena silicea", "silice", "sílice", "cuarzo", "cuarcita",
                      "arenisca cuarzosa", "vidrio"],
        "rmi": [("Arena Silícea", 9), ("Sílice", 43)],
        "litologia": [
            ("A", "Cuarcita / ortocuarcita",
             r"\b(ORTO)?CUARCITA|CUARZOARENIT|CUARZO ?ARENIT"),
            ("A", "Arenisca cuarcítica",
             r"ARENISCAS? CUARC[IÍ]TICAS?"),
            ("A", "Arenisca cuarzosa",
             r"ARENISCAS?( DE GRANO \w+)?( Y \w+)?( BLANCAS?| GRISES?| BLANQUECINAS?)? CUARZOSAS?"),
            ("A", "Arena silícea / sílice",
             r"ARENAS? SIL[IÍ]CEAS?|\bS[IÍ]LICE\b"),
            # «arenas cuarzosas», pero también con palabras en medio dentro de la misma frase:
            # «arenas eólicas, cuarzosas de color blanco», «arenas de cuarzosas…», «arena media bien
            # seleccionada y de composición cuarzosa» (depósitos eólicos de la 50K)
            ("A", "Arena cuarzosa",
             r"\bARENAS?\b[^.;]{0,70}?\bCUARZOS[AO]S?\b"),
            # Goyllarisquizga solo SIN DIVIDIR: el grupo incluye las Fms. Santa (calizas) y
            # Carhuaz (lutitas). Huancané solo como formación (no el "Centro Volcánico Huancane").
            ("B", "Formación cuarzosa conocida",
             r"MARCAVILCA|HERRADURA|SALTO DEL FRAILE|MORRO SOLAR|CHIM[UÚ]\b|FARRAT|"
             r"GOYLLARISQUI[SZ]GA(?!.*(SANTA|CARHUAZ|PARIAHUANCA|CHULEC|PARIATAMBO))|"
             r"HUALHUANI|CUSHABATAY|AGUA CALIENTE|FORMACI[OÓ]N HUANCAN[EÉ]"),
            ("C", "Arenisca (verificar contenido de cuarzo)",
             r"\bARENISCAS?\b"),
            ("C", "Depósito eólico / arena (verificar)",
             r"E[OÓ]LIC|\bDUNAS?\b"),
        ],
        "excluir": (
            r"MONZON|DIORIT|GRANIT|GRANODIOR|TONALIT|P[OÓ]RFID|ANDESIT|DACIT|RIOLIT|"
            r"BASALT|TOBA|TOB[AÁ]CE|VOLC[AÁ]N|IGNIMBR|ARC[OÓ]SIC|ARCOSA|GRAUVAC|"
            r"VOLCANOCL|LAVA|BRECHA VOLC"
        ),
    },
    # Las demás materias primas las crea el usuario en la app (editor «🧪 Materias primas»):
    # materias_primas.py las agrega aquí y en FORMACIONES al arrancar y al guardarlas.
}

_ORDEN_CLASE = {"A": 0, "B": 1, "C": 2}


def _like(campos: list[str], terminos: list[str]) -> str:
    return "(" + " OR ".join(f"UPPER({c}) LIKE '%{t}%'" for c in campos for t in terminos) + ")"


def _sql(campos: list[str], si: list[str], no: list[str] | None = None) -> str:
    """Filtro SQL (layerDefs / where) para GEOCATMIN."""
    s = _like(campos, si)
    return f"{s} AND NOT {_like(campos, no)}" if no else s


# Catálogo para "Formaciones y depósitos": el usuario elige uno y el mapa
# muestra solo esos polígonos (filtro en el servidor de GEOCATMIN).
# - `patron`: regex (texto normalizado UNIDAD | LITOLOGIA/DESCRIP) para
#   marcar los afloramientos de una búsqueda que pertenecen a este ítem.
# - `sql50` / `sql100`: filtros de las capas 50K (capa 7) y 100K (capa 6).
#   La 100K NO trae nombres de formación (NAME = código, p. ej. "Q-eo"), por
#   eso las formaciones solo filtran la 50K (verificado en GEOCATMIN).
_U50 = ["UNIDAD"]
_L50 = ["LITOLOGIA", "DESCRIP"]
FORMACIONES = {
    "arena_silicea": [
        {"id": "chimu", "nombre": "Formación Chimú", "tipo": "Formación", "edad": "Cretácico inferior",
         "region": "Norte y centro: Cajamarca, La Libertad, Áncash, Huánuco",
         "descripcion": "Ortocuarcitas y areniscas cuarzosas blancas en bancos gruesos, con mantos de carbón. "
                        "Una de las fuentes de sílice más conocidas del país.",
         "patron": r"CHIM[UÚ]\b", "sql50": _sql(_U50, ["CHIMU", "CHIMÚ"]), "sql100": None},
        {"id": "farrat", "nombre": "Formación Farrat", "tipo": "Formación", "edad": "Cretácico inferior",
         "region": "Norte y centro",
         "descripcion": "Areniscas cuarzosas blancas de grano medio a grueso, sobre las Fms. Santa y Carhuaz.",
         "patron": r"FARRAT", "sql50": _sql(_U50, ["FARRAT"]), "sql100": None},
        {"id": "goyllarisquizga", "nombre": "Grupo Goyllarisquizga (sin dividir)", "tipo": "Grupo",
         "edad": "Cretácico inferior", "region": "Centro: Pasco, Junín, Huánuco, Lima",
         "descripcion": "Areniscas cuarzosas y cuarcitas; equivale a Chimú–Santa–Carhuaz–Farrat donde no se separaron. "
                        "Se excluyen las partes ya separadas como Fm. Santa (calizas) o Carhuaz (lutitas).",
         "patron": r"GOYLLARISQUI[SZ]GA(?!.*(SANTA|CARHUAZ|CHIM|FARRAT|PARIAHUANCA|CHULEC|PARIATAMBO))",
         "sql50": _sql(_U50, ["GOYLLARISQUI"], ["SANTA", "CARHUAZ", "CHIM", "FARRAT", "PARIAHUANCA", "CHULEC", "PARIATAMBO"]),
         "sql100": None},
        {"id": "marcavilca", "nombre": "Formación Marcavilca (Gr. Morro Solar)", "tipo": "Formación",
         "edad": "Cretácico inferior", "region": "Costa de Lima: Morro Solar, Lurín, Chilca, Mala, Cañete",
         "descripcion": "Areniscas cuarzosas y cuarcitas blancas. La formación silícea más cercana a Cañete.",
         "patron": r"MARCAVILCA", "sql50": _sql(_U50, ["MARCAVILCA"]), "sql100": None},
        {"id": "salto_fraile", "nombre": "Formación Salto del Fraile (Gr. Morro Solar)", "tipo": "Formación",
         "edad": "Cretácico inferior", "region": "Costa de Lima",
         "descripcion": "Cuarcitas y areniscas cuarzosas; base del Grupo Morro Solar.",
         "patron": r"SALTO DEL FRAILE", "sql50": _sql(_U50, ["SALTO DEL FRAILE"]), "sql100": None},
        {"id": "herradura", "nombre": "Formación Herradura (Gr. Morro Solar)", "tipo": "Formación",
         "edad": "Cretácico inferior", "region": "Costa de Lima",
         "descripcion": "Mayormente lutitas, con niveles de cuarcitas: menos favorable, solo los niveles cuarcíticos.",
         "patron": r"HERRADURA", "sql50": _sql(_U50, ["HERRADURA"]), "sql100": None},
        {"id": "hualhuani", "nombre": "Formación Hualhuani (Gr. Yura)", "tipo": "Formación",
         "edad": "Cretácico inferior", "region": "Sur: Arequipa, Moquegua, Tacna, Puno",
         "descripcion": "Cuarcitas blancas masivas; la principal formación silícea del sur.",
         "patron": r"HUALHUANI", "sql50": _sql(_U50, ["HUALHUANI"]), "sql100": None},
        {"id": "huancane", "nombre": "Formación Huancané", "tipo": "Formación", "edad": "Cretácico inferior",
         "region": "Altiplano: Puno",
         "descripcion": "Areniscas cuarzosas blancas a rojizas. (No confundir con el Centro Volcánico Huancané.)",
         "patron": r"FORMACI[OÓ]N HUANCAN[EÉ]",
         "sql50": _sql(_U50, ["FORMACIÓN HUANCAN", "FORMACION HUANCAN"]), "sql100": None},
        {"id": "cushabatay", "nombre": "Formación Cushabatay (Gr. Oriente)", "tipo": "Formación",
         "edad": "Cretácico inferior", "region": "Oriente: San Martín, Loreto, Ucayali, Huánuco",
         "descripcion": "Areniscas cuarzosas blancas de grano medio a grueso.",
         "patron": r"CUSHABATAY", "sql50": _sql(_U50, ["CUSHABATAY"]), "sql100": None},
        {"id": "agua_caliente", "nombre": "Formación Agua Caliente (Gr. Oriente)", "tipo": "Formación",
         "edad": "Cretácico", "region": "Oriente",
         "descripcion": "Areniscas cuarzosas blancas a grises.",
         "patron": r"AGUA CALIENTE", "sql50": _sql(_U50, ["AGUA CALIENTE"]), "sql100": None},
        {"id": "cuarcitas", "nombre": "Cuarcitas / ortocuarcitas (cualquier unidad)", "tipo": "Roca",
         "edad": "", "region": "Todo el Perú",
         "descripcion": "Polígonos cuya litología nombra cuarcita, arenisca cuarcítica u ortocuarcita.",
         "patron": r"\b(ORTO)?CUARCITA|CUARZOARENIT|CUARC[IÍ]TIC",
         "sql50": _sql(_L50, ["CUARCIT", "CUARCÍT", "CUARZOARENIT"]),
         "sql100": _sql(["DESCRIP"], ["CUARCIT", "CUARCÍT", "CUARZOARENIT"])},
        {"id": "areniscas_cuarzosas", "nombre": "Areniscas cuarzosas (cualquier unidad)", "tipo": "Roca",
         "edad": "", "region": "Todo el Perú",
         "descripcion": "Polígonos cuya litología nombra arenisca cuarzosa.",
         "patron": r"ARENISCAS? CUARZOSAS?",
         "sql50": _sql(_L50, ["ARENISCA CUARZOSA", "ARENISCAS CUARZOSAS"]),
         "sql100": _sql(["DESCRIP"], ["ARENISCA CUARZOSA", "ARENISCAS CUARZOSAS"])},
        {"id": "arenas_cuarzosas", "nombre": "Arenas cuarzosas / silíceas", "tipo": "Depósito",
         "edad": "Cuaternario", "region": "Todo el Perú",
         "descripcion": "Depósitos de arena descritos como cuarzosa o silícea (sin consolidar: más fáciles de extraer).",
         "patron": r"\bARENAS? (CUARZOSAS?|SIL[IÍ]CEAS?)",
         "sql50": _sql(_L50, ["ARENA CUARZOSA", "ARENAS CUARZOSAS", "ARENA%CUARZOS", "ARENA SIL", "ARENAS SIL"]),
         "sql100": _sql(["DESCRIP"], ["ARENA CUARZOSA", "ARENAS CUARZOSAS", "ARENA%CUARZOS", "ARENA SIL", "ARENAS SIL"])},
        {"id": "eolicos", "nombre": "Depósitos eólicos (dunas, mantos de arena)", "tipo": "Depósito",
         "edad": "Cuaternario", "region": "Costa, sobre todo",
         "descripcion": "Arenas de viento. Pueden ser cuarzosas o feldespáticas: verificar en campo y laboratorio.",
         "patron": r"E[OÓ]LIC|\bDUNAS?\b",
         "sql50": _sql(_U50, ["EÓLIC", "EOLIC"]),
         "sql100": "(UPPER(NAME) LIKE 'Q-EO%' OR UPPER(DESCRIP) LIKE '%EÓLIC%' OR UPPER(DESCRIP) LIKE '% DUNA%')"},
    ],
}


_TILDE = {"A": "Á", "E": "É", "I": "Í", "O": "Ó", "U": "Ú"}
_SIN_TILDE = str.maketrans("ÁÉÍÓÚÜ", "AEIOUU")
_VACIAS = {"DE", "DEL", "LA", "LAS", "EL", "LOS", "Y", "CON", "EN"}


def palabras_busqueda(texto: str) -> list[str]:
    """Palabras útiles del texto libre, en mayúsculas y sin tildes (máx. 4)."""
    t = re.sub(r"[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9 ]", " ", str(texto or "")).upper().translate(_SIN_TILDE)
    return [w for w in t.split() if len(w) >= 3 and w not in _VACIAS][:4]


def variantes_tilde(palabra: str) -> list[str]:
    """CHIMU → [CHIMU, CHÍMU, CHIMÚ]: en GEOCATMIN los nombres llevan tilde
    (Chimú, Formación, silícea) y el usuario puede escribir sin ella. Se
    prueba la palabra sin tilde y con UNA tilde en cada vocal."""
    out = [palabra]
    for i, ch in enumerate(palabra):
        if ch in _TILDE:
            out.append(palabra[:i] + _TILDE[ch] + palabra[i + 1:])
    return out


def sql_texto(texto: str, campos: list[str]) -> str | None:
    """Filtro SQL para buscar texto libre en la geología: TODAS las palabras
    deben aparecer (en cualquiera de los campos), sin importar las tildes.
    Mismo algoritmo que `sqlTexto()` en frontend/src/geo.ts."""
    palabras = palabras_busqueda(texto)
    if not palabras:
        return None
    partes = []
    for w in palabras:
        ors = [f"UPPER({c}) LIKE '%{v}%'" for c in campos for v in variantes_tilde(w)]
        partes.append("(" + " OR ".join(ors) + ")")
    return " AND ".join(partes)


CAMPOS_TEXTO_50K = ["UNIDAD", "LITOLOGIA", "DESCRIP"]
CAMPOS_TEXTO_100K = ["UNIDAD", "DESCRIP"]

# INGEMMET no escribe "arena silícea" en sus mapas geológicos (0 polígonos,
# verificado): esa búsqueda se traduce a todas las unidades silíceas, el
# mismo filtro de la capa «Geología: solo unidades silíceas» (Mapa.tsx).
_TERMINOS_SILICE = ["ARENISCA CUARZOSA", "ARENISCAS CUARZOSAS", "ARENA CUARZOSA", "ARENAS CUARZOSAS", "ARENA%CUARZOS",
                    "CUARCIT", "CUARCÍT", "CUARZOARENIT", "ARENA SIL", "ARENAS SIL"]
_SINONIMOS_SILICE = {"ARENA SILICEA", "ARENAS SILICEAS", "SILICE", "SILICEA", "ARENA DE SILICE",
                     "SILICE INDUSTRIAL", "ARENA PARA VIDRIO"}


def filtro_texto(texto: str) -> dict | None:
    """Convierte lo que el usuario escribe en un filtro de mapa:
    {id, nombre, tipo, descripcion, nota, palabras, sql50, sql100}."""
    clave = " ".join(re.sub(r"[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9 ]", " ", str(texto or "")).upper()
                     .translate(_SIN_TILDE).split())
    if clave in _SINONIMOS_SILICE:
        return {
            "id": "texto:SILICE", "nombre": "Todas las unidades silíceas", "tipo": "Búsqueda",
            "edad": "", "region": "Todo el Perú",
            "descripcion": "Cuarcita, arenisca cuarzosa, arena cuarzosa o silícea en cualquier unidad.",
            "nota": "INGEMMET no usa el término «arena silícea» en sus mapas geológicos: "
                    "se muestran todas las unidades silíceas.",
            "palabras": [],
            "sql50": _sql(["LITOLOGIA", "DESCRIP"], _TERMINOS_SILICE),
            "sql100": _sql(["DESCRIP"], _TERMINOS_SILICE),
        }
    palabras = palabras_busqueda(texto)
    if not palabras:
        return None
    return {
        "id": f"texto:{' '.join(palabras)}", "nombre": f"«{' '.join(str(texto).split())}»", "tipo": "Búsqueda",
        "edad": "", "region": "Todo el Perú",
        "descripcion": "Polígonos cuya unidad, litología o descripción contiene: " + ", ".join(palabras).lower()
                       + " (sin importar tildes).",
        "nota": "",
        "palabras": palabras,
        "sql50": sql_texto(texto, CAMPOS_TEXTO_50K),
        "sql100": sql_texto(texto, CAMPOS_TEXTO_100K),
    }


def formaciones_publicas(material: str) -> list[dict]:
    return [{k: v for k, v in f.items() if k != "patron"} for f in FORMACIONES.get(material, [])]


def formaciones_de(material: str, textos: dict) -> list[str]:
    """Ids del catálogo a los que pertenece un polígono (para filtrar resultados)."""
    unidad = normalizar(textos.get("UNIDAD"))
    lito = normalizar(" ".join(str(textos.get(k) or "") for k in ("LITOLOGIA", "DESCRIP", "NAME")))
    objetivo = unidad + " | " + lito
    return [f["id"] for f in FORMACIONES.get(material, []) if re.search(f["patron"], objetivo)]


def lista_publica() -> list[dict]:
    """Materias primas para la app, con el filtro SQL de «sus» unidades para el mapa."""
    return [
        {"id": k, "nombre": v["nombre"], "activo": v["activo"], "sinonimos": v.get("sinonimos", []),
         "usuario": bool(v.get("usuario")),
         "sql50": v.get("sql50") or _sql(["LITOLOGIA", "DESCRIP"], _TERMINOS_SILICE),
         "sql100": v.get("sql100") or _sql(["DESCRIP"], _TERMINOS_SILICE)}
        for k, v in MATERIALES.items()
    ]


def normalizar(texto) -> str:
    """Mayúsculas y espacios simples (las tildes se conservan: los patrones
    ya aceptan ambas variantes)."""
    return re.sub(r"\s+", " ", str(texto or "")).upper().strip()


_ROCAS_NO_CUARZOSAS = (r"LUTITA|LIMOLITA|LIMOARCILLITA|ARCILLITA|CALIZA|MARGA|DOLOM|PIZARRA|"
                        r"FILITA|ESQUISTO|CONGLOMERADO|YESO|CARB[OÓ]N")


_SIN_DATO = {"", "<NULL>", "NULL", "-"}
_ROCA_CUARZOSA = r"CUARC|CUARZ|ARENISC|\bARENAS?\b|S[IÍ]LICE"


_MOTIVOS_ROCA = r"CUARCITA|ARENISCA"   # motivos de roca consolidada: clase B (no depósito)


def _roca_dominante(textos: dict) -> str | None:
    """LITO1 de la 50K: la roca dominante del polígono según INGEMMET
    (la 100K no tiene ese campo → None)."""
    l1 = normalizar(textos.get("LITO1"))
    return None if l1 in _SIN_DATO else l1


def _subordinado(lito: str, patron: str, rocas_no: str = _ROCAS_NO_CUARZOSAS) -> bool:
    """True si la litología EMPIEZA por otra roca y la de interés aparece
    después (\"lutitas con niveles de cuarcitas\"): la roca dominante es la
    primera que se nombra en las descripciones de INGEMMET."""
    m_cuarzo = re.search(patron, lito)
    m_otra = re.search(rocas_no, lito)
    return bool(m_cuarzo and m_otra and m_otra.start() < m_cuarzo.start())


def clasificar(material: str, textos: dict) -> tuple[str, str] | None:
    """Devuelve (clase, motivo) si el polígono es favorable para el
    material, o None. `textos`: {"UNIDAD", "LITOLOGIA", "DESCRIP", "NAME",
    "LITO1".."LITO5"} (los LITO solo existen en la 50K).

    REGLA DEL USUARIO (23/11/2026): decide la DESCRIPCIÓN COMPLETA del polígono (LITOLOGIA + DESCRIP +
    NAME + LITO1–3). Una roca silícea cuenta aunque NO sea la principal («lutitas con niveles de
    cuarcitas» → la cuarcita cuenta). Ya no se rebaja por roca dominante ni por «subordinada».
    - Rocas ígneas/volcánicas (`excluir`): si la roca principal (LITO1) es la silícea, sigue igual con una
      nota; si no, A → C («verificar») y una C se descarta.
    - B (formación conocida): solo si el polígono menciona alguna roca cuarzosa (una "Fm. Santa" de
      calizas no es B)."""
    cfg = MATERIALES.get(material)
    if not cfg or not cfg.get("activo"):
        return None
    lito = normalizar(" ".join(str(textos.get(k) or "") for k in ("LITOLOGIA", "DESCRIP", "NAME", "LITO1", "LITO2", "LITO3")
                               if normalizar(textos.get(k)) not in _SIN_DATO))
    unidad = normalizar(textos.get("UNIDAD"))
    pat_excl = cfg.get("excluir")
    # rocas de interés / que no lo son: las de la sílice o las armadas para una materia prima del usuario
    roca_interes = cfg.get("roca_interes", _ROCA_CUARZOSA)
    rocas_no = cfg.get("rocas_no", _ROCAS_NO_CUARZOSAS)
    motivos_b = cfg.get("motivos_b", _MOTIVOS_ROCA)
    excl = re.search(pat_excl, lito) if pat_excl else None
    dom = _roca_dominante(textos)
    dom_ignea = bool(dom and pat_excl and re.search(pat_excl, dom))

    mejor = None
    for clase, motivo, patron in cfg["litologia"]:
        objetivo = unidad + " | " + lito if clase == "B" else lito
        if not re.search(patron, objetivo):
            continue
        if clase == "B":
            if lito and not re.search(roca_interes, lito):
                # formación conocida, pero ESTE polígono no menciona rocas cuarzosas
                clase, motivo = "C", f"{motivo}, pero este polígono se describe como: {lito.lower()[:60]} (verificar)"
        elif excl:
            # roca ígnea/volcánica mencionada: si la principal (LITO1) es la silícea, solo se anota;
            # si no, una "A" baja a C y una "C" se descarta
            if dom is not None and re.search(roca_interes, dom) and not dom_ignea:
                motivo += " (con rocas ígneas/volcánicas menores)"
            elif clase == "A":
                clase, motivo = "C", motivo + " (con rocas ígneas/volcánicas: verificar)"
            else:
                continue
        if clase in ("A", "C") and dom is not None and not re.search(roca_interes, dom) and not dom_ignea:
            motivo += f" (roca principal: {dom.lower()})"   # informativo: ya NO rebaja la clase
        # Clases del usuario (21/11/2026): A = DEPÓSITOS de arena silícea/cuarzosa; B = ROCAS
        # (arenisca cuarzosa/cuarcítica y cuarcita) y formaciones conocidas. Las rocas pasan por las
        # mismas reglas de rebaje que antes (subordinada, ígnea → C) y solo al final A → B.
        # (Las materias primas del usuario no tienen esa reasignación: motivos_b = None.)
        if motivos_b and clase == "A" and re.match(motivos_b, normalizar(motivo)):
            clase = "B"
        if mejor is None or _ORDEN_CLASE[clase] < _ORDEN_CLASE[mejor[0]]:
            mejor = (clase, motivo)
    return mejor
