"""Incrustaciones (embeddings) — patrón Strategy + Factory.

* HashingEmbedder: vectores densos por n-gramas de caracteres (léxico, determinista, sin descargas). Tolera tildes y variantes.
* OllamaEmbedder: vectores semánticos de un modelo local (p. ej. nomic-embed-text). Requiere Ollama.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

import httpx
import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer

from ..config import Settings


class EmbedError(RuntimeError):
    pass


class Embedder(ABC):
    nombre: str = "abstracto"
    dim: int = 0
    semantico: bool = False

    @abstractmethod
    def embed(self, textos: List[str]) -> np.ndarray:
        ...


class HashingEmbedder(Embedder):
    nombre, dim, semantico = "hash-ngramas", 1024, False

    def __init__(self) -> None:
        self._v = HashingVectorizer(analyzer="char_wb", ngram_range=(3, 5), n_features=self.dim, alternate_sign=False,
                                    norm="l2", strip_accents="unicode", lowercase=True)

    def embed(self, textos: List[str]) -> np.ndarray:
        return self._v.transform(textos).toarray().astype(np.float32)


class OllamaEmbedder(Embedder):
    semantico = True

    def __init__(self, cfg: Settings) -> None:
        self.url, self.modelo = cfg.ollama_url, cfg.ollama_embed_model
        self.nombre = f"ollama:{self.modelo}"
        self.dim = len(self.embed(["prueba"])[0])

    def embed(self, textos: List[str]) -> np.ndarray:
        try:
            r = httpx.post(f"{self.url}/api/embed", json={"model": self.modelo, "input": textos}, timeout=120)
            r.raise_for_status()
            v = np.array(r.json()["embeddings"], dtype=np.float32)
        except Exception as e:  # noqa: BLE001
            raise EmbedError(f"Ollama (embeddings) no respondió: {e}") from e
        n = np.linalg.norm(v, axis=1, keepdims=True)
        return v / np.where(n == 0, 1, n)


def crear_embedder(cfg: Settings) -> Embedder:
    if cfg.embedding_provider == "ollama":
        try:
            return OllamaEmbedder(cfg)
        except EmbedError:
            pass                      # respaldo automático: embeddings léxicos
    return HashingEmbedder()
