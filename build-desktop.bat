@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [error] Missing .venv\Scripts\python.exe
  echo [hint] Run start.bat first to provision the local runtime and install project dependencies.
  exit /b 1
)

echo [1/3] Installing desktop packaging tools...
call ".venv\Scripts\python.exe" -m pip install -r requirements.desktop.txt
if errorlevel 1 (
  echo [error] Failed to install desktop packaging tools.
  exit /b 1
)

if exist "dist\Stream Subtitle Translator" (
  echo [info] Removing previous desktop dist folder to avoid stale packaged files...
  rmdir /s /q "dist\Stream Subtitle Translator"
)

echo [2/3] Building one-folder desktop distribution...
call ".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean "Stream Subtitle Translator.spec"
if errorlevel 1 (
  echo [error] PyInstaller build failed.
  exit /b 1
)

if /I "%SST_DESKTOP_SEED_RUNTIME%"=="0" (
  echo [3/3] Skipping seeded runtime copy for clean desktop build...
  echo [done] Desktop clean build complete:
  echo [info] dist\Stream Subtitle Translator\Stream Subtitle Translator.exe
  exit /b 0
)

echo [3/3] Seeding packaged runtime folders for cold start...
if exist ".python" (
  robocopy ".python" "dist\Stream Subtitle Translator\.python" /E /NFL /NDL /NJH /NJS /NP >nul
)
if exist ".venv" (
  robocopy ".venv" "dist\Stream Subtitle Translator\.venv" /E /NFL /NDL /NJH /NJS /NP >nul
)
if exist "backend\data" (
  robocopy "backend\data" "dist\Stream Subtitle Translator\user-data" /E /NFL /NDL /NJH /NJS /NP >nul
)

echo [done] Desktop build complete:
echo [info] dist\Stream Subtitle Translator\Stream Subtitle Translator.exe
exit /b 0
