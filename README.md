# SST Desktop 2.7.3

SST Desktop is a local Windows application for real-time speech recognition, optional translation, subtitle routing, and OBS-ready output.

This release README is focused on the desktop product only.

## Language
- Russian version: [README.ru.md](./README.ru.md)

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
4. Select startup profile in the splash launcher.
5. Wait for the dashboard to open.

## Startup Profiles
- `Quick Start`
  Browser Speech path for fastest initial startup.
- `NVIDIA GPU (CUDA)`
  Local AI recognition path with GPU-first policy.
- `CPU-only`
  Local AI recognition path without GPU acceleration.

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
- Manage target language list and order.
- Review latest translated output.

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
- Uses a separate browser worker window (`/google-asr`).
- Requires browser microphone permission.
- For stable operation, keep the worker window visible while active.

## Overlay and OBS URLs
- Dashboard: `http://127.0.0.1:8765/`
- Overlay page: `http://127.0.0.1:8765/overlay`
- Browser Speech worker page: `http://127.0.0.1:8765/google-asr`

Overlay query examples:
- `?profile=default`
- `?compact=1`

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
  - `overlay-events.log`
  - `browser-recognition.log`
  - `dashboard-live-events.log`

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
- UI is unreachable:
  - ensure local port `8765` is not occupied by another process.
- Browser Speech returns no text:
  - grant microphone permission in browser;
  - keep worker window open and visible.
- Slow first launch in local AI mode:
  - wait for runtime/model initialization to complete.
- OBS output missing:
  - verify OBS websocket settings and selected output mode.

## Privacy and Runtime Scope
- SST Desktop is local-first.
- Dashboard, API, websocket events, overlay, logs, profiles, cache, and exports run on the same machine.
- Default bind target is localhost (`127.0.0.1`).

## Release Version
- `2.7.3`
