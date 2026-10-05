@echo off
rem Starts Framifold and opens it in the browser. If it is already running, just opens the page.
netstat -ano | findstr ":8510 " | findstr LISTENING >nul && (start "" http://localhost:8510 & exit /b)
cd /d "%~dp0framifold"
python -m streamlit run app.py --server.port 8510
