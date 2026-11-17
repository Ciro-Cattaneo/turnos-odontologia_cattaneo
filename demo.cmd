@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0iniciar-demo.ps1" %*
echo.
pause
endlocal
