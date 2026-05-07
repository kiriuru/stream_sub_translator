# SST Desktop 0.3.0

SST Desktop — локальное Windows-приложение для распознавания речи в реальном времени, опционального перевода, маршрутизации субтитров и вывода в OBS.

Этот README описывает текущий desktop product surface для линии `0.3.0`, включая изменения из текущей ветки `main`, которые ещё не оформлены как отдельный релиз.

## Язык

- English version: [README.md](./README.md)

## Техническая документация

- Полный технический документ: [docs/TECHNICAL_ARCHITECTURE.md](./docs/TECHNICAL_ARCHITECTURE.md)
- Единый changelog: [docs/CHANGELOG.md](./docs/CHANGELOG.md)
- Delta notes для `0.3.0`: [docs/DESKTOP_RELEASE_CHANGELOG_0.3.0.md](./docs/DESKTOP_RELEASE_CHANGELOG_0.3.0.md)
- Текущие branch follow-up notes: `docs/CHANGELOG.md` -> `Unreleased`

## Ключевое про 0.3.0

`0.3.0` — это крупный архитектурный релиз, а не patch.

В него вошли:

- backend split на `api/routes`, `services`, `core`, `schemas`;
- централизованный bootstrap приложения через `backend/core/app_bootstrap.py`;
- явные config migrations и JSON Schema export;
- модульный dashboard frontend на ES modules без build step;
- существенная стабилизация Browser Speech lifecycle и runtime/WebSocket event path;
- best-effort client-event logging без backend `500` из-за live event log;
- документированный experimental worker `/google-asr-experimental`;
- локальный backend ASR теперь ограничен только поддерживаемыми Parakeet provider-ами.

При этом не менялись базовые product constraints:

- local-first остается default;
- UI по-прежнему plain HTML/CSS/JS через FastAPI;
- `browser_google` не удалён;
- локальный Parakeet path остаётся доступным;
- remote mode остаётся отдельным explicit LAN-сценарием.

## Состав релиза

Основной desktop release поставляется как:

- `Stream Subtitle Translator.exe`

При первом запуске bootstrap launcher распаковывает managed runtime рядом с собой и затем запускает desktop runtime с диска.

## Быстрый старт

1. Распакуйте архив в папку с правом записи.
2. Убедитесь, что присутствует `Stream Subtitle Translator.exe`.
3. Запустите `Stream Subtitle Translator.exe`.
4. Дождитесь, пока bootstrap launcher при первом запуске разложит managed runtime рядом.
5. В splash launcher выберите профиль запуска:
   - `Quick Start (Browser Speech)`
   - `NVIDIA GPU (CUDA)`
   - `CPU-only`
   - `Remote Controller`
   - `Remote Worker`
6. Дождитесь открытия локального dashboard.

## Bootstrap Launcher

Bootstrap launcher остаётся основным desktop release flow.

Что он делает:

- распространяется как один публичный `Stream Subtitle Translator.exe`;
- содержит embedded managed payload, собранный из clean desktop runtime;
- при первом запуске распаковывает и проверяет managed runtime рядом с собой;
- умеет чинить runtime, если повреждены `app-runtime/` или внутренний runtime executable.

Текущая раскладываемая структура:

- публичный launcher: `Stream Subtitle Translator.exe`
- managed runtime folder: `app-runtime/`
- скрытый внутренний runtime executable: `.sst-runtime.exe`
- пользовательские данные: `user-data/`
- логи приложения: `user-data/logs/`

Сборка из исходников:

- `build-bootstrap-launcher.bat`

Bootstrap output:

- `dist\bootstrap-launcher\Stream Subtitle Translator.exe`

## Профили запуска

- `Quick Start (Browser Speech)`:
  - самый быстрый путь старта;
  - распознавание остаётся в browser worker окне;
  - локальные AI-зависимости не доустанавливаются.
- `NVIDIA GPU (CUDA)`:
  - поднимает локальный CUDA PyTorch stack;
  - рассчитан на системы с NVIDIA.
- `CPU-only`:
  - поднимает CPU-only PyTorch stack;
  - рассчитан на AMD, Intel или системы без GPU.
- `Remote Controller`:
  - сохраняет запуск лёгким;
  - по умолчанию включает controller role и сознательно пропускает bootstrap локального AI runtime;
  - предназначен для pairing с LAN worker-ом при сохранении локального dashboard и overlay на controller-машине.
- `Remote Worker`:
  - запускает local AI worker role с включённым LAN bind;
  - не допускает Browser Speech на стороне worker-а;
  - использует локальный AI runtime profile, соответствующий выбранной или определённой CPU/GPU среде.

## Что создаётся при первом запуске

Публичный release изначально содержит только:

- `Stream Subtitle Translator.exe`

При первом запуске bootstrap launcher сам распаковывает и/или создаёт рядом:

- `.sst-runtime.exe`
- `app-runtime/`
- `.python/`
- `.venv/`
- `user-data/`
- `user-data/logs/`

Для desktop flow это нормальное поведение. Эти папки нужно хранить рядом с `.exe`.

## Основные возможности

- Распознавание речи с микрофона в реальном времени.
- Опциональный перевод на 0, 1 или несколько целевых языков.
- Гибкая схема вывода субтитров:
  - только оригинал
  - только перевод
  - оригинал + один перевод
  - оригинал + несколько переводов
- Вывод в OBS browser overlay.
- Опциональный вывод в OBS Closed Captions.
- Экспорт сессий в `SRT` и `JSONL`.
- Локальные профили настроек.
- Локальные runtime diagnostics и event logs.

## Кратко об архитектуре

В `0.3.0` текущая архитектура зафиксирована явно.

Backend:

- `backend/api/routes/` для HTTP endpoints;
- `backend/services/` для route-facing orchestration;
- `backend/config/` для defaults, secrets и normalization helpers;
- `backend/core/` для bootstrap, shared lifecycle, WS, subtitle routing и runtime coordination;
- `backend/core/runtime/` для выделенных runtime controllers и status builders;
- `backend/asr/parakeet/` для локальной AI runtime installation, diagnostics и provider adapters;
- `backend/translation/` для provider registry, readiness checks, engine wiring и provider-specific clients;
- `backend/schemas/` для typed config/runtime/diagnostics payloads.

Frontend:

- только plain HTML/CSS/JS;
- `frontend/js/main.js` как dashboard entrypoint;
- `frontend/js/core/` для store, API, WS client, event bus;
- `frontend/js/dashboard/` для actions/helpers/logging;
- `frontend/js/panels/` для panel wiring;
- `frontend/js/normalizers/` для pure normalization logic.

Это всё ещё FastAPI-served desktop UI. Node.js/npm/React/Vite/Webpack/Electron/Tauri не используются.

## Обзор Desktop Dashboard

Главное окно включает:

- Runtime badges:
  - health
  - runtime state
  - ASR provider и device
  - partials availability
  - recognition mode
  - translation status
  - OBS CC status
- Основные кнопки:
  - `Start`
  - `Stop`
- Live panels:
  - transcript (partial + final)
  - выбор микрофона
  - выбор режима распознавания
  - preview итоговых субтитров
  - локальный overlay URL
  - diagnostics/event feed

`Start` теперь отправляет текущий in-memory config snapshot в `/api/runtime/start`, поэтому несохранённые изменения из dashboard могут сразу применяться к runtime без обязательной записи на диск.

Внешний вид dashboard в `0.3.0` не был полностью переработан; основные изменения касаются внутренней архитектуры и устойчивости runtime.

## Основные вкладки

### Translation

- Включение/выключение перевода.
- Выбор default-провайдера для новых линий и legacy fallback-сценариев.
- Настройка ключей/endpoint/model/prompt там, где это нужно.
- `Google Cloud Translation - Advanced (v3)` доступен как отдельный провайдер и использует `project_id` + OAuth access token вместо v2 API key.
- Настройка до пяти translation lines, каждая со своими:
  - enabled
  - target language
  - provider
  - optional label
- Дубли target language теперь допустимы, если используются разные translation slots.
- Порядок preview и overlay теперь опирается на стабильные slot id вида `translation_1 .. translation_5`, а не только на код языка.
- Просмотр последних результатов перевода.
- Provider settings по-прежнему глобальны для каждого провайдера в `translation.provider_settings`; ключи не дублируются внутрь per-line config.
- Translation pipeline теперь отделён от live source-final path: source final публикуется сразу, а fan-out идёт асинхронно по настроенным линиям, и stale jobs подавляются, если уже потеряли lifecycle relevance.

### Subtitles

- Настройка overlay preset:
  - `single`
  - `dual-line`
  - `stacked`
  - `compact`
- Показ/скрытие source text.
- Показ/скрытие translated lines.
- Ограничение числа видимых translated lines.
- Настройка subtitle lifetime behavior.
- Управление display order для preview и overlay.
- По умолчанию предыдущий completed translation остаётся видимым, пока новая source phrase ещё набирается partial-ами.
- Completed translation block переключается только после того, как новая phrase финализирована и для неё пришёл replacement translation.

### Style

- Применение built-in style presets.
- Сохранение и удаление custom presets.
- Настройка base style:
  - font family/size/weight
  - color, outline, shadow
  - background
  - alignment and spacing
  - effects
- Настройка per-line slot overrides.

### OBS

- Настройка OBS websocket host/port/password.
- Включение OBS Closed Captions output.
- Выбор output mode:
  - `source_live`
  - `source_final_only`
  - `translation_1` ... `translation_5`
  - `first_visible_line`
