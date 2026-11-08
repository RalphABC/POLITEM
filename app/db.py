"""Acceso a SQLite (Repository sencillo)."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from .config import get_settings

ESQUEMA = """
CREATE TABLE IF NOT EXISTS cortes(
  id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT NOT NULL, archivo TEXT, n_filas INTEGER, n_validas INTEGER,
  n_rechazadas INTEGER, alcance TEXT NOT NULL DEFAULT 'institucional', formato TEXT, creado TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS bienes(
  corte_id INTEGER NOT NULL, codigo TEXT NOT NULL, descripcion TEXT, marca TEXT, modelo TEXT, serie TEXT, tipo_bien TEXT,
  estado TEXT, condicion TEXT, ubicacion TEXT, sector TEXT, custodio_id TEXT, custodio_nombre TEXT, fecha_ingreso TEXT,
  fecha_ult_dep TEXT, valor_contable REAL, dep_acum REAL, valor_libros REAL, vida_util REAL,
  PRIMARY KEY(corte_id, codigo));
CREATE INDEX IF NOT EXISTS ix_bienes_ubic ON bienes(corte_id, ubicacion);
CREATE TABLE IF NOT EXISTS informes(
  id INTEGER PRIMARY KEY AUTOINCREMENT, creado TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, corte_id INTEGER, tipo TEXT NOT NULL,
  ambito TEXT NOT NULL, etiqueta TEXT, pregunta TEXT, contenido TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS personal(
  id INTEGER PRIMARY KEY AUTOINCREMENT, rol TEXT NOT NULL, titulo TEXT, nombre TEXT NOT NULL, cargo TEXT NOT NULL,
  activo INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS actas(
  id INTEGER PRIMARY KEY AUTOINCREMENT, numero TEXT NOT NULL UNIQUE, anio INTEGER NOT NULL, secuencia INTEGER NOT NULL,
  fecha TEXT NOT NULL, corte_id INTEGER, ubicacion TEXT, modo TEXT NOT NULL, items INTEGER, valor_total REAL, dep_acum REAL,
  valor_manual INTEGER NOT NULL DEFAULT 0, estado TEXT NOT NULL DEFAULT 'emitida', codigos TEXT, estructura TEXT NOT NULL,
  creado TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
"""


def conectar() -> sqlite3.Connection:
    p = get_settings().db_path
    p.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(p)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c


@contextmanager
def sesion() -> Iterator[sqlite3.Connection]:
    c = conectar()
    try:
        yield c
        c.commit()
    finally:
        c.close()


def iniciar() -> None:
    with sesion() as c:
        c.executescript(ESQUEMA)
        if c.execute("SELECT COUNT(*) FROM personal").fetchone()[0] == 0:
            c.executemany("INSERT INTO personal(rol,titulo,nombre,cargo) VALUES(?,?,?,?)", [
                ("analista", "Ing.", "Andrea Adriance", "analista de bienes y bodegas 1"),
                ("analista", "Ing.", "Edith Velázquez", "analista de bienes y bodegas 1"),
                ("analista", "Ing.", "María Augusta Guevara", "analista de bienes y bodegas 1"),
                ("coordinador", "Lcda.", "Mónica Fernández", "coordinadora de bienes y bodegas"),
            ])
