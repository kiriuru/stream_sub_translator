# SST Desktop 0.4.2

SST Desktop — локальное Windows-приложение для распознавания речи в реальном времени, опционального перевода, маршрутизации субтитров и вывода в OBS.

Этот README описывает текущий desktop product surface для линии `0.4.2`.

## Язык

- English version: [README.md](./README.md)

## Техническая документация

- Полный технический документ: [docs/TECHNICAL_ARCHITECTURE.md](./docs/TECHNICAL_ARCHITECTURE.md).
- Единый changelog: [docs/CHANGELOG.md](./docs/CHANGELOG.md)
- **Installer delta `0.4.1`:** [docs/DESKTOP_RELEASE_CHANGELOG_0.4.1.md](./docs/DESKTOP_RELEASE_CHANGELOG_0.4.1.md)
- Полная история (`0.4.0` и ранее): [docs/CHANGELOG.md](./docs/CHANGELOG.md)

## Состав релиза

В GitHub Releases — bootstrap **exe** (сборка локальная; `desktop/` в публичном репо нет):

- `Stream Subtitle Translator.exe` — стандартный bootstrap (payload следует `PROJECT_VERSION`, в этом дереве **0.4.2**)
- `Stream Subtitle Translator Only Web.exe` — только Web Speech (добавлен в 0.4.0; поддерживается)

При первом запуске bootstrap launcher распаковывает managed runtime рядом с собой и затем запускает desktop runtime с диска.

## Быстрый старт

**Стандартный launcher** (`Stream Subtitle Translator.exe`):

1. Распакуйте архив в папку с правом записи.
2. Убедитесь, что присутствует `Stream Subtitle Translator.exe`.
3. Запустите `Stream Subtitle Translator.exe`.
4. Дождитесь, пока bootstrap launcher при первом запуске разложит managed runtime рядом.
5. В стартовом окне выберите профиль:
   - `Quick Start (Web Speech)` — блокирует Local Parakeet до следующего запуска с GPU/CPU
   - `NVIDIA GPU (CUDA)`
   - `CPU-only`
   - `Remote Controller`
   - `Remote Worker`
6. После выбора профиля shell дашборда появляется, как только доступен `GET /` (полный `/api/health` — в фоне). Панели сразу интерактивны; настройки, справка и desktop context догружаются в фоне.

**Only Web** (`Stream Subtitle Translator Only Web.exe`): те же шаги 1–4, без выбора профиля — сразу Web Speech quick start.

## Bootstrap Launcher

Bootstrap launcher остаётся основным desktop release flow.

Что он делает:

- распространяется как один публичный `Stream Subtitle Translator.exe`;
- содержит embedded managed payload, собранный из clean desktop runtime;
- проверяет GitHub Releases на наличие новой версии и показывает окно только если обновление найдено;
- при первом запуске распаковывает и проверяет managed runtime рядом с собой;
- умеет чинить runtime, если повреждены `app-runtime/` или внутренний runtime executable.

Поведение проверки обновлений:

- если обновления нет (или сеть/API недоступны), пользователь ничего не видит и запуск идёт как обычно;
- если новая версия есть, появляется небольшое окно с вариантами:
  - `Continue`: продолжить запуск
  - `Download`: открыть страницу релиза в браузере и затем продолжить запуск

Текущая раскладываемая структура:

- публичный launcher: `Stream Subtitle Translator.exe`
- managed runtime folder: `app-runtime/`
- скрытый внутренний runtime executable: `.sst-runtime.exe`
- пользовательские данные: `user-data/`
- логи приложения: `logs/` (предыдущий запуск desktop → `desktop-launcher.old.log` при следующем старте)
- локальные модели: `user-data/models/`

Сборка desktop exe:

- `build-bootstrap-launcher.bat` → `Stream Subtitle Translator.exe`
- `build-bootstrap-launcher-web-only.bat` → `Stream Subtitle Translator Only Web.exe`
- `publish-desktop-releases.ps1` / `publish-desktop-releases-web-only.ps1`

Разработка из клона GitHub: **`start.bat`** (backend + frontend).

## Профили запуска

