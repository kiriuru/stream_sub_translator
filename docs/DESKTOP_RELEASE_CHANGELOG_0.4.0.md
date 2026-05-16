# SST Desktop 0.4.0

## Русский

`0.4.0` — релиз **наблюдаемости и устойчивости Browser Speech** и **desktop UX** поверх `0.3.2`. Субтитры, жизненный цикл перевода и публичные `/api`/WebSocket-контракты сохранены; `config_version` — `7`.

### Что входит в 0.4.0

**Версия и backend**

- `backend/versioning.py` → `PROJECT_VERSION = "0.4.0"`.
- Browser ASR observability: trace id, monotonic time, normalized ingest, operational FSM, recovery policy, JSONL + replay.
- Ingress: отсев stale transport / overlap до пайплайна.
- WebSocket: bounded queues, drop-oldest; `replay_last`.
- Preview-переводы: supersession в `translation_dispatcher`.
- Исправление: `browser_asr_worker_connected()` — worker не отваливается сразу после connect.

**Desktop packaging**

| Exe | Назначение |
|-----|------------|
| `Stream Subtitle Translator.exe` | Splash: Web Speech quick start, NVIDIA GPU, CPU-only, Remote Controller/Worker |
| `Stream Subtitle Translator Only Web.exe` | Только Web Speech, без панели профилей |

Сборка: `build-bootstrap-launcher.bat`, `build-bootstrap-launcher-web-only.bat`, `publish-desktop-releases.ps1`, `publish-desktop-releases-web-only.ps1`.

**Browser Speech quick start lock**

- `asr.desktop_profile_lock = browser_speech` при Quick Start / Only Web; снимается при NVIDIA GPU / CPU-only.
- В Recognition нет Local Parakeet; hint `browser_quick_start_locked`.

**Dashboard**

- Панели монтируются сразу; настройки и desktop context в фоне (`main.js`, `desktop.js`).

**Документация**

- `docs/TECHNICAL_ARCHITECTURE.md`, `AGENTS.md`, `docs/CHANGELOG.md`, README.

### Проверка

- `python -m compileall backend desktop tests`
- `.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -p "test_*.py"`
- **336** tests, `OK`

## English

`0.4.0` combines **Browser Speech observability and resilience** with **desktop packaging and dashboard UX** on top of `0.3.2`. Subtitle lifecycle and public contracts are unchanged; `config_version` stays `7`.

### What is in 0.4.0

**Version and backend**

- `PROJECT_VERSION = "0.4.0"`.
- Browser ASR observability stack, ingress hardening, bounded WebSocket queues, preview translation supersession.
- Fix: restored `browser_asr_worker_connected()`.

**Desktop packaging**

- `Stream Subtitle Translator.exe` — profile splash.
- `Stream Subtitle Translator Only Web.exe` — Web Speech-only bootstrap.

**Quick start profile lock**

- Persists `desktop_profile_lock`; hides Local Parakeet until GPU/CPU profile launch.

**Dashboard**

- Non-blocking boot: panels first, settings and launch context in the background.

**Docs**

- Architecture, AGENTS, CHANGELOG, README.

### Verification

- Same commands as the Russian section above.
- **336** tests, `OK`
