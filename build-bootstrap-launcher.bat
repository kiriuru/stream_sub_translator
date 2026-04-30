@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [error] Missing .venv\Scripts\python.exe
  echo [hint] Run start.bat first to provision the local runtime and install project dependencies.
  exit /b 1
)

echo [1/5] Installing desktop packaging tools...
call ".venv\Scripts\python.exe" -m pip install -r requirements.desktop.txt
if errorlevel 1 (
  echo [error] Failed to install desktop packaging tools.
  exit /b 1
)

echo [2/5] Building clean managed desktop runtime...
set "SST_DESKTOP_SEED_RUNTIME=0"
call build-desktop.bat
if errorlevel 1 (
  echo [error] Clean managed runtime build failed.
  exit /b 1
)
set "SST_DESKTOP_SEED_RUNTIME="

echo [3/5] Creating embedded bootstrap payload...
if exist "build\bootstrap-payload" rmdir /s /q "build\bootstrap-payload"
call ".venv\Scripts\python.exe" -m desktop.build_bootstrap_payload --source-dist "dist\Stream Subtitle Translator" --output-dir "build\bootstrap-payload"
if errorlevel 1 (
  echo [error] Failed to prepare embedded bootstrap payload.
  exit /b 1
)

echo [4/5] Building one-file bootstrap launcher...
if exist "dist\bootstrap-launcher" rmdir /s /q "dist\bootstrap-launcher"
call ".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --distpath "dist\bootstrap-launcher" --workpath "build\bootstrap-launcher" "Stream Subtitle Translator Bootstrap.spec"
if errorlevel 1 (
  echo [error] Bootstrap launcher build failed.
  exit /b 1
)

echo [5/5] Bootstrap launcher build complete:
echo [info] dist\bootstrap-launcher\Stream Subtitle Translator.exe
exit /b 0
