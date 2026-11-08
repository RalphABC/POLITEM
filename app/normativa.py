"""Orientación normativa por tipo de novedad: usa la misma base vectorial que los reportes (parte «R» de RAG)."""
from __future__ import annotations

from typing import Dict, List

from .rag.indexador import indice

CONSULTAS = {
    "faltante": "bien no ubicado durante la constatación física procedimiento verificación custodio investigación reposición baja",
    "mal_estado": "bien en estado malo diagnóstico técnico reparación baja informe técnico",
    "sobrante": "bien no registrado en el inventario ingreso acta de entrega-recepción",
    "ubicacion_distinta": "cambio de custodio entrega mediante acta bienes ubicación traspaso",
    "sin_etiqueta": "custodio responsable conservación registros actualizados informar novedades",
    "otro": "constatación física verificación existencia ubicación custodio",
}


def orientar(tipo: str, k: int = 1) -> List[Dict]:
    idx = indice()
    idx.asegurar()
    vec = idx.embedder.embed([CONSULTAS.get(tipo, CONSULTAS["otro"])])[0]
    return [{"fuente": "normativa de apoyo", "titulo": h["meta"]["codigo"], "texto": h["texto"].split(". ", 1)[-1], "similitud": round(h["sim"], 3)}
            for h in idx.store.query(vec, k, {"tipo": "norma"})]
