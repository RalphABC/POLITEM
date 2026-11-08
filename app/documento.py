"""Salida del acta en Word (.docx) y del anexo con el detalle de bienes en Excel (.xlsx)."""
from __future__ import annotations

import io
from typing import Dict

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from . import cortes
from .config import get_settings
from .db import sesion


def _campo(par, codigo: str) -> None:
    r = par.add_run()
    for tipo, txt in (("begin", None), (None, codigo), ("end", None)):
        if tipo:
            e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), tipo)
        else:
            e = OxmlElement("w:instrText"); e.set(qn("xml:space"), "preserve"); e.text = txt
        r._r.append(e)


def _p(doc, texto="", *, negrita=False, alinear="j", tam=11, antes=0, despues=8, cursiva=False):
    par = doc.add_paragraph()
    par.alignment = {"j": WD_ALIGN_PARAGRAPH.JUSTIFY, "c": WD_ALIGN_PARAGRAPH.CENTER, "l": WD_ALIGN_PARAGRAPH.LEFT}[alinear]
    par.paragraph_format.space_before, par.paragraph_format.space_after = Pt(antes), Pt(despues)
    r = par.add_run(texto)
    r.bold, r.italic, r.font.size = negrita, cursiva, Pt(tam)
    return par


def acta_docx(est: Dict) -> bytes:
    s = get_settings()
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.59), Cm(27.94)
    sec.left_margin = sec.right_margin = Cm(2.5)
    sec.top_margin, sec.bottom_margin = Cm(1.5), Cm(2)
    st = doc.styles["Normal"]
    st.font.name, st.font.size = "Arial", Pt(11)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
    if s.logo.exists():
        pl = doc.add_paragraph(); pl.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pl.add_run().add_picture(str(s.logo), width=Cm(14.5))
    _p(doc, est["titulo"], negrita=True, alinear="c", antes=6, despues=4)
    _p(doc, f"ACTA N. ° {est['numero']}", negrita=True, alinear="c", despues=12)
    _p(doc, est["apertura"], despues=10)
    t = doc.add_table(rows=0, cols=2)
    t.style, t.alignment, t.autofit = "Table Grid", WD_TABLE_ALIGNMENT.CENTER, False
    for k, v in est["tabla"]:
        cel = t.add_row().cells
        cel[0].width, cel[1].width = Cm(9), Cm(6)
        cel[0].text, cel[1].text = k, v
        cel[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    _p(doc, "", despues=4)
    _p(doc, est["adjunto"], despues=10)
    if est.get("novedades"):
        _p(doc, "Novedades constatadas:", negrita=True, despues=4)
        for n in est["novedades"]:
            par = doc.add_paragraph(style="List Number")
            par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            par.add_run(n)
    if est.get("normativa"):
        _p(doc, "Base normativa de referencia:", negrita=True, despues=4, antes=6)
        for n in est["normativa"]:
            par = doc.add_paragraph(style="List Bullet"); par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            par.add_run(n["titulo"] + ". ").bold = True
            par.add_run(n["texto"])
    f = est["firmas"]
    for par in (_p(doc, est["cierre"], antes=6, despues=26), _p(doc, f["custodio"]["nombre"], alinear="c", despues=0, negrita=True),
                _p(doc, f["custodio"]["cargo"], alinear="c", despues=30)):
        par.paragraph_format.keep_with_next = True
    t2 = doc.add_table(rows=1, cols=2)
    t2.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
    for cel, k in zip(t2.rows[0].cells, ("analista", "coordinador")):
        cel.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        cel.paragraphs[0].add_run(f[k]["nombre"]).bold = True
        cel.paragraphs[0].paragraph_format.space_after = Pt(0)
        q = cel.add_paragraph(f[k]["cargo"]); q.alignment = WD_ALIGN_PARAGRAPH.CENTER
        q.paragraph_format.space_after = Pt(0)
    pie = sec.footer.paragraphs[0]
    pie.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    pie.add_run("P á g i n a ").font.size = Pt(8)
    _campo(pie, "PAGE")
    pie.add_run(" | ").font.size = Pt(8)
    _campo(pie, "NUMPAGES")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def anexo_xlsx(est: Dict) -> bytes:
    """Matriz de bienes verificados (corte usado) y novedades registradas."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Bienes verificados"
    ws.append([f"Anexo del acta N.° {est['numero']} — {est['ubicacion']}"])
    ws["A1"].font = Font(bold=True, size=12)
    ws.append([f"Fuente: matriz de eSByE, corte {est['meta'].get('corte_fecha', '—')}. DEMO con datos ficticios."])
    ws.append([])
    cab = ["Código", "Descripción", "Marca", "Modelo", "Serie", "Estado", "Custodio", "Valor contable", "Dep. acumulada", "Valor en libros"]
    ws.append(cab)
    for c in ws[4]:
        c.font, c.fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="0F4C5C")
    cod = set(est.get("codigos") or [])
    with sesion() as c:
        filas = [dict(r) for r in c.execute("SELECT * FROM bienes WHERE corte_id=? AND ubicacion=? ORDER BY codigo",
                                           (est["meta"].get("corte_id"), est["ubicacion"]))] if cod else []
    filas = [b for b in filas if b["codigo"] in cod]
    for b in filas:
        ws.append([b["codigo"], b["descripcion"], b["marca"], b["modelo"], b["serie"], b["estado"], b["custodio_nombre"],
                   b["valor_contable"], b["dep_acum"], b["valor_libros"]])
    ini, fin = 5, 4 + len(filas)
    ws.append(["TOTAL", f"{len(filas)} ítems", "", "", "", "", "", f"=SUM(H{ini}:H{fin})", f"=SUM(I{ini}:I{fin})", f"=SUM(J{ini}:J{fin})"])
    for c in ws[ws.max_row]:
        c.font = Font(bold=True)
    for fila in ws.iter_rows(min_row=5, min_col=8, max_col=10):
        for c in fila:
            c.number_format = '#,##0.00'
    for i, w in enumerate([14, 34, 14, 18, 16, 10, 24, 14, 14, 14], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A5"
    if est.get("novedades"):
        w2 = wb.create_sheet("Novedades")
        w2.append(["N.°", "Tipo", "Código", "Detalle / lugar", "Nota del analista", "Redacción en el acta"])
        for c in w2[1]:
            c.font = Font(bold=True)
        for i, (o, txt) in enumerate(zip(est.get("observaciones") or [], est["novedades"]), 1):
            w2.append([i, o.get("tipo"), o.get("codigo"), o.get("detalle"), o.get("nota"), txt])
        for i, w in enumerate([6, 20, 14, 28, 36, 80], 1):
            w2.column_dimensions[get_column_letter(i)].width = w
            for c in w2[get_column_letter(i)]:
                c.alignment = Alignment(wrap_text=True, vertical="top")
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def informe_docx(inf: Dict) -> bytes:
    """Reporte inteligente en Word: texto, cifras verificadas, evidencias y validación."""
    import re
    from .totales import dinero
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name, st.font.size = "Arial", Pt(10.5)
    sec = doc.sections[0]
    sec.left_margin = sec.right_margin = Cm(2.2)
    t = doc.add_paragraph(); t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    t.add_run(get_settings().institucion).bold = True
    t2 = doc.add_paragraph(); t2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    t2.add_run("Reporte generado con apoyo de RAG (DEMO — datos ficticios)").italic = True
    doc.add_heading(inf["titulo"], level=1)
    doc.add_paragraph(f"Ámbito: {inf['etiqueta']}\nCorte de la matriz: {inf['fecha_corte']}" + (f"\nPregunta: {inf['pregunta']}" if inf.get("pregunta") else ""))

    def runs(par, txt):
        pos = 0
        for m in re.finditer(r"\*\*(.+?)\*\*", txt):
            par.add_run(txt[pos:m.start()]); par.add_run(m.group(1)).bold = True; pos = m.end()
        par.add_run(txt[pos:])

    for ln in inf["texto"].splitlines():
        ln = ln.rstrip()
        if not ln:
            continue
        if ln.startswith("### "):
            doc.add_heading(ln[4:], level=3)
        elif ln.startswith("## "):
            doc.add_heading(ln[3:], level=2)
        elif ln.startswith("- "):
            runs(doc.add_paragraph(style="List Bullet"), ln[2:])
        elif re.match(r"^\d+\.\s", ln):
            runs(doc.add_paragraph(style="List Number"), re.sub(r"^\d+\.\s", "", ln))
        else:
            runs(doc.add_paragraph(), ln)
    t_ = inf["totales"]
    doc.add_heading("Cifras verificadas (calculadas por el sistema)", level=2)
    tb = doc.add_table(rows=0, cols=2); tb.style = "Table Grid"
    for k, v in (("Bienes registrados", str(t_["total"])), ("Valor contable", dinero(t_["valor_contable"])),
                 ("Depreciación acumulada", dinero(t_["dep_acum"])), ("Valor en libros", dinero(t_["valor_libros"])),
                 ("Bienes críticos", str(t_["n_criticos"])), ("Totalmente depreciados", str(t_["totalmente_depreciados"]))):
        c = tb.add_row().cells; c[0].text, c[1].text = k, v
    v = inf["validacion"]
    doc.add_heading("Trazabilidad", level=2)
    tr = inf["traza"]
    doc.add_paragraph(f"Validación: {v['estado']}. " + " ".join(v["mensajes"]))
    doc.add_paragraph(f"Generación: {tr['proveedor']} ({tr['modelo']}) · Embeddings: {tr['embeddings']} · Base vectorial: {tr['base_vectorial']} · "
                      f"Bienes en contexto: {tr['en_contexto']} de {tr['universo']}.")
    buf = io.BytesIO(); doc.save(buf)
    return buf.getvalue()
