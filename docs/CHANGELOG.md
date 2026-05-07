# SST Desktop Changelog

Единая история изменений desktop-версии.

Этот файл является каноническим changelog для релизов SST Desktop. Версионные release notes в `docs/DESKTOP_RELEASE_CHANGELOG_*.md` остаются как delta-документы по конкретным релизам, но основной историей изменений считается этот файл.

## Unreleased

Post-`0.3.0` branch follow-up focused on internal modularization and runtime start behavior, without changing the local-first product default or the public version source of truth.

### Architecture follow-up

- monolithic `backend/config.py` has been replaced by the `backend/config/` package with explicit `defaults.py`, `secrets.py`, and domain normalizers under `backend/config/normalizers/`;
- `RuntimeOrchestrator` now physically lives in `backend/core/runtime_orchestrator.py`, while `backend/core/subtitle_router.py` keeps subtitle lifecycle logic and a compatibility-only import shim;
- runtime orchestration is now split further across `backend/core/runtime/` helpers, with `backend/core/runtime_orchestrator.py` used directly by bootstrap wiring;
- translation provider extraction is now completed for the current provider set under `backend/translation/providers/`, while `backend/core/translation_engine.py` remains the compatibility engine/shim entrypoint;
- the docs now describe the real launcher profile surface: `Quick Start (Browser Speech)`, `NVIDIA GPU (CUDA)`, `CPU-only`, `Remote Controller`, and `Remote Worker`.

### Translation follow-up

- translation configuration now supports per-line provider selection through `translation.lines`;
- each translation line keeps a stable `slot_id` such as `translation_1`, and that slot id is now the primary identity for overlay ordering and rendering;
- duplicate target languages are now supported as long as the lines use different slots;
- translation cache keys now include `provider_name`, preventing collisions when two providers translate the same source into the same language;
- legacy `translation.provider` and `translation.target_languages` are preserved for compatibility and are regenerated from normalized slot configuration when needed;
- legacy `subtitle_output.display_order` entries based on language codes are migrated to translation slot ids.

### Runtime start contract

- `POST /api/runtime/start` now accepts an optional `config_payload` snapshot alongside `device_id`;
- the dashboard sends its current normalized in-memory config snapshot when the user presses `Start`, so runtime-only changes can take effect immediately without forcing `Save Settings` first;
- runtime start applies the snapshot in memory only, tracks it as active config state metadata, and does not persist it to `user-data/config.json` unless the user explicitly saves settings;
- remote session preload now also reads `remote.session_id` and `remote.pair_code` from that runtime-start snapshot so controller/worker pairing can follow unsaved UI changes cleanly.

### Tests and verification

- added API coverage proving that `/api/runtime/start` uses the unsaved config snapshot without mutating persisted config payloads;
- added runtime status coverage for `active_config_source`, `active_config_persisted`, and `active_config_hash`;
- added architecture coverage asserting that the new `backend/config/`, `backend/core/runtime/`, `backend/asr/parakeet/`, and `backend/translation/` entrypoints exist and import cleanly.

## 0.3.0

Архитектурный релиз с переносом backend на явные services/schemas/bootstrap слои, модульным frontend без build step, config migrations/schema export, новым runtime/browser ASR robustness layer и документированным experimental browser worker path.

### Основные изменения

- backend разделён на `api/routes`, `services`, `core`, `schemas` без смены базового local-first продукта;
- `app.state` больше не собирается вручную в одном `app.py`, а поднимается через централизованный bootstrap;
- config получил явные `config_version` migrations и JSON Schema export;
- dashboard переведён с монолитного `app.js` на ES modules с `core/`, `dashboard/`, `panels/`, `normalizers/`;
- Browser Speech lifecycle вынесен в отдельный supervisor/session manager и стал устойчивее к `onend`, `no-speech`, reconnect и stale worker state;
- `/ws/events` и `/ws/asr_worker` получили более безопасную обработку reconnect/dead socket/stale browser generation сценариев;
- client-event logging стал best-effort и больше не должен валить backend из-за проблем записи live event log;
- overlay/runtime event path теперь лучше переживает duplicate/stale event storm и поздние translation updates;
- отдельная experimental страница `/google-asr-experimental` включена в релиз как поддерживаемый experimental path на базе `SpeechRecognition.start(audioTrack)`;
- локальный AI path и `browser_google` не удалены; Parakeet остаётся доступным;
- unsupported backend ASR experiment removed from the active product surface; only Parakeet + browser worker modes remain.

### Backend Architecture

- добавлены и подключены `backend/services/runtime_service.py`, `settings_service.py`, `asr_service.py`, `translation_service.py`, `diagnostics_service.py`, `export_service.py`, `overlay_service.py`, `model_manager_service.py`;
- введён `backend/core/app_bootstrap.py` как единая точка инициализации runtime paths, managers, services и orchestrator wiring;
- выделены shared utilities:
  - `backend/core/paths.py`
  - `backend/core/logging_setup.py`
  - `backend/core/api_errors.py`
  - `backend/core/redaction.py`
