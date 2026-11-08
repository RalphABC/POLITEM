"""Adaptador de la matriz de eSByE (patrón Adapter) y carga mensual por cortes.

Los encabezados se normalizan y se reconocen por alias. Los nombres corresponden a los campos que el manual público del
módulo de Bienes de eSByE menciona como filtros del reporte «Institucional Bienes por Sector»; los nombres exactos de las
columnas de la exportación real deben validarse con una matriz oficial (basta ajustar ALIAS).
"""
from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional

import pandas as pd

from .db import sesion

ALIAS: Dict[str, List[str]] = {
    "codigo": ["codigo bien", "codigo", "codigo del bien", "cod bien", "codigo_bien"],
    "descripcion": ["descripcion", "descripcion del bien", "detalle", "nombre del bien"],
    "tipo_bien": ["tipo bien", "tipo de bien", "tipo", "categoria", "id tipo bien"],
    "marca": ["marca", "marca/raza/otros", "marca raza otros"],
    "modelo": ["modelo", "modelo/caracteristicas", "modelo caracteristicas"],
    "serie": ["serie", "serie/identificacion", "serie identificacion", "numero de serie"],
    "estado": ["estado", "estado del bien", "estado de conservacion"],
    "condicion": ["condicion del bien", "condicion", "situacion"],
    "ubicacion": ["nombre bodega", "bodega", "ubicacion", "ubicacion fisica", "dependencia"],
    "sector": ["sector"],
    "custodio_id": ["cedula custodio", "cedula/ruc", "cedula", "identificacion custodio", "cedula ruc custodio"],
    "custodio_nombre": ["custodio actual", "custodio", "nombre custodio", "responsable"],
    "fecha_ingreso": ["fecha ingreso", "fecha de ingreso", "fecha adquisicion"],
    "fecha_ult_dep": ["fecha ultima depreciacion", "fecha ult depreciacion", "ultima depreciacion"],
    "valor_contable": ["valor contable", "valor de adquisicion", "costo", "valor inicial"],
    "dep_acum": ["valor depreciacion acumulada", "depreciacion acumulada", "dep acumulada", "valor depreciacion acum"],
    "valor_libros": ["valor libros", "valor en libros", "valor neto"],
    "vida_util": ["vida util", "vida util (anos)", "vida util anos"],
}
OBLIGATORIOS = ["codigo", "descripcion", "valor_contable"]


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t.strip().lower())


def _fecha(v) -> Optional[str]:
    if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() in ("", "NaT", "nan"):
        return None
    if isinstance(v, (datetime, pd.Timestamp)):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s[:10], fmt).date().isoformat()
        except ValueError:
            continue
    return None


