# Эталонная сверка desktop/local runtime (инструкция для агентов)

Дополнение к `AGENTS.md`. Используйте при расследовании «не работает на установке X», когда **тот же bootstrap exe и та же версия** на другой папке (эталон) работают.

**Эталон-образец (логи):** `F:\avatar\005\logs` — сессия `20260524T202917`, desktop CPU, Parakeet local, устройство `2`.

**Пример сломанного окружения (логи):** `F:\avatar\006\logs` — сессия `20260524T202542`, тот же профиль, тот же код сборки, иной рантайм процесса.

**Главный вывод по сравнению 005 vs 006:** код одинаковый; на 006 **сломано окружение/процесс backend** (тяжёлые HTTP-ответы, голодание capture). Не списывать на «неверный микрофон», «двойной Start» или краткий `listening_without_partials` без сверки с пунктами ниже.

---

## 1. Когда применять

- Пользователь сообщает: нет распознавания, VAD ноль, Stop не работает, дашборд тормозит, статусы прыгают.
- Нужно отделить **баг продукта** от **битой установки** (`.venv`, backend subprocess, перегруз API).
- Перед предложением правок в `local_asr_pipeline`, VAD, UI — **сначала** пройти чеклист; если FAIL на gate **§4 (API latency)** — чинить окружение, не код.

---

## 2. Условия сравнения