- `backend/runtime_paths.py` оставлен как совместимый shim поверх нового paths layer;
- routes стали тоньше и делегируют orchestration в app services;
- `backend/api/routes_profiles.py` переведён на более структурированный API error payload.

### Config, Migrations, Schema

- config переведён на явные migrations через `backend/core/config_migrations.py`;
- profiles и основной config теперь проходят общий migration/normalization pipeline;
- добавлен schema export через `backend/core/config_schema_export.py`;
- schema публикуется в `backend/data/config.schema.json`;
- расширены Pydantic schema-модули в `backend/schemas/` для config/runtime/asr/translation/overlay/diagnostics;
- migration v3 переводит `official_eu_parakeet_realtime` на `official_eu_parakeet_low_latency`;
- unsupported historical backend ASR settings are normalized back to the supported Parakeet defaults.

### Frontend Modularization

- dashboard entrypoint переведён на `frontend/js/main.js`;
- новый module stack:
  - `frontend/js/core/`
  - `frontend/js/dashboard/`
  - `frontend/js/panels/`
  - `frontend/js/normalizers/`
- store/API/WebSocket/events/logging вынесены в отдельные модули;
- panel logic разделён по доменам вместо наращивания одного файла;
- normalizers стали отдельными testable pure functions;
- при этом стек остался прежним:
  - plain HTML/CSS/JS
  - FastAPI static serving
  - без Node.js, React, Vite, Webpack и любого build pipeline.

### Browser Speech Robustness

- lifecycle browser recognition вынесен в `frontend/js/browser-asr-session-manager.js`;
- введён supervisor с состояниями:
  - `idle`
  - `starting`
  - `running`
  - `stopping`
  - `restarting`
  - `backoff`
  - `fatal`
- убран старый хаотичный `start/stop/onend` loop;
- `recognition.start()` больше не вызывается поверх `stopping`, а откладывается до controlled restart;
- добавлены reason-aware cooldowns:
  - `normal_onend`
  - `settings_change`
  - `websocket_reconnect`
  - `watchdog_stall`
  - `no_speech`
  - `network`
- добавлены worker diagnostics:
  - `generation_id`
  - `session_id`
  - `recognition_state`
  - `browser_supervisor_state`
  - `desired_running`
  - `pending_start`
  - `restart_count`
  - `no_speech_count`
  - `network_error_count`
  - `duplicate_partial_suppressed`
  - `duplicate_final_suppressed`
  - `late_forced_final_suppressed`
  - mic health fields (`mic_track_ready_state`, `mic_track_muted`, `mic_rms`, `mic_active_recent_ms`, `last_mic_activity_at`)
- browser worker reconnects теперь не должны оставлять runtime в stale `listening/stopping`;
- classic `/google-asr` worker приоритизирует собственные `localStorage` settings и только потом зеркалит их в backend config;
- experimental `/google-asr-experimental` worker синхронизирован с тем же base FSM и больше не должен ломаться из-за устаревшего subclass API.

### WebSocket and Runtime Event Resilience

- `backend/ws_manager.py` стал concurrency-safe и tolerant к disconnect/send failures;
- dead sockets удаляются после `WebSocketDisconnect`, `RuntimeError`, `OSError`, `ConnectionResetError`, `BrokenPipeError`;
- повторный disconnect/close больше не должен валить manager;
- runtime/browser worker events получают sequence-aware/stale-aware handling;
- duplicate `runtime_status -> listening` flood подавляется coalescing logic;
- reconnect `/ws/events` не должен размножать active client loops и старые timers;
- Windows close errors уровня `WinError 10022` обрабатываются как disconnect cleanup, а не как fatal runtime failure.

### Logging and Diagnostics

- `/api/logs/client-event` переведён в best-effort режим;
- проблемы записи live event log больше не должны приводить к backend `500`;
- `SessionLogger` создаёт log directory заранее, не держит проблемный file handle постоянно и считает dropped events;
- client log counters добавлены в runtime diagnostics;
- redaction применяется к чувствительным полям (`token`, `secret`, `password`, `pair_code`, `api_key`, credential-like keys);
- structured runtime logs усилены для browser recognition, runtime metrics и provider-specific paths.

### Overlay and Translation Consistency

- overlay/runtime path стал лучше защищён от stale translation mismatch;
- late/stale translation updates больше не должны так легко прилипать к новому source segment;
- duplicate runtime noise не должен лишний раз дёргать overlay payload;
- subtitle router и overlay broadcaster получили дополнительное suppression/coalescing поведение.

### ASR Surface Cleanup

- current ASR surface is limited to local Parakeet and the two browser worker modes;
- removed/unsupported backend ASR experiments are normalized away during config migration and save/load;
- dashboard and schema no longer expose deprecated backend transport settings.

### Remote Mode and Startup

