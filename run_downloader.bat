@echo off
echo WeChat Image Downloader
echo =======================

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.7 or higher from https://python.org
    pause
    exit /b 1
)

REM Check if setup has been run
if not exist config.json (
    echo Running initial setup...
    python setup.py
    echo.
)

REM Check if user wants to list groups first
set /p choice="Do you want to list available groups first? (y/n): "
if /i "%choice%"=="y" (
    echo.
    echo Available WeChat groups:
    echo ------------------------
    python wechat_image_downloader.py --list-groups
    echo.
)

REM Ask if user wants to proceed with download
set /p proceed="Proceed with image download? (y/n): "
if /i "%proceed%"=="y" (
    echo.
    echo Starting download...
    python wechat_image_downloader.py
) else (
    echo Download cancelled.
)

echo.
pause
