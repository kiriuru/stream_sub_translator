# Журнал изменений SST Desktop

Единая история изменений desktop-версии.

Этот файл — канонический changelog для релизов SST Desktop. Версионные release notes в `docs/DESKTOP_RELEASE_CHANGELOG_*.md` остаются как delta-документы по конкретным релизам, но основной историей изменений считается этот файл.

## Unreleased

После релиза `0.3.1` дополнительных изменений в `main` пока нет. Любые follow-up правки будут добавляться сюда до выпуска следующей версии.

## 0.3.1

Релиз `0.3.1` фиксирует все post-`0.3.0` доработки в `main` и поднимает `PROJECT_VERSION` до `0.3.1`. Это в первую очередь релиз стабилизации рантайма, переноса перевода в выделенный пакет, более жёсткой защиты Web Speech на Windows 11 и доработки UX дашборда. Базовый local-first продукт и контракты `/api`/WebSocket не меняются.

### Версия и идентификация
- `backend/versioning.py`: `PROJECT_VERSION = "0.3.1"`, источник правды для `GET /api/version` и `POST /api/updates/check`.
- bootstrap-лаунчер и desktop-shell поднимают эту же версию.

### Стабилизация рантайма (RuntimeOrchestrator → контроллеры)

`RuntimeOrchestrator` (`backend/core/runtime_orchestrator.py`) стал фасадом над набором явных контроллеров в `backend/core/runtime/`, без изменения формы payload статуса или WebSocket-контракта:

- `RuntimeStateController` — coalescing и упорядочивание broadcast статуса рантайма;
- `AsrModeController` — разрешение и фиксация режима/провайдера ASR на сессию;
- `TranslationRuntimeController` — жизненный цикл `TranslationEngine` + `TranslationDispatcher`;
- `SubtitlePresentationController` — обёртка над `SubtitleRouter`;
- `OutputFanoutController` — fanout публикации в WebSocket дашборда и OBS;
- `TranscriptController` — оркестрация конвейера partial/final транскриптов;
- `RuntimeLifecycleCoordinator` — детерминированный порядок start/stop;
- `RuntimeMetricsController` — учёт метрик рантайма;
- `RuntimeSessionController` — идентичность сессии, метки времени, sequence/generation, записи экспорта;
- `SegmentStateController` — счётчик сегментов, активный сегмент, partial coalescing;
- `BrowserWorkerStateController` — состояние подключения/сессии/generation/signature браузерного worker-а;
- `RuntimeResetController`, `RuntimeStartStateController`, `RuntimeStopStateController`, `RuntimeExportController` — узкие вспомогательные шаги жизненного цикла;
- `SpeechSourceFactory` + явные источники речи `BrowserSpeechSource`, `LocalParakeetSpeechSource`, `RemoteControllerSpeechSource`, `RemoteWorkerSpeechSource`;
- `AudioCaptureController`, `ProcessingTasksController`, `SpeechSourceStateController`, `RemoteAudioStateController` — узкие контроллеры захвата/тасков.

Дополнительно:

- `TranslationDispatcher` стал перезапускаемым: `stop()` больше не «ломает» диспетчер для следующих сессий; `start()` сбрасывает внутреннее состояние остановки.
- очередь перевода: ограничение параллелизма по провайдеру и базовый rate limiting (защита от «пачек» при сохранении параллелизма по целевым языкам).
- проверки готовности локальных endpoint-ов кэшируются с фоновым обновлением, чтобы не блокировать горячие пути повторными пробами.

### Разделение SubtitleRouter

`backend/core/subtitle_router.py` разделён на:

- `subtitle_lifecycle_core.py` — конечный автомат жизненного цикла, TTL/релевантность, promotion/expiry;
- `subtitle_presentation.py` — сборка payload, порядок, слоты стилей, слияние partial и финала;
- `subtitle_router.py` — фасад публикации в overlay/WS, связывает core+presentation и хранит shim совместимости для старых импортов.

Все продуктовые инварианты жизненного цикла сохранены и покрыты регрессией.

### Перевод: новый пакет провайдеров и кеш

