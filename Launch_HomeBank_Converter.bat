@echo off
setlocal

cd /d "%~dp0"

if exist "dist\HomeBankConverterGUI\HomeBankConverterGUI.exe" (
    start "" "dist\HomeBankConverterGUI\HomeBankConverterGUI.exe"
    exit /b 0
)

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "scripts\gui_launcher.py"
    exit /b %ERRORLEVEL%
)

where py >nul 2>&1
if %ERRORLEVEL%==0 (
    py -3 "scripts\gui_launcher.py"
    exit /b %ERRORLEVEL%
)

python "scripts\gui_launcher.py"
exit /b %ERRORLEVEL%
