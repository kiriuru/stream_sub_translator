# SST Desktop 0.4.0

SST Desktop is a local Windows application for real-time speech recognition, optional translation, subtitle routing, and OBS-ready output.

This README describes the current desktop product surface for the `0.4.0` code line.

## Language

- Russian version: [README.ru.md](./README.ru.md)

## Technical Documentation

- Full technical architecture document: [docs/TECHNICAL_ARCHITECTURE.md](./docs/TECHNICAL_ARCHITECTURE.md) (includes browser ASR observability §11.4, WebSocket/replay contracts §9, translation preview supersession §12.2)
- Unified changelog: [docs/CHANGELOG.md](./docs/CHANGELOG.md)
- `0.4.0` delta notes: [docs/DESKTOP_RELEASE_CHANGELOG_0.4.0.md](./docs/DESKTOP_RELEASE_CHANGELOG_0.4.0.md)
- Previous delta (`0.3.2`): [docs/DESKTOP_RELEASE_CHANGELOG_0.3.2.md](./docs/DESKTOP_RELEASE_CHANGELOG_0.3.2.md)
- Full history: [docs/CHANGELOG.md](./docs/CHANGELOG.md)

## Release Highlights

`0.4.0` adds **Browser Speech observability and resilience** on the backend (structured `basr.*` events, monotonic timekeeping, L2 ingress, operational FSM + recovery policy, JSONL replay, bounded WebSocket queues, preview translation supersession) and **desktop packaging/UX**: optional **`Stream Subtitle Translator Only Web.exe`**, **Browser Speech quick start profile lock** (`asr.desktop_profile_lock`), and **non-blocking dashboard** boot. Public HTTP routes and subtitle lifecycle invariants are unchanged; `config_version` stays **7**.

The **`0.3.2`** baseline still applies (post-ASR word replacement, Web Speech policy/session manager, subtitle style presets, Parakeet architecture chapter). See [docs/DESKTOP_RELEASE_CHANGELOG_0.3.2.md](./docs/DESKTOP_RELEASE_CHANGELOG_0.3.2.md).

- `backend/versioning.py::PROJECT_VERSION = "0.4.0"` is the single source of truth.
- **Browser ASR observability:** `backend/core/runtime/browser_asr_*.py`, `timekeeping.py`.
- **Desktop:** `Only Web.exe`, profile lock, `frontend/js/dashboard/desktop-profile-lock.js`, non-blocking `main.js` / `desktop.js`.
- **Tests:** full suite **336** tests, `OK` (including `tests/test_browser_asr_observability.py`, `tests/test_desktop_profile_lock.py`).

## Release Package

The desktop release ships as one or both public executables:

- `Stream Subtitle Translator.exe` — full splash with startup profiles
- `Stream Subtitle Translator Only Web.exe` — Web Speech-only variant (optional second artifact in the same release folders)

On first launch the bootstrap launcher extracts the managed runtime next to itself and then starts the desktop runtime from disk.

## Quick Start

**Standard launcher** (`Stream Subtitle Translator.exe`):

1. Extract the archive to a writable folder.
2. Confirm `Stream Subtitle Translator.exe` is present.
3. Launch `Stream Subtitle Translator.exe`.
4. Wait for the bootstrap launcher to extract the managed runtime on first start.
5. In the splash launcher choose one startup profile:
   - `Quick Start (Web Speech)` — locks out Local Parakeet for this install profile until you pick GPU/CPU on a later launch
   - `NVIDIA GPU (CUDA)`
   - `CPU-only`
   - `Remote Controller`
   - `Remote Worker`
6. The dashboard opens as soon as the shell loads; settings finish loading in the background.

**Web Speech-only launcher** (`Stream Subtitle Translator Only Web.exe`):

1. Same extract/first-run bootstrap steps as above.
2. No profile picker — goes straight into Web Speech quick start with the same Parakeet lock behavior.

## Bootstrap Launcher

The bootstrap launcher remains the primary desktop release flow.

What it does:

- ships as a single public `Stream Subtitle Translator.exe`;
- contains an embedded managed payload built from the clean desktop runtime;
- checks GitHub Releases for a newer version and prompts only when an update is available;
- extracts and verifies the managed runtime next to itself on first launch;
- repairs runtime files when `app-runtime/` or the internal runtime executable become corrupted.

Update prompt behavior:

- if no update is available (or the network/API is unavailable), startup proceeds normally with no extra UI;
- if a newer version is available, a small dialog offers:
  - `Continue`: launch as usual
  - `Download`: open the release page in the browser and then continue launching

Current extracted layout:

