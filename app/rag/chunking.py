"""Carga y segmentación (chunking): cada bien y cada sección de normativa se convierten en un fragmento con metadatos."""
from __future__ import annotations

import re
from typing import Dict, List

from ..config import get_settings
from ..totales import dinero, es_critico, totalmente_depreciado


def bien_a_texto(b: Dict) -> str:
    """Texto del bien SIN el nombre del custodio (los datos personales quedan solo en metadatos/BD)."""
    p = [f"Bien {b['codigo']}: {b['descripcion']}"]
    if b.get("marca") or b.get("modelo"):
        p[0] += f" ({' '.join(x for x in (b.get('marca'), b.get('modelo')) if x)})"
    if b.get("serie"):
        p.append(f"Serie {b['serie']}.")
    p.append(f"Estado {b.get('estado') or 'sin dato'}" + (f", condición {b['condicion']}" if b.get("condicion") else "") + ".")
    p.append(f"Ubicación: {b['ubicacion']}.")
    p.append(f"Valor contable {dinero(b['valor_contable'])}, depreciación acumulada {dinero(b['dep_acum'])}, valor en libros {dinero(b['valor_libros'])}.")
    if b.get("vida_util"):
        p.append(f"Vida útil {b['vida_util']:g} años.")
    if b.get("fecha_ingreso"):
        p.append(f"Ingresó el {b['fecha_ingreso']}.")
    if es_critico(b):
        p.append("Bien crítico.")
    if totalmente_depreciado(b):
        p.append("Totalmente depreciado.")
    return " ".join(p)


def chunks_bienes(corte_id: int, bienes: List[Dict]):
    ids, textos, metas = [], [], []
    for b in bienes:
        ids.append(f"b{corte_id}:{b['codigo']}")
        textos.append(bien_a_texto(b))
        metas.append({"tipo": "bien", "corte_id": corte_id, "codigo": b["codigo"], "cedula": b.get("custodio_id") or "",
                      "ubicacion": b["ubicacion"], "estado": b.get("estado") or "", "critico": int(es_critico(b))})
    return ids, textos, metas


def chunks_normativa():
    ids, textos, metas = [], [], []
    for f in sorted(get_settings().normativa_dir.glob("*.md")):
        for n, sec in enumerate(re.split(r"\n(?=## )", f.read_text(encoding="utf-8"))):
            if sec.startswith("## "):
                titulo, _, cuerpo = sec.partition("\n")
                ids.append(f"n:{f.stem}:{n}")
                textos.append(f"{titulo[3:].strip()}. {cuerpo.strip()}")
                metas.append({"tipo": "norma", "corte_id": 0, "codigo": titulo[3:].strip(), "cedula": "", "ubicacion": "", "estado": "", "critico": 0})
    return ids, textos, metas
