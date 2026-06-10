# VoiceSub

**Преобразуйте голос в живые переводимые субтитры для стримов. Локально, privacy-first, готово для OBS.**

<p align="center">
  <a href="./README.md">English</a> • <a href="./README.ru.md">Русский</a> •
  <a href="./docs/WIKI.en.md">Wiki (EN)</a> • <a href="./docs/WIKI.ru.md">Wiki (RU)</a> •
  <a href="./docs/TECHNICAL_ARCHITECTURE.en.md">Technical Docs (EN)</a> •
  <a href="./docs/TECHNICAL_ARCHITECTURE.md">Technical Docs (RU)</a> •
  <a href="./docs/CHANGELOG.md">Changelog</a>
</p>

VoiceSub `0.5.0` — Windows desktop-приложение для стримеров, которым нужны субтитры в реальном времени с опциональным переводом. Объединяет browser speech recognition, стилизацию, маршрутизацию и вывод в OBS в одном local-first процессе. По умолчанию bind `127.0.0.1:8765` — без cloud backend и аккаунтов.

Преемник SST Desktop `0.4.4`. Стек: **Rust + Tauri**, **Svelte dashboard**, **vanilla OBS overlay**.

## Ключевые возможности

- Распознавание речи через **Chrome/Edge Web Speech worker** (`/google-asr`)
- Многоязычный перевод — **13 провайдеров**, до 5 линий перевода
- OBS **Browser Source overlay** + опциональные **OBS Closed Captions** (WebSocket)
- Анимированные пресеты субтитров, стили по слотам, палитра темы
- **TTS-модуль** — озвучка субтитров + опциональный Twitch chat TTS
- Экспорт diagnostics ZIP (redacted config + логи)
- Локали UI: **en, ru, ja, ko, zh**
- Компактный макет под второй монитор / узкое окно

**Не в core 0.5.0:** локальный Parakeet ASR, LAN remote mode, experimental browser routes (архив в `legacy/` для будущих модулей).

## Системные требования

- Windows 10/11 x64
- **Microsoft Edge WebView2 Runtime** — обязателен для desktop-оболочки VoiceSub (окно dashboard и TTS). На Windows 11 обычно уже установлен; на Windows 10 NSIS-установщик при отсутствии может запустить WebView2 bootstrapper.
- **Google Chrome** (или Edge для smoke) — отдельная system dependency для окна Web Speech worker
- Доступ к микрофону в окне browser worker
- Интернет для внешних провайдеров перевода (опционально)
- Для NSIS-установки: Python, Node.js и CUDA **не требуются** в core-пакете

## Быстрый старт

1. Установите **VoiceSub** из `VoiceSub_0.5.0_x64-setup.exe` (разработчикам: `build-release-msi.bat` → `build-release.ps1`) или папки релиза.
2. Запустите **VoiceSub.exe** — главное окно откроет dashboard на `http://127.0.0.1:8765/`.
3. В OBS добавьте **Browser Source** с URL `http://127.0.0.1:8765/overlay`.
4. При необходимости настройте перевод и стиль субтитров, нажмите **Start**.
5. Держите **окно browser worker** открытым и видимым (запускается автоматически) — разрешение микрофона выдаётся там.

Пошаговый гайд по UI: **[Wiki (RU)](./docs/WIKI.ru.md)** / **[Wiki (EN)](./docs/WIKI.en.md)**.

## Локальные URL

| URL | Назначение |
| --- | --- |
| `http://127.0.0.1:8765/` | Dashboard |
| `http://127.0.0.1:8765/overlay` | OBS Browser Source |
| `http://127.0.0.1:8765/google-asr?autostart=1` | Browser Speech worker |
| `http://127.0.0.1:8765/tts` | UI TTS-модуля |

Примеры query для overlay: `?preset=single`, `?compact=1`, `?profile=default`

## Конфигурация и данные

