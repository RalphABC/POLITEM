import os
import tempfile
from pathlib import Path

import pytest

TMP = Path(tempfile.mkdtemp(prefix="integrado_test_"))
os.environ["DB_PATH"] = str(TMP / "t.db")
os.environ["INDEX_DIR"] = str(TMP / "idx")
_n = {"i": 0}


@pytest.fixture(autouse=True)
def entorno_limpio(monkeypatch):
    from app import db
    from app.config import get_settings
    from app.rag.indexador import reiniciar
    _n["i"] += 1
    monkeypatch.setenv("INDEX_DIR", str(TMP / f"idx{_n['i']}"))
    monkeypatch.setenv("DB_PATH", str(TMP / f"t{_n['i']}.db"))
    get_settings.cache_clear()
    reiniciar()
    db.iniciar()
    yield
    reiniciar()
