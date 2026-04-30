# SST Desktop 0.2.9.1

SST Desktop is a local Windows application for real-time speech recognition, optional translation, subtitle routing, and OBS-ready output.

This release README is focused on the desktop product only.

## Language
- Russian version: [README.ru.md](./README.ru.md)

## Technical Documentation
- Full technical architecture document: [docs/TECHNICAL_ARCHITECTURE.md](./docs/TECHNICAL_ARCHITECTURE.md)
- Full changelog for `0.2.9.0`: [docs/DESKTOP_RELEASE_CHANGELOG_0.2.9.0.md](./docs/DESKTOP_RELEASE_CHANGELOG_0.2.9.0.md)
- Delta changelog for `0.2.9.1`: [docs/DESKTOP_RELEASE_CHANGELOG_0.2.9.1.md](./docs/DESKTOP_RELEASE_CHANGELOG_0.2.9.1.md)

## Release Package
The primary desktop release now ships as:
- `Stream Subtitle Translator.exe`

On first launch the bootstrap launcher extracts the managed runtime next to itself and then starts the legacy desktop runtime from disk.

## Quick Start
1. Extract the archive to a writable folder.
2. Confirm `Stream Subtitle Translator.exe` is present.
3. Launch `Stream Subtitle Translator.exe`.
4. Wait for the bootstrap launcher to extract the managed runtime on first start.
5. In the splash launcher choose one startup profile:
   - `Quick Start (Browser Speech)`
   - `Local AI (NVIDIA GPU)`
   - `Local AI (CPU)`
6. Wait for the local dashboard to open.

## Bootstrap Launcher
The bootstrap launcher is now the primary desktop release flow.

What it does:
- ships as a single public `Stream Subtitle Translator.exe`;
- contains an embedded managed payload built from the clean desktop runtime;
- extracts and verifies the legacy managed runtime next to itself on first launch;
- repairs managed runtime files when `app-runtime/` or the internal runtime executable become corrupted.

Current extracted layout:
- public launcher: `Stream Subtitle Translator.exe`
- managed runtime folder: `app-runtime/`
- hidden internal runtime executable: `.sst-runtime.exe`
- user data: `user-data/`
- logs: `logs/`

Build it from source with:
- `build-bootstrap-launcher.bat`

Bootstrap output:
- `dist\bootstrap-launcher\Stream Subtitle Translator.exe`

## Startup Profiles
- `Quick Start (Browser Speech)`:
  - fastest startup path;
  - keeps recognition in the browser worker window;
  - skips local AI dependency installation.
- `Local AI (NVIDIA GPU)`:
  - provisions the local CUDA PyTorch stack;
  - intended for NVIDIA systems.
- `Local AI (CPU)`:
  - provisions the CPU-only PyTorch stack;
  - intended for AMD, Intel, or no-GPU systems.

## First Launch Behavior
The public release starts with only:
- `Stream Subtitle Translator.exe`

On first launch the bootstrap launcher extracts and/or creates:
- `.sst-runtime.exe`
- `app-runtime/`
- `.python/`
- `.venv/`
- `user-data/`
- `logs/`

These folders are normal for the legacy desktop flow and should be kept next to the executable.

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
- Uses a separate dedicated Chrome/Chromium/Edge worker window (`/google-asr`).
- Desktop behavior is fixed:
  - SST always opens Browser Speech as a separate browser window with an address bar.
  - The launcher uses an isolated browser profile for this worker window.
  - There is no browser-window mode toggle in the desktop UI. Address-bar mode is the only supported desktop behavior.
  - This behavior is intentional and must not be replaced with `--app`, popup-launcher pages, hidden bootstrap windows, or in-tab navigation.
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

## Remote Notes
The source repository still contains optional LAN remote controller/worker support, and the desktop splash now exposes it as a secondary flow:
- default desktop launch stays on `127.0.0.1`;
- `Remote Controller` and `Remote Worker` live under the compact secondary `Remote modes` block in the splash launcher;
- remote tools inside `Tools & Data` are collapsed at the bottom of the dashboard by default.

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
2. Replace the public `Stream Subtitle Translator.exe`.
3. Keep existing `.python/`, `.venv/`, `user-data/`, and `logs/` if you want to preserve local runtime state, settings, and history.
4. If `app-runtime/` or `.sst-runtime.exe` were damaged, use:
   - `--repair`
   - `--reset-runtime`
   or the matching maintenance buttons in the bootstrap splash window.

## Building From Source
- Provision the local dev runtime with `start.bat`.
- Build the desktop one-folder package with `build-desktop.bat`.
- Build the experimental bootstrap one-file launcher with `build-bootstrap-launcher.bat`.
- Publish clean release folders with `publish-desktop-releases.ps1`.
- Build output:
  - `dist\Stream Subtitle Translator\`
  - bootstrap launcher:
    - `dist\bootstrap-launcher\`
  - clean release mirror:
    - `...\stream-sub-translator-desktop-release-clean\`

## Bootstrap Roadmap
- Install / verify / repair is implemented first.
- Runtime update from release assets and launcher self-update are tracked in:
  - [docs/desktop-bootstrap-roadmap.md](./docs/desktop-bootstrap-roadmap.md)

## Troubleshooting
- App does not start:
  - run the bootstrap launcher again and let it recreate `app-runtime/`.
- Managed runtime looks corrupted:
  - use the `Repair Runtime` button in the bootstrap window;
  - or run `Stream Subtitle Translator.exe --repair`.
- Managed runtime must be rebuilt from scratch:
  - use the `Reset Runtime` button in the bootstrap window;
  - or run `Stream Subtitle Translator.exe --reset-runtime`.
- Desktop window fails during initialization:
  - review `logs\desktop-launcher.log`;
  - verify the local `pywebview/pythonnet` runtime inside `app-runtime/`.
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

## 0.2.9.1 Notes
- Desktop Browser Speech is now hard-fixed again to the old dedicated window behavior: a separate Chrome/Chromium/Edge window with a visible address bar and isolated worker profile.
- The browser worker window-mode selector was removed from the desktop UI. Address-bar mode is the only supported desktop behavior.
- Clean portable AI bootstrap now seeds offline `lightning 2.4.0` before NeMo ASR dependency installation, which avoids the recent fresh-install failure on missing `lightning`.
- Versioning now uses the four-part release number `0.2.9.1` consistently across the runtime, API, and docs.

## Privacy and Runtime Scope
- SST Desktop is local-first.
- Dashboard, API, websocket events, overlay, logs, profiles, cache, and exports run on the same machine.
- Default bind target is localhost (`127.0.0.1`).

## Release Version
- `0.2.9.1`
- Single runtime source of truth: `backend/versioning.py` (`PROJECT_VERSION`).
- Future GitHub release sync scaffold:
  - config section: `updates` in `backend/data/config.example.json` and local `config.json`;
  - API endpoint: `GET /api/version` (returns local version + sync metadata, no live polling by default).
