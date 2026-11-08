"""Genera el diagrama técnico (HTML con SVG) para ingenieros en sistemas."""
B = {}
def box(i, x, y, w, h, t, body="", c="#1f6fb2", num=None, dark=False):
    B[i] = dict(x=x, y=y, w=w, h=h, t=t, body=body, c=c, num=num, dark=dark)
def pt(i, side):
    b = B[i]
    return {"l": (b["x"], b["y"] + b["h"] / 2), "r": (b["x"] + b["w"], b["y"] + b["h"] / 2), "t": (b["x"] + b["w"] / 2, b["y"]), "b": (b["x"] + b["w"] / 2, b["y"] + b["h"])}[side]
A = []
def arrow(a, sa, b, sb, label="", c="#55616d", dash=False, via=None):
    A.append((a, sa, b, sb, label, c, dash, via))

# ---------------- INGESTA
box("f", 40, 160, 220, 140, "Archivo de eSByE", "CSV · XLSX · PDF con texto\nmatriz institucional o\ndocumento de un funcionario", "#8a5200")
box("ad", 310, 160, 310, 140, "Adapter · esbye.py", "alias de columnas · números y fechas\nrechazos · alcance (institucional|parcial)\npdf_loader: pdfplumber (tablas + cabecera)", "#1f6fb2")
box("db", 670, 160, 250, 140, "SQLite", "cortes · bienes (por corte)\npersonal · actas · informes\nvalores tal como vienen de eSByE", "#1d7a46")
box("ch", 970, 160, 300, 140, "Chunking", "1 bien = 1 fragmento (sin nombre\ndel custodio) con metadatos\n1 sección de norma = 1 fragmento", "#7b3fa0")
box("em", 1320, 160, 300, 140, "Embedder · Strategy", "Hashing de n-gramas (1024 d, léxico)\no Ollama nomic-embed-text (semántico)\nFactory con respaldo automático", "#7b3fa0")
box("vs", 1670, 160, 290, 140, "VectorStore · Strategy", "ChromaDB persistente (coseno)\no memoria NumPy · metadatos:\ntipo, corte_id, cédula, ubicación", "#b3261e")
box("df", 670, 322, 250, 66, "cortes.comparar()", "altas · bajas · traspasos", "#1d7a46")

# ---------------- CONSULTA RAG
box("ui", 40, 470, 230, 170, "SPA (HTML + JS)", "Reporte inteligente:\námbito = cédula | ubicación\ntipo de reporte o pregunta libre\nchips de cita → evidencia", "#8a5200")
box("api", 310, 470, 210, 170, "API REST · FastAPI", "POST /api/informes\nGET  /api/informes/{id}\nGET  …/docx\nGET  /api/rag/estado", "#1f6fb2")
box("s1", 560, 460, 250, 115, "Resolver ámbito", "cédula → corte que la contiene\nubicación (+custodio) → corte\nlee los bienes de SQLite", "#1d7a46", "1")
box("s2", 560, 595, 250, 125, "Totales (código)", "Σ valor contable · Σ dep. acum.\nvalor en libros · por estado\ncríticos · tot. depreciados", "#1d7a46", "2")
box("s3", 850, 460, 310, 250, "Retriever híbrido", "1) filtro obligatorio por metadatos\n    {corte_id, cédula | ubicación}\n2) similitud coseno en la base vectorial\n3) reglas de negocio (crítico, depreciado)\nscore = .55 sem. + .35 regla + .10 cód.\nlos críticos siempre entran al contexto\n+ normativa (tipo = norma, top-k)", "#b3261e", "3")
box("s4", 1200, 460, 270, 115, "PromptBuilder", "reglas anti-alucinación\nDATOS VERIFICADOS + contexto\ncon códigos citables [ESP-…]", "#7b3fa0", "4")
box("s5", 1200, 595, 270, 125, "LLMProvider · Strategy", "plantilla | Ollama | Anthropic | OpenAI\nnube: sin nombre; cédula enmascarada", "#7b3fa0", "5")
box("s6", 1520, 460, 270, 115, "Validator", "citas ∈ contexto\ncifras ∈ montos permitidos\ncríticos mencionados", "#b3261e", "6")
box("s7", 1520, 595, 270, 115, "Reintento → respaldo", "si RECHAZADO: corrige y reintenta\nsi persiste: plantilla determinista", "#b3261e", "7")
box("out", 1830, 460, 130, 250, "Salida", "texto\n+ cifras\n+ evidencias\n+ validación\n+ traza\n→ tabla informes\n→ Word", "#1d7a46", "8")

