# VoiceSub — WIKI

Операционный гайд по интерфейсу VoiceSub `0.5.0`. Формат описания элементов: **что это**, **зачем**, **как работает**, **на что влияет**, **типовые ошибки**.

Техническая архитектура: `docs/TECHNICAL_ARCHITECTURE.md`. Предшественник SST `0.4.4` — только reference; поведение core описано здесь для VoiceSub.

---

## 0. О продукте и версии

### Элемент: VoiceSub vs SST
- **VoiceSub** — активная линия `0.5.0` (Rust + Tauri + Svelte).
- **SST** `0.4.4` — frozen reference; настройки импортируются, но режимы Parakeet/Remote/Experimental в core не поднимаются.
- **Overlay URL новый:** `http://127.0.0.1:8765/overlay` — обновите Browser Source в OBS вручную.

### Элемент: системные требования
- **Windows 10/11 x64**
- **WebView2 Runtime** — обязателен для `VoiceSub.exe` (dashboard в Tauri/WebView2, окно `/tts`). Без WebView2 приложение не запустится. На Win11 чаще уже есть; на Win10 установщик может предложить bootstrapper.
- **Google Chrome** — отдельно, для окна Web Speech worker (`/google-asr`), не путать с WebView2.
- Микрофон в Chrome worker; интернет — для внешних провайдеров перевода (опционально).

### Элемент: установка и обновление (NSIS)
- **Что делает:** `VoiceSub_0.5.0_x64-setup.exe` ставит `VoiceSub.exe` и статические ресурсы (`bin/dashboard`, overlay, worker, tts).
- **Для чего:** один установщик без Python/Node в runtime; при отсутствии WebView2 — загрузка через bootstrapper (`downloadBootstrapper` в Tauri).
- **Обновление:** закройте приложение → запустите новый `setup.exe` поверх → `user-data/` и `logs/` сохраняются рядом с install path / project root.
- **Разработчикам:** `build-release-msi.bat` → `build-release.ps1` → `F:\AI\VoiceSub - release\v{version}\`.
- **Проверка обновлений:** при старте dashboard опрашивает GitHub Releases (`POST /api/updates/check`). Если на GitHub версия новее установленной — баннер сверху («Доступна VoiceSub X — у вас Y»). **Скачать** открывает страницу release в системном браузере. Настройки: `user-data/config.toml` → `[updates]` (`enabled`, `github_repo`, `check_interval_hours`). Секция подставляется автоматически при апгрейде со SST.

### Элемент: локальные URL
| URL | Назначение |
| --- | --- |
| `/` | Svelte dashboard |
| `/overlay` | OBS Browser Source |
| `/google-asr` | Browser Speech worker |
| `/tts` | TTS-модуль |

---

## 1. Быстрый старт

### Элемент: первый запуск
1. Запустите **VoiceSub.exe**.
2. Dashboard откроется в главном окне Tauri (`http://127.0.0.1:8765/`).
3. Добавьте в OBS Browser Source: `http://127.0.0.1:8765/overlay`.
4. Настройте язык UI (Settings), перевод (Translation) при необходимости.
5. Нажмите **Start** — откроется окно Chrome с `/google-asr?autostart=1`.
6. Разрешите микрофон в Chrome и говорите.

### Элемент: панель runtime (Start / Stop)
- **Start:** `POST /api/runtime/start` — запуск worker, translation, OBS CC, ingest ASR.
- **Stop:** останавливает worker (включая kill Chrome), сбрасывает subtitle state.
- **Важно:** Start отправляет текущий config snapshot, в том числе несохранённые изменения с момента последнего Save (если были).

### Элемент: предпросмотр субтитров (overview)
- **Что делает:** в верхней области «Предпросмотр субтитров» показывает placeholder до Start и live payload после.
- **Зачем:** калибровка стиля без запущенного ASR; пустой `overlay_update` после Save не затирает preview.
- **Подробно:** `TECHNICAL_ARCHITECTURE.md` §20 (Idle subtitle preview).