- провайдеры перевода вынесены из `backend/core/translation_engine.py` в пакет `backend/translation/`:
  - `base.py` (контракты, общий HTTP-слой), `engine.py`, `readiness.py`, `registry.py`,
  - `providers/google_v2.py`, `providers/google_v3.py`, `providers/google_gas.py`, `providers/experimental_google_web.py`, `providers/azure.py`, `providers/deepl.py`, `providers/libretranslate.py`, `providers/openai_compatible.py`, `providers/public_mirrors.py`.
- `backend/translation/registry.py` собирает реестр по умолчанию; `backend/core/translation_engine.py` остаётся точкой совместимости и подготовки запросов, но не содержит реализаций провайдеров.
- `backend/core/cache_manager.py` — новая реализация переводческого кеша: in-memory LRU с дебаунс-персистом на диск, безопасный для asyncio (без блокирующего I/O на каждый ход), автоматический карантин повреждённого файла кеша.
- ключи кеша перевода учитывают `provider_name`, исключая коллизии при двух провайдерах на один язык.
- конфигурация перевода поддерживает выбор провайдера на строку через `translation.lines`; у каждой строки стабильный `slot_id`, дубли целевых языков допустимы при разных слотах; legacy `translation.provider` и `translation.target_languages` сохранены для совместимости.
- legacy `subtitle_output.display_order` по кодам языков мигрируется в id слотов перевода (`translation_1..translation_5`).

### Конфигурация и атомарная запись

- монолитный `backend/config.py` заменён пакетом `backend/config/` с явными `defaults.py`, `secrets.py` и доменными нормализаторами в `backend/config/normalizers/`.
- config и профили пишутся атомарно через `backend/core/atomic_io.py` (временный файл рядом + `os.replace()`), Windows-safe.
- повреждённый `user-data/config.json` восстанавливается автоматически: невалидный JSON переносится в backup с меткой времени, восстанавливаются значения по умолчанию, миграции и нормализаторы выполняются и для восстановленного payload.
- `ConfigStateService` использует явную блокировку: активный in-memory снимок конфига безопасен при конкурентных операциях рантайма и настроек.
- активное состояние конфигурации отслеживается через метаданные `active_config_source`, `active_config_persisted`, `active_config_hash`.

### Поверхность Browser Speech

- Web Speech worker в desktop-сборке запускается через Google Chrome в отдельном окне с адресной строкой и изолированным профилем; `asr.browser.worker_launch_browser` поддерживает только `auto` и `google_chrome`.
- desktop-лаунчер всегда открывает worker в отдельном окне Google Chrome с адресной строкой и изолированным `--user-data-dir`.
- worker-окно Chrome запускается с `HIGH_PRIORITY_CLASS` и на Windows 10/11 c opt-out из `ProcessPowerThrottling` (Efficiency Mode), что устраняет «зависание» Web Speech при перекрытии окна.
- worker запускается с отключёнными Chrome feature gates: `CalculateNativeWinOcclusion`, `HighEfficiencyModeAvailable`, `HeuristicMemorySaver`, `IntensiveWakeUpThrottling`, `GlobalMediaControls`.
- классический и экспериментальный worker берут `navigator.wakeLock.request("screen")` пока распознавание активно и окно видимо; lock автоматически переснимается после visibility-flip и отпускается на Stop.
- ранняя контролируемая ротация сессии: `asr.browser.max_browser_session_age_ms` по умолчанию `180000` мс (раньше `240000`); окно `prepare_cycle_before_ms` остаётся `15000` мс.
- network preflight: после трёх `network` ошибок за ~12 c worker пробует `https://www.google.com/generate_204`; при провале supervisor уходит в терминальный `recognition_network_unreachable` вместо бесконечного цикла рестартов.
- добавлен health-сигнал `voice_below_recognition_threshold`: фиксирует кейс «голос слышен микрофону, но Google не распознаёт» (RMS ≥ 0.025, накопленные `no-speech`, тишина распознавания ≥ 8 с).
- experimental `/google-asr-experimental` выровнен с базовым FSM (`browser-asr-audio-track-session-manager.js`).

### Проверка обновлений (live)

- новый сервис `backend/services/update_service.py` и роут `POST /api/updates/check` (`backend/api/routes_updates.py`):
  - polling GitHub Releases по `updates.github_repo` и `updates.release_channel`;
  - сохраняет `updates.latest_known_version` и `updates.last_checked_utc` в `user-data/config.json`;
  - защищает `runtime_start_snapshot`: метаданные обновлений мерджатся в persisted-payload, а не пишут «снимок старта» обратно на диск.
