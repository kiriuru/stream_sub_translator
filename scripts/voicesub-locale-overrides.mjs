/** VoiceSub-only locale overrides merged after SST locale exports. */

export const voicesubNewKeysEn = {
  "save.status.default": "Settings are written to disk when you press Save.",
  "help.recognition.body":
    "Web Speech opens a separate browser worker window and streams recognition results back to this app.",
  "help.recognition.local":
    "VoiceSub uses Web Speech in a dedicated worker window for browser-based recognition.",
  "help.quick_start.5":
    "Press Start. Use Stop/Start after changing the Web Speech recognition language.",
  "overview.recognition.mode.local": "Web Speech",
  "overview.recognition.provider.parakeet": "Web Speech",
  "overview.recognition.provider.parakeet_low_latency": "Web Speech",
  "overview.recognition.hint.browser_quick_start_locked":
    "This session uses Web Speech. Change recognition settings in the overview cards, then Stop/Start if needed.",
  "diagnostics.local_parakeet.line": "",
  "runtime.local_realtime.line": "",
  "tuning.preset.label": "Latency preset",
  "tuning.apply.full_note":
    "After changing tuning values: click Save, then Stop/Start so recognition picks up the new settings.",
  "tools.advanced.latency_preset": "Latency preset",
  "tools.advanced.latency_preset.help":
    "Applies a ready-made bundle of timing settings (Ultra low latency, Balanced, Quality). Choose Balanced unless you have a specific reason to chase speed or accuracy.",
  "tools.advanced.streaming_decode": "Incremental streaming decode",
  "tools.advanced.streaming_decode.help":
    "When enabled, recognition decodes only new audio since the last step. When disabled, each partial update re-runs on the entire phrase, which is heavier on long utterances.",
  "tools.advanced.note.local":
    "These settings stay local. Save config or profile after changes; use Stop/Start to compare behavior safely.",
  "tools.tts.eyebrow": "Speech output",
  "tools.tts.title": "TTS module",
  "tools.tts.description":
    "Opens a separate window for subtitle speech synthesis and optional Twitch chat TTS.",
  "tools.tts.open": "Open TTS module",
  "tools.tts.opened": "TTS module opened",
  "tools.runtime.full_logging": "Enable full diagnostic logging (restart required)",
  "tools.runtime.full_logging.hint":
    "Compact logs are always written to logs/. Full logging adds verbose runtime events and JSONL traces (api, pipeline, ui, startup). Restart the app after saving.",
  "tools.runtime.dispatcher.reason": "Last dispatcher reason",
  "tools.runtime.dispatcher.stale_dropped": "stale dropped",
  "tools.runtime.dispatcher.provider_skipped": "provider skipped",
  "tools.runtime.dispatcher.timeout": "last timeout",
  "tools.runtime.dispatcher.last_slot": "last slot/target",
  "config.restart_reason.full_logging": "full diagnostic logging",
  "subtitles.keep_completed_during_partial":
    "Keep completed translations visible during an active source partial",
  "subtitles.keep_completed_during_partial.note":
    "When the source line is still growing as a partial, finished translation lines stay on screen instead of clearing early.",
  "translation.latest.show": "Show translated results",
  "translation.latest.hidden":
    "Translated results are hidden. Turn the toggle on to monitor live output.",
  "worker.advanced.title": "Advanced",
  "translation.provider_settings.selector": "Provider to edit",
  "translation.provider_group.stable_recommended": "Stable / Recommended",
  "translation.provider_group.experimental_emergency": "Experimental / Emergency",
  "translation.provider_group.classic_mt": "Classic MT",
  "translation.provider_group.flexible_llm": "Flexible LLM",
  "translation.provider_group.local_llm": "Local LLM",
  "style.preset.custom_description": "User-created local subtitle style.",
  "style.preset.desc.clean_default":
    "Neutral baseline: Inter on a transparent background with a minimal black outline.",
  "style.preset.desc.streamer_bold":
    "Loud display look: Oswald with a cyan fill and a hot-magenta glow for live gameplay.",
  "style.preset.desc.dual_tone":
    "Lato body with distinct fill colors per slot so source and each translation read at a glance.",
  "style.preset.desc.compact_overlay":
    "Source Sans 3 inside a tight semi-opaque black bar — small footprint, maximum legibility.",
  "style.preset.desc.soft_shadow":
    "Comfortaa with a wide diffused shadow and zero outline — feels airy, no edge crunch.",
  "style.preset.desc.anime_stream":
    "Mochiy Pop One for Latin/Japanese + Comfortaa Bold for Cyrillic — classic anime fansub caption.",
  "style.preset.desc.accessibility_high_contrast":
    "Pure white Montserrat Bold on a solid opaque black plate — WCAG AAA contrast in any environment.",
  "style.preset.desc.dark_cinema":
    "Playfair Display ivory on a solid warm sepia plate — letterboxed art-house aesthetic.",
  "style.preset.desc.meeting_soft":
    "Roboto Regular in light grey with no stroke and no plate — minimal, talking-head friendly.",
  "style.preset.desc.retro_terminal":
    "VT323 amber phosphor on a dark CRT panel — DEC VT320 / Apple II vibe with PT Mono for Cyrillic.",
  "style.preset.desc.fallout_pipboy":
    "Share Tech Mono in Pip-Boy phosphor green with a strong scanline glow.",
  "style.preset.desc.comic_burst":
    "Bangers in comic-yellow with a chunky black outline and a hot-red shadow — Marvel SFX panel energy.",
  "style.preset.desc.cyberpunk_neon":
    "Orbitron Black in hot magenta with a cyan halo glow on a deep navy plate.",
  "style.preset.desc.noir_typewriter":
    "Special Elite typewriter on a deep ink plate — 1940s detective / typewritten dossier mood.",
  "style.preset.desc.vlog_pastel":
    "Poppins on a warm pastel pill — cozy lifestyle / vlog look, plays nicely with soft backgrounds.",
  "updates.banner.message": "VoiceSub {latest} is available — you are on {current}.",
  "updates.banner.close": "Close",
  "updates.banner.download": "Download",
};

