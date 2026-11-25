"""Vigilancia del catastro minero de INGEMMET sobre las áreas que le interesan al usuario (cuadrículas 1:25 000
guardadas o las cuadrículas de 100 ha de un expediente de petitorio).

Cada revisión toma una «foto» del catastro dentro del área (derechos de las capas 0 y 1 de
SERV_CATASTRO_MINERO_WGS84 y avisos de SERV_LIBREDENUNCIABILIDAD) y la compara con la foto anterior que
guarda la app. El servidor no guarda nada: la app manda la foto previa y recibe la nueva + las alertas.

Alertas:
  · nuevo       — apareció un derecho minero (petitorio nuevo) que no estaba     → ALTA si toca un petitorio propio
  · estado      — cambió su estado (trámite → titulado, titulado → extinguido…)  → media
  · desaparecio — ya no figura en el catastro: el área pudo quedar libre          → media (verificar)
  · ld          — se publicó como de LIBRE DENUNCIABILIDAD (se podrá pedir)        → alta (oportunidad)
  · ocupado     — el % del área ocupado por derechos vigentes cambió ≥ 5 puntos
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from shapely.ops import unary_union

import geocatmin_rmi as g

CATASTRO = "SERV_CATASTRO_MINERO_WGS84"
CAPAS = (0, 1)
LD = ("SERV_LIBREDENUNCIABILIDAD", 0)
VIGENTES = {"TITULADO", "TRAMITE", "OTROS", "BLOQUEADO", "CONSENTIDO"}


def _txt(v) -> str:
    return str(v or "").strip()


def foto(anillo: list) -> dict:
    """Estado actual del catastro dentro del área (sin fichas pesadas: solo lo que se compara)."""
    pol = g.validar_poligono(anillo)
    esri = g._anillo_esri(pol)
    area = max(g.area_ha(pol), 1e-9)

    def capa(lid):
        return g.query_en_poligono(CATASTRO, lid, esri, "*", timeout=40)

    def ld():
        try:
            return g.query_en_poligono(LD[0], LD[1], esri, "*", timeout=40)
        except Exception:  # noqa: BLE001  (si el servicio de LD falla, se sigue sin él)
            return None

    with ThreadPoolExecutor(3) as ex:
        f_ld = ex.submit(ld)
        feats = [f for r in ex.map(capa, CAPAS) for f in r]
        feats_ld = f_ld.result()
    derechos: dict[str, dict] = {}
    vigentes = []
    for f in feats:
        a = f.get("attributes") or {}
        cod = _txt(a.get("CODIGOU"))
        if not cod or cod in derechos:
            continue
        geom = g.esri_a_shapely(f.get("geometry"), recorte=pol)
        inter = g._limpiar(geom.intersection(pol)) if geom is not None else None
        if inter is None or inter.is_empty:
            continue
        leyenda = _txt(a.get("LEYENDA")).upper()
        fec = a.get("FEC_DENU")
        derechos[cod] = {
            "nombre": _txt(a.get("CONCESION")), "titular": _txt(a.get("TIT_CONCES")),
            "leyenda": leyenda, "estado": _txt(a.get("D_ESTADO")) or leyenda.lower(),
            "sustancia": _txt(a.get("SUSTANCIA")), "ha_total": a.get("HECTAGIS"),
            "ha_dentro": round(g.area_ha(inter), 1),
            "petitorio": datetime.fromtimestamp(fec / 1000, tz=timezone.utc).date().isoformat() if isinstance(fec, (int, float)) else None,
        }
        if leyenda in VIGENTES:
            vigentes.append(inter)
    ocupado = g._limpiar(unary_union(vigentes)) if vigentes else None
    ld_cods = sorted({_txt((x.get("attributes") or {}).get("CODIGOU")) for x in feats_ld or []} - {""}) if feats_ld is not None else None
    return {"fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"), "derechos": derechos,
            "ocupado_pct": round(100 * g.area_ha(ocupado) / area, 1) if ocupado is not None and not ocupado.is_empty else 0.0,
            "ld": ld_cods}


def comparar(previo: dict | None, actual: dict, propio: bool = False) -> list[dict]:
    """Alertas entre dos fotos. `propio` = el área es un petitorio del usuario (lo nuevo encima es ALTA)."""
    if not previo:
        n = len(actual["derechos"])
        return [{"tipo": "base", "nivel": "info", "texto": f"Línea base registrada: {n} derecho(s) minero(s) en el área, "
                 f"{actual['ocupado_pct']} % ocupado por derechos vigentes."}]
    alertas = []
    antes, ahora = previo.get("derechos", {}), actual["derechos"]
    for cod, d in ahora.items():
        if cod not in antes:
            alertas.append({"tipo": "nuevo", "nivel": "alta" if propio or d["leyenda"] in VIGENTES else "media", "codigo": cod,
                            "texto": f"Nuevo derecho minero «{d['nombre']}» ({cod}), {d['estado']}, titular {d['titular'] or '—'}: "
                                     f"{d['ha_dentro']} ha dentro del área" + (f" · petitorio del {d['petitorio']}" if d.get("petitorio") else "") + "."})
        elif antes[cod].get("leyenda") != d["leyenda"]:
            alertas.append({"tipo": "estado", "nivel": "alta" if d["leyenda"] == "EXTINGUIDO" else "media", "codigo": cod,
                            "texto": f"«{d['nombre']}» ({cod}) cambió de {antes[cod].get('estado') or antes[cod].get('leyenda')} a {d['estado']}."
                                     + (" Ya no tiene titular: atento a la publicación de su libre denunciabilidad." if d["leyenda"] == "EXTINGUIDO" else "")})
    for cod, d in antes.items():
        if cod not in ahora:
            alertas.append({"tipo": "desaparecio", "nivel": "media", "codigo": cod,
                            "texto": f"«{d.get('nombre')}» ({cod}) ya no figura en el catastro dentro del área: puede haber quedado libre (verificar en INGEMMET)."})
    if actual.get("ld") is not None and previo.get("ld") is not None:
        for cod in sorted(set(actual["ld"]) - set(previo["ld"])):
            nom = ahora.get(cod, antes.get(cod, {})).get("nombre", "")
            alertas.append({"tipo": "ld", "nivel": "alta", "codigo": cod,
                            "texto": f"Publicado como de LIBRE DENUNCIABILIDAD: {nom or cod} ({cod}). Revisa la fecha desde la que se podrá pedir."})
    dif = actual["ocupado_pct"] - (previo.get("ocupado_pct") or 0)
    if abs(dif) >= 5:
        alertas.append({"tipo": "ocupado", "nivel": "media",
                        "texto": f"El área ocupada por derechos vigentes pasó de {previo.get('ocupado_pct')} % a {actual['ocupado_pct']} %."})
    return alertas


def revisar(items: list[dict]) -> list[dict]:
    """items: [{id, anillo, previo?, propio?}] → [{id, ok, foto, alertas} | {id, ok: False, error}]."""
    def una(it):
        try:
            f = foto(it["anillo"])
            return {"id": it["id"], "ok": True, "foto": f, "alertas": comparar(it.get("previo"), f, bool(it.get("propio")))}
        except Exception as e:  # noqa: BLE001
            return {"id": it["id"], "ok": False, "error": f"{type(e).__name__}: {str(e)[:140]}"}
    with ThreadPoolExecutor(3) as ex:
        return list(ex.map(una, items))
