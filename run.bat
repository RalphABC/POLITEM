@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo ============================================================
echo  Demo integrado - Reportes con RAG y actas (ESPOCH / eSByE)
echo ============================================================
where py >nul 2>nul
if %errorlevel%==0 ( set PY=py -3 ) else ( set PY=python )
if not exist .venv (
  echo [1/3] Creando entorno virtual...
  %PY% -m venv .venv || goto :error
)
call .venv\Scripts\activate.bat
echo [2/3] Instalando dependencias (la primera vez tarda unos minutos)...
python -m pip install --disable-pip-version-check -q -r requirements.txt || goto :error
echo     Instalando la base vectorial ChromaDB (si falla, el sistema usa una base en memoria)...
python -m pip install --disable-pip-version-check -q -r requirements-chroma.txt || echo     [aviso] ChromaDB no se pudo instalar; se usara la base en memoria.
if not exist .env copy /y .env.example .env >nul
if not exist data\matrices\matriz_esbye_2026-10-23.csv python scripts\generar_datos.py
echo [3/3] Iniciando en http://localhost:8000  (Ctrl+C para detener)
start "" http://localhost:8000
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
goto :eof
:error
echo.
echo Ocurrio un error. Verifique que Python 3.10 o superior este instalado (https://www.python.org).
pause
