@echo off
cd /d "%~dp0"
echo Starting AromaAcademy on http://127.0.0.1:8000 ...
start "" http://127.0.0.1:8000
"C:\Users\arina\.venvs\aromaacademy\Scripts\python.exe" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
pause

