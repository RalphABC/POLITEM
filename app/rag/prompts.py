"""Construcción de prompts (patrón Builder). Reglas anti-alucinación en el prompt de sistema."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from ..totales import dinero

TIPOS = {
    "totalizado": "Reporte totalizado de activos",
    "criticos": "Reporte de bienes críticos",
    "consulta_libre": "Consulta en lenguaje natural",
}


@dataclass
class Prompt:
    system: str
    user: str
    datos: Dict[str, Any] = field(default_factory=dict)


SISTEMA = """Eres un asistente de control de bienes públicos de la ESPOCH. Redactas reportes formales, claros y en español \
sobre bienes registrados en eSByE.

REGLAS OBLIGATORIAS:
1. Usa EXCLUSIVAMENTE la información de los bloques CONTEXTO y DATOS VERIFICADOS. Si un dato no está, escribe "no consta en eSByE".
2. Cada afirmación sobre un bien debe citar su código entre corchetes, por ejemplo [ESP-000123]. No cites códigos que no aparezcan en el contexto.
3. No calcules totales ni porcentajes: usa solamente las cifras de DATOS VERIFICADOS (calculadas por el sistema). \
No escribas montos que no estén en el contexto.
4. No inventes causas, fechas, personas ni normas. Los criterios normativos pueden mencionarse como "criterio de referencia".
5. Estructura en Markdown: "### 1. Resumen ejecutivo", "### 2. Hallazgos", "### 3. Recomendaciones" (lista numerada, cada recomendación vinculada a bienes citados).
6. Tono institucional, sin adornos; máximo 450 palabras. Si es una consulta, responde directo y breve."""

INSTRUCCION = {
    "totalizado": "Redacta el reporte totalizado de los activos existentes: cantidad, valor contable, depreciación acumulada y valor en libros, distribución por estado, y los bienes que requieren atención.",
    "criticos": "Redacta un reporte de bienes críticos (mal estado, para baja, no ubicados, en reparación o totalmente depreciados) con una recomendación por grupo.",
    "consulta_libre": "Responde la pregunta del usuario apoyándote solo en el contexto. Si el contexto no alcanza, dilo.",
}


def fmt_totales(t: Dict) -> str:
    pe = t["por_estado"]
    return (f"- Bienes registrados: {t['total']}\n- Valor contable total: {dinero(t['valor_contable'])}\n"
            f"- Depreciación acumulada: {dinero(t['dep_acum'])}\n- Valor en libros: {dinero(t['valor_libros'])}\n"
            f"- Por estado: " + ", ".join(f"{k} {v}" for k, v in pe.items()) + "\n"
            f"- Bienes críticos: {t['n_criticos']}; totalmente depreciados: {t['totalmente_depreciados']}")


class ConstructorPrompt:
    def construir(self, tipo: str, etiqueta: str, totales: Dict, rec: Dict, pregunta: str, fecha_corte: str, correccion: str = "") -> Prompt:
        ctx = "\n".join(f"[{e['codigo']}] {e['texto']}" for e in rec["bienes"])
        norm = "\n".join(f"(Criterio) {n['titulo']}: {n['texto']}" for n in rec["normas"]) or "(sin criterios)"
        user = (f"TIPO: {TIPOS[tipo]}\nFECHA DE CORTE: {fecha_corte}\nÁMBITO: {etiqueta}\nINSTRUCCIÓN: {INSTRUCCION[tipo]}\n"
                + (f"PREGUNTA: {pregunta}\n" if pregunta else "")
                + f"\nDATOS VERIFICADOS (calculados por el sistema):\n{fmt_totales(totales)}\n"
                f"\nCONTEXTO — BIENES RECUPERADOS ({len(rec['bienes'])} de {totales['total']}):\n{ctx}\n"
                f"\nCONTEXTO — CRITERIOS NORMATIVOS:\n{norm}\n" + (f"\nCORRECCIÓN REQUERIDA: {correccion}\n" if correccion else ""))
        datos = {"tipo": tipo, "etiqueta": etiqueta, "totales": totales, "bienes": [e["bien"] for e in rec["bienes"]],
                 "normas": rec["normas"], "pregunta": pregunta, "fecha_corte": fecha_corte}
        return Prompt(SISTEMA, user, datos)