# ---------------- ACTA
box("ua", 40, 830, 230, 160, "SPA · Acta", "ubicación · custodio\nanalista · coordinación\nfecha · N.° · novedades\nmodo manual", "#8a5200")
box("as", 310, 830, 320, 160, "ActaService · Facade", "armar(): cifras de la matriz (Σ) o\nmanuales · advertencias (corte antiguo,\nvalores distintos, custodio ausente)\nemitir(): N.° secuencial único", "#1f6fb2")
box("rd", 690, 826, 290, 90, "redactor · Strategy", "novedades: plantilla | Ollama\n(se descarta si altera códigos)", "#7b3fa0")
box("no", 690, 926, 290, 86, "normativa.orientar()", "consulta vectorial tipo = norma\nsegún el tipo de novedad", "#b3261e")
box("dc", 1040, 830, 300, 160, "documento.py", "Acta .docx: texto fijo, logo, firmas\nAnexo .xlsx: bienes verificados,\nΣ con fórmulas y novedades", "#1d7a46")
box("ac", 1400, 830, 260, 160, "SQLite · actas", "N.° AAAA-secuencia único\nestructura JSON del acta\nestado: emitida | anulada", "#1d7a46")

# ---------------- flechas
arrow("f", "r", "ad", "l")
arrow("ad", "r", "db", "l")
arrow("db", "r", "ch", "l")
arrow("ch", "r", "em", "l")
arrow("em", "r", "vs", "l")
arrow("db", "b", "df", "t")
arrow("ui", "r", "api", "l")
arrow("api", "r", "s1", "l")
arrow("s1", "b", "s2", "t")
arrow("s2", "r", "s3", "l")
arrow("s3", "r", "s4", "l")
arrow("s4", "b", "s5", "t")
arrow("s5", "r", "s6", "l")
arrow("s6", "b", "s7", "t", "", "#b3261e")
arrow("s6", "r", "out", "l")
arrow("s7", "r", "out", "l")
arrow("ua", "r", "as", "l")
arrow("as", "r", "rd", "l")
arrow("as", "r", "no", "l")
arrow("rd", "r", "dc", "l")
arrow("no", "r", "dc", "l")
arrow("dc", "r", "ac", "l")
arrow("vs", "b", "s3", "t", "", "#b3261e", True, via=("v", 1165))

def path(a, sa, b, sb, via):
    (x1, y1), (x2, y2) = pt(a, sa), pt(b, sb)
    if via and via[0] == "v":
        mx = via[1]
        if sa in "tb":
            return f"M{x1},{y1} V{y1 + (-30 if sa=='t' else 30)} H{mx} V{y2 + (-30 if sb=='t' else 30)} H{x2} V{y2}"
        return f"M{x1},{y1} H{mx} V{y2} H{x2}"
    if via and via[0] == "h":
        return f"M{x1},{y1} V{via[1]} H{x2} V{y2}"
    if sa in "lr" and sb in "lr":
        if abs(y1 - y2) < 2:
            return f"M{x1},{y1} H{x2}"
        mx = (x1 + x2) / 2
        return f"M{x1},{y1} H{mx} V{y2} H{x2}"
    if sa in "tb" and sb in "tb":
        return f"M{x1},{y1} V{y2}" if abs(x1 - x2) < 2 else f"M{x1},{y1} V{(y1+y2)/2} H{x2} V{y2}"
    if sa in "lr":
        return f"M{x1},{y1} H{x2} V{y2}"
    return f"M{x1},{y1} V{y2} H{x2}"

html = ['<!doctype html><html lang="es"><head><meta charset="utf-8"><style>',
        '*{box-sizing:border-box}body{margin:0;width:2000px;height:1330px;position:relative;font-family:"Segoe UI",Arial,sans-serif;background:#f6f8fa;color:#1b2733}',
        '.box{position:absolute;background:#fff;border:3px solid var(--c);border-radius:12px;padding:8px 12px;box-shadow:0 2px 8px rgba(0,0,0,.1);overflow:hidden}',
        '.box b{display:block;font-size:19px;color:var(--c);margin-bottom:3px}.box pre{margin:0;font:15px/1.3 "Segoe UI",Arial,sans-serif;white-space:pre-wrap;color:#34424e}',
        '.num{position:absolute;top:-1px;right:-1px;background:var(--c);color:#fff;font-weight:800;font-size:18px;width:32px;height:32px;border-radius:0 9px 0 12px;display:grid;place-items:center}',
        '.band{position:absolute;left:20px;right:20px;border-radius:16px;border:2px dashed #b8c2cc;background:rgba(255,255,255,.55)}',
        '.bl{position:absolute;left:34px;font-weight:800;font-size:21px;letter-spacing:.4px}',
        'h1{position:absolute;left:40px;top:18px;margin:0;font-size:36px;color:#1b2733}.sub{position:absolute;left:42px;top:66px;font-size:19px;color:#5b6b79}',
        '.lg{position:absolute;font-size:16px;line-height:1.35}svg{position:absolute;left:0;top:0}.lbl{font:600 14px "Segoe UI",Arial;fill:#55616d}',
        '</style></head><body>',
        '<h1>Arquitectura del sistema: carga, RAG y acta de constatación</h1>',
        '<div class="sub">Python · FastAPI · SQLite · ChromaDB · embeddings (hash | Ollama) · LLM por Strategy · python-docx / openpyxl · SPA sin dependencias</div>',
        '<div class="band" style="top:112px;height:285px"></div><div class="bl" style="top:118px;color:#1f6fb2;left:1500px;text-align:right;width:420px;display:none"></div>',
        '<div class="band" style="top:420px;height:315px"></div><div class="band" style="top:760px;height:260px"></div>']