- bootstrap-лаунчер тихо проверяет GitHub Releases на старте и показывает диалог только при доступной новой версии (Continue / Download).

### OpenAI helper endpoints

- новый роут `backend/api/routes_openai_models.py`:
  - `GET /api/openai/recommended-models` — курируемый список без обращения к OpenAI API из браузера;
  - `POST /api/openai/models` — листинг моделей по предоставленному ключу (с дефолтным фильтром «вероятно text-моделей»);
  - `POST /api/openai/usable-models` — лёгкая проба моделей через `/responses` с кэшированием и ограничением параллелизма.
- панель Translation использует эти endpoint-ы, чтобы заполнить поле `model` без хранения ключа во фронте.

### Дашборд и UX

- вкладка Translation вынесена в отдельный модуль `frontend/js/panels/translation-panel.js`:
  - разделение на панель маршрутизации/слотов и редактор настроек провайдера;
  - стабильные карточки `translation_1 .. translation_5` (рисуются только для явно добавленных линий);
  - выбор слота перенастраивает редактор настроек провайдера на провайдера этого слота;
  - предупреждения о незаполненных обязательных настройках провайдеров для включённых слотов.
- вкладка Style: тема интерфейса (светлая/тёмная) и палитра акцентного градиента (`ui.theme`, `ui.palette.accent*`), применяется и к окнам Web Speech worker.
- добавлены встроенные эффекты появления субтитров: `slide_up`, `zoom_in`, `blur_in`, `glow` (вместе с `none`, `fade`, `subtle_pop`).
- добавлена вкладка «Справка / Помощь» после «Tools & Data», устроена как локальные topic-tabs; в разделе remote зафиксирован порядок worker → controller → health → pairing → sync settings → prepare run → start worker runtime → bridge windows → start controller dashboard.
- расширенное покрытие i18n: прогресс рантайма, редактор слотов стиля, remote LAN, диагностика и прочий ранее захардкоженный текст.
- карточка прогресса рантайма в режимах Browser Speech переключается на компактный вид.
- смена языка UI сохраняется сразу, без обязательного глобального Save.
- статус `experimental` для экспериментальных провайдеров перевода больше не сводится в `degraded`.
- для разработки маршруты и статика отдаются с заголовками no-store (`Cache-Control: no-store, no-cache, must-revalidate`), обычный refresh подхватывает правки.

### Логи, диагностика, экспорт

- структурированный рантайм-лог сжимается через `backend/core/structured_log_compact.py` (truncate длинных строк, summary длинных списков, ограничение глубины), JSONL остаётся пригодным даже на медленных дисках.
- `/api/logs/client-event` остаётся best-effort: при сбоях записи возвращает `ok=true`, `logged=false`, `reason=log_write_failed`.
- `GET /api/exports/diagnostics` собирает локальный ZIP: `runtime_status.json`, `preflight_report.json`, `config_redacted.json`, `latest_session.jsonl`, `runtime-events.jsonl`, `backend.log`, `environment.txt`, `diagnostics-manifest.json`; чувствительные поля редактируются.
- runtime-кеши/temp остаются локальными к detected runtime environment (`runtime_dir`, `cache_root`, `temp_root`).

### Контракт старта рантайма

- `POST /api/runtime/start` принимает опциональный `config_payload` вместе с `device_id`;
- дашборд отправляет текущий нормализованный in-memory конфиг при нажатии «Старт», чтобы изменения только в рантайме применялись без обязательного «Save Settings»;
- снимок применяется только в памяти, помечается метаданными активного конфига (`runtime_start_snapshot`, `persisted=false`) и не пишется в `user-data/config.json`, пока пользователь явно не сохранит настройки;
- предзагрузка remote-сессии читает `remote.session_id` и `remote.pair_code` из этого снимка, чтобы pairing следовал несохранённым правкам UI.

### Хранилище и пути

- пользовательские логи бэкенда и desktop — в корневом `logs/` (устаревший `user-data/logs/` мигрируется при старте лаунчера/рантайма);
- локальные модели — в `user-data/models/`;
- bundled-схема и примеры в `backend/data/` остаются source assets;
- bind-адрес по умолчанию — `127.0.0.1`; LAN bind включается только в профиле Remote Worker.

### Тесты и верификация

- `python -m compileall backend desktop tests`
- `.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"`

