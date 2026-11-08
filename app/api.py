"""API REST (FastAPI)."""
from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from . import actas, cortes, documento, esbye, informes, normativa, redactor
from .rag.indexador import indice, reiniciar
from .rag.llm import crear_llm
from .config import BASE, get_settings
from .db import sesion

router = APIRouter(prefix="/api")
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _err(e: Exception):
    raise HTTPException(status_code=400, detail=str(e))


@router.get("/salud")
def salud() -> Dict:
    s = get_settings()
    idx = indice()
    cs = cortes.listar()
    with sesion() as c:
        na = c.execute("SELECT COUNT(*) FROM actas").fetchone()[0]
    return {"estado": "ok", "cortes": len(cs), "ultimo_corte": next((c for c in cs if c["alcance"] == "institucional"), cs[0] if cs else None), "actas": na,
            "redaccion": s.llm_provider, "base_vectorial": idx.store.nombre, "embeddings": idx.embedder.nombre, "siguiente_numero": actas.siguiente_secuencia(__import__("datetime").date.today().year)}


@router.get("/tipos-observacion")
def tipos() -> Dict:
    return redactor.TIPOS


# ---- matriz / cortes
@router.get("/cortes")
def get_cortes() -> List[Dict]:
    return cortes.listar()


@router.post("/cortes")
async def subir_corte(archivo: UploadFile = File(...), fecha: Optional[str] = Form(None), alcance: str = Form("institucional")) -> Dict:
    try:
        res = esbye.importar(await archivo.read(), archivo.filename or "matriz.csv", fecha, alcance)
    except ValueError as e:
        _err(e)
    except Exception as e:  # PDF dañado, etc.
        raise HTTPException(400, f"No se pudo leer el archivo: {e}")
    res.indexados = indice().indexar_corte(res.corte_id)
    previo = cortes.anterior_a(res.corte_id)
    return {"carga": res.dict(), "diferencias": cortes.comparar(res.corte_id, previo) if previo else None}


@router.post("/cortes/ejemplo")
def cargar_ejemplo() -> Dict:
    """Carga los tres cortes ficticios incluidos (solo si aún no hay datos)."""
    if cortes.listar():
        raise HTTPException(400, "Ya hay matrices cargadas.")
    for f in sorted((BASE / "data" / "matrices").glob("matriz_esbye_*.csv")):
        r = esbye.importar(f.read_bytes(), f.name, f.stem.replace("matriz_esbye_", ""))
        indice().indexar_corte(r.corte_id)
    return {"cortes": len(cortes.listar())}


@router.get("/cortes/{cid}/diferencias")
def diferencias(cid: int, contra: Optional[int] = None) -> Dict:
    previo = contra or cortes.anterior_a(cid)
    if not previo:
        raise HTTPException(404, "No hay un corte anterior para comparar.")
    return cortes.comparar(cid, previo)


@router.get("/cortes/{cid}/ubicaciones")
def ubicaciones(cid: int) -> List[Dict]:
    return cortes.ubicaciones(cid)


@router.get("/cortes/{cid}/ubicaciones/custodios")
def custodios(cid: int, ubicacion: str) -> List[Dict]:
    return cortes.custodios_de(cid, ubicacion)


@router.get("/cortes/{cid}/bienes")
def bienes(cid: int, ubicacion: str, custodio: Optional[str] = None) -> List[Dict]:
    return cortes.bienes_de(cid, ubicacion, custodio)


# ---- personal (analistas / coordinación)
class Persona(BaseModel):
    rol: str
    titulo: str = ""
    nombre: str
    cargo: str


@router.get("/personal")
def get_personal() -> List[Dict]:
    with sesion() as c:
        return [dict(r) for r in c.execute("SELECT * FROM personal WHERE activo=1 ORDER BY rol, nombre")]


@router.post("/personal")
def crear_persona(p: Persona) -> Dict:
    if p.rol not in ("analista", "coordinador") or not p.nombre.strip() or not p.cargo.strip():
        raise HTTPException(400, "Rol, nombre y cargo son obligatorios.")
    with sesion() as c:
        cur = c.execute("INSERT INTO personal(rol,titulo,nombre,cargo) VALUES(?,?,?,?)", (p.rol, p.titulo.strip(), p.nombre.strip(), p.cargo.strip()))
    return {"id": cur.lastrowid}


