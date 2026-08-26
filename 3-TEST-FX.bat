@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
where %PY% >nul 2>nul || goto NOPYTHON
title 3 - FX Test
echo.
echo   3 var MUTE / UNMUTE thashe. MIXER NI SCREEN JOTA RAHO !
echo.
%PY% m32_app.py testfx
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