- Опциональный debug mirror в OBS text source.
- Тайминги отправки partial/final.

### Tuning

- Ползунки поведения распознавания:
  - appearance speed
  - finalize speed
  - stability/noise sensitivity
- Опциональный RNNoise path.
- Практические live-заметки.

### Tools & Data

- Runtime diagnostics и latency metrics.
- Расширенные ASR controls.
- Live event feed с bounded logging behavior.
- Config save/export/import.
- Profile load/save/delete.
- `Export Diagnostics` создаёт локальный ZIP с redacted config, runtime/preflight snapshots, latest session log и backend log.

## Режимы распознавания

### Local Parakeet

- Локальный runtime и локальный audio capture path.
- GPU-first политика на совместимых NVIDIA системах.
- При необходимости доступен CPU fallback.
- Это по-прежнему основной локальный AI path.
- В `Recognition -> Backend ASR provider` теперь доступны только `Official EU Parakeet Low Latency` и `Official EU Parakeet`.

### Browser Speech

- Работает через отдельное окно Chrome/Chromium/Edge (`/google-asr`).
- Desktop behavior зафиксирован:
  - SST всегда открывает Browser Speech как отдельное окно браузера с адресной строкой.
  - Launcher использует для этого окна isolated browser profile.
  - Browser-window mode toggle в desktop UI отсутствует.
  - Это поведение нельзя заменять на `--app`, popup-launcher pages, hidden bootstrap windows или in-tab navigation.
- Требует browser microphone permission.
- Для стабильности держите окно worker видимым во время работы.

Classic Browser Speech в `0.3.0` теперь включает:

- отдельный lifecycle supervisor;
- controlled `start/stop/restart`;
- reason-aware restart cooldowns;
- generation-aware reconnect handling;
- duplicate partial/final suppression;
- mic health diagnostics;
- приоритет `localStorage` настроек worker-а с best-effort backend mirror;
- best-effort client-event logging, чтобы проблемы с log file не ломали страницу.

### Browser Speech: live smoke checklist

- Откройте `/google-asr`, обновите страницу и проверьте, что язык и toggles восстановились из worker-local settings.
- Запустите распознавание и убедитесь, что одна фраза даёт interim, затем один final без duplicate final spam.
- Помолчите несколько циклов и проверьте, что recovery идёт через cooldown, а не через tight loop `onend`/`start()`.
- Обновите dashboard или дайте `/ws/asr_worker` переподключиться и убедитесь, что worker не создаёт второй active recognition instance.
- Заглушите микрофон или уберите доступ к устройству и проверьте, что diagnostics уходят в `mic_silent` или `mic_track_unavailable`, а не зависают молча.
- Дайте force-finalization закрыть interim и проверьте, что поздний browser final для той же фразы подавляется как late duplicate и не отправляется повторно.

### Browser Speech Experimental

- Работает через отдельное experimental worker окно (`/google-asr-experimental`).
- Сначала открывает один live microphone `MediaStreamTrack`, затем вызывает `SpeechRecognition.start(audioTrack)`.
- Если браузер отвергает `start(audioTrack)`, worker может откатиться на обычный `recognition.start()`.
- Страница теперь привязана к тому же controlled base FSM contract, что и classic worker.
- Поддержка браузерами может отличаться. Во время работы держите окно worker видимым.

### Browser Speech Experimental: smoke checklist

- Откройте `/google-asr-experimental` и сделайте hard refresh, чтобы isolated worker profile подтянул последний JS.
- Запустите распознавание и проверьте, что происходит либо `audio-track-start-success`, либо controlled fallback на обычный `recognition.start()`.
- Быстро нажмите Stop/Start несколько раз; worker не должен зависать в постоянном `stopping`.
- Переподключите dashboard и убедитесь, что worker не создаёт duplicate active recognition instance.
- Закройте или отзовите доступ к микрофону и проверьте, что страница деградирует явно, а не перестаёт работать молча.

## Runtime Robustness в 0.3.0

Runtime/event stack стал значительно защитнее, чем в `0.2.9.2`.

Ключевые эффекты:

- `/ws/events` reconnect больше не должен так легко фризить dashboard;
- duplicate runtime status flood coalesce-ится;
- dead WebSocket connections удаляются после send failures;
- Windows close/send errors обрабатываются как cleanup issue, а не как fatal runtime failure;
- stale browser worker generations игнорируются;
- live event log storage ограничен и лучше переживает duplicate traffic;
- overlay/runtime event flow лучше подавляет stale translation mismatch.

## Локальные URL

- Dashboard: `http://127.0.0.1:8765/`
- Overlay: `http://127.0.0.1:8765/overlay`
- Browser worker: `http://127.0.0.1:8765/google-asr`
- Browser experimental worker: `http://127.0.0.1:8765/google-asr-experimental`

