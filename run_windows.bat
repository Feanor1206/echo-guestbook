@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo  ===============================================
echo            ECHO - THE GUESTBOOK
echo  ===============================================
echo.
where py >nul 2>&1
if %errorlevel%==0 (
  set "PY=py"
) else (
  set "PY=python"
)
%PY% -m pip install -r requirements.txt
if errorlevel 1 (
  echo Khong cai duoc thu vien. Hay kiem tra Python/pip va ket noi Internet.
  pause
  exit /b 1
)
echo.
echo  Mo trinh duyet: http://127.0.0.1:8000
echo  Nhan Ctrl+C de dung server.
echo.
%PY% app.py
pause
