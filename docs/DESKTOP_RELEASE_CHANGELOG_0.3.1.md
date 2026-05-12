# SST Desktop 0.3.1

Сводка изменений относительно `0.3.0`.

Основная история изменений ведётся в [CHANGELOG.md](./CHANGELOG.md). Этот документ — delta-заметки выпущенного `0.3.1`, чтобы пользователям и операторам было видно «что появилось/поменялось в этом релизе» без чтения всего основного changelog.

`0.3.1` — это релиз стабилизации над `0.3.0`. Базовый local-first продукт, контракты `/api` и WebSocket, формы payload-ов overlay/runtime/transcript не менялись. Сборка по-прежнему распространяется как один публичный `Stream Subtitle Translator.exe` bootstrap-лаунчер.

## Кратко

- единая версия `PROJECT_VERSION = "0.3.1"` (`backend/versioning.py`);
- RuntimeOrchestrator превращён в фасад над набором явных контроллеров в `backend/core/runtime/`;
- `SubtitleRouter` разделён на lifecycle-core, presentation и тонкий фасад публикации;
- провайдеры перевода вынесены в отдельный пакет `backend/translation/providers/`, переводческий кеш переписан на in-memory LRU + дебаунс-персист;
- атомарная запись config/profiles и автоматическое восстановление повреждённого `user-data/config.json`;
- удалена ветка Microsoft Edge как отдельного worker-окна; Web Speech worker всегда открывается в отдельном окне Google Chrome с адресной строкой;
- Web Speech на Windows 11 получает Screen Wake Lock, HIGH_PRIORITY + opt-out из EcoQoS, отключённые Chrome feature gates, network preflight и health-сигнал `voice_below_recognition_threshold`;
- live update-чекер: `POST /api/updates/check` и тихая проверка на старте bootstrap-лаунчера;
- helper endpoints `/api/openai/*` для UI выбора моделей без хранения ключей во фронте;
- расширенный UX дашборда (раздельные карточки слотов перевода, тема/палитра, эффекты появления `slide_up`/`zoom_in`/`blur_in`/`glow`, вкладка Help).

## Совместимость

- `0.3.1` совместим с config из `0.3.0`: миграции запускаются автоматически, повреждённый JSON уходит в `*.corrupt-<timestamp>.json`.
- `asr.browser.worker_launch_browser`: разрешённые значения сужены до `auto` и `google_chrome`; legacy `microsoft_edge` мигрируется в `google_chrome`, `chromium` — в `auto`.
- `/google-asr-edge` и `/google-asr-experimental-edge` теперь возвращают `404` — это ожидаемое поведение, оставшееся в тестах (`tests/test_api_and_websockets.py`).
- `translation.lines` остаётся новой slot-aware конфигурацией перевода; `translation.provider` и `translation.target_languages` сохранены для совместимости.
- `subtitle_output.display_order` со старыми кодами языков мигрируется в стабильные id слотов `translation_1..translation_5`.

## Изменения относительно 0.3.0

### 1. Версия и identification

- `backend/versioning.py`: `PROJECT_VERSION = "0.3.1"`; `RELEASE_TRACK = "stable"`.
- `GET /api/version` отдаёт текущую версию и статус `updates.sync` (последняя известная версия, время проверки, доступно ли обновление по сравнению с локальной).
- bootstrap-лаунчер и desktop-shell поднимают эту же версию.

### 2. RuntimeOrchestrator → набор контроллеров

`backend/core/runtime_orchestrator.py` стал фасадом, явные контроллеры живут в `backend/core/runtime/`:

- `RuntimeStateController`, `AsrModeController`, `TranslationRuntimeController`, `SubtitlePresentationController`, `OutputFanoutController`, `TranscriptController`, `RuntimeLifecycleCoordinator`;
- `RuntimeMetricsController`, `RuntimeSessionController`, `SegmentStateController`, `BrowserWorkerStateController`;
- `RuntimeResetController`, `RuntimeStartStateController`, `RuntimeStopStateController`, `RuntimeExportController`;
- `SpeechSourceFactory` + явные источники `BrowserSpeechSource`, `LocalParakeetSpeechSource`, `RemoteControllerSpeechSource`, `RemoteWorkerSpeechSource`;
- `AudioCaptureController`, `ProcessingTasksController`, `SpeechSourceStateController`, `RemoteAudioStateController`.

