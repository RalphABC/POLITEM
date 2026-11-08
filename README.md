# Demo integrado — Reportes inteligentes (RAG) y actas de constatación · ESPOCH · eSByE

Prototipo que reúne **lo que pidió el tutor** (reporte totalizado de activos a partir de un documento de eSByE por cédula, con
arquitectura RAG) y **lo que pidió la Unidad de Bienes y Bodegas** (acta de constatación por defecto, con un clic, a partir de la
matriz mensual). **El RAG es obligatorio y está en el centro del sistema.**

> **Todos los datos son ficticios.** Es independiente de `demo-rag-esbye` y `demo-actas-esbye`.

## Qué hace

| Necesidad | Dónde |
|---|---|
| Entrada: documento de eSByE de una persona, buscado por **cédula**, en **PDF o CSV** (tutor) | «Carga de datos» acepta `.csv`, `.xlsx` y `.pdf` con texto; «Reporte inteligente» busca por cédula |
| **Reporte totalizado** de activos con RAG (tutor) | «Reporte inteligente»: cifras calculadas por el programa + redacción con recuperación, citas `[ESP-000123]` y validación |
| Carga y segmentación, **incrustaciones y base vectorial** (tutor) | `app/rag/`: un fragmento por bien y por norma → embeddings → **ChromaDB** (o memoria como respaldo) |
| **Acta de constatación** por defecto, un modelo único, firmas por defecto (Unidad de Bienes) | «Acta de constatación»: texto fijo, ubicación/custodio/analista elegidos de listas, Word + anexo Excel |
| Matriz que cambia **cada mes** | «Carga de datos»: cada archivo es un *corte*; se comparan altas, bajas, traspasos y cambios |
| Observaciones del analista (faltante, mal estado…) | Se redactan de forma uniforme; la **norma aplicable se recupera con el mismo RAG** |
| Valor total y depreciación | Salen de la matriz; se pueden corregir a mano o ingresar sin matriz (modo manual) |

### Cómo se reparte el trabajo entre el programa y el RAG
- **El programa calcula** (cantidades, valor contable, depreciación acumulada, valor en libros) y arma el acta con su texto fijo.
- **El RAG recupera** los registros y las normas pertinentes y **redacta** los reportes y las novedades.
- **El validador comprueba** que cada código citado exista, que las cifras coincidan con las calculadas y que no falten los bienes críticos; si no, reintenta una vez y luego usa una plantilla determinista.

## Ejecutar (Windows)
1. Instale **Python 3.10 o superior** (marque *Add Python to PATH*).
2. Doble clic en **`run.bat`** (instala dependencias, incluida ChromaDB; abre `http://localhost:8000`).
3. La primera vez carga tres cortes ficticios (agosto, septiembre y octubre de 2026).

Archivos para probar la carga: `data/matrices/` (matrices institucionales) y `data/ejemplos/documento_funcionario_*.pdf|csv`
(documento de un solo funcionario, como el que se descarga buscando por cédula; cárguelo como **parcial**).

## Guion de demostración (6 minutos)
1. **Reporte inteligente** → por cédula (`9942203407`) → *Reporte totalizado* → cifras verificadas, texto con citas, **evidencias recuperadas** y trazabilidad.
2. Pulsar un código `[ESP-…]` → salta a su evidencia (de dónde salió el dato).
3. *Consulta en lenguaje natural*: «¿Qué bienes están en mal estado o totalmente depreciados?».
4. **Carga de datos** → subir `documento_funcionario_9920834547.pdf` como *parcial* → volver al reporte con esa cédula.
5. **Sistema RAG** → pipeline, base vectorial, fragmentos indexados.
6. **Acta de constatación** → ubicación *DTIC - UNIDAD DE SOPORTE Y MANTENIMIENTO* → agregar una novedad → *Emitir* → Word y anexo Excel.
7. Modo manual: reproducir el acta 524-2026 (44 ítems, $ 19.443,77 y $ 14.372,76).

## Modelos (opcional)
Por defecto (`LLM_PROVIDER=plantilla`, `EMBEDDING_PROVIDER=hash`) todo funciona **sin internet ni modelos**: la redacción es determinista y
los embeddings son léxicos (n-gramas de caracteres). Para el RAG completo con modelo local:
```
ollama pull llama3.1:8b          # generación
ollama pull nomic-embed-text     # embeddings semánticos
```
En `.env`: `LLM_PROVIDER=ollama`, `EMBEDDING_PROVIDER=ollama`, y en «Sistema RAG» pulse **Reindexar todo**. También hay proveedores
`anthropic` y `openai` (con la nube no se envían nombres de funcionarios ni fragmentos con datos personales).

## Estructura
```
app/ esbye.py (Adapter CSV/Excel/PDF) · pdf_loader.py · cortes.py · totales.py · informes.py (Facade del RAG) · actas.py (Facade del acta)
     redactor.py · normativa.py · documento.py (Word/Excel) · api.py · main.py
app/rag/ chunking.py · embeddings.py (Strategy) · vectorstore.py (Strategy: Chroma | memoria) · indexador.py · retriever.py ·
         prompts.py (Builder) · llm.py (Strategy: plantilla|Ollama|Anthropic|OpenAI) · validator.py
web/ interfaz · data/ matrices, ejemplos, normativa · docs/ capturas y diagramas · tests/ 30 pruebas
```

## Pruebas
`pruebas.bat` o `python -m pytest -v` (30): importación y formatos, cortes y diferencias, totales, aislamiento por cédula, recuperación,
validador, reintento y respaldo ante alucinación, no envío de nombres a la nube, base en memoria, lectura de PDF, Word/Excel y API de extremo a extremo.

## Límites (ver el PDF «Alcance, limitaciones y requerimientos»)
- No se conecta a eSByE: los datos se suben como archivo. Los nombres de columnas son los de los filtros del manual público; deben validarse con una exportación real.
- El PDF debe tener texto seleccionable (no se aplica OCR) y su diseño real no fue verificado; si falla, use Excel o CSV.
- Los embeddings por defecto son léxicos; la similitud por significado requiere Ollama.
- Sin firma electrónica, inicio de sesión institucional ni bitácora de auditoría. Normativa: resumen de apoyo, no el texto oficial.
- Modelos Ollama/Anthropic/OpenAI probados solo con respuestas simuladas.
