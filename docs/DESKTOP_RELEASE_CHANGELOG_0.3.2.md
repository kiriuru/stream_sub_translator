# SST Desktop 0.3.2

## Русский

`0.3.2` — функциональный релиз поверх `0.3.1`: пост-ASR фильтр слов, обновление схемы конфига (`config_version = 7`), улучшения Web Speech worker, новые пресеты стилей субтитров и расширенная техническая документация по локальному Parakeet. Публичные HTTP-маршруты и базовый local-first контракт сохранены; меняется состав полей в сохраняемом `config.json` (добавлена секция `source_text_replacement`).

### Что нового в 0.3.2

- **Версия:** `backend/versioning.py` → `PROJECT_VERSION = "0.3.2"`.
- **Конфиг `config_version = 7`:** секция `source_text_replacement` (`enabled`, `include_builtin`, `case_insensitive`, `whole_words`, `pairs`).
- **Пост-ASR замена слов:** применяется в `TranscriptController` до субтитров, перевода и OBS captions; встроенный список `backend/data/source_text_builtin_pairs.json`; UI на вкладке «Инструменты и данные». Код: `backend/core/source_text_replacement.py`, нормализатор, тесты `tests/test_source_text_replacement.py`.
- **Web Speech:** `browser-web-speech-recognition-policy.js`, доработки `browser-asr-session-manager.js` (buddy-слот, обработка ошибок Chrome).
- **Стили:** пресеты `accessibility_high_contrast`, `dark_cinema`, `meeting_soft` в `subtitle_style.py`.
- **Документация:** `docs/TECHNICAL_ARCHITECTURE.md` (в т.ч. раздел про Parakeet/VAD/очередь), `README.md` / `README.ru.md`, канонический `docs/CHANGELOG.md`.

### Проверка

- `python -m compileall backend desktop tests`
- `.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -p "test_*.py"`
- `298 tests`, `OK`
- `cmd /c build-desktop.bat` (при необходимости clean) и `cmd /c build-bootstrap-launcher.bat`
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\\publish-desktop-releases.ps1` — копирование `Stream Subtitle Translator.exe` в каталоги installed/clean релиза

## English

`0.3.2` is a feature release on top of `0.3.1`: optional post-ASR word replacement, config schema bump to `config_version = 7`, Web Speech worker improvements, new subtitle style presets, and expanded technical documentation for the local Parakeet stack. Public HTTP routes and the local-first baseline are preserved; persisted `config.json` gains a `source_text_replacement` section.

### What is new in 0.3.2

- **Version:** `backend/versioning.py` → `PROJECT_VERSION = "0.3.2"`.
- **Config `config_version = 7`:** `source_text_replacement` block.
- **Post-ASR word replacement:** applied in `TranscriptController` before subtitles, translation, and OBS captions; bundled pairs JSON + dashboard UI under **Tools & Data**.
- **Web Speech:** `browser-web-speech-recognition-policy.js` and `browser-asr-session-manager.js` updates.
- **Styles:** `accessibility_high_contrast`, `dark_cinema`, `meeting_soft` presets.
- **Docs:** `docs/TECHNICAL_ARCHITECTURE.md` (including Parakeet/VAD/segment queue), README files, `docs/CHANGELOG.md`.

### Verification

- `python -m compileall backend desktop tests`
- `.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -p "test_*.py"`
- `298 tests`, `OK`
- `cmd /c build-bootstrap-launcher.bat`
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\\publish-desktop-releases.ps1`
