# Журнал изменений SST Desktop

Единая история изменений desktop-версии.

Этот файл — канонический changelog для релизов SST Desktop. Версионные release notes в `docs/DESKTOP_RELEASE_CHANGELOG_*.md` остаются как delta-документы по конкретным релизам, но основной историей изменений считается этот файл.

## Unreleased

Изменений после релиза `0.4.0` в этом журнале пока нет.

## 0.4.0

### Версия

- `backend/versioning.py`: `PROJECT_VERSION = "0.4.0"` (источник правды для `GET /api/version` и проверки обновлений).
- `config_version` **не менялся** (остаётся `7`); публичные HTTP-маршруты и контракт субтитров/overlay сохранены.

### Browser ASR observability (backend)

- Новые модули: `backend/core/timekeeping.py` (`MonotonicClock`), `backend/core/runtime/browser_asr_observability.py`, `browser_asr_trace.py`, `browser_asr_normalized_event.py`, `browser_asr_operational_fsm.py`, `browser_asr_recovery_policy.py`, `browser_asr_replay.py`, `translation_preview_lineage.py`.
- Интеграция в `browser_asr_service.py`, `browser_speech_source.py`, `runtime_orchestrator.py`, `browser_asr_gateway.py`, `app_bootstrap.py`.
- L2 ingress: отсев stale transport / speech_source, overlap, структурированные reject-логи с `basr_event_id` / `basr_causal_parent_id`.
- L4 operational FSM + recovery policy (advisory actions, audit accepted/rejected).
- L6 JSONL recorder + operational replay (`tests/fixtures/browser_asr_replay_min.jsonl`, `tests/test_browser_asr_observability.py`).
- Опциональные trace/lineage поля на `TranscriptSegment` (`backend/models.py`).

### WebSocket и перевод

- `backend/ws_manager.py`: bounded per-connection queues, drop-oldest; `replay_last` в обход очереди (см. `docs/TECHNICAL_ARCHITECTURE.md` §9).
- `backend/core/translation_dispatcher.py`: preview supersession (pre-provider skip + отброс устаревшего результата после вычисления); метрика `translation_provider_skipped_before_call`.

### Desktop: Web Speech-only bootstrap (отдельный exe)

