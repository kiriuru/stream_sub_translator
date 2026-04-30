# SST Desktop 0.2.9.0

SST Desktop — локальное Windows-приложение для распознавания речи в реальном времени, опционального перевода, маршрутизации субтитров и вывода в OBS.

Этот README описывает только desktop-версию релиза.

## Язык
- English version: [README.md](./README.md)

## Техническая документация
- Полный технический документ: [docs/TECHNICAL_ARCHITECTURE.md](./docs/TECHNICAL_ARCHITECTURE.md)

## Состав релиза
Основной desktop release теперь поставляется как:
- `Stream Subtitle Translator.exe`

При первом запуске bootstrap launcher сам распаковывает managed runtime рядом с собой и уже потом запускает legacy desktop runtime с диска.

## Быстрый старт
1. Распакуйте архив в папку с правом записи.
2. Проверьте, что рядом находятся:
   - `Stream Subtitle Translator.exe`
   - `app-runtime/`
3. Запустите `Stream Subtitle Translator.exe`.
4. В splash-окне выберите один из профилей запуска:
   - `Quick Start (Browser Speech)`
   - `Local AI (NVIDIA GPU)`
   - `Local AI (CPU)`
5. Дождитесь открытия локального dashboard.

## Bootstrap Launcher
Теперь bootstrap launcher является основным desktop release flow.

Что он делает:
- отдается пользователю как один публичный `Stream Subtitle Translator.exe`;
- содержит embedded managed payload, собранный из clean desktop runtime;
- при первом запуске распаковывает и проверяет legacy managed runtime рядом с собой;
- умеет чинить managed runtime, если повреждены `app-runtime/` или внутренний runtime exe.

Текущая раскладываемая структура:
- публичный launcher: `Stream Subtitle Translator.exe`
- managed runtime folder: `app-runtime/`
- скрытый внутренний runtime exe: `.sst-runtime.exe`
- пользовательские данные: `user-data/`
- логи: `logs/`

Сборка из исходников:
- `build-bootstrap-launcher.bat`

Итоговый bootstrap artifact:
- `dist\bootstrap-launcher\Stream Subtitle Translator.exe`

## Профили запуска
- `Quick Start (Browser Speech)`:
  - самый быстрый путь старта;
  - распознавание остаётся в отдельном browser worker окне;
  - локальные AI-зависимости не доустанавливаются.
- `Local AI (NVIDIA GPU)`:
  - поднимает локальный CUDA PyTorch runtime;
  - рассчитан на системы с NVIDIA.
- `Local AI (CPU)`:
  - поднимает CPU-only PyTorch runtime;
  - рассчитан на AMD, Intel или системы без GPU.

## Что создаётся при первом запуске
Публичный release изначально содержит только:
- `Stream Subtitle Translator.exe`

При первом запуске bootstrap launcher сам распаковывает и/или создаёт рядом:
- `.sst-runtime.exe`
- `app-runtime/`
- `.python/`
- `.venv/`
- `user-data/`
- `logs/`

Для legacy desktop flow это нормальное поведение. Эти папки нужно хранить рядом с `.exe`.

## Основные возможности
- Распознавание речи с микрофона в реальном времени.
- Опциональный перевод на 0, 1 или несколько целевых языков.
- Гибкая схема вывода субтитров:
  - только оригинал
  - только перевод
  - оригинал + один перевод
  - оригинал + несколько переводов
- Вывод в OBS browser overlay.
- Опциональный вывод в OBS Closed Captions.
- Экспорт сессий в `SRT` и `JSONL`.
- Локальные профили настроек.

## Обзор интерфейса Desktop Dashboard
Главное окно включает:
- Runtime-бейджи:
  - health
  - runtime state
  - ASR provider и device
  - доступность partial
  - режим распознавания
  - статус перевода
  - статус OBS CC
- Runtime-состояния:
  - `idle`
  - `starting`
  - `listening`
  - `transcribing`
  - `translating`
  - `error`
- Основные кнопки:
  - `Start`
  - `Stop`
- Рабочие панели:
  - transcript (partial + final)
  - выбор микрофона
  - выбор режима распознавания
  - предпросмотр итоговых субтитров
  - локальный URL overlay

