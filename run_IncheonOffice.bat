@echo off
cd /d "%~dp0"
if exist "%~dp0python\pythonw.exe" (
  start "" "%~dp0python\pythonw.exe" "%~dp0app\main.py"
) else (
  echo python folder not found. Please extract the whole zip file first.
  pause
)
