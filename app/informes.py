"""Servicio de reportes inteligentes (Facade del flujo RAG completo).

Alcance → recuperación (filtro + vectores + reglas) → totales deterministas → prompt → generación → validación → (reintento | respaldo).
"""
from __future__ import annotations

import json
import re
import time
from typing import Dict, List, Optional

from . import cortes
from .config import get_settings
from .db import sesion
from .rag import prompts, retriever, validator
from .rag.llm import LLMError, TemplateLLM, crear_llm
from .rag.indexador import indice
from .totales import calcular, dinero


class ErrorInforme(ValueError):
    pass


def resolver_ambito(ambito: Dict, corte_id: Optional[int]) -> Dict:
    tipo, valor = ambito.get("tipo"), (ambito.get("valor") or "").strip()
    if tipo not in ("cedula", "ubicacion") or not valor:
        raise ErrorInforme("Indique una cédula o una ubicación.")
    if tipo == "cedula":
        corte_id = corte_id or cortes.corte_de_cedula(valor)
        if not corte_id:
            raise ErrorInforme("No hay bienes registrados para esa cédula en ninguna matriz cargada.")
        bienes = cortes.bienes_de_cedula(corte_id, valor)
        nombre = bienes[0]["custodio_nombre"] if bienes else ""
        etiqueta = f"Funcionario {nombre} (cédula {valor})"
        etiqueta_anon = f"Funcionario con cédula {valor[:3]}*******"
    else:
        corte_id = corte_id or cortes.ultimo_id()
        if not corte_id:
            raise ErrorInforme("Aún no hay una matriz cargada.")
        bienes = cortes.bienes_de(corte_id, valor, ambito.get("custodio") or None)
        etiqueta = f"Ubicación {valor}" + (f" — custodio {ambito['custodio']}" if ambito.get("custodio") else "")
        etiqueta_anon = f"Ubicación {valor}"
    if not bienes:
        raise ErrorInforme("No hay bienes para ese ámbito en el corte seleccionado.")
    with sesion() as c:
        fecha = c.execute("SELECT fecha FROM cortes WHERE id=?", (corte_id,)).fetchone()["fecha"]
    return {"corte_id": corte_id, "fecha": fecha, "bienes": bienes, "etiqueta": etiqueta, "etiqueta_anon": etiqueta_anon,
            "ambito": {"tipo": tipo, "valor": valor, "custodio": ambito.get("custodio") or ""}}


def generar(ambito: Dict, tipo: str, pregunta: str = "", corte_id: Optional[int] = None) -> Dict:
    if tipo not in prompts.TIPOS:
        raise ErrorInforme("Tipo de reporte no válido.")
    if tipo == "consulta_libre" and not pregunta.strip():
        raise ErrorInforme("Escriba la pregunta.")
    s = get_settings()
    r = resolver_ambito(ambito, corte_id)
    indice().asegurar()
    totales = calcular(r["bienes"])
    t0 = time.perf_counter()
    rec = retriever.recuperar(r["corte_id"], r["ambito"], r["bienes"], tipo, pregunta)
    t_rec = time.perf_counter() - t0
    llm = crear_llm(s)
    etiqueta = r["etiqueta_anon"] if llm.es_nube else r["etiqueta"]
    constructor = prompts.ConstructorPrompt()
    codigos = {e["codigo"] for e in rec["bienes"]}
    permitidos = [totales["valor_contable"], totales["dep_acum"], totales["valor_libros"]]
    for e in rec["bienes"]:
        permitidos += [e["bien"]["valor_contable"], e["bien"]["dep_acum"], e["bien"]["valor_libros"]]
    permitidos += [v["valor"] for v in totales["por_tipo"].values()]
    intentos, correccion, texto, val, fallback, aviso = 0, "", "", None, False, None
    t1 = time.perf_counter()
    while True:
        intentos += 1
        prompt = constructor.construir(tipo, etiqueta, totales, rec, pregunta, r["fecha"], correccion)
        try:
            texto = llm.generar(prompt)
        except LLMError as e:
            aviso, fallback = f"{e}. Se usó la plantilla determinista como respaldo.", True
            llm = TemplateLLM()
            texto = llm.generar(prompt)
        val = validator.validar(texto, codigos, totales["criticos"] if tipo == "criticos" else [], permitidos, tipo)
        if val.estado != "RECHAZADO" or intentos > s.reintentos or isinstance(llm, TemplateLLM):
            break
        correccion = "Tu respuesta citó códigos que no existen en el contexto: " + ", ".join(val.citas_invalidas) + ". Cita solo códigos del contexto."
    if val.estado == "RECHAZADO" and not isinstance(llm, TemplateLLM):
        aviso, fallback, llm = "La validación rechazó el texto del modelo; se usó la plantilla determinista.", True, TemplateLLM()
        texto = llm.generar(prompt)
        val = validator.validar(texto, codigos, totales["criticos"] if tipo == "criticos" else [], permitidos, tipo)
    t_gen = time.perf_counter() - t1
    idx = indice()
    traza = {"proveedor": llm.nombre, "modelo": llm.modelo, "embeddings": idx.embedder.nombre, "base_vectorial": idx.store.nombre,
             "candidatos": rec["candidatos"], "en_contexto": len(rec["bienes"]), "universo": totales["total"], "intentos": intentos,
             "respaldo_plantilla": fallback, "aviso": aviso, "t_recuperacion_ms": round(t_rec * 1000), "t_generacion_ms": round(t_gen * 1000)}
    evid = [{"codigo": e["codigo"], "texto": e["texto"], "score": e["score"], "componentes": e["componentes"]} for e in rec["bienes"]]
    contenido = {"titulo": prompts.TIPOS[tipo], "ambito": r["ambito"], "etiqueta": r["etiqueta"], "corte_id": r["corte_id"], "fecha_corte": r["fecha"],
                 "texto": texto, "totales": totales, "evidencias": evid, "normas": rec["normas"], "validacion": val.dict(), "traza": traza,
                 "pregunta": pregunta}
    with sesion() as c:
        cur = c.execute("INSERT INTO informes(corte_id,tipo,ambito,etiqueta,pregunta,contenido) VALUES(?,?,?,?,?,?)",
                        (r["corte_id"], tipo, json.dumps(r["ambito"]), r["etiqueta"], pregunta, json.dumps(contenido, ensure_ascii=False)))
        contenido["id"] = cur.lastrowid
    return contenido


def listar() -> List[Dict]:
    with sesion() as c:
        return [dict(r) for r in c.execute("SELECT id,creado,tipo,etiqueta,pregunta FROM informes ORDER BY id DESC")]


def obtener(iid: int) -> Dict:
    with sesion() as c:
        r = c.execute("SELECT * FROM informes WHERE id=?", (iid,)).fetchone()
    if not r:
        raise ErrorInforme("El reporte no existe.")
    d = json.loads(r["contenido"])
    d["id"] = r["id"]
    return d
