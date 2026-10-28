@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   AI Console - starting local service
echo   http://127.0.0.1:8765
echo   close this window to stop
echo ============================================
echo.

set "PY="
if exist "%~dp0python.txt" set /p PY=<"%~dp0python.txt"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY (where py >nul 2>nul && set "PY=py")
if not defined PY (
  echo [ERROR] Python not found in PATH.
  echo Install Python 3.9+ and tick "Add to PATH", then retry.
  echo Or write the full python.exe path into python.txt next to this file.
  pause
  exit /b 1
)

"%PY%" serve.py
if errorlevel 1 pause