Дополнительно:

- `TranslationDispatcher` стал restart-safe (`stop() -> start()`);
- per-provider concurrency/rate-limits в очереди переводов;
- readiness checks локальных endpoint-ов кэшируются и обновляются в фоне.

### 3. SubtitleRouter разделён

- `backend/core/subtitle_lifecycle_core.py` — FSM жизненного цикла субтитров, TTL/релевантность, promotion/expiry;
- `backend/core/subtitle_presentation.py` — сборка payload, порядок, слоты стилей, слияние partial и финала;
- `backend/core/subtitle_router.py` — фасад публикации в overlay и WebSocket дашборда, shim совместимости для старых импортов.

Регрессии покрывают и сценарий «старый завершённый перевод остаётся видимым, пока новая фраза ещё только partial».

### 4. Перевод: новый пакет провайдеров и кеш

- `backend/translation/`:
  - `base.py` (контракты, общий HTTP-слой), `engine.py`, `readiness.py`, `registry.py`;
  - `providers/`:
    - `google_v2.py`, `google_v3.py`, `google_gas.py`, `experimental_google_web.py`,
    - `azure.py`, `deepl.py`, `libretranslate.py`,
    - `openai_compatible.py` (используется для `openai`, `openrouter`, `lm_studio`, `ollama`),
    - `public_mirrors.py`.
- `backend/core/cache_manager.py` — in-memory LRU кеш с дебаунс-персистом, autoflush при выходе через `atexit`, карантин повреждённого `translation_cache.json` (`*.corrupt-<timestamp>.json`).
- ключи кеша включают `provider_name`, чтобы избежать коллизий при двух провайдерах на один язык.
- `TranslationEngine` использует общий `httpx.AsyncClient` с прогретыми keep-alive соединениями.

### 5. Конфигурация и атомарная запись

- `backend/config/`:
  - `defaults.py`, `secrets.py`, `__init__.py` (loader/normalizer + `LocalConfigManager`),
  - `normalizers/`: `asr.py`, `browser.py`, `obs.py`, `remote.py`, `subtitles.py`, `translation.py`.
- `backend/core/atomic_io.py` обеспечивает Windows-safe атомарную запись JSON (`os.replace()` поверх временного файла рядом).
- битый `user-data/config.json` уезжает в backup `config.json.corrupt-<timestamp>` и приложение поднимается на дефолтах, всё с тем же pipeline миграции/нормализации.
- `ConfigStateService` использует явную блокировку для active in-memory snapshot.

### 6. Browser Speech: убрана ветка Edge, усилен Chrome-worker

- `/google-asr-edge` и `/google-asr-experimental-edge` удалены (404).
- `asr.browser.worker_launch_browser` теперь `auto` или `google_chrome`; legacy `microsoft_edge` → `google_chrome`, `chromium` → `auto`.
- desktop-лаунчер всегда открывает worker через Google Chrome:
  - `--new-window` + URL;
  - изолированный `--user-data-dir` для классического и для experimental профилей раздельно;
  - `--disable-features=CalculateNativeWinOcclusion,HighEfficiencyModeAvailable,HeuristicMemorySaver,IntensiveWakeUpThrottling,GlobalMediaControls`;
  - `--disable-backgrounding-occluded-windows`, `--disable-renderer-backgrounding`, `--disable-background-timer-throttling`;
  - процесс стартует с `HIGH_PRIORITY_CLASS` и (Windows 10/11) opt-out из `ProcessPowerThrottling` (EcoQoS/Efficiency Mode).
- worker-страницы (`/google-asr`, `/google-asr-experimental`):
  - берут `navigator.wakeLock.request("screen")` пока распознавание активно и окно видимо; lock автоматически переснимается после visibility-flip и отпускается на Stop;
  - выполняют network preflight (`https://www.google.com/generate_204`) после трёх `network` ошибок за ~12 с; при провале supervisor уходит в терминальный `recognition_network_unreachable`;
  - публикуют health-сигнал `voice_below_recognition_threshold` (голос слышен микрофону, но не распознаётся);
  - `asr.browser.max_browser_session_age_ms` теперь по умолчанию `180000` мс (раньше `240000`), окно `prepare_cycle_before_ms = 15000` мс сохраняется.

### 7. Update checker (live)

