@echo off
cd /d "%~dp0"
py "%~dp0display_toggle.py" --extend
if errorlevel 1 pause