Результат:

- `286 tests`
- `OK`

Покрытие фокусируется на:

- архитектуре backend (`tests/test_backend_architecture.py`, `tests/test_paths_release_contracts.py`);
- миграциях и экспорте схемы конфига (`tests/test_config_migrations.py`, `tests/test_config_schema_export.py`);
- контрактах browser worker и шлюза (`tests/test_browser_worker_contract.py`, `tests/test_browser_asr_gateway.py`, `tests/test_browser_asr_service.py`);
- рантайм-контроллерах (`tests/test_runtime_metrics_controller.py`, `tests/test_runtime_session_controller.py`, `tests/test_segment_state_controller.py`, `tests/test_browser_worker_state_controller.py`, `tests/test_runtime_lifecycle_coordinator.py`, `tests/test_runtime_non_remote_controllers.py`, `tests/test_runtime_event_coalescing.py`, `tests/test_runtime_event_sequence_monotonic.py`);
- subtitle lifecycle и роутере (`tests/test_subtitle_router.py`, `tests/test_subtitle_lifecycle_relevance.py`, `tests/test_subtitle_style_effects.py`);
- очереди перевода и провайдерах (`tests/test_translation_dispatcher.py`, `tests/test_translation_engine.py`, `tests/test_openai_compatible_provider.py`, `tests/test_config_translation_providers.py`, `tests/test_cache_manager.py`);
- update service (`tests/test_update_service_check_now.py`, `tests/test_update_service_persistence.py`);
- OpenAI helper endpoints (`tests/test_openai_models_route.py`);
- логировании и сессии (`tests/test_logging_and_session.py`, `tests/test_structured_log_compact.py`, `tests/test_structured_runtime_logger.py`, `tests/test_session_logger.py`);
- API/WebSocket (`tests/test_api_and_websockets.py`, `tests/test_ws_manager.py`, `tests/test_runtime_status_contract.py`);
- лаунчере и bootstrap (`tests/test_launcher.py`, `tests/test_bootstrap_launcher.py`, `tests/test_bootstrap_payload.py`, `tests/test_runtime_bootstrap.py`);
- ASR-провайдере и параметрах (`tests/test_asr_provider_contract.py`, `tests/test_asr_provider_selection.py`, `tests/test_parakeet_lifecycle.py`, `tests/test_parakeet_model_installer_manifest.py`, `tests/test_vad_engine.py`, `tests/test_segment_queue.py`, `tests/test_rnnoise_processor.py`).

## 0.3.0

Архитектурный релиз с переносом backend на явные слои services/schemas/bootstrap, модульным frontend без шага сборки, миграциями конфига и экспортом схемы, новым слоем устойчивости рантайма/browser ASR и документированным experimental-путём браузерного worker.

### Основные изменения

- backend разделён на `api/routes`, `services`, `core`, `schemas` без смены базового local-first продукта;
- `app.state` больше не собирается вручную в одном `app.py`, а поднимается через централизованный bootstrap;
- config получил явные migrations `config_version` и экспорт JSON Schema;
- dashboard переведён с монолитного `app.js` на ES modules с `core/`, `dashboard/`, `panels/`, `normalizers/`;
- жизненный цикл Browser Speech вынесен в отдельный supervisor/session manager и стал устойчивее к `onend`, `no-speech`, reconnect и устаревшему состоянию worker;
- `/ws/events` и `/ws/asr_worker` получили более безопасную обработку сценариев reconnect, мёртвого сокета и устаревшей generation браузерного worker;
- логирование client-event в режиме best-effort и больше не должно валить backend из-за ошибок записи live event log;
- путь overlay/рантайма лучше переживает шторм дубликатов/устаревших событий и поздние обновления перевода;
- отдельная experimental-страница `/google-asr-experimental` включена в релиз как поддерживаемый experimental-путь на базе `SpeechRecognition.start(audioTrack)`;
- локальный AI-путь и `browser_google` не удалены; Parakeet остаётся доступным;
- неподдерживаемые эксперименты backend ASR убраны с активной продуктовой поверхности; остаются только Parakeet и режимы browser worker.

### Архитектура backend

