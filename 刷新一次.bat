@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PY="
if exist "%~dp0python.txt" set /p PY=<"%~dp0python.txt"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY (where py >nul 2>nul && set "PY=py")
if not defined PY (
  echo [ERROR] Python not found in PATH.
  pause
  exit /b 1
)

echo [1/2] running all agent plugins...
"%PY%" core\runner.py --all
echo.
echo [2/2] aggregating state...
"%PY%" core\aggregate.py
echo.
echo done. press any key to close.
pause >nul