html.append('<svg width="2000" height="1330"><defs>'
            + ''.join(f'<marker id="m{k}" viewBox="0 0 10 10" refX="9" refY="5" markerUnits="userSpaceOnUse" markerWidth="13" markerHeight="13" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>' for k, c in enumerate(["#55616d", "#b3261e", "#1d7a46"]))
            + '</defs>')
for a, sa, b, sb, lab, c, dash, via in A:
    mk = {"#55616d": 0, "#b3261e": 1, "#1d7a46": 2}[c]
    html.append(f'<path d="{path(a, sa, b, sb, via)}" fill="none" stroke="{c}" stroke-width="3" {"stroke-dasharray=\'9 7\'" if dash else ""} marker-end="url(#m{mk})"/>')
html.append('</svg>')
# etiquetas de banda (encima del svg)
for txt, y, c in (("① INGESTA — se ejecuta al cargar un archivo (y al reindexar)", 120, "#1f6fb2"), ("② CONSULTA — reporte inteligente con RAG (por cédula o por ubicación)", 426, "#b3261e"), ("③ ACTA DE CONSTATACIÓN — cifras deterministas; el RAG aporta las novedades y la norma", 768, "#1d7a46")):
    html.append(f'<div class="bl" style="top:{y}px;color:{c}">{txt}</div>')
for i, b in B.items():
    n = f'<div class="num">{b["num"]}</div>' if b["num"] else ""
    body = b["body"].replace("<", "&lt;").replace(">", "&gt;")
    html.append(f'<div class="box" style="--c:{b["c"]};left:{b["x"]}px;top:{b["y"]}px;width:{b["w"]}px;height:{b["h"]}px">{n}<b>{b["t"]}</b><pre>{body}</pre></div>')
# leyenda y patrones
html.append('''<div class="band" style="top:1050px;height:250px"></div>
<div class="lg" style="left:40px;top:1064px;width:560px"><b style="font-size:20px">Patrones de diseño</b><br>
<b>Adapter</b> esbye.py (archivo → dominio) · <b>Facade</b> InformeService, ActaService · <b>Strategy</b> Embedder, VectorStore, LLMProvider, redactor ·
<b>Factory</b> crear_embedder, crear_store, crear_llm · <b>Builder</b> PromptBuilder · <b>Singleton</b> Settings, Indice · <b>Repository</b> db.py / cortes.py</div>
<div class="lg" style="left:640px;top:1064px;width:640px"><b style="font-size:20px">Controles anti-alucinación y de datos</b><br>
• Las cifras las calcula el código; el modelo solo redacta · • Cada afirmación cita [código] y se valida contra el contexto ·
• Filtro por cédula/ubicación antes de la búsqueda vectorial (no se mezclan custodios) · • Reintento y respaldo determinista ·
• Los fragmentos no llevan el nombre del custodio; con LLM en la nube se omite el nombre y se enmascara la cédula</div>
<div class="lg" style="left:1320px;top:1064px;width:640px"><b style="font-size:20px">Despliegue y calidad</b><br>
• Local: Windows 10/11, Python 3.10+, ChromaDB persistente en data/index · • Sin modelos: modo plantilla + embeddings léxicos ·
• Con Ollama: llama3.1:8b + nomic-embed-text (≈16 GB RAM) · • 30 pruebas pytest (API, RAG, PDF, Word/Excel) ·
• Pendiente para producción: SSO, roles, auditoría, PostgreSQL, firma electrónica</div>
<div class="lg" style="left:40px;top:1235px;font-size:17px"><b>Leyenda:</b> &nbsp;<span style="color:#55616d">▬▶ flujo de datos</span> &nbsp; <span style="color:#b3261e">╌▶ consulta vectorial</span> &nbsp; · &nbsp; borde rojo = RAG · morado = IA/embeddings · verde = datos y cálculo determinista · azul = aplicación</div>
</body></html>''')
open("d2_ingeniero_sistemas.html", "w", encoding="utf-8").write("\n".join(html))
