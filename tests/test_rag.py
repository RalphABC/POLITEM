import glob
import io

import pytest
from fastapi.testclient import TestClient

from app import cortes, esbye, informes
from app.rag import chunking, validator
from app.rag.embeddings import HashingEmbedder
from app.rag.indexador import indice, reiniciar
from app.rag.llm import LLMError, LLMProvider
from app.totales import calcular, dinero

CSV = ("Código Bien,Descripción,Nombre Bodega,Custodio Actual,Cédula Custodio,Estado,Condición del Bien,Valor Contable,Valor Depreciación Acumulada\n"
       "Z-001,Laptop Dell,BODEGA X,Ana Paz,990001,Malo,En uso,1000.00,950.00\n"
       "Z-002,Mesa metálica,BODEGA X,Ana Paz,990001,Bueno,En uso,300.00,100.00\n"
       "Z-003,Silla giratoria,BODEGA X,Ana Paz,990001,Bueno,Para baja,50.00,10.00\n"
       "Z-004,Proyector Epson,BODEGA Y,Luis Mora,990002,Bueno,En uso,500.00,50.00\n")


def cargar(csv=CSV, fecha="2026-10-01", alcance="institucional"):
    r = esbye.importar(csv.encode(), "m.csv", fecha, alcance)
    indice().indexar_corte(r.corte_id)
    return r.corte_id


def test_fragmento_no_contiene_nombre_del_custodio():
    cargar()
    b = cortes.bienes_de_cedula(1, "990001")[0]
    assert "Ana Paz" not in chunking.bien_a_texto(b) and b["codigo"] in chunking.bien_a_texto(b)


def test_embeddings_hash_tolerantes_a_tildes_y_cercania():
    e = HashingEmbedder()
    v = e.embed(["computador portátil", "computador portatil", "silla de oficina"])
    assert float(v[0] @ v[1]) > 0.95 and float(v[0] @ v[1]) > float(v[0] @ v[2])


def test_totales_deterministas():
    cargar()
    t = calcular(cortes.bienes_de_cedula(1, "990001"))
    assert t["total"] == 3 and t["valor_contable"] == 1350.0 and t["dep_acum"] == 1060.0 and t["valor_libros"] == 290.0
    assert set(t["criticos"]) == {"Z-001", "Z-003"} and t["totalmente_depreciados"] == 1
    assert dinero(1234.5) == "$ 1.234,50"


def test_recuperacion_filtra_por_cedula():
    cargar()
    r = informes.generar({"tipo": "cedula", "valor": "990001"}, "totalizado")
    assert {e["codigo"] for e in r["evidencias"]} == {"Z-001", "Z-002", "Z-003"}      # nunca Z-004 (otro custodio)
    assert r["traza"]["universo"] == 3 and r["validacion"]["estado"] == "APROBADO"
    assert r["totales"]["valor_contable"] == 1350.0 and "$ 1.350,00" in r["texto"]


def test_reporte_criticos_cita_los_criticos():
    cargar()
    r = informes.generar({"tipo": "cedula", "valor": "990001"}, "criticos")
    assert "[Z-001]" in r["texto"] and "[Z-003]" in r["texto"] and r["validacion"]["criticos_omitidos"] == []


def test_reporte_por_ubicacion_y_normativa():
    cargar()
    r = informes.generar({"tipo": "ubicacion", "valor": "BODEGA X"}, "criticos")
    assert r["totales"]["total"] == 3 and r["normas"]


def test_validaciones_de_entrada():
    cargar()
    with pytest.raises(informes.ErrorInforme, match="cédula"):
        informes.generar({"tipo": "cedula", "valor": "000"}, "totalizado")
    with pytest.raises(informes.ErrorInforme, match="pregunta"):
        informes.generar({"tipo": "cedula", "valor": "990001"}, "consulta_libre")
    with pytest.raises(informes.ErrorInforme):
        informes.generar({"tipo": "ubicacion", "valor": ""}, "totalizado")


def test_validador():
    v = validator.validar("El bien [Z-001] y [Z-999] valen $ 1.000,00 y $1,000.00 y $ 77,00", {"Z-001"}, [], [1000.0], "totalizado")
    assert v.estado == "RECHAZADO" and v.citas_invalidas == ["Z-999"] and v.cifras_no_verificadas == ["$ 77.00"]
    ok = validator.validar("Ver [Z-001] por $ 1.000,00 [nota]", {"Z-001"}, ["Z-001"], [1000.0], "criticos")
    assert ok.estado == "APROBADO"
    om = validator.validar("Sin citas", {"Z-001"}, ["Z-001"], [], "criticos")
    assert om.estado == "ADVERTENCIAS" and om.criticos_omitidos == ["Z-001"]


class Alucinador(LLMProvider):
    nombre, modelo, es_nube = "falso", "alucina", False
    llamadas = 0

    def generar(self, prompt):
        Alucinador.llamadas += 1
        return "El bien [Z-777] está dañado."


