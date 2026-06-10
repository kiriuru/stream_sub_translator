# VoiceSub — WIKI

Operational guide for the VoiceSub `0.5.0` UI. Each element is described as: **what it is**, **why it exists**, **how it works**, **what it affects**, and **common mistakes**.

Technical architecture: `docs/TECHNICAL_ARCHITECTURE.en.md`. SST `0.4.4` is a frozen predecessor; core behavior in this document is VoiceSub-specific.

---

## 0. About the product

### Element: VoiceSub vs SST
- **VoiceSub** — active `0.5.0` line (Rust + Tauri + Svelte).
- **SST** `0.4.4` — frozen reference; settings import works, but Parakeet/Remote/Experimental modes are not started in core.
- **New overlay URL:** `http://127.0.0.1:8765/overlay` — update OBS Browser Source manually.

### Element: system requirements
- **Windows 10/11 x64**
- **WebView2 Runtime** — required for `VoiceSub.exe` (Tauri dashboard shell, `/tts` window). The app will not start without it. Usually present on Windows 11; on Windows 10 the installer may offer the bootstrapper.
- **Google Chrome** — separate dependency for the Web Speech worker window (`/google-asr`); not the same as WebView2.
- Microphone in the Chrome worker; internet for external translation providers (optional).

### Element: install and update (NSIS)
- **What it does:** `VoiceSub_0.5.0_x64-setup.exe` installs `VoiceSub.exe` and bundled static assets (dashboard, overlay, worker, tts).
- **Why:** single installer without Python/Node in runtime; downloads WebView2 via bootstrapper when missing (`downloadBootstrapper` in Tauri).
- **Update:** close app → run new `setup.exe` over existing → `user-data/` and `logs/` persist next to install/project root.
- **Developers:** `build-release-msi.bat` → `build-release.ps1` → `F:\AI\VoiceSub - release\v{version}\`.
- **Update check:** on dashboard bootstrap the app polls GitHub Releases (`POST /api/updates/check`). When a newer tag exists, a top banner appears (“VoiceSub X is available — you are on Y”). **Download** opens the release page in the system browser. Config: `user-data/config.toml` → `[updates]` (`enabled`, `github_repo`, `check_interval_hours`). The section is merged automatically when upgrading from SST.

### Element: local URLs
| URL | Purpose |
| --- | --- |
| `/` | Svelte dashboard |
| `/overlay` | OBS Browser Source |
| `/google-asr` | Browser Speech worker |
| `/tts` | TTS module UI |

---

## 1. Quick start

### Element: first run
1. Launch **VoiceSub.exe**.
2. Dashboard opens in the Tauri main window (`http://127.0.0.1:8765/`).
3. Add OBS Browser Source: `http://127.0.0.1:8765/overlay`.
4. Configure UI language (Settings) and translation (Translation) if needed.
5. Click **Start** — Chrome opens `/google-asr?autostart=1`.
6. Grant microphone permission in Chrome and speak.

### Element: runtime bar (Start / Stop)
- **Start:** `POST /api/runtime/start` — worker, translation, OBS CC, ASR ingest.
- **Stop:** stops worker (kills Chrome tree), resets subtitle state.
- **Note:** Start sends the current config snapshot, including unsaved edits since last Save.

### Element: subtitle preview (overview)
- **What it does:** top **Subtitle Output Preview** shows placeholders before Start and live payload after.
- **Why:** style calibration without running ASR; empty post-save `overlay_update` does not clear preview.
- **Details:** `TECHNICAL_ARCHITECTURE.en.md` §20 (Idle subtitle preview).

### Element: compact layout
- **What it does:** switches Tauri window (~390×844) and navigation with **Live** pane + settings tabs.
- **Where:** layout button in chrome or command palette.
- **IPC:** Tauri `set_dashboard_layout`.

---

## 2. Troubleshooting

### Scenario: no text at all
- Is runtime **Start**ed?
- Is Chrome `/google-asr` window open and **visible**?
- Microphone allowed in **Chrome** (not only Windows)?
- **Tools & Data** → runtime diagnostics: `browser_worker_connected`?

### Scenario: source text but no translation
- **Translation** tab → translation enabled.
- At least one `translation_N` line with `enabled`.
- Check translation results / diagnostics for provider errors.

### Scenario: OBS shows nothing
- Browser Source URL is `/overlay` (not dashboard `/`).
- **Subtitles** → source/translation visibility enabled.
- TTL not too aggressive (text may flash and vanish).
- On WS disconnect overlay keeps last frame (stale-guard + 1–10 s backoff) — expected.
- Text **stuck after TTL/Stop** — update the app and reload Browser Source (`disposeRenderContainer` + `hasVisibleRenderedFrame`, `overlay.js?v=20260610b`).

