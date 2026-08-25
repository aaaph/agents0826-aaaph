@echo off
REM Windows launcher for the cross-platform onboarding script.
REM Double-click, or run from cmd:  deploy\bootstrap.cmd
setlocal
cd /d "%~dp0\.."

where py >nul 2>nul
if %errorlevel%==0 (
    py deploy\bootstrap.py
    goto :done
)
where python >nul 2>nul
if %errorlevel%==0 (
    python deploy\bootstrap.py
    goto :done
)
echo.
echo ERROR: Python not found. Install Python 3.11+ from https://python.org
echo (tick "Add Python to PATH" during installation).
echo.

:done
echo.
pause
endlocal
