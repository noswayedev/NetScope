@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel% neq 0 (
  echo Python was not found. Install Python 3.11+ from python.org.
  pause
  exit /b 1
)
py -m pip install -r requirements.txt
if %errorlevel% neq 0 exit /b 1
py -m PyInstaller --noconfirm --clean --onefile --windowed --icon assets\netscope.ico --add-data "assets\netscope.png;assets" --name NetScope netscope.py
if %errorlevel% neq 0 exit /b 1
echo.
echo Build complete: dist\NetScope.exe
pause
