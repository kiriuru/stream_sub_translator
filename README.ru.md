# SST Desktop

**Преобразуйте голос в живые переводимые субтитры для стримов. Полностью локально, privacy-first, готово для OBS.**

<p align="center">
  <a href="./README.md">English</a> • <a href="./README.ru.md">Русский</a> •
  <a href="./docs/WIKI.en.md">Wiki (EN)</a> • <a href="./docs/WIKI.ru.md">Wiki (RU)</a> •
  <a href="./docs/TECHNICAL_ARCHITECTURE.en.md">Technical Docs (EN)</a> •
  <a href="./docs/TECHNICAL_ARCHITECTURE.md">Technical Docs (RU)</a> •
  <a href="./docs/CHANGELOG.md">Changelog</a>
</p>

SST Desktop — локальное Windows-приложение для стримеров и авторов, которым нужны субтитры в реальном времени с опциональным переводом. Оно объединяет live ASR, стилизацию субтитров, маршрутизацию и вывод в OBS в одном desktop-процессе. Проект local-first по умолчанию (`127.0.0.1`) и поддерживает как browser speech, так и local AI runtime paths. Текущая линия кода: `0.4.4`.

## ✨ Ключевые возможности

- 🎤 Распознавание речи в реальном времени (Local Parakeet или browser-based Web Speech workers)
- 🌍 Многоязычный перевод с большим набором провайдеров (`google_translate_v2`, `deepl`, `azure_translator`, `openai`, `openrouter`, `ollama`, и другие)
- 📺 Интеграция с OBS (Browser Overlay + опциональные OBS Closed Captions)
- 🎨 Кастомизируемые анимированные субтитры (пресеты, slot-based стили, эффекты, line overrides)
- 🔒 Privacy-first local-first runtime (localhost по умолчанию, локальные logs/profiles/exports)
- ⚡ Низкая задержка, оптимизированная для live streaming workflows
- 💾 Экспорт сессий в `SRT` и `JSONL`, плюс diagnostics ZIP export
- 🎭 Startup profiles для Web Speech quick start, GPU, CPU и remote ролей
- 🖥️ Опциональный LAN remote mode (controller/worker split между машинами)
- 🌙 Светлая/темная UI тема с настраиваемой accent gradient palette

## 📑 Содержание