Профили на splash без изменений относительно прошлых релизов. **С 0.4.0:** Quick Start и **Only Web** выставляют `asr.desktop_profile_lock` — раздел **0.4.0** в [CHANGELOG](./docs/CHANGELOG.md).

- `Quick Start (Web Speech)`:
  - самый быстрый путь старта;
  - распознавание остаётся в browser worker окне;
  - локальные AI-зависимости не доустанавливаются;
  - пишет `asr.desktop_profile_lock = browser_speech` в `user-data/config.json` — в dashboard нельзя выбрать Local Parakeet, пока не запустите с NVIDIA GPU или CPU-only.
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
  - не допускает Web Speech на стороне worker-а;
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
- `logs/`
- `user-data/models/`
- `fonts/`

Для desktop flow это нормальное поведение. Эти папки нужно хранить рядом с `.exe`.

Если в старой установке логи ещё лежат в `user-data/logs/`, launcher/runtime перенесёт эти файлы в `logs/`.

При каждом старте desktop shell предыдущий `logs/desktop-launcher.log` архивируется в `desktop-launcher.old.log` — история сбоя прошлого запуска сохраняется.

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
- Настройка темы интерфейса dashboard (светлая/тёмная) и палитры акцентных градиентов, применяемой также к окнам Web Speech worker.
- Локальные runtime diagnostics и event logs.

## Кратко об архитектуре

В `0.3.x` сохранена и уточнена явная архитектура из `0.3.0`.

Backend:

- `backend/api/routes/` для HTTP endpoints;
- `backend/services/` для route-facing orchestration;
- `backend/config/` для defaults, secrets и normalization helpers;
- `backend/core/` для bootstrap, shared lifecycle, WS, subtitle routing и runtime coordination;
- `backend/core/runtime/` для runtime controllers, **тонкого фасада `RuntimeOrchestrator` + mixins**, `LocalAsrPipeline` и status builders;
- `backend/asr/parakeet/` для локальной AI runtime installation, diagnostics и provider adapters;
- `backend/translation/` для provider registry, readiness checks, engine wiring и provider-specific clients;
- `backend/schemas/` для typed config/runtime/diagnostics payloads.

Frontend:

- только plain HTML/CSS/JS;
- `frontend/js/main.js` как dashboard entrypoint;
- `frontend/js/core/` для store (изолированные listeners), API, WS client, `dom.js` idempotent input helpers, event bus;
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

`Start` отправляет текущий in-memory config snapshot в `/api/runtime/start`, поэтому несохранённые изменения из dashboard сразу применяются к runtime без обязательной записи на диск. Снимок отслеживается через `active_config_source = runtime_start_snapshot`, `active_config_persisted = false` и `active_config_hash`, чтобы не перетирать `user-data/config.json`.

Внешний вид dashboard в линии `0.3.x` не переработан; основные изменения остаются на уровне внутренней архитектуры и устойчивости runtime.

**UX настроек dashboard (`0.4.1+`):** панели перерисовываются из central store при обновлениях runtime/config, но поля ввода и чекбоксы обновляются idempotent — caret и фокус не сбрасываются во время редактирования. Ошибка в одном listener панели не блокирует остальные подписчики store.

## Основные вкладки

### Translation

- Включение/выключение перевода.
- Выбор default-провайдера для новых линий и legacy fallback-сценариев.
- Настройка ключей/endpoint/model/prompt там, где это нужно.
- Для OpenAI и OpenAI-совместимых провайдеров (`openai`, `openrouter`, `lm_studio`, `ollama`) dashboard заполняет поле `model` через локальные helper endpoints:
  - `GET /api/openai/recommended-models` — курируемый shortlist без обращения к OpenAI API из браузера;
  - `POST /api/openai/models` — листинг моделей по предоставленному ключу;
  - `POST /api/openai/usable-models` — лёгкая проба через `/responses` с серверным кэшем.
- `Google Cloud Translation - Advanced (v3)` доступен как отдельный провайдер и использует `project_id` + OAuth access token вместо v2 API key.
- Настройка до пяти translation lines, каждая со своими:
  - enabled
  - target language
  - provider
  - optional label
