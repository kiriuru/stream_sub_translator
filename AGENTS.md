# AGENTS.md — VoiceSub

## Engineering Contract (READ FIRST — non-negotiable)

**Full document:** `docs/VOICESUB_ENGINEERING_CONTRACT.ru.md`

Every task must follow these three pillars:

### 1. Full fidelity port — do not break behavior

- Port **all** SST `0.4.4` functionality **as-is**: same logic, algorithms, contracts, side-effect order.
- **Only allowed removals:** Parakeet/local ASR, Remote mode, experimental browser (archived in `legacy/`).
- **Forbidden:** simplifying translation providers, subtitle lifecycle, browser FSM, overlay payload, or config semantics.
- Acceptance: SST golden tests green on Rust; browser worker soak passes.

### 2. Correct structure from day one

- Use canonical workspace layout in engineering contract §2 (layered `crates/`, thin `src-tauri/`, `tests/golden/`).
- One-way dependencies: `voicesub-types` → domain crates → adapters → `voicesub-runtime` → `src-tauri`.
- No business logic in `src-tauri`; no ad-hoc folders; new code only in agreed tree.

### 3. Tests + detailed logs immediately

- **No new Rust module without tests** in the same task (unit + golden where applicable).
- Golden fixtures from SST `tests/` **before or with** each port (subtitle, translation, browser, ws, config).
- **`tracing` only** in Rust (no `println!`); spans on hot path; backbone logs + opt-in JSONL deep traces (`VOICESUB_DEEP_DIAGNOSTICS`, `VOICESUB_TRACE_*`).
- Run `cargo test --workspace` before marking work done.

---

## Product Scope
**VoiceSub** (`0.5.0+`) — Windows-first local real-time subtitle translator for streamers.

Predecessor: SST `0.4.4` at `F:\AI\stream-sub-translator`. **Active development: `F:\AI\VoiceSub` only.**

Core pipeline:
Chrome browser speech worker (`/google-asr`) -> ASR -> optional translation -> OBS overlay (vanilla HTML) + Svelte dashboard -> export

**TTS module** ships in core 0.5.0 (`bin/modules/tts/`, `/tts`). Optional sidecar modules (post-0.5.0): Parakeet, Remote under `bin/modules/`.

Roadmap: `docs/plans/voicesub_roadmap.ru.md`.  
Engineering contract: `docs/VOICESUB_ENGINEERING_CONTRACT.ru.md`.

**Phase status (2026-06-10):** Phase 0 closed (manual soak done). **NSIS installer pipeline works** (`build-release.ps1` → `VoiceSub_0.5.0_x64-setup.exe`). Golden full parity, Phase 1 formal DoD, and public GitHub release **deferred**. SST dashboard field parity and worker default pick **not gates** — see roadmap §12.

## Current Active Development Scope