| Путь | Содержимое |
| --- | --- |
| `user-data/config.toml` | Основные настройки (TOML) |
| `user-data/profiles/` | Именованные профили |
| `user-data/translation-cache/` | Персистентный кэш перевода |
| `logs/` | `core.log`, `runtime-events.log`, `session-latest.jsonl` |
| `bin/fonts/` | Шрифты для субтитров |

SST `config.json` можно импортировать при первом запуске или через настройки — режимы `local` и `remote` маппятся в `browser_google`. См. [Technical Architecture §7](./docs/TECHNICAL_ARCHITECTURE.md).

## Troubleshooting

| Симптом | Проверить |
| --- | --- |
| Нет субтитров вообще | Нажат **Start**; worker-окно открыто; микрофон разрешён в Chrome |
| Есть исходник, нет перевода | Перевод включён; активна хотя бы одна линия; credentials провайдера |
| OBS пустой | Browser Source на `/overlay`; видимость во вкладке «Субтитры»; после обновления — перезагрузите Browser Source (cache-bust overlay) |
| Текст в OBS не исчезает после TTL/Stop | Обновите сборку; перезагрузите Browser Source (`overlay.js?v=20260610b`, fix idle TTL DOM clear) |
| Баннер обновления без текста / кнопка не открывает браузер | Обновите сборку (i18n `updates.banner.*`, IPC `open_external_https_url`) |
| Конфликт порта | Порт `8765` свободен |
| Worker «молчит» | Tools & Data → диагностика; `logs/core.log` |

Полный операционный гайд: **Wiki** → раздел 2.

## Contributing

PR приветствуются. Для крупных изменений — сначала issue.

```powershell
cargo test --workspace
npm run build
npm run test:frontend
```

Политика: `AGENTS.md`, контракт `docs/VOICESUB_ENGINEERING_CONTRACT.ru.md`.

## Документация

- [Wiki (RU)](./docs/WIKI.ru.md) / [Wiki (EN)](./docs/WIKI.en.md) — пользовательский гайд
- [Technical Architecture (RU)](./docs/TECHNICAL_ARCHITECTURE.md) / [(EN)](./docs/TECHNICAL_ARCHITECTURE.en.md)
- [Roadmap](./docs/plans/voicesub_roadmap.ru.md)

## Roadmap

Активная разработка: Parakeet и Remote как опциональные **sidecar-модули** после 0.5.0. См. `docs/plans/voicesub_roadmap.ru.md`.

## License

См. [LICENSE](./LICENSE).

---

<details>
<summary>Для разработчиков: архитектура и сборка</summary>

### Стек

| Слой | Технологии |
| --- | --- |
| Core | Rust workspace (`crates/voicesub-*`) + Axum HTTP/WS |
| Shell | Tauri 2 → `VoiceSub.exe` (NSIS installer) |
| Dashboard | Svelte 5 + Vite → `bin/dashboard/` |
| Worker | Svelte 5 → `bin/worker/` |
| Overlay | Vanilla HTML/JS → `bin/overlay/` |
| TTS | Svelte + Rust service + embedded Python sidecar |

Node.js — **только на этапе сборки**, не в установщике.

### Сборка из исходников

```powershell
npm install
npm run build          # dashboard + worker + TTS
cargo test --workspace
build-release-msi.bat  # → build-release.ps1 → NSIS setup.exe в release_root
```

Tauri `beforeBuildCommand`: `npm run build`. В bundle: `bin/dashboard`, `overlay`, `worker`, `tts`, `fonts`, `modules`.

### Ключевые crates

`voicesub-runtime`, `voicesub-subtitle`, `voicesub-translation`, `voicesub-browser`, `voicesub-ws`, `voicesub-tts`, `voicesub-obs`.

`src-tauri/` — тонкий IPC, без бизнес-логики.

Версия: `voicesub-types::PROJECT_VERSION` = `0.5.0`.

Полный reference: [Technical Architecture](./docs/TECHNICAL_ARCHITECTURE.md).

</details>
