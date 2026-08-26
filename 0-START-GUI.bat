@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
where %PY% >nul 2>nul || goto NOPYTHON
title MIDAS M32 - Auto FX (GUI)
set "PYW=pythonw"
where pythonw >nul 2>nul || set "PYW=%PY%"
start "" %PYW% m32_app.py
exit /b

:NOPYTHON
echo.
echo   [X] PYTHON MALYU NAHI !
echo       python.org parthi Python install karo.
echo.
pause
exit /b
