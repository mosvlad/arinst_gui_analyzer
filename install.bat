@echo off
echo Installing Arinst Spectrum Analyzer GUI dependencies...
echo.

echo Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.7+ from https://python.org
    pause
    exit /b 1
)

echo Installing required packages...
pip install PyQt5>=5.15.0
pip install pyqtgraph>=0.12.0
pip install numpy>=1.19.0
pip install pyserial>=3.4

echo.
echo Installation complete!
echo To run the application: python run.py
echo.
pause 