## Основные вкладки и назначение
### Translation
- Включение/выключение перевода.
- Выбор провайдера.
- Настройка ключей/endpoint/model/prompt (если требуется провайдером).
- `Google Cloud Translation - Advanced (v3)` теперь доступен как отдельный провайдер и использует `project_id` + OAuth access token вместо v2 API-ключа.
- Управление списком и порядком целевых языков.
- Просмотр последних результатов перевода.
- Runtime-перевод больше не держит live subtitles: source final публикуется сразу, а fan-out по целевым языкам уходит в асинхронный слой с timeout на каждый target.
- Поздние translation results теперь мержатся только пока соответствующая subtitle sequence ещё актуальна по lifecycle, поэтому старые jobs не догоняют новый overlay text.
- В `Tools & Data` теперь также выводятся runtime-счётчики dispatcher-а: depth очереди, отмены, stale drops и последние queue/provider latency, без изменения subtitle lifecycle.

### Subtitles
- Настройка пресета компоновки overlay:
  - `single`
  - `dual-line`
  - `stacked`
- Отображение/скрытие исходного текста.
- Отображение/скрытие переводов.
- Ограничение числа видимых строк перевода.
- Тайминги жизненного цикла субтитров (hold/replace/sync expiry).
- Порядок вывода, общий для preview и overlay.

### Style
- Применение встроенных пресетов стиля.
- Сохранение/удаление пользовательских пресетов.
- Настройка базового стиля:
  - шрифт/размер/насыщенность
  - цвет, обводка, тень
  - фон
  - выравнивание и интервалы
  - эффекты
- Персональные override-настройки по слотам строк (source + translation lines).

### OBS
- Настройка OBS websocket host/port/password.
- Включение вывода в OBS Closed Captions.
- Режимы вывода:
  - `source_live`
  - `source_final_only`
  - `translation_1` ... `translation_5`
  - `first_visible_line`
- Опциональный debug mirror в обычный текстовый source OBS.
- Тайминги отправки partial/final.

### Tuning
- Быстрые ползунки поведения распознавания:
  - скорость появления текста
  - скорость финализации
  - стабильность/чувствительность к шуму
- Опциональный RNNoise (экспериментальный путь).
- Практические подсказки для live-режима.

### Tools & Data
- Runtime-диагностика и метрики задержек.
- Расширенные параметры realtime ASR.
- Лента live-событий.
- Сохранение/экспорт/импорт конфигурации.
- Загрузка/сохранение/удаление профилей.

## Режимы распознавания
### Local Parakeet
- Локальный runtime и локальный захват аудио.
- GPU-first политика на совместимых системах NVIDIA.
- При необходимости доступен CPU fallback.

### Browser Speech
- Работает через отдельное окно Chrome/Chromium/Edge (`/google-asr`) с обычной адресной строкой, чтобы можно было выдать доступ к микрофону и выбрать устройство.
- Требует доступ к микрофону в браузере.
- Для стабильности держите окно worker видимым во время работы.
- Настройки worker теперь уважают сохранённый флаг `continuous_results`, а не принудительно включают его внутри страницы.
- Обычный `onend` в Web Speech теперь быстро переармливается, если окно должно продолжать слушать; длинный backoff применяется только к повторяющимся `start()` failures и terminal permission errors.
- Browser worker теперь отправляет backend diagnostics о reconnect/degraded/watchdog состоянии, чтобы UI отличал disconnect, hidden-window throttling и повторяющиеся rearm failures.
- Structured browser-recognition diagnostics теперь пишутся по meaningful status-transition событиям worker-а, чтобы после пауз можно было понять, был ли `onend`, watchdog rearm, hidden-window throttle или terminal browser error.

## Локальные URL (Dashboard/Overlay/Worker)
- Dashboard: `http://127.0.0.1:8765/`
- Overlay: `http://127.0.0.1:8765/overlay`
- Browser worker: `http://127.0.0.1:8765/google-asr`
- Overlay теперь очищает зависший текст при websocket-disconnect и после reconnect получает последний subtitle payload, если локальный backend ещё работает.

Примеры query для overlay:
- `?profile=default`
- `?compact=1`

## Remote Notes
В исходном репозитории по-прежнему есть опциональный LAN controller/worker workflow, и теперь desktop splash показывает его как вторичный сценарий:
- desktop launcher по умолчанию работает на `127.0.0.1`;
- `Remote Controller` и `Remote Worker` находятся в компактном вторичном блоке `Remote modes` в splash launcher;
- remote-tools внутри `Tools & Data` по умолчанию свернуты и перенесены вниз вкладки.

## Где лежат данные и логи
Создаются рядом с `.exe`:
- `user-data/`
  - `config.json`
  - `profiles/`
  - `exports/`
  - `models/`
  - `cache/`
