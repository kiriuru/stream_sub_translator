"""Build frontend/js/i18n/dynamic-locales.js from embedded EN/RU pairs."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "js" / "i18n" / "dynamic-locales.js"

# fmt: off
PAIRS: dict[str, tuple[str, str]] = {
    "format.list.two": ("{first} and {second}", "{first} и {second}"),
    "format.list.many": ("{head}, and {last}", "{head} и {last}"),
    "config.save.live_applied_log": (
        "[config] saved locally{suffix}",
        "[config] сохранено локально{suffix}",
    ),
    "config.save.live_suffix": (" and applied live", " и применено сразу"),
    "config.save.failed_ui": ("Save failed: {message}", "Сохранение не удалось: {message}"),
    "config.save.failed_log": ("[config] save failed -> {message}", "[config] ошибка сохранения -> {message}"),
    "config.imported_log": ("[config] imported", "[config] импорт выполнен"),
    "config.exported_log": ("[config] exported", "[config] экспорт выполнен"),
    "config.restart_reason.microphone": ("microphone device", "микрофон"),
    "config.restart_reason.recognition_mode": ("recognition mode", "режим распознавания"),
    "config.restart_reason.asr_provider": ("ASR provider", "ASR-провайдер"),
    "config.restart_reason.gpu_policy": ("GPU policy", "политика GPU"),
    "config.restart_reason.web_speech_language": ("Web Speech recognition language", "язык Web Speech"),
    "config.save.applied_immediately": ("Saved and applied immediately.", "Сохранено и сразу применено."),
    "config.save.saved_locally": ("Saved locally.", "Сохранено локально."),
    "config.save.restart_after_stop_start": ("after Stop/Start", "после Стоп/Старт"),
    "config.save.restart_on_next_start": ("on the next Start", "при следующем Старт"),
    "config.save.applied_with_restart": (
        "Saved and applied immediately. {subject} changes will take effect {restartLabel}.",
        "Сохранено и сразу применено. Изменения для: {subject} вступят в силу {restartLabel}.",
    ),
    "config.save.local_with_restart": (
        "Saved locally. {subject} changes will take effect {restartLabel}.",
        "Сохранено локально. Изменения для: {subject} вступят в силу {restartLabel}.",
    ),
    "preview.source_line": ("Source subtitle preview", "Предпросмотр исходной строки"),
    "preview.live_partial": ("Live partial preview", "Предпросмотр live-partial"),
    "bootstrap.error.settings": ("Settings: {error}", "Настройки: {error}"),
    "bootstrap.error.version": ("Version: {error}", "Версия: {error}"),
    "bootstrap.error.health": ("Health: {error}", "Health: {error}"),
    "bootstrap.error.obs_url": ("OBS URL: {error}", "OBS URL: {error}"),
    "bootstrap.error.audio": ("Audio: {error}", "Аудио: {error}"),
    "bootstrap.incomplete": (
        "Dashboard bootstrap incomplete: {errors}",
        "Загрузка дашборда частично не удалась: {errors}",
    ),
    "bootstrap.load_dashboard_failed": (
        "Failed to load dashboard: {message}",
        "Не удалось загрузить дашборд: {message}",
    ),
    "log.audio.devices_found": (
        "[audio] detected {count} input device(s)",
        "[audio] найдено входных устройств: {count}",
    ),
    "log.audio.no_devices": ("[audio] no input devices found", "[audio] входные устройства не найдены"),
    "log.diagnostics.exported": ("[diagnostics] bundle exported", "[diagnostics] архив экспортирован"),
    "log.desktop.launcher_active": (
        "[desktop] desktop launcher active | startup={startup} | remote_role={remoteRole}",
        "[desktop] desktop launcher активен | startup={startup} | remote_role={remoteRole}",
    ),
    "runtime.start.preparing_experimental": (
        "Preparing Web Speech (Experimental)...",
        "Подготавливается Web Speech (Experimental)...",
    ),
    "runtime.start.preparing_web_speech": ("Preparing Web Speech...", "Подготавливается Web Speech..."),
    "runtime.start.preparing_asr": ("Preparing ASR runtime...", "Подготавливается ASR runtime..."),
    "runtime.save_button.saving": ("Saving...", "Сохранение..."),
    "asr.device.default_suffix": (" (default)", " (по умолчанию)"),
    "asr.device.meta": (
        "channels: {channels}, rate: {rate} Hz",
        "каналы: {channels}, частота: {rate} Гц",
    ),
    "asr.device.not_selected": ("No device selected.", "Устройство не выбрано."),
    "asr.transcript.waiting_partial": ("Waiting for speech...", "Ожидание речи..."),
    "asr.transcript.no_finals": ("No final transcript yet.", "Пока нет завершённого текста."),
    "asr.worker_browser_next_open_log": (
        "[asr] Web Speech worker will use the selected browser on next open (desktop)",
        "[asr] окно Web Speech: при следующем открытии worker будет использован выбранный браузер (desktop)",
    ),
    "worker.open_external_failed_log": (
        "[browser-asr] failed to open external browser worker",
        "[browser-asr] не удалось открыть внешний browser worker",
    ),
    "worker.settings.default_status": (
        "This window prioritizes its own localStorage settings and mirrors them to backend config when possible.",
        "Настройки этого окна сначала берутся из localStorage worker-а, а затем при возможности синхронизируются в backend config.",
    ),
    "worker.settings.saving": ("Saving settings...", "Сохранение настроек..."),
    "worker.settings.saved_backend": (
        "Saved locally and mirrored to backend at {time}",
        "Сохранено локально и синхронизировано с backend в {time}",
    ),
    "worker.settings.saved_local_backend_failed": (
        "Saved locally; backend sync failed: {message}",
        "Сохранено локально; backend sync failed: {message}",
    ),
    "worker.experimental.settings_local_only": (
        "Experimental worker settings are stored locally in the browser.",
        "Настройки experimental worker сохраняются локально в браузере.",
    ),
    "worker.settings.saved_local": ("Saved locally at {time}", "Сохранено локально в {time}"),
    "worker.visibility.hidden_warning": (
        "The Web Speech window is currently hidden or minimized. In this state, recognition can stall, end via onend, or stop producing partial/final results.",
        "Окно Web Speech сейчас скрыто или свернуто. В таком состоянии распознавание может подвисать, завершаться через onend или переставать выдавать partial/final результаты.",
    ),
    "worker.counters.language_line": (
        "{configured} -> source {source}",
        "{configured} -> источник {source}",
    ),
    "worker.recognition.status.idle": ("idle", "ожидание"),
    "worker.recognition.status.ready": ("ready", "готово"),
    "worker.recognition.status.listening": ("listening", "слушает"),
    "worker.recognition.status.capturing_audio": ("capturing-audio", "идёт захват аудио"),
    "worker.recognition.status.forced_finalized": ("forced-finalized", "принудительно завершено"),
    "worker.recognition.status.waiting_websocket": ("waiting-for-websocket", "ожидание websocket"),
    "worker.recognition.status.socket_reconnecting": ("socket-reconnecting", "переподключение websocket"),
    "worker.recognition.status.socket_error": ("socket-error", "ошибка websocket"),
    "worker.recognition.status.restarting": ("restarting", "перезапуск"),
    "worker.recognition.status.stopped": ("stopped", "остановлено"),
    "worker.recognition.status.stopping": ("stopping", "остановка"),
    "worker.recognition.status.interim": ("interim", "получен partial"),
    "worker.recognition.status.final": ("final", "получен final"),
    "worker.recognition.status.unsupported_browser": ("unsupported-browser", "браузер не поддерживается"),
    "browser_asr.mic_error_status": ("mic-error: {message}", "ошибка микрофона: {message}"),
    "browser_asr.error.no_audio_track": (
        "The browser did not return an audio track.",
        "Браузер не вернул audio track.",
    ),
    "browser_asr.error.wrong_track_kind": (
        "Expected an audio track, got: {kind}",
        "Ожидался audio track, получено: {kind}",
    ),
    "browser_asr.error.track_not_live": (
        "Audio track is not live: {state}",
        "Audio track не live: {state}",
    ),
    "browser_asr.error.open_mic_track": (
        "Could not open microphone audio track.",
        "Не удалось открыть микрофонный audio track.",
    ),
    "browser_asr.error.track_recovery_failed": ("Audio track recovery failed.", "Audio track recovery failed."),
    "browser_asr.error.fallback_default_start": (
        "Could not fall back to the default recognition.start().",
        "Не удалось переключиться на обычный recognition.start().",
    ),
    "browser_asr.error.experimental_start_failed": (
        "Could not start experimental Web Speech recognition.",
        "Не удалось запустить экспериментальное браузерное распознавание.",
    ),
    "browser_asr.network.status_unreachable": (
        "recognition cloud unreachable",
        "сеть недоступна для Web Speech",
    ),
    "browser_asr.network.hint": (
        "Web Speech network error: recognition service unreachable (VPN, firewall, DNS, proxy, blockers). Check connectivity; changing the browser microphone usually does not fix this.",
        "Web Speech: ошибка network — облако распознавания недоступно (VPN, фаервол, DNS, прокси, блокировщики). Проверьте интернет; смена микрофона в браузере это обычно не лечит.",
    ),
    "browser_asr.network.preflight_failed_log": (
        "Web Speech: network preflight failed — recognition cloud unreachable. Check VPN/firewall/DNS/proxy and press Start again.",
        "Web Speech: сетевой preflight provalil — облако распознавания недоступно. Проверьте VPN/firewall/DNS/прокси и нажмите Start заново.",
    ),
    "browser_asr.error.phrases_retry": (
        "Web Speech: phrases-not-supported — retrying without on-device phrase hints.",
        "Web Speech: phrases-not-supported — повтор без on-device phrase hints.",
    ),
    "browser_asr.error.language_retry": (
        "Web Speech: language-not-supported — one retry after clearing on-device hints.",
        "Web Speech: language-not-supported — одна попытка повтора после сброса on-device подсказок.",
    ),
    "browser_asr.error.terminal_status": ("error: {errorKind}", "ошибка: {errorKind}"),
    "overlay.preview.config_not_loaded": (
        "Subtitle style preview is unavailable until config loads.",
        "Предпросмотр стиля субтитров появится после загрузки config.",
    ),
    "overlay.preview.renderer_unavailable": (
        "SubtitleStyleRenderer unavailable.",
        "SubtitleStyleRenderer недоступен.",
    ),
    "overlay.preview.no_visible_lines": (
        "No visible subtitle lines for the current settings yet.",
        "По текущим настройкам сейчас нет видимых строк субтитров.",
    ),
    "overlay.preview.live_block": (
        "Live subtitle block{suffix}.",
        "Живой блок субтитров{suffix}.",
    ),
    "overlay.preview.live_partial": ("Live partial preview.", "Предпросмотр live-partial."),
    "overlay.preset_hint.single": (
        "Single: all visible subtitle items are rendered inside one physical row in the saved order.",
        "Одна строка: все видимые элементы выводятся в одном физическом ряду слева направо по сохранённому порядку.",
    ),
    "overlay.preset_hint.dual_line": (
        "Dual-line: the first visible item uses the top row, and the remaining visible items share the second row.",
        "Две строки: первый видимый элемент идёт в верхний ряд, остальные делят нижний ряд.",
    ),
    "overlay.preset_hint.stacked": (
        "Stacked: each visible subtitle item gets its own row.",
        "Стопка: каждый видимый элемент получает собственный ряд.",
    ),
    "style.ui_theme.custom": ("Custom", "Пользовательский"),
    "style.ui_theme.ocean": ("Ocean", "Океан"),
    "style.ui_theme.neon": ("Neon", "Неон"),
    "style.ui_theme.sunset": ("Sunset", "Закат"),
    "style.ui_theme.paper": ("Paper", "Бумага"),
    "style.preset.default_description": (
        "Choose a preset and tweak it locally.",
        "Выберите пресет и подстройте его локально.",
    ),
    "style.preset.editing_custom": (
        'Editing custom preset "{name}".',
        'Редактируется пользовательский пресет "{name}".',
    ),
    "style.preset.editing_builtin": (
        'Editing built-in preset "{name}".',
        'Редактируется встроенный пресет "{name}".',
    ),
    "style.font_catalog.counts": (
        "Project-local fonts: {projectCount}. System fonts: {systemCount}.",
        "Шрифтов проекта: {projectCount}. Системных шрифтов: {systemCount}.",
    ),
    "style.slot.enabled_hint": (
        "Selected slot: {slotLabel}. Empty values inherit from base.",
        'Выбран слот: {slotLabel}. Пустое значение означает "наследовать базовый стиль".',
    ),
    "style.slot.disabled_hint": (
        "Selected slot: {slotLabel}. Enable Override to reveal slot controls.",
        'Выбран слот: {slotLabel}. Включите "Переопределить", чтобы показать настройки слота.',
    ),
    "style.slot.pick_preset_placeholder": ("— pick preset —", "— выбрать пресет —"),
    "translation.models.loaded_count": ("Loaded {count} models.", "Моделей загружено: {count}."),
    "translation.models.loading_recommended": (
        "Loading recommended list...",
        "Загрузка рекомендуемого списка...",
    ),
    "translation.models.list_loaded": ("Loaded {count} models.", "Список загружен: {count} моделей."),
    "translation.models.error": ("Error: {message}", "Ошибка: {message}"),
    "translation.ws.provider": ("Provider: {label}", "Провайдер: {label}"),
    "translation.ws.group": ("Group: {group}", "Группа: {group}"),
    "translation.ws.local_provider": ("Local provider", "Локальный провайдер"),
    "translation.ws.experimental": ("Experimental", "Экспериментально"),
    "translation.ws.default_prompt": ("Default prompt", "Prompt по умолчанию"),
    "source_text_replacement.pair_limit_log": (
        "[source-text-replacement] at most {max} custom pairs",
        "[source-text-replacement] не более {max} своих пар",
    ),
    "obs.cc.status.disabled": (
        "OBS Closed Captions are disabled. The browser overlay remains unchanged.",
        "OBS Closed Captions выключены. На browser overlay это не влияет.",
    ),
    "obs.cc.status.connected": (
        "Connected to OBS websocket, mode: {mode}.",
        "OBS websocket подключён, режим: {mode}.",
    ),
    "obs.cc.status.error": (
        "OBS captions are enabled but not connected: {error}",
        "OBS captions включены, но не подключены: {error}",
    ),
    "obs.cc.status.waiting": (
        "OBS captions are enabled and waiting for the OBS websocket connection.",
        "OBS captions включены и ждут подключение к OBS websocket.",
    ),
    "help.load_failed": ("Failed to load help content.", "Не удалось загрузить справку."),
    "diagnostics.local_parakeet.line": (
        "Local Parakeet (saved): preset {preset}, incremental decode {incremental}, partial emit {emitMode}, min new words {minWords}. Engine streaming: {engine}.",
        "Local Parakeet (saved): preset {preset}, incremental decode {incremental}, partial emit {emitMode}, min new words {minWords}. Engine streaming: {engine}.",
    ),
}
# fmt: on


def main() -> None:
    en = {k: v[0] for k, v in PAIRS.items()}
    ru = {k: v[1] for k, v in PAIRS.items()}
    body = (
        "(function () {\n"
        "  window.__SST_I18N_DYNAMIC = {\n"
        f"    en: {json.dumps(en, ensure_ascii=False, indent=2)},\n"
        f"    ru: {json.dumps(ru, ensure_ascii=False, indent=2)}\n"
        "  };\n"
        "})();\n"
    )
    OUT.write_text(body, encoding="utf-8")
    print(f"wrote {OUT} ({len(PAIRS)} keys)")


if __name__ == "__main__":
    main()