- **Rust workspace** (`crates/*`) + **Tauri** shell → **`VoiceSub.exe`** (SST icons)
- **Svelte + Vite** dashboard (compile-time static bundle inside NSIS installer)
- **Vanilla HTML/JS overlay** for OBS (lightweight, no Svelte)
- Browser Speech **Svelte worker only** (`/google-asr`, `/google-asr-edge` — same bundle)
- **Full port** `TranslationDispatcher` — 13 providers, all lifecycle rules
- TOML config + SST `config.json` import (no session SRT/JSONL export)
- **i18n: en, ru, ja, ko, zh** in Svelte dashboard
- Tauri **NSIS** packaging (`build-release-msi.bat` → `build-release.ps1` → `VoiceSub_{version}_x64-setup.exe` in `F:\AI\VoiceSub - release\v{version}\`, see `build/release.config.json`)

**Removed from active project (archived in `legacy/`):**

- Remote controller/worker (future **remote module**)
- `browser_google_experimental` and all experimental worker routes
- in-process Parakeet / `local` ASR / torch / NeMo
- Core Audio in Rust core (Parakeet module only, Phase 4)
- Python in core installer
- pywebview / PyInstaller bootstrap (reference until deleted)

Legacy SST Python tree is **port reference** until Rust parity; do not add features on Python path.

## Local-First Baseline
- Default bind `127.0.0.1`; no cloud/SaaS/accounts.
- OBS overlay: **new URL** documented for 0.5.0; users update Browser Source manually.
- GitHub update check: `POST /api/updates/check` + dashboard banner; opens release URL via `open_external_https_url` (not `window.open`).

## Hard Constraints
- **Do NOT use Node.js** in shipped product runtime or as a dependency inside the installer.
- **No extra runtime installs** for end users: NSIS `setup.exe` + system Chrome for Web Speech; no Python/Node/torch in core.
- **Allowed target stack:** Rust, Tauri, Svelte, Vite (build-time frontend toolchain on **developer/build machine only**), TypeScript for frontend sources.
- **Forbidden:** React, Webpack, Electron, Node.js in runtime.
- Dashboard = Svelte; overlay = **plain HTML/JS** (OBS).
- Browser worker: **Svelte only** at `/google-asr` (`src-worker/` → `bin/worker/`). Overlay stays vanilla HTML in `bin/overlay/`.
- Python only in optional `modules/parakeet/` sidecar (Phase 4).
- **TTS Python sidecar frozen:** ship `bin/modules/tts/runtime/{platform}/google_tts_fetch.exe` only; `google_tts_fetch.py` / `build_runtime.*` are gitignored (local dev artifacts). Release builds must not depend on system Python (`VOICESUB_TTS_ALLOW_SYSTEM_PYTHON` is debug-only).
- Default mic: Chrome worker `getUserMedia`; WASAPI only in Parakeet module.

## Runtime Modes (core 0.5.0)
- **`browser_google` only** — `/google-asr` (Edge: `/google-asr-edge`)
- No `local`, no `browser_google_experimental`, no remote roles in core

### Browser worker invariants
- Separate Chrome/Edge window with **visible address bar**
- Isolated `--user-data-dir` (classic profile only — no experimental variant dir)
- Edge: `--disable-sync`, `--allow-browser-signin=false`; never `--disable-extensions` / `--bwsi`
- No `--app`, hidden windows, in-tab worker
- Chrome anti-throttling flags + Windows EcoQoS opt-out (`desktop/browser_worker_launcher.py` reference)

## Rust Workspace Layout (canonical)

**Authoritative tree and dependency graph:** `docs/VOICESUB_ENGINEERING_CONTRACT.ru.md` §2.

Summary:

```
crates/voicesub-{types,config,subtitle,translation,browser,ws,http,logging,export,runtime}/
src-tauri/          # thin Tauri shell only
tests/golden/       # SST fixture port
bin/overlay/        # vanilla OBS (shipped)
bin/dashboard/      # vite dashboard build
src-worker/ → bin/worker/
legacy/             # archived parakeet, remote, experimental
```

- `src-tauri/src/main.rs` only calls `lib::run()`.
- Commit `Cargo.lock`.

## Translation Rules
Full port required — all 13 providers, queue, stale drop, preview supersession `(segment_id, revision)`, `provider_limits`, cache.

Critical lifecycle invariant: completed block stays until new phrase is finalized; late translations allowed; no wall-clock stale detection for browser path.

Golden fixtures under `tests/golden/` (ported from SST) must pass in Rust (`cargo test --workspace`).

## Overlay Rules
- Lightweight **separate** `/overlay` vanilla page for OBS Browser Source
- Auto-reconnect WebSocket
- Port `subtitle-style.js` fast/slow path invariants
- **Empty payload:** caller must `disposeRenderContainer` when `render()` returns `empty: true` (dashboard preview + OBS `overlay.js`)
- **Not** Svelte; **not** bundled in dashboard Vite chunk
- New URL for VoiceSub; query-param backward compat with SST **not required**

## OBS and Dashboard
- Dashboard preview uses same WS payload shape as overlay
- OBS closed captions: port from SST, optional

## i18n
All five locales: en, ru, ja, ko, zh — port SST catalogs into Svelte i18n layer in Phase 2.

## Testing
- **Policy:** no code without tests; golden-first port from SST (see engineering contract §3).
- `cargo test --workspace` required before done.
- Per-crate: `cargo test -p voicesub-<name>`; integration: `tests/integration/`; fixtures: `tests/golden/`.
- Translation/subtitle/browser/ws changes must update golden tests.
- Windows-safe; Vitest allowed for Svelte only.

## Logging
- **`tracing`** in all Rust code; no `println!` in production paths.
- Backbone: `logs/core.log`, `logs/runtime-events.log`, `logs/session-latest.jsonl`.
- Deep JSONL traces opt-in via `VOICESUB_DEEP_DIAGNOSTICS` + `VOICESUB_TRACE_*` (contract §4).
- Hot path spans: session/generation, segment/revision, translation stale/supersession, lifecycle transitions.

## Data and Versioning
- `user-data/`, `logs/` local
- `PROJECT_VERSION = "0.5.0"` until crate-only source of truth
- Parakeet models: `bin/modules/parakeet/models/` when module exists

## Directory Guidance

| Path | Role |
| --- | --- |
| `legacy/remote/` | archived SST remote for future module |
| `legacy/experimental-browser/` | archived experimental worker |
| `legacy/modules-source/parakeet/` | Parakeet Python until `bin/modules/parakeet` |
| `bin/overlay/` | active OBS surface |
| `src-worker/` → `bin/worker/` | Svelte Web Speech worker `/google-asr` |
| `bin/modules/tts/` | TTS module shipped runtime |
| `docs/plans/tts_dual_sink_native_playback.ru.md` | TTS dual sink + native playback — **reference plan** (verify against code + web; not strict spec) |

Do not reintroduce remote/experimental routes into active Rust HTTP server.

## Done Means (VoiceSub)
- Engineering contract §6 checklist satisfied
- SST behavior parity (except parakeet/remote/experimental removals)
- Web Speech classic path works
- Rust workspace structure matches contract §2; no logic in `src-tauri`
- Golden tests pass; `cargo test --workspace` run
- Logging/tracing on new hot paths; deep traces behind flags
- **VoiceSub.exe** NSIS installer; SST icon; no Python/Node in install
- Overlay vanilla + OBS new URL documented
- All 5 locales in dashboard
- `TranslationDispatcher` full port verified
- README + TECH_ARCH updated when surfaces change

## GitHub Releases
Deferred (user decision) — no release repo action until instructed.
