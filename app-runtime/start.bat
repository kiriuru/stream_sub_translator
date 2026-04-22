@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_VERSION=3.11.9"
set "LOCAL_PYTHON=%CD%\.python\python.exe"
set "PYTHON_CMD="
set "INSTALL_PROFILE_FILE=%CD%\user-data\install_profile.txt"
set "INSTALL_PROFILE="
set "INSTALL_PROFILE_OVERRIDE="
set "PROJECT_CACHE_DIR=%CD%\.cache"
set "PROJECT_TEMP_DIR=%CD%\.tmp"
set "PROJECT_HF_DIR=%PROJECT_CACHE_DIR%\huggingface"
set "TORCH_PROFILE_STATE_FILE=%CD%\.venv\torch_profile_state.txt"

call :prepare_local_environment

if /i "%~1"=="--cpu" set "INSTALL_PROFILE_OVERRIDE=cpu"
if /i "%~1"=="--nvidia" set "INSTALL_PROFILE_OVERRIDE=nvidia"
if /i "%STREAM_SUB_TRANSLATOR_INSTALL_PROFILE%"=="cpu" set "INSTALL_PROFILE_OVERRIDE=cpu"
if /i "%STREAM_SUB_TRANSLATOR_INSTALL_PROFILE%"=="nvidia" set "INSTALL_PROFILE_OVERRIDE=nvidia"
if /i "%STREAM_SUB_TRANSLATOR_INSTALL_PROFILE%"=="cuda" set "INSTALL_PROFILE_OVERRIDE=nvidia"

echo [1/7] Resolving project-local Python runtime...
call :resolve_python
if errorlevel 1 (
  pause
  exit /b 1
)
echo [info] Using Python: %PYTHON_CMD%

echo [2/7] Creating or reusing .venv...
call :ensure_venv
if errorlevel 1 (
  pause
  exit /b 1
)

echo [3/7] Resolving local ASR install profile...
call :resolve_install_profile
if errorlevel 1 (
  pause
  exit /b 1
)
echo [info] Install profile: %INSTALL_PROFILE%

echo [4/7] Installing/updating requirements...
call ".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
  echo Failed to upgrade pip in .venv
  pause
  exit /b 1
)
call :ensure_torch_profile
if errorlevel 1 (
  pause
  exit /b 1
)
call ".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Failed to install shared requirements from requirements.txt
  pause
  exit /b 1
)

echo [5/7] Ensuring model directory exists...
if not exist "user-data\models" mkdir "user-data\models"
if not exist "user-data\models\parakeet-tdt-0.6b-v3\parakeet-tdt-0.6b-v3.nemo" (
  echo [info] Official EU multilingual Parakeet model is not installed yet.
  echo [info] The first Start in the dashboard will download it automatically into user-data\models.
  echo [info] Watch this console for download progress during that first ASR startup.
  echo [info] Optional manual install command:
  echo [info]   .venv\Scripts\python.exe -m backend.install_asr_model --model eu
)

if /i "%INSTALL_PROFILE%"=="cpu" (
  echo [policy] Install profile is CPU-only. NVIDIA CUDA PyTorch wheels are not installed.
  echo [policy] This mode is intended for AMD, Intel, or no-GPU machines.
) else (
  echo [policy] Install profile is NVIDIA CUDA 12.8. Realtime GPU mode is preferred.
)
echo [preflight] Checking local environment summary...
call ".venv\Scripts\python.exe" -m backend.preflight
if errorlevel 1 (
  echo [warning] Preflight reported a problem. Startup will continue, but runtime behavior may be degraded.
)

for /f "usebackq delims=" %%i in (`".venv\Scripts\python.exe" -c "import importlib; torch = importlib.import_module('torch'); build = getattr(getattr(torch, 'version', None), 'cuda', None); available = bool(torch.cuda.is_available()); print('CPU_ONLY' if not build else ('CUDA_READY' if available else 'CUDA_DEGRADED'))" 2^>nul`) do set TORCH_BUILD=%%i
if /i "%TORCH_BUILD%"=="CPU_ONLY" (
  echo [warning] Detected CPU-only PyTorch in the project venv.
  echo [warning] Realtime GPU mode is unavailable; the app will run in degraded CPU fallback mode.
  echo [warning] Install a CUDA-enabled PyTorch build in this same .venv to enable the default GPU path.
)
if /i "%TORCH_BUILD%"=="CUDA_DEGRADED" (
  echo [warning] CUDA-enabled PyTorch is installed, but torch.cuda.is_available^(^) is false.
  echo [warning] Realtime GPU mode is unavailable; the app will run in degraded CPU fallback mode.
)
if /i "%TORCH_BUILD%"=="CUDA_READY" (
  echo [info] CUDA-enabled PyTorch detected. Realtime GPU mode is the expected runtime path.
)
echo [info] Translation configuration can be disabled, ready, partial, or experimental.
echo [info] See the preflight lines above if translation is not ready on this machine.

