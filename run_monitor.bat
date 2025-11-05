@echo off
echo WeChat File Monitor
echo ===================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.7 or higher from https://python.org
    pause
    exit /b 1
)

REM Pass all arguments to the Python script
python wechat_file_monitor.py %*

pause

