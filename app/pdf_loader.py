"""Lectura de documentos PDF de eSByE (tablas con encabezado). No aplica OCR: el PDF debe tener texto seleccionable."""
from __future__ import annotations

import io
import re
from typing import Dict, Tuple

import pandas as pd


def leer_pdf(contenido: bytes) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """Devuelve (tabla, metadatos). Los metadatos intentan capturar cédula y custodio de la cabecera del documento."""
    import pdfplumber

    filas, cab, meta, texto_total = [], None, {}, []
    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        for pag in pdf.pages:
            texto_total.append(pag.extract_text() or "")
            for tabla in pag.extract_tables():
                for fila in tabla:
                    fila = [(c or "").replace("\n", " ").strip() for c in fila]
                    if not any(fila):
                        continue
                    if cab is None:
                        cab = fila
                    elif fila == cab:
                        continue            # encabezado repetido en cada página
                    else:
                        filas.append(fila)
    if cab is None or not filas:
        raise ValueError("No se encontraron tablas en el PDF. Si es un documento escaneado (imagen) no se puede leer; "
                         "descargue el reporte de eSByE en Excel o CSV.")
    ancho = len(cab)
    filas = [(f + [""] * ancho)[:ancho] for f in filas]
    txt = "\n".join(texto_total)
    m = re.search(r"(?:c[eé]dula|ruc|identificaci[oó]n)[^\d]{0,25}(\d{10,13})", txt, re.I)
    if m:
        meta["cedula"] = m.group(1)
    m = re.search(r"custodio[^:\n]{0,15}:\s*([^\n]+?)(?:\s{2,}|\n|$)", txt, re.I)
    if m:
        meta["custodio"] = m.group(1).strip()
    return pd.DataFrame(filas, columns=cab), meta
