# SST Desktop 0.3.0

SST Desktop is a local Windows application for real-time speech recognition, optional translation, subtitle routing, and OBS-ready output.

This README describes the current desktop product surface for the `0.3.0` code line, including the current main-branch follow-up changes that are not yet cut as a separate release.

## Language

- Russian version: [README.ru.md](./README.ru.md)

## Technical Documentation

- Full technical architecture document: [docs/TECHNICAL_ARCHITECTURE.md](./docs/TECHNICAL_ARCHITECTURE.md)
- Unified changelog: [docs/CHANGELOG.md](./docs/CHANGELOG.md)
- `0.3.0` delta notes: [docs/DESKTOP_RELEASE_CHANGELOG_0.3.0.md](./docs/DESKTOP_RELEASE_CHANGELOG_0.3.0.md)
- Current branch follow-up notes: `docs/CHANGELOG.md` -> `Unreleased`

## Release Highlights

`0.3.0` is the release where the current codebase shape becomes official:

- backend is now split across `api/routes`, `services`, `core`, and `schemas`;
- app initialization is centralized through `backend/core/app_bootstrap.py`;
- config now uses explicit migrations and has a generated JSON Schema;
- dashboard frontend is modular ES module JavaScript without any build step;
- translation routing is now managed through stable `translation_1 .. translation_5` slot cards with per-line provider selection;
- provider settings editing can follow the selected translation slot and warns when enabled lines are missing required credentials;
- Browser Speech lifecycle is supervised and more resilient to `onend`, reconnect, stale worker state, and client-event/logging failures;
- dashboard/runtime WebSocket paths are more defensive under reconnect and dead-socket scenarios;
- desktop launcher/bootstrap logs and runtime models now stay under `user-data/`, with legacy root `logs/` migrated forward automatically;
- `/google-asr-experimental` is documented as a separate experimental browser worker path;
- local backend ASR is now limited to the supported Parakeet providers only.

## Release Package

The primary desktop release ships as:

- `Stream Subtitle Translator.exe`

On first launch the bootstrap launcher extracts the managed runtime next to itself and then starts the desktop runtime from disk.

## Quick Start

1. Extract the archive to a writable folder.
2. Confirm `Stream Subtitle Translator.exe` is present.
3. Launch `Stream Subtitle Translator.exe`.
4. Wait for the bootstrap launcher to extract the managed runtime on first start.
5. In the splash launcher choose one startup profile:
   - `Quick Start (Browser Speech)`
   - `NVIDIA GPU (CUDA)`
   - `CPU-only`
   - `Remote Controller`
   - `Remote Worker`
6. Wait for the local dashboard to open.

## Bootstrap Launcher

The bootstrap launcher remains the primary desktop release flow.

What it does:

- ships as a single public `Stream Subtitle Translator.exe`;
- contains an embedded managed payload built from the clean desktop runtime;
- extracts and verifies the managed runtime next to itself on first launch;
- repairs runtime files when `app-runtime/` or the internal runtime executable become corrupted.

Current extracted layout:

- public launcher: `Stream Subtitle Translator.exe`
- managed runtime folder: `app-runtime/`
- hidden internal runtime executable: `.sst-runtime.exe`
- user data: `user-data/`
- app logs: `logs/`
- local models: `user-data/models/`

Build it from source with:

- `build-bootstrap-launcher.bat`

Bootstrap output:

- `dist\bootstrap-launcher\Stream Subtitle Translator.exe`

## Startup Profiles

- `Quick Start (Browser Speech)`:
  - fastest startup path;
  - keeps recognition in the browser worker window;
  - skips local AI dependency installation.
- `NVIDIA GPU (CUDA)`:
  - provisions the local CUDA PyTorch stack;
  - intended for NVIDIA systems.
- `CPU-only`:
  - provisions the CPU-only PyTorch stack;
  - intended for AMD, Intel, or no-GPU systems.
- `Remote Controller`:
  - keeps startup lightweight;
  - defaults to controller role with local AI bootstrap skipped;
  - is intended to pair with a LAN worker while keeping the local dashboard and overlay on the controller machine.
- `Remote Worker`:
  - starts the local AI worker role with LAN bind enabled;
  - keeps Browser Speech disabled on the worker side;
  - reuses the local AI runtime profile that matches the detected or selected CPU/GPU environment.

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
- `user-data/models/`
- `fonts/`

If an older install still has `user-data/logs/`, the launcher/runtime migrates those files into `logs/`.

These folders are normal for the desktop flow and should be kept next to the executable.

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
- Local-first diagnostics and runtime logs.