### Элемент: компактный макет
- **Что делает:** переключает окно Tauri (~390×844) и навигацию с pane **Live** + вкладки настроек.
- **Где:** кнопка layout в chrome или command palette (`Переключить компактный макет`).
- **IPC:** Tauri `set_dashboard_layout`.

---

## 2. Диагностика: если «не работает»

### Сценарий: нет вообще никакого текста
- Runtime запущен (**Start**)?
- Окно Chrome `/google-asr` открыто и **видимо** (не свёрнуто надолго)?
- Микрофон разрешён в Chrome (не только в Windows)?
- Вкладка **Tools & Data** → runtime diagnostics: `browser_worker_connected`?

### Сценарий: исходный текст есть, перевода нет
- Вкладка **Translation** → перевод включён.
- Хотя бы одна линия `translation_N` с `enabled`.
- Блок результатов перевода / diagnostics — ошибки ключа, endpoint, квоты.

### Сценарий: в OBS пусто
- Browser Source URL = `/overlay` (не dashboard `/`).
- **Subtitles** → видимость source/translation включена.
- TTL не слишком короткий (текст может мелькать и исчезать).
- После reconnect overlay держит последний кадр (stale-guard + backoff 1–10 с) — это нормально.
- Текст **не исчезает после TTL/Stop** — обновите приложение и перезагрузите Browser Source (`disposeRenderContainer` + `hasVisibleRenderedFrame`, `overlay.js?v=20260610b`).

### Сценарий: worker отваливается
- Проверьте сеть (Web Speech идёт через Google).
- `logs/browser-trace.jsonl` при `VOICESUB_TRACE_BROWSER=1`.
- Перезапуск: **Stop** → **Start** или перезапуск worker из Tools.

---

## 3. Вкладки dashboard

| Вкладка | Назначение |
| --- | --- |
| **Translation** | Провайдеры, линии перевода, кэш, лимиты диспетчера |
| **Subtitles** | Пресет overlay, видимость, порядок, TTL lifecycle |
| **Style** | Шрифты, цвета, эффекты, слот-стили, custom presets |
| **UI Theme** | Тёмная/светлая тема, accent palette |
| **OBS** | Overlay URL, Closed Captions, debug mirror |
| **Word Replace** | Замена текста до перевода |
| **Tools & Data** | Профили, диагностика, экспорт ZIP |
| **Settings** | Язык UI, layout, импорт SST config, Web Speech advanced |
| **Help** | Встроенные темы справки |

**Command palette** (`Ctrl+K` / поиск в header): быстрый переход, Start/Stop, Save, export diagnostics.

---

## 4. Распознавание (Browser Speech)

### Элемент: единственный production-режим core 0.5.0
- **`browser_google`** — Web Speech в отдельном окне Chrome.
- Микрофон выбирается **в Chrome** (`getUserMedia`), не в dashboard.
- `/api/devices/audio-inputs` пустой — by design.

### Элемент: окно browser worker
- **Отдельное окно** с **видимой адресной строкой** (не app-mode, не скрытая вкладка).
- URL: `http://127.0.0.1:8765/google-asr?autostart=1[&locale=…]`.
- Изолированный Chrome profile: `user-data/browser-worker-profile-classic-*`.
- Anti-throttle flags + EcoQoS opt-out (Windows).

### Элемент: язык распознавания
- **Settings** → Web Speech / `asr.browser.recognition_language`.
- Worker UI может показывать live/final текст и диагностику WS.
- Если dashboard пуст, но worker показывает текст — проблема на стороне ingest/WS, не Chrome.

### Элемент: расширенные настройки Web Speech
- **Settings** → блок «Расширенные настройки Web Speech» (`asr.browser.*`).
- Группы: forced final, restart, network reconnect, session rotation, partial filtering.
- После изменений: Save config → при необходимости **Stop/Start** и переоткрытие worker.

### Элемент: устойчивость worker (наследие SST, портировано)
- Screen Wake Lock при активном распознавании.
- Session rotation `max_browser_session_age_ms` (default 180000 ms).
- Network preflight → terminal `recognition_network_unreachable` после серии network errors.
- Force-finalization при залипшем partial.

