"""Indexación: fragmentos → embeddings → base vectorial. Un único objeto por proceso (Singleton)."""
from __future__ import annotations

import time
from functools import lru_cache
from typing import Dict, List

from .. import cortes
from ..config import get_settings
from ..db import sesion
from .chunking import chunks_bienes, chunks_normativa
from .embeddings import Embedder, crear_embedder
from .vectorstore import VectorStore, crear_store


class Indice:
    def __init__(self) -> None:
        s = get_settings()
        self.embedder: Embedder = crear_embedder(s)
        self.store: VectorStore = crear_store(s, self.embedder.nombre, self.embedder.dim)
        self.ultima_indexacion: Dict = {}

    def _anadir(self, ids, textos, metas) -> None:
        for i in range(0, len(ids), 128):
            self.store.add(ids[i:i + 128], self.embedder.embed(textos[i:i + 128]), textos[i:i + 128], metas[i:i + 128])

    def indexar_corte(self, corte_id: int) -> int:
        t0 = time.perf_counter()
        with sesion() as c:
            bienes = [dict(r) for r in c.execute("SELECT * FROM bienes WHERE corte_id=?", (corte_id,))]
        self.store.delete({"tipo": "bien", "corte_id": corte_id})
        ids, textos, metas = chunks_bienes(corte_id, bienes)
        self._anadir(ids, textos, metas)
        self.ultima_indexacion[corte_id] = {"fragmentos": len(ids), "segundos": round(time.perf_counter() - t0, 2)}
        return len(ids)

    def indexar_normativa(self) -> int:
        self.store.delete({"tipo": "norma"})
        ids, textos, metas = chunks_normativa()
        if ids:
            self._anadir(ids, textos, metas)
        return len(ids)

    def asegurar(self) -> None:
        """Indexa lo que falte (normativa y cortes) — se llama al iniciar."""
        if self.store.count({"tipo": "norma"}) == 0:
            self.indexar_normativa()
        for c in cortes.listar():
            if self.store.count({"tipo": "bien", "corte_id": c["id"]}) != c["n_validas"]:
                self.indexar_corte(c["id"])

    def estado(self) -> Dict:
        s = get_settings()
        return {"base_vectorial": self.store.nombre, "embeddings": self.embedder.nombre, "dimension": self.embedder.dim,
                "semantico": self.embedder.semantico, "fragmentos_normativa": self.store.count({"tipo": "norma"}),
                "cortes": [{"id": c["id"], "fecha": c["fecha"], "alcance": c["alcance"], "bienes": c["n_validas"],
                            "indexados": self.store.count({"tipo": "bien", "corte_id": c["id"]})} for c in cortes.listar()],
                "solicitado": {"vector_store": s.vector_store, "embeddings": s.embedding_provider}}


@lru_cache(maxsize=1)
def indice() -> Indice:
    return Indice()


def reiniciar() -> None:
    indice.cache_clear()