- [🖥️ Системные требования](#️-system-requirements)
- [🚀 Быстрый старт](#-quick-start)
- [📦 Профили запуска](#-startup-profiles)
- [🌐 Локальные URL](#-local-urls)
- [🔧 Конфигурация и данные](#-configuration--data)
- [❓ Troubleshooting](#-troubleshooting)
- [🤝 Contributing](#-contributing)
- [💬 Support & Community](#-support--community)
- [🗺️ Roadmap](#️-roadmap)
- [📄 License](#-license)
- [🛠️ Для разработчиков: Архитектура и сборка](#️-for-developers-architecture--building)
- [📦 Для разработчиков: Сборка из исходников и desktop packaging](#-for-developers-building-from-source--desktop-packaging)
- [🔬 Для разработчиков: Runtime internals и hardening](#-for-developers-runtime-internals--hardening)

## 🖥️ System Requirements

- Windows 10/11 x64
- Доступ к микрофону
- Для GPU-режима: NVIDIA GPU + совместимый CUDA runtime stack
- Для внешних translation providers: интернет + валидные provider credentials

## 🚀 Quick Start

1. Скачайте последний `.exe` пакет из [GitHub Releases](https://github.com/kiriuru/stream_sub_translator/releases).
2. Распакуйте в папку с правом записи и запустите `Stream Subtitle Translator.exe`.
3. Выберите startup profile в splash окне.
4. Нажмите **Start** и говорите - субтитры появятся в preview и OBS.

📖 Для детальной настройки, интеграции с OBS, конфигурации перевода и расширенного тюнинга см. **[Wiki (EN)](./docs/WIKI.en.md)** и **[Wiki (RU)](./docs/WIKI.ru.md)**.

## 📦 Startup Profiles

| Профиль | Лучший сценарий | Примечания |
| --- | --- | --- |
| `Quick Start (Web Speech)` | Самый быстрый первый запуск | Browser worker path, пропускает local AI install |
| `NVIDIA GPU (CUDA)` | Минимальная задержка local AI на NVIDIA | Разворачивает CUDA PyTorch stack |
| `CPU-only` | Системы без NVIDIA | Разворачивает CPU-only local AI stack |
| `Remote Controller` | Dashboard/overlay машина в LAN split | Облегченная controller роль |
| `Remote Worker` | Выделенная LAN worker машина | AI worker роль с LAN bind |

Начиная с `0.4.0`, `Quick Start (Web Speech)` и `Stream Subtitle Translator Only Web.exe` выставляют `asr.desktop_profile_lock = browser_speech` в `user-data/config.json`; Local Parakeet разблокируется после следующего GPU/CPU запуска. См. раздел `0.4.0` в [docs/CHANGELOG.md](./docs/CHANGELOG.md).

## 🌐 Local URLs

- Dashboard: `http://127.0.0.1:8765/`
- Overlay: `http://127.0.0.1:8765/overlay`
- Web Speech worker: `http://127.0.0.1:8765/google-asr`
- Experimental worker: `http://127.0.0.1:8765/google-asr-experimental`
- Overlay query params: `?profile=default`, `?compact=1`

## 🔧 Configuration & Data

- `user-data/` - config, profiles, exports, models, cache, secrets, debug files
- `logs/` - launcher, backend, runtime и session logs
- `fonts/` - локальные font assets, используемые subtitle rendering
- `user-data/models/` - local AI model/runtime assets

Записи config на Windows атомарные (`os.replace()` flow). Поврежденные config/cache файлы карантинируются как `*.corrupt-<timestamp>.json`, и runtime безопасно откатывается через тот же migration/normalization pipeline.

## ❓ Troubleshooting

- Приложение не запускается: перезапустите и дайте bootstrap заново создать `app-runtime/`.
- Managed runtime поврежден: используйте **Repair Runtime** или `Stream Subtitle Translator.exe --repair`.
- Web Speech не возвращает текст: выдайте mic permission и держите worker окно открытым/видимым.
- Нет вывода в OBS: проверьте OBS websocket settings и выбранный output mode.
- UI недоступен: убедитесь, что локальный порт `8765` свободен.

Полный troubleshooting см. в User Wiki и в `Tools & Data -> Runtime Diagnostics` внутри приложения.

## 🤝 Contributing

PR приветствуются. Для больших изменений сначала откройте issue, чтобы scope и направление оставались согласованными.

Запуск тестов:

```powershell
python -m unittest discover -s tests
```

## 💬 Support & Community

- 📖 Документация: [Wiki (EN)](./docs/WIKI.en.md), [Wiki (RU)](./docs/WIKI.ru.md), [Technical Architecture (EN)](./docs/TECHNICAL_ARCHITECTURE.en.md), [Technical Architecture (RU)](./docs/TECHNICAL_ARCHITECTURE.md)
- 🐛 Bug Reports: [GitHub Issues](https://github.com/kiriuru/stream_sub_translator/issues)
- 💡 Feature Requests: [GitHub Discussions](https://github.com/kiriuru/stream_sub_translator/discussions)

## 🗺️ Roadmap

Идеи, не обязательства:

- Исследование более широкой OS-поддержки (возможность macOS/Linux)
- Больше вариантов локальных ASR моделей сверх текущего Parakeet path
- Дополнительные provider-level quality/latency инструменты
- Plugin-style extension points для интеграций и автоматизации
- Companion control surfaces для secondary/mobile устройств

## 📄 License

См. файл [LICENSE](./LICENSE) для подробностей.

<details>
<summary>🛠️ For Developers: Architecture & Building</summary>

## Architecture Summary

Текущая release architecture намеренно явная.

Backend:

- `backend/api/routes/` style separation для HTTP endpoints;
- `backend/services/` для route-facing orchestration;
- `backend/config/` для defaults, secrets, и normalization helpers;
- `backend/core/` для bootstrap, shared lifecycle, WS, subtitle routing, и runtime coordination;
- `backend/core/runtime/` для extracted runtime controllers, **thin `RuntimeOrchestrator` facade + mixins**, `LocalAsrPipeline`, и status builders;
- `backend/asr/parakeet/` для local AI runtime installation, diagnostics, и provider adapters;
- `backend/translation/` для provider registry, readiness checks, engine wiring, и provider-specific clients;
- `backend/schemas/` для typed config/runtime/diagnostics payloads.

Frontend:

- plain HTML/CSS/JS only;
- `frontend/js/main.js` как dashboard entrypoint;
- `frontend/js/core/` для store (isolated panel listeners), API, WS client, `dom.js` idempotent input helpers, event bus;
- `frontend/js/dashboard/` для actions/helpers/logging;
- `frontend/js/panels/` для dashboard panel wiring;
- `frontend/js/normalizers/` для pure normalization logic.

Это остается FastAPI-served desktop UI. Node.js, npm, React, Vite, Webpack, Electron, и Tauri не используются.

</details>

<details>
<summary>📦 For Developers: Building From Source & Desktop Packaging</summary>

## Building From Source

**Из публичного GitHub clone** (включает `backend/`, `frontend/`, `overlay/`, `tests/`, **`desktop/`**, и PyInstaller `*.spec` files):

- Разворачивайте и запускайте через `start.bat` (exe не требуется).
- Сборка bootstrap exe на Windows (venv с `requirements.desktop.txt`) через **локальные** `build-*.bat` и `publish-desktop-releases*.ps1` scripts (не в git - см. `.gitignore`). См. [Technical Architecture (EN)](./docs/TECHNICAL_ARCHITECTURE.en.md) раздел 14 и раздел 20 (или [RU version](./docs/TECHNICAL_ARCHITECTURE.md)).

**Desktop exe packaging** (build/publish scripts и outputs не коммитятся):

Build output:

- `dist\Stream Subtitle Translator\`
- bootstrap launchers:
  - `dist\bootstrap-launcher\Stream Subtitle Translator.exe`
  - `dist\bootstrap-launcher-web-only\Stream Subtitle Translator Only Web.exe`
- versioned release bundle (local): `dist\desktop-releases\v0.4.4\` (`01-bootstrap-onefile\`, `01-bootstrap-web-only-onefile\`, `02-managed-app-onefolder\`, `03-installers-both\`, `README.txt`) для этой линии; старые деревья могут по-прежнему содержать `v0.4.1\` или `v0.4.0\`.
- publish script defaults (оба exe попадают в каждую папку):
  - `F:\AI\stream-sub-translator-desktop-release`
  - `F:\AI\stream-sub-translator-desktop-release-clean`

Release package notes:

- `Stream Subtitle Translator.exe` - стандартный bootstrap (payload следует `PROJECT_VERSION`, сейчас `0.4.4`)
- `Stream Subtitle Translator Only Web.exe` - только Web Speech (добавлен в `0.4.0`; по-прежнему поддерживается)
- При первом запуске bootstrap launcher распаковывает managed runtime рядом с собой и запускает desktop runtime с диска.

</details>

<details>
<summary>🔬 For Developers: Runtime Internals & Hardening</summary>

## Runtime robustness (0.3.x)

Runtime/event stack значительно более защитный, чем в `0.2.9.2`, и `0.3.1` добавил больше структуры поверх `0.3.0`:

- `RuntimeOrchestrator` — facade над явными controllers в `backend/core/runtime/` (state, lifecycle, metrics, session, segments, browser-worker bookkeeping, speech sources, audio capture, processing tasks, translation runtime, transcript pipeline, output fanout).
- `SubtitleRouter` разделен на `subtitle_lifecycle_core.py` (FSM, TTL, relevance), `subtitle_presentation.py` (payload assembly, slot styling, partial/final merging), и тонкий publish facade.
- `TranslationDispatcher` restart-safe (`stop() -> start()` больше не ломает последующие сессии) и имеет per-provider concurrency/rate limits.
- `CacheManager` (`backend/core/cache_manager.py`) заменяет прежний read-modify-write JSON cache на in-memory LRU с debounced disk persistence и карантинирует поврежденные cache файлы в `*.corrupt-<timestamp>.json`.
- Запись config атомарна (`backend/core/atomic_io.py`, Windows-safe `os.replace()`). Поврежденный `user-data/config.json` ротируется в `*.corrupt-<timestamp>.json`, приложение стартует на defaults и проходит тот же migration/normalization pipeline.

Highlights, унаследованные и уточненные из `0.3.0`:

- `/ws/events` reconnect больше не должен так легко фризить dashboard;
- одинаковые runtime status flood события коалесцируются;
- dead WebSocket connections удаляются после send failures;
- Windows close/send ошибки считаются cleanup issues, а не fatal runtime failures;
- stale browser worker generations игнорируются;
- live event log storage ограничено и устойчивее при duplicate traffic;
- overlay/runtime event flow лучше подавляет stale translation mismatches.

## Web Speech Recognition Stability Hardening

Worker pipeline теперь добавляет несколько защит поверх базового supervisor, чтобы распознавание продолжало идти, когда ОС, сеть или Chrome могли бы молча деградировать его:

- **Screen Wake Lock**: когда распознавание активно и worker tab видим, worker вызывает `navigator.wakeLock.request("screen")` и отпускает lock на `Stop`. Это не дает ОС переводить систему в power-save режимы, где Chrome троттлит audio callbacks и Web Speech тихо стопорится. После visibility flip lock автоматически берется снова.
- **Earlier controlled session rotation**: `asr.browser.max_browser_session_age_ms` по умолчанию `180000` ms (было `240000` ms), что дает Chrome больший запас перед его собственным ~4-минутным тихим Web Speech kill. Окно `prepare_cycle_before_ms` сохраняется.
- **Network preflight terminal degradation**: после трех `network` ошибок примерно за 12 секунд worker один раз проверяет `https://www.google.com/generate_204` с коротким timeout. Если probe неуспешен, supervisor переходит в terminal `recognition_network_unreachable` вместо бесконечных restart loops.
- **`voice_below_recognition_threshold` signal**: отдельный от `web_speech_stalled` и `mic_silent`; срабатывает когда voice-level RMS есть, а распознавание остается тихим.
- **Chrome process priority and EcoQoS opt-out**: worker window запускается с `HIGH_PRIORITY_CLASS`; на Windows 10/11 launcher вызывает `SetProcessInformation(ProcessPowerThrottling, OPT_OUT)`.
- **Chrome feature gates disabled**: `CalculateNativeWinOcclusion`, `HighEfficiencyModeAvailable`, `HeuristicMemorySaver`, `IntensiveWakeUpThrottling`, `GlobalMediaControls`, плюс существующие background-throttling disable switches.

Эти hardening parts применяются и к classic Web Speech, и к Web Speech Experimental и не меняют `/api` или websocket payload contracts.

## Web Speech Live Smoke Checklist

- Откройте `/google-asr`, refresh страницу, и проверьте что language/toggles восстановились из worker-local settings.
- Запустите распознавание и убедитесь: одна spoken phrase дает interim text, затем один final segment без duplicate final spam.
- Помолчите несколько циклов и проверьте recovery через cooldowns, а не tight `onend`/`start()` loop.
- Обновите dashboard или дайте `/ws/asr_worker` reconnect и проверьте, что worker не создает второй active recognition instance.
- Отключите микрофон и проверьте деградацию diagnostics до `mic_silent` или `mic_track_unavailable`.
- Дайте force-finalization закрыть interim, затем проверьте что поздний browser final для той же фразы подавляется как late duplicate.
- После Start проверьте что Wake Lock удерживается во время распознавания и отпускается после Stop или `recognition_network_unreachable`.
- Заблокируйте Web Speech endpoints и проверьте что supervisor переходит в terminal `recognition_network_unreachable`.
- Перекройте Chrome worker window на Windows 11 и проверьте что partial/final flow продолжается.

## Web Speech Experimental

- Использует отдельное experimental worker window (`/google-asr-experimental`).
- Сначала открывает один live microphone `MediaStreamTrack`, затем вызывает `SpeechRecognition.start(audioTrack)`.
- Если браузер отклоняет `start(audioTrack)`, worker может fallback на обычный `recognition.start()`.
- Страница подключена к тому же controlled base FSM contract, что и classic worker.
- Поддержка браузеров может различаться; держите worker window видимым во время работы.

## Web Speech Experimental Smoke Checklist

- Откройте `/google-asr-experimental` и сделайте hard refresh.
- Запустите распознавание и проверьте либо `audio-track-start-success`, либо controlled fallback на `recognition.start()`.
- Быстро stop/start и убедитесь, что worker не застревает в постоянном `stopping`.
- Переподключите dashboard и убедитесь, что не появляется duplicate active recognition instance.
- Закройте/отзовите доступ к микрофону и проверьте явную degraded обработку.

## Config and Schema Notes

`0.3.x` сохраняет явный config contract, введенный в `0.3.0`, и усиливает его:

- config versioned и мигрирует явными шагами (`backend/core/config_migrations.py`, текущий `CURRENT_CONFIG_VERSION = 7` в `backend/schemas/config_schema.py`);
- config normalization находится в `backend/config/` (`defaults.py`, `secrets.py`, `normalizers/asr.py|browser.py|obs.py|remote.py|subtitles.py|translation.py|source_text_replacement.py`);
- profiles используют тот же migration/normalization pipeline;
- generated schema находится в `backend/data/config.schema.json` и публикуется через `python -m backend.core.config_schema_export`;
- `translation.lines` это slot-aware translation config surface (`translation_1..translation_5` с per-line `enabled`, `target_lang`, `provider`, `label`), legacy `translation.provider` и `translation.target_languages` сохранены для совместимости;
- legacy language-based `subtitle_output.display_order` значения мигрируют в slot ids вида `translation_1`;
- `/api/runtime/start` может применить optional normalized `config_payload` snapshot для runtime-only изменений без сохранения `user-data/config.json` (tracked через `active_config_source = runtime_start_snapshot`, `active_config_persisted = false`, `active_config_hash`);
- config writes атомарны на Windows (temporary file рядом + `os.replace()`); поврежденный `user-data/config.json` ротируется в `*.corrupt-<timestamp>.json` и defaults восстанавливаются;
- `backend/versioning.py` (`PROJECT_VERSION = "0.4.4"`) остается single source of truth.

## Remote Notes

В репозитории по-прежнему есть optional LAN remote controller/worker support:

- default desktop launch остается на `127.0.0.1`;
- `Remote Controller` и `Remote Worker` остаются explicit secondary flows;
- remote worker runtime AI-only и не должен запускать browser speech modes;
- remote worker sync предотвращает drift в browser-worker paths во время controller -> worker settings sync.

Рекомендуемый порядок запуска remote mode:

1. Сначала запустите worker machine через `Remote Worker` или `start-remote-worker.bat`.
2. Запустите controller machine через `Remote Controller` или `start-remote-controller.bat`.
3. Введите worker LAN URL в `Worker Base URL`.
4. Выполните `Check Worker Health` перед pairing/runtime start.
5. Создайте/проверьте local pair, затем refresh remote state.
6. Выполните `Sync Worker Settings`, затем `Prepare Remote Run`.
7. Запустите/проверьте worker runtime.
8. Держите controller и worker bridge windows открытыми, пока remote run активен.
9. Нажмите **Start** в controller dashboard, чтобы начать microphone capture и remote audio/result flow.

Experimental translation providers сохраняют `experimental` dashboard status вместо сворачивания в `degraded`.

## Local Data and Logs

Создаются рядом с executable:

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
  - browser/client logs по текущему runtime path

Legacy installs с `user-data/logs/` мигрируются в `logs/` на startup launcher/runtime.

Полезные diagnostics paths:

- backend/runtime failures: `logs/backend.log`
- structured runtime events: `logs/runtime-events.log`
- latest dashboard/overlay/browser-worker client events: `logs/session-latest.jsonl`

Runtime cache/temp paths управляются автоматически; первый запуск может быть дольше из-за инициализации.

## Desktop Dashboard Overview

Главное окно включает runtime badges (`health`, runtime state, ASR provider/device, partials, recognition mode, translation status, OBS CC status), **Start/Stop** controls, transcript/mic/mode/preview/local overlay URL/diagnostics panels.

`Start` отправляет in-memory config snapshot в `/api/runtime/start`, включая runtime-only unsaved changes, tracked как `active_config_source = runtime_start_snapshot`, `active_config_persisted = false`, и `active_config_hash`.

Dashboard settings UX (`0.4.1+`) использует idempotent DOM updates, так что focused inputs/carets не сбрасываются при panel rerenders.

## Main Tabs

### Translation

- Включение/выключение перевода.
- Выбор default provider для новых линий и legacy fallback behavior.
- Настройка credentials/endpoints/model/prompt where applicable.
- OpenAI-compatible helpers:
  - `GET /api/openai/recommended-models`
  - `POST /api/openai/models`
  - `POST /api/openai/usable-models`
- `Google Cloud Translation - Advanced (v3)` использует `project_id` + OAuth access token.
- Настройка до пяти slot-based lines (`translation_1 .. translation_5`), каждая с `enabled`, `target_lang`, `provider`, optional `label`.
- Slot cards рендерятся только для линий, присутствующих в `translation.lines`.
- Overlay/preview ordering следует стабильным slot ids.
- Translation fan-out асинхронный; stale lifecycle-irrelevant jobs отбрасываются.

### Subtitles

- Presets: `single`, `dual-line`, `stacked`, `compact`.
- Переключение source и translated visibility.
- Настройка max visible translated lines, lifetime behavior, и display order.
- Предыдущий completed translation остается видимым, пока новая фраза только partial; replacement происходит после finalization новой фразы и прихода перевода.

### Style

- Built-in presets и custom presets.
- Base style controls: font family/size/weight, color, outline, shadow, background, alignment, spacing, effects.
- Effects: `none`, `fade`, `subtle_pop`, `slide_up`, `zoom_in`, `blur_in`, `glow`.
- Slot-specific overrides.

### OBS

- OBS websocket host/port/password.
- Опциональный OBS Closed Captions output.
- Output mode: `source_live`, `source_final_only`, `translation_1` ... `translation_5`, `first_visible_line`.
- Опциональные debug mirror и partial/final timing controls.

### Tuning

- Recognition behavior sliders: appearance speed, finalize speed, stability/noise sensitivity.
- Опциональный RNNoise path.
- Точный Parakeet realtime-тюнинг — вкладка **ASR Advanced** (кнопка `?` у каждого поля, однострочные «рекомендуемое» подсказки).

### Tools & Data

- Runtime diagnostics/latency metrics.
- Translation queue/provider state, Web Speech connectivity, OBS CC state, log locations.
- Live event feed, localization coverage, config/profile import-export controls.
- `Export Diagnostics` создает локальный ZIP с redacted config, runtime/preflight snapshots, session log, backend log.

### Help

- Topic tabs: overview, recognition and tuning, translation, subtitles and style, OBS, tools and diagnostics, desktop and remote mode.
- Remote topic включает startup sequence, pairing order, bridge window notes, и field descriptions.

## Recognition Modes

### Local Parakeet

- Local runtime с local audio capture path.
- GPU-first policy на совместимых NVIDIA системах.
- CPU fallback доступен.
- `Recognition -> Backend ASR provider` предлагает только **Official EU Parakeet Low Latency** (`official_eu_parakeet` migrates в low latency).
- Tuning presets: `ultra_low_latency`, `balanced`, `quality`, `custom`.

### Web Speech

- Profile lock behavior после quick-start paths (`asr.desktop_profile_lock = browser_speech`).
- Выделенное Chrome worker window (`/google-asr`) с изолированным `user-data-dir`.
- Desktop behavior фиксирован: address-bar window mode (`--new-window`), без app-mode toggle.
- Worker launch browser setting в desktop: `asr.browser.worker_launch_browser` (`auto` или `google_chrome`, оба идут в Chrome).
- Нужны mic permission и видимое worker window для стабильной работы.
- Controlled lifecycle supervisor, restart cooldowns, generation-aware reconnects, duplicate suppression, mic health diagnostics, localStorage-first worker settings.

## Overlay and OBS URLs

- Dashboard: `http://127.0.0.1:8765/`
- Overlay page: `http://127.0.0.1:8765/overlay`
- Web Speech worker page: `http://127.0.0.1:8765/google-asr`
- Web Speech experimental worker page: `http://127.0.0.1:8765/google-asr-experimental`
- Overlay query examples: `?profile=default`, `?compact=1`

Overlay остается отдельной lightweight page для OBS Browser Source и auto-reconnect после websocket drops.

## First Launch Behavior and Update Procedure

Public release начинается только с `Stream Subtitle Translator.exe`.

На первом запуске bootstrap извлекает/создает:

- `.sst-runtime.exe`
- `app-runtime/`
- `.python/`
- `.venv/`
- `user-data/`
- `logs/`
- `user-data/models/`
- `fonts/`

Launcher ротирует прошлый `logs/desktop-launcher.log` в `desktop-launcher.old.log` на каждом запуске.

Чтобы обновить:

1. Закройте приложение.
2. Замените public `Stream Subtitle Translator.exe`.
3. Сохраните существующие `.python/`, `.venv/`, `user-data/`, и `fonts/`, чтобы сохранить local state.
4. При необходимости используйте `--repair` или `--reset-runtime` (или splash maintenance buttons).

## Troubleshooting (Extended)

- Managed runtime поврежден: **Repair Runtime** или `Stream Subtitle Translator.exe --repair`.
- Полный managed runtime reset: **Reset Runtime** или `Stream Subtitle Translator.exe --reset-runtime`.
- Проверки обновлений:
  - launcher автоматически проверяет GitHub Releases и показывает prompt только при наличии обновления;
  - backend manual endpoint: включите `updates.enabled` в `user-data/config.json`, затем `POST /api/updates/check`.
- Dashboard blank/unresponsive после splash (legacy `0.4.0` issue): обновите launcher build, проверьте `logs\desktop-launcher.log`, используйте repair/reset если payload mismatch сохраняется.

## Automated Tests

GitHub-tracked suite:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

Для `0.4.4` запускайте:

```powershell
python -m unittest discover -s tests
```

## Privacy and Runtime Scope

- Local-first design.
- Dashboard/API/websocket/overlay/logs/profiles/cache/exports работают на той же машине.
- Default bind target: localhost (`127.0.0.1`).

## Release Version

- `0.4.4` (current code line)
- `0.4.3`
- `0.4.1`
- `0.4.0`
- Version source of truth: `backend/versioning.py` (`PROJECT_VERSION`)

</details>
