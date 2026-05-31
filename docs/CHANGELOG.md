# Журнал изменений SST Desktop

Единая история изменений desktop-версии.

Этот файл — канонический changelog для релизов SST Desktop. Installer delta для текущей линии: [DESKTOP_RELEASE_CHANGELOG_0.4.1.md](./DESKTOP_RELEASE_CHANGELOG_0.4.1.md). Старые per-version delta (`0.3.x`, `0.4.0`) удалены — история только здесь.

**Формат записей (как [GitHub Release v0.2.9.2](https://github.com/kiriuru/stream_sub_translator/releases/tag/v0.2.9.2)):** одно предложение о версии; буллеты «что вошло» — только факты изменений; для desktop-exe — блок «формат release» (структура поставки, без перечисления старых профилей как новинки).

## Unreleased

_(пусто — см. [0.4.4](#044))_

## 0.4.4

Patch release. `PROJECT_VERSION` в `backend/versioning.py` — **0.4.4**; `config_version` **7**. Публичные HTTP/WebSocket route contracts и subtitle/translation lifecycle **не менялись**.

### Security (OpenAI helper routes)

- **`backend/core/outbound_url_policy.py`**: SSRF-политика для `POST /api/openai/models` и `POST /api/openai/usable-models` — при LAN-exposed bind (`0.0.0.0`/`::` или `SST_ALLOW_LAN=1`) запрещены loopback, RFC1918, link-local и metadata hostnames в `base_url`; при default localhost bind частные URL по-прежнему разрешены (локальные OpenAI-compatible серверы). Outbound URL translation providers **не затронуты**.
- Регрессии: `tests/test_outbound_url_policy.py`, расширен `tests/test_openai_models_route.py`.

### Frontend store и desktop bridge

- **`frontend/js/core/store.js`**: slice `desktop` + `patchDesktopContext()` — единый snapshot desktop-контекста для dashboard.
- **`frontend/js/main.js`**: один listener `sst:desktop-context`; `DesktopBridge.getContext()` без дублирующих вызовов.
- **`frontend/js/desktop.js`**: удалены мёртвые записи в `window.AppState`.
- Регрессии: `tests/test_frontend_architecture.py`, `tests/test_desktop_profile_lock.py`.

### Overlay WebSocket

- **`frontend/js/core/ws-stale-guard-logic.js`**: общий stale-алгоритм (timestamp-first при reset sequence после stop/start).
- **`frontend/js/core/ws-client.js`**: рефакторинг на shared module.
- **`overlay/overlay.js`**: тот же stale-filter, exponential reconnect 1–10 s; при disconnect последний кадр сохраняется до reconnect (OBS UX).
- Регрессии: `tests/test_ws_stale_guard.py`.

### Desktop launcher (module split)

- **`desktop/launcher.py`**: тонкий facade (re-export); **`desktop/launcher_bootstrap.py`**: `DesktopLauncher`, `main()`, bootstrap/run; mixins **`launcher_window.py`**, **`launcher_backend.py`**, **`browser_worker_launcher.py`**; **`launcher_context.py`**, **`launcher_api.py`**.
- Регрессии: `tests/test_launcher.py`, `tests/test_launcher_module_layout.py`.

### Dashboard polish и bind/profile tests

- Bootstrap errors banner в dashboard (`frontend/js/main.js`, `frontend/js/dashboard/actions/data-actions.js`).
- `escapeHtml(label)` в compact nav (`frontend/js/layout/layout-controller.js`).
- **`backend/run.py`**: `resolve_bind_host()` для тестируемой bind-политики; **`ProfileManager`**: `resolve()` + `is_relative_to()` для path safety.
- Регрессии: `tests/test_bind_policy.py`, `tests/test_profile_manager_paths.py`.

### UI localization (ja / ko / zh)

- **Локали:** dashboard, Browser Speech worker и OBS overlay — **en**, **ru**, **ja**, **ko**, **zh**; выбор в header/settings, сохранение в `ui.language` (`config.json`) и `localStorage` (`sst.ui.language`).
- **Смена архитектуры i18n (кратко):** вместо двух встроенных словарей в `i18n.js` — отдельные файлы `frontend/js/i18n/locales/*.js`, синхронный **`locales-bundle.js`** (все локали одним script для WebView2), слой **`dynamic-locales.js`** для en/ru «поздних» ключей; runtime merge в `i18n.js` (`english ∪ locale ∪ dynamic[locale]`). Генерация CJK: `tools/generate_i18n_locales.py`, дозаполнение `tools/fix_untranslated_cjk.py`, сборка bundle `tools/build_i18n_locale_bundle.py`.
- **Поведение:** мгновенное переключение без fetch; `sst:locale-changed` для панелей с динамическим DOM (translation results, ASR, style, overlay); смена языка сразу пишет конфиг через `saveCurrentConfig()`.
- **`desktop/ui_locale.py`**: общая нормализация `ui.language` для splash/desktop API.
- Регрессии: `tests/test_i18n_locales.py`, `tests/test_i18n_dynamic_locales.py`, `tests/test_ui_locale.py`.
- Подробно: **§16.8** в `docs/TECHNICAL_ARCHITECTURE.md`.

### Dashboard — ASR advanced (вкладка «ASR расширенные»)

- **`frontend/index.html`**, **`frontend/js/ui/field-help-popover.js`**, **`frontend/js/panels/asr-panel.js`**: у каждого поля расширенного ASR-тюнинга — кнопка `?` и всплывающая справка (нижний край popover на уровне кнопки; закрытие по повторному клику, клику снаружи, `Esc`); mount на `[data-tab-panel="asr_advanced"]`, обновление текста на `sst:locale-changed`.
- **Подписи рекомендуемых значений:** вместо двойных hint-строк вида `по умолчанию:… безопаснее:…` — одна строка `Рекомендуемое: …` / `Recommended: …` / `推奨:` / `권장:` / `推荐:` (`tools.advanced.*.note`).
- **i18n:** полные тексты справки `tools.advanced.*.help` и `tools.advanced.field_help.aria` для **en**, **ru**, **ja**, **ko**, **zh**; в описании пресета задержки — локализованные имена пресетов из `tuning.preset.*` (не slug `balanced` / `ultra low latency` в CJK UI).
- **CSS:** `frontend/css/app.css` — `.field-help-btn`, `.field-help-popover`, `.inline-field-title`; двухколоночная сетка `.asr-advanced-fields-grid` (одна колонка на узких экранах); popover/button используют токены темы (`--bg-panel-elevated`, `--line-subtle`), а не захардкоженный тёмный fallback.
- **Layout:** боковый блок `tools.notes.*` удалён — пояснения только через `?` у каждого поля; Parakeet-only extras (`#rt-tools-local-parakeet-extras`) участвуют в сетке через `display: contents`; в **compact** — одна колонка (`compact-layout.css`).
- **Сопровождение:** `tools/patch_asr_advanced_i18n_cjk.py` (пакетное обновление note/help для ja/ko/zh); после правок locale-файлов — `python tools/build_i18n_locale_bundle.py`.
- Регрессии: `tests/test_field_help_popover.py`.

### Dashboard preview (idle, до Start)

- **`frontend/js/dashboard/action-helpers.js`**: `buildPreviewPayload` не подменяет style-placeholder пустым `overlay_update` с WS после Save, пока runtime не запущен — можно настраивать стили до явного Start.
- Регрессии: `tests/test_dashboard_idle_preview.py`.

### Документация

- `docs/TECHNICAL_ARCHITECTURE.md`, `docs/TECHNICAL_ARCHITECTURE.en.md` — синхронизированы с 0.4.4 (launcher layout, store/overlay WS, pip bootstrap policy, SSRF, **§16.6.1 ASR advanced**, **§16.8 UI i18n**, idle preview §16.7.6).
- `README.md`, `README.ru.md`, `docs/WIKI.en.md`, `docs/WIKI.ru.md` — версия и операционные заметки по изменениям 0.4.4.

## 0.4.3

Patch release. `PROJECT_VERSION` в `backend/versioning.py` — **0.4.3**; `config_version` **7**. Публичные HTTP/WebSocket route contracts и subtitle/translation lifecycle **не менялись**.

### Subtitle renderer (DOM lifecycle, long-session stability)

- **`frontend/js/subtitle-style.js`**: persisted render state (`entrySurfaces`, `partialSurfaceBySlot`, `wrapper`) хранит **WeakRef** на DOM-узлы (fallback на strong ref без `WeakRef`), чтобы отцеплённые surface не удерживались между кадрами при slow path (переиспользование completed source при появлении перевода).
- Перед единственным slow-path `container.innerHTML = ""` — `_releaseOrphanedSurfaces`: сброс `__sstAppliedStyleMap` у surface, не попавших в следующий кадр.
- **`disposeRenderContainer(container)`** — явный cleanup state и DOM; вызывается из **`frontend/js/panels/overlay-panel.js`** при unmount превью и при пустом payload.
- Регрессии: `tests/test_subtitle_style_effects.py` — контракты WeakRef, orphan release, `disposeRenderContainer`.

## 0.4.2

Stabilization release. `PROJECT_VERSION` в `backend/versioning.py` — **0.4.2**; `config_version` **7**. Публичные HTTP/WebSocket route contracts и subtitle/translation lifecycle **не менялись**.

### Parakeet integrity (idle latency fix)

- **`backend/asr/parakeet/model_installer.py`**: добавлен потокобезопасный кеш результата `official_eu_parakeet_integrity_state()` по ключу `(file_path, mtime_ns, size, expected_sha)`. SHA-256 многогигабайтного `.nemo` теперь считается один раз за жизнь процесса вместо каждого вызова `/api/runtime/status` и `/api/health`. На свежей установке с `sha256` в `manifest.json` idle-latency status падает с 3–10 с до миллисекунд.
- Публичная `invalidate_official_eu_parakeet_integrity_cache()` для явной инвалидации; вызывается из `ensure_official_eu_parakeet_model()` после записи манифеста, чтобы закрыть гонку «`shutil.move` → manifest write».
- Регрессии: `tests/test_parakeet_model_installer_manifest.py` — 8 тестов, включая прямой regression `test_integrity_state_caches_sha256_result`.

### Desktop bootstrap install/repair

- **`desktop/bootstrap_payload.py`**: при detected mismatch теперь чистит существующий `app-runtime/` перед извлечением нового payload — drop-in замена exe обновляет managed runtime без накопления stale файлов от прошлой версии.
- **`backend/bootstrap_pip_pins.py`** + `vendor/python-wheels/antlr4_python3_runtime-4.9.3-py3-none-any.whl`: vendored ANTLR4 runtime wheel ставится перед NeMo, чтобы убрать flaky sdist-сборку `antlr4-python3-runtime==4.9.3` на Windows (path/cache/egg-info race в `pip`). Регрессия: `tests/test_bootstrap_pip_pins.py`.

### Subtitle renderer (incremental effects, no full-line re-render)

- **`frontend/js/subtitle-style.js`** — capability-сохраняющая перезапись потока рендера:
  - Эффект (typewriter / pop-in / glow burst / underline sweep / scale fade / blur sharpen / spotlight pop / ink bloom / vintage flicker) теперь применяется **только к свежим фрагментам** partial-обновления, ранее набранная часть остаётся статичной. CSS-классы `.subtitle-fragment-static` / `.subtitle-fragment-fresh` в `frontend/css/subtitle-style.css`.
  - Введена **shape-signature** для строки субтитров (`_shapeSignatureForRows`, `_shapeSignatureForEntry`); если сигнатура совпадает с предыдущим кадром, рендер идёт через fast path (повторно используется существующий wrapper/stage/row/surface DOM) — `container.innerHTML = ""` больше не вытирает блок при partial-обновлении исходного текста.
  - Fast path охватывает и переход transient→completed: `_canFastPathFinalize` / `_finalizeTransientSurfaceInPlace` доконсолидируют partial-source в финальный блок без повторной анимации.
  - Slow path при добавлении новой строки перевода переиспользует уже завершённую source-поверхность из `previousEntrySurfaces`, чтобы исходник не переанимировался при появлении блока перевода.
  - В `composeRenderRows` partial-source при `lifecycle_state === "completed_with_partial"` помечается `transient: true`, так что live partial не считается завершённым и обновляется in-place через fast path.
  - Новые поля `render_summary`: `fast_path_reason`, `finalized_in_place`, `reused_completed_surface`, `reused_partial_surfaces`. Включаются через `SST_TRACE_SUBTITLE_RENDER=1` (см. отладочный канал в `frontend/js/dashboard/ui-trace.js`).
- **`frontend/js/normalizers/overlay-normalizer.js`** + **`overlay/overlay.js`**: `lifecycle_state` теперь дотягивается из backend-payload до `SubtitleStyleRenderer.render` и в дашборд-превью, и в overlay. Без него fast path неправильно классифицировал completed_with_partial frames.
- **`frontend/js/panels/overlay-panel.js`**: дашборд-превью очищает все `.subtitle-stage-note` перед добавлением нового, чтобы блок «Живой блок субтитров #N» не размножался кадр-за-кадром.
- Кеш-бастинг `index.html` / `overlay.html` бамп `?v=20260525a` для `subtitle-style.js` / `overlay.js` / `i18n.js` / `main.js` — старые кэшированные сборки во встроенном WebView2 не перетянут back старую логику.
- Регрессии: `tests/test_subtitle_style_effects.py` — ~25 новых тестов на fast path / shape signature / finalization / lifecycle_state plumbing / DOM reuse.

### Subtitle styles и bundled fonts

- **`backend/core/subtitle_style.py`** — `_STYLE_PRESETS` переработан (10 различимых тематических пресетов): обновлены `anime_stream` (Mochiy Pop One + Comfortaa, белая заливка, узкий фиолетовый stroke 1px, мягкая тень), `cinema_plate`, `max_contrast`, `comic_burst`, `retro_terminal`; добавлены `fallout_terminal` (зелёный неон в стиле Pip-Boy), `cyberpunk_neon`, `noir_caption`, `jp_style` слит в общий пресет (бывший «JP dual» удалён). `_LEGACY_PRESET_MIGRATIONS` перенаправляет старые ключи.
- **`fonts/*.ttf`** — 28 popular Google Fonts добавлены прямо в репозиторий (Bangers, BebasNeue, Comfortaa, ComicRelief, CutiveMono, Exo2, Inter, JetBrainsMono, Lato, Merriweather, MochiyPopOne, Montserrat, NotoSans, OpenSans, Orbitron, Oswald, PTMono, PlayfairDisplay, Poppins, Raleway, Roboto, ShareTechMono, SourceSans3, SpecialElite, UbuntuMono, Underdog, VT323). Все пресеты используют fallback-цепочку с кириллицей (Comfortaa Regular, Lato Regular, Noto Sans, Open Sans), чтобы тематические шрифты не разрушали русский текст.
- **`backend/core/font_catalog.py`**: `_CAMEL_TO_SPACE_RE` нормализует имена файлов `MochiyPopOne-Regular.ttf` → `Mochiy Pop One Regular` для UI-каталога. Регрессия: `tests/test_font_catalog.py`.
- **Frontend: системные шрифты не пропадают при сохранении.** `frontend/js/dashboard/action-helpers.js` экспортирует `mergeFontCatalogPreservingSystem`; `data-actions.js` мерджит каталог из сервера с client-side кешем `system_font_catalog` (localStorage), `config-actions.js` использует тот же merge при save/import. Раньше save затирал `system` записи на серверном каталоге и пользователь терял выбранный системный шрифт.
- **Style editor UI**:
  - `frontend/js/panels/style/style-editor-panel-shared.js` — `extractPrimaryFontFamily` парсит первое quoted имя из CSS font-family chain, чтобы dropdown отображал реально выбранный шрифт при загрузке пресета.
  - `frontend/js/panels/style/style-editor-panel-render.js` + `frontend/js/panels/style-editor-panel.js` — новый селектор `#style-line-slot-apply-preset`: применяет base-стиль выбранного пресета только к конкретному line slot override, форсит `enabled=true` для слота, после применения сбрасывается в placeholder.
- **Browser Speech worker (`frontend/google_asr.html`)**: `buildSettingsSavePayload` теперь сначала загружает свежий `/api/settings/load`, мерджит в него только browser-specific поля и сохраняет — раньше окно браузер-воркера затирало изменения, сделанные в дашборде между его открытием и кнопкой «Сохранить». Регрессия: `tests/test_browser_worker_contract.py::test_browser_worker_save_reloads_latest_config_before_save`.

### Dashboard UI: compact layout и Parakeet-настройки

- **`frontend/css/compact-layout.css`** — `body.sst-layout-compact .overview-preview-card { display:none !important; }` гарантирует, что live snapshot preview не показывается в compact view даже если DOM перенесёт его за пределы `.overview-layout`.
- Compact-mode hide-правила декоративных `.eyebrow`, `<p class="muted">` под заголовками и stand-alone `<p class="muted" data-i18n>` теперь **исключают** technical-панели `recognition`, `tuning`, `asr_advanced` через `:not([data-tab-panel="..."])`. Технические подсказки и notes на Parakeet-страницах остаются видимыми в compact-режиме (раньше агрессивно скрывались).
- Live snapshot preview card перенесён в `frontend/index.html` под блок «Завершённый текст» (`<pre id="final-transcript">`), чтобы стандартная и compact раскладки одинаково группировали ASR-output блоки.
- **`frontend/js/panels/asr/asr-panel-render.js`** — Parakeet tuning controls (`#parakeet-latency-preset-row`, `#rt-tools-local-parakeet-extras`: streaming decode toggle, `partial_emit_mode`, `partial_min_new_words`) теперь видны всегда, кроме случая `desktop_profile_lock="browser_speech"` (Web-Speech-only install). Раньше эти контролы скрывались при текущем `asr.mode === "browser_google"`, и пользователь не мог настроить Parakeet до переключения mode. Регрессия: `tests/test_frontend_architecture.py::test_parakeet_tuning_controls_visible_outside_browser_speech_lock`.
- Кнопки `start-btn` / `stop-btn` помечены `type="button"`, чтобы не триггерили subm​it ближайшей формы и не вызывали посторонний reload состояния.

### Opt-in deep-diagnostic tracing

- **`backend/core/diagnostic_flags.py`** (новый модуль) — централизованный контроль через переменные окружения: `SST_DEEP_DIAGNOSTICS` (мастер-свитч) или индивидуальные `SST_TRACE_API`, `SST_TRACE_PIPELINE`, `SST_TRACE_UI`, `SST_TRACE_STARTUP_JOURNEY`, `SST_TRACE_RUNTIME_LIFECYCLE`, `SST_TRACE_RUNTIME_EVENTS_VERBOSE`.
- **`backend/core/app_bootstrap.py`** — `configure_api_trace_log`, `configure_ui_trace_log`, `configure_pipeline_trace_log`, `configure_startup_journey_log` вызываются только при включённом флаге. JSONL trace-файлы (`logs/api-trace.jsonl`, `logs/pipeline-trace.jsonl`, `logs/ui-trace.jsonl`, `logs/startup-journey.jsonl`) не создаются и helper-функции становятся no-op без флага.
- **`backend/core/runtime_lifecycle_trace.py`** — `runtime_trace()` короткозамкнут на `is_runtime_lifecycle_trace_enabled()` (события `runtime_lifecycle.*` в `runtime-events.log` не пишутся, если выключено).
- **`backend/core/structured_runtime_logger.py`** — добавлен per-event severity-фильтр. По умолчанию пишутся только `INF/WRN/ERR/CRT` события (`translation_publish_accepted`, `browser_external_final`, `browser_degraded`, …). `DBG/VRB` поток (`basr.fsm_transition`, `basr.policy_action_result`, `browser_worker_status`, `translation_queue_depth_changed`, `browser_rearm_scheduled`, …) подключается через `SST_TRACE_RUNTIME_EVENTS_VERBOSE=1` (или мастер-свитч). Это сокращает `logs/runtime-events.log` на штатной сессии примерно в 20–50 раз (с ~250 КБ до ~5–15 КБ) и совпадает с 0.4.1-дисковым следом для install-папок.
- **`desktop/launcher.py`** — `configure_startup_journey_log`, `configure_ui_trace_log`, `configure_api_trace_log` теперь обёрнуты `is_startup_journey_enabled()` / `is_ui_trace_enabled()` / `is_api_trace_enabled()` гейтом, так что desktop процесс не создаёт пустые `startup-journey.jsonl` / `ui-trace.jsonl` / `api-trace.jsonl` рядом с public exe без явного opt-in (раньше эти файлы создавались launcher-процессом независимо от backend-гейта). `deps-install-trace.jsonl` и `subprocess-trace.jsonl` остаются always-on для bootstrap triage (маленькие).
- Opt-in deep traces: `SST_TRACE_RUNTIME_EVENTS_VERBOSE` и desktop launcher-гейты для JSONL-трейсов.
- Регрессии: `tests/test_diagnostic_flags.py` (флаги off-by-default, мастер-свитч, индивидуальные флаги, truthy-токены, no-op helpers); `tests/test_structured_runtime_logger.py::test_default_skips_dbg_and_vrb_events` (DBG/VRB фильтр); `tests/test_api_and_websockets.py::test_runtime_start_emits_structured_lifecycle_trace` обёрнут `mock.patch.dict("os.environ", {"SST_TRACE_RUNTIME_LIFECYCLE": "1"})`.

### Документация

Инженерный hardening, ранее лежавший в `Unreleased` поверх `0.4.1`, фиксируется как часть `0.4.2`-линии:

### Runtime orchestrator и local Parakeet

- **`RuntimeOrchestrator`** (`backend/core/runtime_orchestrator.py`, ~380 строк) — тонкий фасад с mixin-модулями: `runtime_orchestrator_{lifecycle,local_asr,browser_worker,diagnostics,state_metrics,remote_ingress}_mixin.py`.
- Вынесены модули local ASR: `local_asr_pipeline`, `local_asr_realtime_settings`, `local_asr_recognition_processing`, `local_asr_hallucination_filter`, `local_asr_vad_tuning`, `local_parakeet_transcript_segment`, `segment_audio_enqueue`, `partial_emit_coordinator`, `realtime_transcript_emit_policy`, `asr_diagnostics_assembler`, `browser_worker_transcript_builders`.
- `PartialEmitCoordinator`: исправлен порядок mark → duplicate check для partial emit.
- `prepare_recognition_audio_bytes`: legacy `experimental_noise_reduction_enabled` + type guard (согласовано с `apply_recognition_processing_settings`).
- `parakeet_provider`: кэш результата `nvidia-smi` (не блокировать event loop на каждом diagnostics/status).

### WebSocket и Browser ASR transport

- **`WebSocketManager`**: per-connection `asyncio.Lock` для сериализации `send_json` (`_send_json_locked`); `send_direct` для bootstrap `hello` на `/ws/events`; регрессии в `test_ws_manager.py`.
- **`BrowserAsrService`**: `_send_lock` для worker socket; `send_hello`; idempotent `disconnect`; отклонение stale session rollback по `generation_id`; регрессии в `test_browser_asr_service.py`.

### Dashboard UI и конфиг (frontend)

- **`store.js`**: `emit()` — snapshot listeners + `try/catch` per listener (сбой одной панели не останавливает остальные).
- **`dom.js`**: `setInputValueIfChanged`, `setCheckedIfChanged` — idempotent render без сброса caret/focus.
- Панели: diagnostics `configJson`, ASR/OBS/overlay/translation/profiles/remote — idempotent DOM updates; ASR/OBS — один `change` handler на checkbox/select; remote panel — без двойной подписки на config; translation panel — импорт `getLineMap`.
- **`config-normalizer.js`**: `asr.browser.continuous_results` default **true** (`!== false`), согласовано с backend.

### Desktop launcher и bootstrap

- **`desktop/launcher.py`**: ротация `desktop-launcher.log` → `desktop-launcher.old.log` (и sibling live logs) при старте.
- **`desktop/bootstrap_launcher.py`**: ротация `bootstrap-launcher.log`; GitHub update check timeout **2.5 s**.
- Новые тесты: `test_desktop_launcher_config.py`, `test_desktop_bootstrap_payload.py`, `test_desktop_runtime_bootstrap.py`.

### Документация

- `docs/TECHNICAL_ARCHITECTURE.md` — полное обновление §6, §9, §14, §16–§17, §20–§21.
- `README.md` / `README.ru.md` — architecture summary, recognition, desktop logs, dashboard UX stability.

### Тесты

- `python -m unittest discover -s tests -p "test_*.py"` — **462** collected, **461** OK (1 pre-existing loader error: `test_browser_asr_observability` import `tests.test_translation_dispatcher`).

## 0.4.1

Релиз поверх `0.4.0`. `PROJECT_VERSION = "0.4.1"`; `config_version` остаётся **7**. Публичные HTTP/WebSocket-контракты и жизненный цикл субтитров сохранены. Delta: [docs/DESKTOP_RELEASE_CHANGELOG_0.4.1.md](./DESKTOP_RELEASE_CHANGELOG_0.4.1.md).

### Что вошло

- **Local Parakeet realtime:** streaming decode, `word_growth` partial policy, delta ASR queue, overlay partial dedup bypass; `LocalAsrPipeline` и `local_asr_realtime_settings`.
- **Dashboard:** пресеты задержки на Tuning, согласованные слайдеры с пресетами, подсказки Save + Stop/Start; строка runtime с сохранённым realtime-профилем; Tools → поля `streaming_decode`, `partial_emit_mode`, `partial_min_new_words`, зеркало пресета.
- **Продукт:** только `official_eu_parakeet_low_latency` в UI; миграция старых `official_eu_parakeet` в low latency.
- **Диагностика:** расширенный `AsrDiagnostics` (preset / streaming / emit mode / min words).
- **Документация:** обновлён `docs/TECHNICAL_ARCHITECTURE.md` (пайплайн Parakeet 0.4.1).

### Тесты

- `python -m unittest discover -s tests` — прогон после изменений (tracked suite; desktop-only тесты — локально при наличии `desktop/`).

## 0.4.0

Релиз поверх `0.3.2`. `PROJECT_VERSION = "0.4.0"`; `config_version` остаётся **7**. Публичные HTTP/WebSocket-контракты и жизненный цикл субтитров сохранены.

### Что вошло

- **Browser ASR observability:** `timekeeping.py`, `browser_asr_*` (trace, normalized ingest, operational FSM, recovery policy, JSONL replay); L2 ingress (stale transport / overlap); trace-поля на `TranscriptSegment`.
- **WebSocket:** bounded per-connection queues, drop-oldest; `replay_last` (§9 `TECHNICAL_ARCHITECTURE.md`).
- **Перевод:** preview supersession в `translation_dispatcher.py`.
- **Компактный дашборд:** `ui.layout` `standard` | `compact`; `compact-layout.css`, `layout/layout-controller.js`; ресайз окна desktop-shell при смене layout (~1440×940 vs ~400×844).
- **Desktop exe:** второй bootstrap `Stream Subtitle Translator Only Web.exe` (Web Speech без splash профилей); в стандартном exe — payload 0.4.0 с теми же splash-профилями, что раньше.
- **Web Speech quick start:** `asr.desktop_profile_lock` в схеме config и после save/load; Recognition без Local Parakeet до запуска с GPU/CPU (`desktop-profile-lock.js`, нормализаторы, packaged launcher).
- **Desktop dashboard:** панели монтируются сразу; справка (`dashboard-help-topics.html`) и `loadInitialData()` — в фоне; `desktop.js` / `main.js` не блокируют UI на `pywebviewready`.
- **Desktop launcher (pywebview):** переход на дашборд через `location.replace` вместо `load_url`; без `evaluate_js` в splash после навигации; ранний `GET /` + health в фоне; не вызывать `get_current_url()` из `loaded`-handler; профиль WebView2 в `runtime_root/pywebview-profile`.
- **Fix:** `RuntimeOrchestrator.browser_asr_worker_connected()` — worker WS не обрывается сразу после connect.
- **Тесты (GitHub):** `test_browser_asr_observability.py`, `test_frontend_modular_vanilla.py`, расширены ws/translation/browser contracts. Desktop packaging tests — только локально (`test_desktop_launcher_startup.py`, `test_launcher.py`, …).

### Тесты

- `python -m unittest discover -s tests` — **336** tests, `OK` (локально с desktop-only тестами; в публичном репозитории — tracked suite без `desktop/`).

## 0.3.2

Релиз поверх `0.3.1`. `PROJECT_VERSION = "0.3.2"`; `config_version = 7` (`source_text_replacement`).

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
- `README.md` / `README.ru.md`: версия `0.3.2`.

### Тесты

- Полный прогон: `python -m unittest discover -s tests` — **298** тестов, `OK` (на момент фиксации релиза).

## 0.3.1

Релиз стабилизации поверх `0.3.0`. `PROJECT_VERSION = "0.3.1"`. Публичные `/api`/WebSocket без изменений.

### Версия и идентификация

- `backend/versioning.py`: `PROJECT_VERSION = "0.3.1"`, источник правды для `GET /api/version` и `POST /api/updates/check`.
- bootstrap-лаунчер и desktop-shell поднимают эту же версию.

### Bootstrap-лаунчер

- В полном dev-дереве: `desktop/bootstrap_launcher.py`, `desktop/bootstrap_payload.py` (в публичном GitHub-клоне каталог `desktop/` может отсутствовать).
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
- Per-version installer delta для `0.3.1` (ранее отдельный файл; содержимое в этом CHANGELOG).

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
