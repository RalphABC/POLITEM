"""Genera un documento de ejemplo por funcionario (PDF y CSV), como el que se descarga de eSByE buscando por cédula. Requiere reportlab."""
import csv
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

BASE = Path(__file__).resolve().parent.parent
src = BASE / "data" / "matrices" / "matriz_esbye_2026-10-23.csv"
filas = list(csv.DictReader(src.open(encoding="utf-8-sig")))
ced = sys.argv[1] if len(sys.argv) > 1 else None
por = {}
for f in filas:
    por.setdefault(f["Cédula Custodio"], []).append(f)
ced = ced or max(por, key=lambda k: len(por[k]))
mis = por[ced]
out = BASE / "data" / "ejemplos"
out.mkdir(parents=True, exist_ok=True)
cols = ["Código Bien", "Descripción", "Estado", "Nombre Bodega", "Fecha Ingreso", "Valor Contable", "Valor Depreciación Acumulada", "Valor Libros"]
with (out / f"documento_funcionario_{ced}.csv").open("w", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh); w.writerow(cols + ["Cédula Custodio", "Custodio Actual"])
    for f in mis:
        w.writerow([f[c] for c in cols] + [f["Cédula Custodio"], f["Custodio Actual"]])
est = getSampleStyleSheet()
doc = SimpleDocTemplate(str(out / f"documento_funcionario_{ced}.pdf"), pagesize=landscape(A4), leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24)
datos = [cols] + [[f["Código Bien"], f["Descripción"][:34], f["Estado"], f["Nombre Bodega"], f["Fecha Ingreso"], f["Valor Contable"], f["Valor Depreciación Acumulada"], f["Valor Libros"]] for f in mis]
t = Table(datos, repeatRows=1)
t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1b2733")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), .3, colors.grey),
                       ("FONTSIZE", (0, 0), (-1, -1), 7.5), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f5f7")])]))
doc.build([Paragraph("Sistema de Bienes y Existencias — Reporte de bienes por custodio (EJEMPLO FICTICIO)", est["Title"]),
           Paragraph(f"Cédula/RUC: {ced}", est["Normal"]), Paragraph(f"Custodio: {mis[0]['Custodio Actual']}", est["Normal"]), Spacer(1, 8), t])
print(ced, len(mis))
