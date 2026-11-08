"""Cortes mensuales de la matriz y comparación entre cortes (altas, bajas, traspasos...)."""
from __future__ import annotations

from typing import Dict, List, Optional

from .db import sesion


def listar() -> List[Dict]:
    with sesion() as c:
        return [dict(r) for r in c.execute("SELECT * FROM cortes ORDER BY fecha DESC, id DESC")]


def ultimo_id() -> Optional[int]:
    with sesion() as c:
        r = c.execute("SELECT id FROM cortes ORDER BY (alcance='institucional') DESC, fecha DESC, id DESC LIMIT 1").fetchone()
        return r["id"] if r else None


def corte_de_cedula(cedula: str) -> Optional[int]:
    """Corte más reciente que contiene bienes de esa cédula."""
    with sesion() as c:
        r = c.execute("""SELECT c.id FROM cortes c WHERE EXISTS(SELECT 1 FROM bienes b WHERE b.corte_id=c.id AND b.custodio_id=?)
                         ORDER BY c.fecha DESC, c.id DESC LIMIT 1""", (cedula,)).fetchone()
        return r["id"] if r else None


def funcionarios(corte_id: int) -> List[Dict]:
    with sesion() as c:
        return [dict(r) for r in c.execute("""SELECT custodio_id cedula, custodio_nombre nombre, COUNT(*) n, ROUND(SUM(valor_contable),2) valor
                                              FROM bienes WHERE corte_id=? GROUP BY custodio_id, custodio_nombre ORDER BY custodio_nombre""", (corte_id,))]


def bienes_de_cedula(corte_id: int, cedula: str) -> List[Dict]:
    with sesion() as c:
        return [dict(r) for r in c.execute("SELECT * FROM bienes WHERE corte_id=? AND custodio_id=? ORDER BY codigo", (corte_id, cedula))]


def anterior_a(corte_id: int) -> Optional[int]:
    """Corte institucional anterior (solo se comparan matrices institucionales entre sí)."""
    with sesion() as c:
        f = c.execute("SELECT fecha,id,alcance FROM cortes WHERE id=?", (corte_id,)).fetchone()
        if not f or f["alcance"] != "institucional":
            return None
        r = c.execute("SELECT id FROM cortes WHERE alcance='institucional' AND (fecha<? OR (fecha=? AND id<?)) ORDER BY fecha DESC,id DESC LIMIT 1",
                      (f["fecha"], f["fecha"], f["id"])).fetchone()
        return r["id"] if r else None


def _mapa(c, corte_id: int) -> Dict[str, dict]:
    return {r["codigo"]: dict(r) for r in c.execute("SELECT * FROM bienes WHERE corte_id=?", (corte_id,))}


def comparar(nuevo: int, previo: int) -> Dict:
    """Diferencias del corte `nuevo` respecto a `previo`."""
    with sesion() as c:
        a, b = _mapa(c, previo), _mapa(c, nuevo)
    altas = [b[k] for k in b if k not in a]
    bajas = [a[k] for k in a if k not in b]
    traspasos, reubic, estado, valor, dep = [], [], [], [], 0
    for k in b.keys() & a.keys():
        x, y = a[k], b[k]
        if (x["custodio_id"] or x["custodio_nombre"]) != (y["custodio_id"] or y["custodio_nombre"]):
            traspasos.append({"codigo": k, "descripcion": y["descripcion"], "de": x["custodio_nombre"], "a": y["custodio_nombre"]})
        if x["ubicacion"] != y["ubicacion"]:
            reubic.append({"codigo": k, "descripcion": y["descripcion"], "de": x["ubicacion"], "a": y["ubicacion"]})
        if (x["estado"] or "") != (y["estado"] or ""):
            estado.append({"codigo": k, "descripcion": y["descripcion"], "de": x["estado"], "a": y["estado"]})
        if abs((x["valor_contable"] or 0) - (y["valor_contable"] or 0)) > 0.005:
            valor.append({"codigo": k, "descripcion": y["descripcion"], "de": x["valor_contable"], "a": y["valor_contable"]})
        if abs((x["dep_acum"] or 0) - (y["dep_acum"] or 0)) > 0.005:
            dep += 1
    ref = lambda l: [{"codigo": r["codigo"], "descripcion": r["descripcion"], "ubicacion": r["ubicacion"],  # noqa: E731
                      "custodio": r["custodio_nombre"], "valor": r["valor_contable"]} for r in l]
    return {"corte": nuevo, "contra": previo, "altas": ref(altas), "bajas": ref(bajas), "traspasos": traspasos,
            "reubicaciones": reubic, "cambios_estado": estado, "cambios_valor": valor, "dep_actualizada": dep,
            "total_nuevo": len(b), "total_previo": len(a)}


def ubicaciones(corte_id: int) -> List[Dict]:
    with sesion() as c:
        filas = c.execute("""SELECT ubicacion, COUNT(*) n, ROUND(SUM(valor_contable),2) valor, ROUND(SUM(dep_acum),2) dep,
                             COUNT(DISTINCT custodio_nombre) custodios FROM bienes WHERE corte_id=?
                             GROUP BY ubicacion ORDER BY ubicacion""", (corte_id,)).fetchall()
        return [dict(r) for r in filas]


def custodios_de(corte_id: int, ubicacion: str) -> List[Dict]:
    with sesion() as c:
        filas = c.execute("""SELECT custodio_id, custodio_nombre, COUNT(*) n, ROUND(SUM(valor_contable),2) valor,
                             ROUND(SUM(dep_acum),2) dep FROM bienes WHERE corte_id=? AND ubicacion=?
                             GROUP BY custodio_id, custodio_nombre ORDER BY n DESC""", (corte_id, ubicacion)).fetchall()
        return [dict(r) for r in filas]


def bienes_de(corte_id: int, ubicacion: str, custodio_nombre: Optional[str] = None) -> List[Dict]:
    q, p = "SELECT * FROM bienes WHERE corte_id=? AND ubicacion=?", [corte_id, ubicacion]
    if custodio_nombre:
        q += " AND custodio_nombre=?"; p.append(custodio_nombre)
    with sesion() as c:
        return [dict(r) for r in c.execute(q + " ORDER BY codigo", p)]
