# TTS Dual Sink + Native Playback — опорный план реализации

**Статус:** реализовано в **0.5.1** (2026-06-13); reference для post-MVP  
**Дата:** 2026-06-13 (обновлено)  
**Продукт:** VoiceSub `0.5.1`  
**Модуль:** TTS (`src-tts/`, `crates/voicesub-tts/`, `crates/voicesub-audio/`)

---

## 0. Как агентам пользоваться этим документом

### 0.1 Не следовать слепо

Этот файл — **опорная гипотеза и черновик архитектуры**, собранный из обсуждений. Репозиторий, версии crate'ов, API Tauri/cpal/rodio и поведение Windows **могут расходиться** с текстом ниже.

**Обязательно перед реализацией и при любой неясности:**

1. **Свериться с каноническими источниками в репозитории** (список §12).
2. **Прочитать актуальный код** затрагиваемых файлов — план может устареть.
3. **Искать решения в интернете** (документация crate'ов, GitHub issues cpal/rodio/Tauri, Stack Overflow, WebView2 Feedback) — особенно для:
   - выбора устройства WASAPI / `cpal::Device`;
   - параллельных `OutputStream` / `Sink`;
   - передачи бинарных данных через Tauri IPC;
   - ограничений `rodio` (Send/Sync, lifetime `OutputStream`).
4. **Не ломать рабочую логику** fetch, planner, Twitch IRC, proxy — менять только playback/routing, если задача не говорит иное.
5. Следовать **`AGENTS.md`** (локально): тесты с новым Rust-кодом, `tracing`, без бизнес-логики в `src-tauri`.

### 0.2 Когда документ и код расходятся

| Приоритет | Действие |
| --- | --- |
| 1 | **Код и контракт** (`ENGINEERING_CONTRACT`, golden tests) |
| 2 | **`docs/TECHNICAL_ARCHITECTURE.md` §17** (если обновлён) |
| 3 | **Этот план** — как намерение, уточнять у пользователя при крупном отклонении |
| 4 | **Внешние источники** — для API/платформенных деталей |

После существенных отклонений от плана — **обновить этот файл** или оставить комментарий в PR/issue (кратко: что изменилось и почему).

---

## 1. Цель

Разделить озвучивание **субтитров/переводов** (`speech`) и **Twitch-чата** (`twitch`) на **два независимых аудиоканала** с:

- **разными устройствами вывода** (типично: VB-Cable → OBS vs наушники стримера);
- **параллельным воспроизведением** (чат не ждёт окончания перевода);
- **надёжным playback в Rust** (WASAPI через `cpal`/`rodio`), без зависимости от `HTMLAudioElement.setSinkId()` в production.

### 1.1 Не-цели (на первую итерацию)

- Переписывать Google TTS proxy / Python sidecar.
- Менять `SubtitleSpeechPlanner` / Twitch filter pipeline (кроме enqueue в правильный канал).
- WinAPI per-process routing (`VOICESUB_TTS_PER_PROCESS_ROUTING`) — **не использовать** для dual sink.
- OBS «Streamer preset» — опционально после MVP.

---

## 2. Текущее состояние (baseline)

Сверять с кодом; цифры и пути — ориентир на 2026-06-10.

### 2.1 Поток данных сегодня

```text
subtitle_payload (WS) ──┐
                        ├──► один SpeechEngine (JS) ──► prefetch MP3 ──► HTMLAudioElement + setSinkId
twitch_chat (WS) ───────┘
```

- UI: `src-tts/App.svelte`, движок: `src-tts/lib/speech-engine.ts`.
- Fetch: `src-tts/lib/google-tts.ts` → `/api/tts/google` | `/api/tts/python`.
- Конфиг: `user-data/modules/tts/config.toml` — **одно** поле `audio_output_device_id`.
- Rust `SpeechQueue` + IPC `tts_enqueue` — **не участвуют** в реальном playback (прототип).

### 2.2 Audio routing сегодня

| Режим | Условие | Механизм |
| --- | --- | --- |
| `browser` | по умолчанию | `setSinkId` + `enumerateDevices` / `selectAudioOutput` |
| `winapi` | `VOICESUB_TTS_PER_PROCESS_ROUTING=1` | `SetPersistedDefaultAudioEndpoint` на PID окна |

Известные проблемы: browser `deviceId` ≠ WASAPI endpoint ID; WebView2 audio ненадёжен; per-process — один device на процесс, PID renderer ≠ host.

### 2.3 Ключевые пути в репозитории

| Что | Где |
| --- | --- |
| TTS UI | `src-tts/` → `bin/tts/` |
| Speech engine | `src-tts/lib/speech-engine.ts` |
| Google TTS fetch | `src-tts/lib/google-tts.ts` |
| Browser devices | `src-tts/lib/browser-audio-output.ts` |
| Tauri IPC | `src-tauri/src/tts.rs` |
| TTS service | `crates/voicesub-tts/src/service.rs` |
| Subtitle planner | `crates/voicesub-tts/src/subtitle_speech.rs` |
| WASAPI enum | `crates/voicesub-audio/src/platform.rs` |
| HTTP proxy | `crates/voicesub-runtime/src/http/tts_proxy.rs` |
| Twitch IRC | `crates/voicesub-twitch/` |
| Архитектура §17 | `docs/TECHNICAL_ARCHITECTURE.md` |

---

## 3. Целевая архитектура

### 3.1 Принципы

1. **Dual channel:** `speech` | `twitch` — отдельные очереди, device, volume, rate (twitch может наследовать root defaults).
2. **Native playback primary:** Rust воспроизводит MP3; WebView — UI + orchestration (MVP) или только UI (позже).
3. **Strategy fallback:** `playback.mode = "native" | "browser"` — browser path для отката и регрессии.
4. **Идентификация устройств:** **label-first** (WASAPI friendly name / `cpal` device name); browser `deviceId` deprecate.
5. **Параллельность:** два worker'а playback (по одному на канал), не один глобальный mutex на звук.
6. **Расширять `voicesub-audio`**, а не плодить дублирующий crate (рабочее имя модуля: `playback`).

### 3.2 Диаграмма (целевая)

```text
┌─ src-tts ─────────────────────────────────────────────────────┐
│ speechEngine(channel=speech)    twitchEngine(channel=twitch)     │
│   prefetch (google-tts.ts) — без изменений логики fetch          │
│   AudioPlayer (Strategy)                                         │
│     NativeAudioPlayer → IPC                                      │
│     HtmlAudioPlayer   → fallback (setSinkId)                     │
│   listen playback-finished → pump next item                        │
└────────────────────────────┬────────────────────────────────────┘
                             │ Tauri invoke + events
┌────────────────────────────▼────────────────────────────────────┐
│ src-tauri — thin IPC only                                        │
│   tts_play_audio / tts_stop_channel / tts_set_channel_device     │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│ voicesub-audio::PlaybackHub (новое)                              │
│   speech_worker: dedicated thread + OutputStream + play queue    │
│   twitch_worker:  dedicated thread + OutputStream + play queue   │
│   resolve_device(label) → cpal::Device                           │
│   play_mp3(bytes, volume, rate) → completion notify              │
└──────────────────────────────────────────────────────────────────┘
```

### 3.3 Альтернатива (post-MVP, не блокирует старт)

Перенести fetch в Rust (`enqueue(text, lang, channel)` → proxy уже в `voicesub-runtime`) и **не передавать MP3 bytes через IPC**. При реализации сверить latency и сложность с текущим prefetch в JS.

---

## 4. Конфигурация

### 4.1 Целевая схема `config.toml`

```toml
enabled = true
tts_provider = "browser_google"   # без изменений: кто fetch'ит MP3

# Режим воспроизведения: "native" | "browser"
playback_mode = "native"          # первый релиз feature: default "browser" до QA

# Speech / subtitles (корневые поля — speech channel)
audio_output_device_label = ""    # primary key
audio_output_device_id = ""       # deprecated: WASAPI id, optional hint
speech_rate = 1.0
speech_volume = 1.0

[speech]
speak_source = true
speak_translations = true
translation_slots = []
min_chars = 2
max_queue_items = 8

[twitch]
enabled = false
# ... существующие поля TwitchTtsSettings ...
audio_output_device_label = ""    # NEW
audio_output_device_id = ""       # NEW, optional
speech_rate = 1.0                 # NEW, optional override
speech_volume = 0.8               # NEW, optional override
max_queue_items = 6               # NEW, optional
```

### 4.2 Миграция

- Существующий root `audio_output_device_id` / `label` → остаются для **speech**.
- `[twitch].audio_output_device_*` — пустые по умолчанию (**не копировать** speech device в twitch).
- Старые browser-only ID не использовать в native mode; при первом запуске native — предложить перевыбор из WASAPI list.

---

## 5. Реализация по слоям

### 5.1 `voicesub-audio` — playback

**Задачи (чеклист):**

- [ ] Модуль `playback` (или `hub.rs`): `PlaybackHub` с двумя каналами.
- [ ] **Dedicated thread на канал**; `OutputStream` хранить живым на время воспроизведения (проверить по docs rodio — droop stream = silence).
- [ ] Воспроизведение через **rodio** (предпочтительно) с MP3 decoder; версию crate сверить с workspace / совместимостью Windows.
- [ ] `resolve_device(label) -> Device` — сопоставление с `list_output_devices()`; при промахе — default + `tracing::warn`.
- [ ] `play(channel, bytes, item_id, volume, rate)` — блокирующее на worker thread; по завершении — callback / channel completion.
- [ ] `stop(channel)` — прерывание текущего sink.
- [ ] Unit tests: decode sample MP3 fixture; resolve label; error on empty bytes.
- [ ] **Не** зависеть от `tauri` внутри `voicesub-audio`.

**Предупреждения (проверить в issues/docs):**

- `Sink` / `OutputStream` may not be `Send` — не тащить между tokio tasks без проверки.
- `sleep_until_end()` блокирует — только worker thread.
- Имена устройств WASAPI vs `cpal::Device::name()` могут отличаться — при необходимости хранить mapping при enumeration.

### 5.2 `src-tauri` — IPC

Тонкая обёртка; логика в `voicesub-audio` + `voicesub-tts`.

**Команды (черновик имён):**

| Command | Назначение |
| --- | --- |
| `tts_play_audio` | `channel`, `item_id`, `audio_bytes`, `volume`, `rate` |
| `tts_stop_channel` | остановить текущий clip канала |
| `tts_set_channel_device` | `channel`, `device_label` (+ optional id hint) |
| `tts_get_playback_mode` / `tts_set_playback_mode` | native vs browser |

**События:**

```json
{ "channel": "speech"|"twitch", "item_id": "...", "ok": true, "error": null }
```

Emit из `src-tauri` после completion callback из `PlaybackHub`.

**Передача bytes:** использовать эффективный тип Tauri (`Vec<u8>` / `Uint8Array`) — **не** `Array.from` на больших буферах. Сверить с актуальной документацией Tauri 2.

Расширить существующие:

- `tts_set_audio_device` → channel-aware или заменить на `tts_set_channel_device`.
- `tts_list_output_devices` — при необходимости добавить поле для rodio/cpal lookup.

### 5.3 `src-tts` — TypeScript

**Задачи:**

- [ ] Интерфейс `AudioPlayer` + `NativeAudioPlayer` + `HtmlAudioPlayer` (Strategy).
- [ ] `SpeechEngine` принимает `channel` + `player`; логика очереди/prefetch **минимально** меняется.
- [ ] Два экземпляра в `App.svelte`: `speechEngine`, `twitchEngine`.
- [ ] `planSubtitleSpeech` → `speechEngine.enqueue`; Twitch WS → `twitchEngine.enqueue`.
- [ ] `runtime stop` → `clear()` на обоих.
- [ ] UI: device selector на вкладке **Twitch**; speech — в header или speech tab.
- [ ] Списки устройств только из `tts_list_output_devices` в native mode.
- [ ] `listen('playback-finished')` с фильтром по `channel`.
- [ ] `ttsTrace` — поле `channel` во всех playback событиях.

### 5.4 `voicesub-tts` / `voicesub-twitch`

- [ ] Поля `audio_output_device_*`, `speech_rate`, `speech_volume`, `max_queue_items` в `TwitchTtsSettings` (`crates/voicesub-twitch/src/settings.rs` + `src-tts/lib/types.ts`).
- [ ] Сериализация в `config.toml`.
- [ ] **Post-MVP:** подключить Rust `SpeechQueue` к playback или удалить/deprecate `tts_enqueue` с документацией.

---

## 6. Fallback (browser)

Оставить существующий путь `google-tts.ts` → `HTMLAudioElement` + `setSinkId` при `playback_mode = "browser"`.

- Не инвестировать в label↔browserId стабилизацию для production.
- Acceptance: при `browser` режиме поведение **не хуже** текущего 0.5.0 до изменений.

---

## 7. Тестирование

### 7.1 Автоматические

- Rust unit: decode MP3, device resolve, empty/corrupt input.
- `cargo test --workspace` перед merge.
- При наличии: Vitest для `NativeAudioPlayer` mock invoke (опционально).

### 7.2 Ручные (Windows)

| Сценарий | Критерий |
| --- | --- |
| VB-Cable + наушники | speech на Cable, twitch на phones одновременно |
| Быстрый чат во время длинного перевода | чат слышен без ожидания конца перевода |
| Смена device в UI | следующий clip на новом устройстве |
| `playback_mode=browser` | регрессия: как раньше |
| Runtime stop | обе очереди очищены, звук остановлен |
| Отключение USB-устройства | ошибка в логе, очередь не зависает |

### 7.3 Trace

- `VOICESUB_TRACE_TTS=1` → `logs/tts-trace.jsonl`
- События: `playback_start`, `playback_end`, `playback_error`, `device_resolve`, `channel`

---

## 8. Риски и смягчение

| Риск | Смягчение |
| --- | --- |
| Несовпадение label WASAPI / cpal | mapping при enum; exact + contains match; логировать кандидатов |
| rodio/cpal regression на конкретной сборке Windows | feature flag; fallback browser |
| IPC latency на больших MP3 | prefetch; позже fetch в Rust |
| Два OutputStream — артефакты/CPU | shared mode WASAPI; тест на целевых машинах |
| Дублирование очереди JS/Rust | MVP JS; consolidation documented as post-MVP |

При расхождении с таблицей — искать актуальные issues в RustAudio/rodio/cpal.

---

## 9. Оценка усилий (ориентир, не SLA)

| Этап | Дни |
| --- | --- |
| rodio spike (один device, MP3) | 0.5–1 |
| PlaybackHub + 2 channels + tests | 1.5–2 |
| Tauri IPC + events | 0.5–1 |
| TS Strategy + dual SpeechEngine + UI | 1–1.5 |
| QA + fallback + docs §17 | 1.5–2 |
| **Итого MVP** | **5–7** |

Сроки уточнять по фактической сложности device matching.

---

## 10. Post-MVP (не блокирует)

- Перенос очереди в `voicesub-tts` (`SpeechQueue`).
- Fetch MP3 в Rust (убрать bytes из IPC).
- UI preset «Streamer mode» (Cable + headphones).
- `tts_stop_all`, приоритет speech over twitch (опционально).
- Deprecate `VOICESUB_TTS_PER_PROCESS_ROUTING` в документации TTS.

---

## 11. Открытые вопросы (решать по ходу, фиксировать в PR)

1. Точное совпадение полей `AudioOutputDevice` с rodio device enumeration.
2. Default `playback_mode` в первом релизе с native: `browser` vs `native`.
3. Отдельные rate/volume для twitch в UI с первого дня или наследование.
4. Нужен ли `tts_play_audio` sync error return или только event `playback-finished` с `ok: false`.

---

## 12. Обязательные источники для сверки

### 12.1 Репозиторий VoiceSub

| Документ / путь | Зачем |
| --- | --- |
| `AGENTS.md` | политика, тесты, структура |
| `docs/TECHNICAL_ARCHITECTURE.md` | архитектура, слои |
| `docs/TECHNICAL_ARCHITECTURE.md` §17 | TTS module canon |
| `src-tts/App.svelte` | текущий enqueue |
| `src-tts/lib/speech-engine.ts` | очередь, prefetch |
| `src-tts/lib/google-tts.ts` | fetch, play today |
| `crates/voicesub-audio/` | enumeration, routing |
| `crates/voicesub-tts/src/subtitle_speech.rs` | planner |
| `src-tauri/src/tts.rs` | IPC surface |

### 12.2 Внешние (проверять актуальную версию)

| Тема | С чего начать поиск |
| --- | --- |
| rodio playback, OutputStream lifetime | https://docs.rs/rodio/ , RustAudio/rodio issues |
| cpal device id / WASAPI | https://github.com/RustAudio/cpal/issues |
| Tauri events + binary invoke | https://tauri.app/ (версия в `src-tauri/Cargo.toml`) |
| setSinkId (только fallback) | MDN Audio Output Devices API |
| WebView2 audio | MicrosoftEdge/WebView2Feedback |

**Поисковые запросы (примеры):** `rodio parallel OutputStream`, `cpal WASAPI device id windows`, `tauri invoke Vec u8`, `symphonia mp3 decode rodio`.

---

## 13. История решений (кратко)

| Решение | Причина |
| --- | --- |
| Native-first, без browser Phase 2 | `setSinkId` ненадёжен; WASAPI id ≠ browser id |
| Dual sink обязателен | стримерский сценарий OBS + наушники |
| Очередь в JS на MVP | меньший diff; planner уже через IPC |
| Расширить `voicesub-audio` | enumeration уже там |
| Strategy fallback | безопасный rollout |
| Не WinAPI per-process для dual | 1 process ≈ 1 routed device |

---

*Конец опорного документа. При реализации обновлять `docs/TECHNICAL_ARCHITECTURE.md` §17 и этот файл при смене IPC/конфига.*
