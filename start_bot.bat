@echo off
echo Starting DEX Trading Bot...
echo.

:: Enable delayed expansion
setlocal enabledelayedexpansion

:: Change to the bot directory
cd /d "%~dp0"

:: Create necessary directories
if not exist "logs" mkdir logs
if not exist "data" mkdir data
if not exist "abi" mkdir abi

:: Clear previous log files
echo. > logs\startup.log
echo. > logs\bot.log

echo Starting bot at %date% %time% >> logs\startup.log 2>&1

:: Check if Python is installed
python --version > nul 2>&1
if errorlevel 1 (
    echo Python is not installed or not in PATH >> logs\startup.log 2>&1
    echo Please install Python 3.8 or later >> logs\startup.log 2>&1
    type logs\startup.log
    pause
    exit /b 1
)

:: Remove old virtual environment if it exists
if exist "venv" (
    echo Removing old virtual environment... >> logs\startup.log 2>&1
    rmdir /s /q venv
)

:: Create new virtual environment
echo Creating virtual environment... >> logs\startup.log 2>&1
python -m venv venv
if errorlevel 1 (
    echo Failed to create virtual environment >> logs\startup.log 2>&1
    type logs\startup.log
    pause
    exit /b 1
)

:: Activate virtual environment using full path
echo Activating virtual environment... >> logs\startup.log 2>&1
call "%~dp0venv\Scripts\activate.bat"
if errorlevel 1 (
    echo Error activating virtual environment >> logs\startup.log 2>&1
    type logs\startup.log
    pause
    exit /b 1
)

:: Upgrade pip
echo Upgrading pip... >> logs\startup.log 2>&1
python -m pip install --upgrade pip >> logs\startup.log 2>&1

:: Install requirements with detailed error logging
echo Installing requirements... >> logs\startup.log 2>&1
pip install -r requirements.txt >> logs\startup.log 2>&1
if errorlevel 1 (
    echo Error installing requirements >> logs\startup.log 2>&1
    type logs\startup.log
    pause
    exit /b 1
)

:: Start the web server with immediate output
echo Starting web server... >> logs\startup.log 2>&1

:: Run Python with unbuffered output
python -u web_server.py >> logs\startup.log 2>&1

:: Check if the server started successfully
timeout /t 2 /nobreak > nul

:: Try to connect to the server
powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://127.0.0.1:8081' -TimeoutSec 5; exit 0 } catch { exit 1 }" > nul 2>&1
if errorlevel 1 (
    echo Server failed to start. Checking logs... >> logs\startup.log 2>&1
    echo. >> logs\startup.log 2>&1
    echo Bot Log Contents: >> logs\startup.log 2>&1
    type logs\bot.log >> logs\startup.log 2>&1
    echo. >> logs\startup.log 2>&1
    echo Startup failed. See error details above. >> logs\startup.log 2>&1
    type logs\startup.log
    pause
    exit /b 1
)

:: If we get here, server started successfully
echo Server started successfully! >> logs\startup.log 2>&1
start http://127.0.0.1:8081

echo.
echo Bot is running! The web interface should open in your browser.
echo If the web interface doesn't open automatically, visit: http://127.0.0.1:8081
echo.
echo Press Ctrl+C in this window to stop the bot.
echo.
echo Showing logs (press Ctrl+C to stop):
echo -----------------------------------

:: Show logs in real-time
powershell -Command "Get-Content -Path logs\bot.log -Wait"

endlocal
pause
