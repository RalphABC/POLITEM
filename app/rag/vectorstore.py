"""Base vectorial — patrón Strategy: ChromaDB (persistente) o memoria (respaldo)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

import numpy as np

from ..config import Settings


class VectorStore(ABC):
    nombre = "abstracto"

    @abstractmethod
    def add(self, ids: List[str], vecs: np.ndarray, textos: List[str], metas: List[Dict]) -> None: ...

    @abstractmethod
    def query(self, vec: np.ndarray, k: int, where: Dict) -> List[Dict]: ...

    @abstractmethod
    def count(self, where: Optional[Dict] = None) -> int: ...

    @abstractmethod
    def delete(self, where: Dict) -> None: ...


def _y(where: Dict) -> Optional[Dict]:
    items = [{k: v} for k, v in where.items()]
    return None if not items else (items[0] if len(items) == 1 else {"$and": items})


class ChromaStore(VectorStore):
    def __init__(self, cfg: Settings, coleccion: str) -> None:
        import chromadb
        cfg.index_dir.mkdir(parents=True, exist_ok=True)
        self.nombre = f"ChromaDB {chromadb.__version__}"
        self._c = chromadb.PersistentClient(path=str(cfg.index_dir / "chroma"))
        self._col = self._c.get_or_create_collection(coleccion, metadata={"hnsw:space": "cosine"})

    def add(self, ids, vecs, textos, metas):
        for i in range(0, len(ids), 256):
            s = slice(i, i + 256)
            self._col.upsert(ids=ids[s], embeddings=vecs[s].tolist(), documents=textos[s], metadatas=metas[s])

    def query(self, vec, k, where):
        n = self.count(where)
        if n == 0:
            return []
        r = self._col.query(query_embeddings=[vec.tolist()], n_results=min(k, n), where=_y(where))
        return [{"id": i, "texto": d, "meta": m, "sim": 1.0 - float(dist)}
                for i, d, m, dist in zip(r["ids"][0], r["documents"][0], r["metadatas"][0], r["distances"][0])]

    def count(self, where=None):
        if not where:
            return self._col.count()
        return len(self._col.get(where=_y(where), include=[])["ids"])

    def delete(self, where):
        self._col.delete(where=_y(where))


class MemoryStore(VectorStore):
    nombre = "Memoria (NumPy)"

    def __init__(self) -> None:
        self.ids: List[str] = []
        self.v: Optional[np.ndarray] = None
        self.t: List[str] = []
        self.m: List[Dict] = []

    def add(self, ids, vecs, textos, metas):
        self.delete_ids(ids)
        self.ids += ids
        self.t += textos
        self.m += metas
        self.v = vecs if self.v is None else np.vstack([self.v, vecs])

    def delete_ids(self, ids):
        s = set(ids)
        keep = [i for i, x in enumerate(self.ids) if x not in s]
        self._keep(keep)

    def _keep(self, keep):
        self.ids = [self.ids[i] for i in keep]
        self.t = [self.t[i] for i in keep]
        self.m = [self.m[i] for i in keep]
        self.v = self.v[keep] if self.v is not None and keep else None

    def _idx(self, where):
        return [i for i, m in enumerate(self.m) if all(m.get(k) == v for k, v in (where or {}).items())]

    def query(self, vec, k, where):
        idx = self._idx(where)
        if not idx:
            return []
        sims = self.v[idx] @ vec
        orden = np.argsort(-sims)[:k]
        return [{"id": self.ids[idx[o]], "texto": self.t[idx[o]], "meta": self.m[idx[o]], "sim": float(sims[o])} for o in orden]

    def count(self, where=None):
        return len(self._idx(where))

    def delete(self, where):
        borrar = set(self._idx(where))
        self._keep([i for i in range(len(self.ids)) if i not in borrar])


def crear_store(cfg: Settings, embedder_nombre: str, dim: int) -> VectorStore:
    """Factory: Chroma si está disponible (o se pidió), memoria en otro caso."""
    if cfg.vector_store in ("auto", "chroma"):
        try:
            col = "esbye_" + "".join(ch if ch.isalnum() else "_" for ch in embedder_nombre) + f"_{dim}"
            return ChromaStore(cfg, col)
        except Exception:  # noqa: BLE001
            if cfg.vector_store == "chroma":
                raise
    return MemoryStore()