- `logs/`
  - `desktop-launcher.log`
  - `translation-dispatcher.log`
  - `browser-recognition.log`
  - `browser-recognition-live.log`
  - `overlay-events.log`
  - `dashboard-live-events.log`

Для новых hot-path диагностик:
- задержки/timeout/stale drop перевода:
  - смотрите `logs/translation-dispatcher.log`
- паузы/rearm/degraded у Browser Speech:
  - смотрите `logs/browser-recognition.log`
- человекочитаемая лента overlay/dashboard:
  - смотрите `logs/overlay-events.log` и `logs/dashboard-live-events.log`

Runtime-кеши и temp-папки управляются автоматически. Первый запуск может быть дольше из-за инициализации.

## Системные требования
- Windows 10/11 x64
- Доступ к микрофону
- Для GPU-режима: NVIDIA GPU + совместимый CUDA runtime stack
- Для внешних переводчиков: интернет + валидные ключи/доступы провайдера

## Обновление
Чтобы обновить SST Desktop:
1. Закройте приложение.
2. Замените публичный `Stream Subtitle Translator.exe`.
3. Сохраните существующие `.python/`, `.venv/`, `user-data/` и `logs/`, если хотите оставить локальный runtime state, настройки и историю.
4. Если `app-runtime/` или `.sst-runtime.exe` повреждены, используйте:
   - `--repair`
   - `--reset-runtime`
   или соответствующие maintenance-кнопки в bootstrap splash окне.

## Сборка Из Исходников
- Поднимите локальное dev-окружение через `start.bat`.
- Соберите desktop one-folder пакет через `build-desktop.bat`.
- Соберите экспериментальный bootstrap one-file launcher через `build-bootstrap-launcher.bat`.
- Подготовьте clean release папки через `publish-desktop-releases.ps1`.
- Итоговые артефакты:
  - `dist\Stream Subtitle Translator\`
  - bootstrap launcher:
    - `dist\bootstrap-launcher\`
  - clean release mirror:
    - `...\stream-sub-translator-desktop-release-clean\`

## Roadmap Для Bootstrap Launcher
- Сначала реализованы install / verify / repair.
- Runtime update из release assets и отдельный self-update launcher-а пока только запланированы и описаны здесь:
  - [docs/desktop-bootstrap-roadmap.md](./docs/desktop-bootstrap-roadmap.md)

## Быстрый troubleshooting
- Приложение не стартует:
  - просто запустите bootstrap launcher повторно и дайте ему заново создать `app-runtime/`.
- Managed runtime выглядит повреждённым:
  - используйте кнопку `Repair Runtime` в bootstrap окне;
  - или запустите `Stream Subtitle Translator.exe --repair`.
- Managed runtime нужно пересобрать с нуля:
  - используйте кнопку `Reset Runtime` в bootstrap окне;
  - или запустите `Stream Subtitle Translator.exe --reset-runtime`.
- Desktop window падает на инициализации:
  - проверьте `logs\desktop-launcher.log`;
  - проверьте локальный `pywebview/pythonnet` runtime внутри `app-runtime/`.
- Интерфейс не открывается:
  - убедитесь, что локальный порт `8765` не занят.
- В Browser Speech нет текста:
  - выдайте доступ к микрофону в браузере;
  - держите окно worker открытым и видимым.
- Медленный первый запуск в AI-режиме:
  - дождитесь завершения инициализации runtime/моделей.
- Нет вывода в OBS:
  - проверьте OBS websocket-параметры и выбранный output mode.

## Автотесты
- Текущие regression-тесты запускаются так:
  - `.venv\Scripts\python.exe -m unittest discover -s tests`

## Что изменилось в 0.2.9.0
- Убран нерабочий translation provider `MyMemory`.
- Добавлен `Google Cloud Translation - Advanced (v3)` как отдельный провайдер, не смешанный с `Google Translate v2`.
- Версия проекта теперь последовательно используется в формате `0.2.9.0` в runtime, API и документации.

## Приватность и границы выполнения
- SST Desktop работает в local-first режиме.
- Dashboard, API, websocket-события, overlay, логи, профили, кеш и экспорты работают на одной машине.
- По умолчанию используется localhost (`127.0.0.1`).

## Версия релиза
- `0.2.9.0`
- Единый runtime-источник версии: `backend/versioning.py` (`PROJECT_VERSION`).
- Каркас будущей синхронизации с GitHub releases:
  - секция `updates` в `backend/data/config.example.json` и локальном `config.json`;
  - endpoint `GET /api/version` (возвращает локальную версию и метаданные синхронизации, без live-пуллинга по умолчанию).
