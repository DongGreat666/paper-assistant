@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\reflex.exe" (
    echo [ERROR] Project virtual environment not found.
    echo Run: python -m venv .venv
    echo Then: .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)
if exist "scripts\patch_vite_watch.py" (
    ".venv\Scripts\python.exe" "scripts\patch_vite_watch.py"
)
set "REFLEX_HOT_RELOAD_EXCLUDE_PATHS=paper_translation:uploaded_files:data:logs:MyPapers"
start /min cmd /c ".venv\Scripts\reflex.exe run"
timeout /t 3 /nobreak > nul
start http://localhost:3000/