echo [6/7] Starting FastAPI app...
echo [7/7] Opening local UI in browser and keeping logs here...
call ".venv\Scripts\python.exe" -m backend.run --open-browser

echo Server stopped.
pause
exit /b 0

:resolve_python
call :validate_local_python
if not errorlevel 1 (
  set "PYTHON_CMD="%LOCAL_PYTHON%""
  exit /b 0
)

echo [info] Project-local Python runtime is missing. Auto-provisioning CPython %PYTHON_VERSION% into .python\ ...
call powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap-python.ps1" -ProjectRoot "%CD%" -PythonVersion "%PYTHON_VERSION%"
if errorlevel 1 (
  echo [error] Automatic local Python provisioning failed.
  echo [error] This project does not use system Python as a fallback.
  echo [error] Fix the local bootstrap step and run start.bat again.
  exit /b 1
) else (
  call :validate_local_python
  if not errorlevel 1 (
    set "PYTHON_CMD="%LOCAL_PYTHON%""
    exit /b 0
  )
  echo [error] Provisioning finished, but .python\python.exe is still not usable.
  echo [error] This project does not use system Python as a fallback.
  exit /b 1
)

echo Suitable Python could not be prepared.
echo.
echo Expected normal path:
echo   1. start.bat downloads official CPython %PYTHON_VERSION%
echo   2. CPython is installed locally into .python\
echo   3. .venv is created from that local runtime
exit /b 1

:validate_local_python
if not exist "%LOCAL_PYTHON%" exit /b 1
set "LOCAL_PY_VER="
set "LOCAL_PY_MAJOR="
set "LOCAL_PY_MINOR="
for /f "tokens=2 delims= " %%V in ('"%LOCAL_PYTHON%" --version 2^>nul') do set "LOCAL_PY_VER=%%V"
for /f "tokens=1,2 delims=." %%A in ("%LOCAL_PY_VER%") do (
  set "LOCAL_PY_MAJOR=%%A"
  set "LOCAL_PY_MINOR=%%B"
)
if not "%LOCAL_PY_MAJOR%"=="3" exit /b 1
if "%LOCAL_PY_MINOR%"=="" exit /b 1
if %LOCAL_PY_MINOR% GEQ 10 exit /b 0
exit /b 1

:ensure_venv
if not exist ".venv\Scripts\python.exe" goto :recreate_venv
set "VENV_VER="
set "VENV_MAJOR="
set "VENV_MINOR="
for /f "tokens=2 delims= " %%V in ('".venv\Scripts\python.exe" --version 2^>nul') do set "VENV_VER=%%V"
for /f "tokens=1,2 delims=." %%A in ("%VENV_VER%") do (
  set "VENV_MAJOR=%%A"
  set "VENV_MINOR=%%B"
)
if "%VENV_MAJOR%"=="3" (
  if not "%VENV_MINOR%"=="" (
    if %VENV_MINOR% GEQ 10 exit /b 0
  )
)
echo [warning] Existing .venv is unusable. Recreating it from the resolved Python runtime...
if exist ".venv" rmdir /s /q ".venv"

:recreate_venv
call %PYTHON_CMD% -m venv .venv
if errorlevel 1 (
  echo Failed to create .venv from %PYTHON_CMD%
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo .venv was created, but .venv\Scripts\python.exe is missing.
  exit /b 1
)
exit /b 0

:ensure_torch_profile
call ".venv\Scripts\python.exe" -c "import pathlib, sys; p = pathlib.Path(r'%TORCH_PROFILE_STATE_FILE%'); marker = p.read_text(encoding='utf-8').strip().lower() if p.exists() else ''; sys.exit(0 if marker == '%INSTALL_PROFILE%' else 1)" >nul 2>nul
if not errorlevel 1 (
  call ".venv\Scripts\python.exe" -c "import sys, torch, torchaudio; build = getattr(getattr(torch, 'version', None), 'cuda', None); audio_ver = getattr(torchaudio, '__version__', ''); profile = '%INSTALL_PROFILE%'; ok_cpu = (not build) and ('+cu' not in audio_ver); ok_nvidia = bool(build) and ('+cu' in audio_ver); ok = ok_cpu if profile == 'cpu' else ok_nvidia; sys.exit(0 if ok else 1)" >nul 2>nul
  if not errorlevel 1 (
    echo [torch] Reusing existing %INSTALL_PROFILE% PyTorch runtime...
    exit /b 0
  )
)
if /i "%INSTALL_PROFILE%"=="cpu" (
  echo [torch] Installing CPU-only PyTorch runtime...
  call ".venv\Scripts\python.exe" -m pip uninstall -y torch torchaudio >nul 2>nul
  call ".venv\Scripts\python.exe" -m pip install --upgrade -r requirements.torch.cpu.txt
  if errorlevel 1 (
    echo Failed to install CPU-only PyTorch runtime from requirements.torch.cpu.txt
    exit /b 1
  )
) else (
  echo [torch] Installing NVIDIA CUDA 12.8 PyTorch runtime...
  call ".venv\Scripts\python.exe" -m pip uninstall -y torch torchaudio >nul 2>nul
  call ".venv\Scripts\python.exe" -m pip install --upgrade -r requirements.torch.cuda.txt
  if errorlevel 1 (
    echo Failed to install NVIDIA CUDA PyTorch runtime from requirements.torch.cuda.txt
    exit /b 1
  )
)
>"%TORCH_PROFILE_STATE_FILE%" echo %INSTALL_PROFILE%
exit /b 0

