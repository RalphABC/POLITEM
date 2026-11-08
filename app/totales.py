"""Cálculo determinista de totales (el sistema calcula; el modelo solo redacta)."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Dict, List

RE_CRIT = re.compile(r"baja|no ubicad|reparaci|extravi|robo|p[eé]rdida", re.I)


def dinero(v: float) -> str:
    return "$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def es_critico(b: Dict) -> bool:
    return (b.get("estado") or "").strip().lower() == "malo" or bool(RE_CRIT.search(b.get("condicion") or ""))


def totalmente_depreciado(b: Dict) -> bool:
    vc = b.get("valor_contable") or 0
    return vc > 0 and (b.get("valor_libros") or 0) <= vc * 0.10 + 0.01


def calcular(bienes: List[Dict]) -> Dict:
    vc = round(sum(b["valor_contable"] or 0 for b in bienes), 2)
    da = round(sum(b["dep_acum"] or 0 for b in bienes), 2)
    vl = round(sum(b["valor_libros"] or 0 for b in bienes), 2)
    por_estado = Counter((b["estado"] or "Sin dato") for b in bienes)
    tipo, ubic, cust = defaultdict(lambda: [0, 0.0]), Counter(), Counter()
    for b in bienes:
        t = tipo[b["tipo_bien"] or b["descripcion"] or "Otros"]
        t[0] += 1
        t[1] += b["valor_contable"] or 0
        ubic[b["ubicacion"]] += 1
        cust[b["custodio_nombre"]] += 1
    crit = [b["codigo"] for b in bienes if es_critico(b)]
    return {
        "total": len(bienes), "valor_contable": vc, "dep_acum": da, "valor_libros": vl,
        "por_estado": dict(por_estado), "por_ubicacion": dict(ubic), "por_custodio": dict(cust),
        "por_tipo": {k: {"n": v[0], "valor": round(v[1], 2)} for k, v in sorted(tipo.items(), key=lambda kv: -kv[1][1])[:8]},
        "criticos": crit, "n_criticos": len(crit),
        "totalmente_depreciados": sum(1 for b in bienes if totalmente_depreciado(b)),
    }
