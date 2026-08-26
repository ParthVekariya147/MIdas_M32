@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
where %PY% >nul 2>nul || goto NOPYTHON
title MIDAS M32 - AUTO FX (CHALU)
:START
%PY% m32_app.py run
echo.
echo   Program band thai gayo. Fari chalu karva koi pan key dabavo.
pause >nul
goto START

:NOPYTHON
echo.
echo   [X] PYTHON MALYU NAHI !
echo       python.org parthi Python install karo.
echo.
pause
exit /b