## Architecture Summary

The current release architecture is intentionally explicit.

Backend:

- `backend/api/routes/` style separation for HTTP endpoints;
- `backend/services/` for route-facing orchestration;
- `backend/config/` for defaults, secrets, and normalization helpers;
- `backend/core/` for bootstrap, shared lifecycle, WS, subtitle routing, and runtime coordination;
- `backend/core/runtime/` for extracted runtime controllers and status builders;
- `backend/asr/parakeet/` for local AI runtime installation, diagnostics, and provider adapters;
- `backend/translation/` for provider registry, readiness checks, engine wiring, and provider-specific clients;
- `backend/schemas/` for typed config/runtime/diagnostics payloads.

Frontend:

- plain HTML/CSS/JS only;
- `frontend/js/main.js` as the dashboard entrypoint;
- `frontend/js/core/` for store, API, WS client, event bus;
- `frontend/js/dashboard/` for actions/helpers/logging;
- `frontend/js/panels/` for dashboard panel wiring;
- `frontend/js/normalizers/` for pure normalization logic.

This remains a FastAPI-served desktop UI. No Node.js, npm, React, Vite, Webpack, Electron, or Tauri are used.

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
- Main controls:
  - `Start`
  - `Stop`
- Live panels:
  - transcript (partial + final)
  - microphone selector
  - recognition mode selector
  - subtitle output preview
  - local overlay URL
  - diagnostics/event feed

`Start` now sends the current in-memory config snapshot to `/api/runtime/start`, so unsaved dashboard changes can take effect immediately in the runtime without forcing a disk save first.

Visual layout was not redesigned in `0.3.0`; the major change is the internal modular architecture and runtime robustness.

## Main Tabs

### Translation

- Enable/disable translation.
- Select a default provider for new lines and legacy fallback behavior.
- Configure provider credentials/endpoints/model/prompt where applicable.
- `Google Cloud Translation - Advanced (v3)` is available as a separate provider and uses `project_id` plus OAuth access token instead of a v2 API key.
- Configure up to five translation lines with their own enabled state, target language, provider, and optional label.
- The Translation tab now shows each `translation_1 .. translation_5` slot as a separate card with an explicit per-line provider selector.
- Translation slot cards appear only for lines explicitly added/configured in `translation.lines` (empty slots do not render until added).
- Selecting a translation line switches the provider settings editor to that line's provider, while `translation.provider` remains the default provider for new lines and legacy compatibility.
- The provider settings panel can also be pointed at a provider manually when no translation slot is selected.
- Duplicate target languages are supported when they live in different translation slots.
- Overlay and preview ordering now follow stable slot ids such as `translation_1 .. translation_5`, not target language alone.
- Review latest translated output.
- Provider settings remain global per provider under `translation.provider_settings`; API keys are not duplicated into per-line config.
- The dashboard warns when enabled translation lines point at providers with missing required settings.
- Translation now stays off the live source-final path: source finals are published first, translation fan-out runs asynchronously per configured line, and stale jobs are dropped when no longer lifecycle-relevant.

### Subtitles

- Configure overlay layout preset:
  - `single`
  - `dual-line`
  - `stacked`
  - `compact`
- Toggle source text visibility.
- Toggle translated lines visibility.
- Set maximum visible translated lines.
- Configure subtitle lifetime behavior.
- Manage display order used by both preview and overlay.
- By default, the previous completed translation remains visible while a new source phrase is still only an active partial.
- The completed translation block switches only after the newer phrase is finalized and its replacement translation arrives.

### Style

- Apply built-in style presets.
- Save and delete custom presets.
- Configure base style:
  - font family/size/weight
  - color, outline, shadow
  - background
  - alignment and spacing
  - effects
- Built-in effects include: `none`, `fade`, `subtle_pop`, `slide_up`, `zoom_in`, `blur_in`, `glow`.
- Configure per-line slot overrides.

### OBS

- Configure OBS websocket host/port/password.
- Enable OBS Closed Captions output.
- Select output mode:
  - `source_live`
  - `source_final_only`
  - `translation_1` ... `translation_5`
  - `first_visible_line`
- Optional debug mirror to an OBS text source.
- Partial/final send timing controls.

### Tuning

- Quick recognition behavior sliders:
  - appearance speed
  - finalize speed
  - stability/noise sensitivity
- Optional RNNoise path.
- Practical tuning notes for live operation.

### Tools & Data

