# stream-sub-translator

Windows-first local real-time subtitle translator for streamers.

Current state: runnable local app with modular backend, dark UI, overlay page, real local microphone capture, local VAD segmentation, real local NeMo-backed Parakeet ASR wiring, an optional browser speech worker mode, and websocket transcript updates to the dashboard.
Translation foundation is now present with optional provider-based translation, ordered target languages, local JSON settings, websocket translation events, and translated result rendering in the dashboard.
Subtitle routing now produces a unified local payload flow for source text plus translated lines, shared by the dashboard preview and OBS overlay updates.
The dashboard now also includes a first complete local subtitle style system with built-in presets, custom editing, and shared style rendering between the dashboard preview and the OBS overlay.
The dashboard and browser speech worker now support bilingual UI localization with a top-right language switcher (`English` / `Русский`), and the advanced tuning labels use clearer human-readable wording in both languages.

## Main dashboard layout
- The top dashboard area is now arranged as a compact operator layout:
  - left: `Transcript`
  - left-bottom: `OBS Overlay URL`
  - right-top: `Recognition`
  - right-middle: `Microphone`
  - right-bottom: `Subtitle Output Preview`
- The main work sections stay in horizontal tabs below that overview:
  - `Translation`
  - `Subtitles`
  - `Style`
  - `OBS`
  - `Tuning`
  - `Tools & Data`
- The top bar also includes a pinned `Save` button for quick config saves.

## UI localization
- The main dashboard supports two UI languages:
  - `English`
  - `Русский`
- The language switcher lives in the top-right corner of the header.
- The browser speech worker window follows the same saved UI language.
- Diagnostic runtime dumps stay in English even when the rest of the UI is switched to Russian.
- `Recognition language` is shown only when `Recognition method = Browser Speech`.
- Advanced recognition tuning labels were rewritten in clearer user-facing wording in both languages, including:
  - VAD mode descriptions
  - quiet-input / noise gate controls
  - partial/final timing controls
  - subtitle hold / replacement timing

## Tech stack
- Python 3.11+
- FastAPI + Uvicorn
- WebSockets
- Plain HTML/CSS/JavaScript (no Node.js, no bundler)

## Project tree
This repository follows the AGENTS.md structure, including:
- `backend/` for API + core pipeline modules
- `frontend/` for dashboard UI
- `overlay/` for OBS browser source page
- `fonts/` for project-local custom fonts loaded into both preview and overlay
- `start.bat` and `update.bat` for Windows one-click workflows

## Desktop launcher entrypoint
- The desktop launcher now exists as a first-class Python entrypoint:
  - source/dev command: `python -m desktop.launcher`
  - release/user entrypoint: `Stream Subtitle Translator.exe`
- Desktop mode starts the same local FastAPI app on:
  - `127.0.0.1:8765`
- Desktop mode does not open the system browser for the main dashboard.
- Instead, it waits for local health readiness and loads the dashboard inside a `pywebview` window.
- Closing the desktop window shuts down the backend subprocess cleanly.
- The desktop `exe` is now intentionally a thin launcher shell:
  - it does not freeze the full `torch` / `NeMo` / `CUDA` runtime stack into the launcher itself
  - it prepares or reuses the local `.python\` / `.venv\` runtime
  - it starts the backend as a regular local Python subprocess
  - this keeps the desktop window as the main user entrypoint while avoiding fragile frozen-ML startup failures
- The splash launcher now offers three startup choices inside the runtime profile block:
  - `Quick Start` = Browser Speech only
  - `NVIDIA GPU (CUDA)` = local AI runtime with GPU-first PyTorch profile
  - `CPU-only` = local AI runtime with CPU fallback profile
- `Quick Start` intentionally skips local AI dependency installation:
  - it prepares only the lighter desktop/backend runtime
  - it sets the session to `Browser Speech` mode before the dashboard opens
  - the recognition-mode switch is locked in that session so the user does not accidentally trigger local AI installation from the main window
- OBS overlay remains external by design and is still served from the same local app:
  - `http://127.0.0.1:8765/overlay`
- Browser Speech worker also remains external by design:
  - `http://127.0.0.1:8765/google-asr`
  - in desktop mode it opens in an external Chrome/Chromium window, not inside the embedded webview
- If the backend cannot start or the port is already occupied, the launcher shows a desktop error dialog instead of relying on a console window.
- The desktop splash window now also shows temporary startup logs, including:
  - local runtime bootstrap
  - dependency/profile work
  - backend startup progress
  - first model download progress
- Persistent desktop/client logs are written to the project `logs/` folder:
  - `logs/desktop-launcher.log`
  - `logs/overlay-events.log`
  - `logs/browser-recognition.log`
  - `logs/dashboard-live-events.log`

## Windows desktop packaging
- Desktop packaging target is now:
  - `PyInstaller` one-folder distribution
- Build command:
  - `build-desktop.bat`
- Expected output:
  - `dist\Stream Subtitle Translator\Stream Subtitle Translator.exe`
- The packaged desktop build includes:
  - the main desktop `exe`
  - bundled code/assets under `app-runtime\`
  - bundled `backend/`, `frontend/`, `overlay/`, and `fonts/` sources/assets inside that packaged runtime folder
  - bundled sample runtime files such as `backend/data/config.example.json`
  - bundled bootstrap/runtime reference files such as `bootstrap-python.ps1`, `requirements.txt`, `requirements.torch.cpu.txt`, `requirements.torch.cuda.txt`, and `README.md`
- The build step also seeds the packaged folder with the current local runtime when available:
  - `.python\`
  - `.venv\`
- On desktop startup, the launcher can:
  - reuse those seeded runtime folders
  - repair them if they are invalid
  - or bootstrap them again for a cold local start
- On first run, the desktop build creates writable local directories next to the `exe` for:
  - `user-data/cache`
  - `user-data/exports`
  - `user-data/models`
  - `user-data/profiles`
  - `logs`
- Runtime temp/cache folders for backend processing are created under:
  - `C:\Users\Public\Documents\StreamSubtitleTranslatorRuntime\<project>-<hash>\`
- A local webview cache folder may also appear under:
  - `.cache\pywebview`
- In packaged desktop mode:
  - `app-runtime\` is the required bundled application/runtime folder and should be updated together with the `exe`
  - `user-data\` is created automatically on first launch and contains only writable local user/runtime data
- Release flow and dev flow are now intentionally separate:
  - `start.bat` / `update.bat` remain dev/bootstrap tools
  - `Stream Subtitle Translator.exe` is the intended user-facing entrypoint for packaged builds

## Exact startup instructions (Windows dev/bootstrap)
1. Open terminal in the project root:
   - `F:\AI\stream-sub-translator`
2. Run:
   - `start.bat`
3. `start.bat` now performs true portable-first Python bootstrap:
   - it first checks `.\.python\python.exe`
   - if missing, it automatically downloads the pinned official CPython Windows NuGet package
   - it extracts that package and provisions CPython into `.\.python\`
   - it then creates `.venv\` from that local runtime
4. On the first dependency install, `start.bat` asks for a local ASR runtime profile:
   - `NVIDIA GPU (CUDA 12.8)` for NVIDIA cards
   - `CPU-only` for AMD, Intel, or no-GPU Windows machines
5. The selected install profile is saved locally in:
   - `user-data/install_profile.txt`
6. Browser opens:
   - `http://127.0.0.1:8765/`
