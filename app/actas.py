"""Servicio de actas de constatación física (Facade): arma, emite y consulta actas con un único modelo."""
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Dict, List, Optional

from . import cortes, normativa, redactor
from .config import get_settings
from .db import sesion

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


class ErrorActa(ValueError):
    pass


def dinero(v: float) -> str:
    return "$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _persona(rol: str, pid: Optional[int]) -> Dict:
    if not pid:
        raise ErrorActa(f"Seleccione {'al analista' if rol == 'analista' else 'a la coordinación'}.")
    with sesion() as c:
        r = c.execute("SELECT * FROM personal WHERE id=? AND rol=? AND activo=1", (pid, rol)).fetchone()
    if not r:
        raise ErrorActa("La persona seleccionada no existe o está inactiva.")
    return dict(r)


def _nombre(titulo: str, nombre: str) -> str:
    return f"{titulo} {nombre}".strip()


def siguiente_secuencia(anio: int) -> int:
    with sesion() as c:
        r = c.execute("SELECT MAX(secuencia) m FROM actas WHERE anio=?", (anio,)).fetchone()
    return (r["m"] + 1) if r and r["m"] else get_settings().secuencia_inicial


def armar(p: Dict) -> Dict:
    """Devuelve la estructura completa del acta (sin guardarla)."""
    s = get_settings()
    try:
        fecha = date.fromisoformat(p.get("fecha") or date.today().isoformat())
    except ValueError:
        raise ErrorActa("La fecha del acta no es válida.")
    modo = p.get("modo", "matriz")
    ubic = (p.get("ubicacion") or "").strip()
    if not ubic:
        raise ErrorActa("Indique la ubicación (centro) donde se realiza la constatación.")
    analista = _persona("analista", p.get("analista_id"))
    coord = _persona("coordinador", p.get("coordinador_id"))
    advert: List[str] = []
    codigos: List[str] = []
    corte_id = None
    resp_nombre = (p.get("responsable_nombre") or "").strip()
    resp_titulo = (p.get("responsable_titulo") or "").strip()
    meta: Dict = {"modo": modo}

    if modo == "matriz":
        corte_id = p.get("corte_id") or cortes.ultimo_id()
        if not corte_id:
            raise ErrorActa("Aún no hay una matriz cargada. Cargue la matriz de eSByE o use el modo manual.")
        cust = (p.get("custodio_nombre") or "").strip() or None
        bienes = cortes.bienes_de(corte_id, ubic, cust)
        if not bienes:
            raise ErrorActa("La matriz no tiene bienes para esa ubicación (y custodio) en el corte seleccionado.")
        items = len(bienes)
        v_mat = round(sum(b["valor_contable"] or 0 for b in bienes), 2)
        d_mat = round(sum(b["dep_acum"] or 0 for b in bienes), 2)
        valor, dep = v_mat, d_mat
        codigos = [b["codigo"] for b in bienes]
        custs = cortes.custodios_de(corte_id, ubic)
        if not resp_nombre:
            resp_nombre = cust or custs[0]["custodio_nombre"]
        if resp_nombre not in {c["custodio_nombre"] for c in custs}:
            advert.append(f"«{resp_nombre}» no figura como custodio de bienes en esta ubicación según la matriz.")
        if not cust and len(custs) > 1:
            advert.append(f"La ubicación tiene {len(custs)} custodios; el acta incluye los bienes de todos. "
                          "Si el acta es por custodio, seleccione uno.")
        with sesion() as c:
            ffecha = c.execute("SELECT fecha FROM cortes WHERE id=?", (corte_id,)).fetchone()["fecha"]
        dias = (fecha - date.fromisoformat(ffecha)).days
        if dias > 35:
            advert.append(f"La matriz usada tiene fecha {ffecha} ({dias} días antes del acta); se recomienda cargar el corte del mes.")
        malos = [b for b in bienes if (b["estado"] or "").lower() == "malo"]
        if malos:
            advert.append(f"La matriz registra {len(malos)} bien(es) en estado Malo en esta ubicación; confirme si corresponde registrar novedades.")
        meta.update(corte_id=corte_id, corte_fecha=ffecha, items_matriz=items, valor_matriz=v_mat, dep_matriz=d_mat)
        manual_val = p.get("valor_total_manual") not in (None, "")
        manual_dep = p.get("dep_acum_manual") not in (None, "")
        if manual_val:
            valor = _positivo(p["valor_total_manual"], "valor total")
        if manual_dep:
            dep = _positivo(p["dep_acum_manual"], "depreciación acumulada")
        if manual_val and abs(valor - v_mat) > 0.005:
            advert.append(f"El valor total ingresado ({dinero(valor)}) difiere del de la matriz ({dinero(v_mat)}).")
        if manual_dep and abs(dep - d_mat) > 0.005:
            advert.append(f"La depreciación ingresada ({dinero(dep)}) difiere de la de la matriz ({dinero(d_mat)}).")
        meta["valor_manual"] = bool(manual_val or manual_dep)
        indice = {b["codigo"]: b for b in bienes}
    else:
        items = int(p.get("items") or 0)
        if items <= 0:
            raise ErrorActa("Ingrese el número de ítems (mayor a cero).")
        if not resp_nombre:
            raise ErrorActa("Ingrese el nombre del responsable (custodio).")
        valor = _positivo(p.get("valor_total"), "valor total")
        dep = _positivo(p.get("dep_acum"), "depreciación acumulada")
        if dep > valor:
            raise ErrorActa("La depreciación acumulada no puede superar el valor total.")
        meta.update(valor_manual=True)
        indice = {}
        advert.append("Modo manual: no se adjunta el detalle de bienes; el anexo debe descargarse de eSByE.")

    obs_in = []
    for o in p.get("observaciones") or []:
        o = dict(o)
        cod = (o.get("codigo") or "").strip().upper()
        o["codigo"] = cod
        if cod and cod in indice:
            o["descripcion"] = indice[cod]["descripcion"]
        elif cod and modo == "matriz" and o.get("tipo") != "sobrante":
            advert.append(f"El código {cod} de una observación no consta en esta ubicación según la matriz.")
        obs_in.append(o)
    red = redactor.redactar(obs_in, ubic)
    if red["aviso"]:
        advert.append(red["aviso"])
    base_norm = []
    if p.get("incluir_normativa"):
        vistos = set()
        for t in sorted({o.get("tipo", "otro") for o in obs_in}):
            for h in normativa.orientar(t, 1):
                if h["titulo"] not in vistos:
                    vistos.add(h["titulo"])
                    base_norm.append({"titulo": h["titulo"], "texto": h["texto"], "fuente": h["fuente"]})

    adjunto = ("Como documento adjunto se encuentra la matriz descargada del sistema esByE con el detalle de los bienes verificados."
               if modo == "matriz" else
               "Los valores consignados en la presente acta fueron ingresados por el analista de bienes y bodegas.")
    resp_full = _nombre(resp_titulo, resp_nombre)
    anal_full = _nombre(analista["titulo"] or "", analista["nombre"])
    apertura = (f"En la ciudad de {s.ciudad} a los {fecha.day} días del mes de {MESES[fecha.month - 1]} de {fecha.year}, en cumplimiento a la "
                f"disposición de trabajo y contando con la presencia de {resp_full.upper()} en calidad de responsable de la ubicación {ubic}, "
                f"y de {anal_full}, {analista['cargo']}, se procede a realizar la constatación física de los bienes que se encuentran en la "
                "dependencia antes mencionada, los mismos que se detallan a continuación:")
    anio = fecha.year
    seq = int(p["secuencia"]) if p.get("secuencia") else siguiente_secuencia(anio)
    return {
        "numero": f"{seq}-{anio}", "secuencia": seq, "anio": anio, "fecha": fecha.isoformat(), "ubicacion": ubic,
        "institucion": s.institucion, "titulo": f"ACTA DE CONSTATACIÓN FÍSICA DE BIENES {ubic.upper()}",
        "apertura": apertura, "tabla": [["Ítems…", str(items)], ["Valor Total", dinero(valor)], ["Depreciación acumulada", dinero(dep)]],
        "items": items, "valor_total": valor, "dep_acum": dep, "adjunto": adjunto,
        "novedades": red["oraciones"], "novedades_modo": red["modo"], "normativa": base_norm,
        "cierre": ("Para constancia de lo actuado y en fe de conformidad y aceptación suscriben la presente acta en tres copias de igual "
                   "tenor y efecto las personas que intervienen en la presente diligencia."),
        "firmas": {"custodio": {"nombre": resp_full, "cargo": "CUSTODIO"},
                   "analista": {"nombre": anal_full, "cargo": analista["cargo"].upper()},
                   "coordinador": {"nombre": _nombre(coord["titulo"] or "", coord["nombre"]), "cargo": coord["cargo"].upper()}},
        "advertencias": advert, "meta": meta, "codigos": codigos, "observaciones": obs_in,
    }


