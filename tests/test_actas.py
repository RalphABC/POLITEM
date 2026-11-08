import io
import json
from datetime import date
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app import actas, cortes, documento, esbye, redactor
from app.config import BASE

CSV1 = ("Código Bien,Descripción,Nombre Bodega,Custodio Actual,Cédula Custodio,Estado,Valor Contable,Valor Depreciación Acumulada,Extra\n"
        "A-001,Laptop,BODEGA X,Ana Paz,990001,Bueno,\"1.200,50\",\"400,00\",z\n"
        "A-002,Mesa,BODEGA X,Ana Paz,990001,Malo,300.00,100.00,z\n"
        "A-003,Silla,BODEGA Y,Luis Mora,990002,Bueno,$ 50,10,z\n"
        ",Sin código,BODEGA X,Ana Paz,990001,Bueno,10,1,z\n"
        "A-001,Duplicado,BODEGA X,Ana Paz,990001,Bueno,10,1,z\n")
CSV2 = CSV1.replace("A-003,Silla,BODEGA Y,Luis Mora,990002", "A-003,Silla,BODEGA X,Ana Paz,990001") + "A-004,Monitor,BODEGA X,Ana Paz,990001,Bueno,200,20,z\n"


def cargar(csv, fecha):
    return esbye.importar(csv.encode("utf-8"), "m.csv", fecha)


def base(**k):
    p = {"ubicacion": "BODEGA X", "analista_id": 1, "coordinador_id": 4, "fecha": "2026-10-23"}
    p.update(k)
    return p


def test_importacion_alias_numeros_y_rechazos():
    r = cargar(CSV1, "2026-10-01")
    assert r.n_validas == 3 and len(r.rechazos) == 2 and "Extra" in r.sin_mapear
    b = {x["codigo"]: x for x in cortes.bienes_de(r.corte_id, "BODEGA X") + cortes.bienes_de(r.corte_id, "BODEGA Y")}
    assert b["A-001"]["valor_contable"] == 1200.50 and b["A-001"]["dep_acum"] == 400.0
    assert b["A-003"]["valor_contable"] == 50.0
    assert b["A-001"]["valor_libros"] == 800.5


def test_columnas_obligatorias():
    with pytest.raises(ValueError, match="Faltan columnas"):
        esbye.importar(b"a,b\n1,2\n", "x.csv")


@pytest.mark.parametrize("v,esp", [("1.234,56", 1234.56), ("1,234.56", 1234.56), ("$ 12,5", 12.5), ("1234", 1234.0), ("abc", None)])
def test_numero(v, esp):
    assert esbye.numero(v) == esp


def test_cortes_y_diferencias():
    a, b = cargar(CSV1, "2026-09-01"), cargar(CSV2, "2026-10-01")
    d = cortes.comparar(b.corte_id, a.corte_id)
    assert [x["codigo"] for x in d["altas"]] == ["A-004"] and not d["bajas"]
    assert d["traspasos"][0]["codigo"] == "A-003" and d["reubicaciones"][0]["codigo"] == "A-003"
    assert cortes.anterior_a(b.corte_id) == a.corte_id and cortes.ultimo_id() == b.corte_id


def test_acta_cifras_vienen_de_la_matriz():
    cargar(CSV1, "2026-10-20")
    e = actas.armar(base())
    assert e["items"] == 2 and e["valor_total"] == 1500.5 and e["dep_acum"] == 500.0
    assert e["tabla"][1][1] == "$ 1.500,50"
    assert "BODEGA X" in e["titulo"] and e["numero"] == "1-2026"
    assert "ANA PAZ" in e["apertura"] and "Riobamba" in e["apertura"]
    assert any("estado Malo" in a for a in e["advertencias"])


