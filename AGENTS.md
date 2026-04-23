# AGENTS.md

## Product Scope
Windows-first local real-time subtitle translator for streamers.

Core pipeline:
microphone or browser speech worker -> ASR -> optional translation to 1..N target languages -> local OBS browser overlay -> export logs/subtitles

This repository now has two valid operation families:
- local-first single-machine runtime (default)
- optional LAN remote controller/worker runtime (explicit startup mode)

## Local-First Baseline and Remote Exception
- Keep default startup local-first and localhost-only.
- `start.bat` must default to local mode and force `SST_REMOTE_ROLE=disabled` unless explicit remote bootstrap is requested.
- Default bind target remains `127.0.0.1`.
- LAN bind is an explicit opt-in only for remote worker scenarios.
- Do not add cloud deployment, hosted backend, remote database, accounts, or SaaS assumptions.

Remote exception policy:
- LAN remote mode is allowed and already implemented.
- Remote mode is controller/worker split for the same local product, not a public internet service.
- Do not turn remote mode into internet-facing multi-user infrastructure.

## Hard Constraints
- Do NOT use Node.js, npm, pnpm, yarn, Vite, Webpack, React, TypeScript build pipelines, Electron, or Tauri.
- Frontend must run as plain HTML/CSS/JavaScript served by FastAPI.
- One-click Windows startup via `start.bat` must stay operational.
- Keep microphone audio path simple and predictable.
- Do not add speculative DSP, auto-EQ, auto-gain, or forced enhancement chains in the main path.
- Optional experimental noise-reduction paths must stay optional and off by default.
- GPU-first ASR behavior is the target when CUDA is available.
- CPU fallback must be treated as degraded mode and surfaced honestly.

## Runtime Modes (Current)
- `local` ASR mode: local AI runtime (Parakeet pipeline).
- `browser_google` ASR mode: browser speech worker (`/google-asr`) feeding local pipeline.
- Remote controller role: relays microphone audio to remote worker and ingests remote transcript/translation events.
- Remote worker role: AI runtime mode only for remote processing.

Important role constraints:
- Remote worker role must not run browser speech recognition mode.
- Worker settings sync should enforce AI runtime mode (`asr.mode=local`) on worker side.

## Startup Scripts (Current)
- `start.bat`: default local startup, local bootstrap, opens dashboard.
- `start-remote-controller.bat`: remote controller bootstrap (`SST_REMOTE_BOOTSTRAP=1`, lightweight controller profile).
- `start-remote-worker.bat`: remote worker bootstrap with LAN bind enabled.
- `backend/run.py`: shared runtime launcher with `--remote-role` and `--allow-lan`.
- `backend/run_controller.py`: wrapper for controller defaults.
- `backend/run_worker.py`: wrapper for worker defaults.

Controller lightweight mode expectations:
- No GPU/CPU profile prompt for controller bootstrap.
- Uses `requirements.controller.txt`.
- Skips local AI model bootstrap requirements intentionally.

## API and WebSocket Surface (Current)
Primary local routes:
- `/api/health`
- `/api/runtime/start`
- `/api/runtime/stop`
- `/api/runtime/status`
- `/api/settings/load`
- `/api/settings/save`
- `/api/devices/audio-inputs`
- `/api/obs/url`
- `/api/version`

Remote API routes:
- `/api/remote/state`
- `/api/remote/pair/create`
- `/api/remote/pair/verify`
- `/api/remote/heartbeat`
- `/api/remote/worker/settings/sync`
- `/api/remote/worker/runtime/start`
- `/api/remote/worker/runtime/stop`
- `/api/remote/worker/runtime/status`
- `/api/remote/worker/health`

WebSocket routes:
- `/ws/events`
- `/ws/asr_worker`
- `/ws/remote/signaling`
- `/ws/remote/audio_ingest`
- `/ws/remote/result_ingest`

Remote bridge pages:
- `/remote/controller-bridge`
- `/remote/worker-bridge`

## Translation Rules
- Google Translate v2 is first-class primary provider.
- Translation must remain optional.
- Recognition must continue working without translation.
- User can configure zero or more target languages and explicit output order.
- Support source-only, translation-only, and mixed source+translation subtitle modes.

## Subtitle Output and Rendering Rules
Required output flexibility:
- source only
- translation only
- source + one translation
- source + multiple translations
- multiple translations without source text

Requirements:
- configurable number of translation lines
- configurable language order
- independent visibility toggles for source and translated text
- UI preview and OBS overlay must follow the same saved output ordering/visibility rules

## Subtitle Style Rules
Subtitle styling is core product behavior and must include:
- built-in style presets
- custom style editing
- local persistence in config/profiles
- compatibility across source-only, translation-only, and mixed modes

Style controls should include:
- font family
- font size
- text color
- outline/stroke
- shadow
- background style
- timing/ttl
- line behavior

## Frontend Rules
- Plain HTML/CSS/JavaScript only.
- No JS build step.
- Modular JS files are allowed.
- Dashboard, browser worker page, and remote bridge pages must stay FastAPI-served static pages.

## Overlay Rules
- Overlay remains a lightweight separate page for OBS Browser Source.
- Must auto-reconnect on websocket drop.
- Keep preset behavior (`single`, `dual-line`, `stacked`, `compact`) and query-param compatibility.

## Data, Logs, and Versioning
- Keep local data under project-local `user-data/` and log outputs local.
- Keep runtime caches/temp local to the project runtime environment.
- Project version source of truth is `backend/versioning.py` (`PROJECT_VERSION`).
- `GET /api/version` must remain aligned with local version metadata.
- Future release-sync scaffolding should remain optional and local-safe by default.

## Directory Guidance
The existing working structure is authoritative.
Do not reshuffle stable code to match old placeholder layouts.

Current remote-related files must be preserved:
- `backend/api/routes_remote.py`
- `backend/api/routes_version.py`
- `backend/core/remote_mode.py`
- `backend/core/remote_session.py`
- `backend/core/remote_signaling.py`
- `backend/core/remote_diagnostics.py`
- `backend/run_controller.py`
- `backend/run_worker.py`
- `frontend/js/remote.js`
- `frontend/js/remote-controller-bridge.js`
- `frontend/js/remote-worker-bridge.js`
- `frontend/js/remote-worker-audio-worklet.js`
- `frontend/remote_controller_bridge.html`
- `frontend/remote_worker_bridge.html`
- `start-remote-controller.bat`
- `start-remote-worker.bat`
- `requirements.controller.txt`

## Done Means
A change is complete only if:
- behavior works in the intended mode without regressing default local startup
- routes/modules are wired and not dead code
- README documentation is updated when behavior or startup flow changes
- no forbidden frontend/tooling stack is introduced
- local dashboard and overlay remain served from Python app
- remote mode remains explicit opt-in and does not hijack default local `start.bat` flow