- Во вкладке Translation каждый слот `translation_1 .. translation_5` теперь показывается как отдельная карточка с явным выбором provider-а для конкретной линии.
- Карточки slot-ов появляются только для линий, которые явно добавлены в `translation.lines` (пустые слоты не отображаются, пока их не добавили).
- При выборе линии редактор provider settings автоматически переключается на provider этой линии, а `translation.provider` остаётся default provider-ом для новых линий и legacy compatibility.
- Если translation slot не выбран, provider settings panel можно вручную переключить на нужный provider.
- Дубли target language теперь допустимы, если используются разные translation slots.
- Порядок preview и overlay теперь опирается на стабильные slot id вида `translation_1 .. translation_5`, а не только на код языка.
- Просмотр последних результатов перевода.
- Provider settings по-прежнему глобальны для каждого провайдера в `translation.provider_settings`; ключи не дублируются внутрь per-line config.
- Dashboard теперь отдельно предупреждает, если включённые translation lines используют provider-ы с неполными настройками.
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
- Встроенные эффекты: `none`, `fade`, `subtle_pop`, `slide_up`, `zoom_in`, `blur_in`, `glow`.
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
- Во вкладке Tuning остаются только пользовательские настройки «ощущения» распознавания; точные ASR timing значения находятся в `Tools & Data`.

### Tools & Data

- Runtime diagnostics и latency metrics.
- Runtime diagnostics покрывают latency, ASR state, translation queue/provider state, Web Speech worker connectivity, OBS Closed Captions state и local log locations.
- Расширенные ASR controls показывают точные timing/gate значения: VAD mode, partial emit interval, min speech, silence hold, pause-to-finalize, max phrase length, chunk window/overlap, min RMS, voiced ratio и first partial speech.
- Live event feed с bounded logging behavior.
- Более широкое покрытие локализации dashboard, включая runtime progress, remote tools, style slot editor и diagnostics strings.
- Config save/export/import.
- Profile load/save/delete.
- `Export Diagnostics` создаёт локальный ZIP с redacted config, runtime/preflight snapshots, latest session log и backend log.

### Help / Помощь

- В основном dashboard добавлена отдельная вкладка `Help / Помощь` после `Tools & Data`.
- Help устроен как внутренние topic-tabs: на экране виден только один подробный раздел.
- Темы справки:
  - обзор
  - распознавание и tuning
  - перевод
  - субтитры и стиль
  - OBS
  - tools и diagnostics
  - desktop и remote mode
- Remote-раздел содержит практический порядок запуска controller/worker, порядок pairing, замечания про bridge windows и объяснение полей `Worker Base URL`, `Session ID`, `Pair Code`, remote state и worker runtime status.

## Режимы распознавания

### Local Parakeet

- Локальный runtime и локальный audio capture path.
- GPU-first политика на совместимых NVIDIA системах.
- При необходимости доступен CPU fallback.
- Это по-прежнему основной локальный AI path.
- В `Recognition -> Backend ASR provider` доступен только **Official EU Parakeet Low Latency** (legacy `official_eu_parakeet` мигрирует в low latency).
- Вкладка Tuning: пресеты задержки (`ultra_low_latency` / `balanced` / `quality` / `custom`), согласованы с `local_asr_realtime_settings.py`.

### Web Speech

- После **Quick Start (Web Speech)** или **Only Web**: `asr.desktop_profile_lock = browser_speech` — в Recognition нет Local Parakeet до запуска с **GPU/CPU**. Код: `frontend/js/dashboard/desktop-profile-lock.js`, packaged launcher (локальное дерево), `backend/config/normalizers/asr.py`, `AsrConfig.desktop_profile_lock`.
- Работает через отдельное окно **Google Chrome** (`/google-asr`).
- В desktop-сборке в Overview → Recognition можно выбрать **Auto** или **Google Chrome** (`asr.browser.worker_launch_browser`: `auto` или `google_chrome`); оба варианта запускают Chrome. Настройка читается из `config.json` при каждом открытии worker. В чисто веб-дашборде (`start.bat` в обычном браузере) этот переключатель скрыт: `window.open` всегда ведёт в браузер по умолчанию ОС.
- Desktop behavior зафиксирован:
  - SST всегда открывает Web Speech как отдельное окно браузера с адресной строкой (`--new-window` + URL воркера).
  - **Google Chrome:** для этого окна launcher использует **изолированный** `user-data-dir` в runtime.
  - Browser-window mode toggle в desktop UI отсутствует.
  - Это поведение нельзя заменять на `--app`, popup-launcher pages, hidden bootstrap windows или in-tab navigation.