- **`Stream Subtitle Translator Only Web.exe`** — one-file bootstrap без выбора профиля на splash; сразу Web Speech quick start (`--web-speech-only`).
- `desktop/bootstrap_launcher_web_only.py`, `Stream Subtitle Translator Bootstrap Web Only.spec`.
- Сборка: `build-bootstrap-launcher-web-only.bat` → `dist\bootstrap-launcher-web-only\`.
- Публикация: `publish-desktop-releases-web-only.ps1` (копирует Only Web exe в те же release-папки, что и стандартный launcher).
- `desktop/launcher.py`: `web_speech_only`, пропуск ожидания выбора профиля; компактный splash (`SPLASH_WINDOW_WEB_ONLY` в `desktop/splash_screen.py`).

### Desktop: блокировка Local Parakeet в Browser Speech quick start

- **`asr.desktop_profile_lock`** (`""` | `"browser_speech"`) в `backend/schemas/config_schema.py` — сохраняется через `ConfigSchema` / `LocalConfigManager`.
- Launcher при **Quick Start (Web Speech)** и **Only Web** пишет lock + `asr.mode: browser_google`; при **NVIDIA GPU** / **CPU-only** снимает lock и возвращает `asr.mode: local`.
- `backend/config/normalizers/asr.py`, `frontend/js/dashboard/desktop-profile-lock.js`, `asr-panel.js`, `actions.js`, `config-normalizer.js`.

### Desktop: неблокирующий старт dashboard

- `frontend/js/main.js` — панели сразу; `getContext()` и `loadInitialData()` в фоне.
- `frontend/js/desktop.js` — `immediateDesktopContext()`, `scheduleContextRefresh()`; без блокировки UI на `pywebviewready`.

### Исправления

- Восстановлен публичный `RuntimeOrchestrator.browser_asr_worker_connected()` (регрессия ломала WebSocket worker сразу после connect).
- Регрессии: `tests/test_browser_asr_service.py`, `tests/test_ws_manager.py`, `tests/test_translation_dispatcher.py`, `tests/test_api_and_websockets.py`.
- Desktop profile lock и UI boot: `tests/test_desktop_profile_lock.py`; расширены `tests/test_launcher.py`, `tests/test_browser_worker_contract.py`.

### Документация

- `docs/TECHNICAL_ARCHITECTURE.md`: §9 WebSocket/replay, §11.4 browser ASR observability, §12.2 preview supersession, §14–16 desktop (Only Web, profile lock, dashboard boot).
- `AGENTS.md`: observability, preview supersession, desktop profile lock и packaging.
- `README.md` / `README.ru.md`, `docs/DESKTOP_RELEASE_CHANGELOG_0.4.0.md`, `backend/data/config.example.json`.

### Тесты

- Полный прогон: `python -m unittest discover -s tests` — **336** тестов, `OK`.

## 0.3.2

### Версия и конфигурация

- `backend/versioning.py`: `PROJECT_VERSION = "0.3.2"` (источник правды для `GET /api/version` и проверки обновлений).
- `backend/schemas/config_schema.py`: `CURRENT_CONFIG_VERSION = 7`.
- Новая секция конфига `source_text_replacement`: опциональная пост-ASR замена слов/фраз до перевода, субтитров и OBS captions; не влияет на распознавание.
- `backend/data/source_text_builtin_pairs.json`: стартовый список пар (английский + русский), заменяемый/дополняемый пользовательскими парами в UI.
- `backend/core/source_text_replacement.py`, `backend/config/normalizers/source_text_replacement.py`, правки `LocalConfigManager`, `TranscriptController`, `runtime_orchestrator`.
- `backend/data/config.example.json`: версия `7` и блок `source_text_replacement`.
- Регрессии: `tests/test_source_text_replacement.py`, расширены `tests/test_config_migrations.py`, `tests/test_runtime_status_contract.py`.

### Dashboard и i18n

- `frontend/index.html`, `frontend/js/panels/source-text-replacement-panel.js`, `frontend/js/main.js`, `frontend/js/normalizers/config-normalizer.js`, `frontend/js/i18n.js`, `frontend/css/app.css`: вкладка **Инструменты и данные** — блок «После распознавания / замена слов» (вкл/выкл, встроенный список, регистр, целые слова; свои пары: два поля «слово» и «замена», кнопка «Добавить», список с выбором чекбоксами и одна кнопка «Удалить выбранные»; для применения к запущенному backend — глобальное **Сохранить**).
- Справка Help: уточнён текст `help.tools.body` (EN/RU) про пост-ASR слой.

### Web Speech worker (браузер)

- `frontend/js/browser-web-speech-recognition-policy.js`: политика overlap-сессий (по умолчанию при `continuous=false`) и утилиты для будущих on-device/phrase hints.
- `frontend/js/browser-asr-session-manager.js`: двойной экземпляр `SpeechRecognition` с предстартом «buddy» после финала (снижение разрыва между сессиями Chrome); мягкий повтор при `phrases-not-supported` и одна попытка после `language-not-supported` со сбросом Chrome on-device hints; игнорирование шумного `aborted` на активном слоте при уже запущенном buddy.

### Субтитры и OBS

- `backend/core/subtitle_style.py`: пресеты `accessibility_high_contrast`, `dark_cinema`, `meeting_soft` (ориентиры: доступность, тёмная сцена, спокойный «встречный» вид).
- `backend/core/obs_caption_output.py`, правки стиля/версионирования по мере выравнивания релиза (см. git-историю ветки).

### Документация

- `docs/TECHNICAL_ARCHITECTURE.md`: актуализация под `0.3.2`, `config_version` 7, поток `source_text_replacement`, **расширенный раздел про локальный NVIDIA Parakeet** (VAD, очередь сегментов, RNNoise, два провайдера quality vs low-latency, связь с `subtitle_lifecycle`).
- `README.md` / `README.ru.md`: версия `0.3.2`, ссылка на `docs/DESKTOP_RELEASE_CHANGELOG_0.3.2.md`.
- `docs/DESKTOP_RELEASE_CHANGELOG_0.3.2.md`: delta release notes для установленных папок релиза.

### Тесты

- Полный прогон: `python -m unittest discover -s tests` — **298** тестов, `OK` (на момент фиксации релиза).

## 0.3.1

Релиз `0.3.1` — это стабилизация поверх уже выпущенного `0.3.0`. Архитектурные изменения (`RuntimeOrchestrator` → контроллеры, разделение `SubtitleRouter`, пакет `backend/translation/` с пакетом `providers/`, `cache_manager`, `atomic_io`, `ConfigStateService`, `POST /api/updates/check`, OpenAI helper endpoints, карточки `translation_1..translation_5`, тема/палитра UI, вкладка Help, supervisor Web Speech, запуск worker'а Google Chrome в отдельном окне с изолированным профилем) **уже входили в `0.3.0`** и здесь не дублируются. Базовый local-first продукт и публичные `/api`/WebSocket-контракты не меняются.

### Версия и идентификация

- `backend/versioning.py`: `PROJECT_VERSION = "0.3.1"`, источник правды для `GET /api/version` и `POST /api/updates/check`.
- bootstrap-лаунчер и desktop-shell поднимают эту же версию.

### Bootstrap-лаунчер

- В репозитории впервые отслеживаются `desktop/bootstrap_launcher.py` и `desktop/bootstrap_payload.py` (раньше существовали локально, но не были зафиксированы в git).
- Проверка обновлений в bootstrap игнорирует `v2.x` теги, когда встроенная версия — `0.x`: старые `v2.8.x` релизы больше не показываются как «новее `0.3.x`». Регрессия — `tests/test_bootstrap_release_tag_filter.py`.

### Web Speech: дополнительная защита Windows-окна Chrome worker'а

Поверх изоляции профиля и запуска в отдельном окне Google Chrome, которые уже были в `0.3.0`:

- worker-окно Chrome запускается с `HIGH_PRIORITY_CLASS`;
- на Windows 10/11 worker-процесс делает opt-out из EcoQoS / Efficiency Mode через `SetProcessInformation` + `ProcessPowerThrottling`;
- Chrome feature gates `CalculateNativeWinOcclusion`, `HighEfficiencyModeAvailable`, `HeuristicMemorySaver`, `IntensiveWakeUpThrottling`, `GlobalMediaControls` отключаются, чтобы Web Speech не «засыпал» при перекрытии окна.

### Web Speech: защита распознавания внутри worker'а

`frontend/js/browser-asr-session-manager.js`:

- `navigator.wakeLock.request("screen")` пока распознавание активно и окно видимо; lock автоматически переснимается после visibility-flip и отпускается на Stop;
- network preflight: после трёх ошибок `network` за ~12 c worker пробует `https://www.google.com/generate_204`; при провале supervisor уходит в терминальный `recognition_network_unreachable` вместо бесконечного цикла рестартов;
- health-сигнал `voice_below_recognition_threshold` (RMS ≥ 0.025, накопленные `no-speech`, тишина распознавания ≥ 8 c);
- ранняя контролируемая ротация сессии: `asr.browser.max_browser_session_age_ms` по умолчанию `180000` мс (раньше `240000`), окно `prepare_cycle_before_ms` остаётся `15000` мс.

