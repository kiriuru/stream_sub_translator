# SST Desktop 0.3.1

## Русский

`0.3.1` — релиз стабилизации поверх `0.3.0`. Базовый local-first режим, публичные `/api` и WebSocket-контракты не менялись.

### Главное

- Версия проекта обновлена до `0.3.1`.
- `RuntimeOrchestrator` стал тонким фасадом над явными runtime-контроллерами.
- `SubtitleRouter` разделён на lifecycle-core, presentation и фасад публикации.
- Провайдеры перевода вынесены в `backend/translation/providers/`.
- Переводческий кеш переписан на in-memory LRU с отложенной записью на диск.
- Запись config/profiles стала атомарной; повреждённый `config.json` автоматически сохраняется в backup, приложение стартует на defaults.
- Browser Speech в desktop-сборке запускается через отдельное окно Google Chrome с изолированным профилем.
- Добавлена дополнительная стабилизация Web Speech: Wake Lock, высокий приоритет процесса worker, opt-out из Windows EcoQoS, network preflight и health-сигнал `voice_below_recognition_threshold`.
- Добавлен live update checker: `POST /api/updates/check` и тихая проверка обновлений в bootstrap-лаунчере.
- Добавлены локальные helper endpoints для выбора моделей OpenAI-compatible провайдеров: `/api/openai/recommended-models`, `/api/openai/models`, `/api/openai/usable-models`.
- Dashboard получил карточки слотов перевода, расширенный i18n, тему/палитру, эффекты появления субтитров и вкладку Help.

### Проверка

- `python -m compileall backend desktop tests`
- `.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -p "test_*.py"`
- `286 tests`, `OK`

## English

`0.3.1` is a stabilization release on top of `0.3.0`. The local-first baseline and public `/api` / WebSocket contracts are unchanged.

### Highlights

- Project version is now `0.3.1`.
- `RuntimeOrchestrator` is now a thin facade over explicit runtime controllers.
- `SubtitleRouter` was split into lifecycle core, presentation, and publishing facade.
- Translation providers moved to `backend/translation/providers/`.
- Translation cache was rewritten as an in-memory LRU with deferred disk persistence.
- Config/profile writes are now atomic; corrupted `config.json` files are backed up automatically and the app starts with defaults.
- Desktop Browser Speech launches through a dedicated Google Chrome window with an isolated profile.
- Web Speech stability was improved with Wake Lock, high worker process priority, Windows EcoQoS opt-out, network preflight, and the `voice_below_recognition_threshold` health signal.
- Live update checking was added via `POST /api/updates/check` and the bootstrap launcher's silent update check.
- Local OpenAI-compatible model helper endpoints were added: `/api/openai/recommended-models`, `/api/openai/models`, `/api/openai/usable-models`.
- The dashboard gained translation slot cards, broader i18n, UI theme/palette settings, subtitle entrance effects, and the Help tab.

### Verification

- `python -m compileall backend desktop tests`
- `.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -p "test_*.py"`
- `286 tests`, `OK`