def _positivo(v, nombre: str) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ErrorActa(f"Ingrese un {nombre} numérico.")
    if x < 0:
        raise ErrorActa(f"El {nombre} no puede ser negativo.")
    return round(x, 2)


def emitir(p: Dict) -> Dict:
    est = armar(p)
    with sesion() as c:
        if c.execute("SELECT 1 FROM actas WHERE numero=?", (est["numero"],)).fetchone():
            raise ErrorActa(f"Ya existe el acta N.° {est['numero']}. Cambie la secuencia o deje que el sistema asigne la siguiente.")
        cur = c.execute("""INSERT INTO actas(numero,anio,secuencia,fecha,corte_id,ubicacion,modo,items,valor_total,dep_acum,valor_manual,codigos,estructura)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (est["numero"], est["anio"], est["secuencia"], est["fecha"], est["meta"].get("corte_id"), est["ubicacion"],
                         est["meta"]["modo"], est["items"], est["valor_total"], est["dep_acum"], int(bool(est["meta"].get("valor_manual"))),
                         json.dumps(est["codigos"]), json.dumps(est, ensure_ascii=False)))
        est["id"] = cur.lastrowid
    return est


def listar() -> List[Dict]:
    with sesion() as c:
        return [dict(r) for r in c.execute("""SELECT id,numero,fecha,ubicacion,modo,items,valor_total,dep_acum,valor_manual,estado,creado
                                              FROM actas ORDER BY anio DESC, secuencia DESC""")]


def obtener(aid: int) -> Dict:
    with sesion() as c:
        r = c.execute("SELECT * FROM actas WHERE id=?", (aid,)).fetchone()
    if not r:
        raise ErrorActa("El acta no existe.")
    est = json.loads(r["estructura"])
    est["id"], est["estado"] = r["id"], r["estado"]
    return est


def anular(aid: int) -> None:
    with sesion() as c:
        c.execute("UPDATE actas SET estado='anulada' WHERE id=?", (aid,))
