@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
where %PY% >nul 2>nul || goto NOPYTHON
title 2 - Channel Pasand Karo
echo.
echo   Badhi channel na naam ane awaaj batavse,
echo   pachhi tame fakt CHANNEL NUMBER lakhvana (dakhla: 1,5,9)
echo.
%PY% m32_app.py select
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
