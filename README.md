# SST Desktop

**Turn your voice into live translated subtitles for streaming. Fully local, privacy-first, OBS-ready.**

<p align="center">
  <a href="./README.md">English</a> • <a href="./README.ru.md">Русский</a> •
  <a href="./docs/WIKI.en.md">Wiki (EN)</a> • <a href="./docs/WIKI.ru.md">Wiki (RU)</a> •
  <a href="./docs/TECHNICAL_ARCHITECTURE.en.md">Technical Docs (EN)</a> •
  <a href="./docs/TECHNICAL_ARCHITECTURE.md">Technical Docs (RU)</a> •
  <a href="./docs/CHANGELOG.md">Changelog</a>
</p>

SST Desktop is a local Windows app for streamers and creators who need real-time subtitles with optional translation. It combines live ASR, subtitle styling, routing, and OBS output in one desktop workflow. The project is local-first by default (`127.0.0.1`) and supports both browser speech and local AI runtime paths. Current code line: `0.4.4`.

## ✨ Key Features

- 🎤 Real-time speech recognition (Local Parakeet or browser-based Web Speech workers)
- 🌍 Multi-language translation with many providers (`google_translate_v2`, `deepl`, `azure_translator`, `openai`, `openrouter`, `ollama`, and more)
- 📺 OBS integration (Browser Overlay + optional OBS Closed Captions)
- 🎨 Customizable animated subtitles (presets, slot-based styles, effects, line overrides)
- 🔒 Privacy-first local-first runtime (localhost by default, local logs/profiles/exports)
- ⚡ Low-latency pipeline optimized for live streaming workflows
- 💾 Session export in `SRT` and `JSONL` plus diagnostics ZIP export
- 🎭 Startup profiles for Web Speech quick start, GPU, CPU, and remote roles
- 🖥️ Optional LAN remote mode (controller/worker split across machines)
- 🌙 Light/dark UI with configurable accent gradient palette

## 📑 Table of Contents