- Требует browser microphone permission.
- Для стабильности держите окно worker видимым во время работы.

Classic Web Speech включает:

- отдельный lifecycle supervisor;
- controlled `start/stop/restart`;
- reason-aware restart cooldowns;
- generation-aware reconnect handling;
- duplicate partial/final suppression;
- mic health diagnostics;
- приоритет `localStorage` настроек worker-а с best-effort backend mirror;
- best-effort client-event logging, чтобы проблемы с log file не ломали страницу.

### Web Speech: дополнительные слои стабилизации распознавания

Поверх базового supervisor-а worker применяет ещё несколько защит, которые удерживают
распознавание живым, когда ОС, сеть или сам Chrome пытаются его молча задушить:

- **Screen Wake Lock**: когда распознавание запущено и окно worker-а видимо, страница берёт
  `navigator.wakeLock.request("screen")` и отпускает его на Stop. Это блокирует уход дисплея/
  системы в power-save, при котором Chrome троттлит аудио-колбэки и Web Speech тихо встаёт.
  Wake Lock автоматически берётся снова после смены visibility (например, перенос окна между
  мониторами).
- **Более ранняя контролируемая ротация сессии**: `asr.browser.max_browser_session_age_ms` по
  умолчанию теперь **180000 мс** (было 240000 мс). У Chrome остаётся больший запас до его
  собственного молчаливого ~4-минутного убийства Web Speech. Окно `prepare_cycle_before_ms = 15`
  с по-прежнему применяется, поэтому worker перерождает сессию в районе 2:45, а не получает
  обрыв посреди фразы.
- **Network preflight + терминальная деградация**: после трёх `network` ошибок в окне ~12 с
  worker один раз пробует `https://www.google.com/generate_204` с коротким таймаутом. Если
  проба провалилась, supervisor уходит в терминальный `recognition_network_unreachable` и
  останавливает auto-restart петлю вместо бесполезного жжения CPU/батареи. В лог уходит
  понятная пользователю подсказка про VPN/firewall/DNS/прокси. Удачный результат распознавания
  сбрасывает счётчик burst-ошибок.
- **Health-сигнал `voice_below_recognition_threshold`**: отдельный от `web_speech_stalled` и
  `mic_silent`. Срабатывает, когда у микрофона явный voice-level RMS (>= 0.025) и параллельно
  накопились `no-speech` ошибки при тишине распознавания >= 8 с. Это диагностирует кейс «голос
  есть, но Google его не слышит» (слишком тихо для модели, mismatch локали, или начавшаяся
  деградация сети).
- **Приоритет процесса Chrome и opt-out из Windows EcoQoS**: desktop launcher запускает Chrome
  worker с `HIGH_PRIORITY_CLASS` и на Windows 10/11 вызывает `SetProcessInformation`
  (`ProcessPowerThrottling`, OPT_OUT), чтобы ОС не отправляла процесс в Efficiency Mode, когда
  окно перекрыто или вне фокуса. Это закрывает класс багов «Web Speech встаёт, когда поверх
  Chrome ставят OBS» на Windows 11.
- **Отключение Chrome feature gates для worker-окна**: `CalculateNativeWinOcclusion`,
  `HighEfficiencyModeAvailable`, `HeuristicMemorySaver`, `IntensiveWakeUpThrottling`,
  `GlobalMediaControls`. Это запрещает Chrome объявлять окно occluded, выкидывать вкладку как
  жертву Memory Saver, агрессивно троттлить таймеры и красть фокус media-key попапами. В паре
  с уже существующими `--disable-backgrounding-occluded-windows`, `--disable-renderer-backgrounding`
  и `--disable-background-timer-throttling` это самая жёсткая browser-сайд конфигурация,
  которую можно применить, не отказываясь от окна с адресной строкой.

