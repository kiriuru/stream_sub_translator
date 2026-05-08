# SST Desktop 0.3.0

Delta changelog относительно `0.2.9.2`.

Предыдущий delta changelog:
- [DESKTOP_RELEASE_CHANGELOG_0.2.9.2.md](./DESKTOP_RELEASE_CHANGELOG_0.2.9.2.md)

Post-release изменения для текущей ветки `main` теперь живут в [CHANGELOG.md](./CHANGELOG.md) в секции `Unreleased`, чтобы заметки про shipped `0.3.0` оставались строго release-specific.

Текущее примечание:

- выбор провайдера «на каждую линию перевода», slot-based идентичность перевода, и вынос провайдеров перевода из legacy слоя — это post-`0.3.0` follow-up в ветке `main` и документируется в [CHANGELOG.md](./CHANGELOG.md) -> `Unreleased`, а не в shipped `0.3.0` delta.
- текущий follow-up в `main` также включает разделение UI вкладки Translation, более широкое покрытие i18n для dashboard, и выравнивание storage вокруг `logs/` и `user-data/models/`; эти изменения также отслеживаются в `Unreleased`.

Важно:

Ниже, в дополнение к shipped `0.3.0` delta, перечислены небольшие post-release UX hotfix-правки, которые уже лежат в `main` и воспринимаются пользователями как часть “текущего 0.3.0 поведения” (без смены `PROJECT_VERSION`).

## Кратко

`0.3.0` — это не patch-релиз, а крупный архитектурный релиз desktop-продукта.

Он объединяет несколько больших направлений:

- backend split на `routes/services/core/schemas`;
- централизованный bootstrap вместо ручной сборки `app.state` в `app.py`;
- явные config migrations и JSON Schema export;
- frontend dashboard на ES modules без build step;
- runtime/browser worker/WebSocket robustness layer;
- browser speech lifecycle supervisor и новая диагностика classic/experimental worker paths;
- best-effort client-event logging без backend `500`;
- formalized experimental browser worker `/google-asr-experimental`;
- unsupported backend ASR experiments removed from the active desktop surface; supported paths stay Parakeet + browser workers.

При этом базовые инварианты продукта не менялись:

- local-first desktop flow остаётся основным;
- dashboard/overlay/worker pages по-прежнему обслуживаются FastAPI;
- `browser_google` не удалён;
- локальный Parakeet path остаётся доступным;
- remote mode остаётся отдельным explicit LAN-сценарием.

## Изменения относительно 0.2.9.2

### 1. Backend Stage 1: services + bootstrap

Раньше большая часть orchestration logic была размазана между `backend/app.py`, routes и core-компонентами.

Теперь введён явный service layer:

- `backend/services/runtime_service.py`
- `backend/services/settings_service.py`
- `backend/services/asr_service.py`
- `backend/services/model_manager_service.py`
- `backend/services/translation_service.py`
- `backend/services/diagnostics_service.py`
- `backend/services/export_service.py`
- `backend/services/overlay_service.py`
- `backend/services/browser_asr_service.py`

И отдельный bootstrap:

- `backend/core/app_bootstrap.py`

Практический эффект:

- `app.py` стал точкой wiring, а не местом роста всей runtime логики;
- routes стали тоньше и проще для тестов;
- backend state собирается централизованно и предсказуемо;
- следующий этап декомпозиции runtime теперь можно делать без дальнейшего разрастания одного файла.

### 2. Новый paths/logging/error infrastructure

Добавлены:

- `backend/core/paths.py`
- `backend/core/logging_setup.py`
- `backend/core/api_errors.py`
- `backend/core/redaction.py`

Что это даёт:

- project-local paths теперь централизованы;
- logging setup отделён от бизнес-логики;
- frontend получает более структурированный API error shape;
- redaction применяется к чувствительным полям в diagnostics/export/logging paths.

`backend/runtime_paths.py` оставлен как совместимый shim.

### 3. Config migrations и schema export

Backend config перестал опираться только на неявную post-normalization логику.

Теперь:

- migrations вынесены в `backend/core/config_migrations.py`;
- `config_version` обновляется через явные шаги;
- профили проходят тот же pipeline, что и основной config;
- schema export доступен через `python -m backend.core.config_schema_export`;
- schema публикуется в `backend/data/config.schema.json`.

