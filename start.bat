@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\reflex.exe" (
    echo [ERROR] Project virtual environment not found.
    echo Run: python -m venv .venv
    echo Then: .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

rem Reuse the running app instead of starting another frontend/backend pair.
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://localhost:3000/translate; if ($r.StatusCode -eq 200 -and $r.Content -match '__reactRouterContext') { exit 0 } } catch {}; exit 1" >nul 2>&1
if not errorlevel 1 (
    start http://localhost:3000/translate
    exit /b 0
)

if exist "scripts\patch_vite_watch.py" (
    ".venv\Scripts\python.exe" "scripts\patch_vite_watch.py"
)
set "REFLEX_UPLOADED_FILES_DIR=data/reflex_uploads"
set "REFLEX_HOT_RELOAD_EXCLUDE_PATHS=paper_translation:data/reflex_uploads:data:logs:MyPapers"
start /min cmd /c ".venv\Scripts\reflex.exe run"
timeout /t 3 /nobreak > nul
start http://localhost:3000/