Примеры query для overlay:

- `?profile=default`
- `?compact=1`

Overlay остаётся отдельной lightweight страницей для OBS Browser Source и автоматически переподключается после websocket drop.

## Config и schema notes

`0.3.0` вводит более явный config contract:

- config versioned и проходит через явные migrations;
- config normalization теперь живёт в `backend/config/`, а не в одном монолитном `backend/config.py`;
- profiles используют тот же migration/normalization pipeline;
- generated schema лежит в `backend/data/config.schema.json`;
- `translation.lines` теперь является новой slot-aware config surface, а legacy `translation.provider` и `translation.target_languages` сохранены для совместимости;
- legacy language-based значения `subtitle_output.display_order` мигрируются в slot id вида `translation_1`;
- `/api/runtime/start` может принять optional normalized `config_payload` для runtime-only изменений без сохранения `user-data/config.json`;
- `backend/versioning.py` остаётся single source of truth для версии приложения.

## Remote Notes

В репозитории по-прежнему есть optional LAN remote controller/worker support:

- default desktop launch остаётся на `127.0.0.1`;
- `Remote Controller` и `Remote Worker` остаются explicit secondary flows;
- remote worker runtime является AI-only и не должен запускать browser speech modes;
- remote worker sync также предотвращает уход в browser-worker paths во время controller -> worker settings sync.

## Где лежат данные и логи

Создаются рядом с `.exe`:

- `user-data/`
  - `config.json`
  - `profiles/`
  - `exports/`
  - `models/`
  - `cache/`
- `user-data/logs/`
  - `backend.log`
  - `runtime-events.jsonl`
  - `session-latest.jsonl`
  - browser/client logs в зависимости от активного runtime path

Полезные diagnostics paths:

- backend/runtime сбои:
  - смотрите `user-data/logs/backend.log`
- structured runtime events:
  - смотрите `user-data/logs/runtime-events.jsonl`
- последние dashboard/overlay/browser-worker client events:
  - смотрите `user-data/logs/session-latest.jsonl`

Runtime cache/temp paths управляются автоматически. Первый старт может быть дольше из-за инициализации.

## Системные требования

- Windows 10/11 x64
- Доступ к микрофону
- Для GPU-режима: NVIDIA GPU + совместимый CUDA runtime stack
- Для внешних переводчиков: интернет + валидные provider credentials

## Обновление

Чтобы обновить SST Desktop:

1. Закройте приложение.
2. Замените публичный `Stream Subtitle Translator.exe`.
3. Сохраните существующие `.python/`, `.venv/`, `user-data/` и `logs/`, если хотите оставить локальный runtime state, настройки и историю.
4. Если `app-runtime/` или `.sst-runtime.exe` повреждены, используйте:
   - `--repair`
   - `--reset-runtime`
   или соответствующие maintenance-кнопки в bootstrap splash окне.

## Сборка из исходников

- Поднимите локальное dev-окружение через `start.bat`.
- Соберите desktop one-folder package через `build-desktop.bat`.
- Соберите bootstrap one-file launcher через `build-bootstrap-launcher.bat`.
- Подготовьте clean release folders через `publish-desktop-releases.ps1`.

Build output:

- `dist\Stream Subtitle Translator\`
- bootstrap launcher:
  - `dist\bootstrap-launcher\`

## Troubleshooting

- Приложение не стартует:
  - запустите bootstrap launcher повторно и дайте ему пересоздать `app-runtime/`.
- Managed runtime выглядит повреждённым:
  - используйте кнопку `Repair Runtime` в bootstrap окне;
  - или запустите `Stream Subtitle Translator.exe --repair`.
- Managed runtime нужно пересобрать с нуля:
  - используйте кнопку `Reset Runtime` в bootstrap окне;
  - или запустите `Stream Subtitle Translator.exe --reset-runtime`.
- UI недоступен:
  - убедитесь, что локальный порт `8765` не занят.
- Browser Speech не даёт текст:
  - выдайте browser microphone permission;
  - держите окно worker открытым и видимым;
  - если тестируете experimental path, делайте hard refresh после обновлений.
- Нет вывода в OBS:
  - проверьте OBS websocket settings и выбранный output mode.

## Автотесты

Текущий regression suite запускается так:

- `.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"`

Для текущего состояния `0.3.0` были прогнаны:

- `python -m compileall backend tests`
- `.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"`

Результат:

- `130 tests`
- `OK`

## Приватность и границы выполнения

- SST Desktop работает в local-first режиме.
- Dashboard, API, websocket events, overlay, logs, profiles, cache и exports работают на одной машине.
- По умолчанию используется localhost (`127.0.0.1`).

## Версия релиза

- `0.3.0`
- Single runtime source of truth: `backend/versioning.py` (`PROJECT_VERSION`).