| Параметр | Требование |
|----------|------------|
| Версия exe | Тот же файл, что на эталоне (например из `F:\AI\stream-sub-translator-desktop-release`) |
| Профиль теста | Один сценарий: **CPU** local Parakeet (GPU опционально, отдельный прогон) |
| Микрофон | Тот же `audio.input_device_id` в config (эталон: `"2"`) |
| Сессия | 30–60 с речи после `listening`, затем **Stop** |
| Логи | Свежая папка `logs\` после одного прогона; не смешивать старые `.old` без пометки |

Исторический порядок установки (сначала Web Speech, потом CPU) **не виден в логах одной сессии**, но эталон 005 допускает оба пути bootstrap. Критерий — **метрики ниже**, не «как ставили вручную».

---

## 3. Файлы для сверки (все в `<install-dir>\logs\`)

| Файл | Назначение | Когда пишется |
|------|------------|---------------|
| `bootstrap-launcher.log` | Bootstrap, venv, NeMo verify, spawn backend | всегда |
| `deps-install-trace.jsonl` | Длительность `ensure_local_asr_runtime` | всегда |
| `startup-journey.jsonl` | Start/Stop, метрики на complete | **opt-in** (см. ниже) |
| `api-trace.jsonl` | **Ключевой gate:** latency HTTP | **opt-in** |
| `pipeline-trace.jsonl` | Capture → VAD → ASR (сборки с deep trace) | **opt-in** |
| `ui-trace.jsonl` | Дашборд, кнопки, аномалии UI | **opt-in** |
| `desktop-launcher.log` | `[runtime-metrics]` каждые ~5 с | всегда |
| `session-latest.jsonl` | Человекочитаемая лента | всегда |
| `subprocess-trace.jsonl` | Subprocess backend/browser | всегда |
| `runtime-events.log`, доп. `runtime_lifecycle.*` строки | Жизненный цикл рантайма | **opt-in** |

Экспорт diagnostics zip должен включать эти jsonl (см. `export_service`).

### 3.1. Включение глубоких трейсов (важно для сверки)

С версии **0.4.2** «глубокие» JSONL-трейсы (`api-trace`, `pipeline-trace`,
`ui-trace`, `startup-journey`, расширенные `runtime_lifecycle.*` в
`runtime-events.log`) отключены по умолчанию — чтобы соответствовать
объёму логов 0.4.1 и не нагружать диск/CPU на штатных запусках.

Перед сверкой 005 vs 006 (или любой ETALON-диагностикой) **включите
трейсы** одним из двух способов и **перезапустите** backend / desktop
launcher:

```bat
:: Все глубокие трейсы сразу (рекомендуется для триажа)
set SST_DEEP_DIAGNOSTICS=1
```

или поштучно (если нужно сузить):

```bat
set SST_TRACE_API=1
set SST_TRACE_PIPELINE=1
set SST_TRACE_UI=1
set SST_TRACE_STARTUP_JOURNEY=1
set SST_TRACE_RUNTIME_LIFECYCLE=1
set SST_TRACE_RUNTIME_EVENTS_VERBOSE=1
```

Принятые значения для «on»: `1`, `true`, `yes`, `on` (регистр любой).
Реализация флагов: `backend/core/diagnostic_flags.py`. Без флагов
указанные файлы просто не создаются, а соответствующие in-process
callsites превращаются в no-op.

**`SST_TRACE_RUNTIME_EVENTS_VERBOSE`** дополнительно открывает поток
DBG/VRB событий в `runtime-events.log` (`basr.*` FSM/recovery transitions,
`browser_worker_status` heartbeats, `translation_queue_depth_changed`,
…). По умолчанию структурированный логгер пишет только `INF`/`WRN`/
`ERR`/`CRT` — это совпадает с объёмом `runtime-events.log` на 0.4.1
для штатной сессии (~5–15 КБ вместо ~250 КБ в 0.4.0/0.4.1-dev с открытым
basr observability).

**Desktop launcher.** `desktop/launcher.py` использует те же флаги: без
них `startup-journey.jsonl`, `ui-trace.jsonl`, `api-trace.jsonl` не
создаются на стороне launcher-процесса. Always-on остаются
`bootstrap-launcher.log`, `desktop-launcher.log`, `deps-install-trace.jsonl`,
`subprocess-trace.jsonl`, `session-latest.jsonl`, `runtime-events.log`
(уже отфильтрованный по уровню) и `backend.log` — этого минимума хватает
для Gate A/B/C/F триажа.

---

## 4. Gate A — Bootstrap и venv (окружение создаётся)

Сверка с эталоном 005:

| Проверка | Эталон 005 | FAIL (как 006) |
|----------|------------|----------------|
| `deps-install-trace`: `ensure_local_asr_runtime_complete` | есть, ~**26 s** | отсутствует / ошибка |
| `desktop-launcher`: `verify installed local ASR stack` | `return_code=0` | ≠ 0 |
| `desktop-launcher`: `[deps] Verified local ASR stack for profile: cpu` | есть | нет |
| `startup-journey` / `backend_startup`: `python_executable` | `\<install\>\.venv\Scripts\python.exe` | другой путь / пустой venv |
| `torch_version` в journey | `2.11.0+cpu` (пример) | отсутствует / ошибка импорта |
| `sounddevice_version` | присутствует (напр. `0.5.5`) | отсутствует |

**Не считать FAIL:** предупреждения NeMo/ffmpeg/pydub в bootstrap — на эталоне они тоже есть.

---

## 5. Gate B — Backend и дашборд (процесс живой, UI быстрый)

### 5.1 Subprocess

| Проверка | Эталон |
|----------|--------|
| `subprocess.spawn role=backend` | один backend, `return_code` при штатном закрытии не обязателен 0 |
| `Started server process` в launcher | в течение ~**3 s** после spawn backend |
| `GET /api/health` из launcher | успех, без минут ожидания |

### 5.2 Дашборд (ui-trace)

| Событие | Эталон 005 (порядок) |
|---------|----------------------|
| `dashboard_navigation_begin` → `complete` | **&lt; 5 ms** между строками |
| `dashboard_resize_complete` + `trigger: health ready` | ~**0.5 s** после navigation (не десятки секунд) |
| `ws_connected` + badges `health/asr/device: ready` | сразу после загрузки |
| `runtime_busy` / progress | кратко при Start, не «вечный» loading без backend |

**FAIL:** задержка «пустого» дашборда **десятки секунд** при уже запущенном backend — сначала Gate C (API), не UI-логика.

---

## 6. Gate C — API latency (главный индикатор здорового окружения)

Читать `api-trace.jsonl`, поле `request_complete` → `fields.elapsed_ms`.

### 6.1 В простое (до Start, backend запущен, runtime idle)

| Endpoint | Эталон 005 | Порог FAIL |
|----------|------------|------------|
| `GET /api/health` | 2-й запрос **~6 ms** (1-й cold до ~500 ms допустим) | стабильно **&gt; 500 ms** |
| `GET /api/runtime/status` | median **~1.6 ms**, max разовый до ~600 ms | median **&gt; 200 ms** или постоянно **&gt; 1 s** |

**Эталон 006 (сломано):** health **~1.8 s**, status median **~3.3 s**, max **~8.7 s** — окружение больное **до** нажатия Start.

### 6.2 Runtime Start / Stop (local CPU)

| Endpoint | Эталон 005 | Порог FAIL |
|----------|------------|------------|
| `POST /api/runtime/start` (cold model) | **~15–22 s** → 200, `listening` | &gt; 60 s или зависание без 200 |
| `POST /api/runtime/start` (model warm) | **~10–15 s** | — |
| `POST /api/runtime/stop` | **~0.2–0.5 s** → `idle` | нет строки stop / &gt; 5 s |

**Эталон Browser Speech (005):** start **~10 ms** — отдельный режим, не смешивать с CPU.

### 6.3 Правило для агента

Если **status/health остаются секундами** при idle:

1. Считать **сломанным runtime окружения** (venv, зависший backend, AV/диск, второй процесс на порту).
2. **Не** предлагать правки VAD/Parakeet/Stop в коде до восстановления Gate C.
3. Рекомендовать: чистый `.venv`, переустановка в новую папку, сравнение latency с эталонной папкой; при необходимости копия `.venv` с эталона.

---

## 7. Gate D — `startup-journey.jsonl` (один цикл CPU)

Минимальная цепочка для одного нажатия Start + Stop:

```
backend_startup
runtime_start_request
runtime_start_complete   → status=listening, is_running=true
runtime_stop_request
runtime_stop_complete    → status=idle, is_running=false
```

### 7.1 `runtime_start_complete` (local)

| Поле | Эталон |
|------|--------|
| `asr_diagnostics.model_loaded` | `true` |
| `asr_diagnostics.runtime_initialized` | `true` |
| `asr_diagnostics.capture_sample_rate` | `16000` |
| `asr_diagnostics.selected_device` | `cpu` (или gpu) |
| `metrics` на complete | нули — **норма** |

### 7.2 `runtime_stop_complete` (после речи)

| Метрика | Эталон 005 (речь была) | FAIL |
|---------|------------------------|------|
| `vad_segments_partial` | **18–27** | **0** при длинной сессии с речью |
| `partial_updates_emitted` | **7–9** | **0** |
| `finals_emitted` | **3–5** | **0** |
| `elapsed_ms` stop | **&lt; 500** | — |

**Не путать:** единичные partials на тишине (фантомы модели) ≠ доказательство рабочего VAD. Эталон — **рост vad_partial за 5–20 s в `desktop-launcher.log`**.

---

## 8. Gate E — `pipeline-trace.jsonl` (capture → VAD → ASR)

Требуется сборка с deep pipeline trace (0.4.1+). Без файла или с 1–2 строками — только Gate C/D.

### 8.1 Сводная таблица (эталон 005 vs сломан 006)

| Метрика | Эталон 005 | FAIL 006 |
|---------|------------|----------|
| `capture_loop_enter` | ≥ 1 на сессию | 0 / нет чтения |
| `callback_tick` + `queue_depth` max | **1** | **&gt; 100** (эталон поломки: **3179**) |
| `read_chunk` count | десятки+ | единицы при длинной сессии |
| `read_chunk` `capture_level` median | сотни–тысячи (эталон median **~263**, max **~6678**) | стабильно **&lt; 400** |
| `callback_tick` `level` max | тысячи | callback громкий, read тихий → **очередь не дренируется** |
| `vad_segment_emitted` | **&gt; 0** при речи | **0** |
| `asr_job_done` | **&gt; 0** при речи | **0** |
| `capture_heartbeat` `chunks_read` | растёт непрерывно | застревает (эталон FAIL: **97** за ~96 s) |
| `capture_wait_no_audio` | 0 при открытом capture | много |

### 8.2 Интерпретация (для отчёта пользователю)

- **PortAudio слышит** (callback level) + **queue растёт** + **VAD 0** → runtime не успевает читать очередь, типично из‑за **тяжёлого backend** (Gate C), не «микрофон не тот».
- **VAD 0 + queue 1 + status 2 ms** → искать другую причину (config, device, модель).

---

## 9. Gate F — `desktop-launcher.log` `[runtime-metrics]`

После `listening`, при разговоре **~20–30 s**:

| Интервал | Эталон 005 |
|----------|------------|
| +5 s | `vad_partial` 3+, `finals` 0–1 |
| +10 s | `vad_partial` 9+ |
| +20 s | `vad_partial` 21+, `partials` 7+, `finals` 4+ |

Поля строки: `status`, `capture_sr=16000`, `model_loaded=True`, `vad_partial`, `vad_final`, `partials`, `finals`, `asr_queue`, `in_flight`.

**FAIL:** `warning: VAD/ASR metrics unchanged for 33s while listening` при активной речи.

**FAIL:** `model_loaded=False` в `listening` (не путать с кратким `starting`).

---

## 10. Gate G — UI (`ui-trace.jsonl`)

### 10.1 Start / Stop (эталон)

| Событие | Эталон |
|---------|--------|
| `start_click` | один на цикл; `prior_status: idle` |
| `start_complete` / `start_clicked` | `status: listening`, `is_running: true` |
| `stop_click` | `stop_disabled: false`, `prior_status: listening` |
| `stop_complete` | **&lt; 500 ms**, `status: idle` |
| `stop_button_dom_click` | есть при нажатии (если включён trace) |

Цепочка в `api-trace`: `stop_request` → `stop_complete` **обязательна**.

### 10.2 Статусы — что норма, что FAIL

| Паттерн | Вердикт |
|---------|---------|
| `listening_without_partials` **3–5 s** сразу после Start, затем `transcribing` / partials | **норма** на эталоне |
| `starting` → `idle` **во время** ожидания `POST /runtime/start` | **FAIL** (006) |
| `start_disabled: true` **и** `stop_disabled: true` одновременно | **FAIL** (006) |
| `listening` → `starting` → `listening` без Stop | **FAIL** (006) |
| Нет `stop_*` в trace, пользователь закрыл окно | симптом; смотреть Gate C |

---

## 11. Gate H — Browser Speech (опционально)

Эталон 005 в той же сессии:

| Метрика | Значение |
|---------|----------|
| `runtime_start_complete` elapsed | **~10 ms** |
| `model_loaded` | `false` |
| Stop partials/finals | 8 / 1 (browser path) |

Использовать для проверки «лёгкого» пути; **не заменяет** Gate C–F для CPU.

---

## 12. Порядок проверки (краткий алгоритм для агента)

```
1. Один exe, одна папка, CPU profile, device как на эталоне.
2. Gate C: api-trace health/status в idle → must be ms, not seconds.
   → FAIL? Окружение. Стоп. Не код.
