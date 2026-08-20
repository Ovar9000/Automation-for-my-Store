@echo off
title Sari-Sari Store POS Launcher
cd /d "%~dp0"

echo ==================================================
echo   Starting Sari-Sari Store POS Terminal...
echo ==================================================

if exist "dist\SariSariPOS\SariSariPOS.exe" (
    start "" "dist\SariSariPOS\SariSariPOS.exe"
) else (
    start "" python desktop_app.py
)
exit
