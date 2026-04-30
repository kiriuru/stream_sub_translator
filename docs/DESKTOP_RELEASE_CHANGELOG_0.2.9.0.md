# SST Desktop 0.2.9.0

Полный changelog desktop-версии.

Назначение файла:
- опорный релизный changelog для desktop-сборок;
- использовать как основу для публикации release notes;
- не ориентирован на публикацию в `main` как технический diff-документ.

Базовая точка сравнения:
- GitHub `origin/main`
- commit: `816fa98`

## Кратко

Версия `0.2.9.0` переводит desktop-сборку на более устойчивую локальную runtime-модель:
- source final публикуется сразу;
- перевод работает асинхронно и параллельно по target languages;
- stale translation results больше не должны догонять новый overlay;
- browser speech worker стал заметно устойчивее к `onend`, visibility throttling и reconnect-сценариям;
- в runtime добавлены structured logs и live diagnostics для translation и browser ASR;
- desktop dashboard и overlay стали лучше переживать websocket reconnect и late translation arrival.

## Основные изменения

### 1. Новый subtitle lifecycle

Переработано поведение показа source и translation:
- source и translation теперь имеют раздельные TTL;
- предыдущий перевод может оставаться видимым, пока не истечёт translation TTL;
- новый source partial может идти отдельно от предыдущего translation block;
- новый перевод должен заменять предыдущий только на новом final;
- late translation может появиться даже после исчезновения source, если translation TTL ещё не истёк;
- старые translation results не должны догонять новый overlay text.

Что это исправляет:
- раннее исчезновение перевода при начале следующей фразы;
- потерю перевода, если source TTL был короче translation latency;
- визуальные гонки между новым partial и старым completed block.

### 2. Асинхронный `TranslationDispatcher`

Путь перевода больше не держится на простом встроенном loop.

Добавлено:
- отдельный async dispatcher translation jobs;
- очередь translation jobs;
- отмена устаревших jobs;
- parallel fan-out по target languages;
- per-target timeout / error path;
- queue depth и latency metrics;
- публикация результата только если sequence ещё релевантен.

Практический эффект:
- source final публикуется без ожидания перевода;
- быстрый target не ждёт медленный target;
- slow target больше не должен блокировать все остальные переводы;
- stale jobs можно честно дропать без догоняющего overlay.

### 3. Browser Speech worker стал устойчивее

Browser speech path переработан под более стабильную desktop-эксплуатацию.

Добавлено:
- отдельный `browser-asr-session-manager.js`;
- быстрый `onend` rearm;
- backoff только для repeated start failures;
- watchdog rearm;
- visibility/degraded tracking;
- backend-side browser worker diagnostics;
- richer worker status flow через `/ws/asr_worker`.

Теперь runtime лучше объясняет:
- почему была пауза;
- был ли `onend`;
- сработал ли watchdog;
- было ли окно hidden/minimized;
- был ли terminal browser error;
- был ли worker disconnect.

### 4. Structured runtime logging

Добавлен structured JSONL logging для hot paths.

Новые / выделенные log files:
- `logs/translation-dispatcher.log`
- `logs/browser-recognition.log`
- `logs/browser-recognition-live.log`
- `logs/overlay-events.log`
- `logs/dashboard-live-events.log`

Что логируется:
- lifecycle translation jobs;
- per-target translation outcomes;
- stale drop / cancel / timeout / queue events;
- job-level dispatcher exceptions (`translation_job_error`), включая сбои выше target translation path;
- browser worker connect/disconnect/status events;
- browser degraded/error/rearm/watchdog events.

Требования безопасности соблюдены:
- secrets redacted;
- API keys / tokens / pair codes / passwords не должны попадать в structured logs;
- redaction покрывает и новые auth-поля вроде `access_token`, `refresh_token`, `client_secret`, `credentials`;
- source text по умолчанию не логируется целиком для dispatcher hot path.

### 5. Live diagnostics в dashboard

В dashboard добавлена минимальная live-видимость новых runtime diagnostics.

Translation diagnostics:
- queue depth;
- jobs started;
- jobs cancelled;
- stale results dropped;
- last provider latency;
- last queue latency;
- last runtime reason.

Browser ASR diagnostics:
- worker connected;
- desired/running state;
- recognition state;
- visibility state;
- last partial age;
- last final age;
- rearm count;
- watchdog rearm count;
- last error;
- degraded reason.

Также добавлена discoverability подсказка, какие log files смотреть.

### 6. Overlay и websocket reconnect

Улучшено поведение overlay при reconnect:
- overlay очищает presentation state при websocket disconnect;
- после reconnect получает last known runtime/subtitle/overlay payload;
- уменьшается риск зависшего текста;
- уменьшается риск пустого экрана после reconnect.

### 7. OBS Closed Captions

Исправлено дублирование повторной отправки одинакового перевода в OBS CC.

Добавлено:
- dedupe по `(sequence, output_mode, normalized_text)`;
- reset dedupe state при stop / reconnect.

Результат:
- один и тот же translation caption не должен повторно улетать в OBS CC для одного sequence;
- повтор того же текста на новом sequence при этом не запрещён.

### 8. Translation cache robustness

Усилена устойчивость translation cache:
- corrupted cache quarantine;
- atomic write через temp file + replace.

Это уменьшает риск потери runtime из-за битого cache JSON.

## Translation providers

### Изменения в provider list

Убрано:
- `MyMemory`

