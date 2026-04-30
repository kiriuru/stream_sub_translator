# SST Desktop 0.2.9.0

SST Desktop is a local Windows application for real-time speech recognition, optional translation, subtitle routing, and OBS-ready output.

This release README is focused on the desktop product only.

## Language
- Russian version: [README.ru.md](./README.ru.md)

## Technical Documentation
- Full technical architecture document: [docs/TECHNICAL_ARCHITECTURE.md](./docs/TECHNICAL_ARCHITECTURE.md)

## Release Package
This clean release contains only:
- `Stream Subtitle Translator.exe`
- `app-runtime/`

Do not remove or rename `app-runtime/`. The executable expects it next to the `.exe`.

## Quick Start
1. Extract the archive to a writable folder.
2. Confirm both items are present:
   - `Stream Subtitle Translator.exe`
   - `app-runtime/`
3. Launch `Stream Subtitle Translator.exe`.
4. In splash launcher:
   - Step 1: choose `Local Mode` or `Remote Mode`
   - Step 2: choose startup profile/role
5. Wait for the dashboard to open.

## Startup Profiles
- Local mode:
  - `Quick Start (Browser Speech)` for fastest startup
  - `Local AI (NVIDIA GPU)` for GPU-first local recognition
  - `Local AI (CPU)` for CPU-only local recognition
- Remote mode:
  - `Main PC (Control & Captions)` for controller relay role
  - `AI Processing PC` for worker AI role (LAN bind enabled)

## Core Features
- Real-time microphone recognition.
- Optional translation to zero, one, or multiple target languages.
- Flexible subtitle output:
  - source only
  - translation only
  - source + one translation
  - source + multiple translations
- OBS browser overlay output.
- Optional OBS Closed Captions output.
- Session export in `SRT` and `JSONL`.
- Profile-based local settings management.

## Desktop Dashboard Overview
The main window includes:
- Runtime badges:
  - health
  - runtime state
  - ASR provider and device
  - partials availability
  - recognition mode
  - translation status
  - OBS CC status
- Runtime state pills:
  - `idle`
  - `starting`
  - `listening`
  - `transcribing`
  - `translating`
  - `error`
- Main controls:
  - `Start`
  - `Stop`
- Live panels:
  - transcript (partial + final)
  - microphone selector
  - recognition mode selector
  - subtitle output preview
  - local overlay URL

## Main Tabs and What They Do
### Translation
- Enable/disable translation.
- Select provider.
- Configure provider credentials/endpoints/model/prompt where applicable.
- `Google Cloud Translation - Advanced (v3)` is available as a separate provider and uses `project_id` plus OAuth access token instead of a v2 API key.
- Manage target language list and order.
- Review latest translated output.
- Runtime translation now stays off the live subtitle path: source finals are published first, translation fan-out runs asynchronously per target language, and slow targets are bounded by timeout.
- Late translation results are merged only while the related subtitle sequence is still lifecycle-relevant, which prevents stale jobs from catching up over newer overlay text.
- Tools & Data now also exposes dispatcher runtime counters for queue depth, cancellations, stale drops, and the latest queue/provider latency without changing subtitle lifecycle behavior.

### Subtitles
- Configure overlay layout preset:
  - `single`
  - `dual-line`
  - `stacked`
- Toggle source text visibility.
- Toggle translated lines visibility.
- Set maximum visible translated lines.
- Configure subtitle lifetime behavior (hold, replace, sync expiry).
- Manage display order used by both preview and overlay.

### Style
- Apply built-in style presets.
- Save and delete custom presets.
- Configure base style:
  - font family/size/weight
  - color, outline, shadow
  - background
  - alignment and spacing
  - effects
- Configure per-line slot overrides (source + translation lines).

### OBS
- Configure OBS websocket host/port/password.
- Enable OBS Closed Captions output.
- Select output mode:
  - `source_live`
  - `source_final_only`
  - `translation_1` ... `translation_5`
  - `first_visible_line`
- Optional debug mirror to OBS text source.
- Partial/final send timing controls.

### Tuning
- Quick recognition behavior sliders:
  - appearance speed
  - finalize speed
  - stability/noise sensitivity
- Optional RNNoise path (experimental).
- Practical tuning notes for live operation.

### Tools & Data
- Runtime diagnostics and latency metrics.
- Advanced realtime ASR controls.
- Live event feed.
- Config save/export/import.
- Profile load/save/delete.

## Recognition Modes
### Local Parakeet
- Uses local runtime and local audio capture path.
- Supports GPU-first policy on compatible NVIDIA systems.
- CPU fallback is available when needed.

### Browser Speech
- Uses a separate Chrome/Chromium/Edge worker window (`/google-asr`) with the normal address bar available for microphone permission and device selection.
- Requires browser microphone permission.
- For stable operation, keep the worker window visible while active.
- Normal Web Speech `onend` now re-arms quickly when listening is still desired, while repeated `start()` failures use backoff instead of adding long pauses to ordinary restarts.
- The browser worker now reports reconnect/degraded/watchdog status to backend diagnostics so the dashboard can distinguish worker disconnects, hidden-window throttling, and repeated rearm failures.
- Browser worker settings now honor the saved `continuous_results` flag instead of forcing it on inside the page runtime.
- Structured browser-recognition diagnostics are written on meaningful worker status transitions so pauses, watchdog rearms, visibility throttling, and terminal browser errors can be inspected after the fact.

## Overlay and OBS URLs
- Dashboard: `http://127.0.0.1:8765/`
- Overlay page: `http://127.0.0.1:8765/overlay`
- Browser Speech worker page: `http://127.0.0.1:8765/google-asr`
- Overlay clears stale text on websocket disconnect and replays the latest subtitle payload after reconnect while the local backend is still running.

