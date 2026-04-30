# SST Desktop Changelog

Единая история изменений desktop-версии.

Этот файл является каноническим changelog для релизов SST Desktop.
Старые version-specific release notes можно сохранять как архивные заметки, но для текущей истории изменений ориентироваться нужно на этот файл.

## 0.2.9.2

Patch-релиз со стабилизацией сохранения настроек и desktop translation UI.

Основные изменения:
- исправлено сохранение языка интерфейса;
- добавлено более широкое тестовое покрытие save/load основных групп настроек;
- исправлена ложная надпись в карточке последнего перевода, когда translation уже фактически выполнен.

Детали:
- язык интерфейса теперь сохраняется в `ui.language` и проходит через общий desktop config round-trip;
- добавлено regression-покрытие на `ui`, `audio`, `asr`, `translation`, `subtitle_output`, `subtitle_lifecycle`, `obs_closed_captions`, `remote`, `updates`;
- completion-event `TranslationDispatcher` больше не затирает реальные переводы пустым payload;
- карточка `Translated Results` теперь остаётся согласованной с фактическим translation state.

Проверка:
- `.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"`
- `build-bootstrap-launcher.bat`
- `publish-desktop-releases.ps1`

## 0.2.9.1

Patch-релиз с фиксом bootstrap AI install и жёстким восстановлением Browser Speech window invariant.

Основные изменения:
- clean portable AI bootstrap больше не должен падать на отсутствующем `lightning` при установке NeMo ASR зависимостей;
- desktop Browser Speech возвращён к старому стабильному сценарию запуска: отдельное окно Chrome/Chromium/Edge с видимой адресной строкой и isolated browser profile;
- из desktop UI убран selector режима окна browser worker;
- это поведение зафиксировано в AGENTS, README и технической документации как обязательный invariant.

Детали:
- в desktop runtime bootstrap добавлен офлайн seed для `lightning 2.4.0` перед установкой NeMo ASR зависимостей;
- browser worker снова запускается через отдельное окно с адресной строкой и isolated profile;
- user-facing mode toggle для browser worker window больше не поддерживается.

Совместимость:
- bootstrap one-file launcher остаётся primary release flow;
- managed runtime по-прежнему раскладывается рядом с `Stream Subtitle Translator.exe`;
- `user-data/` и `logs/` остаются локальными рядом с desktop runtime;
- default local-first behavior и localhost bind не меняются.

Проверка:
- `.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"`
- `build-bootstrap-launcher.bat`
- `publish-desktop-releases.ps1`

## 0.2.9.0

Крупный desktop-релиз с переходом на bootstrap one-file launcher и новой translation/runtime моделью.

Основные изменения:
- primary release flow переведён на bootstrap one-file launcher;
- публичный релиз распространяется как один `Stream Subtitle Translator.exe`;
- launcher при первом запуске сам раскладывает managed runtime рядом и умеет `verify / repair / reset`;
- source final публикуется сразу;
- перевод работает асинхронно и параллельно по target languages;
- stale translation results больше не должны догонять новый overlay;
- browser speech worker стал устойчивее к `onend`, visibility throttling и reconnect-сценариям;
- в runtime добавлены structured logs и live diagnostics для translation и browser ASR;
- desktop dashboard и overlay стали лучше переживать websocket reconnect и late translation arrival.

Ключевые технические изменения:
- новый async `TranslationDispatcher`;
- новый subtitle lifecycle с отдельными TTL для source и translation;
- structured JSONL logging для hot paths;
- live diagnostics в dashboard;
- улучшения overlay reconnect и OBS Closed Captions dedupe;
- повышение устойчивости translation cache;
- удалён `MyMemory`;
- добавлен `Google Cloud Translation - Advanced (v3)`.

Packaging итог:
- пользователь скачивает один `exe`;
- launcher сам восстанавливает `app-runtime/`, если он отсутствует или повреждён;
- managed runtime можно обновить простой заменой публичного `exe`.

Что пока не входило:
- runtime update из GitHub Releases;
- self-update самого launcher-а.
