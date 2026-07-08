@echo off
setlocal EnableExtensions

:: Run relative to this script's directory (path-agnostic)
cd /d "%~dp0"

if not exist "site\" (
    echo ERROR: site\ folder not found next to this script.
    echo Expected: %CD%\site
    exit /b 1
)

echo Stopping anything listening on port 8080...
for /f "tokens=5" %%P in ('netstat -ano 2^>nul ^| findstr ":8080" ^| findstr "LISTENING"') do (
    echo   Killing PID %%P
    taskkill /F /PID %%P >nul 2>&1
)

:: Brief pause so the port can release
timeout /t 1 /nobreak >nul

echo Starting site\ on http://localhost:8080 ...
python -m http.server 8080 --directory site
if errorlevel 1 (
    echo.
    echo ERROR: failed to start. Is Python on PATH?
    exit /b 1
)