Overlay query examples:
- `?profile=default`
- `?compact=1`

## LAN Remote Foundation (Phase 1)
This branch now includes an isolated remote foundation that does not change default local behavior.

- Default startup remains local-only on `127.0.0.1`.
- Remote role can be selected at startup:
  - `start-remote-controller.bat`
  - `start-remote-worker.bat`
- `start-remote-controller.bat` uses lightweight bootstrap by default:
  - no GPU/CPU profile prompt
  - no forced local AI/NeMo bootstrap
  - intended for controller relay mode with remote worker execution
- Worker launcher enables LAN bind explicitly through runtime flags.
- API endpoint for diagnostics:
  - `GET /api/remote/state`
- API endpoints for LAN pairing baseline:
  - `POST /api/remote/pair/create`
  - `POST /api/remote/pair/verify`
  - `POST /api/remote/heartbeat`
- Controller endpoints for worker control/sync:
  - `POST /api/remote/worker/settings/sync`
  - `POST /api/remote/worker/runtime/start`
  - `POST /api/remote/worker/runtime/stop`
  - `GET /api/remote/worker/runtime/status`
  - `GET /api/remote/worker/health`

Current scope of this phase:
- remote config normalization
- runtime role wiring (`disabled|controller|worker`)
- LAN-bind startup controls
- remote diagnostics in health/runtime responses

Current LAN bridge baseline:
- WebRTC signaling websocket:
  - `WS /ws/remote/signaling?session_id=...&pair_code=...&role=controller|worker`
- Worker audio ingest websocket:
  - `WS /ws/remote/audio_ingest?session_id=...&pair_code=...`
- Controller local result ingest websocket:
  - `WS /ws/remote/result_ingest`
- Bridge pages:
  - `GET /remote/controller-bridge`
  - `GET /remote/worker-bridge`
- Bridge pages now include automatic reconnect with exponential backoff for transient LAN disconnects.

Quick LAN test flow:
1. On worker machine, run `start-remote-worker.bat`.
2. Open dashboard, go to `Tools & Data -> Remote LAN`, click `Create Local Pair`.
3. On worker machine, open `Open Local Worker Bridge`.
4. On controller machine, run `start-remote-controller.bat`.
5. In controller dashboard `Remote LAN`, set `Worker Base URL` to worker host URL and fill the same session/pair values.
6. Open `Open Controller Bridge`, choose the required microphone in `Microphone Input`, then click `Start Stream`.
7. Click `Prepare Remote Run` on controller dashboard `Remote LAN` to run:
   - worker settings sync
   - worker runtime start
   - controller bridge open
8. Start runtime on the controller dashboard in remote-enabled controller role to route incoming remote transcript/translation events to local preview/overlay/OBS output.

## Local Data and Logs
Created next to the executable:
- `user-data/`
  - `config.json`
  - `profiles/`
  - `exports/`
  - `models/`
  - `cache/`
- `logs/`
  - `desktop-launcher.log`
  - `translation-dispatcher.log`
  - `browser-recognition.log`
  - `browser-recognition-live.log`
  - `overlay-events.log`
  - `dashboard-live-events.log`

When checking the new hot paths:
- translation delays/timeouts/stale drops:
  - inspect `logs/translation-dispatcher.log`
- browser speech pauses/rearms/hidden-window degradation:
  - inspect `logs/browser-recognition.log`
- overlay/dashboard human-readable event trail:
  - inspect `logs/overlay-events.log` and `logs/dashboard-live-events.log`

Runtime cache/temp paths are managed automatically. First start may take longer due to initialization.

## System Requirements
- Windows 10/11 x64
- Microphone access
- For GPU mode: NVIDIA GPU + compatible CUDA runtime stack
- For external translation providers: internet access + valid provider credentials

## Update Procedure
To update SST Desktop:
1. Close the app.
2. Replace:
   - `Stream Subtitle Translator.exe`
   - `app-runtime/`
3. Keep existing `user-data/` and `logs/` if you want to preserve settings/history.

## Troubleshooting
- App does not start:
  - verify `app-runtime/` is present next to `.exe`.
- Second desktop window refuses to start:
  - close the already running launcher instance first.
- UI is unreachable:
  - ensure local port `8765` is not occupied by another process.
- Browser Speech returns no text:
  - grant microphone permission in browser;
  - keep worker window open and visible.
- Slow first launch in local AI mode:
  - wait for runtime/model initialization to complete.
- OBS output missing:
  - verify OBS websocket settings and selected output mode.

## Automated Tests
- Run the current regression tests with:
  - `.venv\Scripts\python.exe -m unittest discover -s tests`

## 0.2.9.0 Notes
- Removed the broken `MyMemory` translation provider from the supported provider list.
- Added `Google Cloud Translation - Advanced (v3)` as a separate provider from `Google Translate v2`.
- Versioning now uses the four-part release number `0.2.9.0` consistently across the runtime, API, and docs.

## Privacy and Runtime Scope
- SST Desktop is local-first.
- Dashboard, API, websocket events, overlay, logs, profiles, cache, and exports run on the same machine.
- Default bind target is localhost (`127.0.0.1`).

## Release Version
- `0.2.9.0`
- Single runtime source of truth: `backend/versioning.py` (`PROJECT_VERSION`).
- Future GitHub release sync scaffold:
  - config section: `updates` in `backend/data/config.example.json` and local `config.json`;
  - API endpoint: `GET /api/version` (returns local version + sync metadata, no live polling by default).
