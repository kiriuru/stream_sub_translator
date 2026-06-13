# VoiceSub

**Turn your voice into live translated subtitles for streaming. Local-first, privacy-first, OBS-ready.**

<p align="center">
  <a href="./README.md">English</a> • <a href="./README.ru.md">Русский</a> •
  <a href="./docs/WIKI.en.md">Wiki (EN)</a> • <a href="./docs/WIKI.ru.md">Wiki (RU)</a> •
  <a href="./docs/TECHNICAL_ARCHITECTURE.en.md">Technical Docs (EN)</a> •
  <a href="./docs/TECHNICAL_ARCHITECTURE.md">Technical Docs (RU)</a> •
  <a href="./docs/CHANGELOG.md">Changelog</a>
</p>

VoiceSub **`0.5.1`** (текущая линия) is a Windows desktop app for streamers who need real-time subtitles with optional translation. It combines browser-based speech recognition, subtitle styling, routing, and OBS output in one local workflow. Default bind is `127.0.0.1:8765` — no cloud backend, no accounts.

Successor to SST Desktop `0.4.4`; first VoiceSub release baseline: **`0.5.0`**. Core stack: **Rust + Tauri**, **Svelte dashboard**, **vanilla OBS overlay**.

## Key features

- Real-time speech via **Chrome/Edge Web Speech worker** (`/google-asr`)
- Multi-language translation — **13 providers**, up to 5 translation lines
- OBS **Browser Source overlay** + optional **OBS Closed Captions** (WebSocket)
- Animated subtitle presets, per-slot styling, theme palette
- **TTS module** — native/Sonic dual-sink playback; subtitle speech + Twitch chat TTS (up to **5 IRC channels** per OAuth, live filter apply)
- Diagnostics ZIP export (redacted config + logs)
- UI locales: **en, ru, ja, ko, zh**
- Compact phone-style layout for secondary monitors

**Not in core 0.5.x:** local Parakeet ASR, experimental browser routes (archived in `legacy/`).

## System requirements

- Windows 10/11 x64
- **Microsoft Edge WebView2 Runtime** — required for the VoiceSub desktop shell (dashboard and TTS window). Usually preinstalled on Windows 11; on Windows 10 the NSIS installer can run the WebView2 bootstrapper if it is missing.
- **Google Chrome** (or Edge for smoke tests) — separate system dependency for the Web Speech worker window
- Microphone access for the browser worker window
- Internet for external translation providers (optional)
- For NSIS install: no Python, Node.js, or CUDA required in core package

## Quick start

1. Install **VoiceSub** from the release installer (`VoiceSub_0.5.1_x64-setup.exe` or latest in your release folder; developers: `build-release-msi.bat` → `build-release.ps1`).
2. Launch **VoiceSub.exe** — the main window opens the dashboard at `http://127.0.0.1:8765/`.
3. In OBS, add a **Browser Source** pointing to `http://127.0.0.1:8765/overlay`.
4. Configure translation and subtitle style if needed, then click **Start**.
5. Keep the **browser worker window** open and visible (launched automatically) — mic permission is granted there.

For step-by-step UI guidance, see **[Wiki (EN)](./docs/WIKI.en.md)** / **[Wiki (RU)](./docs/WIKI.ru.md)**.

## Local URLs

| URL | Purpose |
| --- | --- |
| `http://127.0.0.1:8765/` | Dashboard |
| `http://127.0.0.1:8765/overlay` | OBS Browser Source |
| `http://127.0.0.1:8765/google-asr?autostart=1` | Browser Speech worker |
| `http://127.0.0.1:8765/tts` | TTS module UI |

Overlay query examples: `?preset=single`, `?compact=1`, `?profile=default`

## Configuration and data

| Path | Contents |
| --- | --- |
| `user-data/config.toml` | Main settings (TOML) |
| `user-data/profiles/` | Named profile snapshots |
| `user-data/translation-cache/` | Persistent translation cache |
| `logs/` | `core.log`, `runtime-events.log`, `session-latest.jsonl` |
| `bin/fonts/` | Project fonts for subtitle rendering |

SST `config.json` can be imported on first run or via settings — modes like `local` and `remote` are mapped to `browser_google`. See [Technical Architecture §7](./docs/TECHNICAL_ARCHITECTURE.en.md).

## Troubleshooting

| Symptom | Check |
| --- | --- |
| No subtitles at all | Runtime **Start** pressed; worker window open; mic allowed in Chrome |
| Source text but no translation | Translation enabled; at least one line active; provider credentials |
| OBS empty | Browser Source URL is `/overlay`; visibility toggles in Subtitles tab; reload source after app update (overlay cache-bust) |
| OBS text stuck after TTL/Stop | Update to latest build; reload Browser Source (`overlay.js?v=20260610b`, idle TTL DOM clear fix) |
| Update banner shows raw keys / Download does nothing | Update to latest build (i18n `updates.banner.*`, `open_external_https_url` IPC) |
| Port conflict | Ensure `8765` is free or change bind (developer build) |
| Worker dies silently | See Tools & Data → diagnostics; check `logs/core.log` |

Full operational guide: **Wiki** → section 2 (troubleshooting).

## Contributing

PRs welcome. For larger changes, open an issue first.

```powershell
cargo test --workspace
npm run build
npm run test:frontend
```

## Documentation

- [Wiki (EN)](./docs/WIKI.en.md) / [Wiki (RU)](./docs/WIKI.ru.md) — user guide
- [Technical Architecture (EN)](./docs/TECHNICAL_ARCHITECTURE.en.md) / [(RU)](./docs/TECHNICAL_ARCHITECTURE.md)
- [Roadmap](./docs/plans/voicesub_roadmap.ru.md)

## Roadmap

Active development: Parakeet as optional **sidecar module** after 0.5.x. Current patch line **`0.5.1`** — see [CHANGELOG](./docs/CHANGELOG.md). Roadmap: `docs/plans/voicesub_roadmap.ru.md`.

## License

See [LICENSE](./LICENSE).

---

<details>
<summary>For developers: architecture and build</summary>

### Stack

| Layer | Tech |
| --- | --- |
| Core | Rust workspace (`crates/voicesub-*`) + Axum HTTP/WS |
| Shell | Tauri 2 → `VoiceSub.exe` (NSIS installer) |
| Dashboard | Svelte 5 + Vite → `bin/dashboard/` |
| Worker | Svelte 5 → `bin/worker/` |
| Overlay | Vanilla HTML/JS → `bin/overlay/` |
| TTS | Svelte + Rust service + embedded Python sidecar |

Node.js is **build-time only** — not shipped in the installer.

### Build from source

```powershell
npm install
npm run build          # dashboard + worker + TTS
cargo test --workspace
build-release-msi.bat  # → build-release.ps1 → NSIS setup.exe in release_root
```

Tauri `beforeBuildCommand`: `npm run build`. Resources bundled: `bin/dashboard`, `overlay`, `worker`, `tts`, `fonts`, `modules`.

### Key crates

`voicesub-runtime` (orchestration), `voicesub-subtitle`, `voicesub-translation`, `voicesub-browser`, `voicesub-ws`, `voicesub-tts`, `voicesub-obs`.

`src-tauri/` is thin IPC only — no business logic.

Version: `voicesub-types::PROJECT_VERSION` = **`0.5.1`**.

Full reference: [Technical Architecture](./docs/TECHNICAL_ARCHITECTURE.en.md).

</details>
