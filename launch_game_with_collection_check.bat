@echo off
echo Steam Workshop Collection Auto-Subscriber
echo ==========================================
echo.
echo This script will check and subscribe to new items in your Steam workshop collection
echo before launching the game...
echo.

REM Navigate to the script directory
cd /d "%~dp0"

REM Run the Python subscription script
echo Running collection subscription check...
python subscribe_collection.py

echo.
echo Collection check complete. Launching game...
echo.

REM Launch Steam with the specific game
REM Replace with your game's Steam URL or executable path
start steam://rungameid/2269950

echo.
echo Game launch command sent to Steam.
echo You can close this window.
pause