- [🖥️ System Requirements](#️-system-requirements)
- [🚀 Quick Start](#-quick-start)
- [📦 Startup Profiles](#-startup-profiles)
- [🌐 Local URLs](#-local-urls)
- [🔧 Configuration & Data](#-configuration--data)
- [❓ Troubleshooting](#-troubleshooting)
- [🤝 Contributing](#-contributing)
- [💬 Support & Community](#-support--community)
- [🗺️ Roadmap](#️-roadmap)
- [📄 License](#-license)
- [🛠️ For Developers: Architecture & Building](#️-for-developers-architecture--building)
- [📦 For Developers: Building From Source & Desktop Packaging](#-for-developers-building-from-source--desktop-packaging)
- [🔬 For Developers: Runtime Internals & Hardening](#-for-developers-runtime-internals--hardening)

## 🖥️ System Requirements

- Windows 10/11 x64
- Microphone access
- For GPU mode: NVIDIA GPU + compatible CUDA runtime stack
- For external translation providers: internet access + valid provider credentials

## 🚀 Quick Start

1. Download the latest `.exe` package from [GitHub Releases](https://github.com/kiriuru/stream_sub_translator/releases).
2. Extract to a writable folder and run `Stream Subtitle Translator.exe`.
3. Choose a startup profile in the splash window.
4. Click **Start** and speak - subtitles appear in preview and OBS.

📖 For detailed setup, OBS integration, translation configuration, and advanced tuning, see **[Wiki (EN)](./docs/WIKI.en.md)** and **[Wiki (RU)](./docs/WIKI.ru.md)**.

## 📦 Startup Profiles

| Profile | Best for | Notes |
| --- | --- | --- |
| `Quick Start (Web Speech)` | Fastest first run | Browser worker path, skips local AI install |
| `NVIDIA GPU (CUDA)` | Lowest latency local AI on NVIDIA | Provisions CUDA PyTorch stack |
| `CPU-only` | Non-NVIDIA systems | Provisions CPU-only local AI stack |
| `Remote Controller` | Dashboard/overlay machine in LAN split | Lightweight controller role |
| `Remote Worker` | Dedicated LAN worker machine | AI worker role with LAN bind |

Since `0.4.0`, `Quick Start (Web Speech)` and `Stream Subtitle Translator Only Web.exe` set `asr.desktop_profile_lock = browser_speech` in `user-data/config.json`; Local Parakeet is unlocked after a later GPU/CPU launch. See [docs/CHANGELOG.md](./docs/CHANGELOG.md) section `0.4.0`.

## 🌐 Local URLs

- Dashboard: `http://127.0.0.1:8765/`
- Overlay: `http://127.0.0.1:8765/overlay`
- Web Speech worker: `http://127.0.0.1:8765/google-asr`
- Experimental worker: `http://127.0.0.1:8765/google-asr-experimental`
- Overlay query params: `?profile=default`, `?compact=1`

## 🔧 Configuration & Data

- `user-data/` - config, profiles, exports, models, cache, secrets, debug files
- `logs/` - launcher, backend, runtime, and session logs
- `fonts/` - local font assets used by subtitle rendering
- `user-data/models/` - local AI model/runtime assets

Config writes are atomic on Windows (`os.replace()` flow). Corrupted config/cache files are quarantined as `*.corrupt-<timestamp>.json`, and runtime falls back safely through the same migration/normalization pipeline.

## ❓ Troubleshooting

- App does not start: relaunch and let bootstrap recreate `app-runtime/`.
- Managed runtime corrupted: use **Repair Runtime** or run `Stream Subtitle Translator.exe --repair`.
- Web Speech returns no text: grant mic permission and keep worker window open/visible.
- OBS output missing: verify OBS websocket settings and selected output mode.
- UI unreachable: ensure local port `8765` is free.

For full troubleshooting, see the User Wiki and `Tools & Data -> Runtime Diagnostics` inside the app.

## 🤝 Contributing

PRs are welcome. For larger changes, please open an issue first so scope and direction stay aligned.

Run tests:

```powershell
python -m unittest discover -s tests
```

## 💬 Support & Community

- 📖 Documentation: [Wiki (EN)](./docs/WIKI.en.md), [Wiki (RU)](./docs/WIKI.ru.md), [Technical Architecture (EN)](./docs/TECHNICAL_ARCHITECTURE.en.md), [Technical Architecture (RU)](./docs/TECHNICAL_ARCHITECTURE.md)
- 🐛 Bug Reports: [GitHub Issues](https://github.com/kiriuru/stream_sub_translator/issues)
- 💡 Feature Requests: [GitHub Discussions](https://github.com/kiriuru/stream_sub_translator/discussions)

## 🗺️ Roadmap

Ideas, not commitments:

- Broader OS support research (macOS/Linux feasibility)
- More local ASR model options beyond the current Parakeet path
- Additional provider-level quality/latency tooling
- Plugin-style extension points for integrations and automation
- Companion control surfaces for secondary/mobile devices

## 📄 License

See [LICENSE](./LICENSE) file for details.

<details>
<summary>🛠️ For Developers: Architecture & Building</summary>

## Architecture Summary

The current release architecture is intentionally explicit.

Backend:

- `backend/api/routes/` style separation for HTTP endpoints;
- `backend/services/` for route-facing orchestration;
- `backend/config/` for defaults, secrets, and normalization helpers;
- `backend/core/` for bootstrap, shared lifecycle, WS, subtitle routing, and runtime coordination;
- `backend/core/runtime/` for extracted runtime controllers, **thin `RuntimeOrchestrator` facade + mixins**, `LocalAsrPipeline`, and status builders;
- `backend/asr/parakeet/` for local AI runtime installation, diagnostics, and provider adapters;
- `backend/translation/` for provider registry, readiness checks, engine wiring, and provider-specific clients;
- `backend/schemas/` for typed config/runtime/diagnostics payloads.

Frontend:

- plain HTML/CSS/JS only;
- `frontend/js/main.js` as the dashboard entrypoint;
- `frontend/js/core/` for store (isolated panel listeners), API, WS client, `dom.js` idempotent input helpers, event bus;
- `frontend/js/dashboard/` for actions/helpers/logging;
- `frontend/js/panels/` for dashboard panel wiring;
- `frontend/js/normalizers/` for pure normalization logic.

This remains a FastAPI-served desktop UI. No Node.js, npm, React, Vite, Webpack, Electron, or Tauri are used.

</details>

<details>
<summary>📦 For Developers: Building From Source & Desktop Packaging</summary>

## Building From Source

**From a public GitHub clone** (includes `backend/`, `frontend/`, `overlay/`, `tests/`, **`desktop/`**, and PyInstaller `*.spec` files):

- Provision and run with `start.bat` (no exe required).
- Build bootstrap exes on Windows (venv with `requirements.desktop.txt`) using **local** `build-*.bat` and `publish-desktop-releases*.ps1` scripts (not in git - see `.gitignore`). See [Technical Architecture (EN)](./docs/TECHNICAL_ARCHITECTURE.en.md) section 14 and section 20 (or [RU version](./docs/TECHNICAL_ARCHITECTURE.md)).

**Desktop exe packaging** (build/publish scripts and outputs are not committed):

Build output:

- `dist\Stream Subtitle Translator\`
- bootstrap launchers:
  - `dist\bootstrap-launcher\Stream Subtitle Translator.exe`
  - `dist\bootstrap-launcher-web-only\Stream Subtitle Translator Only Web.exe`
- versioned release bundle (local): `dist\desktop-releases\v0.4.4\` (`01-bootstrap-onefile\`, `01-bootstrap-web-only-onefile\`, `02-managed-app-onefolder\`, `03-installers-both\`, `README.txt`) when publishing this line; older trees may still show `v0.4.1\` or `v0.4.0\`.
- publish script defaults (both exes end up in each folder):
  - `F:\AI\stream-sub-translator-desktop-release`
  - `F:\AI\stream-sub-translator-desktop-release-clean`

Release package notes:

- `Stream Subtitle Translator.exe` - standard bootstrap (payload tracks `PROJECT_VERSION`, currently `0.4.4`)
- `Stream Subtitle Translator Only Web.exe` - Web Speech only (introduced in `0.4.0`; still supported)
- On first launch, the bootstrap launcher extracts managed runtime near itself and starts desktop runtime from disk.

</details>

<details>
<summary>🔬 For Developers: Runtime Internals & Hardening</summary>

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

## Web Speech Recognition Stability Hardening

The worker pipeline now layers several additional defenses on top of the base supervisor to keep recognition flowing when the OS, the network, or Chrome itself would otherwise quietly degrade it:

- **Screen Wake Lock**: when recognition is running and the worker tab is visible, the worker acquires `navigator.wakeLock.request("screen")` and releases it on `Stop`. This prevents the OS from putting the display/system into power-save modes that throttle Chrome's audio callbacks and silently stall Web Speech. The lock is re-acquired automatically after a visibility flip.
- **Earlier controlled session rotation**: `asr.browser.max_browser_session_age_ms` defaults to `180000` ms (was `240000` ms), giving Chrome more headroom before its own ~4 minute silent Web Speech kill. The `prepare_cycle_before_ms` window still applies.
- **Network preflight terminal degradation**: after three `network` errors within ~12 seconds, the worker probes `https://www.google.com/generate_204` once with a short timeout. If probe fails, supervisor transitions to terminal `recognition_network_unreachable` instead of running endless restart loops.
- **`voice_below_recognition_threshold` signal**: separate from `web_speech_stalled` and `mic_silent`; triggered when voice-level RMS is present but recognition remains quiet.
- **Chrome process priority and EcoQoS opt-out**: worker window starts with `HIGH_PRIORITY_CLASS`; on Windows 10/11 launcher calls `SetProcessInformation(ProcessPowerThrottling, OPT_OUT)`.
- **Chrome feature gates disabled**: `CalculateNativeWinOcclusion`, `HighEfficiencyModeAvailable`, `HeuristicMemorySaver`, `IntensiveWakeUpThrottling`, `GlobalMediaControls`, plus existing background-throttling disable switches.

These hardening pieces apply to both classic Web Speech and Web Speech Experimental and do not change `/api` or websocket payload contracts.

## Web Speech Live Smoke Checklist

- Open `/google-asr`, refresh page, and confirm language/toggles restore from worker-local settings.
- Start recognition and verify one spoken phrase yields interim text followed by one final segment without duplicate final spam.
- Stay silent for a few cycles and confirm recovery uses cooldowns instead of a tight `onend`/`start()` loop.
- Refresh dashboard or let `/ws/asr_worker` reconnect and confirm worker does not create a second active recognition instance.
- Mute/remove microphone access and confirm diagnostics degrade to `mic_silent` or `mic_track_unavailable`.
- Let force-finalization close an interim, then confirm later browser final for same phrase is suppressed as late duplicate.
- After Start, verify Wake Lock is held while recognition runs and released after Stop or `recognition_network_unreachable`.
- Block Web Speech endpoints and confirm supervisor enters terminal `recognition_network_unreachable`.
- Cover Chrome worker window on Windows 11 and confirm partial/final flow continues.

## Web Speech Experimental

- Uses a separate experimental worker window (`/google-asr-experimental`).
- Opens one live microphone `MediaStreamTrack` first, then calls `SpeechRecognition.start(audioTrack)`.
- If browser rejects `start(audioTrack)`, worker can fall back to normal `recognition.start()`.
- The page is wired to the same controlled base FSM contract as classic worker.
- Browser support may vary; keep worker window visible while active.

## Web Speech Experimental Smoke Checklist

- Open `/google-asr-experimental` and do a hard refresh.
- Start recognition and confirm either `audio-track-start-success` or controlled fallback to `recognition.start()`.
- Stop/start quickly and confirm worker does not get stuck in permanent `stopping`.
- Disconnect/reconnect dashboard and confirm no duplicate active recognition instance appears.
- Close/revoke microphone access and confirm explicit degraded handling.

## Config and Schema Notes

`0.3.x` keeps the explicit config contract introduced in `0.3.0` and tightens it further:

- config is versioned and migrated through explicit steps (`backend/core/config_migrations.py`, current `CURRENT_CONFIG_VERSION = 7` in `backend/schemas/config_schema.py`);
- config normalization lives under `backend/config/` (`defaults.py`, `secrets.py`, `normalizers/asr.py|browser.py|obs.py|remote.py|subtitles.py|translation.py|source_text_replacement.py`);
- profiles use the same migration/normalization pipeline;
- generated schema lives at `backend/data/config.schema.json` and is published via `python -m backend.core.config_schema_export`;
- `translation.lines` is the slot-aware translation config surface (`translation_1..translation_5` with per-line `enabled`, `target_lang`, `provider`, `label`), while legacy `translation.provider` and `translation.target_languages` stay for compatibility;
- legacy language-based `subtitle_output.display_order` values are migrated to slot ids like `translation_1`;
- `/api/runtime/start` can apply an optional normalized `config_payload` snapshot for runtime-only changes without persisting `user-data/config.json` (tracked via `active_config_source = runtime_start_snapshot`, `active_config_persisted = false`, `active_config_hash`);
- config writes are atomic on Windows (temporary file in same folder + `os.replace()`); a corrupt `user-data/config.json` is rotated into `*.corrupt-<timestamp>.json` and defaults are restored;
- `backend/versioning.py` (`PROJECT_VERSION = "0.4.4"`) remains single source of truth.

## Remote Notes

Repository still contains optional LAN remote controller/worker support:

- default desktop launch stays on `127.0.0.1`;
- `Remote Controller` and `Remote Worker` remain explicit secondary flows;
- remote worker runtime is AI-only and must not run browser speech modes;
- remote worker sync prevents drift into browser-worker paths during controller -> worker settings sync.

Recommended remote startup order:

1. Start worker machine first with `Remote Worker` or `start-remote-worker.bat`.
2. Start controller machine with `Remote Controller` or `start-remote-controller.bat`.
3. Enter worker LAN URL in `Worker Base URL`.
4. Run `Check Worker Health` before pairing/runtime start.
5. Create/verify local pair, then refresh remote state.
6. Run `Sync Worker Settings`, then `Prepare Remote Run`.
7. Start/check worker runtime.
8. Keep controller and worker bridge windows open while remote run is active.
9. Press **Start** on controller dashboard to begin microphone capture and remote audio/result flow.

Experimental translation providers keep `experimental` dashboard status instead of being collapsed into `degraded`.

## Local Data and Logs

Created next to executable:

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
  - browser/client logs as applicable to current runtime path

Legacy installs with `user-data/logs/` are migrated into `logs/` during launcher/runtime startup.

Useful diagnostics paths:

- backend/runtime failures: `logs/backend.log`
- structured runtime events: `logs/runtime-events.log`
- latest dashboard/overlay/browser-worker client events: `logs/session-latest.jsonl`

Runtime cache/temp paths are managed automatically; first start may take longer due to initialization.

## Desktop Dashboard Overview

Main window includes runtime badges (`health`, runtime state, ASR provider/device, partials, recognition mode, translation status, OBS CC status), **Start/Stop** controls, transcript/mic/mode/preview/local overlay URL/diagnostics panels.

`Start` sends in-memory config snapshot to `/api/runtime/start`, enabling runtime-only unsaved changes tracked as `active_config_source = runtime_start_snapshot`, `active_config_persisted = false`, and `active_config_hash`.

Dashboard settings UX (`0.4.1+`) uses idempotent DOM updates so focused inputs/carets are not reset during panel rerenders.

## Main Tabs

### Translation

- Enable/disable translation.
- Select default provider for new lines and legacy fallback behavior.
- Configure credentials/endpoints/model/prompt where applicable.
- OpenAI-compatible helpers:
  - `GET /api/openai/recommended-models`
  - `POST /api/openai/models`
  - `POST /api/openai/usable-models`
- `Google Cloud Translation - Advanced (v3)` uses `project_id` + OAuth access token.
- Configure up to five slot-based lines (`translation_1 .. translation_5`), each with `enabled`, `target_lang`, `provider`, optional `label`.
- Slot cards render only for lines present in `translation.lines`.
- Overlay/preview ordering follows stable slot ids.
- Translation fan-out is async; stale lifecycle-irrelevant jobs are dropped.

### Subtitles

- Presets: `single`, `dual-line`, `stacked`, `compact`.
- Toggle source and translated visibility.
- Configure max visible translated lines, lifetime behavior, and display order.
- Previous completed translation stays visible while new phrase is only partial; replacement happens after newer phrase finalization and translation arrival.

### Style

- Built-in presets and custom presets.
- Base style controls: font family/size/weight, color, outline, shadow, background, alignment, spacing, effects.
- Effects: `none`, `fade`, `subtle_pop`, `slide_up`, `zoom_in`, `blur_in`, `glow`.
- Slot-specific overrides.

### OBS

- OBS websocket host/port/password.
- Optional OBS Closed Captions output.
- Output mode: `source_live`, `source_final_only`, `translation_1` ... `translation_5`, `first_visible_line`.
- Optional debug mirror and partial/final timing controls.

### Tuning

- Recognition behavior sliders: appearance speed, finalize speed, stability/noise sensitivity.
- Optional RNNoise path.
- Fine-grained Parakeet realtime timings and gates — **ASR Advanced** tab (contextual `?` help per field, single-line recommended hints).

### Tools & Data

- Runtime diagnostics/latency metrics.
- Translation queue/provider state, Web Speech connectivity, OBS CC state, log locations.
- Live event feed, localization coverage, config/profile import-export controls.
- `Export Diagnostics` builds local ZIP with redacted config, runtime/preflight snapshots, session log, backend log.

### Help

- Topic tabs: overview, recognition and tuning, translation, subtitles and style, OBS, tools and diagnostics, desktop and remote mode.
- Remote topic includes startup sequence, pairing order, bridge window notes, and field descriptions.

## Recognition Modes

### Local Parakeet

- Local runtime with local audio capture path.
- GPU-first policy on compatible NVIDIA systems.
- CPU fallback available.
- `Recognition -> Backend ASR provider` offers **Official EU Parakeet Low Latency** only (`official_eu_parakeet` migrates to low latency).
- Tuning presets: `ultra_low_latency`, `balanced`, `quality`, `custom`.

### Web Speech

- Profile lock behavior after quick-start paths (`asr.desktop_profile_lock = browser_speech`).
- Dedicated Chrome worker window (`/google-asr`) with isolated `user-data-dir`.
- Desktop behavior is fixed address-bar window mode (`--new-window`); no app-mode toggle.
- Worker launch browser setting in desktop: `asr.browser.worker_launch_browser` (`auto` or `google_chrome`, both resolve to Chrome).
- Requires mic permission and visible worker window for stable operation.
- Controlled lifecycle supervisor, restart cooldowns, generation-aware reconnects, duplicate suppression, mic health diagnostics, localStorage-first worker settings.

## Overlay and OBS URLs

- Dashboard: `http://127.0.0.1:8765/`
- Overlay page: `http://127.0.0.1:8765/overlay`
- Web Speech worker page: `http://127.0.0.1:8765/google-asr`
- Web Speech experimental worker page: `http://127.0.0.1:8765/google-asr-experimental`
- Overlay query examples: `?profile=default`, `?compact=1`

Overlay remains a separate lightweight page for OBS Browser Source and auto-reconnects after websocket drops.

## First Launch Behavior and Update Procedure

Public release starts with only `Stream Subtitle Translator.exe`.

On first launch bootstrap extracts/creates:

- `.sst-runtime.exe`
- `app-runtime/`
- `.python/`
- `.venv/`
- `user-data/`
- `logs/`
- `user-data/models/`
- `fonts/`

Launcher rotates previous `logs/desktop-launcher.log` into `desktop-launcher.old.log` each run.

To update:

1. Close app.
2. Replace public `Stream Subtitle Translator.exe`.
3. Keep existing `.python/`, `.venv/`, `user-data/`, and `fonts/` to preserve local state.
4. If needed, use `--repair` or `--reset-runtime` (or splash maintenance buttons).

## Troubleshooting (Extended)

- Managed runtime corrupted: **Repair Runtime** or `Stream Subtitle Translator.exe --repair`.
- Managed runtime full reset: **Reset Runtime** or `Stream Subtitle Translator.exe --reset-runtime`.
- Update checks:
  - launcher checks GitHub Releases automatically and prompts only when update exists;
  - backend manual endpoint: enable `updates.enabled` in `user-data/config.json`, then `POST /api/updates/check`.
- Dashboard blank/unresponsive after splash (legacy `0.4.0` issue): refresh launcher build, inspect `logs\desktop-launcher.log`, use repair/reset if payload mismatch remains.

## Automated Tests

GitHub-tracked suite:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

For `0.4.4`: run:

```powershell
python -m unittest discover -s tests
```

## Privacy and Runtime Scope

- Local-first design.
- Dashboard/API/websocket/overlay/logs/profiles/cache/exports run on same machine.
- Default bind target is localhost (`127.0.0.1`).

## Release Version

- `0.4.4` (current code line)
- `0.4.3`
- `0.4.1`
- `0.4.0`
- Version source of truth: `backend/versioning.py` (`PROJECT_VERSION`)

</details>
