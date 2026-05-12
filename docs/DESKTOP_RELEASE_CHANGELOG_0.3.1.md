# SST Desktop 0.3.1

## Русский

`0.3.1` — релиз стабилизации поверх уже выпущенного `0.3.0`. Архитектурные изменения (`RuntimeOrchestrator` → контроллеры, split `SubtitleRouter`, пакет `backend/translation/`, `cache_manager`, `atomic_io`, `ConfigStateService`, `/api/updates/check`, OpenAI helper endpoints, карточки `translation_1..translation_5`, тема и палитра UI, вкладка Help, supervisor Web Speech, запуск worker'а Google Chrome в отдельном окне с изолированным профилем) **уже входили в `0.3.0`** — здесь они не дублируются. Базовый local-first продукт и публичные `/api` / WebSocket-контракты не меняются.

### Что реально новое в 0.3.1

- `backend/versioning.py`: `PROJECT_VERSION = "0.3.1"`, источник правды для `GET /api/version` и `POST /api/updates/check`.
- В репозитории теперь отслеживаются `desktop/bootstrap_launcher.py` и `desktop/bootstrap_payload.py` (раньше они существовали локально, но не были закоммичены).
- Bootstrap фильтрует legacy-теги `v2.x`, когда встроенная версия лаунчера — `0.x`: семантическое сравнение больше не предлагает старые `v2.8.x` как «новее `0.3.x`». Покрыто `tests/test_bootstrap_release_tag_filter.py`.
- Web Speech, дополнительная защита Windows-окна Chrome worker'а (поверх изоляции профиля, которая уже была в `0.3.0`):
  - запуск с `HIGH_PRIORITY_CLASS`;
  - opt-out из Windows EcoQoS / Efficiency Mode через `SetProcessInformation` + `ProcessPowerThrottling`;
  - отключённые Chrome feature gates `CalculateNativeWinOcclusion`, `HighEfficiencyModeAvailable`, `HeuristicMemorySaver`, `IntensiveWakeUpThrottling`, `GlobalMediaControls`.
- Web Speech, защита распознавания в самом worker'е (`frontend/js/browser-asr-session-manager.js`):
  - `navigator.wakeLock.request("screen")` пока распознавание активно и окно видимо, с авто-перехватом после visibility-flip;
  - network preflight через `https://www.google.com/generate_204` после трёх ошибок `network` за ~12 c; при провале supervisor уходит в терминальный `recognition_network_unreachable` вместо бесконечного рестарт-цикла;
  - health-сигнал `voice_below_recognition_threshold` (RMS ≥ 0.025, накопленные `no-speech`, тишина распознавания ≥ 8 c);
  - ранняя контролируемая ротация сессии: `asr.browser.max_browser_session_age_ms` по умолчанию `180000` мс (раньше `240000`), окно `prepare_cycle_before_ms` остаётся `15000` мс.
- `backend/core/cache_manager.py` переписан на in-memory LRU с debounce-персистом на диск (раньше блокирующая запись на каждый ход). Карантин повреждённого файла кеша сохранён.
- `backend/core/structured_log_compact.py` — новый helper для сжатия структурированных рантайм-логов (truncate длинных строк, summary длинных списков, ограничение глубины); подключён в `structured_runtime_logger`.
- `TranslationDispatcher`: стал restart-safe (`stop()` больше не «ломает» диспетчер для следующих сессий), добавлено ограничение параллелизма по провайдеру и базовый rate limiting, параллелизм по целевым языкам сохраняется.
- Новые встроенные эффекты появления субтитров: `slide_up`, `zoom_in`, `blur_in`, `glow` (поверх существовавших `none`, `fade`, `subtle_pop`).
- Уточнения в frontend-панелях: translation panel и slot cards стали аккуратнее в крайних случаях, расширены строки i18n, добавлены мелкие правки ASR/runtime/style.
- Документация: `CHANGELOG.md` и `TECHNICAL_ARCHITECTURE.md` приведены к единому русскому изложению; `docs/DESKTOP_RELEASE_CHANGELOG_0.3.0.md` заменён на этот файл.

### Что было уже в 0.3.0 и не считается новым в 0.3.1

- Декомпозиция `RuntimeOrchestrator` на runtime-контроллеры в `backend/core/runtime/` (state/metrics/session/segment/lifecycle/browser-worker/speech sources/audio capture/processing tasks/translation runtime/transcript/output fanout).
- Разделение `SubtitleRouter` на `subtitle_lifecycle_core.py` + `subtitle_presentation.py` + фасад.
- Пакет `backend/translation/` с `base.py`, `engine.py`, `readiness.py`, `registry.py` и `providers/*`.
- `backend/core/atomic_io.py` и атомарная запись config/profiles.
- `backend/services/config_state_service.py` (`ConfigStateService` с явной блокировкой и метаданными активного снимка).
- `backend/services/update_service.py` + `POST /api/updates/check` + защита `runtime_start_snapshot` от записи метаданных обновлений.
- OpenAI helper endpoints: `GET /api/openai/recommended-models`, `POST /api/openai/models`, `POST /api/openai/usable-models`.
- Карточки `translation_1..translation_5`, `TranslationLineConfig`, миграция `subtitle_output.display_order` в id слотов перевода.
- Web Speech worker в Google Chrome в отдельном окне с адресной строкой и изолированным `--user-data-dir`; `asr.browser.worker_launch_browser` со значениями `auto` / `google_chrome`.
- Web Speech supervisor (`browser-asr-session-manager.js`), experimental `/google-asr-experimental`, тема и палитра UI, вкладка Help, расширенный i18n, runtime-event coalescing и стабильность `/ws/events` / `/ws/asr_worker`.
- `GET /api/exports/diagnostics` (ZIP с runtime/config/log/session-данными) и best-effort `/api/logs/client-event`.

### Проверка

- `python -m compileall backend desktop tests`
- `.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -p "test_*.py"`
- `283 tests`, `OK`

## English

`0.3.1` is a stabilization release on top of the already-shipped `0.3.0`. The architectural milestones (`RuntimeOrchestrator` → runtime controllers, `SubtitleRouter` split, the `backend/translation/` package, `cache_manager`, `atomic_io`, `ConfigStateService`, `/api/updates/check`, OpenAI helper endpoints, `translation_1..translation_5` slot cards, UI theme/palette, the Help tab, the Web Speech supervisor, launching the worker as a dedicated Google Chrome window with an isolated profile) **were already part of `0.3.0`** — they are not repeated here. The local-first baseline and public `/api` / WebSocket contracts are unchanged.

### Actually new in 0.3.1

- `backend/versioning.py`: `PROJECT_VERSION = "0.3.1"`, source of truth for `GET /api/version` and `POST /api/updates/check`.
- `desktop/bootstrap_launcher.py` and `desktop/bootstrap_payload.py` are now tracked in the repo (they existed locally before but were not committed).
- The bootstrap update check now filters out legacy `v2.x` tags when the built-in launcher is on the `0.x` line: semver no longer surfaces old `v2.8.x` releases as "newer than `0.3.x`". Covered by `tests/test_bootstrap_release_tag_filter.py`.
- Additional Web Speech worker hardening for the Windows Chrome worker window (on top of the isolated profile that was already in `0.3.0`):
  - launched with `HIGH_PRIORITY_CLASS`;
  - Windows EcoQoS / Efficiency Mode opt-out via `SetProcessInformation` + `ProcessPowerThrottling`;
  - Chrome feature gates `CalculateNativeWinOcclusion`, `HighEfficiencyModeAvailable`, `HeuristicMemorySaver`, `IntensiveWakeUpThrottling`, `GlobalMediaControls` disabled.
- In-worker recognition hardening (`frontend/js/browser-asr-session-manager.js`):
  - `navigator.wakeLock.request("screen")` while recognition is active and the window is visible, with automatic re-acquire after visibility flips;
  - network preflight against `https://www.google.com/generate_204` after three `network` errors within ~12s; on failure the supervisor moves to a terminal `recognition_network_unreachable` state instead of looping restarts forever;
  - new `voice_below_recognition_threshold` health signal (RMS ≥ 0.025, accumulated `no-speech`, recognition silence ≥ 8s);
  - earlier controlled session rotation: `asr.browser.max_browser_session_age_ms` default `180000` ms (was `240000`); the `prepare_cycle_before_ms` window stays at `15000` ms.
- `backend/core/cache_manager.py` was rewritten as an in-memory LRU with debounced disk persistence (previously it wrote on every call from the asyncio path). The quarantine for corrupted cache files is preserved.
- `backend/core/structured_log_compact.py` is a new helper that compacts structured runtime logs (truncate long strings, summarize long lists, depth limits), wired into `structured_runtime_logger`.
- `TranslationDispatcher` is now restart-safe (`stop()` no longer leaves the dispatcher unusable for the next session) and gains per-provider concurrency limits plus a basic rate limit; per-target parallelism is preserved.
- New built-in subtitle entrance effects: `slide_up`, `zoom_in`, `blur_in`, `glow` (in addition to the existing `none`, `fade`, `subtle_pop`).
- Frontend polish: minor refinements to the translation panel / slot card edge cases, expanded i18n strings, small fixes in ASR / runtime / style panels.
- Documentation: `CHANGELOG.md` and `TECHNICAL_ARCHITECTURE.md` were unified to Russian narrative; `docs/DESKTOP_RELEASE_CHANGELOG_0.3.0.md` was replaced by this file.

### Already in 0.3.0 (not new in 0.3.1)

- `RuntimeOrchestrator` decomposition into runtime controllers under `backend/core/runtime/` (state/metrics/session/segment/lifecycle/browser-worker/speech sources/audio capture/processing tasks/translation runtime/transcript/output fanout).
- `SubtitleRouter` split into `subtitle_lifecycle_core.py` + `subtitle_presentation.py` + facade.
- The `backend/translation/` package with `base.py`, `engine.py`, `readiness.py`, `registry.py` and `providers/*`.
- `backend/core/atomic_io.py` and atomic config/profile writes.
- `backend/services/config_state_service.py` (`ConfigStateService` with explicit locking and active-snapshot metadata).
- `backend/services/update_service.py` + `POST /api/updates/check` + protecting `runtime_start_snapshot` from update-metadata writes.
- OpenAI helper endpoints: `GET /api/openai/recommended-models`, `POST /api/openai/models`, `POST /api/openai/usable-models`.
- `translation_1..translation_5` slot cards, `TranslationLineConfig`, and migration of `subtitle_output.display_order` into translation slot ids.
- Web Speech worker opened in Google Chrome as a separate window with an address bar and an isolated `--user-data-dir`; `asr.browser.worker_launch_browser` accepting `auto` / `google_chrome`.
- Web Speech supervisor (`browser-asr-session-manager.js`), experimental `/google-asr-experimental`, UI theme/palette, Help tab, expanded i18n, runtime-event coalescing and `/ws/events` / `/ws/asr_worker` resilience.
- `GET /api/exports/diagnostics` (ZIP with runtime/config/log/session data) and best-effort `/api/logs/client-event`.

### Verification

- `python -m compileall backend desktop tests`
- `.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -p "test_*.py"`
- `283 tests`, `OK`
