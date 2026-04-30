# SST Desktop 0.2.9.1

Delta changelog относительно `0.2.9.0`.

Предыдущий полный changelog:
- [DESKTOP_RELEASE_CHANGELOG_0.2.9.0.md](./DESKTOP_RELEASE_CHANGELOG_0.2.9.0.md)

## Кратко

Версия `0.2.9.1` является patch-релизом для desktop-сборки и фиксирует два проблемных места, всплывших после `0.2.9.0`:
- clean portable AI bootstrap больше не должен падать на отсутствующем `lightning` при установке NeMo ASR зависимостей;
- desktop Browser Speech снова жёстко возвращён к старому стабильному сценарию запуска: отдельное окно Chrome/Chromium/Edge с видимой адресной строкой и isolated browser profile.

Дополнительно:
- из desktop UI убран selector режима окна browser worker;
- в AGENTS, README и технической документации это поведение зафиксировано как обязательный invariant.

## Изменения относительно 0.2.9.0

### 1. Browser Speech window invariant восстановлен

В desktop launcher возвращён и зафиксирован старый рабочий запуск browser worker:
- отдельное окно Chrome/Chromium/Edge;
- видимая адресная строка;
- отдельный `browser-worker-profile`;
- запуск через `--new-window`, а не через `--app`.

Что убрано:
- user-facing переключатель режима окна browser worker;
- попытки запускать worker как app-window без browser chrome;
- временные popup/bootstrap launch схемы.

Практический результат:
- снова доступен значок разрешений в адресной строке для выдачи и смены микрофона;
- desktop UI больше не предлагает режимы, которые расходятся с ожидаемым рабочим поведением;
- future changes теперь должны сохранять именно этот сценарий, а не переизобретать его.

### 2. AI bootstrap fix для fresh portable installs

В desktop runtime bootstrap добавлен офлайн seed для `lightning 2.4.0` перед установкой NeMo ASR зависимостей.

Что это исправляет:
- clean portable install больше не должен падать на ошибке вида `No matching distribution found for lightning<=2.4.0,>2.2.1`;
- поведение стало ближе к уже рабочему dev/runtime окружению, где `lightning` ранее оказывался установленным заранее.

### 3. Документация и version sync

Обновлено:
- `backend/versioning.py` -> `0.2.9.1`;
- `README.md`;
- `README.ru.md`;
- `docs/TECHNICAL_ARCHITECTURE.md`.

Во всех этих местах теперь зафиксировано:
- текущая версия релиза `0.2.9.1`;
- bootstrap one-file desktop flow остаётся primary release path;
- Browser Speech в desktop режиме всегда открывается как отдельное окно с адресной строкой;
- user-facing mode toggle для browser worker window больше не поддерживается.

## Совместимость

Patch `0.2.9.1` не меняет базовую desktop-архитектуру из `0.2.9.0`:
- bootstrap one-file launcher остаётся primary release flow;
- managed runtime по-прежнему раскладывается рядом с `Stream Subtitle Translator.exe`;
- `user-data/` и `logs/` сохраняются локально рядом с desktop runtime;
- default local-first behavior и localhost bind не меняются.

## Проверка

Для этого patch-релиза были прогнаны:
- `.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"`
- `build-bootstrap-launcher.bat`
- `publish-desktop-releases.ps1`