- Runtime diagnostics and latency metrics.
- Advanced ASR controls.
- Live event feed with bounded logging behavior.
- Wider dashboard localization coverage, including runtime progress, remote tools, style slot editor labels, and diagnostics strings.
- Config save/export/import.
- Profile load/save/delete.
- `Export Diagnostics` creates a local ZIP with redacted config, runtime/preflight snapshots, latest session log, and backend log.

## Recognition Modes

### Local Parakeet

- Uses the local runtime and local audio capture path.
- Supports GPU-first policy on compatible NVIDIA systems.
- CPU fallback is available when needed.
- Remains the default local AI path and is still available in `0.3.0`.
- `Recognition -> Backend ASR provider` now only offers `Official EU Parakeet Low Latency` and `Official EU Parakeet`.

### Browser Speech

- Uses a separate dedicated Chrome/Chromium/Edge worker window (`/google-asr`).
- Desktop behavior is fixed:
  - SST always opens Browser Speech as a separate browser window with an address bar.
  - The launcher uses an isolated browser profile for this worker window.
  - There is no browser-window mode toggle in the desktop UI.
  - This behavior must not be replaced with `--app`, popup-launcher pages, hidden bootstrap windows, or in-tab navigation.
- Requires browser microphone permission.
- For stable operation, keep the worker window visible while active.

Classic Browser Speech in `0.3.0` now includes:

- a dedicated lifecycle supervisor;
- controlled `start/stop/restart` behavior;
- reason-aware restart cooldowns;
- backend/browser generation-aware reconnect handling;
- duplicate partial/final suppression;
- mic health diagnostics;
- localStorage-priority worker settings with backend mirror as best effort;
- best-effort client-event logging so log file problems do not break the page.

### Browser Speech Live Smoke Checklist

- Open `/google-asr`, refresh the page, and confirm language/toggles restore from the worker-local settings.
- Start recognition and verify one spoken phrase yields interim text followed by one final segment without duplicate final spam.
- Stay silent for a few cycles and confirm recovery uses cooldowns instead of a tight `onend`/`start()` loop.
- Refresh the dashboard or let `/ws/asr_worker` reconnect and confirm the worker does not create a second active recognition instance.
- Mute or remove microphone access and confirm diagnostics can degrade to `mic_silent` or `mic_track_unavailable` instead of silently hanging forever.
- Let force-finalization close an interim, then confirm a later browser final for the same phrase is suppressed as a late duplicate instead of being emitted again.

### Browser Speech Experimental

- Uses a separate experimental worker window (`/google-asr-experimental`).
- Opens one live microphone `MediaStreamTrack` first, then calls `SpeechRecognition.start(audioTrack)`.
- If the browser rejects `start(audioTrack)`, the worker can fall back to normal `recognition.start()`.
- The page is now wired to the same controlled base FSM contract as the classic worker.
- Browser support may vary. Keep the worker window visible while active.

### Browser Speech Experimental Smoke Checklist

- Open `/google-asr-experimental` and do a hard refresh so the isolated worker profile picks up the latest JS.
- Start recognition and confirm either `audio-track-start-success` or controlled fallback to normal `recognition.start()`.
- Stop and start again quickly; the worker should not get stuck in permanent `stopping`.
- Disconnect/reconnect the dashboard and confirm the worker does not create a duplicate active recognition instance.
- Close or revoke microphone access and confirm the page degrades rather than failing silently.

## Runtime Robustness in 0.3.0

The runtime/event stack is substantially more defensive than in `0.2.9.2`.

Highlights:

- `/ws/events` reconnect should no longer freeze the dashboard as easily;
- identical runtime status floods are coalesced;
- dead WebSocket connections are removed after send failures;
- Windows close/send errors are treated as cleanup issues, not fatal runtime failures;
- stale browser worker generations are ignored;
- live event log storage is bounded and better behaved under duplicate traffic;
- overlay/runtime event flow better suppresses stale translation mismatches.

## Overlay and OBS URLs

- Dashboard: `http://127.0.0.1:8765/`
- Overlay page: `http://127.0.0.1:8765/overlay`
- Browser Speech worker page: `http://127.0.0.1:8765/google-asr`
- Browser Speech experimental worker page: `http://127.0.0.1:8765/google-asr-experimental`

Overlay query examples:

- `?profile=default`
- `?compact=1`

Overlay remains a separate lightweight page for OBS Browser Source and auto-reconnects after websocket drops.

## Config and Schema Notes

`0.3.0` introduces a more explicit config contract:

- config is versioned and migrated through explicit steps;
- config normalization now lives under `backend/config/` instead of one monolithic `backend/config.py`;
- profiles use the same migration/normalization pipeline;
- generated schema lives at `backend/data/config.schema.json`;
- `translation.lines` is the new slot-aware translation config surface, while legacy `translation.provider` and `translation.target_languages` stay for compatibility;
- legacy language-based `subtitle_output.display_order` values are migrated to slot ids like `translation_1`;
- `/api/runtime/start` can apply an optional normalized `config_payload` snapshot for runtime-only changes without persisting `user-data/config.json`;
- `backend/versioning.py` remains the single source of truth for the app version.

## Remote Notes

The repository still contains optional LAN remote controller/worker support:

- default desktop launch stays on `127.0.0.1`;
- `Remote Controller` and `Remote Worker` remain explicit secondary flows;
- remote worker runtime is AI-only and must not run browser speech modes;
- remote worker sync also prevents drift into browser-worker paths during controller -> worker settings sync.

## Local Data and Logs

Created next to the executable:

- `user-data/`
  - `config.json`
  - `profiles/`
  - `exports/`
  - `models/`
  - `cache/`
  - `secrets/`
  - `debug/`
- `logs/`
  - `bootstrap-launcher.log`
  - `desktop-launcher.log`
  - `backend.log`
  - `runtime-events.jsonl`
  - `session-latest.jsonl`
  - browser/client logs as applicable to the current runtime path

Legacy installs that still contain `user-data/logs/` are migrated into `logs/` during launcher/runtime startup.

Useful diagnostics paths:

- backend/runtime failures:
  - inspect `logs/backend.log`
- structured runtime events:
  - inspect `logs/runtime-events.jsonl`
- latest dashboard/overlay/browser-worker client events:
  - inspect `logs/session-latest.jsonl`

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
3. Keep existing `.python/`, `.venv/`, `user-data/`, and `fonts/` if you want to preserve local runtime state, settings, history, and project-local font assets.
4. If `app-runtime/` or `.sst-runtime.exe` were damaged, use:
   - `--repair`
   - `--reset-runtime`
   or the matching maintenance buttons in the bootstrap splash window.

## Building From Source

- Provision the local dev runtime with `start.bat`.
- Build the desktop one-folder package with `build-desktop.bat`.
- Build the bootstrap one-file launcher with `build-bootstrap-launcher.bat`.
- Publish clean release folders with `publish-desktop-releases.ps1`.

Build output:

- `dist\Stream Subtitle Translator\`
- bootstrap launcher:
  - `dist\bootstrap-launcher\`
- publish script defaults:
  - `F:\AI\stream-sub-translator-desktop-release`
  - `F:\AI\stream-sub-translator-desktop-release-clean`

## Troubleshooting

- App does not start:
  - run the bootstrap launcher again and let it recreate `app-runtime/`.
- Managed runtime looks corrupted:
  - use the `Repair Runtime` button in the bootstrap window;
  - or run `Stream Subtitle Translator.exe --repair`.
- Managed runtime must be rebuilt from scratch:
  - use the `Reset Runtime` button in the bootstrap window;
  - or run `Stream Subtitle Translator.exe --reset-runtime`.
- UI is unreachable:
  - ensure local port `8765` is not occupied by another process.
- Browser Speech returns no text:
  - grant microphone permission in the browser;
  - keep the worker window open and visible;
  - if you are testing the experimental path, do a hard refresh after updates.
- OBS output missing:
  - verify OBS websocket settings and selected output mode.

## Automated Tests

Run the current regression suite with:

- `.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"`

The current `0.3.0` verification run for the pending changes used:

- `python -m compileall backend tests desktop`
- `.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"`
- `cmd /c build-desktop.bat`
- `cmd /c build-bootstrap-launcher.bat`
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\publish-desktop-releases.ps1`

Result:

- `155 tests`
- `OK`
- release artifacts refreshed:
  - `dist\Stream Subtitle Translator\Stream Subtitle Translator.exe`
  - `dist\bootstrap-launcher\Stream Subtitle Translator.exe`
  - `F:\AI\stream-sub-translator-desktop-release\Stream Subtitle Translator.exe`
  - `F:\AI\stream-sub-translator-desktop-release-clean\Stream Subtitle Translator.exe`

## Privacy and Runtime Scope

- SST Desktop is local-first.
- Dashboard, API, websocket events, overlay, logs, profiles, cache, and exports run on the same machine.
- Default bind target is localhost (`127.0.0.1`).

## Release Version

- `0.3.0`
- Single runtime source of truth: `backend/versioning.py` (`PROJECT_VERSION`).