const voicesubExtrasLocalized = {
  ru: {
    "save.status.default": "Настройки записываются на диск при нажатии «Сохранить».",
    "help.recognition.body":
      "Web Speech открывает отдельное окно browser worker и отправляет результаты распознавания обратно в приложение.",
    "help.recognition.local":
      "VoiceSub использует Web Speech в отдельном окне worker для браузерного распознавания.",
    "help.quick_start.5":
      "Нажмите Старт. После смены языка Web Speech используйте Стоп/Старт.",
    "overview.recognition.mode.local": "Web Speech",
    "overview.recognition.provider.parakeet": "Web Speech",
    "overview.recognition.provider.parakeet_low_latency": "Web Speech",
    "overview.recognition.hint.browser_quick_start_locked":
      "Эта сессия использует Web Speech. Меняйте настройки распознавания в обзорных карточках, при необходимости — Стоп/Старт.",
    "diagnostics.local_parakeet.line": "",
    "runtime.local_realtime.line": "",
    "tuning.preset.label": "Пресет задержки",
    "tuning.apply.full_note":
      "После изменения параметров тюнинга: нажми Сохранить, затем Стоп/Старт, чтобы распознавание подхватило новые значения.",
    "tools.advanced.latency_preset": "Пресет задержки",
    "tools.advanced.latency_preset.help":
      "Применяет готовый набор таймингов (Минимальная задержка, Баланс, Качество). Обычно выбирай «Баланс», если нет особой причины гнаться за скоростью или качеством.",
    "tools.advanced.streaming_decode": "Инкрементальный streaming decode",
    "tools.advanced.streaming_decode.help":
      "Когда включено, обрабатывается только новая часть аудио с момента прошлого шага. Когда выключено, при каждом partial модель заново распознаёт всю фразу — это тяжелее на длинных репликах.",
    "tools.advanced.note.local":
      "Эти настройки остаются локальными. После изменения сохрани config или профиль; для проверки сделай Стоп/Старт.",
    "document.title.dashboard": "VoiceSub",
    "header.title": "VoiceSub",
    "updates.banner.message": "Доступна VoiceSub {latest} — у вас {current}.",
    "updates.banner.close": "Закрыть",
    "updates.banner.download": "Скачать",
    "save.status.saved": "Настройки сохранены.",
    "obs.overlay.instructions":
      "Добавьте этот URL как OBS Browser Source. Обновите URL при смене bind-адреса VoiceSub.",
    "subtitles.display_order": "Порядок отображения (id слотов через запятую)",
    "style.font_size.source": "Размер шрифта исходника (px)",
    "style.font_size.translation": "Размер шрифта перевода (px)",
    "tools.runtime.note":
      "Runtime-логи и диагностика записываются в папку пользовательских данных.",
    "overlay.preview.waiting": "Ожидание payload субтитров…",
    "translation.dispatcher.eyebrow": "Очередь и таймауты",
    "translation.dispatcher.title": "Диспетчер перевода",
    "translation.dispatcher.timeout_ms": "Таймаут запроса к провайдеру (мс)",
    "translation.dispatcher.queue_max_size": "Максимум задач в очереди",
    "translation.dispatcher.max_concurrent_jobs": "Максимум параллельных задач",
    "translation.dispatcher.note":
      "Увеличьте таймаут для медленных провайдеров. Больше параллелизма — больше расход API.",
    "translation.provider_limits.eyebrow": "Лимиты провайдеров",
    "translation.provider_limits.title": "Лимиты диспетчера по провайдерам",
    "translation.provider_limits.max_concurrent_targets": "Макс. параллельных целей",
    "translation.provider_limits.min_interval_ms": "Мин. интервал между вызовами (мс)",
    "translation.provider_limits.note":
      "Оставьте пустым для значений по умолчанию провайдера. Лимиты применяются по имени провайдера в диспетчере.",
    "translation.cache.max_entries": "Максимум записей в кэше",
    "translation.provider_group.stable_recommended": "Стабильно / рекомендуется",
    "translation.provider_group.experimental_emergency": "Экспериментально / запасной вариант",
    "translation.provider_group.classic_mt": "Классический MT",
    "translation.provider_group.flexible_llm": "Гибкая LLM",
    "translation.provider_group.local_llm": "Локальная LLM",
    "tuning.source_lang": "Подсказка исходного языка (перевод)",
    "tuning.source_lang.note":
      "Подсказка для провайдеров перевода. Авто — определение из распознавания, или выберите фиксированный код языка.",
    "worker.force_finalization_timeout_ms": "Таймаут простоя перед принудительным final (мс)",
    "worker.force_finalization_timeout_ms.note":
      "Сколько ждать без обновлений partial перед отправкой текущего текста как final.",
    "worker.advanced.title": "Дополнительно",
    "translation.latest.show": "Показывать переведённый результат",
    "translation.latest.hidden":
      "Блок скрыт. Включите переключатель, чтобы видеть live-вывод перевода.",
    "tools.tts.eyebrow": "Озвучивание",
    "tools.tts.title": "Модуль TTS",
    "tools.tts.description":
      "Открывает отдельное окно для озвучивания субтитров и опционального TTS Twitch-чата.",
    "tools.tts.open": "Открыть модуль TTS",
    "tools.tts.opened": "Модуль TTS открыт",
    "tools.runtime.full_logging":
      "Включить полное диагностическое логирование (нужен перезапуск)",
    "tools.runtime.full_logging.hint":
      "Сокращённые логи всегда пишутся в logs/. Полное логирование добавляет подробные runtime-события и JSONL-трейсы (api, pipeline, ui, startup). После сохранения перезапустите приложение.",
    "tools.runtime.dispatcher.reason": "Последняя причина диспетчера",
    "tools.runtime.dispatcher.stale_dropped": "stale dropped",
    "tools.runtime.dispatcher.provider_skipped": "provider skipped",
    "tools.runtime.dispatcher.timeout": "последний timeout",
    "tools.runtime.dispatcher.last_slot": "последний slot/target",
    "config.restart_reason.full_logging": "полное диагностическое логирование",
    "subtitles.keep_completed_during_partial":
      "Сохранять завершённые переводы при активном partial исходника",
    "subtitles.keep_completed_during_partial.note":
      "Пока исходная строка ещё растёт как partial, завершённые строки перевода остаются на экране, а не исчезают раньше времени.",
    "translation.provider_settings.selector": "Редактируемый провайдер",
    "style.preset.custom_description": "Пользовательский локальный стиль субтитров.",
    "style.preset.desc.clean_default":
      "Нейтральная база: Inter на прозрачном фоне с минимальной чёрной обводкой.",
    "style.preset.desc.streamer_bold":
      "Яркий стрим-лук: Oswald с cyan-заливкой и hot-magenta glow для live-геймплея.",
    "style.preset.desc.dual_tone":
      "Lato с разными цветами заливки по слотам — исходник и переводы читаются с первого взгляда.",
    "style.preset.desc.compact_overlay":
      "Source Sans 3 в компактной полупрозрачной чёрной плашке — минимальный размер, максимальная читаемость.",
    "style.preset.desc.soft_shadow":
      "Comfortaa с широкой мягкой тенью без обводки — лёгкий, «воздушный» вид.",
    "style.preset.desc.anime_stream":
      "Mochiy Pop One для Latin/Japanese + Comfortaa Bold для кириллицы — классическая anime fansub-плашка.",
    "style.preset.desc.accessibility_high_contrast":
      "Белый Montserrat Bold на сплошной чёрной плашке — контраст WCAG AAA в любой среде.",
    "style.preset.desc.dark_cinema":
      "Playfair Display ivory на тёплой sepia-плашке — эстетика letterbox art-house.",
    "style.preset.desc.meeting_soft":
      "Roboto Regular светло-серым без обводки и плашки — минимализм для talking-head.",
    "style.preset.desc.retro_terminal":
      "VT323 amber phosphor на тёмной CRT-панели — DEC VT320 / Apple II с PT Mono для кириллицы.",
    "style.preset.desc.fallout_pipboy":
      "Share Tech Mono в phosphor green Pip-Boy со scanline glow.",
    "style.preset.desc.comic_burst":
      "Bangers comic-yellow с толстой чёрной обводкой и hot-red тенью — энергия Marvel SFX.",
    "style.preset.desc.cyberpunk_neon":
      "Orbitron Black hot-magenta с cyan halo на deep navy plate.",
    "style.preset.desc.noir_typewriter":
      "Special Elite на deep ink plate — детективное кино / typewritten dossier.",
    "style.preset.desc.vlog_pastel":
      "Poppins на warm pastel pill — уютный lifestyle / vlog look.",
  },
  ja: {
    "save.status.default": "「保存」を押すと設定がディスクに書き込まれます。",
    "help.recognition.body":
      "Web Speech は別の browser worker ウィンドウを開き、認識結果をこのアプリに送り返します。",
    "help.recognition.local":
      "VoiceSub は browser worker 内の Web Speech で認識します。",
    "help.quick_start.5":
      "開始を押します。Web Speech の認識言語を変更した後は停止してから再開してください。",
    "overview.recognition.mode.local": "Web Speech",
    "overview.recognition.provider.parakeet": "Web Speech",
    "overview.recognition.provider.parakeet_low_latency": "Web Speech",
    "overview.recognition.hint.browser_quick_start_locked":
      "このセッションは Web Speech を使用しています。概要カードで認識設定を変更し、必要なら停止/再開してください。",
    "diagnostics.local_parakeet.line": "",
    "runtime.local_realtime.line": "",
    "tuning.preset.label": "レイテンシープリセット",
    "tuning.apply.full_note":
      "チューニング値を変更した後: 保存を押し、認識が新しい設定を読み込むために停止してから再開してください。",
    "tools.advanced.latency_preset": "レイテンシープリセット",
    "tools.advanced.latency_preset.help":
      "タイミング設定プリセット（超低遅延、バランス、品質）を一括適用します。特別な理由がなければ「バランス」を選んでください。",
    "tools.advanced.streaming_decode": "インクリメンタル ストリーミング デコード",
    "tools.advanced.streaming_decode.help":
      "有効にすると前回以降の新しい音声だけを処理します。無効にすると partial ごとにフレーズ全体を再処理するため、長い発話では負荷が高くなります。",
    "document.title.dashboard": "VoiceSub",
    "header.title": "VoiceSub",
    "updates.banner.message": "VoiceSub {latest} が利用可能です（現在 {current}）。",
    "updates.banner.close": "閉じる",
    "updates.banner.download": "ダウンロード",
    "save.status.saved": "設定を保存しました。",
    "obs.overlay.instructions":
      "この URL を OBS Browser Source として追加してください。VoiceSub の bind アドレスが変わったら URL を更新してください。",
    "subtitles.display_order": "表示順（カンマ区切りのスロット ID）",
    "style.font_size.source": "原文フォントサイズ (px)",
    "style.font_size.translation": "翻訳フォントサイズ (px)",
    "tools.runtime.note":
      "ランタイムログと診断はユーザーデータフォルダに書き込まれます。",
    "overlay.preview.waiting": "字幕 payload を待機中…",
    "translation.dispatcher.eyebrow": "キューとタイムアウト",
    "translation.dispatcher.title": "翻訳ディスパッチャー",
    "translation.dispatcher.timeout_ms": "プロバイダーリクエストタイムアウト (ms)",
    "translation.dispatcher.queue_max_size": "キュー内ジョブの最大数",
    "translation.dispatcher.max_concurrent_jobs": "最大並列ジョブ数",
    "translation.dispatcher.note":
      "遅いプロバイダー向けにタイムアウトを増やしてください。並列度が高いほど API クォータを多く使います。",
    "translation.provider_limits.eyebrow": "プロバイダー制限",
    "translation.provider_limits.title": "プロバイダー別ディスパッチャー制限",
    "translation.provider_limits.max_concurrent_targets": "最大同時ターゲット数",
    "translation.provider_limits.min_interval_ms": "呼び出し間の最小間隔 (ms)",
    "translation.provider_limits.note":
      "空欄のままにするとプロバイダーのデフォルトを使用します。制限はディスパッチャー内のプロバイダー名ごとに適用されます。",
    "translation.cache.max_entries": "キャッシュエントリの最大数",
    "translation.provider_group.stable_recommended": "安定 / 推奨",
    "translation.provider_group.experimental_emergency": "実験的 / 予備",
    "translation.provider_group.classic_mt": "クラシック MT",
    "translation.provider_group.flexible_llm": "柔軟な LLM",
    "translation.provider_group.local_llm": "ローカル LLM",
    "tuning.source_lang": "原文言語ヒント（翻訳）",
    "tuning.source_lang.note":
      "翻訳プロバイダー向けのヒント。auto で認識から検出するか、固定言語コードを選びます。",
    "worker.advanced.title": "詳細設定",
    "translation.latest.show": "翻訳結果を表示",
    "translation.latest.hidden":
      "翻訳結果は非表示です。ライブ出力を監視するにはトグルをオンにしてください。",
    "worker.force_finalization_timeout_ms": "強制 final 前のアイドルタイムアウト (ms)",
    "worker.force_finalization_timeout_ms.note":
      "partial 更新がない状態でどれだけ待ってから、現在のライブテキストを final セグメントとして送るか。",
    "tools.tts.eyebrow": "音声出力",
    "tools.tts.title": "TTS モジュール",
    "tools.tts.description":
      "字幕の音声合成と Twitch チャット TTS 用の別ウィンドウを開きます。",
    "tools.tts.open": "TTS モジュールを開く",
    "tools.tts.opened": "TTS モジュールを開きました",
    "tools.runtime.full_logging": "フル診断ログを有効にする（再起動が必要）",
    "tools.runtime.full_logging.hint":
      "コンパクトログは常に logs/ に書き込まれます。フルログは詳細な runtime イベントと JSONL トレース（api、pipeline、ui、startup）を追加します。保存後にアプリを再起動してください。",
    "tools.runtime.dispatcher.reason": "ディスパッチャー最終理由",
    "tools.runtime.dispatcher.stale_dropped": "stale dropped",
    "tools.runtime.dispatcher.provider_skipped": "provider skipped",
    "tools.runtime.dispatcher.timeout": "最終 timeout",
    "tools.runtime.dispatcher.last_slot": "最終 slot/target",
    "config.restart_reason.full_logging": "フル診断ログ",
    "subtitles.keep_completed_during_partial":
      "原文 partial 中も完了した翻訳を表示したままにする",
    "subtitles.keep_completed_during_partial.note":
      "原文行が partial としてまだ伸びている間、完了した翻訳行は早く消えずに画面に残ります。",
    "translation.provider_settings.selector": "編集するプロバイダー",
    "style.preset.custom_description": "ユーザー作成のローカル字幕スタイル。",
    "style.preset.editing_custom": "カスタムプリセット「{name}」を編集しています。",
    "style.preset.editing_builtin": "組み込みプリセット「{name}」を編集しています。",
    "style.preset.desc.clean_default":
      "ニュートラルなベースライン: 透明背景の Inter と最小限の黒アウトライン。",
    "style.preset.desc.streamer_bold":
      "派手な配信向けルック: Oswald にシアン塗りと hot-magenta のグロー。",
    "style.preset.desc.dual_tone":
      "スロットごとに異なる塗り色の Lato — 原文と各翻訳が一目で区別できます。",
    "style.preset.desc.compact_overlay":
      "半透明の黒バー内 Source Sans 3 — 小さな footprint で最大の可読性。",
    "style.preset.desc.soft_shadow":
      "Comfortaa に広い拡散シャドウ、アウトラインなし — 軽やかでエッジが硬くない見た目。",
    "style.preset.desc.anime_stream":
      "Latin/Japanese 向け Mochiy Pop One + キリル向け Comfortaa Bold — 定番 anime fansub キャプション。",
    "style.preset.desc.accessibility_high_contrast":
      "不透明な黒板の上の白 Montserrat Bold — どんな環境でも WCAG AAA コントラスト。",
    "style.preset.desc.dark_cinema":
      "Playfair Display の ivory を warm sepia plate 上に — letterbox art-house 風。",
    "style.preset.desc.meeting_soft":
      "Roboto Regular を light grey、stroke/plate なし — talking-head 向けミニマル。",
    "style.preset.desc.retro_terminal":
      "VT323 amber phosphor on dark CRT panel — DEC VT320 / Apple II 風、キリルは PT Mono。",
    "style.preset.desc.fallout_pipboy":
      "Share Tech Mono を Pip-Boy phosphor green + scanline glow で。",
    "style.preset.desc.comic_burst":
      "Bangers comic-yellow、太い黒アウトライン、hot-red shadow — Marvel SFX パネル感。",
    "style.preset.desc.cyberpunk_neon":
      "Orbitron Black hot-magenta + cyan halo on deep navy plate。",
    "style.preset.desc.noir_typewriter":
      "Special Elite typewriter on deep ink plate — film noir dossier 風。",
    "style.preset.desc.vlog_pastel":
      "Poppins on warm pastel pill — cozy lifestyle / vlog look。",
  },
  ko: {
    "save.status.default": "저장을 누르면 설정이 디스크에 기록됩니다.",
    "help.recognition.body":
      "Web Speech는 별도 browser worker 창을 열고 인식 결과를 이 앱으로 다시 보냅니다.",
    "help.recognition.local":
      "VoiceSub는 browser worker의 Web Speech로 인식합니다.",
    "help.quick_start.5":
      "시작을 누르세요. Web Speech 인식 언어를 변경한 뒤에는 중지 후 다시 시작하세요.",
    "overview.recognition.mode.local": "Web Speech",
    "overview.recognition.provider.parakeet": "Web Speech",
    "overview.recognition.provider.parakeet_low_latency": "Web Speech",
    "overview.recognition.hint.browser_quick_start_locked":
      "이 세션은 Web Speech를 사용합니다. 개요 카드에서 인식 설정을 변경하고 필요하면 중지/시작하세요.",
    "diagnostics.local_parakeet.line": "",
    "runtime.local_realtime.line": "",
    "tuning.preset.label": "지연 시간 프리셋",
    "tuning.apply.full_note":
      "튜닝 값을 변경한 뒤: 저장을 누르고, 인식이 새 설정을 읽도록 중지 후 시작하세요.",
    "tools.advanced.latency_preset": "지연 시간 프리셋",
    "tools.advanced.latency_preset.help":
      "타이밍 프리셋(매우 낮은 지연, 균형, 품질)을 한 번에 적용합니다. 특별한 이유가 없으면 '균형'을 선택하세요.",
    "tools.advanced.streaming_decode": "증분 스트리밍 디코드",
    "tools.advanced.streaming_decode.help":
      "사용하면 마지막 단계 이후 새 오디오만 처리합니다. 끄면 partial마다 전체 구문을 다시 처리해 긴 발화에서 부하가 큽니다.",
    "tools.advanced.note.local":
      "이 설정은 로컬에 유지됩니다. 변경 후 config 또는 프로필을 저장하고, 비교하려면 중지/시작을 사용하세요.",
    "document.title.dashboard": "VoiceSub",
    "header.title": "VoiceSub",
    "updates.banner.message": "VoiceSub {latest}을(를) 사용할 수 있습니다(현재 {current}).",
    "updates.banner.close": "닫기",
    "updates.banner.download": "다운로드",
    "save.status.saved": "설정을 저장했습니다.",
    "obs.overlay.instructions":
      "이 URL을 OBS Browser Source로 추가하세요. VoiceSub bind 주소가 바뀌면 URL을 업데이트하세요.",
    "subtitles.display_order": "표시 순서(쉼표로 구분된 슬롯 ID)",
    "style.font_size.source": "원문 글꼴 크기 (px)",
    "style.font_size.translation": "번역 글꼴 크기 (px)",
    "tools.runtime.note":
      "런타임 로그와 진단 정보는 사용자 데이터 폴더에 기록됩니다.",
    "overlay.preview.waiting": "자막 payload 대기 중…",
    "translation.dispatcher.eyebrow": "큐 및 타임아웃",
    "translation.dispatcher.title": "번역 디스패처",
    "translation.dispatcher.timeout_ms": "프로바이더 요청 타임아웃 (ms)",
    "translation.dispatcher.queue_max_size": "최대 대기 작업 수",
    "translation.dispatcher.max_concurrent_jobs": "최대 병렬 작업 수",
    "translation.dispatcher.note":
      "느린 프로바이더에는 타임아웃을 늘리세요. 병렬도가 높을수록 API 할당량을 더 사용합니다.",
    "translation.provider_limits.eyebrow": "프로바이더 제한",
    "translation.provider_limits.title": "프로바이더별 디스패처 제한",
    "translation.provider_limits.max_concurrent_targets": "최대 동시 대상 수",
    "translation.provider_limits.min_interval_ms": "호출 간 최소 간격 (ms)",
    "translation.provider_limits.note":
      "비워 두면 프로바이더 기본값을 사용합니다. 제한은 디스패처의 프로바이더 이름별로 적용됩니다.",
    "translation.cache.max_entries": "최대 캐시 항목 수",
    "translation.provider_group.stable_recommended": "안정 / 권장",
    "translation.provider_group.experimental_emergency": "실험적 / 비상",
    "translation.provider_group.classic_mt": "클래식 MT",
    "translation.provider_group.flexible_llm": "유연한 LLM",
    "translation.provider_group.local_llm": "로컬 LLM",
    "tuning.source_lang": "원문 언어 힌트(번역)",
    "tuning.source_lang.note":
      "번역 프로바이더용 힌트입니다. auto는 인식에서 감지하고, 고정 언어 코드를 선택할 수도 있습니다.",
    "worker.advanced.title": "고급",
    "translation.latest.show": "번역 결과 표시",
    "translation.latest.hidden":
      "번역 결과가 숨겨져 있습니다. 라이브 출력을 보려면 토글을 켜세요.",
    "worker.force_finalization_timeout_ms": "강제 final 전 유휴 타임아웃 (ms)",
    "worker.force_finalization_timeout_ms.note":
      "partial 업데이트 없이 얼마나 기다린 뒤 현재 라이브 텍스트를 final 세그먼트로 보낼지.",
    "tools.tts.eyebrow": "음성 출력",
    "tools.tts.title": "TTS 모듈",
    "tools.tts.description":
      "자막 음성 합성과 Twitch 채팅 TTS용 별도 창을 엽니다.",
    "tools.tts.open": "TTS 모듈 열기",
    "tools.tts.opened": "TTS 모듈을 열었습니다",
    "tools.runtime.full_logging": "전체 진단 로깅 사용(재시작 필요)",
    "tools.runtime.full_logging.hint":
      "컴팩트 로그는 항상 logs/에 기록됩니다. 전체 로깅은 상세 runtime 이벤트와 JSONL 트레이스(api, pipeline, ui, startup)를 추가합니다. 저장 후 앱을 재시작하세요.",
    "tools.runtime.dispatcher.reason": "디스패처 마지막 사유",
    "tools.runtime.dispatcher.stale_dropped": "stale dropped",
    "tools.runtime.dispatcher.provider_skipped": "provider skipped",
    "tools.runtime.dispatcher.timeout": "마지막 timeout",
    "tools.runtime.dispatcher.last_slot": "마지막 slot/target",
    "config.restart_reason.full_logging": "전체 진단 로깅",
    "subtitles.keep_completed_during_partial":
      "원문 partial 동안 완료된 번역을 계속 표시",
    "subtitles.keep_completed_during_partial.note":
      "원문 줄이 아직 partial로 늘어나는 동안 완료된 번역 줄은 일찍 사라지지 않고 화면에 남습니다.",
    "translation.provider_settings.selector": "편집할 프로바이더",
    "style.preset.custom_description": "사용자가 만든 로컬 자막 스타일.",
    "style.preset.editing_builtin": "내장 프리셋 \"{name}\" 편집 중.",
    "style.preset.desc.clean_default":
      "중립 기본값: 투명 배경의 Inter와 최소한의 검은 윤곽선.",
    "style.preset.desc.streamer_bold":
      "화려한 방송 룩: Oswald에 cyan 채우기와 hot-magenta glow.",
    "style.preset.desc.dual_tone":
      "슬롯별 다른 채우기 색의 Lato — 원문과 각 번역을 한눈에 구분.",
    "style.preset.desc.compact_overlay":
      "반투명 검은 바 안 Source Sans 3 — 작은 footprint, 최대 가독성.",
    "style.preset.desc.soft_shadow":
      "Comfortaa에 넓은 확산 그림자, 윤곽선 없음 — 가볍고 부드러운 느낌.",
    "style.preset.desc.anime_stream":
      "Latin/Japanese용 Mochiy Pop One + 키릴용 Comfortaa Bold — 클래식 anime fansub 캡션.",
    "style.preset.desc.accessibility_high_contrast":
      "불투명 검은 판 위 흰 Montserrat Bold — 어떤 환경에서도 WCAG AAA 대비.",
    "style.preset.desc.dark_cinema":
      "Playfair Display ivory on warm sepia plate — letterbox art-house aesthetic.",
    "style.preset.desc.meeting_soft":
      "Roboto Regular light grey, stroke/plate 없음 — talking-head friendly minimal.",
    "style.preset.desc.retro_terminal":
      "VT323 amber phosphor on dark CRT panel — DEC VT320 / Apple II vibe, PT Mono for Cyrillic.",
    "style.preset.desc.fallout_pipboy":
      "Share Tech Mono in Pip-Boy phosphor green with scanline glow.",
    "style.preset.desc.comic_burst":
      "Bangers comic-yellow with chunky black outline and hot-red shadow.",
    "style.preset.desc.cyberpunk_neon":
      "Orbitron Black hot-magenta with cyan halo on deep navy plate.",
    "style.preset.desc.noir_typewriter":
      "Special Elite typewriter on deep ink plate — film noir dossier mood.",
    "style.preset.desc.vlog_pastel":
      "Poppins on warm pastel pill — cozy lifestyle / vlog look.",
  },
  zh: {
    "save.status.default": "按“保存”后，设置会写入磁盘。",
    "help.recognition.body":
      "Web Speech 会打开单独的 browser worker 窗口，并将识别结果流式传回此应用。",
    "help.recognition.local":
      "VoiceSub 在 browser worker 中使用 Web Speech 进行识别。",
    "help.quick_start.5":
      "按开始。更改 Web Speech 识别语言后请停止再启动。",
    "overview.recognition.mode.local": "Web Speech",
    "overview.recognition.provider.parakeet": "Web Speech",
    "overview.recognition.provider.parakeet_low_latency": "Web Speech",
    "overview.recognition.hint.browser_quick_start_locked":
      "当前会话使用 Web Speech。在概览卡片中更改识别设置，必要时停止/启动。",
    "diagnostics.local_parakeet.line": "",
    "runtime.local_realtime.line": "",
    "tuning.preset.label": "延迟预设",
    "tuning.apply.full_note":
      "更改调优值后：点击保存，然后停止/启动以便识别加载新设置。",
    "tools.advanced.latency_preset": "延迟预设",
    "tools.advanced.latency_preset.help":
      "一次性应用时序预设（超低延迟、均衡、质量）。除非有特别理由，否则选“均衡”。",
    "tools.advanced.streaming_decode": "增量流式解码",
    "tools.advanced.streaming_decode.help":
      "开启后只处理自上次步骤以来的新音频。关闭后每次 partial 都会重新处理整句，长句时负载更大。",
    "tools.advanced.note.local":
      "这些设置保留在本地。更改后保存 config 或配置文件；用停止/启动安全对比行为。",
    "document.title.dashboard": "VoiceSub",
    "header.title": "VoiceSub",
    "updates.banner.message": "VoiceSub {latest} 已可用（当前 {current}）。",
    "updates.banner.close": "关闭",
    "updates.banner.download": "下载",
    "save.status.saved": "设置已保存。",
    "obs.overlay.instructions":
      "将此 URL 添加为 OBS Browser Source。VoiceSub bind 地址变更时请更新 URL。",
    "subtitles.display_order": "显示顺序（逗号分隔的 slot id）",
    "style.font_size.source": "原文 font size (px)",
    "style.font_size.translation": "翻译 font size (px)",
    "tools.runtime.note": "运行时日志和诊断写入用户数据文件夹。",
    "overlay.preview.waiting": "等待字幕 payload…",
    "translation.dispatcher.eyebrow": "队列与超时",
    "translation.dispatcher.title": "翻译调度器",
    "translation.dispatcher.timeout_ms": "Provider 请求超时 (ms)",
    "translation.dispatcher.queue_max_size": "最大排队任务数",
    "translation.dispatcher.max_concurrent_jobs": "最大并行任务数",
    "translation.dispatcher.note":
      "慢速 provider 请增大超时。更高并行度会消耗更多 API 配额。",
    "translation.provider_limits.eyebrow": "Provider 限制",
    "translation.provider_limits.title": "按 provider 的调度器限制",
    "translation.provider_limits.max_concurrent_targets": "最大并发目标数",
    "translation.provider_limits.min_interval_ms": "调用最小间隔 (ms)",
    "translation.provider_limits.note":
      "留空则使用 provider 默认值。限制按调度器中的 provider 名称应用。",
    "translation.cache.max_entries": "最大缓存条目数",
    "translation.provider_group.stable_recommended": "稳定 / 推荐",
    "translation.provider_group.experimental_emergency": "实验性 / 备用",
    "translation.provider_group.classic_mt": "经典 MT",
    "translation.provider_group.flexible_llm": "灵活 LLM",
    "translation.provider_group.local_llm": "本地 LLM",
    "tuning.source_lang": "原文语言提示（翻译）",
    "tuning.source_lang.note":
      "供翻译 provider 使用的提示。auto 从识别检测，或选择固定语言代码。",
    "worker.advanced.title": "高级",
    "translation.latest.show": "显示翻译结果",
    "translation.latest.hidden": "翻译结果已隐藏。打开开关以查看实时输出。",
    "worker.force_finalization_timeout_ms": "强制 final 前的空闲超时 (ms)",
    "worker.force_finalization_timeout_ms.note":
      "在没有 partial 更新的情况下，等待多久后将当前 live 文本作为 final 段发送。",
    "tools.tts.eyebrow": "语音输出",
    "tools.tts.title": "TTS 模块",
    "tools.tts.description": "打开用于字幕语音合成和 Twitch 聊天 TTS 的独立窗口。",
    "tools.tts.open": "打开 TTS 模块",
    "tools.tts.opened": "已打开 TTS 模块",
    "tools.runtime.full_logging": "启用完整诊断日志（需要重启）",
    "tools.runtime.full_logging.hint":
      "精简日志始终写入 logs/。完整日志会添加详细的 runtime 事件和 JSONL 跟踪（api、pipeline、ui、startup）。保存后请重启应用。",
    "tools.runtime.dispatcher.reason": "调度器最近原因",
    "tools.runtime.dispatcher.stale_dropped": "stale dropped",
    "tools.runtime.dispatcher.provider_skipped": "provider skipped",
    "tools.runtime.dispatcher.timeout": "最近超时",
    "tools.runtime.dispatcher.last_slot": "最近 slot/target",
    "config.restart_reason.full_logging": "完整诊断日志",
    "subtitles.keep_completed_during_partial": "原文 partial 期间保留已完成的翻译",
    "subtitles.keep_completed_during_partial.note":
      "当原文行仍以 partial 增长时，已完成的翻译行会留在屏幕上，而不会过早清除。",
    "translation.provider_settings.selector": "要编辑的 provider",
    "style.preset.custom_description": "用户创建的本地字幕样式。",
    "style.preset.desc.clean_default":
      "中性基线：透明背景上的 Inter 与最小黑色描边。",
    "style.preset.desc.streamer_bold":
      "醒目直播风格：Oswald 青色填充与 hot-magenta 光晕。",
    "style.preset.desc.dual_tone":
      "Lato 各 slot 不同填充色 — 原文与各翻译一目了然。",
    "style.preset.desc.compact_overlay":
      "半透明黑条内的 Source Sans 3 — 小 footprint，高可读性。",
    "style.preset.desc.soft_shadow":
      "Comfortaa 宽扩散阴影、无描边 — 轻盈无硬边。",
    "style.preset.desc.anime_stream":
      "Latin/Japanese 用 Mochiy Pop One + 西里尔用 Comfortaa Bold — 经典 anime fansub 样式。",
    "style.preset.desc.accessibility_high_contrast":
      "不透明白 Montserrat Bold 于黑底 — 任何环境 WCAG AAA 对比度。",
    "style.preset.desc.dark_cinema":
      "Playfair Display ivory on warm sepia plate — letterbox art-house aesthetic.",
    "style.preset.desc.meeting_soft":
      "Roboto Regular light grey, no stroke/plate — minimal talking-head friendly.",
    "style.preset.desc.retro_terminal":
      "VT323 amber phosphor on dark CRT panel — DEC VT320 / Apple II vibe.",
    "style.preset.desc.fallout_pipboy":
      "Share Tech Mono in Pip-Boy phosphor green with scanline glow.",
    "style.preset.desc.comic_burst":
      "Bangers comic-yellow with chunky black outline and hot-red shadow.",
    "style.preset.desc.cyberpunk_neon":
      "Orbitron Black hot-magenta with cyan halo on deep navy plate.",
    "style.preset.desc.noir_typewriter":
      "Special Elite typewriter on deep ink plate — film noir dossier mood.",
    "style.preset.desc.vlog_pastel":
      "Poppins on warm pastel pill — cozy lifestyle / vlog look.",
  },
};

export function voicesubLocaleOverrides(locale) {
  const extras = voicesubExtrasLocalized[locale] || {};
  if (locale === "en") {
    return { ...voicesubNewKeysEn };
  }
  return { ...voicesubNewKeysEn, ...extras };
}
