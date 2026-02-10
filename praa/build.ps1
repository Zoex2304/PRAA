# PRAA Build Script — Nuitka standalone .exe
# Usage: .\build.ps1

$ErrorActionPreference = "Stop"

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "  PRAA Build Script — Nuitka Standalone Binary" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan

# Ensure we're in the praa directory
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

# Check for icon file
$iconArg = ""
$iconPath = Join-Path $projectRoot "assets\icon.ico"
if (Test-Path $iconPath) {
    $iconArg = "--windows-icon-from-ico=$iconPath"
    Write-Host "[OK] Icon found: $iconPath" -ForegroundColor Green
} else {
    Write-Host "[SKIP] No icon.ico found in assets/, building without icon" -ForegroundColor Yellow
}

# Build command
Write-Host "`nBuilding with Nuitka..." -ForegroundColor Yellow
$mainPy = Join-Path $projectRoot "src\main.py"

$buildArgs = @(
    "-m", "nuitka",
    "--standalone",
    "--onefile",
    "--windows-disable-console",
    "--output-filename=praa.exe",
    "--output-dir=$projectRoot\dist",
    "--include-package=src",
    $mainPy
)

if ($iconArg) {
    $buildArgs = @("-m", "nuitka", "--standalone", "--onefile", "--windows-disable-console", $iconArg, "--output-filename=praa.exe", "--output-dir=$projectRoot\dist", "--include-package=src", $mainPy)
}

python @buildArgs

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
    Write-Host "  Build successful!" -ForegroundColor Green
    Write-Host "  Output: $projectRoot\dist\praa.exe" -ForegroundColor Green
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green

    # Copy config.json alongside the exe
    $configSrc = Join-Path $projectRoot "config.json"
    $configDst = Join-Path $projectRoot "dist\config.json"
    if (Test-Path $configSrc) {
        Copy-Item $configSrc $configDst -Force
        Write-Host "[OK] config.json copied to dist/" -ForegroundColor Green
    }
} else {
    Write-Host "`n[ERROR] Build failed with exit code $LASTEXITCODE" -ForegroundColor Red
    exit 1
}
