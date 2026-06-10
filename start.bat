@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\reflex.exe" (
    echo [ERROR] Project virtual environment not found.
    echo Run: python -m venv .venv
    echo Then: .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)
start /min cmd /c ".venv\Scripts\reflex.exe run"
timeout /t 3 /nobreak > nul
start http://localhost:3000/
