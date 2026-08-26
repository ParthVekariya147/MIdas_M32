@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
where %PY% >nul 2>nul || goto NOPYTHON
title EXE banavo
echo.
echo   .EXE BANAVU CHHU
echo   ----------------
echo   2-3 minute lagshe. Purun thay etle "dist" folder khulshe.
echo.
%PY% -m PyInstaller --version >nul 2>nul || (
  echo   PyInstaller install karu chhu...
  %PY% -m pip install pyinstaller
)
%PY% build_exe.py
if exist dist explorer dist
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