Эти слои подключены и в classic Web Speech, и в Web Speech Experimental. Контракт `/api` и
websocket-payload-ов не изменился. Supervisor по-прежнему ротирует сессии, подавляет дубликаты
и force-finalize-ит при interruption-ах ровно как раньше.

### Web Speech: live smoke checklist

- Откройте `/google-asr`, обновите страницу и проверьте, что язык и переключатели восстановились из локальных настроек worker-а.
- Запустите распознавание и убедитесь, что одна фраза даёт interim (частичный текст), затем один final (финальный сегмент) без дубликатов.
- Помолчите несколько циклов и проверьте, что восстановление идёт через cooldown (задержки), а не через «тесный» цикл `onend`/`start()`.
- Обновите dashboard или дайте `/ws/asr_worker` переподключиться и убедитесь, что worker не создаёт второй active recognition instance.
- Заглушите микрофон или уберите доступ к устройству и проверьте, что диагностика уходит в `mic_silent` или `mic_track_unavailable`, а не зависает молча.
- Дайте force-finalization закрыть interim и проверьте, что поздний browser final для той же фразы подавляется как late duplicate и не отправляется повторно.
- После Start проверьте, что Wake Lock держится во время работы (Chrome DevTools -> Application -> Wake Locks); и что он освобождается после Stop или после деградации `recognition_network_unreachable`.
- Заблокируйте Web Speech эндпоинт (отключите интернет или фаерволом закройте `*.google.com`) и убедитесь, что supervisor уходит в терминальный `recognition_network_unreachable` после burst-порога, а не циклится бесконечно.
- На Windows 11 накройте окно Chrome worker другим окном (OBS preview, dashboard) и убедитесь, что partials/finals продолжают идти — это проверка `CalculateNativeWinOcclusion` и EcoQoS opt-out.

### Web Speech Experimental

- Работает через отдельное experimental worker окно (`/google-asr-experimental`).
- Сначала открывает один live microphone `MediaStreamTrack`, затем вызывает `SpeechRecognition.start(audioTrack)`.
- Если браузер отвергает `start(audioTrack)`, worker может откатиться на обычный `recognition.start()`.
- Страница теперь привязана к тому же controlled base FSM contract, что и classic worker.
- Поддержка браузерами может отличаться. Во время работы держите окно worker видимым.

### Web Speech Experimental: smoke checklist

- Откройте `/google-asr-experimental` и сделайте hard refresh, чтобы воркер подтянул последний JS (у Chrome изолированный профиль).
- Запустите распознавание и проверьте, что происходит либо `audio-track-start-success`, либо controlled fallback на обычный `recognition.start()`.
- Быстро нажмите Stop/Start несколько раз; worker не должен зависать в постоянном `stopping`.
- Переподключите dashboard и убедитесь, что worker не создаёт duplicate active recognition instance.
- Закройте или отзовите доступ к микрофону и проверьте, что страница деградирует явно, а не перестаёт работать молча.

## Runtime robustness (линия 0.3.x)

Runtime/event stack стал значительно защитнее, чем в `0.2.9.2`, и `0.3.1` добавил поверх `0.3.0` ещё одну порцию структуры:

- `RuntimeOrchestrator` — фасад над явными контроллерами в `backend/core/runtime/` (state, lifecycle, metrics, session, segments, browser-worker bookkeeping, speech sources, audio capture, processing tasks, translation runtime, transcript pipeline, output fanout).
- `SubtitleRouter` разделён на `subtitle_lifecycle_core.py` (FSM, TTL, релевантность), `subtitle_presentation.py` (сборка payload, слоты стилей, partial/final) и тонкий публикующий фасад.
- `TranslationDispatcher` стал restart-safe (`stop() -> start()` не ломает следующие сессии) и получил per-provider concurrency/rate limits.
- `CacheManager` (`backend/core/cache_manager.py`) заменил предыдущий read-modify-write JSON-кеш: in-memory LRU + дебаунс-персист + карантин повреждённого файла кеша.
- Запись config стала Windows-safe атомарной (`backend/core/atomic_io.py`, `os.replace()`); повреждённый `user-data/config.json` уезжает в `*.corrupt-<timestamp>.json` и приложение поднимается на дефолтах через тот же pipeline миграции/нормализации.

