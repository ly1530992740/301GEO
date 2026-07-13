@echo off
setlocal

set "APP_DIR=%~dp0"
set "PORT=8501"

echo [1/3] Switching to project directory...
cd /d "%APP_DIR%"

echo [2/3] Stopping existing Streamlit process on port %PORT%...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do (
    echo Stopping PID %%a
    taskkill /F /PID %%a >nul 2>nul
)

echo [3/3] Starting Streamlit...
echo URL: http://127.0.0.1:%PORT%
python -m streamlit run app.py --server.address 127.0.0.1 --server.port %PORT%

pause