- `backend/services/update_service.py`:
  - polling GitHub Releases по `updates.github_repo` и `updates.release_channel`;
  - сохраняет `updates.latest_known_version` и `updates.last_checked_utc`;
  - не пишет в `user-data/config.json` целиком, если активный конфиг — `runtime_start_snapshot`: метаданные обновлений мерджатся именно в persisted-снимок.
- `POST /api/updates/check` (`backend/api/routes_updates.py`) — ручная проверка.
- bootstrap-лаунчер тихо проверяет GitHub Releases на старте и показывает диалог только при доступной новой версии (Continue / Download).
- `versioning.extract_latest_github_release_version()` обрабатывает draft/prerelease и нормализует semver.

### 8. OpenAI helper endpoints

`backend/api/routes_openai_models.py`:

- `GET /api/openai/recommended-models` — курируемый shortlist (`gpt-4o-mini`, `gpt-4.1-mini`, `gpt-4.1-nano`, `gpt-4o`, `gpt-4.1`) без обращения к OpenAI API из браузера;
- `POST /api/openai/models` — листинг моделей по предоставленному ключу с фильтрацией «вероятно text-моделей»;
- `POST /api/openai/usable-models` — лёгкая проба моделей через `/responses` (max 16 tokens, store=false), кэширование на 10 минут, ограничение параллелизма (Semaphore=3).

Это позволяет панели Translation заполнить поле `model` без хранения ключа во фронте.

### 9. Дашборд и UX

- вкладка Translation вынесена в отдельный модуль `frontend/js/panels/translation-panel.js`:
  - разделение на панель маршрутизации/слотов и редактор настроек провайдера;
  - стабильные карточки `translation_1 .. translation_5`, рисуются только для явно добавленных линий;
  - выбор слота перенастраивает редактор настроек провайдера на провайдера этого слота;
  - предупреждения о незаполненных обязательных настройках провайдеров для включённых слотов.
- вкладка Style: тема интерфейса (светлая/тёмная) и палитра акцентного градиента (`ui.theme`, `ui.palette.accent*`) — применяются и к окнам Web Speech worker.
- встроенные эффекты появления субтитров расширены: `none`, `fade`, `subtle_pop`, `slide_up`, `zoom_in`, `blur_in`, `glow`. Используется как в превью дашборда, так и в OBS overlay.
- добавлена вкладка «Справка / Помощь» после «Tools & Data», организована как локальные topic-tabs:
  - обзор;
  - распознавание/тюнинг;
  - перевод;
  - субтитры/стиль;
  - OBS;
  - инструменты/диагностика;
  - desktop/remote.
- порядок remote-операций зафиксирован: worker → controller → check worker health → pairing/refresh remote state → sync worker settings → prepare remote run → start/check worker runtime → bridge windows открытыми → start controller dashboard.
- расширенное покрытие i18n (прогресс рантайма, редактор слотов стиля, remote LAN, диагностика и другие ранее захардкоженные тексты).
- карточка прогресса рантайма в режимах Browser Speech переключается на компактный вид.
- смена языка UI сохраняется сразу, без обязательного глобального Save.
- статус `experimental` для экспериментальных провайдеров перевода больше не нормализуется в `degraded`.
- для разработки фронтенд-маршруты отдаются с `Cache-Control: no-store, no-cache, must-revalidate`, обычный refresh подхватывает правки без жёсткой перезагрузки.

### 10. Логи, диагностика, экспорт

- `backend/core/structured_log_compact.py` сжимает структурированные runtime-события (truncate длинных строк, summary длинных списков, ограничение глубины), JSONL остаётся пригодным на медленных дисках и сетевых шарах.
- `/api/logs/client-event` остаётся best-effort: при сбоях записи возвращает `ok=true`, `logged=false`, `reason=log_write_failed`.
- `GET /api/exports/diagnostics` собирает локальный ZIP: `runtime_status.json`, `preflight_report.json`, `config_redacted.json`, `latest_session.jsonl`, `runtime-events.jsonl`, `backend.log`, `environment.txt`, `diagnostics-manifest.json`. Чувствительные поля редактируются.

### 11. Контракт старта рантайма