3. Gate A: deps verify rc=0.
4. Gate B: dashboard ui-trace < few seconds to ready.
5. Start → 30s speech → Stop.
6. Gate D: journey stop metrics vad_partial > 0.
7. Gate E: pipeline queue_depth max ≤ few; vad_segment_emitted > 0.
8. Gate F: runtime-metrics рост vad_partial.
9. Gate G: stop chain complete.
10. Сравнить с эталонной папкой side-by-side (таблица §13).
```

---

## 13. Side-by-side: эталон vs сломан (шпаргалка)

| # | Проверка | 005 OK | 006 FAIL |
|---|----------|--------|----------|
| 1 | status API median | ~2 ms | ~3300 ms |
| 2 | health API (warm) | ~6 ms | ~1800 ms |
| 3 | queue_depth max | 1 | 3179 |
| 4 | vad_segment_emitted | 53 | 0 |
| 5 | stop API | ~460 ms | нет |
| 6 | vad_partial @ stop | 27 | — |
| 7 | UI idle mid-start | нет | да |
| 8 | dashboard ready | ~2 s | задержка из-за API |

---

## 14. Что НЕ использовать как доказательство

| Наблюдение | Почему не вывод |
|------------|-----------------|
| Краткий `listening_without_partials` | На эталоне тоже есть до первого partial |
| 1–2 фантомных partial на тишине | Модель может шуметь; смотреть **vad_partial** и **queue** |
| `backend exit code 1` при закрытии окна | Пользователь убил процесс, не обязательно баг |
| Разный порядок «Web потом CPU» в истории | Сверять **метрики gates**, не историю установки |
| Разный `config` theme/ui | Не влияет на capture |

---

## 15. Восстановление окружения (рекомендации пользователю, не код)

1. Удалить `<install>\.venv`, при необходимости `logs`, повторить bootstrap тем же exe.
2. Сравнить `GET /api/health` с эталонной папкой (PowerShell/browser или `api-trace` после 10 s idle).
3. Убедиться: один backend на `127.0.0.1:8765`, нет зависшего процесса.
4. Проверка: скопировать рабочий `.venv` с эталона → если 006 оживает, виноват venv.
5. Включить в отчёт: `api-trace.jsonl`, `pipeline-trace.jsonl`, `startup-journey.jsonl` за один прогон.

---

## 16. Ссылка на эталонные числа (сессия 005, CPU local #1)

- Start complete: **21578 ms**, device **2**, `listening`
- Stop complete: **458 ms**, `vad_segments_partial` **27**, `partials` **9**, `finals` **5**
- First partial после listening: **~3 s** (session-latest / ui-trace)
- API status median (idle): **~1.65 ms**
- Pipeline: **53** vad segments, queue max **1**

Обновлять эталонные числа при смене железа/версии, перезаписывая этот раздел после нового эталонного прогона.

---

## 17. Связь с AGENTS.md

- Не менять frozen remote / subtitle lifecycle из-за FAIL Gate C.
- Deep trace — диагностика, не продуктовый контракт для пользователя.
- Desktop publish policy не отменяет эту сверку на **пользовательской** папке установки.