### Кеш перевода и очередь перевода

- `backend/core/cache_manager.py` переписан на in-memory LRU с дебаунс-персистом на диск (раньше — блокирующая запись на каждый ход из asyncio-пути), карантин повреждённого файла кеша сохранён.
- `TranslationDispatcher` стал перезапускаемым (`stop()` больше не «ломает» диспетчер для следующих сессий), добавлено ограничение параллелизма по провайдеру и базовый rate limiting, параллелизм по целевым языкам сохраняется.

### Логи

- `backend/core/structured_log_compact.py` — новый helper для сжатия структурированных рантайм-логов (truncate длинных строк, summary длинных списков, ограничение глубины), подключён в `structured_runtime_logger`.

### UX и стили

- встроенные эффекты появления субтитров пополнились на `slide_up`, `zoom_in`, `blur_in`, `glow` (рядом с уже существовавшими `none`, `fade`, `subtle_pop`).
- мелкие правки frontend-панелей: translation panel и slot cards стали аккуратнее в крайних случаях, расширены строки i18n, точечные доработки ASR/runtime/style-панелей.

### Документация

- `docs/CHANGELOG.md` и `docs/TECHNICAL_ARCHITECTURE.md` приведены к единому русскому изложению.
- `docs/DESKTOP_RELEASE_CHANGELOG_0.3.0.md` заменён на `docs/DESKTOP_RELEASE_CHANGELOG_0.3.1.md`; в новом файле явно отделено «реально новое в 0.3.1» от «уже было в 0.3.0».

### Что было уже в 0.3.0 и не считается новым в 0.3.1

- Декомпозиция `RuntimeOrchestrator` на контроллеры под `backend/core/runtime/` (state/metrics/session/segment/lifecycle/browser-worker/speech sources/audio capture/processing tasks/translation runtime/transcript/output fanout).
- Разделение `SubtitleRouter` на `subtitle_lifecycle_core.py` + `subtitle_presentation.py` + фасад.
- Пакет `backend/translation/` (`base.py`, `engine.py`, `readiness.py`, `registry.py`) и пакет провайдеров `providers/*`.
- `backend/core/atomic_io.py` и атомарная запись config/profiles.
- `backend/services/config_state_service.py` (`ConfigStateService` с явной блокировкой и метаданными активного снимка конфига).
- `backend/services/update_service.py` + `POST /api/updates/check` + защита `runtime_start_snapshot` от записи метаданных обновлений.
- OpenAI helper endpoints `GET /api/openai/recommended-models`, `POST /api/openai/models`, `POST /api/openai/usable-models`.
- Карточки `translation_1..translation_5`, `TranslationLineConfig`, миграция `subtitle_output.display_order` в id слотов перевода.
- Web Speech worker в Google Chrome в отдельном окне с адресной строкой и изолированным `--user-data-dir`, `asr.browser.worker_launch_browser` со значениями `auto`/`google_chrome`.
- Web Speech supervisor (`browser-asr-session-manager.js`), experimental `/google-asr-experimental`, тема/палитра UI, вкладка Help, расширенный i18n, runtime-event coalescing и стабильность `/ws/events` / `/ws/asr_worker`.
- `GET /api/exports/diagnostics` (ZIP с runtime/config/log/session-данными) и best-effort `/api/logs/client-event`.

### Тесты и верификация

- `python -m compileall backend desktop tests`
- `.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"`

Результат:

- `283 tests`
- `OK`

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
