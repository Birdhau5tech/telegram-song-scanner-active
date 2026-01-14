@echo off
REM Wrapper to run the PowerShell setup script with a temporary bypass
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0setup_windows_env.ps1"
