@echo off
setlocal
cd /d "%~dp0"

if exist "target\release\ai-ex-desktop.exe" (
    start "AIex" "target\release\ai-ex-desktop.exe" %*
    exit /b 0
)
if exist "target\debug\ai-ex-desktop.exe" (
    start "AIex" "target\debug\ai-ex-desktop.exe" %*
    exit /b 0
)

where cargo >nul 2>&1
if errorlevel 1 (
    echo AIex desktop is not built and Cargo was not found.
    echo Install Rust or place ai-ex-desktop.exe in target\release.
    pause
    exit /b 1
)

echo AIex desktop binary is not built; starting the development fallback.
cargo run --manifest-path "crates\ai-ex-desktop\Cargo.toml" -- %*
if errorlevel 1 pause