7. OBS overlay URL:
   - `http://127.0.0.1:8765/overlay`
8. Optional OBS Closed Captions output:
   - disabled by default
   - uses the local OBS websocket connection
   - configured from the dashboard under `OBS Closed Captions`
   - keeps one persistent OBS websocket session alive while runtime is active and OBS CC remains enabled

Development note:
- `start.bat` is still the recommended bootstrap flow for creating `.python\` and `.venv\`.
- After the environment exists, you can also test the desktop shell directly from source:
  - `.venv\Scripts\python.exe -m desktop.launcher`

Important:
- The current real ASR target is the official EU multilingual model:
  - `nvidia/parakeet-tdt-0.6b-v3`
- AMD GPU acceleration is not implemented in this Windows-first build.
  - AMD owners should choose the `CPU-only` install profile.
  - CPU-only install avoids NVIDIA CUDA PyTorch wheels entirely.
- If that model is missing or invalid, the app still opens, but pressing `Start` returns runtime status `error` with a clear ASR message.
- Importing the app and opening health/status diagnostics no longer restores the NeMo model eagerly; full ASR runtime initialization is deferred until runtime start.

`start.bat` performs:
1. Project-local Python resolution
   - official runtime folder: `.\.python\`
2. Automatic CPython provisioning if `.\.python\python.exe` is missing
   - downloads the pinned official CPython 64-bit Windows NuGet package
   - extracts `tools\` from that package into `.\.python\`
   - does not require admin privileges
   - does not modify global `PATH`
   - does not register a machine-wide or user-wide Python install
3. `.venv` creation or repair from that local runtime
4. local ASR runtime profile selection (`NVIDIA GPU` or `CPU-only`)
5. profile-specific PyTorch install
6. shared dependency install from `requirements.txt`
7. model directory creation (`user-data\models`)
8. local preflight summary
9. FastAPI start
10. browser open + console kept open for logs

## Manual startup (optional)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.torch.cpu.txt
pip install -r requirements.txt
python -m backend.run --open-browser
```

Manual install note:
- replace `requirements.torch.cpu.txt` with `requirements.torch.cuda.txt` on NVIDIA machines
- keep `requirements.torch.cpu.txt` for AMD, Intel, or no-GPU Windows machines

Portable Windows note:
- Normal users do not need to install Python manually before running `start.bat`.
- The official project-local runtime folder is:
  - `.\.python\`
- The official project-local app environment folder is:
  - `.\.venv\`
- The pinned auto-provisioned runtime is:
  - CPython `3.11.9` 64-bit for Windows
- The provisioning source is the official Python NuGet package URL:
  - `https://api.nuget.org/v3-flatcontainer/python/3.11.9/python.3.11.9.nupkg`
