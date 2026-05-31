## Stream Subtitle Translator 0.4.4

EN:

This release updates the desktop bootstrap payload to app version **0.4.4** (`config_version` **7** unchanged). Public API/WebSocket contracts and subtitle/translation lifecycle semantics are unchanged.

Included in this release:

- **UI localization (ja / ko / zh):** dashboard, Browser Speech worker, and OBS overlay support **en**, **ru**, **ja**, **ko**, **zh**; split locale files + synchronous `locales-bundle.js` for reliable WebView2 load; instant language switch with config persistence;
- **OpenAI helper SSRF guard:** when bound beyond localhost, `/api/openai/models` and `/api/openai/usable-models` block private/loopback/metadata URLs in `base_url`; default `127.0.0.1` bind still allows local OpenAI-compatible servers;
- **Overlay WebSocket:** shared stale guard + exponential reconnect (1–10 s); OBS overlay keeps the last frame during disconnect;
- **Desktop launcher refactor:** `desktop/launcher.py` split into focused modules (`launcher_bootstrap`, `launcher_window`, `launcher_backend`, `launcher_context`, `launcher_api`, `browser_worker_launcher`);
- **Dashboard store:** `store.desktop` + `patchDesktopContext()` — single desktop context snapshot for panels;
- **ASR Advanced UX:** per-field `?` help popovers, two-column layout, localized “Recommended” hints; removed duplicate side notes block;
- **Idle subtitle preview:** style placeholder stays visible after **Save** until runtime **Start** — empty post-save `overlay_update` no longer clears the dashboard preview.

### Desktop release format

- `Stream Subtitle Translator.exe` — bootstrap launcher (startup profiles unchanged; embedded app **0.4.4**);
- `Stream Subtitle Translator Only Web.exe` — Web Speech quick start (unchanged role from 0.4.0).

### Change history

- full changelog: [docs/CHANGELOG.md](https://github.com/kiriuru/stream_sub_translator/blob/main/docs/CHANGELOG.md)

---

## RU

Релиз обновляет payload внутри desktop bootstrap до версии приложения **0.4.4** (`config_version` **7** без изменений). Публичные API/WebSocket и семантика жизненного цикла субтитров/перевода сохранены.

Что вошло:

- **Локализация UI (ja / ko / zh):** dashboard, Browser Speech worker и OBS overlay — **en**, **ru**, **ja**, **ko**, **zh**; отдельные locale-файлы + синхронный `locales-bundle.js` для WebView2; мгновенная смена языка с сохранением в конфиг;
- **SSRF guard для OpenAI helper:** при bind не только на localhost маршруты `/api/openai/models` и `/api/openai/usable-models` блокируют private/loopback/metadata URL в `base_url`; при default `127.0.0.1` локальные OpenAI-compatible серверы по-прежнему разрешены;
- **Overlay WebSocket:** общий stale guard + exponential reconnect (1–10 с); OBS overlay сохраняет последний кадр на время disconnect;
- **Рефактор desktop launcher:** split `desktop/launcher.py` на модули (`launcher_bootstrap`, `launcher_window`, `launcher_backend`, `launcher_context`, `launcher_api`, `browser_worker_launcher`);
- **Dashboard store:** `store.desktop` + `patchDesktopContext()` — единый snapshot desktop-контекста для панелей;
- **ASR Advanced UX:** кнопка `?` у каждого поля, двухколоночная сетка, локализованные подсказки «рекомендуемое»; удалён дублирующий боковой блок notes;
- **Idle preview субтитров:** placeholder остаётся после **Save** до **Start** — пустой `overlay_update` после сохранения конфига больше не затирает предпросмотр в дашборде.

### Формат desktop release

- `Stream Subtitle Translator.exe` — bootstrap (профили запуска те же; внутри приложение **0.4.4**);
- `Stream Subtitle Translator Only Web.exe` — быстрый старт Web Speech (как в 0.4.0).

### История изменений

- полный changelog: [docs/CHANGELOG.md](https://github.com/kiriuru/stream_sub_translator/blob/main/docs/CHANGELOG.md)
