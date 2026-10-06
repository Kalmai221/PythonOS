@echo off
rem PythonOS Setup Wizard for Windows. Double-click this file: it opens the wizard.
rem To use the terminal version, open an Administrator Command Prompt in this folder and run:  PythonOS-Wizard.exe --cli --help
cd /d "%~dp0"
if not exist "PythonOS-Wizard.exe" (
    echo PythonOS-Wizard.exe is missing. Extract the whole zip first, then run this file again.
    pause
    exit /b 1
)
start "" "%~dp0PythonOS-Wizard.exe" %*
