"""Proveedores de modelos de lenguaje (patrón Strategy + Factory): plantilla determinista | Ollama | Anthropic | OpenAI-compatible."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List

import httpx

from ..config import Settings
from ..totales import dinero, es_critico, totalmente_depreciado
from .prompts import Prompt


class LLMError(RuntimeError):
    pass


class LLMProvider(ABC):
    nombre: str = "abstracto"
    modelo: str = ""
    es_nube: bool = False

    @abstractmethod
    def generar(self, prompt: Prompt) -> str:
        ...

    def estado(self) -> Dict[str, Any]:
        return {"proveedor": self.nombre, "modelo": self.modelo, "disponible": True, "detalle": ""}


def _linea(b: Dict[str, Any]) -> str:
    return (f"- [{b['codigo']}] {b['descripcion']}: estado {b['estado'] or 'sin dato'}"
            + (f", condición {b['condicion']}" if b.get("condicion") else "") + f", valor en libros {dinero(b['valor_libros'])}.")


class TemplateLLM(LLMProvider):
    """Línea base determinista (sin modelo) y respaldo ante fallas."""
    nombre, modelo = "plantilla", "plantilla-determinista"

    def generar(self, prompt: Prompt) -> str:
        d = prompt.datos
        t, tipo, bienes = d["totales"], d["tipo"], d["bienes"]
        crit = [b for b in bienes if es_critico(b)]
        out: List[str] = []
        if tipo == "consulta_libre":
            out += ["### Respuesta a la consulta", f"Consulta: *{d.get('pregunta') or '(sin texto)'}*", "",
                    "El sistema está en **modo plantilla** (sin modelo generativo). Estos son los registros más relevantes recuperados:"]
            out += [_linea(b) for b in bienes[:10]] or ["- No se recuperaron bienes relacionados con la consulta."]
            return "\n".join(out)
        pe = t["por_estado"]
        out += [f"### {'Reporte totalizado de activos' if tipo == 'totalizado' else 'Reporte de bienes críticos'}",
                f"**Ámbito:** {d['etiqueta']} · **Corte:** {d['fecha_corte']}", "", "### 1. Resumen ejecutivo",
                f"Se registran **{t['total']} bienes** con un valor contable de {dinero(t['valor_contable'])}, una depreciación acumulada de "
                f"{dinero(t['dep_acum'])} y un valor en libros de {dinero(t['valor_libros'])}. Por estado: "
                + ", ".join(f"{v} {k.lower()}" for k, v in pe.items()) + "."]
        if t["totalmente_depreciados"]:
            out.append(f"{t['totalmente_depreciados']} bien(es) están totalmente depreciados (conservan solo su valor residual).")
        out += ["", "### 2. Hallazgos"]
        if tipo == "totalizado":
            top = sorted(bienes, key=lambda b: -(b["valor_contable"] or 0))[:5]
            out.append("Bienes de mayor valor contable:")
            out += [f"- [{b['codigo']}] {b['descripcion']}: valor contable {dinero(b['valor_contable'])}." for b in top]
        if crit:
            out.append(f"Se identificaron **{len(crit)} bien(es) crítico(s)** (mal estado, para baja, no ubicados o en reparación):")
            out += [_linea(b) for b in crit[:25]]
        else:
            out.append("No se identificaron bienes críticos entre los registros analizados.")
        if tipo == "criticos":
            dep = sorted([b for b in bienes if totalmente_depreciado(b)], key=lambda b: -(b["valor_contable"] or 0))[:8]
            if dep:
                out.append("Bienes totalmente depreciados de mayor valor contable:")
                out += [f"- [{b['codigo']}] {b['descripcion']}: valor contable {dinero(b['valor_contable'])}, valor en libros {dinero(b['valor_libros'])}." for b in dep]
        out += ["", "### 3. Recomendaciones"]
        rec = []
        if crit:
            rec.append("Solicitar diagnóstico técnico de " + ", ".join(f"[{b['codigo']}]" for b in crit[:8]) + " para decidir reparación o baja.")
        if t["totalmente_depreciados"]:
            rec.append("Revisar la vida útil restante de los bienes totalmente depreciados antes de la próxima constatación.")
        if d.get("normas"):
            rec.append(f"Criterio de referencia: {d['normas'][0]['titulo']}.")
        rec = rec or ["Mantener el seguimiento periódico; no se requieren acciones inmediatas."]
        out += [f"{i}. {r}" for i, r in enumerate(rec, 1)]
        return "\n".join(out)


# ---------------------------------------------------------------------------
# Proveedores generativos
# ---------------------------------------------------------------------------
class OllamaLLM(LLMProvider):
    nombre = "ollama"

    def __init__(self, cfg: Settings) -> None:
        self.url, self.modelo = cfg.ollama_url, cfg.ollama_model
        self.temp, self.timeout = cfg.temperatura, cfg.timeout_s

    def generar(self, prompt: Prompt) -> str:
        try:
            r = httpx.post(f"{self.url}/api/chat", timeout=self.timeout, json={
                "model": self.modelo, "stream": False,
                "options": {"temperature": self.temp, "num_ctx": 8192},
                "messages": [{"role": "system", "content": prompt.system},
                             {"role": "user", "content": prompt.user}]})
            r.raise_for_status()
            return r.json()["message"]["content"].strip()
        except Exception as e:  # noqa: BLE001
            raise LLMError(f"Ollama no respondió: {e}") from e

    def estado(self) -> Dict[str, Any]:
        try:
            r = httpx.get(f"{self.url}/api/tags", timeout=3)
            r.raise_for_status()
            modelos = [m["name"] for m in r.json().get("models", [])]
            ok = any(self.modelo == m or m.startswith(self.modelo + ":") or self.modelo.startswith(m.split(":")[0])
                     for m in modelos)
            return {"proveedor": self.nombre, "modelo": self.modelo, "disponible": ok,
                    "detalle": "" if ok else f"Modelo no instalado. Disponibles: {', '.join(modelos) or 'ninguno'}"}
        except Exception as e:  # noqa: BLE001
            return {"proveedor": self.nombre, "modelo": self.modelo, "disponible": False,
                    "detalle": f"Ollama no accesible en {self.url} ({type(e).__name__})"}


class AnthropicLLM(LLMProvider):
    nombre = "anthropic"
    es_nube = True

    def __init__(self, cfg: Settings) -> None:
        self.key, self.modelo = cfg.anthropic_api_key, cfg.anthropic_model
        self.temp, self.timeout = cfg.temperatura, cfg.timeout_s

    def generar(self, prompt: Prompt) -> str:
        if not self.key:
            raise LLMError("Falta ANTHROPIC_API_KEY")
        try:
            r = httpx.post("https://api.anthropic.com/v1/messages", timeout=self.timeout,
                           headers={"x-api-key": self.key, "anthropic-version": "2023-06-01",
                                    "content-type": "application/json"},
                           json={"model": self.modelo, "max_tokens": 2500, "temperature": self.temp,
                                 "system": prompt.system,
                                 "messages": [{"role": "user", "content": prompt.user}]})
            r.raise_for_status()
            return "".join(b.get("text", "") for b in r.json()["content"]).strip()
        except Exception as e:  # noqa: BLE001
            raise LLMError(f"Anthropic API falló: {e}") from e

    def estado(self) -> Dict[str, Any]:
        ok = bool(self.key)
        return {"proveedor": self.nombre, "modelo": self.modelo, "disponible": ok,
                "detalle": "" if ok else "Falta ANTHROPIC_API_KEY"}


class OpenAICompatLLM(LLMProvider):
    nombre = "openai"
    es_nube = True

    def __init__(self, cfg: Settings) -> None:
        self.base, self.key, self.modelo = cfg.openai_base_url, cfg.openai_api_key, cfg.openai_model
        self.temp, self.timeout = cfg.temperatura, cfg.timeout_s

    def generar(self, prompt: Prompt) -> str:
        try:
            r = httpx.post(f"{self.base}/chat/completions", timeout=self.timeout,
                           headers={"Authorization": f"Bearer {self.key}"},
                           json={"model": self.modelo, "temperature": self.temp,
                                 "messages": [{"role": "system", "content": prompt.system},
                                              {"role": "user", "content": prompt.user}]})
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:  # noqa: BLE001
            raise LLMError(f"API compatible con OpenAI falló: {e}") from e

    def estado(self) -> Dict[str, Any]:
        ok = bool(self.key)
        return {"proveedor": self.nombre, "modelo": self.modelo, "disponible": ok,
                "detalle": "" if ok else "Falta OPENAI_API_KEY"}


def crear_llm(cfg: Settings) -> LLMProvider:
    """Factory: instancia el proveedor indicado en ``LLM_PROVIDER``."""
    return {
        "ollama": lambda: OllamaLLM(cfg),
        "anthropic": lambda: AnthropicLLM(cfg),
        "openai": lambda: OpenAICompatLLM(cfg),
    }.get(cfg.llm_provider, TemplateLLM)()