- public launcher: `Stream Subtitle Translator.exe`
- managed runtime folder: `app-runtime/`
- hidden internal runtime executable: `.sst-runtime.exe`
- user data: `user-data/`
- app logs: `logs/`
- local models: `user-data/models/`

Build from source:

- Standard: `build-bootstrap-launcher.bat` → `dist\bootstrap-launcher\Stream Subtitle Translator.exe`
- Web Speech-only: `build-bootstrap-launcher-web-only.bat` → `dist\bootstrap-launcher-web-only\Stream Subtitle Translator Only Web.exe`
- Publish both to release folders: `publish-desktop-releases.ps1` and `publish-desktop-releases-web-only.ps1`

## Startup Profiles

- `Quick Start (Web Speech)`:
  - fastest startup path;
  - keeps recognition in the browser worker window;
  - skips local AI dependency installation;
  - sets `asr.desktop_profile_lock = browser_speech` in `user-data/config.json` so the dashboard cannot switch to Local Parakeet until a GPU/CPU profile is chosen on a later launch.
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
  - keeps Web Speech disabled on the worker side;
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
- Configurable dashboard UI theme (light/dark) with a customizable accent gradient palette applied to both the dashboard and Web Speech worker windows.
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

`Start` sends the current in-memory config snapshot to `/api/runtime/start`, so unsaved dashboard changes can take effect immediately in the runtime without forcing a disk save first. The snapshot is tracked through `active_config_source = runtime_start_snapshot`, `active_config_persisted = false`, and `active_config_hash`, so it does not silently overwrite `user-data/config.json`.

Visual layout was not redesigned in the `0.3.x` line; major work remains internal modular architecture and runtime robustness.

## Main Tabs

### Translation

- Enable/disable translation.
- Select a default provider for new lines and legacy fallback behavior.
- Configure provider credentials/endpoints/model/prompt where applicable.
- For OpenAI and OpenAI-compatible providers (`openai`, `openrouter`, `lm_studio`, `ollama`), the dashboard can populate the `model` field via local helper endpoints:
  - `GET /api/openai/recommended-models` — curated shortlist with no OpenAI API call from the browser;
  - `POST /api/openai/models` — list available models for the provided key;
  - `POST /api/openai/usable-models` — light probe through `/responses` with on-server caching.
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
- The tuning tab keeps only user-facing recognition feel controls; exact ASR timing values live under `Tools & Data`.

### Tools & Data

- Runtime diagnostics and latency metrics.
- Runtime diagnostics cover latency, ASR state, translation queue/provider state, Web Speech worker connectivity, OBS Closed Captions state, and local log locations.
- Advanced ASR controls expose exact timing and gate values such as VAD mode, partial emit interval, min speech, silence hold, pause-to-finalize, max phrase length, chunk window/overlap, min RMS, voiced ratio, and first partial speech.
- Live event feed with bounded logging behavior.
- Wider dashboard localization coverage, including runtime progress, remote tools, style slot editor labels, and diagnostics strings.
- Config save/export/import.
- Profile load/save/delete.
- `Export Diagnostics` creates a local ZIP with redacted config, runtime/preflight snapshots, latest session log, and backend log.

### Help

- The main dashboard now includes a dedicated `Help` tab after `Tools & Data`.
- Help is organized as topic tabs, with only one detailed article visible at a time:
  - overview
  - recognition and tuning
  - translation
  - subtitles and style
  - OBS
  - tools and diagnostics
  - desktop and remote mode
- The remote help topic includes a practical controller/worker startup sequence, pairing order, bridge-window notes, and field explanations for `Worker Base URL`, `Session ID`, `Pair Code`, remote state, and worker runtime status.

## Recognition Modes

### Local Parakeet

- Uses the local runtime and local audio capture path.
- Supports GPU-first policy on compatible NVIDIA systems.
- CPU fallback is available when needed.
- Remains the default local AI path in current builds.
- `Recognition -> Backend ASR provider` now only offers `Official EU Parakeet Low Latency` and `Official EU Parakeet`.

### Web Speech

