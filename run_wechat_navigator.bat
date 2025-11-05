@echo off
REM ============================================================================
REM WeChat Auto Navigator - Batch File Launcher
REM ============================================================================
REM
REM This batch file launches the WeChat Auto Navigator Python script.
REM
REM USAGE EXAMPLES:
REM ---------------
REM 1. Use default chat (Meadowland):
REM    run_wechat_navigator.bat
REM
REM
REM 3. Navigate to Chinese or mixed name chat:
REM    run_wechat_navigator.bat "太平 Meadowland 3"
REM
REM 4. Navigate to group chat:
REM    run_wechat_navigator.bat "Wairau"
REM
REM NOTES:
REM ------
REM - Use quotes if chat name contains spaces
REM - Supports English, Chinese, and mixed language names
REM - WeChat must be open and visible before running
REM - Move mouse to top-left corner to abort at any time
REM
REM For more options, run: python wechat_auto_navigator.py --help
REM ============================================================================

echo.
echo ============================================================
echo WeChat Auto Navigator
echo ============================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo.
    echo Please install Python 3.7 or higher from:
    echo https://python.org
    echo.
    pause
    exit /b 1
)

REM Check if chat name argument is provided
if "%~1"=="" (
    set CHAT_NAME=Meadowland
    echo Chat Name: Meadowland (default)
) else (
    set CHAT_NAME=%~1
    echo Chat Name: %CHAT_NAME%
)

echo.
echo What this script does:
echo - Finds and activates WeChat window
echo - Navigates to '%CHAT_NAME%' chat using Ctrl+F
echo - Finds and clicks on images in the chat
echo - Navigates through 3 images using left arrow
echo - Closes image preview when done
echo.
echo Prerequisites:
echo [x] WeChat Desktop must be open and visible
echo.
echo Safety:
echo - Move mouse to top-left corner to abort anytime
echo - All windows remain open after completion
echo.
echo Starting in 3 seconds...
echo ============================================================
echo.

python wechat_auto_navigator.py --chat "%CHAT_NAME%"

echo.
echo ============================================================
echo Script completed
echo ============================================================
pause