- `POST /api/runtime/start` принимает опциональный `config_payload` вместе с `device_id`.
- Снимок нормализуется через тот же pipeline, что и сохранение, применяется только в памяти и помечается метаданными `active_config_source = runtime_start_snapshot`, `active_config_persisted = false`, `active_config_hash`.
- `user-data/config.json` не перезаписывается, пока пользователь явно не сохранит настройки.
- Предзагрузка remote-сессии читает `remote.session_id` и `remote.pair_code` из этого снимка, чтобы pairing следовал несохранённым правкам UI.

### 12. Хранилище и пути

- пользовательские логи бэкенда и desktop — в корневом `logs/` (устаревший `user-data/logs/` мигрируется при старте лаунчера/рантайма);
- локальные модели — в `user-data/models/`;
- runtime-кеши/temp — локальные к detected runtime environment (`runtime_dir`, `cache_root`, `temp_root`);
- bind-адрес по умолчанию — `127.0.0.1`; LAN bind включается только в профиле Remote Worker.

## Ключевые файлы релиза

### Backend

- `backend/app.py`
- `backend/versioning.py`
- `backend/core/app_bootstrap.py`
- `backend/core/atomic_io.py`
- `backend/core/cache_manager.py`
- `backend/core/config_migrations.py`
- `backend/core/config_schema_export.py`
- `backend/core/runtime_orchestrator.py`
- `backend/core/runtime/` (контроллеры и источники речи)
- `backend/core/subtitle_router.py`, `subtitle_lifecycle_core.py`, `subtitle_presentation.py`
- `backend/core/structured_runtime_logger.py`, `structured_log_compact.py`
- `backend/core/translation_engine.py`, `translation_dispatcher.py`
- `backend/translation/` (пакет провайдеров)
- `backend/services/` (включая `update_service.py` и `config_state_service.py`)
- `backend/schemas/` (включая `config_schema.py` v6)
- `backend/api/routes_*.py` (включая `routes_updates.py` и `routes_openai_models.py`)
- `backend/ws_manager.py`

### Frontend

- `frontend/index.html`
- `frontend/google_asr.html`, `frontend/google_asr_experimental.html`
- `frontend/js/main.js`
- `frontend/js/core/` (store, API client, WS client, events, redaction)
- `frontend/js/dashboard/` (actions, helpers, logging, constants)
- `frontend/js/panels/` (translation-panel, asr-panel, runtime-panel, style-editor-panel, overlay-panel, diagnostics-panel, obs-captions-panel, profiles-panel, remote-panel, model-manager-panel)
- `frontend/js/normalizers/`
- `frontend/js/browser-asr-session-manager.js`, `browser-asr-audio-track-session-manager.js`
- `frontend/js/i18n.js`, `subtitle-style.js`, `ui-theme.js`, `desktop.js`

### Desktop

- `desktop/launcher.py` (Chrome worker, isolated profile, EcoQoS opt-out, feature-flag gates)
- `desktop/bootstrap_launcher.py` (тихая проверка обновлений + диалог Continue/Download)
- `desktop/runtime_bootstrap.py`
- `desktop/bootstrap_payload.py`, `desktop/build_bootstrap_payload.py`
- `requirements.desktop.txt`, `Stream Subtitle Translator.spec`, `Stream Subtitle Translator Bootstrap.spec`
- `build-desktop.bat`, `build-bootstrap-launcher.bat`, `publish-desktop-releases.ps1`

## Совместимость и ограничения

- `0.3.1` не меняет local-first baseline.
- Remote mode остаётся explicit opt-in LAN-сценарием.
- Browser Speech Experimental остаётся режимом без гарантий совместимости со всеми браузерами.
- Edge-сборка Web Speech удалена окончательно: используется только Google Chrome.
- Локальный Parakeet path и `browser_google` не удалены.

## Проверка

Для текущего состояния релиза прогнано:

- `python -m compileall backend desktop tests`
- `.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"`
- `cmd /c build-desktop.bat`
- `cmd /c build-bootstrap-launcher.bat`
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\publish-desktop-releases.ps1`

Результат:

- `286 tests`
- `OK`
- обновлённые артефакты:
  - `dist\Stream Subtitle Translator\Stream Subtitle Translator.exe`
  - `dist\bootstrap-launcher\Stream Subtitle Translator.exe`
  - `F:\AI\stream-sub-translator-desktop-release\Stream Subtitle Translator.exe`
  - `F:\AI\stream-sub-translator-desktop-release-clean\Stream Subtitle Translator.exe`