- After **Quick Start (Web Speech)** or **Only Web**, the dashboard enforces `asr.desktop_profile_lock = browser_speech`: Recognition mode has no Local Parakeet entry, and save/load keeps `asr.mode` on `browser_google` until you launch with **NVIDIA GPU** or **CPU-only** (launcher clears the lock). Implementation: `frontend/js/dashboard/desktop-profile-lock.js`, `desktop/launcher.py`, `backend/config/normalizers/asr.py`, `backend/schemas/config_schema.py` (`AsrConfig.desktop_profile_lock`).
- Uses a separate dedicated **Google Chrome** worker window (`/google-asr`).
- On desktop, Overview → Recognition can pick **Auto** or **Google Chrome** for that worker (`asr.browser.worker_launch_browser`: `auto` or `google_chrome`); both resolve to launching Chrome. The launcher reads this from `config.json` each time the worker URL is opened. The same control is hidden in the web-only dashboard (`start.bat` in a normal browser), where `window.open` always follows the OS default browser.
- Desktop behavior is fixed:
  - SST always opens Web Speech as a separate browser window with an address bar.
  - The launcher opens the worker in a **separate Chrome window** with the address bar (`--new-window` + worker URL).
  - Chrome uses an **isolated** `user-data-dir` under the runtime root for that window only.
  - There is no browser-window mode toggle in the desktop UI.
  - This behavior must not be replaced with `--app`, popup-launcher pages, hidden bootstrap windows, or in-tab navigation.
- Requires browser microphone permission.
- For stable operation, keep the worker window visible while active.

Classic Web Speech includes:

- a dedicated lifecycle supervisor;
- controlled `start/stop/restart` behavior;
- reason-aware restart cooldowns;
- backend/browser generation-aware reconnect handling;
- duplicate partial/final suppression;
- mic health diagnostics;
- localStorage-priority worker settings with backend mirror as best effort;
- best-effort client-event logging so log file problems do not break the page.

### Web Speech Recognition Stability Hardening

The worker pipeline now layers several additional defenses on top of the base supervisor to keep
recognition flowing when the OS, the network, or Chrome itself would otherwise quietly degrade it:

- **Screen Wake Lock**: when recognition is running and the worker tab is visible, the worker
  acquires `navigator.wakeLock.request("screen")` and releases it on `Stop`. This prevents the OS
  from putting the display/system into power-save modes that throttle Chrome's audio callbacks
  and silently stall Web Speech. The lock is re-acquired automatically after a visibility flip
  (e.g. moving the worker between monitors).
- **Earlier controlled session rotation**: `asr.browser.max_browser_session_age_ms` now defaults
  to **180000 ms** (was 240000 ms), giving Chrome more headroom before its own ~4 min silent
  Web Speech kill. The 15 s `prepare_cycle_before_ms` window still applies, so the worker
  rotates the session at ~2:45 instead of being cut off mid-phrase.
- **Network preflight terminal degradation**: after three `network` errors within ~12 s, the
  worker probes `https://www.google.com/generate_204` once with a short timeout. If the probe
  fails, the supervisor transitions to a terminal `recognition_network_unreachable` state and
  stops the auto-restart loop instead of burning CPU/battery. The user gets a clear log line
  about VPN/firewall/DNS/proxy. Successful recognition results reset the burst counter.
- **`voice_below_recognition_threshold` health signal**: distinct from `web_speech_stalled` and
  `mic_silent`. Triggered when the mic clearly has voice-level RMS (>= 0.025) and `no-speech`
  has accumulated while recognition has been quiet for >= 8 s. Surfaces the case of "voice is
  there, Google can't recognise it" (too quiet for the model, locale mismatch, or upstream
  network deterioration).
- **Chrome worker process priority and Windows EcoQoS opt-out**: the desktop launcher now starts
  the Chrome worker window with `HIGH_PRIORITY_CLASS` and, on Windows 10/11, calls
  `SetProcessInformation(ProcessPowerThrottling, OPT_OUT)` so the OS does not place the worker
  into Efficiency Mode when it sits in the background. This stops the common "Web Speech stops
  when OBS covers the Chrome window" failure mode on Windows 11.
- **Chrome feature gates disabled for the worker window**: `CalculateNativeWinOcclusion`,
  `HighEfficiencyModeAvailable`, `HeuristicMemorySaver`, `IntensiveWakeUpThrottling`,
  `GlobalMediaControls`. These prevent Chrome from declaring the window occluded, discarding
  the tab as a Memory Saver victim, throttling timers, or stealing focus through media-key
  popups. Combined with the pre-existing `--disable-backgrounding-occluded-windows`,
  `--disable-renderer-backgrounding`, and `--disable-background-timer-throttling` switches,
  this is the strongest browser-side configuration we can apply without replacing the address
  bar window.

These hardening pieces are wired into both classic Web Speech and Web Speech Experimental.
None of them change the `/api` or websocket payload contracts. The supervisor still rotates
sessions, suppresses duplicates, and force-finalizes on interruption the same way as before.

### Web Speech Live Smoke Checklist