**Не доступно в core:** local Parakeet, experimental `/google-asr-experimental`, remote ingest.

---

## 5. Перевод

### 5.1 Основные переключатели

#### Элемент: включение перевода
- Включает/выключает translation pipeline.
- ASR работает и без перевода (source-only).

#### Элемент: кэш переводов
- **В памяти:** не дублировать запросы к провайдеру.
- **На диск:** `user-data/translation-cache/` между сессиями.
- **Риск:** старый кэш при смене промпта LLM может давать устаревший стиль.

### 5.2 Линии перевода (слоты `translation_1`…`translation_5`)

- До **5** независимых линий: `enabled`, `target_lang`, `provider`, `label`.
- Каждая активная линия — отдельная нагрузка на dispatcher.
- Порядок отображения — **Subtitles** → display order (slot ids).

### 5.3 Провайдеры (13)

`google_translate_v2` (default), `google_cloud_translation_v3`, `google_gas_url`, `google_web`, `azure_translator`, `deepl`, `libretranslate`, `openai`, `openrouter`, `lm_studio`, `ollama`, `public_libretranslate_mirror`, `free_web_translate`.

- OpenAI-compatible helpers: `/api/openai/recommended-models`, `/api/openai/models` (static list).
- Поля credentials в `translation.provider_settings` — хранятся локально в `config.toml`.

### 5.4 Диспетчер перевода
- Таймаут, размер очереди, max concurrent jobs.
- Per-provider limits (`provider_limits`).
- **Lifecycle:** завершённый блок остаётся до финализации новой фразы; late translations разрешены; stale drop только для устаревших in-flight jobs.

### 5.5 Блок результатов перевода
- Показывает последние переводы и ошибки провайдера.
- Задержка перевода ≠ всегда ошибка (supersession / stale protection).

---

## 6. Вывод субтитров (Subtitles)

### Элемент: пресет overlay
- `single`, `dual-line`, `stacked`, `compact`.
- Query override: `?preset=…&compact=1`.

### Элемент: видимость
- Source / translations toggles.
- Max visible translation lines (cap по порядку).

### Элемент: TTL и lifecycle
- `completed_block_ttl_ms`, source/translation TTL.
- Sync flags: держать source пока виден перевод.
- **Ключевой смысл:** завершённый перевод виден, пока новая фраза ещё partial; замена — после final новой фразы.

### Элемент: порядок строк
- Влияет на dashboard preview, OBS overlay и OBS CC mode `first_visible_line`.

---

## 7. Стиль субтитров (Style)

- Built-in и custom presets.
- Base controls: font, size, weight, color, outline, shadow, background, alignment, spacing.
- Effects: `none`, `fade`, `subtle_pop`, `slide_up`, `zoom_in`, `blur_in`, `glow`.
- Per-slot overrides: `source`, `translation_1`…`translation_5`.
- **Единый payload** для dashboard preview и OBS overlay.
- Сохраняйте config/profile после правок.

---

## 8. Тема UI (Theme)

- Dark / light mode.
- Accent palette (primary, secondary, tertiary gradients).
- Влияет только на dashboard chrome, не на OBS overlay (overlay — subtitle-style config).

---

## 9. OBS

### Элемент: overlay URL
- Копируется из вкладки **OBS** (`GET /api/obs/url`).
- Default: `http://127.0.0.1:8765/overlay`.
- При смене bind (LAN) обновите URL в OBS.

### Элемент: OBS Closed Captions
- WebSocket host/port/password (OBS v5).
- Output mode: source live/final, translation slots, first visible line.
- Timing: partial throttle, min delta, clear after ms, dedupe.
- Debug mirror — текстовый источник для отладки CC.

---

## 10. Замена слов (Word Replace)

- Правила find/replace **до** перевода и вывода.
- Built-in profanity lists (en, ru, ja, ko, zh).
- Case-insensitive / whole words only.
- Синхронизация с TTS: `tts_sync_source_text_replacement` (если TTS включён).

