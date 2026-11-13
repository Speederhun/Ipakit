@echo off
rem Ipakit installer: installs everything needed and puts an icon on the desktop.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup.ps1"
echo.
pause