- Open `/google-asr`, refresh the page, and confirm language/toggles restore from the worker-local settings.
- Start recognition and verify one spoken phrase yields interim text followed by one final segment without duplicate final spam.
- Stay silent for a few cycles and confirm recovery uses cooldowns instead of a tight `onend`/`start()` loop.
- Refresh the dashboard or let `/ws/asr_worker` reconnect and confirm the worker does not create a second active recognition instance.
- Mute or remove microphone access and confirm diagnostics can degrade to `mic_silent` or `mic_track_unavailable` instead of silently hanging forever.
- Let force-finalization close an interim, then confirm a later browser final for the same phrase is suppressed as a late duplicate instead of being emitted again.
- After Start, verify a Wake Lock is held while recognition is running (Chrome DevTools -> Application -> Wake Locks); confirm it is released after Stop or after `recognition_network_unreachable` degrade.
- Block Web Speech endpoints (e.g. unplug ethernet or block `*.google.com` in a firewall) and confirm the supervisor enters terminal `recognition_network_unreachable` after the burst threshold instead of looping forever.
- Cover the Chrome worker window with another window (OBS preview, dashboard) on Windows 11 and confirm partials/finals keep flowing - this exercises the `CalculateNativeWinOcclusion` and EcoQoS opt-out paths.

### Web Speech Experimental

- Uses a separate experimental worker window (`/google-asr-experimental`).
- Opens one live microphone `MediaStreamTrack` first, then calls `SpeechRecognition.start(audioTrack)`.
- If the browser rejects `start(audioTrack)`, the worker can fall back to normal `recognition.start()`.
- The page is now wired to the same controlled base FSM contract as the classic worker.
- Browser support may vary. Keep the worker window visible while active.

### Web Speech Experimental Smoke Checklist

- Open `/google-asr-experimental` and do a hard refresh so the worker picks up the latest JS (Chrome uses an isolated profile).
- Start recognition and confirm either `audio-track-start-success` or controlled fallback to normal `recognition.start()`.
- Stop and start again quickly; the worker should not get stuck in permanent `stopping`.
- Disconnect/reconnect the dashboard and confirm the worker does not create a duplicate active recognition instance.
- Close or revoke microphone access and confirm the page degrades rather than failing silently.

## Runtime robustness (0.3.x)

The runtime/event stack is substantially more defensive than in `0.2.9.2`, and `0.3.1` added more structure on top of `0.3.0`:

- `RuntimeOrchestrator` is a facade over explicit controllers in `backend/core/runtime/` (state, lifecycle, metrics, session, segments, browser-worker bookkeeping, speech sources, audio capture, processing tasks, translation runtime, transcript pipeline, output fanout).
- `SubtitleRouter` is split into `subtitle_lifecycle_core.py` (FSM, TTL, relevance), `subtitle_presentation.py` (payload assembly, slot styling, partial/final merging), and a thin publish facade.
- `TranslationDispatcher` is restart-safe (`stop() -> start()` no longer breaks subsequent sessions) and has per-provider concurrency/rate limits.
- `CacheManager` (`backend/core/cache_manager.py`) replaces the previous read-modify-write JSON cache with an in-memory LRU and debounced disk persistence, and quarantines corrupt cache files into `*.corrupt-<timestamp>.json`.
- Config writes are atomic (`backend/core/atomic_io.py`, Windows-safe `os.replace()`). A corrupt `user-data/config.json` is rotated into `*.corrupt-<timestamp>.json` and the app boots on defaults, still passing through the same migration/normalization pipeline.

Highlights inherited and refined from `0.3.0`:

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
- Web Speech worker page: `http://127.0.0.1:8765/google-asr`
- Web Speech experimental worker page: `http://127.0.0.1:8765/google-asr-experimental`

Overlay query examples:

- `?profile=default`
- `?compact=1`

Overlay remains a separate lightweight page for OBS Browser Source and auto-reconnects after websocket drops.

## Config and Schema Notes

`0.3.x` keeps the explicit config contract introduced in `0.3.0` and tightens it further:

- config is versioned and migrated through explicit steps (`backend/core/config_migrations.py`, current `CURRENT_CONFIG_VERSION = 7` in `backend/schemas/config_schema.py`);
- config normalization lives under `backend/config/` (`defaults.py`, `secrets.py`, `normalizers/asr.py|browser.py|obs.py|remote.py|subtitles.py|translation.py|source_text_replacement.py`);
- profiles use the same migration/normalization pipeline;
- generated schema lives at `backend/data/config.schema.json` and is published via `python -m backend.core.config_schema_export`;
- `translation.lines` is the slot-aware translation config surface (`translation_1..translation_5` with per-line `enabled`, `target_lang`, `provider`, `label`), while legacy `translation.provider` and `translation.target_languages` stay for compatibility;
- legacy language-based `subtitle_output.display_order` values are migrated to slot ids like `translation_1`;
- `/api/runtime/start` can apply an optional normalized `config_payload` snapshot for runtime-only changes without persisting `user-data/config.json` (tracked via `active_config_source = runtime_start_snapshot`, `active_config_persisted = false`, `active_config_hash`);
- config writes are atomic on Windows (temporary file in the same folder + `os.replace()`); a corrupt `user-data/config.json` is rotated into `*.corrupt-<timestamp>.json` and defaults are restored;
- `backend/versioning.py` (`PROJECT_VERSION = "0.4.0"`) remains the single source of truth for the app version.

## Remote Notes

The repository still contains optional LAN remote controller/worker support:

- default desktop launch stays on `127.0.0.1`;
- `Remote Controller` and `Remote Worker` remain explicit secondary flows;
- remote worker runtime is AI-only and must not run browser speech modes;
- remote worker sync also prevents drift into browser-worker paths during controller -> worker settings sync.

Recommended remote startup order:

1. Start the worker machine first with `Remote Worker` or `start-remote-worker.bat`.
2. Start the controller machine with `Remote Controller` or `start-remote-controller.bat`.
3. Enter the worker LAN URL in `Worker Base URL`.
4. Run `Check Worker Health` before pairing or runtime start.
5. Create/verify the local pair, then refresh remote state.
6. Run `Sync Worker Settings`, then `Prepare Remote Run`.
7. Start/check the worker runtime.
8. Keep the controller and worker bridge windows open while the remote run is active.
9. Press `Start` on the controller dashboard to begin microphone capture and remote audio/result flow.

Experimental translation providers keep `experimental` as their dashboard status instead of being collapsed into `degraded`; true degraded states remain reserved for error/fallback conditions.

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
  - `runtime-events.log`
  - `session-latest.jsonl`
  - browser/client logs as applicable to the current runtime path

Legacy installs that still contain `user-data/logs/` are migrated into `logs/` during launcher/runtime startup.

Useful diagnostics paths:

- backend/runtime failures:
  - inspect `logs/backend.log`
- structured runtime events:
  - inspect `logs/runtime-events.log`
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
- Build the Web Speech-only bootstrap with `build-bootstrap-launcher-web-only.bat`.
- Publish clean release folders with `publish-desktop-releases.ps1` and `publish-desktop-releases-web-only.ps1`.

Build output:

- `dist\Stream Subtitle Translator\`
- bootstrap launchers:
  - `dist\bootstrap-launcher\Stream Subtitle Translator.exe`
  - `dist\bootstrap-launcher-web-only\Stream Subtitle Translator Only Web.exe`
- publish script defaults (both exes end up in each folder):
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
- Update checks:
  - desktop bootstrap launcher checks GitHub Releases automatically and only prompts when an update is available.
  - backend also exposes a manual check endpoint:
    - enable `updates.enabled` in `user-data/config.json`
    - run `POST /api/updates/check` (persists `updates.latest_known_version` + `updates.last_checked_utc`).
- UI is unreachable:
  - ensure local port `8765` is not occupied by another process.
- Web Speech returns no text:
  - grant microphone permission in the browser;
  - keep the worker window open and visible;
  - if you are testing the experimental path, do a hard refresh after updates.
- OBS output missing:
  - verify OBS websocket settings and selected output mode.

## Automated Tests

Run the current regression suite with:

- `.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"`

The current `0.4.0` verification run used:

- `python -m compileall backend desktop tests`
- `.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"`
- `cmd /c build-desktop.bat`
- `cmd /c build-bootstrap-launcher.bat`
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\publish-desktop-releases.ps1`

Result for `0.4.0`:

- **336** tests, `OK`
- release artifacts refreshed:
  - `dist\bootstrap-launcher\Stream Subtitle Translator.exe`
  - `dist\bootstrap-launcher-web-only\Stream Subtitle Translator Only Web.exe`
  - both exes under `F:\AI\stream-sub-translator-desktop-release` and `-clean`

## Privacy and Runtime Scope

- SST Desktop is local-first.
- Dashboard, API, websocket events, overlay, logs, profiles, cache, and exports run on the same machine.
- Default bind target is localhost (`127.0.0.1`).

## Release Version

- `0.4.0`
- Single runtime source of truth: `backend/versioning.py` (`PROJECT_VERSION`).