### Scenario: worker keeps dying
- Check network (Web Speech uses Google endpoints).
- `logs/browser-trace.jsonl` with `VOICESUB_TRACE_BROWSER=1`.
- Recovery: **Stop** → **Start** or relaunch worker from Tools.

---

## 3. Dashboard tabs

| Tab | Purpose |
| --- | --- |
| **Translation** | Providers, translation lines, cache, dispatcher limits |
| **Subtitles** | Overlay preset, visibility, order, TTL lifecycle |
| **Style** | Fonts, colors, effects, slot styles, custom presets |
| **UI Theme** | Dark/light mode, accent palette |
| **OBS** | Overlay URL, Closed Captions, debug mirror |
| **Word Replace** | Text replacement before translation |
| **Tools & Data** | Profiles, diagnostics, ZIP export |
| **Settings** | UI language, layout, SST config import, Web Speech advanced |
| **Help** | Built-in help topics |

**Command palette** (header search / `Ctrl+K`): quick navigation, Start/Stop, Save, export diagnostics.

---

## 4. Recognition (Browser Speech)

### Element: sole production mode in core 0.5.0
- **`browser_google`** — Web Speech in a separate Chrome window.
- Microphone is selected **in Chrome** (`getUserMedia`), not in the dashboard.
- `/api/devices/audio-inputs` returns empty — by design.

### Element: browser worker window
- **Separate window** with **visible address bar** (no app mode, no hidden tab).
- URL: `http://127.0.0.1:8765/google-asr?autostart=1[&locale=…]`.
- Isolated Chrome profile: `user-data/browser-worker-profile-classic-*`.
- Anti-throttle flags + EcoQoS opt-out on Windows.

### Element: recognition language
- **Settings** → Web Speech / `asr.browser.recognition_language`.
- Worker UI shows live/final text and WS diagnostics.
- If worker has text but dashboard is empty — issue is ingest/WS, not Chrome recognition.

### Element: advanced Web Speech settings
- **Settings** → “Advanced Web Speech settings” (`asr.browser.*`).
- Groups: forced final, restart, network reconnect, session rotation, partial filtering.
- After changes: Save config → **Stop/Start** and reopen worker if needed.

### Element: worker stability (ported from SST)
- Screen Wake Lock while recognition runs.
- Session rotation `max_browser_session_age_ms` (default 180000 ms).
- Network preflight → terminal `recognition_network_unreachable` after repeated network errors.
- Force-finalization for stuck partials.

**Not in core:** local Parakeet, experimental `/google-asr-experimental`, remote ingest.

---

## 5. Translation

### 5.1 Main toggles

#### Element: enable translation
- Turns translation pipeline on/off.
- ASR works without translation (source-only flow).

#### Element: translation cache
- **In memory:** skip duplicate provider calls.
- **On disk:** `user-data/translation-cache/` across sessions.
- **Trade-off:** old cache may conflict with changed LLM prompts.

### 5.2 Translation lines (`translation_1`…`translation_5`)

- Up to **5** independent lines: `enabled`, `target_lang`, `provider`, `label`.
- Each enabled line adds dispatcher load.
- Display order — **Subtitles** tab (slot ids).

### 5.3 Providers (13)

`google_translate_v2` (default), `google_cloud_translation_v3`, `google_gas_url`, `google_web`, `azure_translator`, `deepl`, `libretranslate`, `openai`, `openrouter`, `lm_studio`, `ollama`, `public_libretranslate_mirror`, `free_web_translate`.

- OpenAI-compatible helpers: `/api/openai/recommended-models`, `/api/openai/models` (static list).
- Credentials in `translation.provider_settings` — stored locally in `config.toml`.

### 5.4 Translation dispatcher
- Timeout, queue size, max concurrent jobs.
- Per-provider limits (`provider_limits`).
- **Lifecycle:** completed block stays until new phrase finalizes; late translations allowed; stale drop for superseded in-flight jobs only.

### 5.5 Translation results block
- Shows latest translations and provider errors.
- Delayed translation is not always failure (supersession / stale protection).

---

## 6. Subtitle output (Subtitles)

### Element: overlay preset
- `single`, `dual-line`, `stacked`, `compact`.
- Query override: `?preset=…&compact=1`.

### Element: visibility
- Source / translation toggles.
- Max visible translation lines.

### Element: TTL and lifecycle
- `completed_block_ttl_ms`, source/translation TTL.
- Sync flags: keep source while translation visible.
- **Intent:** completed translation stays visible while next phrase is still partial; replacement after new phrase finalizes.

### Element: line order
- Affects dashboard preview, OBS overlay, and OBS CC `first_visible_line` mode.

---

## 7. Subtitle style (Style)