Эффекты, унаследованные и уточнённые из `0.3.0`:

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

`0.3.x` сохраняет явный config contract из `0.3.0` и усиливает его:

- config versioned и проходит через явные migrations (`backend/core/config_migrations.py`, текущая `CURRENT_CONFIG_VERSION = 7` в `backend/schemas/config_schema.py`);
- config normalization живёт в `backend/config/` (`defaults.py`, `secrets.py`, `normalizers/asr.py|browser.py|obs.py|remote.py|subtitles.py|translation.py|source_text_replacement.py`);
- profiles используют тот же migration/normalization pipeline;
- generated schema лежит в `backend/data/config.schema.json` и публикуется через `python -m backend.core.config_schema_export`;
- `translation.lines` — slot-aware config surface (`translation_1..translation_5` с `enabled`, `target_lang`, `provider`, `label`); legacy `translation.provider` и `translation.target_languages` сохранены для совместимости;
- legacy language-based значения `subtitle_output.display_order` мигрируются в slot id вида `translation_1`;
- `/api/runtime/start` может принять optional normalized `config_payload` для runtime-only изменений без сохранения `user-data/config.json` (трекинг через `active_config_source = runtime_start_snapshot`, `active_config_persisted = false`, `active_config_hash`);
- запись config — Windows-safe атомарная (временный файл рядом + `os.replace()`); повреждённый `user-data/config.json` уезжает в `*.corrupt-<timestamp>.json`, и приложение поднимается на дефолтах;
- `backend/versioning.py` (`PROJECT_VERSION = "0.4.2"`) — single source of truth для версии приложения.

## Remote Notes

В репозитории по-прежнему есть optional LAN remote controller/worker support:

- default desktop launch остаётся на `127.0.0.1`;
- `Remote Controller` и `Remote Worker` остаются explicit secondary flows;
- remote worker runtime является AI-only и не должен запускать browser speech modes;
- remote worker sync также предотвращает уход в browser-worker paths во время controller -> worker settings sync.

Рекомендуемый порядок запуска remote mode:

1. Сначала запустите worker-машину через `Remote Worker` или `start-remote-worker.bat`.
2. Затем запустите controller-машину через `Remote Controller` или `start-remote-controller.bat`.
3. На controller-е введите LAN URL worker-а в `Worker Base URL`.
4. Выполните `Check Worker Health` до pairing или запуска runtime.
5. Создайте/проверьте пару, затем обновите remote state.
6. Выполните `Sync Worker Settings`, затем `Prepare Remote Run`.
7. Запустите и проверьте worker runtime.
8. Держите controller и worker bridge windows открытыми, пока remote run активен.
9. Нажмите `Start` в dashboard на controller-е, чтобы начать захват микрофона и remote audio/result flow.

Экспериментальные провайдеры перевода снова отображают status `experimental` в dashboard, а не сворачиваются в `degraded`; реальные degraded-состояния остаются для ошибок и fallback-условий.

## Где лежат данные и логи

Создаются рядом с `.exe`:

- `user-data/`
  - `config.json`
  - `profiles/`
  - `exports/`
  - `models/`
  - `cache/`
  - `secrets/`
  - `debug/`
- `logs/`
  - `bootstrap-launcher.log`
  - `desktop-launcher.log`
  - `backend.log`
  - `runtime-events.log`
  - `session-latest.jsonl`
  - browser/client logs в зависимости от активного runtime path

Legacy desktop installs, где логи ещё лежат в `user-data/logs/`, автоматически мигрируют эти файлы в `logs/` при старте launcher/runtime.

Полезные diagnostics paths:

- backend/runtime сбои:
  - смотрите `logs/backend.log`
- structured runtime events:
  - смотрите `logs/runtime-events.log`