class Caido(LLMProvider):
    nombre, modelo = "caido", "x"

    def generar(self, prompt):
        raise LLMError("sin conexión")


def test_reintento_y_respaldo_ante_alucinacion(monkeypatch):
    cargar()
    Alucinador.llamadas = 0
    monkeypatch.setattr(informes, "crear_llm", lambda cfg: Alucinador())
    r = informes.generar({"tipo": "cedula", "valor": "990001"}, "totalizado")
    assert Alucinador.llamadas == 2 and r["traza"]["respaldo_plantilla"] and "Z-777" not in r["texto"] and r["validacion"]["estado"] != "RECHAZADO"


def test_respaldo_si_el_modelo_cae(monkeypatch):
    cargar()
    monkeypatch.setattr(informes, "crear_llm", lambda cfg: Caido())
    r = informes.generar({"tipo": "cedula", "valor": "990001"}, "totalizado")
    assert r["traza"]["respaldo_plantilla"] and "sin conexión" in r["traza"]["aviso"]


def test_nube_no_recibe_el_nombre(monkeypatch):
    cargar()
    vistos = []

    class Nube(LLMProvider):
        nombre, modelo, es_nube = "nube", "m", True

        def generar(self, prompt):
            vistos.append(prompt.user)
            return "Resumen de [Z-001]."
    monkeypatch.setattr(informes, "crear_llm", lambda cfg: Nube())
    informes.generar({"tipo": "cedula", "valor": "990001"}, "totalizado")
    assert vistos and "Ana Paz" not in vistos[0] and "Luis Mora" not in vistos[0]


def test_base_en_memoria_equivale(monkeypatch):
    monkeypatch.setenv("VECTOR_STORE", "memoria")
    from app.config import get_settings
    get_settings.cache_clear(); reiniciar()
    cargar()
    assert indice().store.nombre.startswith("Memoria")
    r = informes.generar({"tipo": "cedula", "valor": "990001"}, "criticos")
    assert r["traza"]["base_vectorial"].startswith("Memoria") and "[Z-001]" in r["texto"]


def test_pdf_de_un_funcionario_y_corte_parcial():
    cargar()
    pdf = glob.glob("data/ejemplos/*.pdf")[0]
    ced = pdf.split("_")[-1][:-4]
    res = esbye.importar(open(pdf, "rb").read(), "doc.pdf", "2026-10-23", "parcial")
    indice().indexar_corte(res.corte_id)
    assert res.n_validas > 50 and any("cabecera" in a for a in res.advertencias)
    assert cortes.anterior_a(res.corte_id) is None                    # los parciales no se comparan
    assert cortes.corte_de_cedula(ced) == res.corte_id
    r = informes.generar({"tipo": "cedula", "valor": ced}, "totalizado")
    assert r["totales"]["total"] == res.n_validas and r["validacion"]["estado"] == "APROBADO"


def test_pdf_ilegible():
    with pytest.raises(Exception):
        esbye.importar(b"%PDF-1.4 no es un pdf", "x.pdf")


def test_api_extremo_a_extremo():
    from app.main import crear_app
    c = TestClient(crear_app())
    h = c.get("/api/salud").json()
    assert h["cortes"] == 3 and "Chroma" in h["base_vectorial"]
    est = c.get("/api/rag/estado").json()
    assert all(x["indexados"] == x["bienes"] for x in est["cortes"]) and est["fragmentos_normativa"] >= 5
    cid = c.get("/api/cortes").json()[0]["id"]
    fun = c.get(f"/api/cortes/{cid}/funcionarios").json()
    r = c.post("/api/informes", json={"ambito": {"tipo": "cedula", "valor": fun[0]["cedula"]}, "tipo": "totalizado"})
    assert r.status_code == 200
    iid = r.json()["id"]
    assert c.get(f"/api/informes/{iid}/docx").content[:2] == b"PK" and len(c.get("/api/informes").json()) == 1
    assert c.post("/api/informes", json={"ambito": {"tipo": "cedula", "valor": "x"}, "tipo": "totalizado"}).status_code == 400
    ub = c.get(f"/api/cortes/{cid}/ubicaciones").json()[0]["ubicacion"]
    a = c.post("/api/actas", json={"ubicacion": ub, "corte_id": cid, "analista_id": 1, "coordinador_id": 4, "fecha": "2026-10-23",
                                    "observaciones": [{"tipo": "faltante", "codigo": "ESP-000001"}], "incluir_normativa": True})
    assert a.status_code == 200 and a.json()["normativa"]
    pdf = glob.glob("data/ejemplos/*.pdf")[0]
    up = c.post("/api/cortes", files={"archivo": ("d.pdf", open(pdf, "rb").read(), "application/pdf")}, data={"fecha": "2026-10-23", "alcance": "parcial"})
    assert up.status_code == 200 and up.json()["diferencias"] is None and up.json()["carga"]["indexados"] > 50
    assert c.post("/api/cortes", files={"archivo": ("m.csv", b"x,y\n1,2", "text/csv")}).status_code == 400
    assert c.post("/api/rag/reindexar").status_code == 200
