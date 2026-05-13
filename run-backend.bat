@echo off
cd /d "F:\IA\Analisis IA-v2\backend"
venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
pause