- remote mode сохранён как explicit LAN-only exception;
- remote worker sync дополнительно фиксирует локальный AI provider, чтобы worker не уходил в browser worker path;
- default startup остаётся local-first;
- `start.bat` по смыслу не превращён в remote bootstrap;
- dashboard/overlay/browser worker pages по-прежнему обслуживаются локальным FastAPI backend.

### Документация

- обновлены `README.md` и `README.ru.md` под релиз `0.3.0`;
- обновлена полная техническая документация `docs/TECHNICAL_ARCHITECTURE.md`;
- обновлён delta changelog `docs/DESKTOP_RELEASE_CHANGELOG_0.3.0.md`;
- добавлен и обновлён manual Browser Speech live smoke checklist для classic и experimental worker paths.

### Тесты и верификация

Добавлено/обновлено покрытие для:

- backend architecture
- config migrations
- config schema export
- browser worker contract
- browser ASR service and gateway
- runtime event coalescing
- WebSocket manager dead-socket cleanup
- session logger failure tolerance
- frontend modular architecture
- dashboard logging contract
- runtime status contract
- ASR provider selection and legacy-config migration cleanup
- remote flow and versioning

Проверка на актуальном наборе изменений:

- `python -m compileall backend tests`
- `.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"`

Результат:

- `135 tests`
- `OK`

## 0.2.9.2

Patch-релиз со стабилизацией сохранения настроек и desktop translation UI.

### Основные изменения

- исправлено сохранение языка интерфейса;
- добавлено более широкое тестовое покрытие save/load основных групп настроек;
- исправлена ложная надпись в карточке последнего перевода, когда translation уже фактически выполнен.

### Детали

- язык интерфейса теперь сохраняется в `ui.language` и проходит через общий desktop config round-trip;
- добавлено regression-покрытие на `ui`, `audio`, `asr`, `translation`, `subtitle_output`, `subtitle_lifecycle`, `obs_closed_captions`, `remote`, `updates`;
- completion-event `TranslationDispatcher` больше не затирает реальные переводы пустым payload;
- карточка `Translated Results` теперь остаётся согласованной с фактическим translation state.

### Проверка

- `.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"`
- `build-bootstrap-launcher.bat`
- `publish-desktop-releases.ps1`

## 0.2.9.1

Patch-релиз с фиксом bootstrap AI install и жёстким восстановлением Browser Speech window invariant.

### Основные изменения

- clean portable AI bootstrap больше не должен падать на отсутствующем `lightning` при установке NeMo ASR зависимостей;
- desktop Browser Speech возвращён к старому стабильному сценарию запуска: отдельное окно Chrome/Chromium/Edge с видимой адресной строкой и isolated browser profile;
- из desktop UI убран selector режима окна browser worker;
- это поведение зафиксировано в AGENTS, README и технической документации как обязательный invariant.

### Детали

- в desktop runtime bootstrap добавлен офлайн seed для `lightning 2.4.0` перед установкой NeMo ASR зависимостей;
- browser worker снова запускается через отдельное окно с адресной строкой и isolated profile;
- user-facing mode toggle для browser worker window больше не поддерживается.

### Совместимость

- bootstrap one-file launcher остаётся primary release flow;
- managed runtime по-прежнему раскладывается рядом с `Stream Subtitle Translator.exe`;
- `user-data/` и `logs/` остаются локальными рядом с desktop runtime;
- default local-first behavior и localhost bind не меняются.

### Проверка

- `.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"`
- `build-bootstrap-launcher.bat`
- `publish-desktop-releases.ps1`

## 0.2.9.0

Крупный desktop-релиз с переходом на bootstrap one-file launcher и новой translation/runtime моделью.

### Основные изменения

- primary release flow переведён на bootstrap one-file launcher;
- публичный релиз распространяется как один `Stream Subtitle Translator.exe`;
- launcher при первом запуске сам раскладывает managed runtime рядом и умеет `verify / repair / reset`;
- source final публикуется сразу;
- перевод работает асинхронно и параллельно по target languages;
- stale translation results больше не должны догонять новый overlay;
- browser speech worker стал устойчивее к `onend`, visibility throttling и reconnect-сценариям;
- в runtime добавлены structured logs и live diagnostics для translation и browser ASR;
- desktop dashboard и overlay стали лучше переживать websocket reconnect и late translation arrival.

### Ключевые технические изменения

- новый async `TranslationDispatcher`;
- новый subtitle lifecycle с отдельными TTL для source и translation;
- structured JSONL logging для hot paths;
- live diagnostics в dashboard;
- улучшения overlay reconnect и OBS Closed Captions dedupe;
- повышение устойчивости translation cache;
- удалён `MyMemory`;
- добавлен `Google Cloud Translation - Advanced (v3)`.

### Packaging итог

- пользователь скачивает один `exe`;
- launcher сам восстанавливает `app-runtime/`, если он отсутствует или повреждён;
- managed runtime можно обновить простой заменой публичного `exe`.

### Что пока не входило

- runtime update из GitHub Releases;
- self-update самого launcher-а.
