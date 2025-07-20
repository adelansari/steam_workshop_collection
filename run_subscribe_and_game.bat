@echo off
REM Batch wrapper: subscribe to collection, then launch The Karters 2

REM Run the Python subscription script
python "%~dp0subscribe_collection.py"
if errorlevel 1 (
    echo Subscription script failed. Exiting.
    exit /b 1
)

REM Launch the game executable passed by Steam (detached)
start "" %*
exit /b 0
