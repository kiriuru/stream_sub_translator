# AGENTS.md

## Local-first product rules
- This project is local-first for the main app, UI, API, websocket, overlay, logs, cache, profiles, and exports.
- Do not add cloud deployment, Docker deployment, hosted backend, remote database, or SaaS assumptions.
- Do not add authentication, user accounts, multi-user support, or internet-facing hosting logic.
- All UI, API, websocket, overlay, logs, cache, profiles, and exports must run locally on the same Windows machine.
- Bind server to 127.0.0.1 by default, not 0.0.0.0.
- OBS overlay must be served from the same local FastAPI app via localhost.
- Do not introduce Electron, Tauri, Node.js, npm, pnpm, yarn, Vite, React, or frontend build tooling.
- Do not assume Codex cloud tasks are required to build or run the project.
- Prioritize local development workflow and local Codex-compatible repository structure.
- Browser-based speech recognition modes are allowed as explicit optional features when they are clearly labeled as browser-dependent/external and still feed the same local app pipeline.

## Project
Windows-first local real-time subtitle translator for streamers.

Pipeline:
microphone or browser speech worker -> ASR -> translation to 1..N target languages -> local OBS browser overlay -> export logs/subtitles

## Hard constraints
- Do NOT use Node.js, npm, pnpm, yarn, Vite, Webpack, or any frontend build tool.
- The app must be runnable with one click on Windows via `start.bat`.
- Keep microphone audio path simple and clean. Do not add speculative DSP, automatic EQ, auto gain, or “audio enhancement” logic. Optional experimental noise reduction paths may exist only as clearly labeled local-only features that stay off by default and do not replace the raw recognition path.
- Frontend must work without a JS build step.
- Realtime ASR must be GPU-first by default when CUDA is available.
- The default ASR provider/runtime policy should prefer `official_eu_parakeet_realtime` with GPU enabled.
- CPU fallback is allowed only as an explicit degraded safety mode and must be reported honestly.
- Optional browser-based ASR modes are allowed as alternative recognition backends and may use separate browser windows/tabs and browser APIs when clearly marked in UI and docs.
- Keep the architecture modular and easy to extend.

## Stack
- Python 3.11+
- FastAPI
- Uvicorn
- Pydantic
- WebSockets
- sounddevice
- numpy
- webrtcvad or silero-vad
- onnxruntime / onnxruntime-gpu
- httpx

## Translation rules
- Google Translate v2 is the primary translation provider and must be implemented first-class
- Translation must be optional
- Recognition must continue working without translation
- The user must be able to configure zero or more target languages and their output order
- The product must support source-only, translation-only, and mixed source+translation subtitle modes

## Subtitle output flexibility
The product must support flexible subtitle output modes.

Required output modes:
- source language only
- translation output only
- source language + one translation
- source language + multiple translations
- multiple translations without source text if configured

Requirements:
- the number of displayed translated languages must be configurable
- the order of displayed languages must be configurable
- source text visibility must be independently configurable
- translated text visibility must be independently configurable
- the UI and overlay must both follow the saved language order and visibility settings

Examples of valid user configurations:
- source only
- English only
- English + Japanese
- source + English
- source + English + Japanese

These examples are illustrative, not mandatory defaults.

## Language display rules
Do not hardcode any language as always required or always first.
Displayed languages and their order must come from user settings.
The app must support zero or more translation outputs depending on user configuration.

## Subtitle style requirements
Subtitle styling is a core product feature.

The app must support:
- multiple built-in subtitle style presets
- custom style editing
- local persistence of style settings in config and profiles
- compatibility with source-only, translation-only, and mixed subtitle modes

Style controls should support:
- font family
- font size
- text color
- outline/stroke
- shadow
- background style
- timing / ttl
- line behavior

## Subtitle rendering consistency
Dashboard preview and OBS overlay must use the same saved subtitle output settings and the same subtitle style settings.
Do not create separate conflicting style/state systems for preview and overlay unless explicitly required.

## Frontend rules
- Use plain HTML/CSS/JavaScript served by FastAPI.
- No Node.js dependency.
- No React, no TypeScript, no bundler.
- Keep UI simple, dark theme, modular JS files allowed.

## Overlay rules
- Overlay is a separate lightweight page for OBS Browser Source.
- It must reconnect automatically if websocket drops.
- Support presets:
  - single
  - dual-line
  - stacked
  - compact
- Support query params like:
  - `?profile=default`
  - `?profile=jp_stream&compact=1`

## Backend rules
Implement:
- `/api/health`
- `/api/runtime/start`
- `/api/runtime/stop`
- `/api/settings/save`
- `/api/devices/audio-inputs`
- `/api/obs/url`

Use:
- REST for settings and runtime control
- WebSocket for transcript / translation / overlay events / metrics

## Pipeline behavior
- microphone capture
- VAD segmentation
- ASR with partial and final segments
- translation fan-out to multiple languages
- overlay payload broadcasting
- export to `.srt` and `.jsonl`

## Required features
- Profiles
- Translation cache by `(source_text, source_lang, target_lang)`
- Per-stage latency metrics:
  - vad
  - asr
  - translation
  - total
- Status badges:
  - starting
  - idle
  - listening
  - transcribing
  - translating
  - error

## One-click startup
`start.bat` must:
1. Check Python
2. Create `.venv` if missing
3. Install requirements if needed
4. Ensure model directory exists
5. Start FastAPI app
6. Open browser to local UI
7. Keep console open with logs

`update.bat` must:
1. Pull updates if git exists
2. Upgrade/install requirements
3. Preserve config
4. Optionally clear stale caches

## Directory target
The listed directory target is a guiding structure, not a rigid requirement.
Do not reshuffle working code into placeholder files unless there is a clear functional benefit.

Create this structure:

stream-sub-translator/
  start.bat
  update.bat
  requirements.txt
  README.md
  .env.example
  AGENTS.md

  backend/
    app.py
    config.py
    models.py
    ws_manager.py

    api/
      routes_settings.py
      routes_runtime.py
      routes_devices.py
      routes_profiles.py
      routes_exports.py

    core/
      audio_capture.py
      vad.py
      segment_queue.py
      asr_engine.py
      parakeet_provider.py
      translation_engine.py
      subtitle_router.py
      overlay_broadcaster.py
      exporter.py
      profile_manager.py
      cache_manager.py

    data/
      config.json
      profiles/
      logs/
      exports/
      cache/
      models/

  frontend/
    index.html
    css/
      app.css
    js/
      app.js
      api.js
      state.js
      ws.js
      dashboard.js
      profiles.js
      logs.js
      overlay-designer.js

  overlay/
    overlay.html
    overlay.css
    overlay.js

## Done means
A task is complete only if:
- code is created in the correct files
- routes and modules are wired together
- README is updated
- startup commands are documented
- no Node.js dependency is introduced
- the local UI and overlay are both served from the Python app