@router.delete("/personal/{pid}")
def borrar_persona(pid: int) -> Dict:
    with sesion() as c:
        c.execute("UPDATE personal SET activo=0 WHERE id=?", (pid,))
    return {"ok": True}


# ---- actas
@router.post("/actas/previa")
def previa(p: Dict) -> Dict:
    try:
        return actas.armar(p)
    except actas.ErrorActa as e:
        _err(e)


@router.post("/actas")
def emitir(p: Dict) -> Dict:
    try:
        return actas.emitir(p)
    except actas.ErrorActa as e:
        _err(e)


@router.get("/actas")
def listar_actas() -> List[Dict]:
    return actas.listar()


@router.get("/actas/{aid}")
def get_acta(aid: int) -> Dict:
    try:
        return actas.obtener(aid)
    except actas.ErrorActa as e:
        raise HTTPException(404, str(e))


@router.post("/actas/{aid}/anular")
def anular(aid: int) -> Dict:
    actas.anular(aid)
    return {"ok": True}


@router.get("/actas/{aid}/docx")
def acta_docx(aid: int) -> Response:
    est = get_acta(aid)
    return Response(documento.acta_docx(est), media_type=DOCX,
                    headers={"Content-Disposition": f'attachment; filename="Acta_{est["numero"]}.docx"'})


@router.get("/actas/{aid}/anexo")
def acta_anexo(aid: int) -> Response:
    est = get_acta(aid)
    if est["meta"]["modo"] != "matriz":
        raise HTTPException(400, "El acta manual no tiene anexo generado.")
    return Response(documento.anexo_xlsx(est), media_type=XLSX,
                    headers={"Content-Disposition": f'attachment; filename="Anexo_Acta_{est["numero"]}.xlsx"'})


@router.post("/actas/previa/docx")
def previa_docx(p: Dict) -> Response:
    try:
        est = actas.armar(p)
    except actas.ErrorActa as e:
        _err(e)
    return Response(documento.acta_docx(est), media_type=DOCX, headers={"Content-Disposition": 'attachment; filename="Borrador_acta.docx"'})


# ---- funcionarios y reportes inteligentes (RAG)
@router.get("/cortes/{cid}/funcionarios")
def funcionarios(cid: int) -> List[Dict]:
    return cortes.funcionarios(cid)


@router.post("/informes")
def generar_informe(p: Dict) -> Dict:
    try:
        return informes.generar(p.get("ambito") or {}, p.get("tipo", "totalizado"), p.get("pregunta", ""), p.get("corte_id"))
    except informes.ErrorInforme as e:
        _err(e)


@router.get("/informes")
def listar_informes() -> List[Dict]:
    return informes.listar()


@router.get("/informes/{iid}")
def get_informe(iid: int) -> Dict:
    try:
        return informes.obtener(iid)
    except informes.ErrorInforme as e:
        raise HTTPException(404, str(e))


@router.get("/informes/{iid}/docx")
def informe_docx(iid: int) -> Response:
    inf = get_informe(iid)
    return Response(documento.informe_docx(inf), media_type=DOCX, headers={"Content-Disposition": f'attachment; filename="Reporte_{iid}.docx"'})


@router.get("/rag/estado")
def rag_estado() -> Dict:
    idx = indice()
    return {**idx.estado(), "generacion": crear_llm(get_settings()).estado(), "ultima_indexacion": idx.ultima_indexacion}


@router.post("/rag/reindexar")
def reindexar() -> Dict:
    idx = indice()
    n = idx.indexar_normativa()
    for c in cortes.listar():
        idx.indexar_corte(c["id"])
    return {"normativa": n, "cortes": len(cortes.listar())}


# ---- observaciones
@router.post("/observaciones/orientar")
def orientar(p: Dict) -> List[Dict]:
    return normativa.orientar(p.get("tipo", "otro"), 2)


@router.get("/bienes/buscar")
def buscar(cid: int, q: str, ubicacion: Optional[str] = None) -> List[Dict]:
    sql, par = "SELECT codigo,descripcion,estado,ubicacion,custodio_nombre FROM bienes WHERE corte_id=? AND (codigo LIKE ? OR descripcion LIKE ?)", [cid, f"%{q}%", f"%{q}%"]
    if ubicacion:
        sql += " AND ubicacion=?"; par.append(ubicacion)
    with sesion() as c:
        return [dict(r) for r in c.execute(sql + " ORDER BY codigo LIMIT 15", par)]