:resolve_install_profile
if not exist "user-data" mkdir "user-data"
if not "%INSTALL_PROFILE_OVERRIDE%"=="" (
  set "INSTALL_PROFILE=%INSTALL_PROFILE_OVERRIDE%"
  >"%INSTALL_PROFILE_FILE%" echo %INSTALL_PROFILE%
  exit /b 0
)
if exist "%INSTALL_PROFILE_FILE%" (
  set /p INSTALL_PROFILE=<"%INSTALL_PROFILE_FILE%"
  set "INSTALL_PROFILE=%INSTALL_PROFILE: =%"
  if /i "%INSTALL_PROFILE%"=="cpu" exit /b 0
  if /i "%INSTALL_PROFILE%"=="nvidia" exit /b 0
)
echo Select local runtime profile:
echo   [1] NVIDIA GPU ^(CUDA 12.8^) - recommended for NVIDIA cards
echo   [2] CPU-only - recommended for AMD, Intel, or no-GPU machines
set "INSTALL_CHOICE="
set /p INSTALL_CHOICE=Choose 1 or 2 [1]: 
if "%INSTALL_CHOICE%"=="" set "INSTALL_CHOICE=1"
if "%INSTALL_CHOICE%"=="2" (
  set "INSTALL_PROFILE=cpu"
) else (
  set "INSTALL_PROFILE=nvidia"
)
>"%INSTALL_PROFILE_FILE%" echo %INSTALL_PROFILE%
echo [info] Saved install profile to user-data\install_profile.txt
exit /b 0

:prepare_local_environment
if not exist "%PROJECT_CACHE_DIR%" mkdir "%PROJECT_CACHE_DIR%"
if not exist "%PROJECT_CACHE_DIR%\pip" mkdir "%PROJECT_CACHE_DIR%\pip"
if not exist "%PROJECT_CACHE_DIR%\torch" mkdir "%PROJECT_CACHE_DIR%\torch"
if not exist "%PROJECT_CACHE_DIR%\matplotlib" mkdir "%PROJECT_CACHE_DIR%\matplotlib"
if not exist "%PROJECT_CACHE_DIR%\numba" mkdir "%PROJECT_CACHE_DIR%\numba"
if not exist "%PROJECT_CACHE_DIR%\xdg" mkdir "%PROJECT_CACHE_DIR%\xdg"
if not exist "%PROJECT_CACHE_DIR%\cuda" mkdir "%PROJECT_CACHE_DIR%\cuda"
if not exist "%PROJECT_HF_DIR%" mkdir "%PROJECT_HF_DIR%"
if not exist "%PROJECT_HF_DIR%\hub" mkdir "%PROJECT_HF_DIR%\hub"
if not exist "%PROJECT_HF_DIR%\transformers" mkdir "%PROJECT_HF_DIR%\transformers"
if not exist "%PROJECT_HF_DIR%\datasets" mkdir "%PROJECT_HF_DIR%\datasets"
if not exist "%PROJECT_TEMP_DIR%" mkdir "%PROJECT_TEMP_DIR%"
set "PYTHONNOUSERSITE=1"
set "PIP_CACHE_DIR=%PROJECT_CACHE_DIR%\pip"
set "HF_HOME=%PROJECT_HF_DIR%"
set "HUGGINGFACE_HUB_CACHE=%PROJECT_HF_DIR%\hub"
set "TRANSFORMERS_CACHE=%PROJECT_HF_DIR%\transformers"
set "HF_DATASETS_CACHE=%PROJECT_HF_DIR%\datasets"
set "TORCH_HOME=%PROJECT_CACHE_DIR%\torch"
set "MPLCONFIGDIR=%PROJECT_CACHE_DIR%\matplotlib"
set "NUMBA_CACHE_DIR=%PROJECT_CACHE_DIR%\numba"
set "XDG_CACHE_HOME=%PROJECT_CACHE_DIR%\xdg"
set "CUDA_CACHE_PATH=%PROJECT_CACHE_DIR%\cuda"
set "TMP=%PROJECT_TEMP_DIR%"
set "TEMP=%PROJECT_TEMP_DIR%"
exit /b 0
