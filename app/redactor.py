"""Redacción de las novedades del acta (Strategy: plantilla determinista | Ollama opcional con validación)."""
from __future__ import annotations

import re
from typing import Dict, List, Optional

import httpx

from .config import get_settings

TIPOS = {
    "faltante": "Bien faltante (no ubicado)",
    "mal_estado": "Bien en mal estado",
    "sobrante": "Bien sobrante (no consta en la matriz)",
    "ubicacion_distinta": "Bien en otra ubicación",
    "sin_etiqueta": "Bien sin etiqueta / código ilegible",
    "otro": "Otra novedad",
}
RE_COD = re.compile(r"[A-Z]{2,4}-\d{3,}")


def _bien(o: Dict) -> str:
    cod, desc = o.get("codigo") or "", o.get("descripcion") or ""
    if cod and desc:
        return f"El bien con código {cod} ({desc})"
    if cod:
        return f"El bien con código {cod}"
    return f"El bien {desc}".strip() if desc else "Un bien"


def _fin(t: str) -> str:
    t = t.strip()
    return t if t.endswith((".", "!", "?")) else t + "."


def por_plantilla(o: Dict, ubicacion: str) -> str:
    tipo, det, nota = o.get("tipo", "otro"), (o.get("detalle") or "").strip(), (o.get("nota") or "").strip()
    donde = f", ubicado en {det}," if det else ""
    if tipo == "faltante":
        base = f"{_bien(o)} no se encuentra en la ubicación {ubicacion}; se registra como bien faltante"
    elif tipo == "mal_estado":
        base = f"{_bien(o)}{donde} se encuentra en mal estado"
    elif tipo == "sobrante":
        base = f"Se encontró en la ubicación {ubicacion} un bien que no consta en la matriz de eSByE"
        base += f": {o.get('descripcion')}" if o.get("descripcion") else ""
    elif tipo == "ubicacion_distinta":
        base = f"{_bien(o)} no se encuentra en {ubicacion}, sino en {det or 'otra ubicación'}"
    elif tipo == "sin_etiqueta":
        base = f"{_bien(o)} no tiene etiqueta con código o este es ilegible"
    else:
        base = f"{_bien(o)}".rstrip() + (" presenta una novedad" if o.get("codigo") else "")
    return _fin(base + (f". Observación del analista: {nota}" if nota else ""))


def _ollama(oraciones: List[str]) -> Optional[List[str]]:
    s = get_settings()
    prompt = ("Reescribe cada oración en español formal e institucional, una por línea, sin añadir información, sin cambiar códigos "
              "ni cifras y sin numerar:\n" + "\n".join(oraciones))
    try:
        r = httpx.post(f"{s.ollama_url}/api/chat", timeout=60, json={
            "model": s.ollama_model, "stream": False, "options": {"temperature": 0},
            "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        lineas = [l.strip(" -•\t") for l in r.json()["message"]["content"].splitlines() if l.strip()]
    except Exception:
        return None
    if len(lineas) != len(oraciones):
        return None
    for orig, nuevo in zip(oraciones, lineas):      # validación: mismos códigos y mismas cifras
        if set(RE_COD.findall(orig)) != set(RE_COD.findall(nuevo)):
            return None
        if set(re.findall(r"\d+", orig)) - set(re.findall(r"\d+", nuevo)):
            return None
    return lineas


def redactar(observaciones: List[Dict], ubicacion: str) -> Dict:
    base = [por_plantilla(o, ubicacion) for o in observaciones]
    modo, aviso = "plantilla", None
    if observaciones and get_settings().llm_provider == "ollama":
        mejorado = _ollama(base)
        if mejorado:
            base, modo = mejorado, "ollama"
        else:
            aviso = "El modelo local no respondió o alteró códigos/cifras; se usó la plantilla."
    return {"oraciones": base, "modo": modo, "aviso": aviso}
