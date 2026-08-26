@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
where %PY% >nul 2>nul || goto NOPYTHON
title 6 - GUI Practice (mixer vagar)
echo.
echo   MIXER VAGAR PRACTICE -- nakli M32 andar j chalu thashe.
echo   CH 1 Guruji, CH 2 Vocal 2, CH 4 Tabla, CH 5 Flute gata dekhashe.
echo.
%PY% m32_app.py gui --sim
exit /b

:NOPYTHON
echo.
echo   [X] PYTHON MALYU NAHI !
echo       python.org parthi Python install karo.
echo.
pause
exit /b
