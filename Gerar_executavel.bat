@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
 echo Instale Python 3.11 ou superior em python.org, com o Python Launcher.
 pause
 exit /b 1
)
if not exist .venv\Scripts\python.exe (
 py -3 -m venv .venv
 if errorlevel 1 goto erro
)
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto erro
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name ControleLED --hidden-import pystray._win32 controle_led.py
if errorlevel 1 goto erro
 echo.
 echo Pronto! Abra ControleLED.exe na pasta dist.
 start "" "%~dp0dist"
 pause
 exit /b 0
:erro
 echo Falha. Copie a mensagem acima para analisarmos.
 pause
 exit /b 1
