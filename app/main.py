from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import cortes, db
from .api import cargar_ejemplo, router
from .config import BASE


def crear_app() -> FastAPI:
    db.iniciar()
    app = FastAPI(title="Demo — Actas de constatación (eSByE)", version="1.0")
    app.include_router(router)
    if not cortes.listar() and (BASE / "data" / "matrices").exists():
        cargar_ejemplo()
    from .rag.indexador import indice
    indice().asegurar()
    web = BASE / "web"
    app.mount("/static", StaticFiles(directory=web), name="static")

    @app.get("/")
    def indice():
        return FileResponse(web / "index.html")

    return app


app = crear_app()