def numero(v, defecto: Optional[float] = None) -> Optional[float]:
    """Acepta 1234.56, 1,234.56, 1.234,56, $ 1 234,56."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return defecto
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d,.\-]", "", str(v))
    if not s or s in ("-", ".", ","):
        return defecto
    if "," in s and "." in s:
        s = s.replace(",", "") if s.rfind(".") > s.rfind(",") else s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".") if re.search(r",\d{1,2}$", s) else s.replace(",", "")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return defecto


def _s(v) -> str:
    return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()


@dataclass
class ResultadoCarga:
    corte_id: int = 0
    fecha: str = ""
    n_filas: int = 0
    n_validas: int = 0
    rechazos: List[Dict] = field(default_factory=list)
    sin_mapear: List[str] = field(default_factory=list)
    mapeo: Dict[str, str] = field(default_factory=dict)
    faltantes: List[str] = field(default_factory=list)
    advertencias: List[str] = field(default_factory=list)
    indexados: int = 0

    def dict(self) -> Dict:
        return self.__dict__


def leer_tabla(contenido: bytes, nombre: str, meta: Optional[Dict] = None) -> pd.DataFrame:
    if nombre.lower().endswith(".pdf"):
        from .pdf_loader import leer_pdf
        df, m = leer_pdf(contenido)
        if meta is not None:
            meta.update(m)
        return df
    if nombre.lower().endswith((".xlsx", ".xlsm", ".xls")):
        return pd.read_excel(io.BytesIO(contenido), dtype=object)
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(io.BytesIO(contenido), dtype=object, sep=None, engine="python", encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError("No se pudo leer el archivo: use .csv (UTF-8) o .xlsx")


def importar(contenido: bytes, nombre: str, fecha_corte: Optional[str] = None, alcance: str = "institucional") -> ResultadoCarga:
    meta: Dict = {}
    df = leer_tabla(contenido, nombre, meta)
    res = ResultadoCarga(n_filas=len(df))
    if alcance not in ("institucional", "parcial"):
        raise ValueError("El alcance debe ser «institucional» o «parcial».")
    normalizadas = {_norm(c): c for c in df.columns}
    for campo, alias in ALIAS.items():
        for a in alias:
            if a in normalizadas:
                res.mapeo[campo] = normalizadas[a]
                break
    usados = set(res.mapeo.values())
    res.sin_mapear = [c for c in df.columns if c not in usados]
    res.faltantes = [c for c in OBLIGATORIOS if c not in res.mapeo]
    if res.faltantes:
        raise ValueError("Faltan columnas obligatorias: " + ", ".join(res.faltantes) +
                         ". Columnas detectadas: " + ", ".join(map(str, df.columns)))
    if "custodio_nombre" not in res.mapeo and not meta.get("custodio"):
        raise ValueError("El documento no indica el custodio (ni en columnas ni en la cabecera).")
    if "ubicacion" not in res.mapeo:
        res.advertencias.append("El documento no trae ubicación; se asignó «SIN UBICACIÓN REGISTRADA».")
    if "custodio_nombre" not in res.mapeo:
        res.advertencias.append(f"Custodio tomado de la cabecera del documento: {meta.get('custodio')}.")
    fecha = _fecha(fecha_corte) or date.today().isoformat()
    res.fecha = fecha
    filas, vistos = [], set()
    for i, fila in df.iterrows():
        def g(k):
            if k in res.mapeo:
                return fila[res.mapeo[k]]
            return {"ubicacion": "SIN UBICACIÓN REGISTRADA", "custodio_nombre": meta.get("custodio"), "custodio_id": meta.get("cedula")}.get(k)
        cod = _s(g("codigo"))
        motivo = None
        if not cod:
            motivo = "código vacío"
        elif cod in vistos:
            motivo = "código duplicado en el archivo"
        elif not _s(g("custodio_nombre")):
            motivo = "custodio vacío"
        elif numero(g("valor_contable")) is None:
            motivo = "valor contable no numérico"
        if motivo:
            res.rechazos.append({"fila": int(i) + 2, "codigo": cod, "motivo": motivo})
            continue
        vistos.add(cod)
        vc = numero(g("valor_contable"), 0.0)
        da = numero(g("dep_acum"), None)
        vl = numero(g("valor_libros"), None)
        if da is None and vl is not None:
            da = round(vc - vl, 2)
        if da is None:
            da = 0.0
            res.advertencias.append(f"{cod}: sin depreciación acumulada; se asumió 0") if len(res.advertencias) < 15 else None
        if vl is None:
            vl = round(vc - da, 2)
        filas.append((cod, _s(g("descripcion")), _s(g("marca")), _s(g("modelo")), _s(g("serie")), _s(g("tipo_bien")),
                      _s(g("estado")), _s(g("condicion")), _s(g("ubicacion")) or "SIN UBICACIÓN REGISTRADA", _s(g("sector")),
                      _s(g("custodio_id")), _s(g("custodio_nombre")), _fecha(g("fecha_ingreso")),
                      _fecha(g("fecha_ult_dep")), vc, da, vl, numero(g("vida_util"), None)))
    res.n_validas = len(filas)
    if not filas:
        raise ValueError("El archivo no contiene filas válidas.")
    with sesion() as c:
        cur = c.execute("INSERT INTO cortes(fecha,archivo,n_filas,n_validas,n_rechazadas,alcance,formato) VALUES(?,?,?,?,?,?,?)",
                        (fecha, nombre, res.n_filas, res.n_validas, len(res.rechazos), alcance, nombre.rsplit(".", 1)[-1].lower()))
        res.corte_id = cur.lastrowid
        c.executemany("INSERT INTO bienes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      [(res.corte_id,) + f for f in filas])
    return res
