# Manual smoke checklist (non-remote runtime)

Scope: **local Parakeet**, **Browser Speech classic**, **Browser Speech experimental**, **overlay**, **OBS captions**, and **update checks**.

Out of scope: **remote** (no remote websocket endpoint/security changes in this pass).

## Preconditions

- Start from repo root.
- Use the repo venv: `.\.venv\Scripts\python.exe`
- Default bind should remain **localhost-only** (`127.0.0.1`).

## Browser Speech classic

- **Start app** and open dashboard (`/`).
- **Open worker** page (`/google-asr`) using the desktop/launcher behavior.
  - Confirm: separate browser window, visible address bar, isolated profile directory.
- **Start recognition** in the worker.
- **Speak short phrase**.
  - Verify: partial appears, then final appears in dashboard and overlay.
- **Stop runtime** from dashboard.
  - Verify: overlay clears and status returns to idle.
- **Start again**.
  - Verify: worker reconnects/continues and transcript flow still works (no “dead after restart”).

## Browser Speech experimental

- Repeat the same flow but with `/google-asr-experimental`.
- Verify:
  - audio-track start path is used when supported
  - fallback to normal recognition happens if audio-track start is rejected (diagnostics in worker UI)

## Local Parakeet (microphone)

- Start runtime in local Parakeet mode with a microphone device selected.
- Verify ASR diagnostics:
  - provider/mode correct
  - GPU/CPU fallback status is honest (CPU fallback should be visible as degraded where applicable)
- Speak:
  - verify partial/final behavior
  - verify stop/start cycles (start → stop → start) do not break capture or ASR

## Overlay reconnect

- Open `/overlay` in a browser/OBS source.
- Start runtime and speak a short phrase.
- Refresh the overlay page.
  - Verify: latest payload is replayed quickly (overlay shows current/last visible block) and continues updating.

## OBS captions

- Enable OBS closed captions output in settings.
- Start runtime, speak a short phrase, then stop runtime.
- Verify:
  - no duplicate/stale caption spam on start/stop
  - restarting runtime does not duplicate caption streams

## Update check (runtime_start_snapshot protection)

- In dashboard, change a setting but **do not press Save** (ensure runtime start uses a `config_payload` snapshot).
- Start runtime (active config source should become `runtime_start_snapshot`).
- Trigger update check (`POST /api/updates/check` via dashboard UI/tools).
- Verify:
  - only `updates.latest_known_version` + `updates.last_checked_utc` were persisted to `user-data/config.json`
  - active config source remains `runtime_start_snapshot` after the update check
  - the unsaved runtime-only setting did not get written to disk

