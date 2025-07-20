@echo off
REM Ensure working directory is the script location
cd /d "%~dp0"
REM Batch wrapper: auto-update all collections, then launch the game
python "%~dp0auto_update_all.py"
if errorlevel 1 (
    echo Auto-update failed. Exiting.
    exit /b 1
)
REM Run the subscription script for a final full collection subscribe
python "%~dp0subscribe_collection.py"
if errorlevel 1 (
    echo Subscription script failed. Exiting.
    exit /b 1
)
REM Give Steam a few seconds to sync subscriptions
timeout /t 5 /nobreak >nul
REM Launch the game via the original Steam command so Steam tracks it properly
call %*
exit /b 0