- The bootstrap flow extracts the official CPython package into the project and no longer relies on the Windows EXE installer path.
- The project does not fall back to system Python anymore. Startup and updates use only:
  - project-local CPython in `.python\`
  - project-local virtual environment in `.venv\`
- If local Python bootstrap fails, `start.bat` / `update.bat` stop with an error instead of using any system interpreter.
- Python `3.10` is not used anymore, because several pinned wheels in this project require Python `3.11`.
- Shared install-critical wheels are pinned to versions verified on a clean Windows machine:
  - `numpy==2.2.6`
  - `onnxruntime==1.23.2`
- Bootstrap/update cache folders are project-local:
  - `.cache\pip`
  - `.cache\huggingface`
  - `.cache\torch`
  - `.cache\matplotlib`
  - `.cache\numba`
  - `.cache\cuda`
  - `.tmp`
- Backend runtime cache/temp folders are isolated under:
  - `C:\Users\Public\Documents\StreamSubtitleTranslatorRuntime\<project>-<hash>\`
- Runtime root can be overridden with:
  - `SST_RUNTIME_ROOT`
- The launcher also sets `PYTHONNOUSERSITE=1`, so user-level site-packages from the system profile are not imported into this project.

## Update workflow
Run:
- `update.bat`

Optional cache clear:
- `update.bat --clear-cache`

Optional install profile override:
- `start.bat --cpu`
- `start.bat --nvidia`
- `update.bat --cpu`
- `update.bat --nvidia`

If no override flag is passed, both scripts reuse the locally saved profile from `user-data/install_profile.txt`.

## Desktop build workflow
1. Run `start.bat` once so the project-local runtime and `.venv\` already exist.
2. Run:
   - `build-desktop.bat`
3. Test the packaged result from:
   - `dist\Stream Subtitle Translator\Stream Subtitle Translator.exe`
4. Publish/update desktop release folders:
   - `powershell -ExecutionPolicy Bypass -File .\publish-desktop-releases.ps1`
5. Default publish targets:
   - installed release: `F:\AI\stream-sub-translator-desktop-release`
   - clean release: `F:\AI\stream-sub-translator-desktop-release-clean` (contains only `Stream Subtitle Translator.exe` + `app-runtime\`)

Desktop runtime note:
- The desktop shell targets `pywebview` on Windows and expects a modern local webview runtime.
- The dashboard frontend is modern enough that the intended Windows renderer path is Edge/WebView2 rather than an old IE-based fallback.
- The packaged backend now runs from the local Python environment next to the desktop launcher, not from an embedded frozen ASR runtime.

## Implemented API endpoints
- `GET /api/health`
- `POST /api/runtime/start`
- `POST /api/runtime/stop`
- `GET /api/runtime/status`
- `GET /api/settings/load`
- `POST /api/settings/save`
- `GET /api/devices/audio-inputs`
- `GET /api/obs/url`

Also present:
- `GET /api/profiles`
- `GET /api/profiles/{name}`
- `POST /api/profiles/{name}`
- `DELETE /api/profiles/{name}`
- `GET /api/exports`
  - lists generated local export files with size and modified timestamp
- `WS /ws/events`

## ASR diagnostics and instrumentation
- `GET /api/health` now includes structured ASR diagnostics:
  - active ASR provider
  - model path
  - provider capability flags
  - whether GPU execution is requested
  - whether GPU execution is available
  - selected execution device/provider in practice
  - whether partial transcripts are supported
  - current audio/VAD window settings when known
- Before runtime start, ASR diagnostics stay lightweight and report that full dependency/model initialization is deferred.
- `GET /api/runtime/status` now includes:
  - `asr_diagnostics`
  - `metrics`
- WebSocket `runtime_update` events also carry the same runtime diagnostics and metrics.
- Current latency metrics:
  - `vad_ms`
  - `asr_partial_ms`
  - `asr_final_ms`
  - `translation_ms`
  - `total_ms`
- These metrics are best-effort instrumentation and do not change recognition behavior if collection fails.

## ASR provider abstraction
- The runtime now treats ASR behind a provider interface instead of coupling the app directly to one concrete backend.
- Provider-facing capability fields include:
  - `provider_name`
  - `supports_gpu`
  - `supports_partials`
  - `supports_streaming`
  - `supports_word_timestamps`
  - `actual_selected_device`
  - `actual_execution_provider`
  - `model_path`
  - `diagnostics()`
- The current baseline provider remains the official local NeMo-backed EU Parakeet path:
  - `official_eu_parakeet`
- A second provider now also exists behind the same abstraction:
  - `official_eu_parakeet_realtime`
- Provider behavior is intentionally honest:
  - `official_eu_parakeet` remains the stable final-first baseline
  - `official_eu_parakeet_realtime` uses the same official local `.nemo` model through a direct in-memory NeMo path
    - `official_eu_parakeet_realtime` can emit real partial transcript updates from the current growing speech segment
    - the realtime path remains tuned conservatively for quality first, while advanced VAD admission controls stay optional
  - This keeps the working prototype stable while preserving the earlier transcription quality baseline.

## Transcript segment and event model
- Transcript payloads now have a stable segment model that can support both the current final-first provider and future streaming-capable providers.
- Each transcript segment can carry:
  - `segment_id`
  - `text`
  - `is_partial`
  - `is_final`
  - `start_ms`
  - `end_ms`
  - `source_lang`
  - `provider`
  - `latency_ms`
  - `sequence`
  - `revision`
- Backend lifecycle event types are prepared for:
  - `segment_started`
  - `partial_updated`
  - `segment_finalized`
- WebSocket compatibility remains practical:
  - the existing `transcript_update` flow still drives the current dashboard
  - the backend can also emit `transcript_segment_event` for provider-agnostic segment lifecycle work
- Current official `.nemo` recognition remains final-first in practice on the baseline provider.
- When the realtime provider is selected, `partial_updated` events can carry real provider output for the current in-progress segment.

## Local config and profiles
- All runtime configuration is JSON-only and local-only under `user-data/`.
- Main live config file: `user-data/config.json`.
- `user-data/config.json` and `user-data/profiles/*.json` are local machine files and should stay out of git.
- Safe committed references live in:
  - `backend/data/config.example.json`
  - `backend/data/dictionary_overrides.example.json`
- If `user-data/config.json` is missing, the backend auto-generates a default local config on startup using built-in defaults, so first-run startup still works without copying any file manually.
- Local bind and URL source of truth is fixed in backend settings:
  - host: `127.0.0.1`
  - port: `8765`
- These values are intentionally not editable through the JSON settings UI.
- Profiles are stored as JSON files under `user-data/profiles/`:
  - example: `user-data/profiles/default.json`
- Dashboard supports:
  - save current config
    - a primary `Save` button is pinned near the top tab bar for quick access
    - the `Local Config` section still exposes save/export/import tools for raw JSON work
  - export config to file
  - import config from file
  - list profiles
  - load profile into current config
  - save profile
  - delete profile
  - persist selected local microphone id
  - persist translation settings and provider credentials locally
- Active profile source of truth is `config.profile`.
- Saving from the dashboard applies most settings immediately through the live runtime settings path.
- The following settings should be treated as restart-sensitive and take effect on the next `Start` or after `Stop` -> `Start` if runtime is already active:
  - microphone device (`audio.input_device_id`)
  - ASR provider preference (`asr.provider_preference`)
  - ASR GPU policy (`asr.prefer_gpu`)
- ASR backend preference is stored locally under `asr` in `user-data/config.json`:
  - `provider_preference`
  - `prefer_gpu`
- Supported provider preference values:
  - `official_eu_parakeet_realtime`
  - `official_eu_parakeet`
  - `auto`

## Audio input enumeration (local-only)
- Audio devices are enumerated locally via `sounddevice` (`PortAudio`) on the same Windows machine.
- Endpoint: `GET /api/devices/audio-inputs`.
- Returned entries include:
  - device id (local index)
  - device name
  - default flag
  - max input channels
  - default sample rate
- If no microphone devices are available or enumeration fails, API returns a safe empty list (`devices: []`) and UI remains usable.

## Recognition flow (step 4)
- Open the local UI.
- Choose a microphone from the local device dropdown.
- Press `Start`.
- The backend starts:
  - local microphone capture via `sounddevice`
  - ring buffer updates
  - streaming VAD segmentation via `webrtcvad`
  - ASR work queue processing
  - websocket transcript events to the dashboard
- The dashboard shows:
  - runtime state updates
  - partial transcript updates
  - final transcript lines
  - ASR diagnostics badges
  - latest latency metrics
- The default provider is now `official_eu_parakeet_realtime`.
- GPU-preferred execution is the default expected path.
- If the app cannot activate realtime GPU mode, it enters an explicitly degraded fallback mode instead of pretending CPU mode is normal.
- The older `official_eu_parakeet` path remains available only for fallback/debug compatibility.

## Realtime tuning controls
- Local config now includes:
  - `asr.realtime` for low-level realtime ASR cadence
  - `subtitle_lifecycle` for completed subtitle block timing
- The normal dashboard flow now uses three simpler controls first:
  - how quickly text appears
  - how quickly speech is considered finished
  - how stable / less chatty updates should be
- Raw ASR/VAD timing fields remain available under `Tools & Data` -> `Advanced Recognition & Diagnostics`.
- Subtitle presentation timing is configured in `Subtitle Output`:
  - completed source hold
  - completed translation hold
  - keep source paired with translation while translation is visible
  - early replace when the next phrase finalizes
- In `Advanced Realtime Tuning`, important raw fields now show inline `default / safer` hints directly beside the control instead of using a separate note block.
- The dashboard also includes an optional `RNNoise noise reduction (experimental)` path:
  - off by default
  - local-only
  - applied only to recognition input after VAD has produced a speech segment
  - configurable with a `0% .. 100%` strength slider
  - strength is implemented as a wet/dry mix:
    - `0%` keeps the raw recognition audio
    - `100%` uses the full RNNoise output
  - intended to reduce false recognition from constant background noise
  - may still change recognition behavior depending on the mic and room
  - when the recognition path is not already `48000 Hz`, the app uses an explicit resample path:
    - input recognition audio -> `48000 Hz` RNNoise processing -> resample back to the ASR input rate
  - if the RNNoise backend is unavailable, diagnostics report that honestly and recognition stays on the raw path
- Current local defaults:
  - `vad_mode: 3`
  - `partial_emit_interval_ms: 450`
  - `min_speech_ms: 180`
  - `first_partial_min_speech_ms: 180`
  - `silence_hold_ms: 180`
  - `pause_to_finalize_ms: 350`
  - `hard_max_phrase_ms: 5500`
  - `completed_source_ttl_ms: 4500`
  - `completed_translation_ttl_ms: 4500`
  - `allow_early_replace_on_next_final: true`
  - `sync_source_and_translation_expiry: true`
  - `chunk_window_ms: 0`
  - `chunk_overlap_ms: 0`
  - `partial_min_delta_chars: 4`
  - `partial_coalescing_ms: 160`
  - `energy_gate_enabled: false`
  - `min_rms_for_recognition: 0.0018`
  - `min_voiced_ratio: 0.0`
- Practical effect:
  - these defaults trade a little micro-update frequency for much better stability on long continuous speech
  - lower `pause_to_finalize_ms` makes a spoken phrase finalize sooner after a meaningful pause
  - higher `partial_min_delta_chars` and `partial_coalescing_ms` suppress noisy micro-updates
  - lower `hard_max_phrase_ms` prevents one long uninterrupted phrase from growing into a huge expensive ASR segment
  - higher completed source/translation hold values keep finished subtitles on screen longer
- Safety notes:
  - these settings are applied to `official_eu_parakeet_realtime`
    - the baseline provider keeps the older final-first behavior for compatibility
    - `chunk_window_ms` and `chunk_overlap_ms` remain advanced compatibility/tuning fields
    - advanced VAD admission also includes:
      - `vad_mode`
      - `energy_gate_enabled`
      - `min_rms_for_recognition`
      - `min_voiced_ratio`
      - `first_partial_min_speech_ms`
    - these controls are optional and should be enabled carefully, because overly aggressive admission can hurt recognition quality
- Dashboard diagnostics now also expose:
  - effective VAD/realtime timing values
  - `partial_updates_emitted`
  - `finals_emitted`
  - `suppressed_partial_updates`

## Subtitle style system
- Subtitle style is now persisted locally inside the same JSON config/profile payloads:
  - `subtitle_style`
- Built-in presets currently included:
  - `clean_default`
  - `streamer_bold`
  - `dual_tone`
  - `compact_overlay`
  - `soft_shadow`
  - `jp_stream_single`
  - `jp_dual_caption`
- The dashboard `Subtitle Style` section lets you:
  - choose a built-in preset
  - save the current edited style as a custom local preset
  - delete a saved custom local preset
  - edit the shared base subtitle style
  - override separate line slots for:
    - `source`
    - `translation_1`
    - `translation_2`
    - `translation_3`
    - `translation_4`
    - `translation_5`
- Current style controls include:
  - font family
  - font size and weight
  - fill color
  - outline color and width
  - shadow color, blur, and offset
  - background color, opacity, padding, and radius
  - line spacing
  - letter spacing
  - text alignment
  - line gap
  - simple effect preset:
    - `none`
    - `fade`
    - `subtle_pop`
- Font handling:
  - project-local fonts are the reliable custom-font path
  - place `.ttf`, `.otf`, `.woff`, or `.woff2` files into:
    - `fonts/`
  - both the dashboard preview and the OBS overlay load them through generated `@font-face` rules from the same FastAPI app
  - fallback Windows-friendly font families stay available even with no custom fonts
  - best-effort system font enumeration is attempted from the browser when supported, but the app does not depend on it
- Visible translated subtitle lines are intentionally capped at `5` for style-slot control and rendering consistency.
- Rendering behavior:
  - the dashboard preview and OBS overlay both render from the same subtitle style payload shape
  - runtime overlay payloads now carry resolved effective style data
  - while editing locally in the dashboard, the preview reflects the current local style draft immediately
  - after saving, the overlay and runtime payloads use the same saved style state

## Official EU multilingual Parakeet model
- Current real ASR target:
  - `nvidia/parakeet-tdt-0.6b-v3`
- This is downloaded and stored locally.
- Local install destination:
  - `user-data/models/parakeet-tdt-0.6b-v3/parakeet-tdt-0.6b-v3.nemo`
- Reproducible local install command:
```powershell
.\.venv\Scripts\python.exe -m backend.install_asr_model --model eu
```
- Direct official download source used by the installer:
  - [Hugging Face model page](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3)
- Runtime behavior:
  - if the official EU model is installed and NeMo runtime dependencies are present, real local inference is used
  - if the model is missing, the first `Start` in the dashboard now downloads it automatically into `user-data/models/`
  - while that first-start download/load is running, the dashboard shows `runtime: starting ...` and `start.bat` shows download progress in the console
  - if the model download fails or the local file is invalid, runtime start fails clearly
  - the app does not silently pretend recognition is real
- CPU fallback remains safe.
- GPU can now be requested through local ASR config:
  - `user-data/config.json`
  - `asr.prefer_gpu = true`
- If CUDA is available and the selected provider initializes successfully on GPU, diagnostics report `selected_device = cuda`.
- If GPU is requested but unavailable or initialization fails, diagnostics report CPU fallback clearly instead of pretending GPU is active.
- Mock ASR is only allowed when explicitly enabled through:
  - `STREAM_SUB_TRANSLATOR_ALLOW_MOCK_ASR=1`

## ASR backend options
- `browser_google`
  - optional browser speech worker mode
  - opens a separate browser window at `/google-asr`
  - uses the browser `SpeechRecognition` / `webkitSpeechRecognition` API instead of local NeMo inference
  - forwards partial/final text back into the same local subtitle and translation pipeline over `/ws/asr_worker`
  - browser-dependent and best used in Chrome/Chromium-class browsers
  - may rely on browser-managed online recognition services depending on the browser/runtime
- `official_eu_parakeet_realtime`
  - default provider
  - GPU-first expected path
  - lower-latency provider using the same official local `.nemo` model
  - direct in-memory NeMo transcription path
    - real partial transcript updates on the current growing segment
    - `supports_partials = true`
    - `supports_streaming = false`
- `official_eu_parakeet`
  - baseline fallback/debug provider
  - NeMo file-based transcription path
  - final-first behavior
  - `supports_partials = false`
  - `supports_streaming = false`
- `auto`
  - tries `official_eu_parakeet_realtime` first
  - falls back to `official_eu_parakeet`
- Default policy:
  - `mode = local`
  - `provider_preference = official_eu_parakeet_realtime`
  - `prefer_gpu = true`
- Degraded mode examples:
  - realtime provider active on CPU because GPU is unavailable
  - baseline provider active because realtime provider could not initialize

## Real ASR dependencies
- The official EU Parakeet path uses local NeMo runtime dependencies.
- Install/update project dependencies with:
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```
- The requirements now include the NeMo ASR runtime package used for local inference.
- On Windows, the project requirements now also pin the CUDA-enabled PyTorch stack used by the realtime GPU path:
  - `torch==2.11.0+cu128`
  - `torchaudio==2.11.0+cu128`
  - `fsspec==2024.12.0` to stay compatible with `nemo-toolkit==2.7.2`
- Important for Windows GPU use:
  - the project only uses GPU if the same local `.venv` contains a CUDA-enabled PyTorch build
  - a CPU-only PyTorch build will force honest CPU fallback even if the machine has an NVIDIA GPU

## Translation subsystem
- Translation is optional and recognition keeps working when translation is disabled or fails.
- Translation runs on the separate translation queue and does not block the realtime ASR path.
- Translation is applied to final transcript segments only by default.
- Browser Speech final transcript segments are fed into the same translation queue as the local ASR path.
- Translation settings now apply live after `Save Current Config` without restarting the whole app.
- Live apply behavior:
  - provider changes, API key changes, endpoint/base URL changes, model changes, custom prompt changes, target language changes, and subtitle visibility/order changes are applied to the running translation layer
  - the ASR runtime is not restarted just to apply translation settings
  - the latest subtitle payload is republished immediately so dashboard preview and overlay reflect saved visibility/order settings
  - new provider/client settings affect new finalized transcript segments; already finished translations are not retroactively regenerated
- Translation config is stored locally in JSON:
  - `translation.enabled`
  - `translation.provider`
  - `translation.target_languages`
  - `translation.provider_settings`
- Provider credentials and prompt overrides remain local in:
  - `user-data/config.json`
  - `user-data/profiles/*.json`
- These local files are intentionally gitignored so machine-specific settings and secrets do not get committed by accident.
- Translation cache key:
  - `(source_text, source_lang, target_lang)`
- Translation cache is cleared automatically when live translation provider settings change, so switching provider/key/model does not keep reusing stale cached results from an older configuration.
- Translation readiness is now summarized compactly in startup preflight output and in the dashboard diagnostics area.
- Practical translation readiness states:
  - `disabled`
  - `ready`
  - `partial`
  - `experimental`
  - `degraded`
  - `error`
- Output combinations supported end-to-end:
  - source only
  - translation only
  - source + one translation
  - source + multiple translations
  - multiple translations without source text
- Ordering and visibility are controlled by saved local config/profile settings and shared by:
  - dashboard translated results
  - dashboard subtitle output preview
  - overlay payload routing

## Translation providers
- Stable / recommended:
  - Google Translate v2
  - Azure Translator
- Flexible LLM providers:
  - OpenAI
  - OpenRouter
- Local LLM providers:
  - LM Studio
  - Ollama
- Classic MT providers kept available:
  - DeepL
  - LibreTranslate
- Experimental / no-key public web providers:
  - Google Web
  - Google GAS URL
  - MyMemory
  - Public LibreTranslate mirror
  - Free Web Translate
- Experimental providers are best-effort only and are not the recommended default path.

## Subtitle routing and overlay payload flow (step 5B)
- Final transcript segments are routed into a unified subtitle record keyed by local sequence id.
- When translation is enabled, translated results are merged into that same record.
- The backend builds one local subtitle payload containing:
  - source text
  - translated lines
  - saved display order
  - source/translation visibility flags
  - max visible translated language count
  - full ordered `visible_items`
  - overlay-friendly `line1` / `line2` values
  - lifecycle state for shared dashboard/overlay rendering
- The dashboard preview and the OBS overlay both follow the saved subtitle output settings from local config/profile JSON.
- OBS Closed Captions is now a separate optional local output target:
  - it does not replace the browser overlay
  - it keeps one persistent `obs-websocket` connection while runtime is active instead of reconnecting for every caption send
  - it uses `SendStreamCaption`, so OBS must have an active stream output; preview-only OBS is not enough
  - optional debug mirroring can also write the same text into a normal OBS text input via `SetInputSettings` (for example `CC_DEBUG`)
  - diagnostics expose `connection_state`, reconnect attempts, and whether the last send reused an already-active connection
  - `source_live` sends partial plus final source captions with its own throttle controls
  - `source_final_only` sends finalized source text only
  - `translation_1` .. `translation_5` send finalized visible translated lines by visible translation slot
  - `first_visible_line` follows the current saved subtitle output order and visibility
  - a practical debug setup is:
    - partials -> debug text input only
    - finals -> native `SendStreamCaption` plus the debug text input
- Output modes supported by the routing layer:
  - source only
  - translation only
  - source + one translation
  - source + multiple translations
- For more than two visible subtitle lines, the overlay payload keeps the full ordered `visible_items` list and also composes:
  - `line1`: first visible item
  - `line2`: remaining visible items joined for lightweight overlay rendering
- The overlay now renders from the ordered `visible_items` list and no longer drops translated lines after the first source line.

## Subtitle output settings
- Local config now includes `subtitle_output`:
  - `show_source`
  - `show_translations`
  - `max_translation_languages`
  - `display_order`
- Local config also includes `subtitle_lifecycle`:
  - `completed_source_ttl_ms`
  - `completed_translation_ttl_ms`
  - `pause_to_finalize_ms`
  - `sync_source_and_translation_expiry`
  - `allow_early_replace_on_next_final`
  - `hard_max_phrase_ms`
- `display_order` is shared by:
  - dashboard subtitle output preview
  - overlay payload generation
- In the dashboard UI, subtitle timing values are shown in seconds for easier tuning:
  - example: `1.0`, `2.5`, `4.5`
- In saved JSON config/profile files, the same timing values remain stored in milliseconds:
  - example: `1000`, `2500`, `4500`
- This allows local combinations such as:
  - source only
  - English only
  - English + Japanese
  - source + English
  - source + English + Japanese

## Subtitle lifecycle behavior
- Subtitle presentation is now separate from raw ASR finalization.
- The runtime tracks:
  - an active partial phrase
  - one currently displayed completed subtitle block
- Translated lines come from the latest completed subtitle block.
- Source text can keep streaming live while the previous translated block is still visible.
- Completed block behavior:
  - a phrase normally finalizes after `pause_to_finalize_ms`
  - after finalization, the completed source line and its translations become the current completed subtitle block
  - `completed_source_ttl_ms` controls how long the finished source line stays visible
  - `completed_translation_ttl_ms` controls how long the finished translated lines stay visible
  - if `sync_source_and_translation_expiry` is enabled, the completed source stays together with its translation until the translation timer ends
  - if the next phrase is still partial, the old completed source is hidden and the new live source starts updating immediately, while the old completed translation may remain visible until it expires
  - when the next phrase finalizes, it can replace the previous completed translation block immediately
  - old subtitle blocks do not queue up
- Expiry behavior:
  - source and translation can now expire independently
  - if the old completed block expires while a new phrase is already in progress, the new live partial source remains visible
- Dashboard preview and OBS overlay now follow the same lifecycle behavior.
- Practical UI mapping:
  - if `Completed source hold (seconds)` is set to `1.0`, the finished source line should remain for about one second
  - if `Completed translation hold (seconds)` is set to `1.0`, the finished translated lines should remain for about one second
  - if `Keep completed source visible while its translation is still visible` is enabled, the source can stay as long as the translation stays

## Provider-specific settings
- The dashboard now hides irrelevant translation fields for the selected provider instead of showing one generic pile of inputs.
- Google Translate v2:
  - `api_key`
- Google GAS URL:
  - `gas_url`
- Azure Translator:
  - `api_key`
  - `endpoint`
  - `region`
- OpenAI / OpenRouter / LM Studio / Ollama:
  - `base_url`
  - `api_key` where required
  - `model`
  - optional `custom_prompt`
- DeepL:
  - `api_key`
  - `api_url`
- LibreTranslate:
  - optional `api_key`
  - `api_url`
- Experimental providers:
  - minimal settings only
  - best-effort / no reliability guarantee

## LLM prompt behavior
- LLM providers use a built-in default subtitle translation prompt when `custom_prompt` is empty.
- The default prompt tells the model to:
  - translate only
  - avoid explanations or assistant chatter
  - keep subtitle output concise and readable
  - preserve names and game terms where appropriate
- If a custom prompt is provided, it overrides the built-in default for that provider.

## Google Translate v2 setup
1. Open the local dashboard.
2. Enable translation.
3. Select `Google Translate v2`.
4. Paste the API key into `API key`.
5. Add one or more target languages such as `en` and `ja`.
6. Click `Save Current Config`.

Google v2 key-path diagnostics:
- The app now reports, on translation failure:
  - selected provider
  - endpoint used
  - whether the key is present
  - key length
  - masked key preview
  - whether trimming changed the value
  - whether the app had to sanitize a pasted query-string style key
  - HTTP status/body excerpt when the remote API returned one
- The full API key is never logged.

Important:
- If the saved value looks like a full URL or contains trailing query-string fragments, the app now extracts the actual `key` value where possible instead of sending the whole pasted string unchanged.

## Google GAS URL setup
1. Deploy your Google Apps Script as a web app.
2. In the dashboard, select `Google GAS URL`.
3. Paste the web app URL into `Google Apps Script web app URL`.
4. Add target languages.
5. Click `Save Current Config`.

Expected request payload:
- `text`
- `source_lang`
- `target_lang`

Accepted response fields:
- `translatedText`
- `text`
- `translation`
- `output`

## Azure Translator setup
1. Enable translation.
2. Select `Azure Translator`.
3. Fill:
   - `API key`
   - `Endpoint`
   - `Region` when required by your Azure resource
4. Add target languages.
5. Save config or profile.

## OpenAI and OpenRouter setup
1. Enable translation.
2. Select `OpenAI` or `OpenRouter`.
3. Fill:
   - `API key`
   - `Base URL`
   - `Model`
4. Leave `Custom prompt override` empty to use the built-in subtitle prompt, or set your own.
5. Save config or profile.

## LM Studio and Ollama setup
1. Start the local model server first.
2. In the dashboard, select `LM Studio` or `Ollama`.
3. Fill:
   - `Base URL`
   - `Model`
4. `API key` is not required for typical local setups.
5. Leave `Custom prompt override` empty to use the built-in subtitle prompt unless you need a custom translation style.

## Experimental provider limitations
- `Google Web`, `Google GAS URL`, `MyMemory`, `Public LibreTranslate Mirror`, and `Free Web Translate` are experimental.
- They are intended as emergency or test-only paths.
- They may fail, rate-limit, or change behavior without notice.
- They should not be treated as the primary production recommendation.

## Translation diagnostics and failure behavior
- Failed translations do not stop recognition.
- Failed translations do not stop runtime start/stop.
- Failed translations do not break overlay payload routing.
- Translation errors are surfaced locally through:
  - `Translated Results`
  - runtime last-error text when a provider call fails hard
  - websocket `translation_update` payload status fields
  - startup preflight translation summary
  - dashboard translation diagnostics line
- If a translation provider fails for a target language:
  - source text still flows normally when source visibility is enabled
  - failed translated lines are marked with honest error text
- Translation readiness states are intended to be practical:
  - `disabled`: translation is turned off
  - `ready`: provider is configured enough for normal use
  - `partial`: required settings such as API key, endpoint, model, or target languages are missing
  - `degraded`: the provider is configured but not fully usable, for example a local LLM endpoint is unreachable
  - `experimental`: best-effort public provider is selected
  - `error`: diagnostics could not be computed safely

## Overlay presets
- Overlay is still served locally from the same FastAPI app:
  - `http://127.0.0.1:8765/overlay`
- Supported query styles:
  - `?profile=default`
  - `?profile=jp_stream&compact=1`
  - `?preset=dual-line`
  - `?preset=stacked`
  - `?preset=compact`
  - `?debug=1`
- Behavior:
  - `single`: all visible subtitle lines joined into one line in the saved order
  - `dual-line`: first visible subtitle line on line 1, remaining visible lines collapsed into line 2
  - `stacked`: first visible subtitle line on line 1, remaining visible lines shown beneath it
  - `compact`: reduced spacing/font while preserving the selected preset
- Overlay lifecycle behavior:
  - completed subtitle blocks are rendered from the latest ordered `visible_items`
  - while a new phrase is still partial, the overlay may show live source text while the previous completed translation block remains visible
  - when the new phrase finalizes and its translation arrives, the new completed block replaces the previous one immediately
  - no queue of older completed subtitle blocks is rendered
- Overlay debug mode:
  - `?debug=1` shows a small on-page debug panel
  - the overlay also writes lifecycle events to the browser console:
    - websocket connect/disconnect
    - payload state changes
    - text shown
    - text updated
    - text hidden

## Testing the local subtitle routing flow
1. Run `start.bat`.
2. Open `http://127.0.0.1:8765/`.
3. Choose a local microphone.
4. In `Translation Settings`, optionally enable translation and configure target languages.
5. In `Subtitle Output`, set visibility/order/count as needed.
6. Press `Save Current Config`.
7. Press `Start` and speak into the microphone.
8. Check:
  - `Transcript` for raw recognition updates
  - `Translated Results` for provider output
  - `Subtitle Output Preview` for final routed source + translation payload order
  - `/overlay` for OBS-facing rendering

Useful local checks:
- Source only:
  - enable `Show source text`
  - disable `Show translated text`
- Translation only:
  - disable `Show source text`
  - enable translation plus `Show translated text`
- Source + multiple translations:
  - enable both source and translations
  - add multiple target languages
  - set `Max translated languages` to `2` or higher
  - reorder languages in the saved display order list

## Exact translation verification steps
1. Run `start.bat`.
2. Open `http://127.0.0.1:8765/`.
3. Select a microphone.
4. Choose a translation provider and fill only the fields shown for that provider.
5. Add target languages and save config.
6. Press `Start` and speak a short phrase.

Source only:
1. Disable `Show translated text`.
2. Leave `Show source text` enabled.
3. You should still see transcript text and overlay payload source lines only.

Translation only:
1. Enable translation.
2. Disable `Show source text`.
3. Enable `Show translated text`.
4. With a working provider, dashboard preview and overlay payload should contain only translated lines.

Mixed source + translation:
1. Enable both `Show source text` and `Show translated text`.
2. Add multiple target languages, for example `en` and `ja`.
3. Set `Max translated languages` to the number you want visible.
4. Reorder the saved display order.
5. Dashboard preview and overlay payload should follow the saved order and visibility settings.

Provider failure behavior:
1. Enable translation and choose a provider.
2. Leave required credentials blank or set an invalid endpoint/base URL.
3. Press `Start` and speak.
4. Expected behavior:
   - recognition still works
   - source transcript still flows
   - runtime does not crash
   - translated results show honest local error messages
   - overlay remains valid and only displays successful lines

## Subtitle lifecycle verification
1. Run `start.bat`.
2. Open `http://127.0.0.1:8765/` and `/overlay`.
3. Keep the default lifecycle settings first:
   - `pause_to_finalize_ms: 350`
   - `completed_source_ttl_ms: 4500`
   - `completed_translation_ttl_ms: 4500`
   - `allow_early_replace_on_next_final: true`
   - `hard_max_phrase_ms: 5500`
   - in the dashboard UI these appear as:
     - `Completed source hold (seconds): 4.5`
     - `Completed translation hold (seconds): 4.5`
4. Press `Start` and speak one short phrase.
5. Expected behavior:
   - the phrase stays partial while you are still speaking
   - after a meaningful pause, one completed block appears
   - source and translation appear together in that same block when translation is enabled
6. Before the visible block expires, start speaking a second phrase.
7. Expected behavior:
   - the first completed translation can remain visible while the second phrase is still partial
   - the old completed source is replaced by the new live source immediately
   - no queue of older completed blocks builds up
8. Finish the second phrase and pause.
9. Expected behavior:
   - the newly completed block replaces the previous one immediately
   - source and translation follow the configured hold timers

Cross-PC first-start checklist:
1. Copy the project to the other Windows PC.
2. Run `start.bat`.
3. Read the preflight lines in the console before the server fully starts.
4. Confirm:
   - if the model file is missing, the first dashboard `Start` auto-downloads it locally
   - torch version is detected
   - CUDA build/availability are reported honestly
   - likely runtime mode matches expectations
   - translation readiness is shown
5. Open `http://127.0.0.1:8765/`.
6. Check the dashboard badges:
   - `asr`
   - `device`
   - `partials`
   - `mode`
   - `translation`
7. If the machine is in degraded mode:
   - do not edit code first
   - use the preflight summary plus dashboard diagnostics to identify whether the cause is:
     - missing model
     - CPU-only torch
     - CUDA unavailable
     - baseline fallback
     - missing translation credentials
     - unreachable local translation server

Live-apply verification:
1. Start the app and press `Start`.
2. With runtime still running, change one of:
   - translation provider
   - API key
   - endpoint/base URL
   - model
   - custom prompt
   - target languages
   - source/translation visibility
   - display order
3. Click `Save Current Config`.
4. Expected behavior:
   - no full app restart
   - no forced ASR restart
   - dashboard log reports the config was applied live
   - preview/overlay visibility and order update immediately
   - the next finalized spoken segment uses the new translation settings

Google Translate v2 path verification:
1. Select `Google Translate v2`.
2. Paste the key and click `Save Current Config`.
3. Speak a short phrase.
4. If translation fails, inspect `Translated Results` or live logs for:
   - provider `google_translate_v2`
   - endpoint `https://translation.googleapis.com/language/translate/v2`
   - key present yes/no
   - masked key preview
    - whether trimming or sanitization changed the saved value
    - HTTP failure detail when available

## Local export behavior
- Export files are written locally under `user-data/exports/`.
- Export is generated automatically when runtime stops, but only if the session produced exportable finalized subtitle records.
- Export outputs:
  - `.srt`
    - contains only finalized visible subtitle lines
    - each cue uses the finalized subtitle payload after source/translation visibility and language order are applied
    - cue text is written as one line per visible subtitle item
  - `.jsonl`
    - starts with one session metadata row
    - then writes one structured row per finalized exportable subtitle record
    - includes source text, source language, translations, ordered visible items, and relative timing offsets
- If a session never reaches exportable finalized subtitle records, no `.srt` or `.jsonl` file is created.

## What is real vs stubbed
- Real in this step:
  - microphone device enumeration
  - microphone capture
  - ring buffer
  - VAD segmentation
  - ASR queue wiring
  - real local official EU multilingual Parakeet inference when the model is installed
  - websocket transcript feed
  - live transcript panel updates in the local UI
  - translation provider abstraction
  - translation cache
  - websocket translation events
  - translated result rendering in the local UI
  - unified subtitle routing for source + translated lines
  - overlay payload generation from final local transcript records
  - local `.srt` export from finalized subtitle session data
  - local `.jsonl` export from finalized subtitle session records

## Runtime state machine
- Runtime states:
  - `idle`
  - `listening`
  - `transcribing`
  - `translating`
  - `error`
- `POST /api/runtime/start`:
  - moves to `listening` when at least one local input device exists and a local stream can open
  - moves to `error` with local message when no input devices are found
- While running, real local audio moves runtime between:
  - `listening -> transcribing -> listening`
- `POST /api/runtime/stop` always returns runtime to `idle`.
- Frontend polls `GET /api/runtime/status` and also receives websocket runtime events.

## Local diagnostics verification
1. Run `start.bat`.
2. Open `http://127.0.0.1:8765/`.
3. Confirm the dashboard shows:
   - `asr: <actual provider>`
   - `device: cpu` or `device: cuda`
   - `partials: on` only when the actual provider truly supports partials
   - `mode: ...` badge describing active mode or degraded fallback
   - `translation: ...` badge describing translation readiness
4. Open `http://127.0.0.1:8765/api/health` and verify:
   - `asr_ready: true`
   - `asr_diagnostics.requested_provider`
   - `asr_diagnostics.model_path` points to the local `.nemo` file
   - `asr_diagnostics.degraded_mode`
   - `asr_diagnostics.fallback_reason`
   - `asr_diagnostics.selected_device` shows the actual runtime device
   - `asr_diagnostics.selected_execution_provider` shows the actual backend path
   - `translation_diagnostics.status`
   - `translation_diagnostics.summary`
   - `translation_diagnostics.reason`
   - `obs_caption_diagnostics.output_mode`
   - `obs_caption_diagnostics.connected`
   - `obs_caption_diagnostics.last_error`
5. Press `Start` and speak.
6. Watch the dashboard diagnostics lines update with:
   - `vad`
   - `asr partial`
   - `asr final`
   - `translation`
   - `total`
   - `partials`
   - `finals`
   - `suppressed`

OBS Closed Captions verification:
1. In OBS, enable websocket access and note host, port, and password.
2. Create a normal OBS text source if you want a visible debug mirror, for example `CC_DEBUG`.
3. In the dashboard, open `OBS Closed Captions`.
4. Enable it, choose `source_live`, and click `Save Current Config`.
5. Optional: enable the debug mirror, set `CC_DEBUG` as the input name, and keep `Send partials to the debug text input` enabled.
6. Press `Start` and speak.
7. Expected behavior:
   - the browser overlay still works as before
   - OBS native captions receive live source partials and the final source replacement
   - if debug mirroring is enabled, the `CC_DEBUG` text source also shows the same text for quick visual verification
8. Change mode to `translation_1` or `first_visible_line`, save again, and speak another phrase.
9. Expected behavior:
   - OBS native captions now send final-ish routed subtitle text instead of source partials
   - `first_visible_line` follows the current saved `Subtitle Output` order and visibility
   - if debug mirroring is enabled, the same selected text is mirrored into the configured OBS text source

## Safe realtime tuning comparison on Windows
1. Run `start.bat`.
2. Open `http://127.0.0.1:8765/`.
3. Keep the default realtime provider:
   - `official_eu_parakeet_realtime`
4. In `Realtime Tuning`, start with the shipped defaults.
5. Press `Save Current Config`.
6. Press `Start` and speak a sentence of 3-5 seconds.
7. Observe:
   - how quickly the first partial appears
   - whether partial text flickers too much
   - how quickly final text lands after you stop speaking
   - `partials`, `finals`, and `suppressed` counters
8. Stop runtime before making bigger changes.
9. Change one setting at a time, save config again, then test the same phrase length.
10. Good low-risk experiments:
   - lower `partial_emit_interval_ms` from `450` to `360` if you want quicker partials and your GPU keeps up
   - raise `pause_to_finalize_ms` from `350` to `450` if phrases break too aggressively on breaths
   - lower `partial_min_delta_chars` from `12` to `8` if you want livelier partials
   - raise `partial_coalescing_ms` from `160` to `220` if partials still spam too often

## Local test steps for the provider abstraction pass
1. Run `start.bat`.
2. Open `http://127.0.0.1:8765/`.
3. Open `http://127.0.0.1:8765/api/health` and confirm:
   - `asr_diagnostics.provider` matches the selected ASR backend
   - `asr_diagnostics.supports_partials` matches the provider capability
   - `asr_diagnostics.supports_streaming` remains `false`
   - `asr_diagnostics.selected_execution_provider` reports the actual backend path in use
4. Choose a microphone in the dashboard.
5. Press `Start` and speak a short phrase.
6. Confirm:
   - runtime still moves through `listening` and `transcribing`
   - final transcript text still appears in the page
   - translation still works when enabled
   - overlay still updates from finalized subtitle payloads
7. If you inspect WebSocket traffic locally, expect:
   - `transcript_update` for the current working UI flow
   - `transcript_segment_event` as the provider-agnostic lifecycle-oriented event channel

## How to verify actual GPU usage locally
1. Open `user-data/config.json`.
2. Set:
   - `"asr": { "provider_preference": "official_eu_parakeet_realtime", "prefer_gpu": true }`
3. Run `start.bat`.
4. Open `http://127.0.0.1:8765/api/health`.
5. Check:
   - `asr_diagnostics.gpu_requested = true`
   - `asr_diagnostics.gpu_available`
   - `asr_diagnostics.selected_device`
   - `asr_diagnostics.selected_execution_provider`
6. Interpret the result honestly:
   - if `selected_device = cuda`, the provider is actually running on GPU
   - if `selected_device = cpu`, GPU was not available or the provider fell back to CPU
   - if `degraded_mode = true`, the app is not in the preferred realtime GPU path

## Windows GPU troubleshooting
- Check the project interpreter first:
  - `F:\AI\stream-sub-translator\.venv\Scripts\python.exe`
- Clean reproducible project-local GPU install/update:
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```
- This repository now resolves the Windows GPU path through the official PyTorch CUDA 12.8 wheel index from `requirements.txt`.
- Verify the local venv, not system Python:
```powershell
.\.venv\Scripts\python.exe -c "import sys, torch; print(sys.executable); print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available())"
```
- Interpret the result:
  - if `torch.version.cuda` is `None`, the project is using a CPU-only PyTorch build
  - if `torch.version.cuda` has a value but `torch.cuda.is_available()` is `False`, CUDA runtime initialization is failing
- Check system GPU visibility:
```powershell
nvidia-smi
```
- The app reports the current state explicitly through:
  - `GET /api/health`
  - `GET /api/runtime/status`
  - dashboard ASR diagnostics text
  - startup preflight summary

## Portability and startup on another Windows PC
- `start.bat` is still the main workflow.
- The startup console now prints a compact preflight summary covering:
  - Python executable
  - project venv path
  - config path
  - official EU model presence
  - torch version
  - CUDA build / CUDA availability
  - GPU count / first GPU name
  - ASR provider policy
  - likely runtime mode
  - translation readiness summary
- Typical likely runtime modes:
  - `realtime GPU`
  - `realtime CPU fallback`
  - `baseline compatibility`
  - `baseline fallback`
  - `ASR blocked (model missing)`
- Typical translation states:
  - `disabled`
  - `ready`
  - `partial`
  - `degraded`
  - `experimental`
- The goal is that another Windows PC can explain its own startup state without code editing.

## Translation troubleshooting on another PC
- First, read the translation line in the `start.bat` preflight output.
- Then check the dashboard `translation:` badge and translation diagnostics line.
- Common cases:
  - `translation: disabled`
    - translation is simply turned off in the saved config/profile
  - `translation: partial`
    - a required setting is missing, such as:
      - API key
      - endpoint
      - model
      - target language list
  - `translation: degraded`
    - common for local providers when:
      - LM Studio is not running
      - Ollama is not running
      - the configured local endpoint/port is unreachable
  - `translation: experimental`
    - a best-effort public provider is selected
- Translation provider problems should not stop ASR, runtime start/stop, or overlay payload flow.

## How to verify whether partials are truly supported
1. Open `user-data/config.json`.
2. Set:
   - `"asr": { "provider_preference": "official_eu_parakeet_realtime", "prefer_gpu": true }`
3. Run `start.bat`.
4. In the dashboard, confirm the badge shows:
   - `partials: on`
5. Select a microphone and press `Start`.
6. Speak a phrase longer than one second.
7. Confirm:
   - partial transcript text appears while you are still speaking
   - final transcript still appears when the segment closes
8. If you switch back to:
   - `"provider_preference": "official_eu_parakeet"`
   then the badge should return to `partials: off` and the path becomes final-first again.

## Expected default policy behavior
- Default requested provider:
  - `official_eu_parakeet_realtime`
- Default requested device policy:
  - `gpu_preferred`
- Preferred steady-state result:
  - realtime provider active
  - CUDA selected
  - `degraded_mode = false`
- Allowed last-resort fallback:
  - CPU fallback with explicit degraded diagnostics
  - baseline provider fallback with explicit degraded diagnostics

## Real-ASR local test instructions
1. Install dependencies:
   - `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`
2. Download the official EU multilingual model:
   - `.\.venv\Scripts\python.exe -m backend.install_asr_model --model eu`
3. Optional ASR backend selection in `user-data/config.json`:
   - realtime partial-capable path:
     - `"provider_preference": "official_eu_parakeet_realtime"`
   - baseline fallback/debug path:
     - `"provider_preference": "official_eu_parakeet"`
   - automatic choice:
     - `"provider_preference": "auto"`
   - GPU preference:
     - `"prefer_gpu": true`
4. Run:
   - `start.bat`
5. Open:
   - `http://127.0.0.1:8765/`
6. Confirm the health badge shows:
   - `asr: ready`
7. Select a local microphone.
8. Press `Start`.
9. Speak a short phrase.
10. Verify:
   - runtime moves through `listening` and `transcribing`
   - transcript events appear in the page
   - final transcript text is actual recognized speech, not `[mock-parakeet] ...`
   - if `official_eu_parakeet_realtime` is selected, partial transcript updates should appear before the final line closes

## Exact expected diagnostics by mode
1. Realtime GPU success
   - `requested_provider = official_eu_parakeet_realtime`
   - `provider = official_eu_parakeet_realtime`
   - `requested_device_policy = gpu_preferred`
   - `selected_device = cuda`
   - `selected_execution_provider = nemo_direct`
   - `degraded_mode = false`
   - UI mode badge:
     - `realtime GPU active`

2. Realtime CPU fallback
   - `requested_provider = official_eu_parakeet_realtime`
   - `provider = official_eu_parakeet_realtime`
   - `requested_device_policy = gpu_preferred`
   - `selected_device = cpu`
   - `selected_execution_provider = nemo_direct`
   - `degraded_mode = true`
   - `fallback_reason` explains why GPU could not activate
   - UI mode badge:
     - `realtime CPU fallback`
     - or `CPU-only torch detected`

3. Baseline fallback
   - `requested_provider = official_eu_parakeet_realtime` or `auto`
   - `provider = official_eu_parakeet`
   - `selected_execution_provider = nemo_file`
   - `degraded_mode = true`
   - `fallback_reason` explains why realtime provider was not used
   - UI mode badge:
     - `baseline fallback active`

## Failure behavior when model files are missing or invalid
- App startup still succeeds so the dashboard can explain the problem.
- `GET /api/health` reports ASR readiness details.
- Pressing `Start` now auto-downloads the official model if it is still missing locally.
- During that first model download/load, runtime goes to `starting` and the console shows progress.
- If model download or initialization fails, runtime moves to `error` with a clear message.
- `start.bat` prints a console hint when the official EU model file is still missing at app startup.
