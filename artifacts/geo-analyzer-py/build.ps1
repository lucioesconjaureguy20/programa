# GeoAnalyzer Build Script (PowerShell)
# Run with: powershell -ExecutionPolicy Bypass -File build.ps1

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  GeoAnalyzer - Build portable .exe" -ForegroundColor Cyan  
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
try {
    $pyVersion = python --version 2>&1
    Write-Host "[OK] Found: $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python not found. Download from https://python.org" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[1/3] Installing Python dependencies..." -ForegroundColor Yellow
python -m pip install -r requirements.txt -q
if ($LASTEXITCODE -ne 0) { Write-Host "[ERROR] pip install failed" -ForegroundColor Red; exit 1 }

Write-Host "[2/3] Installing PyInstaller..." -ForegroundColor Yellow
python -m pip install pyinstaller -q

Write-Host "[3/3] Building GeoAnalyzer.exe..." -ForegroundColor Yellow

$hasIcon = Test-Path "icon.ico"
$iconArgs = if ($hasIcon) { @("--icon", "icon.ico", "--add-data", "icon.ico;.") } else { @() }

$pyinstallerArgs = @(
    "-m", "PyInstaller",
    "--onefile",
    "--windowed",
    "--name", "GeoAnalyzer",
    "--hidden-import", "customtkinter",
    "--hidden-import", "PIL._tkinter_finder",
    "--collect-all", "customtkinter"
) + $iconArgs + @("app.py")

python @pyinstallerArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[ERROR] Build failed. Check output above." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=========================================" -ForegroundColor Green
Write-Host "  SUCCESS! dist\GeoAnalyzer.exe ready" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Copy dist\GeoAnalyzer.exe anywhere and run it." -ForegroundColor White
Write-Host "No Node, Python, or installation needed." -ForegroundColor Gray