Новые/важные migration-шаги:

- `v3`: переход на `official_eu_parakeet_low_latency`;
- save/load pipeline дополнительно убирает deprecated backend ASR settings и возвращает конфиг к Parakeet defaults.

### 4. Dashboard frontend теперь модульный

Dashboard больше не держится на одном legacy `app.js`.

Новая структура:

- `frontend/js/main.js`
- `frontend/js/core/`
- `frontend/js/dashboard/`
- `frontend/js/panels/`
- `frontend/js/normalizers/`

Практический эффект:

- есть центральный store и отдельный ws/api client layer;
- panel logic больше не переплетён напрямую друг с другом;
- normalizers можно покрывать отдельно и не привязывать к DOM;
- это по-прежнему plain HTML/CSS/JS без Node.js/npm/Vite/Webpack/React.

### 4.1 UI hotfix follow-up (в текущем `main` после 0.3.0)

Небольшие UX-правки, которые не меняют архитектурные контракты, но заметны в ежедневном использовании:

- вкладка Translation:
  - подписи слотов перевода отображаются как человекочитаемые (`Перевод 1..5`), а не raw id;
  - карточки линий перевода показываются только после явного добавления (пустые слоты не “занимают место”);
  - исправлено поведение кликов/селектов внутри карточек (dropdown больше не схлопывается при выборе);
  - линия может быть временно выключена галочкой и остаётся видимой для повторного включения без перенастройки.
- runtime progress:
  - при Browser Speech режимах прогресс-блок становится компактным (в локальном runtime пути остаётся расширенным).
- i18n/персист UI:
  - experimental browser worker `/google-asr-experimental` использует тот же i18n слой, что и classic `/google-asr`;
  - переключение языка интерфейса сохраняется сразу, без обязательного нажатия `Save`.
- dev-итерация:
  - для frontend страниц и ассетов отключено HTTP-кеширование (обычный refresh подтягивает правки без “жёсткой” перезагрузки).
- style effects:
  - добавлены популярные эффекты появления: `slide_up`, `zoom_in`, `blur_in`, `glow` (работают и в dashboard preview, и в OBS overlay).

### 5. Runtime и WebSocket robustness layer

`0.3.0` значительно усиливает устойчивость runtime event path:

- `backend/ws_manager.py` теперь concurrency-safe и устойчивее к dead sockets;
- dead websocket connections удаляются после send/close errors;
- broadcast failures не ломают остальные live connections;
- runtime status duplicate flood теперь coalesce-ится;
- reconnect `/ws/events` и `/ws/asr_worker` больше не должны оставлять старые active loops/timers;
- stale browser worker generations подавляются на backend;
- Windows close errors уровня `WinError 10022` обрабатываются как disconnect cleanup, а не как fatal runtime failure.

Это критично для dashboard, overlay и Browser Speech lifecycle, потому что все они зависят от одного runtime/event surface.

### 6. Browser Speech classic path получил новый supervisor lifecycle

Classic `/google-asr` worker теперь использует выделенный lifecycle manager:

- `frontend/js/browser-asr-session-manager.js`

Ключевые изменения:

- supervisor state machine:
  - `idle`
  - `starting`
  - `running`
  - `stopping`
  - `restarting`
  - `backoff`
  - `fatal`
- controlled restart вместо синхронного `onend -> start()` loop;
- `start()` больше не стреляет повторно поверх `stopping`;
- reason-aware restart cooldown:
  - `normal_onend`
  - `settings_change`
  - `websocket_reconnect`
  - `watchdog_stall`
  - `no_speech`
  - `network`
- duplicate/forced-final suppression через `client_segment_id` и `generation_id`;
- mic health diagnostics:
  - `mic_track_ready_state`
  - `mic_track_muted`
  - `mic_rms`
  - `mic_active_recent_ms`
  - `last_mic_activity_at`
- degraded reasons:
  - `document_hidden`
  - `websocket_disconnected`
  - `mic_silent`
  - `mic_track_unavailable`
  - `web_speech_stalled`

Дополнительно:

- classic worker использует в приоритете собственный `localStorage`;
- backend config остаётся mirror/fallback path, а не жёсткий override для classic `/google-asr`;
- `/api/logs/client-event` больше не должен валить worker page при log write failures.

### 7. Browser Speech experimental path формализован и починен

`/google-asr-experimental` теперь задокументирован как отдельный experimental runtime path.

Состав:

- `frontend/google_asr_experimental.html`
- `frontend/js/browser-asr-audio-track-session-manager.js`

Поведение:

- сначала открывается live `MediaStreamTrack`;
- затем worker пытается вызвать `SpeechRecognition.start(audioTrack)`;
- если browser отклоняет `start(audioTrack)`, используется fallback на обычный `recognition.start()`.

Что важно в `0.3.0`:

- experimental subclass синхронизирован с новым base FSM API;
- cleanup идёт через общий `destroy()/pagehide` path;
- reconnect/settings reload не должны использовать устаревшие removed methods старого manager contract;
- теперь этот path официально отражён в документации и тестах как experimental.

### 8. Client-event logging больше не должен ломать backend

Route:

- `POST /api/logs/client-event`

Теперь работает в best-effort режиме:

- при успешной записи: `ok=true`, `logged=true`;
- при проблеме записи: `ok=true`, `logged=false`, `reason=log_write_failed`.

Практический эффект:

- lock/PermissionError на live event файле больше не приводит к backend `500`;
- dashboard/browser worker/overlay не должны падать только из-за проблем с local log file;
- dropped log events считаются отдельными diagnostics counters.

### 9. Overlay и subtitle routing лучше переживают stale event storm

В router/broadcast path усилены guards против stale/duplicate runtime noise:

- duplicate `runtime_status -> listening` flood подавляется;
- stale translation/source mismatch в overlay path дополнительно ограничен;
- browser worker telemetry больше не должна бесконечно генерировать одинаковые runtime snapshots;
- reconnect не должен размножать старый status history в dashboard.

### 10. ASR Surface Cleanup

Текущий проект после post-0.3.0 cleanup держит только:

- `browser_google`
- `browser_google_experimental`
- локальный Parakeet (`official_eu_parakeet_low_latency` / `official_eu_parakeet`)

### 11. Тестовое покрытие расширено

Добавлены/обновлены тесты для:

- backend architecture
- config migrations
- config schema export
- browser worker contract
- browser ASR service/gateway
- ws manager cleanup
- runtime event coalescing
- session logger failure handling
- frontend architecture
- dashboard logging
- remote flow
- versioning
- ASR provider selection and migration cleanup

## Ключевые файлы релиза

### Backend

- `backend/core/app_bootstrap.py`
- `backend/core/paths.py`
- `backend/core/api_errors.py`
- `backend/core/config_migrations.py`
- `backend/core/config_schema_export.py`
- `backend/core/redaction.py`
- `backend/runtime_paths.py`
- `backend/services/`
- `backend/schemas/`
- `backend/ws_manager.py`
- `backend/app.py`

### Browser Speech

- `frontend/google_asr.html`
- `frontend/google_asr_experimental.html`
- `frontend/js/browser-asr-session-manager.js`
- `frontend/js/browser-asr-audio-track-session-manager.js`
- `backend/core/browser_asr_gateway.py`
- `backend/services/browser_asr_service.py`
- `backend/core/session_logger.py`
- `backend/api/routes_logs.py`

### Dashboard frontend

- `frontend/index.html`
- `frontend/js/main.js`
- `frontend/js/core/`
- `frontend/js/dashboard/`
- `frontend/js/panels/`
- `frontend/js/normalizers/`

## Совместимость и ограничения

- `0.3.0` не меняет local-first baseline;
- remote mode остаётся explicit opt-in LAN scenario;
- Browser Speech experimental остаётся best-effort режимом;
- classic `browser_google` и локальный Parakeet path не удалены;
- dashboard визуально не перестраивался как новый продукт, хотя внутренняя модульная архитектура сильно изменилась.

## Проверка

Для текущего состояния релиза прогнано:

- `python -m compileall backend tests`
- `.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"`

Результат:

- `161 tests`
- `OK`