- Built-in and custom presets.
- Base controls: font, size, weight, color, outline, shadow, background, alignment, spacing.
- Effects: `none`, `fade`, `subtle_pop`, `slide_up`, `zoom_in`, `blur_in`, `glow`.
- Per-slot overrides: `source`, `translation_1`…`translation_5`.
- **Shared payload** for dashboard preview and OBS overlay.
- Save config/profile after edits.

---

## 8. UI theme (Theme)

- Dark / light mode.
- Accent palette gradients.
- Affects dashboard chrome only; OBS overlay uses subtitle-style config.

---

## 9. OBS

### Element: overlay URL
- Copied from **OBS** tab (`GET /api/obs/url`).
- Default: `http://127.0.0.1:8765/overlay`.
- Update OBS if bind changes (LAN mode).

### Element: OBS Closed Captions
- WebSocket host/port/password (OBS v5).
- Output mode: source live/final, translation slots, first visible line.
- Timing: partial throttle, min delta, clear after ms, dedupe.
- Debug mirror — text source for CC debugging.

---

## 10. Word replacement

- Find/replace rules **before** translation and output.
- Built-in profanity lists (en, ru, ja, ko, zh).
- Case-insensitive / whole words only.
- TTS sync via `tts_sync_source_text_replacement` when TTS is enabled.

---

## 11. TTS module

### Element: `/tts` window
- Separate UI: **Speech** and **Twitch** tabs.
- Open from dashboard or Tauri IPC `tts_open_window`.

### Element: Speech
- TTS provider, voice, rate/pitch/volume.
- Audio routing: browser element or WinAPI per-process (`VOICESUB_TTS_PER_PROCESS_ROUTING`).
- Subtitle-driven planner (`tts_plan_subtitle_speech`).

### Element: Twitch
- OAuth via system browser.
- IRC chat → speech queue.
- Filters, emotes, replacements (`voicesub-twitch` crate).

### Element: Python sidecar
- `bin/modules/tts/runtime/` — embedded fetcher for Google TTS proxy.
- `/api/tts/python/status` — runtime probe.

---

## 12. Tools & Data

### Element: Runtime Diagnostics
- Phase, worker connected, translation queue, OBS CC state, metrics.
- Log paths: `logs/core.log`, `runtime-events.log`, `session-latest.jsonl`.

### Element: profiles
- CRUD via UI → `user-data/profiles/{name}.toml`.
- Quick switching between streaming setups.

### Element: Export Diagnostics
- ZIP: redacted config, runtime status, session log, core log.
- `GET /api/exports/diagnostics`.

### Element: deep diagnostics (env)
- `VOICESUB_DEEP_DIAGNOSTICS=1` or `logging.full_enabled` in config.
- Per-channel: `VOICESUB_TRACE_SUBTITLE`, `_BROWSER`, `_WS`, `_TTS`, …

---

## 13. Settings

### Element: UI language (EN / RU / JA / KO / ZH)
- Svelte i18n: `src/lib/i18n/locales/*.json`.
- Saved in `ui.language` → Save config.
- Worker gets `locale` query param on launch.
- Overlay i18n: `bin/overlay/shared/js/i18n/`.
- **Details:** `TECHNICAL_ARCHITECTURE.en.md` §23.

### Element: SST config.json import
- Migrates to `config.toml`, `config_version` → 8.
- `local` / `remote` / experimental → `browser_google` + import hint.
- `ui.show_remote_tools` → false.

### Element: layout
- `standard` vs `compact` — affects Tauri window size.

---

## 14. Help

Built-in topics: overview, recognition, translation, subtitles/style, OBS, tools. No remote mode section (removed from core).

---

## 15. Privacy and local-first

- **Local-first:** default `127.0.0.1`; LAN only with `VOICESUB_ALLOW_LAN=1`.
- API keys and Twitch tokens — local disk only.
- Diagnostics export — redacted secrets.
- Chrome worker — isolated profile, no sync.

---

## 16. Glossary

| Term | Meaning |
| --- | --- |
| **partial** | In-progress recognized text |
| **final** | Finalized phrase segment |
| **translation slot** | Line `translation_1`…`translation_5` |
| **overlay** | Vanilla `/overlay` page for OBS |
| **browser worker** | Chrome window running Web Speech |
| **completed block** | Final subtitle until next phrase finalizes |
| **TTS module** | Sidecar `/tts` + Rust service |

---

## 17. Archived features (not in core 0.5.0)

| SST feature | VoiceSub status |
| --- | --- |
| Local Parakeet | `legacy/modules-source/parakeet/` → Phase 4 module |
| Remote controller/worker | `legacy/remote/` → future module |
| Experimental browser | `legacy/experimental-browser/` — routes removed |
| PyInstaller bootstrap | Replaced by Tauri NSIS installer |
| Splash startup profiles | None — single `VoiceSub.exe` |

For browser/translation/subtitle parity, see golden tests in `tests/golden/`.