---

## 11. TTS-модуль

### Элемент: окно `/tts`
- Отдельный UI: вкладки **Speech** и **Twitch**.
- Открытие: из dashboard или Tauri IPC `tts_open_window`.

### Элемент: Speech
- Провайдер TTS, голос, rate/pitch/volume.
- Audio routing: browser element или WinAPI per-process (`VOICESUB_TTS_PER_PROCESS_ROUTING`).
- Планировщик речи от subtitle payload (`tts_plan_subtitle_speech`).

### Элемент: Twitch
- OAuth через system browser.
- IRC chat → очередь озвучки.
- Фильтры, emotes, replacements (crate `voicesub-twitch`).

### Элемент: Python sidecar
- `bin/modules/tts/runtime/` — embedded fetcher для Google TTS proxy.
- `/api/tts/python/status` — probe runtime.

---

## 12. Инструменты и данные (Tools & Data)

### Элемент: Runtime Diagnostics
- Phase, worker connected, translation queue, OBS CC state, metrics.
- Пути к логам: `logs/core.log`, `runtime-events.log`, `session-latest.jsonl`.

### Элемент: профили
- CRUD через UI → `user-data/profiles/{name}.toml`.
- Быстрое переключение сценариев стрима.

### Элемент: Export Diagnostics
- ZIP: redacted config, runtime status, session log, core log.
- `GET /api/exports/diagnostics`.

### Элемент: глубокая диагностика (env)
- `VOICESUB_DEEP_DIAGNOSTICS=1` или `logging.full_enabled` в config.
- Per-channel: `VOICESUB_TRACE_SUBTITLE`, `_BROWSER`, `_WS`, `_TTS`, …

---

## 13. Настройки (Settings)

### Элемент: язык интерфейса (EN / RU / JA / KO / ZH)
- Svelte i18n: `src/lib/i18n/locales/*.json`.
- Сохраняется в `ui.language` → Save config.
- Worker получает `locale` query param при launch.
- Overlay i18n: `bin/overlay/shared/js/i18n/`.
- **Подробно:** `TECHNICAL_ARCHITECTURE.md` §23.

### Элемент: импорт SST config.json
- Миграция в `config.toml`, `config_version` → 8.
- `local` / `remote` / experimental → `browser_google` + import hint.
- `ui.show_remote_tools` → false.

### Элемент: layout
- `standard` vs `compact` — влияет на Tauri window size.

---

## 14. Справка (Help)

Встроенные темы: обзор, распознавание, перевод, субтитры/стиль, OBS, инструменты. Без раздела remote mode (удалён из core).

---

## 15. Локализация и приватность

- **Local-first:** default `127.0.0.1`; LAN только `VOICESUB_ALLOW_LAN=1`.
- API keys и Twitch tokens — только на диске пользователя.
- Diagnostics export — redacted secrets.
- Chrome worker — isolated profile, без sync.

---

## 16. Глоссарий

| Термин | Значение |
| --- | --- |
| **partial** | Черновой распознанный текст |
| **final** | Зафиксированная фраза |
| **translation slot** | Линия `translation_1`…`translation_5` |
| **overlay** | Vanilla страница `/overlay` для OBS |
| **browser worker** | Окно Chrome с Web Speech |
| **completed block** | Финальный субтитр до следующей финализации |
| **TTS module** | Sidecar `/tts` + Rust service |

---

## 17. Архивные возможности (не в core 0.5.0)

| Было в SST | Статус в VoiceSub |
| --- | --- |
| Local Parakeet | `legacy/modules-source/parakeet/` → модуль Phase 4 |
| Remote controller/worker | `legacy/remote/` → будущий модуль |
| Experimental browser | `legacy/experimental-browser/` — удалён из routes |
| PyInstaller bootstrap | Заменён Tauri NSIS installer |
| Splash startup profiles | Нет — единый `VoiceSub.exe` |

Для parity-поведения browser/translation/subtitle см. golden tests в `tests/golden/`.
