@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
where %PY% >nul 2>nul || goto NOPYTHON
title 2B - Auto Scan
echo.
echo   AUTO SCAN : bolo etle channel JATE shodhi lese.
echo.
%PY% m32_app.py scan
echo.
pause
exit /b

:NOPYTHON
echo.
echo   [X] PYTHON MALYU NAHI !
echo       python.org parthi Python install karo.
echo.
pause
exit /b
