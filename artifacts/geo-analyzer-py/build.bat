@echo off
setlocal

echo =========================================
echo   GeoAnalyzer - Build portable .exe
echo =========================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Download from https://python.org
    pause
    exit /b 1
)

echo [1/3] Installing dependencies...
python -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo [2/3] Installing PyInstaller...
python -m pip install pyinstaller --quiet

echo [3/3] Building GeoAnalyzer.exe ...
python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "GeoAnalyzer" ^
    --icon "icon.ico" ^
    --add-data "icon.ico;." ^
    --hidden-import "customtkinter" ^
    --hidden-import "PIL._tkinter_finder" ^
    --collect-all "customtkinter" ^
    app.py

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. Check output above.
    pause
    exit /b 1
)

echo.
echo =========================================
echo   SUCCESS! GeoAnalyzer.exe is in dist\
echo =========================================
echo.
echo Copy dist\GeoAnalyzer.exe anywhere and run it.
echo No installation needed.
echo.
pause
