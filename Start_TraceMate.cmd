@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
    py -3 start_local.py %*
) else (
    python start_local.py %*
)
if errorlevel 1 (
    echo.
    echo TraceMate could not start. Python 3.10 or newer is required.
    pause
)
endlocal
