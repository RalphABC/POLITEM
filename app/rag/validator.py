"""Validación de fundamentación: citas existentes, cifras verificadas y críticos mencionados."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, List, Set

from ..esbye import numero

RE_CITA = re.compile(r"\[([^\[\]\s]{3,40})\]")
RE_MONTO = re.compile(r"\$\s?(\d[\d.,]*\d|\d)")


@dataclass
class Validacion:
    estado: str = "APROBADO"
    citas_total: int = 0
    citas_validas: int = 0
    citas_invalidas: List[str] = field(default_factory=list)
    cifras_no_verificadas: List[str] = field(default_factory=list)
    criticos_omitidos: List[str] = field(default_factory=list)
    mensajes: List[str] = field(default_factory=list)

    def dict(self):
        return self.__dict__


def validar(texto: str, codigos_contexto: Set[str], criticos: Iterable[str], montos_permitidos: Iterable[float], tipo: str) -> Validacion:
    v = Validacion()
    citas = [c for c in RE_CITA.findall(texto) if any(ch.isdigit() for ch in c)]
    v.citas_total = len(citas)
    v.citas_validas = sum(1 for c in citas if c in codigos_contexto)
    v.citas_invalidas = sorted({c for c in citas if c not in codigos_contexto})
    if tipo == "criticos":
        v.criticos_omitidos = [c for c in criticos if c not in set(citas)][:20]
    permitidos = {round(float(x), 2) for x in montos_permitidos}
    malos = set()
    for m in RE_MONTO.findall(texto):
        val = numero(m)
        if val is not None and round(val, 2) not in permitidos:
            malos.add(f"$ {val:,.2f}")
    v.cifras_no_verificadas = sorted(malos)
    if v.citas_invalidas:
        v.estado = "RECHAZADO"
        v.mensajes.append("Se citaron códigos inexistentes en el contexto: " + ", ".join(v.citas_invalidas) + ".")
    elif v.cifras_no_verificadas or v.criticos_omitidos:
        v.estado = "ADVERTENCIAS"
        if v.cifras_no_verificadas:
            v.mensajes.append("Hay montos que no coinciden con los datos verificados: " + ", ".join(v.cifras_no_verificadas) + ".")
        if v.criticos_omitidos:
            v.mensajes.append(f"El reporte no menciona {len(v.criticos_omitidos)} bien(es) crítico(s).")
    else:
        v.mensajes.append("Todas las citas existen en el contexto y las cifras coinciden con los datos verificados.")
    return v