Причина:
- provider показал себя как нерабочий/ненадёжный путь;
- его сохранение в основном списке ухудшало реальную эксплуатацию desktop-сборки.

Добавлено:
- `Google Cloud Translation - Advanced (v3)`

Важно:
- это отдельный provider, не равный `Google Translate v2`;
- он использует другой API path и другой auth model.

### Что нужно для `Google Cloud Translation - Advanced (v3)`

Используются поля:
- `project_id`
- `access_token`
- `location`
- optional `model`

В UI это отображается как:
- `Access token`
- `Project ID`
- `Location`
- `Model (optional)`

Важно:
- v2 API key сюда не подходит;
- это не замена `google_translate_v2`, а отдельный provider.

### Что сохранено

Не менялось:
- default translation provider остаётся `google_translate_v2`;
- recognition может работать без translation;
- translation остаётся optional;
- target language ordering по-прежнему сохраняется в config/profile.

## Config и schema changes

В translation config добавлены runtime fields:
- `timeout_ms`
- `queue_max_size`
- `max_concurrent_jobs`

Для `google_cloud_translation_v3` добавлены provider settings:
- `project_id`
- `access_token`
- `location`
- `model`

Сохранение schema для `google_cloud_translation_v3` нормализовано так, чтобы в `config.json` оставались именно:
- `project_id`
- `access_token`
- `location`
- `model`

А legacy-поля вида `api_key` / `endpoint` / `region` не продолжали жить рядом в сохранённой конфигурации.

Если в старом config/profile был выбран `mymemory`, теперь fallback идёт на:
- `google_translate_v2`

## Runtime / API / payload additions

Публичные routes и websocket endpoints намеренно не ломались.

Но внутри существующих payload/diagnostics появились новые поля.

Новые runtime metrics:
- `translation_queue_depth`
- `translation_jobs_started`
- `translation_jobs_cancelled`
- `translation_stale_results_dropped`
- `translation_queue_latency_ms`
- `translation_provider_latency_ms`

Новые diagnostics fields:
- `AsrDiagnostics.browser_worker`
- queue/runtime counters в `TranslationDiagnostics`
- `TranslationEvent.is_complete`

Это важно для desktop UI и release diagnostics, даже если API surface по route names сохранён.

## Browser worker / desktop UX

Дополнительно улучшено:
- browser worker settings restart path;
- visibility-aware status updates;
- reconnect handling для websocket worker channel;
- вычищены legacy inline browser-recognition helpers из `google_asr.html`, runtime-логика вынесена в `browser-asr-session-manager.js`;
- runtime distinction между ordinary restart, terminal error и degraded mode.

## Remote / LAN related changes

Remote mode не превращён в hosted/cloud mode.

Сохранено:
- default local-first startup;
- default bind `127.0.0.1:8765`;
- remote/LAN остаётся opt-in.

Локальные улучшения в remote dashboard:
- polling не крутится без нужды;
- лучше учитывается pairing context;
- меньше лишней фоновой активности.

## Версия

Версия проекта поднята до:
- `0.2.9.0`

Дополнительно:
- version parser обновлён под 4-part version;
- `/api/version` и update comparison теперь умеют корректно работать с `0.2.9.0`.

## Документация

Обновлены:
- `README.md`
- `README.ru.md`
- `docs/TECHNICAL_ARCHITECTURE.md`
- `app-runtime/README.md`

Что отражено в документации:
- новый translation/runtime flow;
- новые structured logs;
- новый Google Cloud provider;
- removal of MyMemory;
- версия `0.2.9.0`;
- где смотреть translation/browser speech diagnostics.

## Автотесты

Добавлено и расширено backend coverage для:
- translation dispatcher;
- translation dispatcher job-level error logging;
- translation target timeout structured event path;
- subtitle lifecycle relevance;
- failed translation target как завершённый lifecycle input;
- late translation after source TTL;
- browser ASR gateway;
- browser worker contract;
- structured runtime logger;
- structured logger redaction для `access_token` и родственных ключей;
- OBS CC duplicate prevention;
- version parsing и release payload;
- config normalization для translation providers.

Локальный прогон на момент подготовки файла:
- `56 tests`
- `OK`

Команда:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
```

## Что особенно важно для релизной публикации

Если нужен короткий public-facing summary, главные release points для `0.2.9.0` такие:

1. Subtitle lifecycle стал заметно стабильнее для source + translation сценариев.
2. Translation теперь асинхронный, параллельный и лучше защищён от stale results.
3. Browser Speech worker стал устойчивее к `onend`, reconnect и hidden-window сценариям.
4. Добавлены structured logs и live diagnostics для translation и browser ASR.
5. Исправлены duplicate sends в OBS Closed Captions.
6. Убран `MyMemory`, добавлен `Google Cloud Translation - Advanced (v3)`.
7. Версия приведена к `0.2.9.0`.

## Не как часть changelog, а как примечание для подготовки релиза

Для внутренней опоры вместе с этим changelog использовать:
- [docs/DESKTOP_DIFF_FROM_GITHUB_MAIN.md](/F:/AI/stream-sub-translator/docs/DESKTOP_DIFF_FROM_GITHUB_MAIN.md)

Роли документов разные:
- `DESKTOP_RELEASE_CHANGELOG_0.2.9.0.md` — публикационный список изменений;
- `DESKTOP_DIFF_FROM_GITHUB_MAIN.md` — техническая карта расхождений от GitHub baseline.