- последние dashboard/overlay/browser-worker client events:
  - смотрите `logs/session-latest.jsonl`

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
3. Сохраните существующие `.python/`, `.venv/`, `user-data/` и `fonts/`, если хотите оставить локальный runtime state, настройки, историю и project-local font assets.
4. Если `app-runtime/` или `.sst-runtime.exe` повреждены, используйте:
   - `--repair`
   - `--reset-runtime`
   или соответствующие maintenance-кнопки в bootstrap splash окне.

## Сборка из исходников

**Клон GitHub** (только tracked-исходники):

- Запуск и разработка: `start.bat` (без каталога `desktop/`).

**Сборка desktop exe** (полное локальное дерево с `desktop/`, скрипты не в публичном репо):

- `build-desktop.bat`, `build-bootstrap-launcher.bat`, `build-bootstrap-launcher-web-only.bat`
- `publish-desktop-releases.ps1`, `publish-desktop-releases-web-only.ps1`

Build output:

- `dist\Stream Subtitle Translator\`
- bootstrap launcher:
  - `dist\bootstrap-launcher\Stream Subtitle Translator.exe`
  - `dist\bootstrap-launcher-web-only\Stream Subtitle Translator Only Web.exe`
- версионный bundle (локально): `dist\desktop-releases\v0.4.2\` (`01-bootstrap-onefile\`, …) при publish этой линии; в старых деревьях может оставаться `v0.4.1\` или `v0.4.0\`.
- publish script по умолчанию пишет сюда:
  - `F:\AI\stream-sub-translator-desktop-release`
  - `F:\AI\stream-sub-translator-desktop-release-clean`

## Troubleshooting

- Приложение не стартует:
  - запустите bootstrap launcher повторно и дайте ему пересоздать `app-runtime/`.
- Managed runtime выглядит повреждённым:
  - используйте кнопку `Repair Runtime` в bootstrap окне;
  - или запустите `Stream Subtitle Translator.exe --repair`.
- Managed runtime нужно пересобрать с нуля:
  - используйте кнопку `Reset Runtime` в bootstrap окне;
  - или запустите `Stream Subtitle Translator.exe --reset-runtime`.
- Проверка обновлений:
  - desktop bootstrap launcher проверяет GitHub Releases автоматически и показывает окно только при наличии новой версии.
  - backend также содержит ручной endpoint проверки:
    - включите `updates.enabled` в `user-data/config.json`
    - выполните `POST /api/updates/check` (сохраняет `updates.latest_known_version` + `updates.last_checked_utc`).
- UI недоступен:
  - убедитесь, что локальный порт `8765` не занят.
- Дашборд ~20 с пустой или не кликается после splash (исправлено в сборках launcher `0.4.0`):
  - замените bootstrap exe на актуальный `0.4.0` из `dist\desktop-releases\v0.4.0\03-installers-both\` или publish-папки;
  - в `logs\desktop-launcher.log` запросы CSS/JS должны идти сразу после `GET /?desktop=1`, а не через ~20 с;
  - если пауза остаётся — `--repair` или `--reset-runtime`, чтобы `app-runtime/` совпал с новым payload.
- Web Speech не даёт текст:
  - выдайте browser microphone permission;
  - держите окно worker открытым и видимым;
  - если тестируете experimental path, делайте hard refresh после обновлений.
- Нет вывода в OBS:
  - проверьте OBS websocket settings и выбранный output mode.

## Автотесты

Tracked suite (GitHub-клон):

```
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

Для `0.4.2`: после правок запускай `python -m unittest discover -s tests`; публичный репозиторий — tracked subset (включая `test_browser_asr_observability`). Сборка bootstrap — только локально, см. [docs/TECHNICAL_ARCHITECTURE.md](./docs/TECHNICAL_ARCHITECTURE.md) §20.

## Приватность и границы выполнения

- SST Desktop работает в local-first режиме.
- Dashboard, API, websocket events, overlay, logs, profiles, cache и exports работают на одной машине.
- По умолчанию используется localhost (`127.0.0.1`).

## Версия релиза

- `0.4.2` (текущая линия кода)
- `0.4.1`
- `0.4.0`
- Single runtime source of truth: `backend/versioning.py` (`PROJECT_VERSION`).
