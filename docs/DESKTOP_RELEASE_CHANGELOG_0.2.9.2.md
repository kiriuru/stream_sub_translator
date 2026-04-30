# SST Desktop 0.2.9.2

Delta changelog относительно `0.2.9.1`.

Предыдущий delta changelog:
- [DESKTOP_RELEASE_CHANGELOG_0.2.9.1.md](./DESKTOP_RELEASE_CHANGELOG_0.2.9.1.md)

## Кратко

Версия `0.2.9.2` — это patch-релиз со стабилизацией сохранения настроек и desktop translation UI:
- исправлено сохранение языка интерфейса;
- добавлено более широкое тестовое покрытие save/load основных групп настроек;
- исправлена ложная надпись в карточке последнего перевода, когда translation уже фактически выполнен.

## Изменения относительно 0.2.9.1

### 1. UI language теперь сохраняется в config

Ранее язык интерфейса жил в browser storage и не проходил через общий desktop config round-trip.

Теперь:
- язык интерфейса сохраняется в `ui.language`;
- загружается обратно из desktop config;
- остаётся совместимость со старыми конфигами, где этого поля ещё не было.

Практический эффект:
- выбранный язык интерфейса не должен теряться между перезапусками;
- язык больше не выпадает из общего save/load поведения desktop-настроек.

### 2. Широкий round-trip test для основных настроек

Добавлено regression-покрытие на сохранение и повторную загрузку основных групп настроек:
- `ui`
- `audio`
- `asr`
- `translation`
- `subtitle_output`
- `subtitle_lifecycle`
- `obs_closed_captions`
- `remote`
- `updates`

Это не заменяет ручной UI smoke-test, но покрывает центральный backend config/API save/load path.

### 3. Исправлена карточка `Translated Results`

Найдена проблема в desktop translation UI:
- `TranslationDispatcher` посылал completion-event;
- фронтенд трактовал его как пустой translation state;
- карточка могла показать сообщение, что перевод выключен, хотя translation уже реально пришёл.

Теперь:
- completion-event сохраняет итоговый translation payload;
- фронтенд не должен затирать реальные переводы пустым completion update;
- карточка последнего результата должна оставаться согласованной с фактическим translation state.

## Проверка

Для `0.2.9.2` были прогнаны:
- `.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_config_translation_providers.py"`
- `.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_translation_dispatcher.py"`
- `.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"`
- `build-bootstrap-launcher.bat`
- `publish-desktop-releases.ps1`