- добавлены и подключены `backend/services/runtime_service.py`, `settings_service.py`, `asr_service.py`, `translation_service.py`, `diagnostics_service.py`, `export_service.py`, `overlay_service.py`, `model_manager_service.py`;
- введён `backend/core/app_bootstrap.py` как единая точка инициализации путей рантайма, менеджеров, сервисов и связывания orchestrator;
- выделены общие утилиты:
  - `backend/core/paths.py`
  - `backend/core/logging_setup.py`
  - `backend/core/api_errors.py`
  - `backend/core/redaction.py`
- `backend/runtime_paths.py` оставлен как совместимый shim поверх нового слоя путей;
- маршруты стали тоньше и делегируют оркестрацию сервисам приложения;
- `backend/api/routes_profiles.py` переведён на более структурированный payload ошибок API.

### Конфигурация, миграции, схема

- config переведён на явные migrations через `backend/core/config_migrations.py`;
- профили и основной config проходят общий pipeline миграции/нормализации;
- добавлен экспорт схемы через `backend/core/config_schema_export.py`;
- схема публикуется в `backend/data/config.schema.json`;
- расширены Pydantic schema-модули в `backend/schemas/` для config/runtime/asr/translation/overlay/diagnostics;
- migration v3 переводит `official_eu_parakeet_realtime` на `official_eu_parakeet_low_latency`;
- устаревшие настройки исторического backend ASR при нормализации возвращаются к поддерживаемым дефолтам Parakeet.

### Модульность фронтенда

- точка входа dashboard — `frontend/js/main.js`;
- новый стек модулей:
  - `frontend/js/core/`
  - `frontend/js/dashboard/`
  - `frontend/js/panels/`
  - `frontend/js/normalizers/`
- store/API/WebSocket/events/logging вынесены в отдельные модули;
- логика панелей разделена по доменам вместо разрастания одного файла;
- normalizers — отдельные чистые функции, удобные для тестов;
- стек без изменений по принципу:
  - plain HTML/CSS/JS
  - раздача через FastAPI static
  - без Node.js, React, Vite, Webpack и любого конвейера сборки.

### Устойчивость Browser Speech

- жизненный цикл распознавания в браузере вынесен в `frontend/js/browser-asr-session-manager.js`;
- введён supervisor с состояниями: `idle`, `starting`, `running`, `stopping`, `restarting`, `backoff`, `fatal`;
- убран старый хаотичный цикл `start/stop/onend`;
- `recognition.start()` больше не вызывается поверх `stopping`, а откладывается до контролируемого перезапуска;
- добавлены cooldown с учётом причины: `normal_onend`, `settings_change`, `websocket_reconnect`, `watchdog_stall`, `no_speech`, `network`;
- добавлена диагностика worker (generation/session id, FSM-состояние, счётчики дубликатов/сетевых ошибок, здоровье микрофона);
- переподключения browser worker не должны оставлять рантайм в устаревшем `listening/stopping`;
- experimental `/google-asr-experimental` синхронизирован с тем же базовым FSM.

### Устойчивость WebSocket и событий рантайма

- `backend/ws_manager.py` стал безопаснее при конкуренции и терпимее к disconnect/ошибкам send;
- мёртвые сокеты удаляются после `WebSocketDisconnect`, `RuntimeError`, `OSError`, `ConnectionResetError`, `BrokenPipeError`;
- события рантайма/browser worker обрабатываются с учётом sequence и устаревания;
- лавина дубликатов `runtime_status -> listening` подавляется логикой coalescing;
- reconnect `/ws/events` не должен плодить активные client loops и старые таймеры;
- ошибки закрытия Windows уровня `WinError 10022` обрабатываются как очистка disconnect.

### Логирование и диагностика

- `/api/logs/client-event` переведён в режим best-effort;
- `SessionLogger` создаёт каталог логов заранее, не держит проблемный file handle постоянно и считает отброшенные события;
- структурированные логи рантайма усилены, чувствительные поля редактируются.

### Очистка поверхности ASR

- текущая поверхность ASR ограничена локальным Parakeet и двумя режимами browser worker;
- удалённые/неподдерживаемые эксперименты backend ASR вычищаются при миграции и save/load конфига.

### Тесты

Контрольная проверка на финальном наборе изменений `0.3.0`:

- `python -m compileall backend tests`
- `.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"`

Результат: `135 tests`, `OK`.

## 0.2.9.x

История `0.2.9.*` остаётся в архивных релизных заметках и не ведётся в этом основном changelog-файле.
