# SST Desktop 2.8.0

SST Desktop — локальное Windows-приложение для распознавания речи в реальном времени, опционального перевода, маршрутизации субтитров и вывода в OBS.

Этот README описывает только desktop-версию релиза.

## Язык
- English version: [README.md](./README.md)

## Техническая документация
- Полный технический документ: [docs/TECHNICAL_ARCHITECTURE.md](./docs/TECHNICAL_ARCHITECTURE.md)

## Состав релиза
В clean-релиз входят только:
- `Stream Subtitle Translator.exe`
- `app-runtime/`

Не удаляйте и не переименовывайте `app-runtime/`: `.exe` ожидает эту папку рядом.

## Быстрый старт
1. Распакуйте архив в папку с правом записи.
2. Проверьте, что рядом находятся:
   - `Stream Subtitle Translator.exe`
   - `app-runtime/`
3. Запустите `Stream Subtitle Translator.exe`.
4. В splash-окне:
   - Шаг 1: выберите `Local Mode` или `Remote Mode`
   - Шаг 2: выберите профиль/роль запуска
5. Дождитесь открытия dashboard.

## Профили запуска
- Local mode:
  - `Quick Start (Browser Speech)` для максимально быстрого старта
  - `Local AI (NVIDIA GPU)` для локального распознавания с приоритетом GPU
  - `Local AI (CPU)` для локального распознавания без GPU
- Remote mode:
  - `Main PC (Control & Captions)` для роли контроллера
  - `AI Processing PC` для роли worker (включается LAN bind)

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
- Управление списком и порядком целевых языков.
- Просмотр последних результатов перевода.

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
- Работает через отдельное browser worker окно (`/google-asr`).
- Требует доступ к микрофону в браузере.
- Для стабильности держите окно worker видимым во время работы.

## Локальные URL (Dashboard/Overlay/Worker)
- Dashboard: `http://127.0.0.1:8765/`
- Overlay: `http://127.0.0.1:8765/overlay`
- Browser worker: `http://127.0.0.1:8765/google-asr`

Примеры query для overlay:
- `?profile=default`
- `?compact=1`

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
  - `overlay-events.log`
  - `browser-recognition.log`
  - `dashboard-live-events.log`

Runtime-кеши и temp-папки управляются автоматически. Первый запуск может быть дольше из-за инициализации.

## Системные требования
- Windows 10/11 x64
- Доступ к микрофону
- Для GPU-режима: NVIDIA GPU + совместимый CUDA runtime stack
- Для внешних переводчиков: интернет + валидные ключи/доступы провайдера

## Обновление
Чтобы обновить SST Desktop:
1. Закройте приложение.
2. Замените:
   - `Stream Subtitle Translator.exe`
   - `app-runtime/`
3. Сохраните существующие `user-data/` и `logs/`, если хотите оставить настройки и историю.

## Быстрый troubleshooting
- Приложение не стартует:
  - проверьте, что `app-runtime/` лежит рядом с `.exe`.
- Интерфейс не открывается:
  - убедитесь, что локальный порт `8765` не занят.
- В Browser Speech нет текста:
  - выдайте доступ к микрофону в браузере;
  - держите окно worker открытым и видимым.
- Медленный первый запуск в AI-режиме:
  - дождитесь завершения инициализации runtime/моделей.
- Нет вывода в OBS:
  - проверьте OBS websocket-параметры и выбранный output mode.

## Приватность и границы выполнения
- SST Desktop работает в local-first режиме.
- Dashboard, API, websocket-события, overlay, логи, профили, кеш и экспорты работают на одной машине.
- По умолчанию используется localhost (`127.0.0.1`).

## Версия релиза
- `2.8.0`
- Единый runtime-источник версии: `backend/versioning.py` (`PROJECT_VERSION`).
- Каркас будущей синхронизации с GitHub releases:
  - секция `updates` в `backend/data/config.example.json` и локальном `config.json`;
  - endpoint `GET /api/version` (возвращает локальную версию и метаданные синхронизации, без live-пуллинга по умолчанию).
