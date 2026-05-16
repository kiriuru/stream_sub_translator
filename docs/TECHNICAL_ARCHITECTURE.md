# SST Desktop 0.4.0 — Технический документ

Актуально для линии кода, где `backend/versioning.py` содержит `PROJECT_VERSION = "0.4.0"`.

Этот документ описывает реальный layout проекта, контракт API/WebSocket, доменные схемы (Pydantic), конфигурационный pipeline и поток данных через рантайм. Документ — основной reference: README — короткий обзор продукта, CHANGELOG — история изменений, delta installer notes — `docs/DESKTOP_RELEASE_CHANGELOG_*.md` (формат как [GitHub Release v0.2.9.2](https://github.com/kiriuru/stream_sub_translator/releases/tag/v0.2.9.2)), здесь — архитектура.

### Публичный GitHub vs локальная desktop-сборка

| Поверхность | В публичном репозитории (`start.bat`) | Только локально (exe / PyInstaller) |
| --- | --- | --- |
| Backend, frontend, overlay, `tests/` (tracked) | да | да (внутри managed runtime) |
| `desktop/`, `build-*.bat`, `publish-desktop-releases*.ps1`, `*.spec` | **нет** | да |
| Desktop-only тесты (`test_launcher`, `test_desktop_profile_lock`, …) | **нет** | да |
| GitHub Releases: `Stream Subtitle Translator.exe`, `Only Web.exe` | assets | собираются локально |

Разработка рантайма и UI — из клона GitHub + `start.bat`. Установщики desktop — из локального дерева с `desktop/` (см. §14).

## 1. Назначение и границы системы

`stream-sub-translator` — локальное Windows desktop-приложение для субтитров в реальном времени:

- захват речи:
  - локальный микрофон (sounddevice + Parakeet);
  - browser speech worker (отдельное окно Google Chrome с адресной строкой);
  - опциональная цепочка remote controller → worker (только LAN, явный профиль запуска).
- ASR:
  - локальный AI runtime (Parakeet, GPU/CPU);
  - приём потока от browser speech worker через `/ws/asr_worker`.
- опциональный перевод на 0..N целевых языков с независимым выбором провайдера на слот;
- единая маршрутизация subtitle payload в dashboard, OBS overlay и OBS Closed Captions;
- экспорт сессий (SRT/JSONL/diagnostics) и локальные runtime/client diagnostics.

Жёсткие границы (за пределы выходить нельзя):

- рантайм по умолчанию local-first и только localhost (`127.0.0.1`);
- без cloud backend, accounts, hosted database, SaaS-assumptions;
- frontend без Node.js/React/build-pipeline;
- dashboard, browser worker pages, overlay и remote bridge pages обслуживаются FastAPI;
- remote mode — отдельный explicit LAN-сценарий, не интернет-facing deployment.

## 2. Технологический стек

- Python 3.11+;
- FastAPI + Uvicorn (HTTP/WebSocket);
- Pydantic v2 schemas (`backend/schemas/`);
- `httpx` для исходящих HTTP-запросов провайдеров перевода и update-чекера;
- `sounddevice`, `numpy`, `webrtcvad`, опциональный RNNoise (CPU);
- Parakeet (NeMo) для локального ASR (GPU-first, CPU fallback);
- frontend — plain HTML/CSS/JavaScript (ES modules), без шага сборки;
- desktop-shell — `pywebview` для splash-launcher с выбором startup-профиля;
- bootstrap-лаунчер на чистом Python (PyInstaller one-file).

## 3. Верхнеуровневая схема рантайма

```mermaid
flowchart LR
  subgraph Capture["Источник речи"]
    M["sounddevice (микрофон)"]
    BW["Browser Speech worker<br/>Chrome window /google-asr*"]
    RC["Remote controller<br/>(LAN audio ingest)"]
  end

  subgraph ASR["ASR"]
    PA["Local Parakeet<br/>(GPU/CPU)"]
    BG["BrowserAsrGateway"]
    RW["Remote worker results"]
  end

  subgraph Routing["Subtitle pipeline"]
    TR["TranscriptController<br/>+ optional text filter"]
    SLC["SubtitleLifecycleCore<br/>(TTL, FSM)"]
    SP["SubtitlePresentation<br/>(payload, slots, order)"]
    SR["SubtitleRouter<br/>(facade)"]
  end

  subgraph Translation["Перевод (опционально)"]
    TD["TranslationDispatcher<br/>(slots, queue, rate limit)"]
    TE["TranslationEngine<br/>+ CacheManager"]
    TP["Providers:<br/>google_v2/v3, gas, web,<br/>azure, deepl, libre,<br/>openai/openrouter/lm_studio/ollama"]
  end

  subgraph Output["Локальный вывод"]
    WS["/ws/events (dashboard)"]
    OV["/overlay (OBS Browser Source)"]
    OBS["OBS Closed Captions"]
    EX["Экспорт SRT/JSONL/diagnostics"]
    LG["Структурированные логи"]
  end

  M --> PA
  BW -->|/ws/asr_worker| BG
  RC -->|/ws/remote/audio_ingest| PA
  RW -->|/ws/remote/result_ingest| BG

  PA --> TR
  BG --> TR
  TR --> SR

  SR --> SLC
  SR --> SP
  SR --> TD
  TD --> TE
  TE --> TP
  TP --> TD
  TD --> SR

  SR --> WS
  SR --> OV
  SR --> OBS
  SR --> EX
  SR --> LG
```

## 4. Layout репозитория

```
stream-sub-translator/
├── backend/
│   ├── app.py                    # FastAPI app + bootstrap + WebSocket handlers
│   ├── versioning.py             # PROJECT_VERSION + GitHub Releases helpers
│   ├── ws_manager.py             # WebSocket manager: snapshot, dead-socket cleanup
│   ├── preflight.py              # стартовая диагностика
│   ├── models.py                 # внешние pydantic-модели ответа API
│   ├── server_runtime.py
│   ├── run.py / run_controller.py / run_worker.py
│   ├── runtime_paths.py          # shim над backend.core.paths
│   ├── install_asr_model.py
│   ├── api/                      # тонкие HTTP-маршруты
│   ├── asr/parakeet/             # локальный Parakeet runtime
│   ├── config/                   # defaults, normalizers, LocalConfigManager
│   ├── core/                     # bootstrap, runtime, subtitle, logging, cache, atomic IO
│   ├── core/runtime/             # явные runtime-контроллеры
│   ├── data/                     # bundled config.example.json + config.schema.json
│   ├── schemas/                  # Pydantic-схемы (config/runtime/asr/...)
│   ├── services/                 # сервисы для маршрутов
│   └── translation/              # реестр перевода + провайдеры
├── frontend/
│   ├── index.html                # dashboard
│   ├── google_asr.html           # classic browser worker
│   ├── google_asr_experimental.html
│   ├── remote_controller_bridge.html
│   ├── remote_worker_bridge.html
│   ├── css/
│   └── js/
│       ├── main.js, app.js, api.js, ws.js, state.js, i18n.js, desktop.js
│       ├── browser-asr-session-manager.js
│       ├── browser-web-speech-recognition-policy.js
│       ├── browser-asr-audio-track-session-manager.js
│       ├── core/                 # store, api-client, ws-client, events, redaction
│       ├── dashboard/            # actions, helpers, logging, constants, desktop-profile-lock.js
│       ├── normalizers/          # pure normalization helpers
│       └── panels/               # translation, asr, runtime, style, overlay, diagnostics, ...
├── overlay/                      # overlay.html / overlay.css / overlay.js (OBS Browser Source)
├── tests/                        # unittest (tracked на GitHub; см. §20)
├── docs/                         # CHANGELOG, TECHNICAL_ARCHITECTURE, DESKTOP_RELEASE_CHANGELOG_*
├── start.bat, start-remote-*.bat # default local / remote entrypoints (в публичном репо)
├── requirements.*.txt            # backend / controller (desktop requirements — локально)
└── user-data/, logs/, fonts/     # локальные runtime-данные

# Ниже — layout полного dev-дерева (desktop packaging не в публичном GitHub):
# desktop/ (launcher.py, bootstrap_launcher*.py, runtime_bootstrap.py, …)
# build-desktop.bat, build-bootstrap-launcher*.bat, publish-desktop-releases*.ps1, *.spec
```

## 5. Backend layout (детально)

### 5.1 `backend/api/`

Тонкий транспорт. Каждый файл — только маршруты, делегирующие в сервисы.

| Файл | Префикс | Назначение |
| --- | --- | --- |
| `routes_runtime.py` | `/api` | `/runtime/start`, `/runtime/stop`, `/runtime/status`, `/obs/url` |
| `routes_settings.py` | `/api/settings` | `/load`, `/save` |
| `routes_devices.py` | `/api/devices` | `/audio-inputs` |
| `routes_profiles.py` | `/api/profiles` | CRUD профилей + структурированные API-ошибки |
| `routes_exports.py` | `/api/exports` | список экспортов + diagnostics ZIP |
| `routes_logs.py` | `/api/logs` | `/client-event` (best-effort write) |
| `routes_version.py` | `/api` | `GET /version` |
| `routes_updates.py` | `/api/updates` | `POST /check` (live polling GitHub Releases) |
| `routes_openai_models.py` | `/api/openai` | `recommended-models`, `models`, `usable-models` |
| `routes_remote.py` | `/api/remote` | state/pair/heartbeat + worker control surface |

### 5.2 `backend/services/`

Сервисный слой, инициализируется централизованно `backend/core/app_bootstrap.py`.

- `runtime_service.py` — фасад над `RuntimeOrchestrator` для маршрутов: start/stop/status, OBS URL.
- `settings_service.py` — load/save config через `LocalConfigManager`, координация с `ConfigStateService`.
- `config_state_service.py` — owner активного in-memory snapshot конфига:
  - метаданные `source` (`loaded_from_disk`, `settings_saved`, `runtime_start_snapshot`), `persisted`, `hash`;
  - явная блокировка для конкурентных операций рантайма и настроек;
  - `update_active_updates_metadata(...)` — патч `updates.*` без перетирания снимка старта.
- `asr_service.py` — приём аудиочанков (микрофон/remote), маршрутизация транскриптов в `RuntimeOrchestrator`.
- `browser_asr_service.py` — учёт identity browser worker (transport id, generation, session id), heartbeat, статус, передача транскриптов в `SubtitleRouter`.
- `translation_service.py` — фасад над `TranslationEngine`/`TranslationDispatcher`.
- `diagnostics_service.py` — `health`, `version_info`, runtime-метрики.
- `export_service.py` — построение SRT/JSONL и diagnostics ZIP (с редактированием чувствительных полей).
- `overlay_service.py` — построение overlay-URL по конфигу/профилю.
- `model_manager_service.py` — установка/обнаружение локальных моделей Parakeet.
- `update_service.py` — `check_now(force=...)`: polling GitHub Releases, сохранение `updates.latest_known_version` + `updates.last_checked_utc`, защита `runtime_start_snapshot`.

### 5.3 `backend/core/` — общая инфраструктура и subtitle/translation pipeline

| Модуль | Назначение |
| --- | --- |
| `app_bootstrap.py` | Поднимает `app.state.*`: paths, config_manager, ConfigStateService, ws_manager, audio devices, profile manager, cache_manager, dictionary_manager, structured/session loggers, RuntimeOrchestrator, все сервисы (включая UpdateService). |
| `paths.py` | `APP_PATHS`, `ensure_app_layout()` — корни runtime/data/logs/cache/temp/models/fonts. |
| `runtime_paths.py` (shim) | Совместимый импорт старого `backend.runtime_paths`. |
| `logging_setup.py` | Конфигурация `backend.log` (rotating handler). |
| `api_errors.py` | Структурированные ошибки FastAPI. |
| `redaction.py` | Маскировка чувствительных полей (`token`, `secret`, `password`, `pair_code`, `api_key`, и т.п.) для логов/экспорта. |
| `atomic_io.py` | Windows-safe атомарная запись JSON через `os.replace()`. |
| `cache_manager.py` | In-memory LRU кеш перевода + дебаунс-персист на диск + карантин повреждённого `translation_cache.json`. |
| `config_migrations.py` | Версионные миграции (`config_version`, текущая `7` в `schemas/config_schema.py`): UI/translation_lines/display_order/parakeet provider/legacy ASR cleanup; новые поля конфига подхватываются через defaults + нормализаторы без отдельного шага migrate для каждой мелкой секции. |
| `source_text_replacement.py` | Пост-ASR замена фраз (regex, целые слова, CI): слияние встроенного JSON и пользовательских пар, применение к тексту. |
| `config_schema_export.py` | `python -m backend.core.config_schema_export` — публикует `backend/data/config.schema.json`. |
| `runtime_orchestrator.py` | Фасад рантайма (см. §6). |
| `subtitle_router.py` | Фасад публикации в overlay/WS + shim для legacy-импортов. |
| `subtitle_lifecycle_core.py` | FSM жизненного цикла субтитров, TTL/релевантность, promotion/expiry. |
| `subtitle_presentation.py` | Сборка payload: порядок, слоты стилей, слияние partial и финала. |
| `subtitle_style.py` | Style-presets, эффекты (`none`, `fade`, `subtle_pop`, `slide_up`, `zoom_in`, `blur_in`, `glow`). |
| `overlay_broadcaster.py` | Публикация overlay payload c sequence/created_at_ms. |
| `obs_caption_output.py` | OBS Closed Captions output (websocket к OBS). |
| `session_logger.py` | `SessionLogger` + `SessionLogManager` (best-effort JSONL запись клиентских событий). |
| `structured_runtime_logger.py` | `runtime-events.log` — структурированный рантайм-лог (компактные текстовые строки). |
| `structured_log_compact.py` | Сжатие значений (truncate строк, summary длинных списков, ограничение глубины). |
| `audio_capture.py`, `audio_devices.py`, `vad.py`, `segment_queue.py` | аудиоконвейер. |
| `asr_engine.py`, `asr_provider_selection.py`, `parakeet_provider.py` | локальный ASR layer. |
| `browser_asr_gateway.py` | Шлюз для browser worker: identity, generation, heartbeat, маршрутизация транскриптов. |
| `translation_engine.py` | Подготовка запросов перевода (по слотам), keep-alive `httpx.AsyncClient`, обёртка для readiness + retries. |
| `translation_dispatcher.py` | Очередь перевода: per-provider concurrency/rate limit, slot-aware identity, drop stale jobs. |
| `font_catalog.py` | `GET /project-fonts.css` — каталог локальных шрифтов. |
| `exporter.py` | Запись SRT/JSONL. |
| `profile_manager.py` | Профили (`user-data/profiles/`), нормализация payload, default profile. |
| `dictionary_manager.py` | Пользовательские словари. |
| `remote_mode.py`, `remote_session.py`, `remote_signaling.py`, `remote_diagnostics.py` | Remote controller/worker support (frozen surface). |

### 5.4 `backend/core/runtime/` — явные контроллеры рантайма

`RuntimeOrchestrator` делегирует логику в эти контроллеры; форма payload статуса не меняется при их перестановке.

| Контроллер | Назначение |
| --- | --- |
| `runtime_state_controller.py` | Coalescing/упорядочивание broadcast статуса рантайма (defensive против шторма duplicate updates). |
| `runtime_lifecycle_coordinator.py` | Детерминированный порядок start/stop ключевых компонентов. |
| `runtime_metrics_controller.py` | Учёт метрик рантайма (latency, ASR state, и т.п.). |
| `runtime_metrics_collector.py` | Сбор метрик. |
| `runtime_status_builder.py` | Сборка структуры статуса для WS/API. |
| `runtime_session_controller.py` | Идентичность сессии, sequence/generation, метки времени, записи экспорта. |
| `runtime_start_state_controller.py`, `runtime_stop_state_controller.py` | Узкие шаги жизненного цикла. |
| `runtime_reset_controller.py` | Согласованный reset перед каждым стартом. |
| `runtime_export_controller.py` | Попытка экспорта на stop + захват ошибок. |
| `segment_state_controller.py` | Счётчик сегментов, активный сегмент, partial coalescing. |
| `browser_worker_state_controller.py` | Состояние подключения/сессии/generation/signature browser worker-а. |
| `remote_audio_state_controller.py` | Удалённый аудио-ingest + queue lifecycle. |
| `speech_source.py`, `speech_source_factory.py` | Абстракция источника речи + фабрика. |
| `browser_speech_source.py`, `local_parakeet_speech_source.py`, `remote_controller_speech_source.py`, `remote_worker_speech_source.py` | Конкретные источники речи. |
| `speech_source_state_controller.py` | Выбор/очистка активного источника. |
| `audio_capture_controller.py` | Жизненный цикл `AudioCapture`. |
| `processing_tasks_controller.py` | Жизненный цикл capture/ASR тасков. |
| `asr_mode_controller.py` | Разрешение и фиксация режима/провайдера ASR на сессию. |
| `asr_runtime_controller.py`, `audio_runtime_controller.py` | Узкие helper-контроллеры рантайма. |
| `translation_runtime_controller.py` | Жизненный цикл `TranslationEngine` + `TranslationDispatcher`. |
| `translation_runtime_coordinator.py` | Кросс-координация перевода с рантаймом. |
| `transcript_controller.py` | Оркестрация конвейера partial/final: опционально применяет `source_text_replacement` до WS-транскрипта, `SubtitleRouter`, OBS source events и `TranslationRuntimeController.submit_final()`. |
| `subtitle_presentation_controller.py` | Тонкая обёртка над `SubtitleRouter`. |
| `output_fanout_controller.py`, `output_fanout_coordinator.py` | Fanout публикации в WS дашборда/OBS. |

### 5.5 `backend/config/` — конфигурация

```
backend/config/
├── __init__.py            # LocalConfigManager + AppSettings + global settings
├── defaults.py            # build_default_config(prefer_gpu)
├── secrets.py             # маскирование/нормализация секретов
└── normalizers/
    ├── asr.py             # asr.*, включая realtime и browser
    ├── browser.py         # asr.browser.* (worker_launch_browser etc.)
    ├── obs.py             # obs_closed_captions.*
    ├── remote.py          # remote.*
    ├── subtitles.py       # subtitle_output / subtitle_lifecycle
    ├── source_text_replacement.py  # source_text_replacement.* (пары, флаги)
    └── translation.py     # translation.lines, provider_settings, кэш, лимиты
```

`LocalConfigManager.load()/save()` гарантирует, что любой payload:

1. пройдёт через `migrate_config()` (`backend/core/config_migrations.py`);
2. пройдёт доменные normalizers + Pydantic validation (`ConfigSchema.model_validate`);
3. будет записан атомарно (Windows-safe `os.replace()`);
4. при невалидном JSON исходный файл уезжает в `config.json.corrupt-<timestamp>` и приложение поднимается на дефолтах.

`normalize_profile_payload()` используется для save/load профилей и для runtime-start snapshot.

### 5.6 `backend/schemas/` — Pydantic-схемы

| Файл | Назначение |
| --- | --- |
| `config_schema.py` | Полная схема конфига (`CURRENT_CONFIG_VERSION = 7`); `SourceTextReplacementConfig` и др. |
| `runtime_schema.py` | Runtime status payload (state, sequence, generation, метрики). |
| `asr_schema.py` | ASR-специфические события и поля. |
| `translation_schema.py` | Translation events/items. |
| `overlay_schema.py` | Overlay payload + presentation slots. |
| `diagnostics_schema.py` | Diagnostics payload (latency, queue state, и т.п.). |
| `model_schema.py` | Описание моделей/каталога. |

### 5.7 `backend/asr/parakeet/` — локальный ASR

```
backend/asr/parakeet/
├── runtime_loader.py          # загрузка/проверка окружения NeMo
├── model_installer.py         # загрузка EU multilingual Parakeet, URL, integrity
├── device_diagnostics.py
├── mock_provider.py
└── providers/                 # вспомогательные артефакты установки (по мере развития инсталлятора)
```

Основная логика инференса и двух режимов (`official_eu_parakeet` vs `official_eu_parakeet_low_latency`) сосредоточена в `backend/core/parakeet_provider.py` (см. §17).

### 5.8 `backend/translation/` — реестр + провайдеры

```
backend/translation/
├── base.py        # TranslationProviderInfo, BaseTranslationProvider, общий HTTP-слой
├── engine.py      # обёртки контракта engine
├── readiness.py   # readiness-проверки endpoint-ов
├── registry.py    # build_default_provider_registry()
└── providers/
    ├── google_v2.py
    ├── google_v3.py
    ├── google_gas.py
    ├── experimental_google_web.py   # GoogleWebProvider + FreeWebTranslateProvider
    ├── azure.py
    ├── deepl.py
    ├── libretranslate.py
    ├── openai_compatible.py         # используется для openai, openrouter, lm_studio, ollama
    └── public_mirrors.py
```

`backend/core/translation_engine.py` остаётся обёрткой подготовки запросов, общим `httpx.AsyncClient` с keep-alive и связыванием с `CacheManager`. Сами реализации провайдеров живут в `backend/translation/providers/`.

## 6. RuntimeOrchestrator: фасад и lifecycle

`RuntimeOrchestrator` (`backend/core/runtime_orchestrator.py`) теперь — фасад, который:

- хранит ссылки на контроллеры из `backend/core/runtime/`;
- предоставляет API `start(device_id, config_payload)`, `stop()`, `status()`, `obs_url()`;
- делегирует:
  - выбор/инициализацию `SpeechSource` через `SpeechSourceFactory`;
  - запуск/останов AudioCapture и processing tasks через соответствующие контроллеры;
  - конфигурацию `TranslationRuntimeController` (включая пересоздание `TranslationDispatcher` при изменении настроек);
  - публикацию статуса через `RuntimeStateController` (coalescing) + `OutputFanoutController`;
  - сборку payload статуса через `RuntimeStatusBuilder`;
  - lifecycle reset через `RuntimeResetController`/`Start/StopStateController`;
  - попытку экспорта на stop через `RuntimeExportController`.

Контракт `runtime_status` payload (упрощённо):

```
{
  "state": "stopped|listening|...",
  "asr_mode": "local|browser_google|browser_google_experimental",
  "asr_provider": "official_eu_parakeet_low_latency|...",
  "device_id": "...",
  "active_config_source": "loaded_from_disk|settings_saved|runtime_start_snapshot",
  "active_config_persisted": true|false,
  "active_config_hash": "...",
  "session_id": "...",
  "event_sequence": 1234,
  "metrics": { "latency_ms": ..., "queue": ..., ... },
  "browser_worker": { "session_id": ..., "generation_id": ..., "recognition_state": ..., ... },
  "translation": { "dispatch_state": ..., "providers": [...] },
  "subtitles": { ... }
}
```

## 7. Конфигурация и миграции

Главный config path: `user-data/config.json`.

### 7.1 `CURRENT_CONFIG_VERSION = 7`

Текущие явные миграции (`backend/core/config_migrations.py`):

| Стадия | Что делает |
| --- | --- |
| `migrate_ui_and_config_shape` (v<2) | Нормализует `ui.language`, гарантирует `translation.target_languages` из `targets`. |
| `migrate_parakeet_provider_name` (v<3) | `official_eu_parakeet_realtime` → `official_eu_parakeet_low_latency`. |
| `migrate_removed_legacy_asr_provider` (always) | Заменяет неподдерживаемые ASR провайдеры на `official_eu_parakeet_low_latency`, удаляет legacy ASR ключи. |
| `migrate_translation_lines_and_display_order` (v<6) | Строит `translation.lines` из `target_languages`, нормализует провайдеров, конвертирует `subtitle_output.display_order` из кодов языков в slot id (`translation_1..translation_5`). |

После версионных миграций выполняются доменные нормализаторы и Pydantic validation через `ConfigSchema`. Секция `source_text_replacement` не требует отдельного `if version < 7`: при отсутствии в старом JSON она появляется из `defaults.py` и `normalize_source_text_replacement_config()`.

### 7.2 Основные секции `ConfigSchema`

```
ConfigSchema
├── config_version: int (=7)
├── profile: str
├── ui: UiConfig
│   ├── language: "" | "en" | "ru"
│   ├── theme: "dark" | "light"
│   └── palette: { accent, accent_secondary, accent_tertiary }
├── source_lang: str
├── targets: list[str]                       # compat-зеркало enabled translation lines
├── asr: AsrConfig
│   ├── mode: "local" | "browser_google" | "browser_google_experimental"
│   ├── desktop_profile_lock: "" | "browser_speech"   # desktop quick start / Only Web; нормализатор держит mode=browser_google
│   ├── provider_preference: "official_eu_parakeet" | "official_eu_parakeet_low_latency"
│   ├── prefer_gpu, model_load_mode, model_revision, rnnoise_enabled, rnnoise_strength
│   ├── browser: AsrBrowserConfig
│   │   ├── recognition_language
│   │   ├── worker_launch_browser: "auto" | "google_chrome"
│   │   ├── interim_results, continuous_results
│   │   ├── force_finalization_enabled, force_finalization_timeout_ms
│   │   ├── minimum_reconnect_interval_ms, normal_restart_delay_ms,
│   │   │   no_speech_restart_delay_ms, network_reconnect_initial_ms, network_reconnect_max_ms,
│   │   │   stuck_stopping_timeout_ms
│   │   ├── max_browser_session_age_ms       (default 180000)
│   │   ├── prepare_cycle_before_ms          (default 15000)
│   │   ├── force_final_on_interruption, force_final_min_chars, force_final_min_stable_ms
│   │   └── experimental: { start_with_audio_track, fallback_to_default_start,
│   │                       keep_stream_alive, audio_track_constraints }
│   └── realtime: AsrRealtimeConfig (VAD/timings)
├── translation: TranslationConfig
│   ├── enabled, provider (default for new lines), target_languages (legacy compat)
│   ├── timeout_ms, queue_max_size, max_concurrent_jobs
│   ├── lines: list[TranslationLineConfig]
│   │   └── { slot_id (translation_1..5), enabled, target_lang, provider, label }
│   ├── provider_settings: TranslationProviderSettings
│   │   └── google_translate_v2 | google_cloud_translation_v3 | google_gas_url | google_web |
│   │       azure_translator | deepl | libretranslate |
│   │       openai | openrouter | lm_studio | ollama |
│   │       public_libretranslate_mirror | free_web_translate
│   ├── cache: { enabled, persist, max_entries (default 5000) }
│   └── provider_limits: dict[str, dict[str, Any]]
├── overlay: { preset: single|dual-line|stacked, compact }
├── obs_closed_captions:
│   ├── enabled, output_mode
│   ├── connection: { host, port, password }
│   ├── debug_mirror: { enabled, input_name, send_partials }
│   └── timing: { send_partials, partial_throttle_ms, min_partial_delta_chars,
│                final_replace_delay_ms, clear_after_ms, avoid_duplicate_text }
├── audio: { input_device_id }
├── remote: RemoteConfig
│   ├── enabled, role: disabled|controller|worker, session_id, pair_code
│   ├── lan: { bind_enabled, bind_host (default 0.0.0.0), port (default 8876) }
│   ├── controller: { worker_url, connect_timeout_ms, reconnect_delay_ms }
│   └── worker: { allow_unpaired, heartbeat_timeout_ms }
├── updates: UpdatesConfig
│   └── { enabled, provider: github_releases, github_repo, release_channel: stable|prerelease,
│         check_interval_hours, last_checked_utc, latest_known_version }
├── subtitle_output: { show_source, show_translations, max_translation_languages, display_order }
├── subtitle_style: dict (динамические пресеты/перекрытия слотов)
├── subtitle_lifecycle:
│   ├── completed_block_ttl_ms, completed_source_ttl_ms, completed_translation_ttl_ms
│   ├── pause_to_finalize_ms, hard_max_phrase_ms
│   └── allow_early_replace_on_next_final, sync_source_and_translation_expiry,
│       keep_completed_translation_during_active_partial
└── source_text_replacement:        # пост-ASR замена слов (до перевода и overlay)
    ├── enabled: bool               # по умолчанию false
    ├── include_builtin: bool       # JSON `backend/data/source_text_builtin_pairs.json`
    ├── case_insensitive: bool
    ├── whole_words: bool           # границы \w в regex (Unicode-aware)
    └── pairs: list[{ source, target }]  # до 100 пользовательских пар; перекрывают builtin по ключу
```

JSON Schema публикуется в `backend/data/config.schema.json` через `python -m backend.core.config_schema_export`.

### 7.3 Pipeline нормализации

1. `load()`:
   - читается JSON из `user-data/config.json` (если нет — создаётся дефолтный конфиг);
   - выполняется `migrate_config()`;
   - доменные normalizers приводят секции к безопасным дефолтам и диапазонам;
   - результат валидируется через `ConfigSchema` и (при необходимости) перезаписывается на диск.
2. `save()`:
   - входной payload проходит тот же pipeline;
   - на диск пишется уже нормализованный `ConfigSchema` (mode="json") атомарно.
3. `POST /api/runtime/start`:
   - dashboard может передать `config_payload` snapshot (даже несохранённый);
   - snapshot нормализуется и применяется только в памяти, помечается `active_config_source = runtime_start_snapshot`, `active_config_persisted = false`.
4. `POST /api/updates/check`:
   - сохраняет `updates.latest_known_version` + `updates.last_checked_utc` в `user-data/config.json`;
   - если активный конфиг — `runtime_start_snapshot`, обновлятся persisted-файл, а активный снимок только патчится в памяти.

### 7.4 Пост-ASR замена слов (`source_text_replacement`)

Назначение: **не меняя ASR**, подменить фрагменты распознанного текста до того, как он попадёт в субтитры, перевод и OBS captions.

Поток:

1. `VadEngine` / `SegmentQueue` / Parakeet (или browser worker) формируют «сырой» `TranscriptEvent`.
2. `TranscriptController.handle_event()` (`backend/core/runtime/transcript_controller.py`) получает `config_getter` и вызывает `apply_to_transcript_event()` из `backend/core/source_text_replacement.py`.
3. Во все downstream-вызовы уходит уже изменённый `text` и `segment.text` (если сегмент был).

Правила слияния пар:

- сначала пользовательские `pairs`, затем встроенные из JSON (если `include_builtin`), без дубликатов ключа (`casefold` при `case_insensitive`);
- применение по убыванию длины `source`, чтобы длинные фразы имели приоритет;
- замена через скомпилированный regex; строка замены передаётся через `lambda` в `re.sub`, чтобы символы `\` в тексте не интерпретировались как backreference.

UI: вкладка **Tools & Data** → блок «После распознавания», панель `frontend/js/panels/source-text-replacement-panel.js`: поля «слово / замена», «Добавить», список `pairs` с чекбоксами выбора и одна кнопка «Удалить выбранные»; актуальный конфиг для рантайма подхватывается после сохранения настроек (`POST /api/settings/save` → `app.state.config`).

Регрессии: `tests/test_source_text_replacement.py`, `tests/test_config_migrations.py` (наличие секции после миграции), `tests/test_browser_worker_contract.py` (разметка панели замены в `index.html`).

## 8. HTTP API (локальный)

| Метод | Маршрут | Назначение |
| --- | --- | --- |
| GET | `/api/health` | Health-чек, `diagnostics_service.health()` |
| POST | `/api/runtime/start` | Старт рантайма с опциональным `config_payload` |
| POST | `/api/runtime/stop` | Стоп рантайма |
| GET | `/api/runtime/status` | Текущий статус рантайма |
| GET | `/api/obs/url` | Overlay URL для OBS |
| GET | `/api/settings/load` | Чтение текущих настроек |
| POST | `/api/settings/save` | Сохранение настроек (через `LocalConfigManager.save()`) |
| GET | `/api/devices/audio-inputs` | Список доступных микрофонов |
| GET | `/api/version` | Версия + `sync` метаданные (latest known/last checked) |
| POST | `/api/updates/check` | Live polling GitHub Releases (опт-ин через `updates.enabled` + `github_repo`) |
| GET | `/api/profiles` | Список профилей |
| GET/POST/DELETE | `/api/profiles/{name}` | Операции с профилем |
| GET | `/api/exports` | Список экспортов |
| GET | `/api/exports/diagnostics` | Diagnostics ZIP (см. §10) |
| POST | `/api/logs/client-event` | Best-effort запись клиентского события |
| GET | `/api/openai/recommended-models` | Курируемый shortlist (без обращения к OpenAI API из браузера) |
| POST | `/api/openai/models` | Листинг моделей по предоставленному ключу |
| POST | `/api/openai/usable-models` | Лёгкая проба моделей через `/responses`, кэш 10 минут |

Remote endpoints:

- `/api/remote/state`
- `/api/remote/pair/create`
- `/api/remote/pair/verify`
- `/api/remote/heartbeat`
- `/api/remote/worker/settings/sync`
- `/api/remote/worker/runtime/start`
- `/api/remote/worker/runtime/stop`
- `/api/remote/worker/runtime/status`
- `/api/remote/worker/health`

Frontend pages (FastAPI static):

- `/`
- `/overlay`
- `/google-asr`
- `/google-asr-experimental`
- `/remote/controller-bridge`
- `/remote/worker-bridge`
- `/project-fonts.css` (динамический CSS-каталог локальных шрифтов)
- `/static/*`, `/overlay-assets/*`, `/project-fonts/*`

Все эти маршруты в desktop-режиме отдаются с заголовками `Cache-Control: no-store, no-cache, must-revalidate`, чтобы обычный refresh подхватывал правки без жёсткой перезагрузки.

### 8.1 События в `/ws/events`

Маршрут `/ws/events` принимает только heartbeat от клиентов и отправляет:

- `runtime_update` (на фронте нормализуется в `runtime_status`);
- `subtitle_payload_update` (на фронте нормализуется в `overlay_update`);
- `overlay_update` (payload для overlay-страницы с `created_at_ms`).

Каждое событие содержит monotonic `event_sequence`. Dashboard и overlay фильтруют stale события по `event_sequence`/`created_at_ms`, иначе после реконнекта могут «откатывать» текст.

При подключении клиент получает `hello` + `replay_last(...)` для перечисленных типов, чтобы UI поднимался актуальным.

## 9. WebSocket-поверхность

| Маршрут | Назначение |
| --- | --- |
| `/ws/events` | Главный канал событий для dashboard и overlay |
| `/ws/asr_worker` | Канал browser worker (`/google-asr*`) |
| `/ws/remote/signaling` | Сигналлинг между remote controller и worker |
| `/ws/remote/audio_ingest` | Передача аудио в worker |
| `/ws/remote/result_ingest` | Доставка транскриптов/переводов обратно в controller |

`backend/ws_manager.py`:

- снимок подключений (`list(self._connections)`) перед broadcast — итерация не держит lock на всём цикле;
- per-connection bounded `asyncio.Queue` (по умолчанию 128) + отдельная sender-task на сокет;
- при переполнении очереди — drop-oldest, счётчик `ws_events_dropped_oldest`;
- после `disconnect` сокет удаляется из `_out_queues` — повторный `_enqueue_to_connection` **no-op** (нет роста orphan-очередей);
- удаление мёртвых сокетов после `WebSocketDisconnect`, `RuntimeError`, `OSError`, `ConnectionResetError`, `BrokenPipeError`, `WinError 10022`;
- `_last_message_by_type` — глобальный кэш последнего payload по `type` (не удерживает ссылки на сокеты).

**`replay_last` (контракт):** отправляет последний кэшированный message per type **напрямую** в сокет, минуя per-connection queue. Это **best-effort snapshot bootstrap** при подключении; **может гоняться** с одновременным `broadcast`. **Нет гарантии FIFO** между replay и последующим live-потоком — клиент не должен предполагать строгий порядок без своей сериализации.

`/ws/asr_worker` использует `BrowserAsrService` + `BrowserAsrGateway` для подавления устаревших generation/session, типизации сообщений (`external_asr_update`, `browser_asr_status`, `browser_asr_heartbeat`) и экспонирования диагностики worker в статус рантайма. Детали backend observability — §11.4.

## 10. Логи, диагностика, экспорт

| Поток | Файл |
| --- | --- |
| Backend stdout/stderr | `logs/backend.log` (rotating) |
| Структурированные события рантайма | `logs/runtime-events.log` (через `StructuredRuntimeLogger`, поля сжимаются `structured_log_compact.compact_for_runtime_log`) |
| Клиентские live-события | `logs/session-latest.jsonl` (через `SessionLogger`, best-effort) |
| Desktop-launcher | `logs/desktop-launcher.log` |
| Bootstrap-launcher | `logs/bootstrap-launcher.log` |
| Browser worker | `logs/browser-recognition.log` |

`GET /api/exports/diagnostics` собирает локальный ZIP:

- `runtime_status.json`;
- `preflight_report.json`;
- `config_redacted.json` (через `redaction.redact_payload`);
- `latest_session.jsonl` (ограниченный по объёму client-event лог);
- `runtime-events.log`;
- `backend.log` (с редактированием по строкам);
- `environment.txt`;
- `diagnostics-manifest.json`.

Цель — пользователь может отправить архив для разбора проблем, не раскрывая ключи/токены/пароли.

## 11. Browser Speech: классический и experimental пути

### 11.1 Общая модель

- desktop-лаунчер всегда открывает worker в отдельном окне Google Chrome с адресной строкой и изолированным `--user-data-dir` (классический и experimental — разные профили);
- `asr.browser.worker_launch_browser` ∈ `{auto, google_chrome}`; в чисто веб-дашборде (без desktop-shell) этот переключатель скрыт, и `window.open` ведёт в браузер по умолчанию ОС;
- Chrome запускается с:
  - `HIGH_PRIORITY_CLASS`;
  - opt-out из `ProcessPowerThrottling` (`SetProcessInformation`, Windows 10/11);
  - `--disable-features=CalculateNativeWinOcclusion,HighEfficiencyModeAvailable,HeuristicMemorySaver,IntensiveWakeUpThrottling,GlobalMediaControls`;
  - `--disable-backgrounding-occluded-windows`, `--disable-renderer-backgrounding`, `--disable-background-timer-throttling`;
  - `--no-first-run`, `--no-default-browser-check`, `--disable-default-apps`, `--disable-session-crashed-bubble`;
- worker берёт `navigator.wakeLock.request("screen")` пока распознавание активно и окно видимо;
- `asr.browser.max_browser_session_age_ms` по умолчанию `180000` мс, окно `prepare_cycle_before_ms = 15000` мс — это даёт раннюю контролируемую ротацию сессии до Chrome-внутреннего ~4-минутного убийства Web Speech.

### 11.2 Supervisor FSM

`frontend/js/browser-asr-session-manager.js` владеет FSM распознавания:

- состояния: `idle`, `starting`, `running`, `stopping`, `restarting`, `backoff`, `fatal`;
- `start()` игнорируется/откладывается, если повторный `recognition.start()` небезопасен;
- `stop()` идемпотентен и учитывает generation;
- `onend` никогда не выполняет синхронный небезопасный перезапуск;
- cooldown reason-aware: `normal_onend`, `settings_change`, `websocket_reconnect`, `watchdog_stall`, `no_speech`, `network`;
- duplicate partial/final suppression + поздние принудительные финалы;
- network preflight (`https://www.google.com/generate_204`) после burst-порога `network` ошибок; при провале — терминальный `recognition_network_unreachable`;
- health-сигналы: `mic_silent`, `mic_track_unavailable`, `web_speech_stalled`, `document_hidden`, `websocket_disconnected`, новый `voice_below_recognition_threshold`.

### 11.3 Experimental путь

`/google-asr-experimental` использует `frontend/js/browser-asr-audio-track-session-manager.js`:

- открывается живой `MediaStreamTrack`;
- вызывается `SpeechRecognition.start(audioTrack)`;
- при отказе браузера — fallback на обычный `recognition.start()`;
- subclass синхронизирован с базовым FSM (общий `destroy()`/`pagehide` cleanup, общая диагностика).

`asr.browser.experimental.start_with_audio_track` контролирует использование experimental API; по умолчанию `true`.

### 11.4 Backend: Browser ASR observability (Domain A / L1–L5)

План реализации (внутренний): `docs/plans/browser_asr_observability_roadmap.md`. **Операционные контракты для кода и агентов — в этом документе и в `AGENTS.md`.**

**Trace scope:** Domain A (browser ASR path + явные hot-path точки), не distributed tracing всего pipeline. Domains **A** (operational ASR), **B** (revision lineage на сегменте), **C** (preview supersession) связаны только **reference links** (`asr_operational_event_id`, `translation_preview_lineage_key`), не единым causal graph.

**Время:**

- Семплинг heartbeat/detail в `BrowserAsrGateway` — **`MonotonicClock`** (`backend/core/timekeeping.py`), не wall clock.
- Поля `*_at_ms` от worker (`backend_received_at_ms`, `last_seen_at_ms`, client timestamps) — **только correlation/diagnostics**. **Не использовать** для stale detection, cooldown, suppression или ordering; ordering — session/generation/`worker_message_sequence` + monotonic ingress (`basr_mono_ingress_at`).

**Authoritative ownership (текущее):**

| Concern | Источник истины |
| --- | --- |
| Transport accept/reject (generation/session) | `BrowserAsrService` |
| Semantic ingress (overlap sequence, speech_source stale) | `BrowserSpeechSource` |
| Полный snapshot `BrowserAsrDiagnostics` | `BrowserAsrGateway` |
| Coalescing signature / broadcast runtime status | `BrowserWorkerStateController` |
| Operational phase (FSM) | `BrowserAsrOperationalFsm` — **projection** для observability/policy; **не** заменяет gateway для product diagnostics |
| Subtitle/translation relevance | `SubtitleRouter` + hooks диспетчера |

**Двойной gate session/generation** на transport и speech source — намеренное разделение границ; при изменении правил выравнивать оба слоя или вынести общий predicate-helper, иначе drift.

**Policy (`BrowserAsrRecoveryPolicy` + `BrowserAsrPolicyExecutor`):** логирует suggested → accepted/rejected. `SEND_CONTROL` **accepted** сейчас означает «probe transport разрешил», **не** «control message отправлена». Реальный IO — `BrowserAsrService.send_control` / orchestrator; policy остаётся **advisory**, не скрытым transport executor. Probe (`set_browser_asr_transport_probe` в bootstrap) — **совет**, не guarantee: transport может исчезнуть сразу после probe.

**JSONL replay (`backend/core/runtime/browser_asr_replay.py`):** opt-in `SST_BROWSER_ASR_RECORD_JSONL`; replay — **causal** (порядок событий + `advance_mono`), не полный **temporal** replay heartbeat/detail окон, пока stepped clock не прокинут во все потребители. Operational outcome (FSM phase, ingress rejects), не bit-identical runtime.

## 12. Перевод: lifecycle и инварианты

### 12.1 Идентичность слотов

- идентичность перевода в первую очередь по `slot_id` (`translation_1..5`), а не по `target_lang`;
- дубликаты целевых языков допускаются, если слоты разные;
- порядок overlay/отображения использует стабильные id слотов;
- настройки провайдера остаются глобальными в `translation.provider_settings`, каждый слот указывает, какой провайдер эти настройки использует.

### 12.2 TranslationDispatcher

- очередь slot-aware, drop stale jobs если их сегмент больше не релевантен;
- per-provider concurrency + rate limit (защита от «пачек»);
- restart-safe: `stop()` не «ломает» диспетчер для следующих сессий, `start()` сбрасывает внутреннее состояние остановки.

**Preview supersession (Domain C):** при `submit_final` ключ `TranslationPreviewLineage.lineage_key(segment_id, revision)` инкрементирует generation; устаревшие jobs не публикуются в router.

- **Pre-provider skip:** перед `translate_target` проверяются sequence relevance и preview supersession; при skip — **нет вызова API**, метрика `translation_provider_skipped_before_call`, событие `translation_provider_call_skipped`. Снижает amplification при быстрой речи; **не отменяет** уже запущенные in-flight provider calls.
- **После compute:** дополнительные проверки перед publish; superseded результат не уходит в `SubtitleRouter`.
- **Observability:** глобальные метрики диспетчера (`translation_last_provider`, latency и т.д.) могут всё ещё отражать работу, отброшенную **после** provider call. Не считать их идеальным control surface для throttling/auto-degrade до ужесточения «commit metrics only on accepted publish».

### 12.3 Lifecycle перевода (критический инвариант)

- previously finalized source и его translation остаются активными, пока новая фраза source ещё только partial;
- старый перевод может «догнать» позже, пока новый source ещё не финализирован;
- старый перевод заменяется только когда новая фраза source финализируется и реально входит в translation path;
- `subtitle_lifecycle.completed_source_ttl_ms` и `completed_translation_ttl_ms` контролируются раздельно (с опцией `sync_source_and_translation_expiry`);
- regression coverage: `tests/test_subtitle_router.py`, `tests/test_subtitle_lifecycle_relevance.py`, `tests/test_translation_dispatcher.py`.

### 12.4 CacheManager

`backend/core/cache_manager.py`:

- in-memory LRU с конфигурируемым `max_entries`;
- ключи: `provider_name::source_lang::target_lang::source_text` (либо без `provider_name` для legacy);
- дебаунс-флаш на диск через `threading.Timer` (по умолчанию 2.0s);
- `atexit` гарантирует финальный flush;
- битый `translation_cache.json` уезжает в backup `*.corrupt-<timestamp>.json` и заменяется на `{}`.

## 13. Стили субтитров

`backend/core/subtitle_style.py`:

- slot-based styling для `source` + `translation_1..translation_5`;
- встроенные пресеты: `clean_default`, `streamer_bold`, `dual_tone`, `compact_overlay`, `soft_shadow`, `jp_stream_single`, а также `accessibility_high_contrast`, `dark_cinema`, `meeting_soft`;
- effect ∈ `{none, fade, subtle_pop, slide_up, zoom_in, blur_in, glow}`;
- custom presets хранятся в `subtitle_style.custom_presets` и пересоздаются через UI;
- проектные шрифты подключаются через `/project-fonts.css` (`backend/core/font_catalog.py`).

## 14. Desktop runtime и release

Исходники `desktop/` и скрипты PyInstaller **не входят в публичный GitHub**; поведение desktop shell и lock задокументировано здесь и в tracked frontend/backend. Сборка exe — локально (§20).

### 14.1 Файлы (локальное дерево)

- `desktop/launcher.py` — основной desktop entrypoint:
  - pywebview splash с выбором startup-профиля (или `--web-speech-only` / `LaunchContext.web_speech_only` без панели профилей);
  - `_apply_startup_mode_to_config()` — пишет/снимает `asr.desktop_profile_lock` и `asr.mode` в `user-data/config.json`;
  - bootstrap локального runtime через `RuntimeBootstrapper`;
  - **открытие дашборда (`0.4.0`):** `_wait_for_http_ok` на `GET /`, затем `_navigate_to_dashboard()` — `window.location.replace` (fallback `load_url`); не вызывать `window.get_current_url()` из `loaded`-handler; после перехода `_splash_shell_active = false` и splash `evaluate_js` отключён; verify `/api/health` в фоне пишет только в `desktop-launcher.log`; `_schedule_dashboard_resize()` по таймеру;
  - `webview.start(..., storage_path=runtime_root/pywebview-profile)` — профиль Edge/WebView2 вне portable-папки exe;
  - запуск Chrome worker-окна (классический и experimental профили в разных `user-data-dir`);
  - HIGH_PRIORITY + opt-out из EcoQoS;
  - migration `user-data/logs/` → `logs/`.
- `desktop/bootstrap_launcher.py` — публичный `Stream Subtitle Translator.exe`:
  - тихая проверка GitHub Releases;
  - диалог Continue/Download при наличии обновления;
  - extract managed runtime в `app-runtime/`;
  - `--repair`/`--reset-runtime`/maintenance кнопки.
- `desktop/bootstrap_launcher_web_only.py` — публичный `Stream Subtitle Translator Only Web.exe` (всегда передаёт `--web-speech-only` во внутренний runtime).
- `desktop/runtime_bootstrap.py` — managed runtime + auto-detect install profile (CPU/NVIDIA).
- `desktop/bootstrap_payload.py`, `desktop/build_bootstrap_payload.py` — построение payload bootstrap-лаунчера.
- `Stream Subtitle Translator.spec`, `Stream Subtitle Translator Bootstrap.spec`, `Stream Subtitle Translator Bootstrap Web Only.spec` — PyInstaller spec.
- `build-desktop.bat`, `build-bootstrap-launcher.bat`, `build-bootstrap-launcher-web-only.bat`, `publish-desktop-releases.ps1`, `publish-desktop-releases-web-only.ps1` — packaging flow.

### 14.2 Профили desktop-лаунчера

- `Quick Start (Browser Speech)` — пропускает установку локального AI runtime; выставляет `asr.desktop_profile_lock = browser_speech` и `asr.mode = browser_google`;
- **Only Web exe** — тот же browser path без splash-выбора (фиксированный quick start + lock);
- `NVIDIA GPU (CUDA)` — поднимает локальный CUDA PyTorch стек;
- `CPU-only` — поднимает CPU-only PyTorch стек;
- `Remote Controller` — лёгкий старт, role=controller, без локального AI;
- `Remote Worker` — local AI + LAN bind включён, без Browser Speech на worker.

Поведение по умолчанию остаётся local-first; remote — явный профиль запуска.

### 14.3 Startup-скрипты

- `start.bat` — default local startup;
- `start-remote-controller.bat` — controller bootstrap (`SST_REMOTE_BOOTSTRAP=1`);
- `start-remote-worker.bat` — worker bootstrap с LAN bind;
- `backend/run.py` — общий runtime launcher с `--remote-role` и `--allow-lan`;
- `backend/run_controller.py`, `backend/run_worker.py` — обёртки.

## 15. Хранилище и пути

```
project-root/
├── user-data/
│   ├── config.json
│   ├── profiles/
│   ├── exports/
│   ├── models/
│   ├── cache/
│   │   └── translation_cache.json
│   ├── secrets/
│   └── debug/
├── logs/
│   ├── bootstrap-launcher.log
│   ├── desktop-launcher.log
│   ├── backend.log
│   ├── runtime-events.log
│   ├── session-latest.jsonl
│   └── browser-recognition.log
└── fonts/   (project-local font assets)
```

- bind-адрес по умолчанию — `127.0.0.1`;
- LAN bind включается только в профиле `Remote Worker`;
- bundled-схема + пример: `backend/data/config.schema.json`, `backend/data/config.example.json`;
- legacy `user-data/logs/` мигрируется в корневой `logs/` при старте лаунчера/рантайма.

## 16. Frontend (плоско, без build-step)

### 16.1 Dashboard

`frontend/index.html` → `frontend/js/main.js`:

- **Старт dashboard (`0.4.0`):** `main.js` монтирует панели сразу; `loadDashboardHelpContent()` — в фоне после mount; `DesktopBridge.getContext()` и `actions.loadInitialData()` — в фоне (не блокируют shell на `pywebviewready`). Модульная структура: `frontend/js/core/`, `frontend/js/shell/`, `frontend/js/dashboard/actions/`, `frontend/js/panels/`, `frontend/partials/dashboard-help-topics.html`.
- **Компактный layout (`0.4.0`):** `ui.layout` ∈ `{standard, compact}`; `frontend/css/compact-layout.css`, `frontend/js/layout/layout-controller.js` (icon rail, sticky chrome); desktop shell ресайзит окно при смене layout (standard ~1440×940, compact ~400×844).
- `frontend/js/i18n.js` — словари (ru/en);
- `frontend/js/desktop.js` — bridge web ↔ pywebview: `getContext()` возвращает `immediateDesktopContext()` без API; `scheduleContextRefresh()` догружает `get_launch_context` и шлёт `sst:desktop-context`;
- `frontend/js/dashboard/desktop-profile-lock.js` — lock Local Parakeet (`syncRecognitionModeSelectLock` удаляет `<option value="local">`);
- `frontend/js/state.js`, `frontend/js/app.js`, `frontend/js/api.js`, `frontend/js/ws.js` — legacy compat (постепенно вытесняются `core/`);
- `frontend/js/core/`:
  - `store.js`, `api-client.js`, `ws-client.js`, `events.js`, `redaction.js`;
- `frontend/js/dashboard/`:
  - `actions.js`, `helpers.js`, `logging.js`, `constants.js`;
- `frontend/js/panels/`:
  - `runtime-panel.js`, `asr-panel.js`, `translation-panel.js`, `overlay-panel.js`,
  - `diagnostics-panel.js`, `obs-captions-panel.js`, `style-editor-panel.js`,
  - `profiles-panel.js`, `remote-panel.js`, `model-manager-panel.js`, `source-text-replacement-panel.js`;
- `frontend/js/normalizers/`:
  - `config-normalizer.js`, `runtime-normalizer.js`, `diagnostics-normalizer.js`,
  - `translation-normalizer.js`, `overlay-normalizer.js`, `model-normalizer.js`;
- `frontend/js/subtitle-style.js`, `frontend/js/ui-theme.js` — applies UI theme/palette к dashboard и Browser Speech windows.

### 16.2 Browser worker

- `frontend/google_asr.html` + `frontend/js/browser-asr-session-manager.js`;
- `frontend/google_asr_experimental.html` + `frontend/js/browser-asr-audio-track-session-manager.js`.

### 16.3 Remote bridge pages

- `frontend/remote_controller_bridge.html` + `frontend/js/remote-controller-bridge.js`;
- `frontend/remote_worker_bridge.html` + `frontend/js/remote-worker-bridge.js`;
- `frontend/js/remote-worker-audio-worklet.js`.

### 16.4 Overlay

- `overlay/overlay.html` + `overlay/overlay.css` + `overlay/overlay.js` (для OBS Browser Source).

### 16.5 Текущее состояние UX (dashboard)

- вкладка Translation — стабильные карточки слотов `translation_1..translation_5` (рисуются только для явно добавленных линий);
- редактор настроек провайдера следует выбранному слоту, можно переключать вручную;
- для OpenAI/совместимых провайдеров поле `model` заполняется через helper endpoint;
- вкладка Style — тема (светлая/тёмная) и палитра акцентного градиента;
- эффекты появления: `none`, `fade`, `subtle_pop`, `slide_up`, `zoom_in`, `blur_in`, `glow`;
- после `Tools & Data` — вкладка `Help / Помощь` с локальными topic-tabs;
- в тюнинге — «ощущающие» ползунки, точные тайминги/гейты ASR — в `Tools & Data`;
- статус `experimental` для экспериментальных провайдеров перевода остаётся `experimental` (не `degraded`);
- смена языка UI сохраняется сразу.

## 17. Локальный ASR: NVIDIA Parakeet и выбор провайдера

### 17.1 Поверхность режимов

| `asr.mode` | Захват на backend | ASR-движок |
| --- | --- | --- |
| `local` | Да (`sounddevice` через `AudioCaptureController`) | Parakeet (см. ниже) |
| `browser_google` / `browser_google_experimental` | Нет (микрофон в окне Chrome worker) | Google Web Speech → `BrowserAsrGateway` |

Иные backend ASR провайдеры удалены; при устаревшем `provider_preference` срабатывает миграция на Parakeet low-latency.

### 17.2 Пайплайн «микрофон → текст» (local)

```mermaid
flowchart TD
  AC[AudioCapture 16 kHz mono int16] --> RN{RNNoise optional}
  RN --> VAD[VadEngine webrtcvad 30 ms frames]
  VAD --> SQ[SegmentQueue AsrWorkItem partial/final]
  SQ --> ASR[_asr_loop to_thread Parakeet transcribe]
  ASR --> TC[TranscriptController + post-ASR filter]
  TC --> OUT[SubtitleRouter Translation WS OBS]
```

1. **`AudioCapture`** (`backend/core/audio_capture.py`) отдаёт сырые PCM-чанки заданного размера.
2. **`RNNoiseRecognitionProcessor`** (`runtime_orchestrator` включает по `asr.rnnoise_enabled`, сила `asr.rnnoise_strength`) — опциональное смешивание denoise и ресэмпл при необходимости; в browser-режиме RNNoise отключён диагностически.
3. **`VadEngine`** (`backend/core/vad.py`):
   - библиотека `webrtcvad`, кадр **30 ms**, режим чувствительности `vad_mode` 0..3 из `asr.realtime`;
   - параметры тайминга: `silence_hold_ms`, `finalization_hold_ms`, `min_speech_ms`, `partial_emit_interval_ms`, `max_segment_ms`;
   - опциональный энергетический gate: `energy_gate_enabled`, `min_rms_for_recognition`, `min_voiced_ratio`;
   - до **первого** partial применяется адаптивный RMS-порог от медианы «фоновых» кадров, чтобы комнатный шум в режимах 0/1 не превращался в ложную речь.
4. **`SegmentQueue`** (`backend/core/segment_queue.py`): потокобезопасная очередь с коалесcing partial по `segment_id`, лимитом `maxsize`, подсчётом dropped/coalesced; **final** заявки выбираются раньше старых partial, чтобы финал не застревал в хвосте.
5. **`RuntimeOrchestrator._asr_loop`**: забирает `AsrWorkItem`, отбрасывает устаревшие по `generation`, вызывает `provider.transcribe` в `asyncio.to_thread`.
6. **`TranscriptController`**: публикует транскрипт и кормит субтитры/перевод (см. §7.4 для пост-обработки текста).

### 17.3 Две реализации Parakeet (`backend/core/parakeet_provider.py`)

Обе наследуют `BaseOfficialEuParakeetNemoProvider` (загрузка `nemo.collections.asr.models.ASRModel`, CUDA→CPU fallback, диагностика Torch).

**A. `OfficialEuParakeetProvider` — `official_eu_parakeet` («качество»)**

- Метод `transcribe` **возвращает пустой результат для partial** (`is_final=False`): live-гипотезы на уровне NeMo для этого режима не стримятся.
- Для **final** сегмента VAD записывает PCM во временный WAV и вызывает `model.transcribe([path], batch_size=1)` — один проход декодера на целую высказанную фразу.

**B. `OfficialEuParakeetRealtimeProvider` — `official_eu_parakeet_low_latency` (по умолчанию)**

- Держит per-`segment_id` состояние `_StreamingSegmentState` (буфер NeMo `ContextSize`, `decoder_state`, накопленные гипотезы).
- На каждом аудио-куске вызывает encoder + `decoding_computer` (RNNT greedy batch, `loop_labels=True`).
- Окна декодирования: из `asr.realtime.chunk_window_ms` / `chunk_overlap_ms`; если оба 0 — вычисляются от `partial_emit_interval_ms` (`_resolved_streaming_window_ms`, `_resolved_partial_decode_window_ms`), чтобы сохранить низкую задержку без ручной настройки.
- Поддерживает **partial и final** гипотезы; `capabilities.supports_partials=True`.

**Модель и диск**

- Файл и репозиторий константы в `model_installer.py` (`OFFICIAL_EU_PARAKEET_*`).
- Режим загрузки `asr.model_load_mode`: `auto` | `local_nemo` | `from_pretrained`.
- Целостность локального файла: `official_eu_parakeet_integrity_state()` — при `corrupt` провайдер поднимает `AsrProviderError` с понятным сообщением.

### 17.4 Связь таймингов VAD и субтитров

`LocalConfigManager` после нормализации принудительно выставляет:

- `asr.realtime.finalization_hold_ms = subtitle_lifecycle.pause_to_finalize_ms`
- `asr.realtime.max_segment_ms = subtitle_lifecycle.hard_max_phrase_ms`

Так пользовательские ползунки «сколько ждать финал фразы» и «жёсткий потолок длины фразы» остаются согласованными между движком VAD и жизненным циклом субтитров.

### 17.5 Browser Speech (сводка)

Детально — §11 (frontend FSM) и §11.4 (backend observability). Транскрипты поступают как `TranscriptEvent` с уже заполненным текстом; дальнейший путь через `TranscriptController` совпадает с локальным ASR (включая §7.4). Preview lineage на финале — §12.2.

## 18. Remote mode (frozen surface)

Remote-режим подключается только явным выбором пользователя (opt-in).

Артефакты controller/worker сохранены и не удалены:

- `backend/api/routes_remote.py`;
- `backend/core/remote_mode.py`, `remote_session.py`, `remote_signaling.py`, `remote_diagnostics.py`;
- `backend/run_controller.py`, `backend/run_worker.py`;
- `frontend/js/remote.js`, `remote-controller-bridge.js`, `remote-worker-bridge.js`, `remote-worker-audio-worklet.js`;
- `frontend/remote_controller_bridge.html`, `frontend/remote_worker_bridge.html`;
- `start-remote-controller.bat`, `start-remote-worker.bat`, `requirements.controller.txt`.

Ограничения:

- remote worker не должен работать в режиме browser speech;
- синхронизация remote worker закрепляет локальный AI-путь, не допуская ухода в провайдеры browser worker.

Порядок действий оператора:

1. Запустить worker (`Remote Worker` или `start-remote-worker.bat`).
2. Запустить controller (`Remote Controller` или `start-remote-controller.bat`).
3. На controller задать `Worker Base URL` и выполнить `Check Worker Health`.
4. Создать/проверить pairing, обновить remote state.
5. Выполнить синхронизацию настроек worker перед подготовкой запуска.
6. Подготовить удалённый запуск, запустить/проверить runtime worker, держать bridge-окна открытыми.
7. Запустить рантайм дашборда controller для захвата микрофона и потока удалённых аудио/результатов.

## 19. Версионирование и проверка обновлений

- `backend/versioning.py::PROJECT_VERSION = "0.4.0"` — single source of truth.
- `GET /api/version` отдаёт текущую версию + `sync` метаданные (`provider`, `enabled`, `github_repo`, `release_channel`, `latest_known_version`, `last_checked_utc`, `update_available`, `check_supported`, `message`).
- `POST /api/updates/check` (через `UpdateService`):
  - проверяет `updates.enabled` и наличие `github_repo`;
  - polling `https://api.github.com/repos/{repo}/releases?per_page=20`;
  - выбирает latest stable/prerelease по `release_channel`;
  - сохраняет `updates.latest_known_version` и `updates.last_checked_utc`;
  - не перетирает `runtime_start_snapshot` (мерджит только updates-метаданные в persisted-payload).
- bootstrap-лаунчер на старте тихо опрашивает GitHub Releases и показывает диалог только при наличии обновления (Continue / Download).

## 20. Тестирование

`tests/` — Python `unittest`, Windows-safe, без Node/browser-build инфраструктуры. Полный прогон:

```
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

Текущий результат для `0.4.0` (публичный tracked suite на GitHub):

- **336** tests локально (полное дерево с `desktop/`);
- на GitHub без `desktop/` — меньше тестов, без desktop-only модулей;
- в репозитории обязательно: `tests/test_browser_asr_observability.py` и связанные ws/translation/browser contracts.

Команда для CI/клона GitHub:

```
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

Расширенная верификация **только в локальном dev-дереве** (есть `desktop/`):

- `python -m compileall backend desktop tests`
- `cmd /c build-desktop.bat`, `build-bootstrap-launcher.bat`, `build-bootstrap-launcher-web-only.bat`
- `publish-desktop-releases.ps1`, `publish-desktop-releases-web-only.ps1`
- desktop-only: `test_launcher.py`, `test_bootstrap_launcher.py`, `test_bootstrap_payload.py`, `test_runtime_bootstrap.py`, `test_desktop_profile_lock.py`, `test_desktop_launcher_startup.py`
- packaged release folders: `dist/desktop-releases/v0.4.0/` (`01-bootstrap-onefile/`, `01-bootstrap-web-only-onefile/`, `02-managed-app-onefolder/`, `03-installers-both/`)

Покрытие фокусируется на:

- архитектуре backend и path-контрактах (`test_backend_architecture.py`, `test_paths_release_contracts.py`);
- миграциях и экспорте схемы конфига (`test_config_migrations.py`, `test_config_schema_export.py`);
- контрактах browser worker, шлюза и observability (`test_browser_worker_contract.py`, `test_browser_asr_gateway.py`, `test_browser_asr_service.py`, `test_browser_asr_observability.py`);
- рантайм-контроллерах (`test_runtime_metrics_controller.py`, `test_runtime_session_controller.py`, `test_segment_state_controller.py`, `test_browser_worker_state_controller.py`, `test_runtime_lifecycle_coordinator.py`, `test_runtime_non_remote_controllers.py`, `test_runtime_event_coalescing.py`, `test_runtime_event_sequence_monotonic.py`);
- subtitle lifecycle и роутере (`test_subtitle_router.py`, `test_subtitle_lifecycle_relevance.py`, `test_subtitle_style_effects.py`);
- очереди перевода и провайдерах (`test_translation_dispatcher.py`, `test_translation_engine.py`, `test_openai_compatible_provider.py`, `test_config_translation_providers.py`, `test_cache_manager.py`);
- update-сервисе (`test_update_service_check_now.py`, `test_update_service_persistence.py`);
- OpenAI helper endpoints (`test_openai_models_route.py`);
- логировании и сессии (`test_logging_and_session.py`, `test_structured_log_compact.py`, `test_structured_runtime_logger.py`, `test_session_logger.py`);
- API/WebSocket (`test_api_and_websockets.py`, `test_ws_manager.py`, `test_runtime_status_contract.py`);
- ASR-провайдере и параметрах (`test_asr_provider_contract.py`, `test_asr_provider_selection.py`, `test_parakeet_lifecycle.py`, `test_parakeet_model_installer_manifest.py`, `test_vad_engine.py`, `test_segment_queue.py`, `test_rnnoise_processor.py`, `test_source_text_replacement.py`).

Лаунчер/bootstrap (`test_launcher.py`, `test_bootstrap_*.py`, `test_desktop_profile_lock.py`) — только при наличии локального `desktop/`.

## 21. Продуктовые инварианты, сохранённые в 0.4.0

- запуск desktop по умолчанию остаётся local-first;
- Browser Speech по-прежнему доступен (`browser_google`, `browser_google_experimental`);
- локальный Parakeet остаётся доступным;
- визуальная вёрстка дашборда не заменена мастером или новым UI-стеком;
- overlay остаётся отдельной лёгкой страницей для OBS;
- не введён стек Node.js/bundler/frontend framework;
- remote surface — explicit LAN-only исключение и заморожен (frozen).
