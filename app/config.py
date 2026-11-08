"""Configuración de la demo (Singleton vía lru_cache). Variables desde .env."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent


def _cargar_env() -> None:
    f = BASE / ".env"
    if not f.exists():
        return
    for ln in f.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#") and "=" in ln:
            k, v = ln.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


@dataclass(frozen=True)
class Settings:
    db_path: Path
    index_dir: Path
    normativa_dir: Path
    logo: Path
    ciudad: str
    institucion: str
    secuencia_inicial: int
    # RAG
    vector_store: str            # auto | chroma | memoria
    embedding_provider: str      # hash | ollama
    ollama_embed_model: str
    top_k: int
    contexto_max: int
    reintentos: int
    # Generación
    llm_provider: str            # plantilla | ollama | anthropic | openai
    ollama_url: str
    ollama_model: str
    anthropic_api_key: str
    anthropic_model: str
    openai_base_url: str
    openai_api_key: str
    openai_model: str
    temperatura: float
    timeout_s: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    _cargar_env()
    e = os.environ.get
    llm = e("LLM_PROVIDER", "plantilla").lower()
    return Settings(
        db_path=Path(e("DB_PATH", str(BASE / "data" / "integrado_demo.db"))),
        index_dir=Path(e("INDEX_DIR", str(BASE / "data" / "index"))),
        normativa_dir=BASE / "data" / "normativa",
        logo=BASE / "assets" / "logo_espoch.png",
        ciudad=e("CIUDAD", "Riobamba"),
        institucion=e("INSTITUCION", "ESCUELA SUPERIOR POLITÉCNICA DE CHIMBORAZO"),
        secuencia_inicial=int(e("ACTA_SECUENCIA_INICIAL", "1")),
        vector_store=e("VECTOR_STORE", "auto").lower(),
        embedding_provider=e("EMBEDDING_PROVIDER", "hash").lower(),
        ollama_embed_model=e("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
        top_k=int(e("TOP_K", "12")),
        contexto_max=int(e("CONTEXTO_MAX_BIENES", "40")),
        reintentos=int(e("REINTENTOS_VALIDACION", "1")),
        llm_provider="plantilla" if llm == "template" else llm,
        ollama_url=e("OLLAMA_URL", "http://localhost:11434"),
        ollama_model=e("OLLAMA_MODEL", "llama3.1:8b"),
        anthropic_api_key=e("ANTHROPIC_API_KEY", ""),
        anthropic_model=e("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
        openai_base_url=e("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        openai_api_key=e("OPENAI_API_KEY", ""),
        openai_model=e("OPENAI_MODEL", "gpt-4o-mini"),
        temperatura=float(e("TEMPERATURA", "0.1")),
        timeout_s=int(e("TIMEOUT_S", "120")),
    )
