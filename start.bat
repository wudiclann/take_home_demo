@echo off
setlocal enabledelayedexpansion
REM Launcher: sets up and runs both the backend (FastAPI) and frontend (Vite dev
REM server) in their own windows, then opens the app in your browser. Safe to
REM re-run -- it skips any setup step that's already done (existing venv,
REM installed deps, existing .env). Double-click this file in File Explorer,
REM or run it from a terminal.

set "ROOT_DIR=%~dp0"
set "BACKEND_DIR=%ROOT_DIR%backend"
set "FRONTEND_DIR=%ROOT_DIR%frontend"
set "BACKEND_PORT=8000"
set "FRONTEND_PORT=5173"

echo == Voice PDF Book Q&A -- Launcher ==
echo.

REM 1. Prerequisite checks
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: python not found on PATH. Install Python 3.11+ from https://www.python.org/downloads/
    echo        ^(check "Add python.exe to PATH" during install^), then re-run this script.
    pause
    exit /b 1
)
where npm >nul 2>&1
if errorlevel 1 (
    echo ERROR: npm not found on PATH. Install Node.js 20+ from https://nodejs.org/ and re-run this script.
    pause
    exit /b 1
)

REM 2. Free up the ports in case a previous run didn't shut down cleanly
call :free_port %BACKEND_PORT%
call :free_port %FRONTEND_PORT%

REM 3. Backend virtual environment
if not exist "%BACKEND_DIR%\venv" (
    echo Creating Python virtual environment ^(backend\venv^)...
    python -m venv "%BACKEND_DIR%\venv"
)

echo Installing backend dependencies ^(first run downloads a few hundred MB -- ML libraries + a small reranker model; can take a few minutes^)...
call "%BACKEND_DIR%\venv\Scripts\activate.bat"
python -m pip install -q --upgrade pip
pip install -q -r "%BACKEND_DIR%\requirements.txt"
call "%BACKEND_DIR%\venv\Scripts\deactivate.bat"

REM 4. .env -- created empty; the OpenAI key is entered later from the app's own
REM Settings page, not by hand-editing this file.
if not exist "%BACKEND_DIR%\.env" (
    echo Creating backend\.env ^(empty -- add your OpenAI API key from the app's Settings page once it's running^)...
    copy /y "%BACKEND_DIR%\.env.example" "%BACKEND_DIR%\.env" >nul
)

REM 5. Frontend dependencies
if not exist "%FRONTEND_DIR%\node_modules" (
    echo Installing frontend dependencies ^(npm install^)...
    pushd "%FRONTEND_DIR%"
    call npm install
    popd
)

REM 6. Start both servers, each in its own window
echo.
echo Starting backend on http://localhost:%BACKEND_PORT% ...
start "Backend - Take Home Demo" cmd /k "cd /d "%BACKEND_DIR%" && call venv\Scripts\activate.bat && uvicorn app.main:app --host 0.0.0.0 --port %BACKEND_PORT%"

echo Starting frontend on http://localhost:%FRONTEND_PORT% ...
start "Frontend - Take Home Demo" cmd /k "cd /d "%FRONTEND_DIR%" && npm run dev -- --port %FRONTEND_PORT%"

REM 7. Wait for the backend to actually be ready before opening the browser
echo Waiting for the backend to be ready ^(first run is slower -- downloading the reranker model^)...
set "READY=0"
for /l %%i in (1,1,90) do (
    if "!READY!"=="0" (
        curl -s -o nul "http://localhost:%BACKEND_PORT%/documents" >nul 2>&1
        if not errorlevel 1 set "READY=1"
        if "!READY!"=="0" timeout /t 1 /nobreak >nul
    )
)
if "%READY%"=="0" (
    echo The backend didn't come up in time. Check the "Backend - Take Home Demo" window for errors.
)

timeout /t 2 /nobreak >nul
start "" "http://localhost:%FRONTEND_PORT%"

echo.
echo Take Home Demo is running:
echo   App (open this):  http://localhost:%FRONTEND_PORT%
echo   Backend API:       http://localhost:%BACKEND_PORT%
echo.
echo First time running? Go to Settings in the app and add your OpenAI API key.
echo Backend and frontend logs are in their own windows -- close both windows (or press Ctrl+C in each) to stop the app.
echo.
pause
exit /b 0

:free_port
set "PORT=%~1"
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%PORT%" ^| findstr "LISTENING"') do (
    echo Port %PORT% is in use -- stopping the existing process so this run can use it...
    taskkill /F /PID %%p >nul 2>&1
)
exit /b 0
