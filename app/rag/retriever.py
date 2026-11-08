"""Recuperación híbrida: filtro obligatorio por ámbito (cédula/ubicación) + similitud vectorial + reglas de negocio."""
from __future__ import annotations

import re
from typing import Dict, List

from ..config import get_settings
from ..totales import es_critico, totalmente_depreciado
from .indexador import indice

CONSULTA_TIPO = {
    "totalizado": "resumen del estado de los bienes valor contable depreciación acumulada valor en libros estado bueno regular malo",
    "criticos": "bien en mal estado crítico para baja no ubicado en reparación totalmente depreciado",
}
PESOS = {"semantica": 0.55, "regla": 0.35, "codigo": 0.10}
RE_COD = re.compile(r"[A-Za-z]{2,5}-\d{3,}")


def _regla(b: Dict, tipo: str, maxv: float) -> float:
    r = 1.0 if es_critico(b) else 0.0
    if totalmente_depreciado(b):
        r = max(r, 0.5)
    if tipo == "totalizado":
        r = 0.7 * r + 0.3 * ((b["valor_contable"] or 0) / maxv if maxv else 0)
    return r


def recuperar(corte_id: int, ambito: Dict, bienes: List[Dict], tipo: str, pregunta: str = "") -> Dict:
    """`bienes`: universo del ámbito, ya filtrado y leído de la BD. Devuelve evidencias ordenadas y normativa."""
    s, idx = get_settings(), indice()
    q = pregunta.strip() if tipo == "consulta_libre" and pregunta.strip() else CONSULTA_TIPO.get(tipo, CONSULTA_TIPO["totalizado"])
    vec = idx.embedder.embed([q])[0]
    donde = {"tipo": "bien", "corte_id": corte_id}
    if ambito["tipo"] == "cedula":
        donde["cedula"] = ambito["valor"]
    else:
        donde["ubicacion"] = ambito["valor"]
    por_codigo = {b["codigo"]: b for b in bienes}
    candidatos = idx.store.query(vec, max(len(bienes), 1), donde)
    candidatos = [c for c in candidatos if c["meta"]["codigo"] in por_codigo]
    maxv = max((b["valor_contable"] or 0 for b in bienes), default=0)
    cods_pregunta = {c.upper() for c in RE_COD.findall(pregunta or "")}
    evid = []
    for c in candidatos:
        b = por_codigo[c["meta"]["codigo"]]
        comp = {"semantica": round(max(0.0, c["sim"]), 4), "regla": round(_regla(b, tipo, maxv), 4),
                "codigo": 1.0 if b["codigo"].upper() in cods_pregunta else 0.0}
        score = sum(PESOS[k] * comp[k] for k in PESOS)
        evid.append({"codigo": b["codigo"], "texto": c["texto"], "score": round(score, 4), "componentes": comp, "bien": b})
    evid.sort(key=lambda e: -e["score"])
    limite = s.top_k if tipo == "consulta_libre" else s.contexto_max
    elegidos = evid[:limite]
    criticos = [e for e in evid if es_critico(e["bien"])]
    if tipo != "consulta_libre":                 # los críticos siempre entran al contexto
        vistos = {e["codigo"] for e in elegidos}
        elegidos += [e for e in criticos if e["codigo"] not in vistos][:limite]
    normas = idx.store.query(vec, 3, {"tipo": "norma"}) if tipo != "totalizado" or pregunta else idx.store.query(vec, 2, {"tipo": "norma"})
    return {"bienes": elegidos, "normas": [{"titulo": n["meta"]["codigo"], "texto": n["texto"], "sim": round(n["sim"], 3)} for n in normas],
            "candidatos": len(candidatos)}