def test_modo_manual_y_validaciones():
    e = actas.armar(base(modo="manual", items=44, valor_total=19443.77, dep_acum=14372.76, responsable_nombre="Marcelo Velasco", responsable_titulo="Ing.", secuencia=524, fecha="2026-07-16"))
    assert e["numero"] == "524-2026" and "16 días del mes de julio de 2026" in e["apertura"] and "ING. MARCELO VELASCO" in e["apertura"]
    assert e["tabla"][2][1] == "$ 14.372,76"
    with pytest.raises(actas.ErrorActa, match="no puede superar"):
        actas.armar(base(modo="manual", items=1, valor_total=10, dep_acum=11, responsable_nombre="X"))
    with pytest.raises(actas.ErrorActa, match="ítems"):
        actas.armar(base(modo="manual", items=0, valor_total=10, dep_acum=1, responsable_nombre="X"))
    with pytest.raises(actas.ErrorActa, match="analista"):
        actas.armar(base(modo="manual", analista_id=None, items=1, valor_total=1, dep_acum=0, responsable_nombre="X"))
    with pytest.raises(actas.ErrorActa, match="ubicación"):
        actas.armar(base(ubicacion=""))


def test_correccion_manual_de_valores_advierte():
    cargar(CSV1, "2026-10-20")
    e = actas.armar(base(valor_total_manual=1600, dep_acum_manual=500))
    assert e["valor_total"] == 1600 and e["meta"]["valor_manual"] and any("difiere" in a for a in e["advertencias"])


def test_numeracion_secuencial_y_duplicados():
    cargar(CSV1, "2026-10-20")
    assert actas.emitir(base())["numero"] == "1-2026"
    assert actas.emitir(base())["numero"] == "2-2026"
    with pytest.raises(actas.ErrorActa, match="Ya existe"):
        actas.emitir(base(secuencia=2))
    assert len(actas.listar()) == 2
    actas.anular(1)
    assert actas.obtener(1)["estado"] == "anulada"


def test_observaciones_plantilla_y_normativa():
    cargar(CSV1, "2026-10-20")
    e = actas.armar(base(observaciones=[{"tipo": "faltante", "codigo": "a-002"}, {"tipo": "mal_estado", "codigo": "A-001", "detalle": "oficina 3", "nota": "no enciende"}],
                         incluir_normativa=True))
    assert "A-002 (Mesa)" in e["novedades"][0] and "bien faltante" in e["novedades"][0]
    assert "oficina 3" in e["novedades"][1] and "no enciende" in e["novedades"][1]
    assert e["normativa"] and all(n["titulo"] for n in e["normativa"])


def test_ollama_descartado_si_altera_codigos(monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    get_settings.cache_clear()

    class R:
        def __init__(self, t): self.t = t
        def raise_for_status(self): pass
        def json(self): return {"message": {"content": self.t}}
    obs = [{"tipo": "faltante", "codigo": "A-002", "descripcion": "Mesa"}]
    monkeypatch.setattr(redactor.httpx, "post", lambda *a, **k: R("El bien A-999 no fue hallado."))
    r = redactor.redactar(obs, "BODEGA X")
    assert r["modo"] == "plantilla" and "A-002" in r["oraciones"][0] and r["aviso"]
    monkeypatch.setattr(redactor.httpx, "post", lambda *a, **k: R("Se informa que el bien con código A-002 (Mesa) no fue hallado en BODEGA X."))
    r = redactor.redactar(obs, "BODEGA X")
    assert r["modo"] == "ollama"
    get_settings.cache_clear()


def test_docx_y_anexo():
    cargar(CSV1, "2026-10-20")
    e = actas.emitir(base(observaciones=[{"tipo": "faltante", "codigo": "A-002"}]))
    est = actas.obtener(e["id"])
    d = Document(io.BytesIO(documento.acta_docx(est)))
    txt = "\n".join(p.text for p in d.paragraphs) + "\n".join(c.text for t in d.tables for r in t.rows for c in r.cells)
    assert "ACTA N. ° 1-2026" in txt and "$ 1.500,50" in txt and "CUSTODIO" in txt and "COORDINADORA DE BIENES Y BODEGAS" in txt and "bien faltante" in txt
    wb = load_workbook(io.BytesIO(documento.anexo_xlsx(est)))
    ws = wb["Bienes verificados"]
    cods = [r[0].value for r in ws.iter_rows(min_row=5) if r[0].value and str(r[0].value).startswith("A-")]
    assert cods == ["A-001", "A-002"] and "Novedades" in wb.sheetnames
    assert "SUM(H5:H6)" in str(ws["H7"].value)


