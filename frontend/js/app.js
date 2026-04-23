(async function () {
  const PROVIDERS = {
    google_translate_v2: {
      label: "Google Translate v2",
      group: "Stable / Recommended",
      hint: "Primary recommended provider. Requires a Google Translate v2 API key.",
      fields: ["api_key"],
      status: "Stable machine-translation provider.",
    },
    google_gas_url: {
      label: "Google GAS URL",
      group: "Experimental / Emergency",
      hint: "Experimental best-effort Google Apps Script bridge. Reliability depends on your script and deployment.",
      fields: ["gas_url"],
      status: "Experimental provider. Use only if you control the GAS endpoint.",
    },
    google_web: {
      label: "Google Web",
      group: "Experimental / Emergency",
      hint: "Experimental unofficial Google web endpoint. Best-effort only and may break anytime.",
      fields: [],
      status: "Experimental provider. Not recommended as the primary path.",
    },
    azure_translator: {
      label: "Azure Translator",
      group: "Stable / Recommended",
      hint: "Stable provider. Requires Azure Translator API key and usually a region.",
      fields: ["api_key", "endpoint", "region"],
      endpointPlaceholder: "https://api.cognitive.microsofttranslator.com",
      status: "Stable machine-translation provider.",
    },
    deepl: {
      label: "DeepL",
      group: "Classic MT",
      hint: "Requires a DeepL API key. API URL can stay at the default value.",
      fields: ["api_key", "api_url"],
      apiUrlPlaceholder: "https://api-free.deepl.com/v2/translate",
      status: "Classic MT provider.",
    },
    libretranslate: {
      label: "LibreTranslate",
      group: "Classic MT",
      hint: "Use your own LibreTranslate server or a managed endpoint. API key is optional depending on the server.",
      fields: ["api_key", "api_url"],
      apiUrlPlaceholder: "https://libretranslate.com/translate",
      status: "Classic MT provider. Reliability depends on the endpoint you choose.",
    },
    openai: {
      label: "OpenAI",
      group: "Flexible LLM",
      hint: "Flexible LLM subtitle translation. Requires API key, model, and uses the built-in subtitle prompt unless overridden.",
      fields: ["api_key", "base_url", "model", "custom_prompt"],
      baseUrlPlaceholder: "https://api.openai.com/v1",
      status: "Model-quality-dependent LLM provider.",
    },
    openrouter: {
      label: "OpenRouter",
      group: "Flexible LLM",
      hint: "OpenAI-compatible routing layer. Requires API key and model.",
      fields: ["api_key", "base_url", "model", "custom_prompt"],
      baseUrlPlaceholder: "https://openrouter.ai/api/v1",
      status: "Model-quality-dependent LLM provider.",
    },
    lm_studio: {
      label: "LM Studio",
      group: "Local LLM",
      hint: "Local OpenAI-compatible server. Quality depends on your locally loaded model.",
      fields: ["base_url", "model", "custom_prompt"],
      baseUrlPlaceholder: "http://127.0.0.1:1234/v1",
      status: "Local model-quality-dependent provider.",
    },
    ollama: {
      label: "Ollama",
      group: "Local LLM",
      hint: "Local OpenAI-compatible endpoint. Quality depends on your local model.",
      fields: ["base_url", "model", "custom_prompt"],
      baseUrlPlaceholder: "http://127.0.0.1:11434/v1",
      status: "Local model-quality-dependent provider.",
    },
    mymemory: {
      label: "MyMemory",
      group: "Experimental / Emergency",
      hint: "Experimental public web provider. Best-effort only. Do not treat as a stable production path.",
      fields: [],
      status: "Experimental public provider. Reliability is not guaranteed.",
    },
    public_libretranslate_mirror: {
      label: "Public LibreTranslate Mirror",
      group: "Experimental / Emergency",
      hint: "Experimental public mirror. Availability can change without notice.",
      fields: ["api_url"],
      apiUrlPlaceholder: "https://translate.fedilab.app/translate",
      status: "Experimental public provider. Reliability is not guaranteed.",
    },
    free_web_translate: {
      label: "Free Web Translate",
      group: "Experimental / Emergency",
      hint: "Experimental no-key web provider. Best-effort only.",
      fields: [],
      status: "Experimental public provider. Behavior may change without notice.",
    },
  };

  const LANGUAGES = [
    { code: "en", label: "English" },
    { code: "ja", label: "Japanese" },
    { code: "de", label: "German" },
    { code: "es", label: "Spanish" },
    { code: "fr", label: "French" },
    { code: "it", label: "Italian" },
    { code: "ko", label: "Korean" },
    { code: "pt", label: "Portuguese" },
    { code: "ru", label: "Russian" },
    { code: "zh-cn", label: "Chinese (Simplified)" },
  ];

  const BROWSER_RECOGNITION_LANGUAGES = [
    { code: "ru-RU", label: "Russian (ru-RU)" },
    { code: "en-US", label: "English (en-US)" },
    { code: "de-DE", label: "German (de-DE)" },
    { code: "es-ES", label: "Spanish (es-ES)" },
    { code: "fr-FR", label: "French (fr-FR)" },
    { code: "it-IT", label: "Italian (it-IT)" },
    { code: "ja-JP", label: "Japanese (ja-JP)" },
    { code: "ko-KR", label: "Korean (ko-KR)" },
    { code: "pt-BR", label: "Portuguese (pt-BR)" },
    { code: "uk-UA", label: "Ukrainian (uk-UA)" },
    { code: "zh-CN", label: "Chinese Simplified (zh-CN)" },
  ];

  const SIMPLE_TUNING_OPTIONS = {
    appearance: [
      { label: "Steadier", partial_emit_interval_ms: 560, min_speech_ms: 260 },
      { label: "Calm", partial_emit_interval_ms: 500, min_speech_ms: 220 },
      { label: "Balanced", partial_emit_interval_ms: 450, min_speech_ms: 180 },
      { label: "Quick", partial_emit_interval_ms: 360, min_speech_ms: 140 },
      { label: "Fast", partial_emit_interval_ms: 280, min_speech_ms: 100 },
    ],
    finish: [
      { label: "Wait Longer", silence_hold_ms: 260, pause_to_finalize_ms: 650 },
      { label: "Relaxed", silence_hold_ms: 220, pause_to_finalize_ms: 500 },
      { label: "Balanced", silence_hold_ms: 180, pause_to_finalize_ms: 350 },
      { label: "Quick", silence_hold_ms: 150, pause_to_finalize_ms: 300 },
      { label: "Fast", silence_hold_ms: 120, pause_to_finalize_ms: 260 },
    ],
    stability: [
      { label: "Live", partial_min_delta_chars: 4, partial_coalescing_ms: 80 },
      { label: "Responsive", partial_min_delta_chars: 8, partial_coalescing_ms: 120 },
      { label: "Balanced", partial_min_delta_chars: 12, partial_coalescing_ms: 160 },
      { label: "Steady", partial_min_delta_chars: 15, partial_coalescing_ms: 240 },
      { label: "Very Steady", partial_min_delta_chars: 18, partial_coalescing_ms: 320 },
    ],
  };

  const PROVIDER_GROUP_KEYS = {
    "Stable / Recommended": { en: "Stable / Recommended", ru: "Стабильно / рекомендуется" },
    "Experimental / Emergency": { en: "Experimental / Emergency", ru: "Экспериментально / запасной вариант" },
    "Classic MT": { en: "Classic MT", ru: "Классический MT" },
    "Flexible LLM": { en: "Flexible LLM", ru: "Гибкая LLM" },
    "Local LLM": { en: "Local LLM", ru: "Локальная LLM" },
  };

  const STYLE_PRESET_COPY = {
    clean_default: {
      label: { en: "Clean Default", ru: "Чистый стандарт" },
      description: {
        en: "Balanced white subtitles with readable outline and no extra effects.",
        ru: "Сбалансированные белые субтитры с читаемой обводкой и без лишних эффектов.",
      },
    },
    streamer_bold: {
      label: { en: "Streamer Bold", ru: "Стримовый акцент" },
      description: {
        en: "Larger, stronger subtitle look for busy gameplay scenes.",
        ru: "Более крупный и выразительный стиль субтитров для насыщенных игровых сцен.",
      },
    },
    dual_tone: {
      label: { en: "Dual Tone", ru: "Два тона" },
      description: {
        en: "Distinct source and translation colors while keeping one coherent layout.",
        ru: "Отдельные цвета для исходника и перевода при сохранении единой композиции.",
      },
    },
    compact_overlay: {
      label: { en: "Compact Overlay", ru: "Компактный overlay" },
      description: {
        en: "Tighter spacing for overlays with limited screen space.",
        ru: "Более плотная компоновка для overlay с ограниченным экранным пространством.",
      },
    },
    soft_shadow: {
      label: { en: "Soft Shadow", ru: "Мягкая тень" },
      description: {
        en: "Minimal stroke with softer shadow and a subtle pop effect.",
        ru: "Минимальная обводка, более мягкая тень и лёгкий эффект появления.",
      },
    },
    jp_stream_single: {
      label: { en: "JP Stream Single", ru: "JP Stream Single" },
      description: {
        en: "One-line focused Japanese-style subtitle direction with heavier outline and tighter spacing.",
        ru: "Однострочный японский стиль с более тяжёлой обводкой и плотной компоновкой.",
      },
    },
    jp_dual_caption: {
      label: { en: "JP Dual Caption", ru: "JP Dual Caption" },
      description: {
        en: "Two-line Japanese-inspired layout tuned for source + one translation or two translation lines.",
        ru: "Двухстрочная японская компоновка для исходника и одного перевода либо двух переводных строк.",
      },
    },
  };

  const PROVIDER_COPY = {
    google_translate_v2: {
      hint: {
        en: "Recommended main provider. Works with Google Translate v2 API key.",
        ru: "Рекомендуемый основной провайдер. Работает с API-ключом Google Translate v2.",
      },
      status: {
        en: "Stable machine-translation provider.",
        ru: "Стабильный провайдер машинного перевода.",
      },
    },
    google_gas_url: {
      hint: {
        en: "Google Apps Script bridge. Reliability depends on your own script and deployment.",
        ru: "Мост через Google Apps Script. Надёжность зависит от вашего скрипта и его публикации.",
      },
      status: {
        en: "Experimental provider. Use it only if you control that GAS endpoint.",
        ru: "Экспериментальный провайдер. Имеет смысл, только если вы сами контролируете этот GAS endpoint.",
      },
    },
    google_web: {
      hint: {
        en: "Unofficial Google web endpoint. Best-effort only and may stop working at any time.",
        ru: "Неофициальный веб-эндпоинт Google. Работает по best-effort и может перестать работать в любой момент.",
      },
      status: {
        en: "Experimental provider. Not recommended as the main path.",
        ru: "Экспериментальный провайдер. Не рекомендуется как основной вариант.",
      },
    },
    azure_translator: {
      hint: {
        en: "Stable provider. Usually needs API key, endpoint, and region.",
        ru: "Стабильный провайдер. Обычно требует API-ключ, endpoint и регион.",
      },
      status: {
        en: "Stable machine-translation provider.",
        ru: "Стабильный провайдер машинного перевода.",
      },
    },
    deepl: {
      hint: {
        en: "Needs a DeepL API key. The API URL usually can stay at the default value.",
        ru: "Нужен API-ключ DeepL. URL API обычно можно оставить по умолчанию.",
      },
      status: {
        en: "Classic MT provider.",
        ru: "Классический провайдер машинного перевода.",
      },
    },
    libretranslate: {
      hint: {
        en: "Use your own LibreTranslate server or a managed endpoint. API key depends on that server.",
        ru: "Можно использовать свой сервер LibreTranslate или внешний endpoint. Нужен ли API-ключ, зависит от выбранного сервера.",
      },
      status: {
        en: "Classic MT provider. Reliability depends on the endpoint you use.",
        ru: "Классический MT-провайдер. Надёжность зависит от выбранного endpoint.",
      },
    },
    openai: {
      hint: {
        en: "Flexible LLM translation. Needs API key and model, and can use a custom subtitle prompt.",
        ru: "Гибкий LLM-перевод. Нужны API-ключ и модель, при желании можно использовать свой subtitle prompt.",
      },
      status: {
        en: "LLM provider. Final quality depends on the chosen model.",
        ru: "LLM-провайдер. Качество зависит от выбранной модели.",
      },
    },
    openrouter: {
      hint: {
        en: "OpenAI-compatible routing layer. Needs API key and model.",
        ru: "OpenAI-совместимый маршрутизатор. Нужны API-ключ и модель.",
      },
      status: {
        en: "LLM provider. Final quality depends on the chosen model.",
        ru: "LLM-провайдер. Качество зависит от выбранной модели.",
      },
    },
    lm_studio: {
      hint: {
        en: "Local OpenAI-compatible server. Quality depends on the model loaded in LM Studio.",
        ru: "Локальный OpenAI-совместимый сервер. Качество зависит от модели, загруженной в LM Studio.",
      },
      status: {
        en: "Local provider. Quality depends on the local model.",
        ru: "Локальный провайдер. Качество зависит от локальной модели.",
      },
    },
    ollama: {
      hint: {
        en: "Local OpenAI-compatible endpoint. Quality depends on the local model in Ollama.",
        ru: "Локальный OpenAI-совместимый endpoint. Качество зависит от локальной модели в Ollama.",
      },
      status: {
        en: "Local provider. Quality depends on the local model.",
        ru: "Локальный провайдер. Качество зависит от локальной модели.",
      },
    },
    mymemory: {
      hint: {
        en: "Public web provider. Good only as a temporary emergency fallback.",
        ru: "Публичный веб-провайдер. Подходит только как временный запасной вариант.",
      },
      status: {
        en: "Experimental public provider. Reliability is not guaranteed.",
        ru: "Экспериментальный публичный провайдер. Надёжность не гарантируется.",
      },
    },
    public_libretranslate_mirror: {
      hint: {
        en: "Public mirror. Availability can change without notice.",
        ru: "Публичное зеркало. Доступность может измениться без предупреждения.",
      },
      status: {
        en: "Experimental public provider. Reliability is not guaranteed.",
        ru: "Экспериментальный публичный провайдер. Надёжность не гарантируется.",
      },
    },
    free_web_translate: {
      hint: {
        en: "No-key web provider. Best-effort only.",
        ru: "Веб-провайдер без ключа. Только best-effort.",
      },
      status: {
        en: "Experimental public provider. Behavior may change without notice.",
        ru: "Экспериментальный публичный провайдер. Поведение может измениться без предупреждения.",
      },
    },
  };

  const LANGUAGE_LABELS = {
    en: { en: "English", ru: "Английский" },
    ja: { en: "Japanese", ru: "Японский" },
    de: { en: "German", ru: "Немецкий" },
    es: { en: "Spanish", ru: "Испанский" },
    fr: { en: "French", ru: "Французский" },
    it: { en: "Italian", ru: "Итальянский" },
    ko: { en: "Korean", ru: "Корейский" },
    pt: { en: "Portuguese", ru: "Португальский" },
    ru: { en: "Russian", ru: "Русский" },
    "zh-cn": { en: "Chinese (Simplified)", ru: "Китайский (упрощённый)" },
  };

  const BROWSER_RECOGNITION_LABELS = {
    "ru-RU": { en: "Russian (ru-RU)", ru: "Русский (ru-RU)" },
    "en-US": { en: "English (en-US)", ru: "Английский (en-US)" },
    "de-DE": { en: "German (de-DE)", ru: "Немецкий (de-DE)" },
    "es-ES": { en: "Spanish (es-ES)", ru: "Испанский (es-ES)" },
    "fr-FR": { en: "French (fr-FR)", ru: "Французский (fr-FR)" },
    "it-IT": { en: "Italian (it-IT)", ru: "Итальянский (it-IT)" },
    "ja-JP": { en: "Japanese (ja-JP)", ru: "Японский (ja-JP)" },
    "ko-KR": { en: "Korean (ko-KR)", ru: "Корейский (ko-KR)" },
    "pt-BR": { en: "Portuguese (pt-BR)", ru: "Португальский (pt-BR)" },
    "uk-UA": { en: "Ukrainian (uk-UA)", ru: "Украинский (uk-UA)" },
    "zh-CN": { en: "Chinese Simplified (zh-CN)", ru: "Китайский упрощённый (zh-CN)" },
  };

  const SIMPLE_TUNING_LABELS = {
    appearance: {
      Steadier: { en: "Steadier", ru: "Спокойнее" },
      Calm: { en: "Calm", ru: "Мягко" },
      Balanced: { en: "Balanced", ru: "Баланс" },
      Quick: { en: "Quick", ru: "Быстро" },
      Fast: { en: "Fast", ru: "Очень быстро" },
    },
    finish: {
      "Wait Longer": { en: "Wait Longer", ru: "Подождать дольше" },
      Relaxed: { en: "Relaxed", ru: "Спокойно" },
      Balanced: { en: "Balanced", ru: "Баланс" },
      Quick: { en: "Quick", ru: "Быстро" },
      Fast: { en: "Fast", ru: "Очень быстро" },
    },
    stability: {
      Live: { en: "Live", ru: "Живее" },
      Responsive: { en: "Responsive", ru: "Отзывчиво" },
      Balanced: { en: "Balanced", ru: "Баланс" },
      Steady: { en: "Steady", ru: "Спокойно" },
      "Very Steady": { en: "Very Steady", ru: "Очень спокойно" },
    },
  };

  const startBtn = document.getElementById("start-btn");
  const stopBtn = document.getElementById("stop-btn");
  const configSaveBtn = document.getElementById("config-save-btn");
  const configExportBtn = document.getElementById("config-export-btn");
  const configImportInput = document.getElementById("config-import-input");
  const configImportBtn = document.getElementById("config-import-btn");
  const configJson = document.getElementById("config-json");
  const profilesSelect = document.getElementById("profiles-select");
  const profileLoadBtn = document.getElementById("profile-load-btn");
  const profileSaveBtn = document.getElementById("profile-save-btn");
  const profileDeleteBtn = document.getElementById("profile-delete-btn");
  const profileNameInput = document.getElementById("profile-name-input");
  const healthBadge = document.getElementById("health-badge");
  const runtimeBadge = document.getElementById("runtime-badge");
  const runtimeProgressCard = document.getElementById("runtime-progress-card");
  const runtimeProgressTitle = document.getElementById("runtime-progress-title");
  const runtimeProgressPercent = document.getElementById("runtime-progress-percent");
  const runtimeProgressText = document.getElementById("runtime-progress-text");
  const runtimeProgressFill = document.getElementById("runtime-progress-fill");
  const asrProviderBadge = document.getElementById("asr-provider-badge");
  const asrDeviceBadge = document.getElementById("asr-device-badge");
  const asrPartialsBadge = document.getElementById("asr-partials-badge");
  const asrModeBadge = document.getElementById("asr-mode-badge");
  const translationStatusBadge = document.getElementById("translation-status-badge");
  const obsCcBadge = document.getElementById("obs-cc-badge");
  const asrDiagnosticsText = document.getElementById("asr-diagnostics-text");
  const translationDiagnosticsText = document.getElementById("translation-diagnostics-text");
  const obsCcDiagnosticsText = document.getElementById("obs-cc-diagnostics-text");
  const latencyMetricsText = document.getElementById("latency-metrics-text");
  const overlayText = document.getElementById("overlay-url");
  const overlayLink = document.getElementById("overlay-link");
  const audioInputsList = document.getElementById("audio-inputs");
  const audioInputSelect = document.getElementById("audio-input-select");
  const audioInputMeta = document.getElementById("audio-input-meta");
  const recognitionModeSelect = document.getElementById("recognition-mode-select");
  const recognitionLanguageRow = document.getElementById("recognition-language-row");
  const recognitionLanguageSelect = document.getElementById("recognition-language-select");
  const recognitionModeHint = document.getElementById("recognition-mode-hint");
  const runtimeStatePills = document.querySelectorAll(".state-pill");
  const partialTranscript = document.getElementById("partial-transcript");
  const finalTranscript = document.getElementById("final-transcript");
  const globalSaveBtn = document.getElementById("global-save-btn");
  const uiLanguageSelect = document.getElementById("ui-language-select");
  const saveStatusText = document.getElementById("save-status-text");
  const translationResults = document.getElementById("translation-results");
  let browserAsrWindow = null;
  const translationEnabled = document.getElementById("translation-enabled");
  const translationProvider = document.getElementById("translation-provider");
  const translationApiKey = document.getElementById("translation-api-key");
  const translationApiKeyRow = document.getElementById("translation-api-key-row");
  const translationBaseUrl = document.getElementById("translation-base-url");
  const translationGasUrl = document.getElementById("translation-gas-url");
  const translationEndpoint = document.getElementById("translation-endpoint");
  const translationRegion = document.getElementById("translation-region");
  const translationRegionRow = document.getElementById("translation-region-row");
  const translationApiUrl = document.getElementById("translation-api-url");
  const translationModel = document.getElementById("translation-model");
  const translationCustomPrompt = document.getElementById("translation-custom-prompt");
  const translationProviderHint = document.getElementById("translation-provider-hint");
  const translationProviderStatus = document.getElementById("translation-provider-status");
  const translationBaseUrlRow = document.getElementById("translation-base-url-row");
  const translationGasUrlRow = document.getElementById("translation-gas-url-row");
  const translationEndpointRow = document.getElementById("translation-endpoint-row");
  const translationApiUrlRow = document.getElementById("translation-api-url-row");
  const translationModelRow = document.getElementById("translation-model-row");
  const translationPromptRow = document.getElementById("translation-prompt-row");
  const translationLanguageSelect = document.getElementById("translation-language-select");
  const translationLanguageOrder = document.getElementById("translation-language-order");
  const translationLangAddBtn = document.getElementById("translation-lang-add-btn");
  const translationLangRemoveBtn = document.getElementById("translation-lang-remove-btn");
  const translationLangUpBtn = document.getElementById("translation-lang-up-btn");
  const translationLangDownBtn = document.getElementById("translation-lang-down-btn");
  const subtitleShowSource = document.getElementById("subtitle-show-source");
  const subtitleShowTranslations = document.getElementById("subtitle-show-translations");
  const subtitleMaxTranslations = document.getElementById("subtitle-max-translations");
  const subtitleDisplayOrder = document.getElementById("subtitle-display-order");
  const subtitleOrderUpBtn = document.getElementById("subtitle-order-up-btn");
  const subtitleOrderDownBtn = document.getElementById("subtitle-order-down-btn");
  const overlayPresetSelect = document.getElementById("overlay-preset-select");
  const overlayPresetHint = document.getElementById("overlay-preset-hint");
  const overlayCompactToggle = document.getElementById("overlay-compact-toggle");
  const obsCcEnabled = document.getElementById("obs-cc-enabled");
  const obsCcHost = document.getElementById("obs-cc-host");
  const obsCcPort = document.getElementById("obs-cc-port");
  const obsCcPassword = document.getElementById("obs-cc-password");
  const obsCcOutputMode = document.getElementById("obs-cc-output-mode");
  const obsCcDebugEnabled = document.getElementById("obs-cc-debug-enabled");
  const obsCcDebugInputName = document.getElementById("obs-cc-debug-input-name");
  const obsCcDebugSendPartials = document.getElementById("obs-cc-debug-send-partials");
  const obsCcSendPartials = document.getElementById("obs-cc-send-partials");
  const obsCcPartialThrottle = document.getElementById("obs-cc-partial-throttle");
  const obsCcMinPartialDelta = document.getElementById("obs-cc-min-partial-delta");
  const obsCcFinalReplaceDelay = document.getElementById("obs-cc-final-replace-delay");
  const obsCcClearAfter = document.getElementById("obs-cc-clear-after");
  const obsCcAvoidDuplicates = document.getElementById("obs-cc-avoid-duplicates");
  const obsCcStatusText = document.getElementById("obs-cc-status-text");
  const subtitleOutputPreview = document.getElementById("subtitle-output-preview");
  const subtitleStylePreset = document.getElementById("subtitle-style-preset");
  const subtitleStylePresetDescription = document.getElementById("subtitle-style-preset-description");
  const subtitleStyleCustomName = document.getElementById("subtitle-style-custom-name");
  const subtitleStyleSaveCustomBtn = document.getElementById("subtitle-style-save-custom-btn");
  const subtitleStyleDeleteCustomBtn = document.getElementById("subtitle-style-delete-custom-btn");
  const subtitleStyleCustomStatus = document.getElementById("subtitle-style-custom-status");
  const projectFontsDir = document.getElementById("project-fonts-dir");
  const fontRefreshBtn = document.getElementById("font-refresh-btn");
  const fontSourceStatus = document.getElementById("font-source-status");
  const styleFontFamily = document.getElementById("style-font-family");
  const styleFontSize = document.getElementById("style-font-size");
  const styleFontWeight = document.getElementById("style-font-weight");
  const styleFillColor = document.getElementById("style-fill-color");
  const styleStrokeColor = document.getElementById("style-stroke-color");
  const styleStrokeWidth = document.getElementById("style-stroke-width");
  const styleShadowColor = document.getElementById("style-shadow-color");
  const styleShadowBlur = document.getElementById("style-shadow-blur");
  const styleShadowOffsetX = document.getElementById("style-shadow-offset-x");
  const styleShadowOffsetY = document.getElementById("style-shadow-offset-y");
  const styleBackgroundColor = document.getElementById("style-background-color");
  const styleBackgroundOpacity = document.getElementById("style-background-opacity");
  const styleBackgroundPaddingX = document.getElementById("style-background-padding-x");
  const styleBackgroundPaddingY = document.getElementById("style-background-padding-y");
  const styleBackgroundRadius = document.getElementById("style-background-radius");
  const styleLineSpacing = document.getElementById("style-line-spacing");
  const styleLetterSpacing = document.getElementById("style-letter-spacing");
  const styleTextAlign = document.getElementById("style-text-align");
  const styleLineGap = document.getElementById("style-line-gap");
  const styleEffect = document.getElementById("style-effect");
  const styleLineSlotTabs = document.getElementById("style-line-slot-tabs");
  const styleLineSlotEnabled = document.getElementById("style-line-slot-enabled");
  const styleLineSlotDescription = document.getElementById("style-line-slot-description");
  const styleLineSlotFields = document.getElementById("style-line-slot-fields");
  const styleLineSlotDetails = document.getElementById("style-line-slot-details");
  const styleLineSlotFontFamily = document.getElementById("style-line-slot-font-family");
  const styleLineSlotFontSize = document.getElementById("style-line-slot-font-size");
  const styleLineSlotFontWeight = document.getElementById("style-line-slot-font-weight");
  const styleLineSlotFillColor = document.getElementById("style-line-slot-fill-color");
  const styleLineSlotStrokeColor = document.getElementById("style-line-slot-stroke-color");
  const styleLineSlotStrokeWidth = document.getElementById("style-line-slot-stroke-width");
  const styleLineSlotShadowColor = document.getElementById("style-line-slot-shadow-color");
  const styleLineSlotShadowBlur = document.getElementById("style-line-slot-shadow-blur");
  const styleLineSlotShadowOffsetX = document.getElementById("style-line-slot-shadow-offset-x");
  const styleLineSlotShadowOffsetY = document.getElementById("style-line-slot-shadow-offset-y");
  const styleLineSlotBackgroundColor = document.getElementById("style-line-slot-background-color");
  const styleLineSlotBackgroundOpacity = document.getElementById("style-line-slot-background-opacity");
  const styleLineSlotBackgroundPaddingX = document.getElementById("style-line-slot-background-padding-x");
  const styleLineSlotBackgroundPaddingY = document.getElementById("style-line-slot-background-padding-y");
  const styleLineSlotBackgroundRadius = document.getElementById("style-line-slot-background-radius");
  const styleLineSlotLineSpacing = document.getElementById("style-line-slot-line-spacing");
  const styleLineSlotLetterSpacing = document.getElementById("style-line-slot-letter-spacing");
  const styleLineSlotTextAlign = document.getElementById("style-line-slot-text-align");
  const styleLineSlotEffect = document.getElementById("style-line-slot-effect");
  const rtVadMode = document.getElementById("rt-vad-mode");
  const rtPartialEmitInterval = document.getElementById("rt-partial-emit-interval");
  const rtMinSpeech = document.getElementById("rt-min-speech");
  const rtMaxSegment = document.getElementById("rt-max-segment");
  const rtSilenceHold = document.getElementById("rt-silence-hold");
  const rtFinalizationHold = document.getElementById("rt-finalization-hold");
  const rtChunkWindow = document.getElementById("rt-chunk-window");
  const rtChunkOverlap = document.getElementById("rt-chunk-overlap");
  const rtEnergyGateEnabled = document.getElementById("rt-energy-gate-enabled");
  const rtMinRms = document.getElementById("rt-min-rms");
  const rtMinVoicedRatio = document.getElementById("rt-min-voiced-ratio");
  const rtFirstPartialMinSpeech = document.getElementById("rt-first-partial-min-speech");
  const rtPartialMinDelta = document.getElementById("rt-partial-min-delta");
  const rtPartialCoalescing = document.getElementById("rt-partial-coalescing");
  const subtitleCompletedSourceTtl = document.getElementById("subtitle-completed-source-ttl");
  const subtitleCompletedTranslationTtl = document.getElementById("subtitle-completed-translation-ttl");
  const subtitleSyncSourceTranslationExpiry = document.getElementById("subtitle-sync-source-translation-expiry");
  const subtitleAllowEarlyReplace = document.getElementById("subtitle-allow-early-replace");
  const simpleAppearanceSpeed = document.getElementById("simple-appearance-speed");
  const simpleAppearanceLabel = document.getElementById("simple-appearance-label");
  const simpleFinishSpeed = document.getElementById("simple-finish-speed");
  const simpleFinishLabel = document.getElementById("simple-finish-label");
  const simpleStability = document.getElementById("simple-stability");
  const simpleStabilityLabel = document.getElementById("simple-stability-label");
  const asrRnnoiseEnabled = document.getElementById("asr-rnnoise-enabled");
  const asrRnnoiseStrength = document.getElementById("asr-rnnoise-strength");
  const asrRnnoiseStrengthLabel = document.getElementById("asr-rnnoise-strength-label");
  const logBox = document.getElementById("log-box");
  const projectVersionTag = document.querySelector(".project-version-tag");
  const tabButtons = Array.from(document.querySelectorAll(".tab-button"));
  const tabPanels = Array.from(document.querySelectorAll("[data-tab-panel]"));
  const TAB_STORAGE_KEY = "sst.dashboard.activeTab";

  function setActiveTab(tabName, { persist = true } = {}) {
    if (!tabName) return;
    let matched = false;
    tabButtons.forEach((button, index) => {
      const active = button.dataset.tabTarget === tabName;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", active ? "true" : "false");
      button.setAttribute("tabindex", active ? "0" : "-1");
      button.id = button.id || `dashboard-tab-${index}`;
      if (active) {
        matched = true;
      }
    });
    tabPanels.forEach((panel, index) => {
      const active = panel.dataset.tabPanel === tabName;
      panel.classList.toggle("active", active);
      panel.hidden = !active;
      panel.setAttribute("role", "tabpanel");
      panel.id = panel.id || `dashboard-panel-${index}`;
    });
    if (matched && persist) {
      try {
        window.localStorage.setItem(TAB_STORAGE_KEY, tabName);
      } catch (_error) {
        // ignore storage failures and keep the UI usable
      }
    }
  }

  function initializeTabs() {
    if (!tabButtons.length || !tabPanels.length) return;
    tabButtons.forEach((button, index) => {
      button.setAttribute("role", "tab");
      button.id = button.id || `dashboard-tab-${index}`;
      const panel = tabPanels.find((item) => item.dataset.tabPanel === button.dataset.tabTarget);
      if (panel) {
        panel.id = panel.id || `dashboard-panel-${index}`;
        button.setAttribute("aria-controls", panel.id);
        panel.setAttribute("aria-labelledby", button.id);
      }
      button.addEventListener("click", () => {
        setActiveTab(button.dataset.tabTarget || "translation");
      });
      button.addEventListener("keydown", (event) => {
        const currentIndex = tabButtons.indexOf(button);
        if (currentIndex < 0) return;
        let nextIndex = null;
        if (event.key === "ArrowRight") {
          nextIndex = (currentIndex + 1) % tabButtons.length;
        } else if (event.key === "ArrowLeft") {
          nextIndex = (currentIndex - 1 + tabButtons.length) % tabButtons.length;
        } else if (event.key === "Home") {
          nextIndex = 0;
        } else if (event.key === "End") {
          nextIndex = tabButtons.length - 1;
        }
        if (nextIndex === null) return;
        event.preventDefault();
        const nextButton = tabButtons[nextIndex];
        nextButton.focus();
        setActiveTab(nextButton.dataset.tabTarget || "translation");
      });
    });
    let initialTab = tabButtons[0]?.dataset.tabTarget || "translation";
    try {
      const saved = window.localStorage.getItem(TAB_STORAGE_KEY);
      if (saved) {
        initialTab = saved;
      }
    } catch (_error) {
      // ignore storage failures and keep the UI usable
    }
    if (!tabPanels.some((panel) => panel.dataset.tabPanel === initialTab)) {
      initialTab = tabButtons[0]?.dataset.tabTarget || "translation";
    }
    setActiveTab(initialTab, { persist: false });
  }

  function getCurrentLocale() {
    return window.I18n?.getLocale?.() || window.AppState.uiLanguage || "en";
  }

  function t(key, variables) {
    return window.I18n?.t ? window.I18n.t(key, variables) : key;
  }

  function localizePair(map, key, fallback) {
    return map?.[key]?.[getCurrentLocale()] || fallback || key;
  }

  function getProviderMeta(providerName) {
    const provider = PROVIDERS[providerName];
    if (!provider) return null;
    const copy = PROVIDER_COPY[providerName] || {};
    return {
      ...provider,
      label: provider.label,
      group: localizePair(PROVIDER_GROUP_KEYS, provider.group, provider.group),
      hint: localizePair({ value: copy.hint }, "value", provider.hint),
      status: localizePair({ value: copy.status }, "value", provider.status),
    };
  }

  function getLocalizedStylePresetMeta(presetName, preset) {
    if (!preset || preset?.built_in === false) {
      return preset || null;
    }
    const copy = STYLE_PRESET_COPY[presetName] || {};
    return {
      ...preset,
      label: localizePair({ value: copy.label }, "value", preset.label || presetName),
      description: localizePair({ value: copy.description }, "value", preset.description || ""),
    };
  }

  function normalizeExternalMessage(text) {
    if (!text) return text;
    let normalized = String(text);
    if (getCurrentLocale() === "en") {
      normalized = normalized.replaceAll(
        "Удаленный компьютер отклонил это сетевое подключение",
        "The remote computer refused the network connection"
      );
      normalized = normalized.replaceAll(
        "Удалённый компьютер отклонил это сетевое подключение",
        "The remote computer refused the network connection"
      );
    }
    return normalized;
  }

  function normalizeVersionLabel(versionText) {
    const raw = String(versionText || "").trim();
    if (!raw) {
      return "";
    }
    return raw.startsWith("v") ? raw : `v${raw}`;
  }

  function renderProjectVersionInfo(versionInfo) {
    if (!projectVersionTag) {
      return;
    }
    const currentVersion = normalizeVersionLabel(
      versionInfo?.current_version || projectVersionTag.textContent || ""
    ) || "v?.?.?";
    projectVersionTag.textContent = currentVersion;

    const sync = versionInfo?.sync && typeof versionInfo.sync === "object"
      ? versionInfo.sync
      : null;
    const updateAvailable = Boolean(sync?.update_available);
    projectVersionTag.classList.toggle("update-available", updateAvailable);

    const titleParts = [`Project version: ${currentVersion}`];
    if (sync?.github_repo) {
      titleParts.push(`Release source: ${sync.github_repo}`);
    }
    if (updateAvailable && sync?.latest_known_version) {
      titleParts.push(`Update available: v${sync.latest_known_version}`);
    } else if (sync?.enabled === false) {
      titleParts.push("Update check: disabled");
    } else if (sync?.enabled === true && !sync?.check_supported) {
      titleParts.push("Update check: repo is not configured");
    }
    projectVersionTag.title = titleParts.join(" | ");
  }

  function applyDocumentLocalization() {
    window.AppState.uiLanguage = getCurrentLocale();
    if (uiLanguageSelect) {
      uiLanguageSelect.value = window.AppState.uiLanguage;
    }
    if (window.I18n) {
      window.I18n.apply(document);
    }
    document.title = t("document.title.dashboard");
    updateOverlayPresetHint();
  }

  function renderRecognitionModeOptions() {
    if (!recognitionModeSelect) return;
    const selected = recognitionModeSelect.value || window.AppState.config?.asr?.mode || "local";
    Array.from(recognitionModeSelect.options).forEach((option) => {
      if (option.value === "browser_google") {
        option.textContent = t("overview.recognition.mode.browser_google");
      } else {
        option.textContent = t("overview.recognition.mode.local");
      }
    });
    recognitionModeSelect.value = selected;
  }

  function isRemoteWorkerRoleActive() {
    const runtimeRemote = window.AppState.runtime?.remote_diagnostics;
    if (runtimeRemote && typeof runtimeRemote === "object") {
      const enabled = runtimeRemote.enabled === true;
      const role = String(runtimeRemote.effective_role || runtimeRemote.configured_role || "disabled")
        .trim()
        .toLowerCase();
      if (enabled && role === "worker") {
        return true;
      }
    }
    return false;
  }

  function enforceRemoteWorkerRecognitionPolicy() {
    if (!window.AppState.config?.asr) {
      return false;
    }
    if (!isRemoteWorkerRoleActive()) {
      return false;
    }
    if (window.AppState.config.asr.mode !== "browser_google") {
      return false;
    }
    window.AppState.config.asr.mode = "local";
    syncConfigText();
    return true;
  }

  function renderVadModeOptions() {
    if (!rtVadMode) return;
    const selected = String(rtVadMode.value || window.AppState.config?.asr?.realtime?.vad_mode || "0");
    Array.from(rtVadMode.options).forEach((option) => {
      option.textContent = t(`tools.advanced.vad_mode.${option.value}`);
    });
    rtVadMode.value = selected;
  }

  function localizeLooseStaticText() {
    const replacements = {
      "Local Parakeet": getCurrentLocale() === "ru" ? "Локальный Parakeet" : "Local Parakeet",
      "Browser Speech": getCurrentLocale() === "ru" ? "Браузерное распознавание" : "Browser Speech",
      "Font family": t("style.field.font_family"),
      "Font size": t("style.field.font_size"),
      "Font weight": t("style.field.font_weight"),
      "Text color": t("style.field.text_color"),
      "Outline color": t("style.field.outline_color"),
      "Outline width": t("style.field.outline_width"),
      "Shadow color": t("style.field.shadow_color"),
      "Shadow blur": t("style.field.shadow_blur"),
      "Background color": t("style.field.background_color"),
      "Background opacity": t("style.field.background_opacity"),
      "Line spacing": t("style.field.line_spacing"),
      "Letter spacing": t("style.field.letter_spacing"),
      "Text alignment": t("style.field.text_align"),
      "Effect": t("style.field.effect"),
      "Shadow offset X": t("style.field.shadow_offset_x"),
      "Shadow offset Y": t("style.field.shadow_offset_y"),
      "Background padding X": t("style.field.background_padding_x"),
      "Background padding Y": t("style.field.background_padding_y"),
      "Background radius": t("style.field.background_radius"),
    };
    document.querySelectorAll("label > span, .metric-title, details summary, .section-heading h2, .section-heading p.eyebrow, option").forEach((element) => {
      if (element.dataset.i18n || element.children.length) return;
      const text = element.textContent.trim();
      if (replacements[text]) {
        element.textContent = replacements[text];
      }
    });
  }

  function localizeDiagnosticsSummary(text) {
    if (getCurrentLocale() !== "ru") {
      return text;
    }
    const replacements = [
      ["requested provider", "запрошенный провайдер"],
      ["requested device policy", "запрошенная политика устройства"],
      ["model", "модель"],
      ["torch cuda build", "сборка torch cuda"],
      ["torch cuda available", "torch cuda доступен"],
      ["gpu count", "число GPU"],
      ["gpu requested", "GPU запрошен"],
      ["gpu available", "GPU доступен"],
      ["degraded", "degraded"],
      ["provider", "провайдер"],
      ["python", "python"],
      ["venv", "venv"],
      ["vad mode", "режим VAD"],
      ["frame", "кадр"],
      ["partial interval", "интервал partial"],
      ["min speech", "минимум речи"],
      ["first partial", "первый partial"],
      ["silence hold", "удержание тишины"],
      ["final hold", "удержание финала"],
      ["max segment", "максимум сегмента"],
      ["quiet gate", "фильтр тихого входа"],
      ["min rms", "минимальный RMS"],
      ["min voiced ratio", "минимальная доля речи"],
      ["chunk window", "окно chunk"],
      ["chunk overlap", "overlap chunk"],
      ["min delta chars", "минимум символов изменения"],
      ["partial coalescing", "склейка partial"],
      ["rnnoise enabled", "rnnoise включён"],
      ["rnnoise strength", "сила rnnoise"],
      ["rnnoise available", "rnnoise доступен"],
      ["rnnoise active", "rnnoise активен"],
      ["rnnoise backend", "backend rnnoise"],
      ["rnnoise resample", "resample rnnoise"],
      ["rnnoise input rate", "частота входа rnnoise"],
      ["rnnoise proc rate", "частота обработки rnnoise"],
      ["rnnoise frame", "кадр rnnoise"],
      ["fallback", "fallback"],
      ["cpu fallback", "cpu fallback"],
      ["note", "заметка"],
      ["summary", "сводка"],
      ["configured", "настроен"],
      ["ready", "готов"],
      ["targets", "цели"],
      ["group", "группа"],
      ["experimental provider", "экспериментальный провайдер"],
      ["local provider", "локальный провайдер"],
      ["endpoint", "endpoint"],
      ["enabled", "включено"],
      ["mode", "режим"],
      ["state", "состояние"],
      ["connected", "подключено"],
      ["password", "пароль"],
      ["set", "задан"],
      ["empty", "пусто"],
      ["debug mirror", "debug mirror"],
      ["partials", "partials"],
      ["throttle", "throttle"],
      ["min delta", "минимум delta"],
      ["final delay", "задержка финала"],
      ["clear after", "очистить через"],
      ["retries", "повторы"],
      ["last send reused", "последняя отправка reuse"],
      ["last send waited", "последняя отправка ждала"],
      ["debug input", "debug input"],
      ["debug partials", "debug partials"],
      ["error", "ошибка"],
      ["last", "последнее"],
      ["debug last", "последний debug"],
      ["yes", "да"],
      ["no", "нет"],
      ["unknown", "неизвестно"],
      ["none", "нет"],
      ["disabled", "выключено"],
      ["vad ", "vad "],
      ["asr partial", "asr partial"],
      ["asr final", "asr final"],
      ["translation", "перевод"],
      ["total", "всего"],
      ["suppressed", "подавлено"],
      ["vad dropped", "отброшено VAD"],
      ["partials ", "partials "],
      ["finals ", "finals "],
    ];
    return replacements.reduce((result, [from, to]) => result.replaceAll(from, to), text);
  }

  function applyLanguageToUi() {
    applyDocumentLocalization();
    localizeLooseStaticText();
    if (healthBadge && !healthBadge.textContent.trim()) {
      healthBadge.textContent = t("runtime.badge.health", { value: t("common.unknown").toLowerCase() });
    }
    if (runtimeBadge && !runtimeBadge.textContent.trim()) {
      runtimeBadge.textContent = t("runtime.badge.runtime", { value: "idle" });
    }
    const fallbackOverlayUrl = `${window.location.origin}/overlay`;
    if (overlayText && (!overlayText.textContent.trim() || overlayText.textContent === t("common.loading"))) {
      overlayText.textContent = fallbackOverlayUrl;
    }
    if (overlayLink && (!overlayLink.href || overlayLink.getAttribute("href") === "#")) {
      overlayLink.href = fallbackOverlayUrl;
    }
    renderRecognitionModeOptions();
    renderVadModeOptions();
    renderTranslationProviderOptions();
    renderTranslationLanguageOptions();
    renderRecognitionLanguageOptions();
    renderTranslationOrder();
    renderSubtitleDisplayOrder();
    syncRecognitionControlsFromConfig();
    syncTranslationFormFromConfig();
    syncSimpleTuningControlsFromConfig();
    syncFontCatalogUi();
    if (window.AppState.config) {
      syncSubtitleStyleControlsFromConfig();
    }
    renderTranscript();
    renderTranslationResults();
    renderSubtitlePreview();
    renderDiagnostics(
      window.AppState.runtime?.asr_diagnostics || null,
      window.AppState.runtime?.translation_diagnostics || null,
      window.AppState.runtime?.metrics || null,
      window.AppState.runtime?.obs_caption_diagnostics || null
    );
  }

  function appendTextLog(target, message) {
    if (!target) return;
    if ("value" in target) {
      target.value += `${message}\n`;
    } else {
      target.textContent += `${message}\n`;
    }
    target.scrollTop = target.scrollHeight;
  }

  function sendClientLogPayload(payload) {
    const body = JSON.stringify(payload);
    fetch("/api/logs/client-event", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    }).catch(() => {
      if (typeof navigator?.sendBeacon === "function") {
        try {
          navigator.sendBeacon(
            "/api/logs/client-event",
            new Blob([body], { type: "application/json" })
          );
        } catch (_error) {
          // local fallback is best-effort
        }
      }
    });
  }

  function postClientLog(channel, message, details) {
    const payload = {
      channel,
      source: details?.source || "dashboard",
      message: String(message || "").trim(),
    };
    if (!payload.message) {
      return;
    }
    if (details && typeof details === "object") {
      const extraDetails = { ...details };
      delete extraDetails.source;
      if (Object.keys(extraDetails).length) {
        payload.details = extraDetails;
      }
    }
    sendClientLogPayload(payload);
  }

  function shouldPersistDashboardLog(message) {
    const normalized = String(message || "").trim().toLowerCase();
    if (!normalized) {
      return false;
    }
    return [
      "[desktop]",
      "[runtime]",
      "[asr]",
      "[translation]",
      "[ui]",
      "[browser-asr]",
      "[overlay]",
      "[obs-cc]",
      "[config] imported",
      "[config] exported",
      "[config] invalid",
      "[config] save failed",
      "[profiles] loaded",
      "[profiles] saved",
      "[profiles] deleted",
      "[audio] detected",
      "[audio] no input devices found",
      "[translation] google key normalized",
      "[ws] connected",
      "[ws] disconnected",
    ].some((token) => normalized.includes(token));
  }

  function persistDashboardLog(message, details) {
    if (!shouldPersistDashboardLog(message)) {
      return;
    }
    postClientLog("dashboard", message, details);
  }

  function log(message, options = {}) {
    if (!logBox) return;
    appendTextLog(logBox, message);
    if (options.persist !== false) {
      persistDashboardLog(message, options);
    }
  }

  function isForcedDesktopPage() {
    try {
      return new URLSearchParams(window.location.search).get("desktop") === "1";
    } catch (_error) {
      return false;
    }
  }

  function isDesktopMode() {
    return Boolean(window.DesktopBridge?.isDesktopMode?.());
  }

  async function openExternalUrl(url) {
    if (window.DesktopBridge?.openExternalUrl) {
      return Boolean(await window.DesktopBridge.openExternalUrl(url));
    }
    if (isForcedDesktopPage() || isDesktopMode()) {
      return false;
    }
    const popup = window.open(url, "_blank", "noopener,noreferrer");
    return Boolean(popup);
  }

  function buildBrowserAsrUrl() {
    const currentLocale = getCurrentLocale();
    const params = new URLSearchParams();
    params.set("autostart", "1");
    if (currentLocale) {
      params.set("locale", currentLocale);
    }
    const relativeUrl = `/google-asr?${params.toString()}`;
    try {
      return new URL(relativeUrl, window.location.href).toString();
    } catch (_error) {
      return relativeUrl;
    }
  }

  function openBrowserAsrWindowPlaceholder() {
    if (isDesktopMode()) {
      return null;
    }
    const popup = window.open("", "browser_asr_worker");
    if (!popup) {
      log("[browser-asr] popup blocked; allow popups for this local app");
      return null;
    }
    try {
      popup.document.title = getCurrentLocale() === "ru"
        ? "Подготовка browser worker..."
        : "Preparing browser worker...";
      popup.document.body.style.margin = "0";
      popup.document.body.style.fontFamily = "Segoe UI, sans-serif";
      popup.document.body.style.background = "#08121f";
      popup.document.body.style.color = "#dfe8ff";
      popup.document.body.style.display = "grid";
      popup.document.body.style.placeItems = "center";
      popup.document.body.style.minHeight = "100vh";
      popup.document.body.textContent = getCurrentLocale() === "ru"
        ? "Подготовка окна browser распознавания..."
        : "Preparing browser recognition window...";
    } catch (_error) {
      // Browser security rules can block styling or DOM writes on some engines.
    }
    return popup;
  }

  function applyDesktopContext(context) {
    if (!context?.desktop_mode) {
      return;
    }
    const signature = JSON.stringify([
      context.desktop_mode,
      context.startup_mode || "",
      context.remote_role || "",
      context.profile_name || "",
      context.install_profile || "",
    ]);
    if (window.AppState.desktop && window.AppState.desktop.__signature === signature) {
      return;
    }
    window.AppState.desktop = context;
    window.AppState.desktop.__signature = signature;
    log(getCurrentLocale() === "ru"
      ? `[desktop] desktop launcher активен | startup=${context.startup_mode || "local"} | remote_role=${context.remote_role || "disabled"} | profile=${context.profile_name || "default"} | install=${context.install_profile || "auto"}`
      : `[desktop] desktop launcher active | startup=${context.startup_mode || "local"} | remote_role=${context.remote_role || "disabled"} | profile=${context.profile_name || "default"} | install=${context.install_profile || "auto"}`);
    if (window.AppState.config) {
      enforceDesktopStartupMode(window.AppState.config);
      syncRecognitionControlsFromConfig();
      syncConfigText();
    }
    updateRecognitionModeUi();
  }

  function enforceDesktopStartupMode(payload) {
    if (!payload || !payload.asr) {
      return payload;
    }
    const startupMode = String(window.AppState.desktop?.startup_mode || "").trim().toLowerCase();
    if (startupMode === "browser_google") {
      payload.asr.mode = "browser_google";
      return payload;
    }
    if (startupMode === "local") {
      const installProfile = String(window.AppState.desktop?.install_profile || "").trim().toLowerCase();
      if (installProfile === "cpu") {
        payload.asr.prefer_gpu = false;
      } else if (installProfile === "nvidia") {
        payload.asr.prefer_gpu = true;
      }
    }
    return payload;
  }

  function cloneConfig(value) {
    return JSON.parse(JSON.stringify(value ?? null));
  }

  function setSaveButtonsBusy(isBusy) {
    if (globalSaveBtn) {
      globalSaveBtn.disabled = isBusy;
      globalSaveBtn.textContent = isBusy
        ? (getCurrentLocale() === "ru" ? "Сохранение..." : "Saving...")
        : t("common.save");
    }
    if (configSaveBtn) {
      configSaveBtn.disabled = isBusy;
      configSaveBtn.textContent = isBusy
        ? (getCurrentLocale() === "ru" ? "Сохранение..." : "Saving...")
        : t("tools.config.save");
    }
  }

  function setSaveStatus(message, tone = "info") {
    if (!saveStatusText) return;
    saveStatusText.textContent = message;
    if (tone && tone !== "info") {
      saveStatusText.dataset.tone = tone;
    } else {
      delete saveStatusText.dataset.tone;
    }
  }

  function getRestartRequiredReasons(previousPayload, nextPayload) {
    const reasons = [];
    if ((previousPayload?.audio?.input_device_id ?? null) !== (nextPayload?.audio?.input_device_id ?? null)) {
      reasons.push(getCurrentLocale() === "ru" ? "микрофон" : "microphone device");
    }
    if (String(previousPayload?.asr?.mode || "local") !== String(nextPayload?.asr?.mode || "local")) {
      reasons.push(getCurrentLocale() === "ru" ? "режим распознавания" : "recognition mode");
    }
    if (String(previousPayload?.asr?.provider_preference || "") !== String(nextPayload?.asr?.provider_preference || "")) {
      reasons.push(getCurrentLocale() === "ru" ? "ASR-провайдер" : "ASR provider");
    }
    if (Boolean(previousPayload?.asr?.prefer_gpu) !== Boolean(nextPayload?.asr?.prefer_gpu)) {
      reasons.push(getCurrentLocale() === "ru" ? "политика GPU" : "GPU policy");
    }
    if (
      String(previousPayload?.asr?.browser?.recognition_language || "ru-RU") !==
      String(nextPayload?.asr?.browser?.recognition_language || "ru-RU")
    ) {
      reasons.push(getCurrentLocale() === "ru" ? "язык браузерного распознавания" : "browser recognition language");
    }
    return reasons;
  }

  function formatList(items) {
    if (!items.length) return "";
    if (items.length === 1) return items[0];
    if (items.length === 2) return getCurrentLocale() === "ru" ? `${items[0]} и ${items[1]}` : `${items[0]} and ${items[1]}`;
    return getCurrentLocale() === "ru"
      ? `${items.slice(0, -1).join(", ")} и ${items[items.length - 1]}`
      : `${items.slice(0, -1).join(", ")}, and ${items[items.length - 1]}`;
  }

  function buildSaveStatusMessage(liveApplied, restartReasons) {
    if (!restartReasons.length) {
      return liveApplied
        ? (getCurrentLocale() === "ru" ? "Сохранено и сразу применено." : "Saved and applied immediately.")
        : (getCurrentLocale() === "ru" ? "Сохранено локально." : "Saved locally.");
    }
    const subject = formatList(restartReasons);
    const restartLabel = window.AppState.runtime?.is_running
      ? (getCurrentLocale() === "ru" ? "после Стоп/Старт" : "after Stop/Start")
      : (getCurrentLocale() === "ru" ? "при следующем Старт" : "on the next Start");
    if (liveApplied) {
      return getCurrentLocale() === "ru"
        ? `Сохранено и сразу применено. Изменения для: ${subject} вступят в силу ${restartLabel}.`
        : `Saved and applied immediately. ${subject} changes will take effect ${restartLabel}.`;
    }
    return getCurrentLocale() === "ru"
      ? `Сохранено локально. Изменения для: ${subject} вступят в силу ${restartLabel}.`
      : `Saved locally. ${subject} changes will take effect ${restartLabel}.`;
  }

  function ensureConfigShape(payload) {
    const normalized = payload || {};
    delete normalized.runtime;
    delete normalized.name;

    if (!normalized.audio || typeof normalized.audio !== "object") {
      normalized.audio = { input_device_id: null };
    }
    if (!normalized.profile || typeof normalized.profile !== "string") {
      normalized.profile = "default";
    }
    if (!normalized.overlay || typeof normalized.overlay !== "object") {
      normalized.overlay = { preset: "single", compact: false };
    }
    normalized.overlay.preset = ["single", "dual-line", "stacked"].includes(String(normalized.overlay.preset || "single"))
      ? String(normalized.overlay.preset || "single")
      : "single";
    normalized.overlay.compact = Boolean(normalized.overlay.compact);
    if (!normalized.obs_closed_captions || typeof normalized.obs_closed_captions !== "object") {
      normalized.obs_closed_captions = {};
    }
    if (!normalized.obs_closed_captions.connection || typeof normalized.obs_closed_captions.connection !== "object") {
      normalized.obs_closed_captions.connection = {};
    }
    if (!normalized.obs_closed_captions.timing || typeof normalized.obs_closed_captions.timing !== "object") {
      normalized.obs_closed_captions.timing = {};
    }
    if (!normalized.obs_closed_captions.debug_mirror || typeof normalized.obs_closed_captions.debug_mirror !== "object") {
      normalized.obs_closed_captions.debug_mirror = {};
    }
    normalized.obs_closed_captions.enabled = Boolean(normalized.obs_closed_captions.enabled);
    normalized.obs_closed_captions.output_mode = [
      "disabled",
      "source_live",
      "source_final_only",
      "translation_1",
      "translation_2",
      "translation_3",
      "translation_4",
      "translation_5",
      "first_visible_line",
    ].includes(String(normalized.obs_closed_captions.output_mode || "disabled"))
      ? String(normalized.obs_closed_captions.output_mode || "disabled")
      : "disabled";
    normalized.obs_closed_captions.connection.host =
      String(normalized.obs_closed_captions.connection.host || "127.0.0.1").trim() || "127.0.0.1";
    normalized.obs_closed_captions.connection.port = Math.max(
      1,
      Math.min(65535, parseIntegerOr(normalized.obs_closed_captions.connection.port ?? 4455, 4455))
    );
    normalized.obs_closed_captions.connection.password =
      String(normalized.obs_closed_captions.connection.password || "");
    normalized.obs_closed_captions.debug_mirror.enabled =
      normalized.obs_closed_captions.debug_mirror.enabled === true;
    normalized.obs_closed_captions.debug_mirror.input_name =
      String(normalized.obs_closed_captions.debug_mirror.input_name || "CC_DEBUG").trim() || "CC_DEBUG";
    normalized.obs_closed_captions.debug_mirror.send_partials =
      normalized.obs_closed_captions.debug_mirror.send_partials !== false;
    normalized.obs_closed_captions.timing.send_partials =
      normalized.obs_closed_captions.timing.send_partials !== false;
    normalized.obs_closed_captions.timing.partial_throttle_ms = Math.max(
      0,
      parseIntegerOr(normalized.obs_closed_captions.timing.partial_throttle_ms ?? 250, 250)
    );
    normalized.obs_closed_captions.timing.min_partial_delta_chars = Math.max(
      0,
      parseIntegerOr(normalized.obs_closed_captions.timing.min_partial_delta_chars ?? 3, 3)
    );
    normalized.obs_closed_captions.timing.final_replace_delay_ms = Math.max(
      0,
      parseIntegerOr(normalized.obs_closed_captions.timing.final_replace_delay_ms ?? 0, 0)
    );
    normalized.obs_closed_captions.timing.clear_after_ms = Math.max(
      0,
      parseIntegerOr(normalized.obs_closed_captions.timing.clear_after_ms ?? 2500, 2500)
    );
    normalized.obs_closed_captions.timing.avoid_duplicate_text =
      normalized.obs_closed_captions.timing.avoid_duplicate_text !== false;
    if (!normalized.translation || typeof normalized.translation !== "object") {
      normalized.translation = {};
    }
    if (!normalized.asr || typeof normalized.asr !== "object") {
      normalized.asr = {
        mode: "local",
        provider_preference: "official_eu_parakeet_realtime",
        prefer_gpu: true,
        browser: {},
        realtime: {},
      };
    }
    if (!normalized.subtitle_output || typeof normalized.subtitle_output !== "object") {
      normalized.subtitle_output = {};
    }
    if (!normalized.remote || typeof normalized.remote !== "object") {
      normalized.remote = {};
    }
    normalized.remote.enabled = normalized.remote.enabled === true;
    normalized.remote.role = String(
      normalized.remote.role || (normalized.remote.enabled ? "controller" : "disabled")
    )
      .trim()
      .toLowerCase();
    if (!["disabled", "controller", "worker"].includes(normalized.remote.role)) {
      normalized.remote.role = normalized.remote.enabled ? "controller" : "disabled";
    }
    if (!normalized.remote.enabled) {
      normalized.remote.role = "disabled";
    }
    if (!normalized.remote.controller || typeof normalized.remote.controller !== "object") {
      normalized.remote.controller = {};
    }
    normalized.remote.controller.worker_url = String(normalized.remote.controller.worker_url || "").trim();
    if (!normalized.asr.provider_preference || typeof normalized.asr.provider_preference !== "string") {
      normalized.asr.provider_preference = "official_eu_parakeet_realtime";
    }
    normalized.asr.mode = String(normalized.asr.mode || "local").toLowerCase();
    if (!["local", "browser_google"].includes(normalized.asr.mode)) {
      normalized.asr.mode = "local";
    }
    if (normalized.remote.enabled && normalized.remote.role === "worker" && normalized.asr.mode === "browser_google") {
      normalized.asr.mode = "local";
    }
    normalized.asr.provider_preference = String(normalized.asr.provider_preference).toLowerCase();
    if (!["official_eu_parakeet_realtime", "official_eu_parakeet", "auto"].includes(normalized.asr.provider_preference)) {
      normalized.asr.provider_preference = "official_eu_parakeet_realtime";
    }
    normalized.asr.prefer_gpu = normalized.asr.prefer_gpu !== false;
    if (!normalized.asr.browser || typeof normalized.asr.browser !== "object") {
      normalized.asr.browser = {};
    }
    normalized.asr.browser.recognition_language =
      String(normalized.asr.browser.recognition_language || "ru-RU").trim() || "ru-RU";
    normalized.asr.browser.interim_results = normalized.asr.browser.interim_results !== false;
    normalized.asr.browser.continuous_results = normalized.asr.browser.continuous_results === true;
    normalized.asr.browser.force_finalization_enabled = normalized.asr.browser.force_finalization_enabled !== false;
    normalized.asr.browser.force_finalization_timeout_ms = Math.max(
      300,
      Math.min(15000, parseIntegerOr(normalized.asr.browser.force_finalization_timeout_ms ?? 1600, 1600))
    );
    normalized.asr.rnnoise_enabled =
      normalized.asr.rnnoise_enabled === true ||
      (normalized.asr.rnnoise_enabled == null && normalized.asr.experimental_noise_reduction_enabled === true);
    normalized.asr.rnnoise_strength = Math.max(
      0,
      Math.min(100, parseIntegerOr(normalized.asr.rnnoise_strength ?? 70, 70))
    );
    if (!normalized.asr.realtime || typeof normalized.asr.realtime !== "object") {
      normalized.asr.realtime = {};
    }
    normalized.asr.realtime.vad_mode = Math.max(
      0,
      Math.min(3, parseIntegerOr(normalized.asr.realtime.vad_mode ?? 2, 2))
    );
    normalized.asr.realtime.energy_gate_enabled = normalized.asr.realtime.energy_gate_enabled === true;
    normalized.asr.realtime.min_rms_for_recognition = Math.max(
      0,
      Math.min(0.05, parseFloatOr(normalized.asr.realtime.min_rms_for_recognition ?? 0.0018, 0.0018))
    );
    normalized.asr.realtime.min_voiced_ratio = Math.max(
      0,
      Math.min(1, parseFloatOr(normalized.asr.realtime.min_voiced_ratio ?? 0.0, 0.0))
    );
    normalized.asr.realtime.partial_emit_interval_ms = Math.max(
      60,
      parseIntegerOr(normalized.asr.realtime.partial_emit_interval_ms ?? 450, 450)
    );
    normalized.asr.realtime.min_speech_ms = Math.max(
      0,
      parseIntegerOr(normalized.asr.realtime.min_speech_ms ?? 180, 180)
    );
    normalized.asr.realtime.first_partial_min_speech_ms = Math.max(
      normalized.asr.realtime.min_speech_ms,
        parseIntegerOr(
        normalized.asr.realtime.first_partial_min_speech_ms ?? normalized.asr.realtime.min_speech_ms,
        normalized.asr.realtime.min_speech_ms
        )
      );
    normalized.asr.realtime.max_segment_ms = Math.max(
      500,
      parseIntegerOr(normalized.asr.realtime.max_segment_ms ?? 5500, 5500)
    );
    normalized.asr.realtime.silence_hold_ms = Math.max(
      60,
      parseIntegerOr(normalized.asr.realtime.silence_hold_ms ?? 180, 180)
    );
    normalized.asr.realtime.finalization_hold_ms = Math.max(
      normalized.asr.realtime.silence_hold_ms,
      parseIntegerOr(normalized.asr.realtime.finalization_hold_ms ?? 360, 360)
    );
    normalized.asr.realtime.chunk_window_ms = Math.max(
      0,
      parseIntegerOr(normalized.asr.realtime.chunk_window_ms ?? 0, 0)
    );
    normalized.asr.realtime.chunk_overlap_ms = Math.max(
      0,
      Math.min(
        normalized.asr.realtime.chunk_window_ms,
        parseIntegerOr(normalized.asr.realtime.chunk_overlap_ms ?? 0, 0)
      )
    );
    normalized.asr.realtime.partial_min_delta_chars = Math.max(
      0,
      parseIntegerOr(normalized.asr.realtime.partial_min_delta_chars ?? 12, 12)
    );
    normalized.asr.realtime.partial_coalescing_ms = Math.max(
      0,
      parseIntegerOr(normalized.asr.realtime.partial_coalescing_ms ?? 160, 160)
    );

    if (!normalized.subtitle_lifecycle || typeof normalized.subtitle_lifecycle !== "object") {
      normalized.subtitle_lifecycle = {};
    }
    const completedBlockTtl = Math.max(
      500,
      parseIntegerOr(normalized.subtitle_lifecycle.completed_block_ttl_ms ?? 4500, 4500)
    );
    normalized.subtitle_lifecycle.completed_source_ttl_ms = Math.max(
      500,
      parseIntegerOr(normalized.subtitle_lifecycle.completed_source_ttl_ms ?? completedBlockTtl, completedBlockTtl)
    );
    normalized.subtitle_lifecycle.completed_translation_ttl_ms = Math.max(
      500,
      parseIntegerOr(normalized.subtitle_lifecycle.completed_translation_ttl_ms ?? completedBlockTtl, completedBlockTtl)
    );
    normalized.subtitle_lifecycle.completed_block_ttl_ms = Math.max(
      normalized.subtitle_lifecycle.completed_source_ttl_ms,
      normalized.subtitle_lifecycle.completed_translation_ttl_ms
    );
    normalized.subtitle_lifecycle.pause_to_finalize_ms = Math.max(
      120,
      parseIntegerOr(
        normalized.subtitle_lifecycle.pause_to_finalize_ms ?? normalized.asr.realtime.finalization_hold_ms ?? 350,
        normalized.asr.realtime.finalization_hold_ms ?? 350
      )
    );
    normalized.subtitle_lifecycle.allow_early_replace_on_next_final =
      normalized.subtitle_lifecycle.allow_early_replace_on_next_final !== false;
    normalized.subtitle_lifecycle.sync_source_and_translation_expiry =
      normalized.subtitle_lifecycle.sync_source_and_translation_expiry !== false;
    normalized.subtitle_lifecycle.hard_max_phrase_ms = Math.max(
      1000,
      parseIntegerOr(
        normalized.subtitle_lifecycle.hard_max_phrase_ms ?? normalized.asr.realtime.max_segment_ms ?? 5500,
        normalized.asr.realtime.max_segment_ms ?? 5500
      )
    );
    normalized.asr.realtime.finalization_hold_ms = normalized.subtitle_lifecycle.pause_to_finalize_ms;
    normalized.asr.realtime.max_segment_ms = normalized.subtitle_lifecycle.hard_max_phrase_ms;

    const translation = normalized.translation;
    if (!translation.provider || !PROVIDERS[translation.provider]) {
      translation.provider = "google_translate_v2";
    }
    translation.enabled = Boolean(translation.enabled);
    if (!Array.isArray(translation.target_languages)) {
      translation.target_languages = Array.isArray(normalized.targets) ? normalized.targets : ["en"];
    }
    translation.target_languages = translation.target_languages
      .map((item) => String(item).toLowerCase())
      .filter((item, index, array) => item && array.indexOf(item) === index);
    if (!translation.provider_settings || typeof translation.provider_settings !== "object") {
      translation.provider_settings = {};
    }
    Object.keys(PROVIDERS).forEach((providerName) => {
      if (!translation.provider_settings[providerName] || typeof translation.provider_settings[providerName] !== "object") {
        translation.provider_settings[providerName] = {};
      }
    });
    translation.provider_settings.google_translate_v2.api_key =
      String(translation.provider_settings.google_translate_v2.api_key || "");
    translation.provider_settings.google_gas_url.gas_url =
      String(translation.provider_settings.google_gas_url.gas_url || "");
    translation.provider_settings.google_web = {};
    translation.provider_settings.azure_translator.api_key =
      String(translation.provider_settings.azure_translator.api_key || "");
    translation.provider_settings.azure_translator.endpoint =
      String(translation.provider_settings.azure_translator.endpoint || "https://api.cognitive.microsofttranslator.com");
    translation.provider_settings.azure_translator.region =
      String(translation.provider_settings.azure_translator.region || "");
    translation.provider_settings.deepl.api_key = String(translation.provider_settings.deepl.api_key || "");
    translation.provider_settings.deepl.api_url =
      String(translation.provider_settings.deepl.api_url || PROVIDERS.deepl.apiUrlPlaceholder);
    translation.provider_settings.libretranslate.api_key =
      String(translation.provider_settings.libretranslate.api_key || "");
    translation.provider_settings.libretranslate.api_url =
      String(translation.provider_settings.libretranslate.api_url || PROVIDERS.libretranslate.apiUrlPlaceholder);
    translation.provider_settings.openai.api_key = String(translation.provider_settings.openai.api_key || "");
    translation.provider_settings.openai.base_url =
      String(translation.provider_settings.openai.base_url || PROVIDERS.openai.baseUrlPlaceholder);
    translation.provider_settings.openai.model = String(translation.provider_settings.openai.model || "");
    translation.provider_settings.openai.custom_prompt =
      String(translation.provider_settings.openai.custom_prompt || "");
    translation.provider_settings.openrouter.api_key = String(translation.provider_settings.openrouter.api_key || "");
    translation.provider_settings.openrouter.base_url =
      String(translation.provider_settings.openrouter.base_url || PROVIDERS.openrouter.baseUrlPlaceholder);
    translation.provider_settings.openrouter.model = String(translation.provider_settings.openrouter.model || "");
    translation.provider_settings.openrouter.custom_prompt =
      String(translation.provider_settings.openrouter.custom_prompt || "");
    translation.provider_settings.lm_studio.api_key = String(translation.provider_settings.lm_studio.api_key || "");
    translation.provider_settings.lm_studio.base_url =
      String(translation.provider_settings.lm_studio.base_url || PROVIDERS.lm_studio.baseUrlPlaceholder);
    translation.provider_settings.lm_studio.model = String(translation.provider_settings.lm_studio.model || "");
    translation.provider_settings.lm_studio.custom_prompt =
      String(translation.provider_settings.lm_studio.custom_prompt || "");
    translation.provider_settings.ollama.api_key = String(translation.provider_settings.ollama.api_key || "");
    translation.provider_settings.ollama.base_url =
      String(translation.provider_settings.ollama.base_url || PROVIDERS.ollama.baseUrlPlaceholder);
    translation.provider_settings.ollama.model = String(translation.provider_settings.ollama.model || "");
    translation.provider_settings.ollama.custom_prompt =
      String(translation.provider_settings.ollama.custom_prompt || "");
    translation.provider_settings.mymemory = {};
    translation.provider_settings.public_libretranslate_mirror.api_url =
      String(
        translation.provider_settings.public_libretranslate_mirror.api_url ||
          PROVIDERS.public_libretranslate_mirror.apiUrlPlaceholder
      );
    translation.provider_settings.free_web_translate = {};

    normalized.targets = [...translation.target_languages];

    const subtitleOutput = normalized.subtitle_output;
    subtitleOutput.show_source = subtitleOutput.show_source !== false;
    subtitleOutput.show_translations = subtitleOutput.show_translations !== false;
    subtitleOutput.max_translation_languages = Math.max(
      0,
      Math.min(5, Number.parseInt(String(subtitleOutput.max_translation_languages ?? 2), 10) || 0)
    );
    if (!Array.isArray(subtitleOutput.display_order)) {
      subtitleOutput.display_order = ["source", ...translation.target_languages];
    }
    subtitleOutput.display_order = subtitleOutput.display_order
      .map((item) => String(item).toLowerCase())
      .filter((item, index, array) => (item === "source" || translation.target_languages.includes(item)) && array.indexOf(item) === index);
    if (!subtitleOutput.display_order.includes("source")) {
      subtitleOutput.display_order.push("source");
    }
    translation.target_languages.forEach((code) => {
      if (!subtitleOutput.display_order.includes(code)) {
        subtitleOutput.display_order.push(code);
      }
    });

    normalized.subtitle_style = normalizeSubtitleStyleConfig(normalized.subtitle_style || {});

    return normalized;
  }

  function syncConfigText() {
    if (configJson && window.AppState.config) {
      configJson.value = JSON.stringify(window.AppState.config, null, 2);
    }
  }

  function getLanguageLabel(code) {
    const item = LANGUAGES.find((entry) => entry.code === code);
    return localizePair(LANGUAGE_LABELS, code, item?.label || code);
  }

  function getRecognitionModeLabel(mode) {
    return mode === "browser_google"
      ? (getCurrentLocale() === "ru" ? "Браузерное распознавание" : "Browser Speech")
      : (getCurrentLocale() === "ru" ? "Локальный Parakeet" : "Local Parakeet");
  }

  function updateOverlayPresetHint() {
    if (!overlayPresetHint) {
      return;
    }
    const preset = String(overlayPresetSelect?.value || window.AppState.config?.overlay?.preset || "single");
    if (preset === "single") {
      overlayPresetHint.textContent = getCurrentLocale() === "ru"
        ? "Одна строка: все видимые элементы выводятся в одном физическом ряду слева направо по сохранённому порядку."
        : "Single: all visible subtitle items are rendered inside one physical row in the saved order.";
      return;
    }
    if (preset === "dual-line") {
      overlayPresetHint.textContent = getCurrentLocale() === "ru"
        ? "Две строки: первый видимый элемент идёт в верхний ряд, остальные делят нижний ряд."
        : "Dual-line: the first visible item uses the top row, and the remaining visible items share the second row.";
      return;
    }
    overlayPresetHint.textContent = getCurrentLocale() === "ru"
      ? "Стопка: каждый видимый элемент получает собственный ряд."
      : "Stacked: each visible subtitle item gets its own row.";
  }

  function renderRecognitionLanguageOptions() {
    if (!recognitionLanguageSelect) return;
    recognitionLanguageSelect.innerHTML = "";
    BROWSER_RECOGNITION_LANGUAGES.forEach((item) => {
      const option = document.createElement("option");
      option.value = item.code;
      option.textContent = localizePair(BROWSER_RECOGNITION_LABELS, item.code, item.label);
      recognitionLanguageSelect.appendChild(option);
    });
  }

  function syncRecognitionControlsFromConfig() {
    if (!window.AppState.config) return;
    enforceRemoteWorkerRecognitionPolicy();
    const asr = window.AppState.config.asr || {};
    const browser = asr.browser || {};
    if (recognitionModeSelect) {
      recognitionModeSelect.value = asr.mode || "local";
    }
    if (recognitionLanguageSelect) {
      recognitionLanguageSelect.value = browser.recognition_language || "ru-RU";
    }
    updateRecognitionModeUi();
  }

  function updateRecognitionModeUi() {
    const forcedToLocal = enforceRemoteWorkerRecognitionPolicy();
    const mode = window.AppState.config?.asr?.mode || "local";
    const browserMode = mode === "browser_google";
    const remoteWorkerRole = isRemoteWorkerRoleActive();
    const browserOnlyDesktopSession = String(window.AppState.desktop?.startup_mode || "").trim().toLowerCase() === "browser_google";
    setElementVisibility(recognitionLanguageRow, browserMode);
    if (recognitionModeSelect) {
      const browserModeOption = Array.from(recognitionModeSelect.options).find((option) => option.value === "browser_google");
      if (browserModeOption) {
        browserModeOption.disabled = remoteWorkerRole;
      }
      if (remoteWorkerRole && recognitionModeSelect.value === "browser_google") {
        recognitionModeSelect.value = "local";
      }
      recognitionModeSelect.disabled = browserOnlyDesktopSession;
    }
    if (audioInputSelect) {
      audioInputSelect.disabled = browserMode;
    }
    if (recognitionModeHint) {
      const browserHint = t("overview.recognition.hint.browser_google");
      recognitionModeHint.textContent = remoteWorkerRole
        ? t("overview.recognition.hint.remote_worker_ai_only")
        : browserMode
          ? browserHint
          : t("overview.recognition.hint.local");
    }
    if (forcedToLocal) {
      log(getCurrentLocale() === "ru"
        ? "[asr] browser mode отключён: remote worker поддерживает только AI runtime"
        : "[asr] browser mode disabled: remote worker supports AI runtime only");
    }
    if (audioInputMeta && browserMode) {
      audioInputMeta.textContent = getCurrentLocale() === "ru"
        ? "В Browser Speech микрофон выбирается через значок разрешений в адресной строке браузера."
        : "In Browser Speech mode, switch microphone using the browser permission icon in the address bar.";
    } else if (audioInputMeta && audioInputSelect) {
      const option = audioInputSelect.selectedOptions?.[0];
      audioInputMeta.textContent = option?.dataset.meta || (getCurrentLocale() === "ru" ? "Устройство не выбрано." : "No device selected.");
    }
  }

  function syncRecognitionConfigFromControls() {
    if (!window.AppState.config) return;
    const asr = window.AppState.config.asr;
    const remoteWorkerRole = isRemoteWorkerRoleActive();
    asr.mode = !remoteWorkerRole && recognitionModeSelect?.value === "browser_google" ? "browser_google" : "local";
    asr.browser = asr.browser || {};
    asr.browser.recognition_language = recognitionLanguageSelect?.value || "ru-RU";
    syncRecognitionControlsFromConfig();
    syncConfigText();
  }

  async function navigateBrowserAsrWindow() {
    const browserAsrUrl = buildBrowserAsrUrl();
    if (isDesktopMode()) {
      const opened = await openExternalUrl(browserAsrUrl);
      if (!opened) {
        log(getCurrentLocale() === "ru"
          ? "[browser-asr] не удалось открыть внешний browser worker"
          : "[browser-asr] failed to open external browser worker");
      }
      return;
    }
    const popup = window.open(browserAsrUrl, "browser_asr_worker");
    if (!popup) {
      log("[browser-asr] popup blocked; allow popups for this local app");
      return;
    }
    popup.focus();
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function parseIntegerOr(value, fallback) {
    const parsed = Number.parseInt(String(value), 10);
    return Number.isFinite(parsed) ? parsed : fallback;
  }

  function parseFloatOr(value, fallback) {
    const parsed = Number.parseFloat(String(value));
    return Number.isFinite(parsed) ? parsed : fallback;
  }

  function formatSecondsFromMs(value, fallbackMs) {
    const ms = Math.max(0, parseIntegerOr(value ?? fallbackMs, fallbackMs));
    return (ms / 1000).toFixed(1);
  }

  function parseSecondsToMs(value, fallbackMs, minimumMs) {
    const seconds = parseFloatOr(value ?? String(fallbackMs / 1000), fallbackMs / 1000);
    return Math.max(minimumMs, Math.round(seconds * 1000));
  }

  function getStylePresetCatalog() {
    return window.AppState.subtitleStylePresets || {};
  }

  function normalizeSubtitleStyleConfig(styleConfig) {
    return window.SubtitleStyleRenderer
      ? window.SubtitleStyleRenderer.normalizeStyleConfig(styleConfig, getStylePresetCatalog())
      : styleConfig || {};
  }

  function buildSubtitleStyleFromPreset(presetName) {
    return window.SubtitleStyleRenderer
      ? window.SubtitleStyleRenderer.buildStyleFromPreset(getStylePresetCatalog(), presetName)
      : {};
  }

  function setElementVisibility(element, visible) {
    if (!element) return;
    element.hidden = !visible;
    element.classList.toggle("is-hidden", !visible);
    element.style.display = visible ? "" : "none";
  }

  function syncRnnoiseStrengthLabel() {
    if (!asrRnnoiseStrengthLabel) return;
    const strength = Math.max(0, Math.min(100, parseIntegerOr(asrRnnoiseStrength?.value ?? 70, 70)));
    asrRnnoiseStrengthLabel.textContent = `${strength}%`;
  }

  function updateObsCcTimingFieldState() {
    const mode = obsCcOutputMode?.value || "disabled";
    const partialsRelevant = mode === "source_live";
    if (obsCcSendPartials) {
      obsCcSendPartials.disabled = !partialsRelevant;
    }
    if (obsCcPartialThrottle) {
      obsCcPartialThrottle.disabled = !partialsRelevant;
    }
    if (obsCcMinPartialDelta) {
      obsCcMinPartialDelta.disabled = !partialsRelevant;
    }
  }

  function syncObsCcControlsFromConfig() {
    if (!window.AppState.config) return;
    const obsCc = window.AppState.config.obs_closed_captions || {};
    const connection = obsCc.connection || {};
    const debugMirror = obsCc.debug_mirror || {};
    const timing = obsCc.timing || {};
    if (obsCcEnabled) obsCcEnabled.checked = Boolean(obsCc.enabled);
    if (obsCcHost) obsCcHost.value = connection.host || "127.0.0.1";
    if (obsCcPort) obsCcPort.value = String(connection.port ?? 4455);
    if (obsCcPassword) obsCcPassword.value = connection.password || "";
    if (obsCcOutputMode) obsCcOutputMode.value = obsCc.output_mode || "disabled";
    if (obsCcDebugEnabled) obsCcDebugEnabled.checked = debugMirror.enabled === true;
    if (obsCcDebugInputName) obsCcDebugInputName.value = debugMirror.input_name || "CC_DEBUG";
    if (obsCcDebugSendPartials) obsCcDebugSendPartials.checked = debugMirror.send_partials !== false;
    if (obsCcSendPartials) obsCcSendPartials.checked = timing.send_partials !== false;
    if (obsCcPartialThrottle) obsCcPartialThrottle.value = String(timing.partial_throttle_ms ?? 250);
    if (obsCcMinPartialDelta) obsCcMinPartialDelta.value = String(timing.min_partial_delta_chars ?? 3);
    if (obsCcFinalReplaceDelay) obsCcFinalReplaceDelay.value = String(timing.final_replace_delay_ms ?? 0);
    if (obsCcClearAfter) obsCcClearAfter.value = String(timing.clear_after_ms ?? 2500);
    if (obsCcAvoidDuplicates) obsCcAvoidDuplicates.checked = timing.avoid_duplicate_text !== false;
    updateObsCcTimingFieldState();
  }

  function syncObsCcConfigFromControls() {
    if (!window.AppState.config) return;
    window.AppState.config.obs_closed_captions = window.AppState.config.obs_closed_captions || {};
    const obsCc = window.AppState.config.obs_closed_captions;
    obsCc.connection = obsCc.connection || {};
    obsCc.debug_mirror = obsCc.debug_mirror || {};
    obsCc.timing = obsCc.timing || {};
    obsCc.enabled = Boolean(obsCcEnabled?.checked);
    obsCc.output_mode = obsCcOutputMode?.value || "disabled";
    obsCc.connection.host = (obsCcHost?.value || "127.0.0.1").trim() || "127.0.0.1";
    obsCc.connection.port = Math.max(1, Math.min(65535, parseIntegerOr(obsCcPort?.value ?? "4455", 4455)));
    obsCc.connection.password = obsCcPassword?.value || "";
    obsCc.debug_mirror.enabled = Boolean(obsCcDebugEnabled?.checked);
    obsCc.debug_mirror.input_name = (obsCcDebugInputName?.value || "CC_DEBUG").trim() || "CC_DEBUG";
    obsCc.debug_mirror.send_partials = Boolean(obsCcDebugSendPartials?.checked);
    obsCc.timing.send_partials = Boolean(obsCcSendPartials?.checked);
    obsCc.timing.partial_throttle_ms = Math.max(0, parseIntegerOr(obsCcPartialThrottle?.value ?? "250", 250));
    obsCc.timing.min_partial_delta_chars = Math.max(0, parseIntegerOr(obsCcMinPartialDelta?.value ?? "3", 3));
    obsCc.timing.final_replace_delay_ms = Math.max(0, parseIntegerOr(obsCcFinalReplaceDelay?.value ?? "0", 0));
    obsCc.timing.clear_after_ms = Math.max(0, parseIntegerOr(obsCcClearAfter?.value ?? "2500", 2500));
    obsCc.timing.avoid_duplicate_text = Boolean(obsCcAvoidDuplicates?.checked);
    updateObsCcTimingFieldState();
    syncConfigText();
  }

  function clampSimpleLevel(value) {
    return Math.max(1, Math.min(5, parseIntegerOr(value, 3)));
  }

  function getSimpleTuningOption(kind, level) {
    return SIMPLE_TUNING_OPTIONS[kind][clampSimpleLevel(level) - 1];
  }

  function findClosestSimpleLevel(kind, currentValues) {
    const entries = SIMPLE_TUNING_OPTIONS[kind];
    let bestLevel = 3;
    let bestScore = Number.POSITIVE_INFINITY;

    entries.forEach((option, index) => {
      const score = Object.entries(option)
        .filter(([key]) => key !== "label")
        .reduce((sum, [key, value]) => {
          const currentValue = Number(currentValues[key] ?? 0);
          return sum + Math.abs(currentValue - Number(value));
        }, 0);
      if (score < bestScore) {
        bestScore = score;
        bestLevel = index + 1;
      }
    });

    return bestLevel;
  }

  function syncSimpleTuningControlsFromConfig() {
    if (!window.AppState.config) return;
    const realtime = window.AppState.config.asr?.realtime || {};
    const lifecycle = window.AppState.config.subtitle_lifecycle || {};
    const appearanceLevel = findClosestSimpleLevel("appearance", {
      partial_emit_interval_ms: realtime.partial_emit_interval_ms,
      min_speech_ms: realtime.min_speech_ms,
    });
    const finishLevel = findClosestSimpleLevel("finish", {
      silence_hold_ms: realtime.silence_hold_ms,
      pause_to_finalize_ms: lifecycle.pause_to_finalize_ms,
    });
    const stabilityLevel = findClosestSimpleLevel("stability", {
      partial_min_delta_chars: realtime.partial_min_delta_chars,
      partial_coalescing_ms: realtime.partial_coalescing_ms,
    });

    if (simpleAppearanceSpeed) {
      simpleAppearanceSpeed.value = String(appearanceLevel);
    }
    if (simpleAppearanceLabel) {
      const option = getSimpleTuningOption("appearance", appearanceLevel);
      simpleAppearanceLabel.textContent = localizePair(SIMPLE_TUNING_LABELS.appearance, option.label, option.label);
    }
    if (simpleFinishSpeed) {
      simpleFinishSpeed.value = String(finishLevel);
    }
    if (simpleFinishLabel) {
      const option = getSimpleTuningOption("finish", finishLevel);
      simpleFinishLabel.textContent = localizePair(SIMPLE_TUNING_LABELS.finish, option.label, option.label);
    }
    if (simpleStability) {
      simpleStability.value = String(stabilityLevel);
    }
    if (simpleStabilityLabel) {
      const option = getSimpleTuningOption("stability", stabilityLevel);
      simpleStabilityLabel.textContent = localizePair(SIMPLE_TUNING_LABELS.stability, option.label, option.label);
    }
  }

  function syncSimpleTuningConfigFromControls() {
    if (!window.AppState.config) return;
    const realtime = window.AppState.config.asr.realtime;
    const lifecycle = window.AppState.config.subtitle_lifecycle;
    const appearance = getSimpleTuningOption("appearance", simpleAppearanceSpeed?.value ?? 3);
    const finish = getSimpleTuningOption("finish", simpleFinishSpeed?.value ?? 3);
    const stability = getSimpleTuningOption("stability", simpleStability?.value ?? 3);

    realtime.partial_emit_interval_ms = appearance.partial_emit_interval_ms;
    realtime.min_speech_ms = appearance.min_speech_ms;
    realtime.silence_hold_ms = finish.silence_hold_ms;
    lifecycle.pause_to_finalize_ms = finish.pause_to_finalize_ms;
    realtime.finalization_hold_ms = finish.pause_to_finalize_ms;
    realtime.partial_min_delta_chars = stability.partial_min_delta_chars;
    realtime.partial_coalescing_ms = stability.partial_coalescing_ms;

    syncTranslationFormFromConfig();
    syncConfigText();
  }

  function formatRuntimeProgressPercent(value) {
    if (!Number.isFinite(value)) {
      return "...";
    }
    const rounded = Math.round(value);
    return Math.abs(value - rounded) < 0.05 ? `${rounded}%` : `${value.toFixed(1)}%`;
  }

  function getRuntimeProgressDetails(runtime) {
    const status = String(runtime?.status || "").trim().toLowerCase();
    const message = String(runtime?.status_message || "").trim();
    const lowerMessage = message.toLowerCase();
    if (runtime?.last_error) {
      return { show: false };
    }
    if (
      status !== "starting" &&
      (
        lowerMessage.includes("download completed") ||
        lowerMessage.includes("loaded on nvidia gpu") ||
        lowerMessage.includes("loaded on cpu")
      )
    ) {
      return { show: false };
    }
    if (!message && status !== "starting") {
      return { show: false };
    }

    let title = getCurrentLocale() === "ru" ? "Подготовка runtime" : "Runtime Progress";
    if (lowerMessage.includes("downloading parakeet model")) {
      title = getCurrentLocale() === "ru" ? "Загрузка модели" : "Model Download";
    } else if (lowerMessage.includes("parakeet model")) {
      title = getCurrentLocale() === "ru" ? "Инициализация модели" : "Model Loading";
    } else if (lowerMessage.includes("browser speech worker")) {
      title = getCurrentLocale() === "ru" ? "Запуск browser speech" : "Browser Speech";
    }

    let percent = null;
    const percentMatch = message.match(/(\d+(?:\.\d+)?)%/);
    if (percentMatch) {
      const parsed = Number.parseFloat(percentMatch[1]);
      if (Number.isFinite(parsed)) {
        percent = Math.min(100, Math.max(0, parsed));
      }
    }
    if (!Number.isFinite(percent)) {
      if (lowerMessage.includes("preparing the first local parakeet model download")) {
        percent = 3;
      } else if (lowerMessage.includes("preparing browser speech worker")) {
        percent = 14;
      } else if (
        lowerMessage.includes("preparing local runtime") ||
        lowerMessage.includes("preparing asr runtime")
      ) {
        percent = 8;
      } else if (lowerMessage.includes("finalizing local parakeet model files")) {
        percent = 97;
      } else if (lowerMessage.includes("loading parakeet model")) {
        percent = 99;
      } else if (status === "starting") {
        percent = 12;
      }
    }

    const show =
      status === "starting" ||
      lowerMessage.includes("parakeet model") ||
      lowerMessage.includes("browser speech worker");

    return {
      show,
      title,
      text: message || (getCurrentLocale() === "ru" ? "Подготавливается локальный runtime..." : "Preparing local runtime..."),
      percent,
      fillWidth: `${Number.isFinite(percent) ? percent : 12}%`,
      percentLabel: formatRuntimeProgressPercent(percent),
    };
  }

  function setRuntime(runtime) {
    runtime = runtime || { status: "idle", is_running: false, status_message: "", last_error: null };
    window.AppState.runtime = runtime;
    const isStarting = runtime?.status === "starting";
    const isRunning = Boolean(runtime?.is_running);
    const runtimeSignature = JSON.stringify([
      runtime?.status || "",
      runtime?.last_error || "",
      runtime?.status_message || "",
    ]);
    if (window.AppState.runtimeLogSignature !== runtimeSignature) {
      window.AppState.runtimeLogSignature = runtimeSignature;
      if (runtime?.last_error) {
        log(`[runtime] ${normalizeExternalMessage(runtime.last_error)}`);
      } else if (runtime?.status_message) {
        log(`[runtime] ${runtime.status_message}`);
      }
    }
    if (runtimeBadge) {
      const suffix = runtime.last_error
        ? ` (${normalizeExternalMessage(runtime.last_error)})`
        : runtime.status_message
          ? ` (${runtime.status_message})`
          : "";
      runtimeBadge.textContent = t("runtime.badge.runtime", { value: `${runtime.status}${suffix}` });
    }
    if (runtimeProgressCard && runtimeProgressTitle && runtimeProgressPercent && runtimeProgressText && runtimeProgressFill) {
      const progress = getRuntimeProgressDetails(runtime);
      runtimeProgressCard.hidden = !progress.show;
      if (progress.show) {
        runtimeProgressTitle.textContent = progress.title;
        runtimeProgressPercent.textContent = progress.percentLabel;
        runtimeProgressText.textContent = progress.text;
        runtimeProgressFill.style.width = progress.fillWidth;
      } else {
        runtimeProgressPercent.textContent = "0%";
        runtimeProgressText.textContent = getCurrentLocale() === "ru"
          ? "Подготавливается локальный runtime..."
          : "Preparing local runtime...";
        runtimeProgressFill.style.width = "0%";
      }
    }
    if (startBtn) {
      startBtn.disabled = isRunning || isStarting;
      startBtn.textContent = isStarting ? t("common.starting") : t("common.start");
    }
    if (stopBtn) {
      stopBtn.disabled = !isRunning || isStarting;
    }
    runtimeStatePills.forEach((pill) => {
      pill.classList.toggle("active", pill.dataset.state === runtime.status);
    });
    renderDiagnostics(
      runtime.asr_diagnostics || null,
      runtime.translation_diagnostics || null,
      runtime.metrics || null,
      runtime.obs_caption_diagnostics || null
    );
    updateRecognitionModeUi();
  }

  function formatMetric(value) {
    return typeof value === "number" ? `${value.toFixed(1)} ms` : "n/a";
  }

  function renderDiagnostics(diagnostics, translationDiagnostics, metrics, obsCaptionDiagnostics) {
    if (asrProviderBadge) {
      asrProviderBadge.textContent = t("runtime.badge.asr", { value: diagnostics?.provider || t("common.unknown").toLowerCase() });
    }
    if (asrDeviceBadge) {
      const device = diagnostics?.selected_device || diagnostics?.selected_execution_provider || "unknown";
      asrDeviceBadge.textContent = t("runtime.badge.device", { value: device });
    }
    if (asrPartialsBadge) {
      asrPartialsBadge.textContent = t("runtime.badge.partials", {
        value: diagnostics?.partials_supported
          ? (getCurrentLocale() === "ru" ? "вкл" : "on")
          : (getCurrentLocale() === "ru" ? "выкл" : "off"),
      });
    }
    if (asrModeBadge) {
      let modeLabel = getCurrentLocale() === "ru" ? "неизвестно" : "unknown";
      if (diagnostics?.provider === "browser_google") {
        modeLabel = getCurrentLocale() === "ru" ? "браузерный speech worker" : "browser speech worker";
      } else if (!diagnostics?.torch_built_with_cuda && diagnostics?.requested_device_policy === "gpu_preferred") {
        modeLabel = getCurrentLocale() === "ru" ? "обнаружен только CPU-вариант torch" : "CPU-only torch detected";
      } else if (diagnostics?.provider === "official_eu_parakeet_realtime" && diagnostics?.selected_device === "cuda" && !diagnostics?.degraded_mode) {
        modeLabel = getCurrentLocale() === "ru" ? "realtime GPU активен" : "realtime GPU active";
      } else if (diagnostics?.provider === "official_eu_parakeet_realtime" && diagnostics?.selected_device === "cpu") {
        modeLabel = getCurrentLocale() === "ru" ? "realtime CPU fallback" : "realtime CPU fallback";
      } else if (diagnostics?.provider === "official_eu_parakeet" && diagnostics?.requested_provider !== "official_eu_parakeet") {
        modeLabel = getCurrentLocale() === "ru" ? "активен baseline fallback" : "baseline fallback active";
      } else if (diagnostics?.provider === "official_eu_parakeet") {
        modeLabel = getCurrentLocale() === "ru" ? "базовая совместимость" : "baseline compatibility";
      }
      asrModeBadge.textContent = t("runtime.badge.mode", { value: modeLabel });
    }
    if (translationStatusBadge) {
      let label = getCurrentLocale() === "ru" ? "неизвестно" : "unknown";
      if (translationDiagnostics?.status === "disabled") {
        label = getCurrentLocale() === "ru" ? "выключен" : "disabled";
      } else if (translationDiagnostics?.status === "ready") {
        label = getCurrentLocale() === "ru" ? "готов" : "ready";
      } else if (translationDiagnostics?.status === "partial") {
        label = getCurrentLocale() === "ru" ? "частично готов" : "partial";
      } else if (translationDiagnostics?.status === "experimental") {
        label = getCurrentLocale() === "ru" ? "экспериментально" : "experimental";
      } else if (translationDiagnostics?.status === "degraded") {
        label = getCurrentLocale() === "ru" ? "в degraded-режиме" : "degraded";
      } else if (translationDiagnostics?.status === "error") {
        label = getCurrentLocale() === "ru" ? "ошибка" : "error";
      }
      translationStatusBadge.textContent = t("runtime.badge.translation", { value: label });
    }
    if (obsCcBadge) {
      let label = getCurrentLocale() === "ru" ? "выключено" : "disabled";
      if (obsCaptionDiagnostics?.enabled && obsCaptionDiagnostics?.output_mode !== "disabled") {
        if (obsCaptionDiagnostics?.connection_state === "connected") {
          label = obsCaptionDiagnostics.output_mode;
        } else if (obsCaptionDiagnostics?.connection_state === "connecting") {
          label = getCurrentLocale() === "ru" ? "подключение" : "connecting";
        } else if (obsCaptionDiagnostics?.connection_state === "auth_failed") {
          label = getCurrentLocale() === "ru" ? "ошибка авторизации" : "auth failed";
        } else if (obsCaptionDiagnostics?.connection_state === "error") {
          label = getCurrentLocale() === "ru" ? "ошибка" : "error";
        } else {
          label = getCurrentLocale() === "ru" ? "отключено" : "disconnected";
        }
      }
      obsCcBadge.textContent = t("runtime.badge.obs_cc", { value: label });
    }
    if (asrDiagnosticsText) {
      const parts = [
        `requested provider: ${diagnostics?.requested_provider || "n/a"}`,
        `requested device policy: ${diagnostics?.requested_device_policy || "n/a"}`,
        `model: ${diagnostics?.model_path || "n/a"}`,
        `torch: ${diagnostics?.torch_version || "n/a"}`,
        `torch cuda build: ${diagnostics?.torch_built_with_cuda ? diagnostics?.torch_cuda_version || "yes" : "no"}`,
        `torch cuda available: ${diagnostics?.torch_cuda_is_available ? "yes" : "no"}`,
        `gpu count: ${diagnostics?.torch_device_count ?? 0}`,
        `gpu0: ${diagnostics?.first_gpu_name || "n/a"}`,
        `gpu requested: ${diagnostics?.gpu_requested ? "yes" : "no"}`,
        `gpu available: ${diagnostics?.gpu_available ? "yes" : "no"}`,
        `degraded: ${diagnostics?.degraded_mode ? "yes" : "no"}`,
        `provider: ${diagnostics?.selected_execution_provider || "n/a"}`,
        `python: ${diagnostics?.python_executable || "n/a"}`,
        `venv: ${diagnostics?.venv_path || "n/a"}`,
        `vad mode: ${diagnostics?.vad_mode ?? "n/a"}`,
        `frame: ${diagnostics?.audio_frame_duration_ms ?? "n/a"} ms`,
        `partial interval: ${diagnostics?.vad_partial_interval_ms ?? "n/a"} ms`,
        `min speech: ${diagnostics?.vad_min_speech_ms ?? "n/a"} ms`,
        `first partial: ${diagnostics?.vad_first_partial_min_speech_ms ?? "n/a"} ms`,
        `silence hold: ${diagnostics?.vad_silence_padding_ms ?? "n/a"} ms`,
        `final hold: ${diagnostics?.vad_finalization_hold_ms ?? "n/a"} ms`,
        `max segment: ${diagnostics?.vad_max_segment_ms ?? "n/a"} ms`,
        `quiet gate: ${diagnostics?.vad_energy_gate_enabled ? "yes" : "no"}`,
        `min rms: ${diagnostics?.vad_min_rms_for_recognition ?? "n/a"}`,
        `min voiced ratio: ${diagnostics?.vad_min_voiced_ratio ?? "n/a"}`,
        `chunk window: ${diagnostics?.realtime_chunk_window_ms ?? "n/a"} ms`,
        `chunk overlap: ${diagnostics?.realtime_chunk_overlap_ms ?? "n/a"} ms`,
        `min delta chars: ${diagnostics?.partial_min_delta_chars ?? "n/a"}`,
        `partial coalescing: ${diagnostics?.partial_coalescing_ms ?? "n/a"} ms`,
        `rnnoise enabled: ${diagnostics?.recognition_noise_reduction_enabled ? "yes" : "no"}`,
        `rnnoise strength: ${diagnostics?.rnnoise_strength ?? 0}%`,
        `rnnoise available: ${diagnostics?.rnnoise_available ? "yes" : "no"}`,
        `rnnoise active: ${diagnostics?.rnnoise_active ? "yes" : "no"}`,
        `rnnoise backend: ${diagnostics?.rnnoise_backend || "n/a"}`,
        `rnnoise resample: ${diagnostics?.rnnoise_uses_resample ? "yes" : "no"}`,
        `rnnoise input rate: ${diagnostics?.rnnoise_input_sample_rate ?? "n/a"} Hz`,
        `rnnoise proc rate: ${diagnostics?.rnnoise_processing_sample_rate ?? "n/a"} Hz`,
        `rnnoise frame: ${diagnostics?.rnnoise_frame_size_samples ?? "n/a"} samples`,
      ];
      if (diagnostics?.fallback_reason) {
        parts.push(`fallback: ${diagnostics.fallback_reason}`);
      }
      if (diagnostics?.cpu_fallback_reason) {
        parts.push(`cpu fallback: ${diagnostics.cpu_fallback_reason}`);
      }
      if (diagnostics?.rnnoise_message) {
        parts.push(`rnnoise: ${diagnostics.rnnoise_message}`);
      }
      if (diagnostics?.message) {
        parts.push(`note: ${diagnostics.message}`);
      }
      asrDiagnosticsText.textContent = parts.join(" | ");
    }
    if (translationDiagnosticsText) {
      const parts = [
        `provider: ${translationDiagnostics?.provider || "none"}`,
        `status: ${translationDiagnostics?.status || "unknown"}`,
        `configured: ${translationDiagnostics?.configured ? "yes" : "no"}`,
        `ready: ${translationDiagnostics?.ready ? "yes" : "no"}`,
        `degraded: ${translationDiagnostics?.degraded ? "yes" : "no"}`,
        `targets: ${(translationDiagnostics?.target_languages || []).join(", ") || "none"}`,
      ];
      if (translationDiagnostics?.provider_group) {
        parts.push(`group: ${translationDiagnostics.provider_group}`);
      }
      if (translationDiagnostics?.experimental) {
        parts.push("experimental provider");
      }
      if (translationDiagnostics?.local_provider) {
        parts.push("local provider");
      }
      if (translationDiagnostics?.provider_endpoint) {
        parts.push(`endpoint: ${translationDiagnostics.provider_endpoint}`);
      }
      if (translationDiagnostics?.reason) {
        parts.push(`note: ${translationDiagnostics.reason}`);
      } else if (translationDiagnostics?.summary) {
        parts.push(`summary: ${translationDiagnostics.summary}`);
      }
      translationDiagnosticsText.textContent = parts.join(" | ");
    }
    if (obsCcDiagnosticsText) {
      const parts = [
        `enabled: ${obsCaptionDiagnostics?.enabled ? "yes" : "no"}`,
        `mode: ${obsCaptionDiagnostics?.output_mode || "disabled"}`,
        `endpoint: ${obsCaptionDiagnostics?.host || "127.0.0.1"}:${obsCaptionDiagnostics?.port ?? 4455}`,
        `state: ${obsCaptionDiagnostics?.connection_state || "disabled"}`,
        `connected: ${obsCaptionDiagnostics?.connected ? "yes" : "no"}`,
        `stream active: ${
          obsCaptionDiagnostics?.stream_output_active === true
            ? "yes"
            : obsCaptionDiagnostics?.stream_output_active === false
            ? "no"
            : "unknown"
        }`,
        `stream reconnecting: ${
          obsCaptionDiagnostics?.stream_output_reconnecting === true
            ? "yes"
            : obsCaptionDiagnostics?.stream_output_reconnecting === false
            ? "no"
            : "unknown"
        }`,
        `native ready: ${obsCaptionDiagnostics?.native_caption_ready ? "yes" : "no"}`,
        `password: ${obsCaptionDiagnostics?.password_configured ? "set" : "empty"}`,
        `debug mirror: ${obsCaptionDiagnostics?.debug_text_input_enabled ? "on" : "off"}`,
        `partials: ${obsCaptionDiagnostics?.send_partials ? "on" : "off"}`,
        `throttle: ${obsCaptionDiagnostics?.partial_throttle_ms ?? 250} ms`,
        `min delta: ${obsCaptionDiagnostics?.min_partial_delta_chars ?? 3}`,
        `final delay: ${obsCaptionDiagnostics?.final_replace_delay_ms ?? 0} ms`,
        `clear after: ${obsCaptionDiagnostics?.clear_after_ms ?? 2500} ms`,
        `retries: ${obsCaptionDiagnostics?.reconnect_attempt_count ?? 0}`,
        `last send reused: ${obsCaptionDiagnostics?.last_send_used_active_connection ? "yes" : "no"}`,
        `last send waited: ${obsCaptionDiagnostics?.last_send_waited_for_connection ? "yes" : "no"}`,
      ];
      if (obsCaptionDiagnostics?.obs_websocket_version) {
        parts.push(`ws: ${obsCaptionDiagnostics.obs_websocket_version}`);
      }
      if (obsCaptionDiagnostics?.obs_studio_version) {
        parts.push(`obs: ${obsCaptionDiagnostics.obs_studio_version}`);
      }
      if (obsCaptionDiagnostics?.debug_text_input_name) {
        parts.push(`debug input: ${obsCaptionDiagnostics.debug_text_input_name}`);
      }
      if (obsCaptionDiagnostics?.debug_text_input_enabled) {
        parts.push(`debug partials: ${obsCaptionDiagnostics?.debug_text_input_send_partials ? "on" : "off"}`);
      }
      if (obsCaptionDiagnostics?.last_error) {
        parts.push(`error: ${normalizeExternalMessage(obsCaptionDiagnostics.last_error)}`);
      } else if (obsCaptionDiagnostics?.native_caption_status) {
        parts.push(`native: ${normalizeExternalMessage(obsCaptionDiagnostics.native_caption_status)}`);
      } else if (obsCaptionDiagnostics?.last_debug_text) {
        parts.push(`debug last: ${String(obsCaptionDiagnostics.last_debug_text).replaceAll("\n", " / ")}`);
      } else if (obsCaptionDiagnostics?.last_caption_text) {
        parts.push(`last: ${String(obsCaptionDiagnostics.last_caption_text).replaceAll("\n", " / ")}`);
      }
      obsCcDiagnosticsText.textContent = parts.join(" | ");
    }
    if (obsCcStatusText) {
      const nativeCaptionEnabled = Boolean(obsCaptionDiagnostics?.enabled) && obsCaptionDiagnostics?.output_mode !== "disabled";
      const nativeCaptionReady = Boolean(obsCaptionDiagnostics?.native_caption_ready);
      const streamOutputActive = obsCaptionDiagnostics?.stream_output_active;
      const streamOutputReconnecting = obsCaptionDiagnostics?.stream_output_reconnecting;
      const nativeCaptionStatus = normalizeExternalMessage(obsCaptionDiagnostics?.native_caption_status);
      const debugMirrorEnabled = Boolean(obsCaptionDiagnostics?.debug_text_input_enabled);
      const debugInputName = obsCaptionDiagnostics?.debug_text_input_name || "CC_DEBUG";
      if (!nativeCaptionEnabled && !debugMirrorEnabled) {
        obsCcStatusText.textContent = getCurrentLocale() === "ru"
          ? "OBS Closed Captions выключены. На browser overlay это не влияет."
          : "OBS Closed Captions are disabled. The browser overlay remains unchanged.";
      } else if (obsCaptionDiagnostics?.connection_state === "connected" && streamOutputActive === false) {
        obsCcStatusText.textContent = debugMirrorEnabled
          ? (getCurrentLocale() === "ru"
              ? `OBS websocket подключён, но stream output не активен. Нативный SendStreamCaption сейчас не дойдёт до зрителя, хотя debug text source (${debugInputName}) всё ещё может обновляться.`
              : `Connected to OBS websocket, but the stream output is not active. Native SendStreamCaption will not reach viewers right now, although the ${debugInputName} debug text source can still update.`)
          : (getCurrentLocale() === "ru"
              ? "OBS websocket подключён, но OBS сейчас не стримит. Native SendStreamCaption работает только во время активного stream output."
              : "Connected to OBS websocket, but OBS is not actively streaming. Native SendStreamCaption only works during an active stream output.");
      } else if (obsCaptionDiagnostics?.connection_state === "connected" && nativeCaptionReady) {
        if (nativeCaptionEnabled && debugMirrorEnabled && streamOutputReconnecting) {
          obsCcStatusText.textContent = getCurrentLocale() === "ru"
            ? `OBS websocket подключён, stream output активен, но сейчас переподключается. Native captions могут быть нестабильны; debug text source ${debugInputName} остаётся доступен.`
            : `Connected to OBS websocket and the stream output is active, but it is currently reconnecting. Native captions may be unstable; the ${debugInputName} debug text source remains available.`;
        } else if (nativeCaptionEnabled && debugMirrorEnabled) {
          obsCcStatusText.textContent = getCurrentLocale() === "ru"
            ? `OBS websocket подключён, stream output активен. Финалы будут отправляться и в нативные captions (${obsCaptionDiagnostics.output_mode}), и в debug text source ${debugInputName}; partial можно зеркалить туда отдельно.`
            : `Connected to OBS websocket and the stream output is active. Finals will go to native ${obsCaptionDiagnostics.output_mode} captions and to the ${debugInputName} debug text source; partials can mirror there separately.`;
        } else if (debugMirrorEnabled) {
          obsCcStatusText.textContent = getCurrentLocale() === "ru"
            ? `OBS websocket подключён и готов зеркалить текст субтитров в debug text source ${debugInputName}.`
            : `Connected to OBS websocket and ready to mirror subtitle text into the ${debugInputName} debug text source.`;
        } else {
          obsCcStatusText.textContent = getCurrentLocale() === "ru"
            ? `OBS websocket подключён, stream output активен, native captions могут отправляться в режиме ${obsCaptionDiagnostics.output_mode}.`
            : `Connected to OBS websocket, the stream output is active, and native ${obsCaptionDiagnostics.output_mode} captions can be sent.`;
        }
      } else if (obsCaptionDiagnostics?.connection_state === "connected" && nativeCaptionEnabled) {
        obsCcStatusText.textContent = debugMirrorEnabled
          ? (getCurrentLocale() === "ru"
              ? `OBS websocket подключён, но готовность native captions ещё не подтверждена. ${nativeCaptionStatus || `Debug text source ${debugInputName} при этом может обновляться.`}`
              : `Connected to OBS websocket, but native caption readiness is not confirmed yet. ${nativeCaptionStatus || `The ${debugInputName} debug text source can still update.`}`)
          : (getCurrentLocale() === "ru"
              ? `OBS websocket подключён, но готовность native captions ещё не подтверждена. ${nativeCaptionStatus || "Нужен активный stream output и поддержка платформы/плеера."}`
              : `Connected to OBS websocket, but native caption readiness is not confirmed yet. ${nativeCaptionStatus || "An active stream output and downstream player/platform support are still required."}`);
      } else if (obsCaptionDiagnostics?.connection_state === "connecting") {
        obsCcStatusText.textContent = getCurrentLocale() === "ru"
          ? "Вывод captions в OBS включён и сейчас фоново подключается к OBS websocket."
          : "OBS caption output is enabled and connecting to OBS websocket in the background.";
      } else if (obsCaptionDiagnostics?.connection_state === "auth_failed") {
        obsCcStatusText.textContent = getCurrentLocale() === "ru"
          ? `Не удалось авторизоваться в OBS websocket: ${normalizeExternalMessage(obsCaptionDiagnostics?.last_error) || "проверьте пароль."}`
          : `OBS captions could not authenticate with OBS websocket: ${normalizeExternalMessage(obsCaptionDiagnostics?.last_error) || "check the configured password."}`;
      } else if (obsCaptionDiagnostics?.last_error) {
        obsCcStatusText.textContent = getCurrentLocale() === "ru"
          ? `OBS captions включены, но не подключены: ${normalizeExternalMessage(obsCaptionDiagnostics.last_error)}`
          : `OBS captions are enabled but not connected: ${normalizeExternalMessage(obsCaptionDiagnostics.last_error)}`;
      } else {
        obsCcStatusText.textContent = getCurrentLocale() === "ru"
          ? "OBS captions включены и ждут постоянное подключение к OBS websocket."
          : "OBS captions are enabled and waiting for the persistent OBS websocket connection.";
      }
    }
    if (latencyMetricsText) {
      latencyMetricsText.textContent = [
        `vad ${formatMetric(metrics?.vad_ms)}`,
        `asr partial ${formatMetric(metrics?.asr_partial_ms)}`,
        `asr final ${formatMetric(metrics?.asr_final_ms)}`,
        `translation ${formatMetric(metrics?.translation_ms)}`,
        `total ${formatMetric(metrics?.total_ms)}`,
        `partials ${metrics?.partial_updates_emitted ?? 0}`,
        `finals ${metrics?.finals_emitted ?? 0}`,
        `suppressed ${metrics?.suppressed_partial_updates ?? 0}`,
        `vad dropped ${metrics?.vad_dropped_segments ?? 0}`,
      ].join(" | ");
    }
  }

  function renderTranscript() {
    if (partialTranscript) {
      partialTranscript.textContent = window.AppState.transcript.partial || (getCurrentLocale() === "ru" ? "Ожидание речи..." : "Waiting for speech...");
    }
    if (finalTranscript) {
      finalTranscript.textContent =
        window.AppState.transcript.finals.length > 0
          ? window.AppState.transcript.finals.join("\n")
          : (getCurrentLocale() === "ru" ? "Пока нет завершённого текста." : "No final transcript yet.");
    }
  }

  function renderTranslationResults() {
    if (!translationResults) return;
    if (!window.AppState.currentTranslationEntry) {
      translationResults.innerHTML = `<p class="muted">${escapeHtml(getCurrentLocale() === "ru" ? "Пока нет переведённых результатов." : "No translated results yet.")}</p>`;
      return;
    }

    const entry = window.AppState.currentTranslationEntry;
    const translationsHtml = entry.translations.length
      ? entry.translations
          .map((item) => {
            const meta = `${getLanguageLabel(item.target_lang)}${item.cached ? " (cached)" : ""}`;
            const content = item.success
              ? escapeHtml(item.text)
              : `<span class="translation-error">${escapeHtml(item.error || (getCurrentLocale() === "ru" ? "Ошибка перевода." : "Translation failed."))}</span>`;
            return `
              <p class="label">${escapeHtml(meta)}</p>
              <p>${content}</p>
            `;
          })
          .join("")
      : `<p class="muted">${escapeHtml(getCurrentLocale() === "ru" ? "Перевод выключен или не настроены целевые языки." : "Translation disabled or no target languages configured.")}</p>`;
    const providerMeta = entry.providerLabel ? `<p class="label">${escapeHtml(entry.providerLabel)}</p>` : "";
    const statusMeta = entry.statusMessage ? `<p class="muted">${escapeHtml(entry.statusMessage)}</p>` : "";
    translationResults.innerHTML = `
      <div class="translation-card">
        <h3>${escapeHtml(getCurrentLocale() === "ru" ? `Сегмент ${entry.sequence}` : `Segment ${entry.sequence}`)}</h3>
        <p class="label">${escapeHtml(t("common.source"))}</p>
        <p>${escapeHtml(entry.sourceText)}</p>
        ${providerMeta}
        ${statusMeta}
        ${translationsHtml}
      </div>
    `;
  }

  function renderTranslationProviderOptions() {
    if (!translationProvider) return;
    const groups = {};
    Object.entries(PROVIDERS).forEach(([providerName, provider]) => {
      const localized = getProviderMeta(providerName) || provider;
      groups[localized.group] = groups[localized.group] || [];
      groups[localized.group].push({ providerName, provider: localized });
    });

    translationProvider.innerHTML = Object.entries(groups)
      .map(([groupLabel, entries]) => {
        const options = entries
          .map(({ providerName, provider }) => `<option value="${providerName}">${provider.label}</option>`)
          .join("");
        return `<optgroup label="${groupLabel}">${options}</optgroup>`;
      })
      .join("");
  }

  function renderTranslationLanguageOptions() {
    if (!translationLanguageSelect) return;
    translationLanguageSelect.innerHTML = LANGUAGES.map(
      (item) => `<option value="${item.code}">${item.label}</option>`
    ).join("");
  }

  function renderTranslationOrder() {
    if (!translationLanguageOrder || !window.AppState.config) return;
    const items = window.AppState.config.translation.target_languages;
    translationLanguageOrder.innerHTML = "";
    items.forEach((code) => {
      const li = document.createElement("li");
      li.textContent = `${getLanguageLabel(code)} (${code})`;
      li.dataset.code = code;
      li.classList.toggle("active", code === window.AppState.selectedTranslationLanguage);
      li.addEventListener("click", () => {
        window.AppState.selectedTranslationLanguage = code;
        renderTranslationOrder();
      });
      translationLanguageOrder.appendChild(li);
    });
  }

  function getDisplayOrderLabel(code) {
    return code === "source" ? t("common.source") : `${getLanguageLabel(code)} (${code})`;
  }

  function renderSubtitleDisplayOrder() {
    if (!subtitleDisplayOrder || !window.AppState.config) return;
    const items = window.AppState.config.subtitle_output.display_order;
    subtitleDisplayOrder.innerHTML = "";
    items.forEach((code) => {
      const li = document.createElement("li");
      li.textContent = getDisplayOrderLabel(code);
      li.dataset.code = code;
      li.classList.toggle("active", code === window.AppState.selectedSubtitleOrderItem);
      li.addEventListener("click", () => {
        window.AppState.selectedSubtitleOrderItem = code;
        renderSubtitleDisplayOrder();
      });
      subtitleDisplayOrder.appendChild(li);
    });
  }

  function setSubtitleStylePresets(presets) {
    window.AppState.subtitleStylePresets = presets && typeof presets === "object" ? presets : {};
    renderSubtitleStylePresetOptions();
  }

  function setFontCatalog(fontCatalog) {
    window.AppState.fontCatalog = {
      project_local: Array.isArray(fontCatalog?.project_local) ? fontCatalog.project_local : [],
      fallback: Array.isArray(fontCatalog?.fallback) ? fontCatalog.fallback : [],
      system: Array.isArray(fontCatalog?.system) ? fontCatalog.system : [],
      project_fonts_dir: fontCatalog?.project_fonts_dir || "",
    };
    syncFontCatalogUi();
  }

  function getAvailableFontCatalog() {
    return {
      project_local: window.AppState.fontCatalog?.project_local || [],
      system: window.AppState.fontCatalog?.system || [],
      fallback: window.AppState.fontCatalog?.fallback || [],
    };
  }

  function getSelectedStyleLineSlot() {
    return window.AppState.selectedStyleLineSlot || "source";
  }

  function getLineSlotLabel(slotName) {
    if (slotName === "source") {
      return t("common.source");
    }
    return getCurrentLocale() === "ru"
      ? slotName.replace("translation_", "Перевод ")
      : slotName.replace("translation_", "Translation ");
  }

  function getLineSlotDescription(slotName) {
    if (slotName === "source") {
      return getCurrentLocale() === "ru"
        ? "Переопределяет стиль исходной строки, когда показывается оригинальный текст."
        : "Overrides the source line when source text is visible.";
    }
    const ordinal = slotName.replace("translation_", "");
    return getCurrentLocale() === "ru"
      ? `Переопределяет стиль видимой строки перевода ${ordinal}. Скрытые или отсутствующие переводы не занимают более ранние слоты.`
      : `Overrides visible translated line ${ordinal}. Hidden or missing translations do not consume earlier slots.`;
  }

  function slugifyCustomPresetName(rawValue) {
    return String(rawValue || "")
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "");
  }

  function normalizeCustomPresetKey(rawValue) {
    const slug = slugifyCustomPresetName(rawValue);
    return slug ? `custom_${slug}` : "";
  }

  function collectCurrentStyleFontFamilies() {
    const families = new Set();
    const style = normalizeSubtitleStyleConfig(window.AppState.config?.subtitle_style || {});
    if (style.base?.font_family) {
      families.add(style.base.font_family);
    }
    Object.values(style.line_slots || {}).forEach((slotStyle) => {
      if (slotStyle?.font_family) {
        families.add(slotStyle.font_family);
      }
    });
    return [...families];
  }

  function mergeFontEntriesWithCurrentValues() {
    const sections = getAvailableFontCatalog();
    const deduped = new Map();
    const pushEntries = (entries) => {
      entries.forEach((entry) => {
        if (!entry?.family) return;
        if (!deduped.has(entry.family)) {
          deduped.set(entry.family, {
            id: entry.id || entry.family,
            label: entry.label || entry.family,
            family: entry.family,
            source: entry.source || "fallback",
          });
        }
      });
    };
    pushEntries(sections.project_local || []);
    pushEntries(sections.system || []);
    pushEntries(sections.fallback || []);
    collectCurrentStyleFontFamilies().forEach((family) => {
      if (!deduped.has(family)) {
        deduped.set(family, {
          id: `current-${family}`,
          label: family.replace(/"/g, ""),
          family,
          source: "current",
        });
      }
    });
    return [...deduped.values()];
  }

  function renderFontPicker(selectElement, selectedValue) {
    if (!selectElement) return;
    const entries = mergeFontEntriesWithCurrentValues();
    const groups = {
      project_local: [],
      system: [],
      fallback: [],
      current: [],
    };
    entries.forEach((entry) => {
      groups[entry.source] = groups[entry.source] || [];
      groups[entry.source].push(entry);
    });
    const labels = {
      project_local: getCurrentLocale() === "ru" ? "Шрифты проекта" : "Project-local fonts",
      system: getCurrentLocale() === "ru" ? "Системные шрифты (best-effort)" : "System fonts (best-effort)",
      fallback: getCurrentLocale() === "ru" ? "Встроенные резервные шрифты" : "Built-in fallback fonts",
      current: getCurrentLocale() === "ru" ? "Сохранённое сейчас" : "Currently saved",
    };
    selectElement.innerHTML = Object.entries(groups)
      .filter(([, items]) => Array.isArray(items) && items.length)
      .map(([groupName, items]) => {
        const options = items
          .sort((left, right) => left.label.localeCompare(right.label))
          .map(
            (entry) =>
              `<option value="${escapeHtml(entry.family)}">${escapeHtml(entry.label)}</option>`
          )
          .join("");
        return `<optgroup label="${labels[groupName] || groupName}">${options}</optgroup>`;
      })
      .join("");
    if (selectedValue) {
      selectElement.value = selectedValue;
    }
    if (selectElement.value !== selectedValue && selectedValue) {
      const option = document.createElement("option");
      option.value = selectedValue;
      option.textContent = selectedValue.replace(/"/g, "");
      selectElement.appendChild(option);
      selectElement.value = selectedValue;
    }
  }

  function syncFontCatalogUi() {
    if (projectFontsDir) {
      projectFontsDir.textContent = window.AppState.fontCatalog?.project_fonts_dir || "fonts";
    }
    if (fontSourceStatus) {
      const projectCount = window.AppState.fontCatalog?.project_local?.length || 0;
      const systemCount = window.AppState.fontCatalog?.system?.length || 0;
      fontSourceStatus.textContent = getCurrentLocale() === "ru"
        ? `Шрифтов проекта: ${projectCount}. Системных шрифтов загружено: ${systemCount}. Резервные шрифты доступны даже если системный доступ не поддерживается или запрещён.`
        : `Project-local fonts: ${projectCount}. System fonts loaded: ${systemCount}. Fallback fonts stay available even if system access is unsupported or denied.`;
    }
    renderFontPicker(styleFontFamily, styleFontFamily?.value || window.AppState.config?.subtitle_style?.base?.font_family || "");
    renderFontPicker(
      styleLineSlotFontFamily,
      styleLineSlotFontFamily?.value ||
        window.AppState.config?.subtitle_style?.line_slots?.[getSelectedStyleLineSlot()]?.font_family ||
        window.AppState.config?.subtitle_style?.base?.font_family ||
        ""
    );
  }

  async function refreshSystemFonts() {
    if (fontRefreshBtn) {
      fontRefreshBtn.disabled = true;
      fontRefreshBtn.textContent = getCurrentLocale() === "ru" ? "Обновление..." : "Refreshing...";
    }
    try {
      if (typeof window.queryLocalFonts !== "function") {
        if (fontSourceStatus) {
          fontSourceStatus.textContent = getCurrentLocale() === "ru"
            ? "В этом окружении браузер не умеет перечислять системные шрифты. Шрифты проекта и резервные шрифты всё равно доступны."
            : "Browser system font enumeration is unavailable here. Project-local fonts and fallback fonts remain available.";
        }
        return;
      }
      const localFonts = await window.queryLocalFonts();
      const seen = new Set();
      const systemFonts = [];
      localFonts.forEach((font) => {
        const family = String(font.family || "").trim();
        if (!family || seen.has(family)) return;
        seen.add(family);
        systemFonts.push({
          id: `system-${family.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`,
          label: family,
          family: `"${family}"`,
          source: "system",
        });
      });
      window.AppState.fontCatalog.system = systemFonts.sort((left, right) => left.label.localeCompare(right.label));
      syncFontCatalogUi();
    } catch (_error) {
      if (fontSourceStatus) {
        fontSourceStatus.textContent = getCurrentLocale() === "ru"
          ? "Доступ к системным шрифтам недоступен или запрещён. Шрифты проекта и резервные шрифты всё равно доступны."
          : "System font access was unavailable or denied. Project-local fonts and fallback fonts remain available.";
      }
    } finally {
      if (fontRefreshBtn) {
        fontRefreshBtn.disabled = false;
        fontRefreshBtn.textContent = t("style.fonts.refresh");
      }
    }
  }

  function renderSubtitleStylePresetOptions() {
    if (!subtitleStylePreset) return;
    const presets = getStylePresetCatalog();
    const entries = Object.entries(presets);
    const builtInEntries = entries.filter(([, preset]) => preset?.built_in !== false);
    const customEntries = entries.filter(([, preset]) => preset?.built_in === false);
    subtitleStylePreset.innerHTML = "";
    if (!entries.length) {
      subtitleStylePreset.innerHTML = '<option value="clean_default">Clean Default</option>';
      return;
    }
    if (builtInEntries.length) {
      const optgroup = document.createElement("optgroup");
      optgroup.label = getCurrentLocale() === "ru" ? "Встроенные" : "Built-in";
      builtInEntries.forEach(([presetName, preset]) => {
        const localizedPreset = getLocalizedStylePresetMeta(presetName, preset) || preset;
        const option = document.createElement("option");
        option.value = presetName;
        option.textContent = localizedPreset.label || presetName;
        optgroup.appendChild(option);
      });
      subtitleStylePreset.appendChild(optgroup);
    }
    if (customEntries.length) {
      const optgroup = document.createElement("optgroup");
      optgroup.label = getCurrentLocale() === "ru" ? "Пользовательские" : "Custom";
      customEntries.forEach(([presetName, preset]) => {
        const option = document.createElement("option");
        option.value = presetName;
        option.textContent = preset.label || presetName;
        optgroup.appendChild(option);
      });
      subtitleStylePreset.appendChild(optgroup);
    }
  }

  function renderStyleLineSlotTabs() {
    if (!styleLineSlotTabs) return;
    const slots = window.SubtitleStyleRenderer?.LINE_SLOT_NAMES || ["source"];
    styleLineSlotTabs.innerHTML = "";
    slots.forEach((slotName) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `slot-tab${slotName === getSelectedStyleLineSlot() ? " active" : ""}`;
      button.dataset.slot = slotName;
      button.textContent = getLineSlotLabel(slotName);
      button.addEventListener("click", () => {
        window.AppState.selectedStyleLineSlot = slotName;
        renderStyleLineSlotTabs();
        syncSubtitleStyleControlsFromConfig();
      });
      styleLineSlotTabs.appendChild(button);
    });
  }

  function getResolvedSubtitleStyle() {
    return window.SubtitleStyleRenderer
      ? window.SubtitleStyleRenderer.resolveEffectiveStyle(
          window.AppState.config?.subtitle_style || {},
          getStylePresetCatalog()
        )
      : {};
  }

  function updateStyleLineSlotVisibility() {
    setElementVisibility(styleLineSlotFields, Boolean(styleLineSlotEnabled?.checked));
    setElementVisibility(styleLineSlotDetails, Boolean(styleLineSlotEnabled?.checked));
  }

  function syncSubtitleStyleControlsFromConfig() {
    if (!window.AppState.config) return;
    const style = normalizeSubtitleStyleConfig(window.AppState.config.subtitle_style || {});
    window.AppState.config.subtitle_style = style;
    const presets = getStylePresetCatalog();
    const presetMeta = presets[style.preset] || null;
    const localizedPresetMeta = getLocalizedStylePresetMeta(style.preset, presetMeta);
    const localizedStyleLabel = style.built_in === false
      ? (style.label || style.preset)
      : (localizedPresetMeta?.label || style.label || style.preset);

    if (subtitleStylePreset) {
      subtitleStylePreset.value = style.preset || "clean_default";
    }
    if (subtitleStylePresetDescription) {
      const description = style.built_in === false
        ? (style.description || presetMeta?.description || "Choose a preset and tweak it locally.")
        : (localizedPresetMeta?.description || style.description || presetMeta?.description || "Choose a preset and tweak it locally.");
      const fallback = getCurrentLocale() === "ru"
        ? "Выберите пресет и при необходимости подстройте его локально."
        : "Choose a preset and tweak it locally.";
      subtitleStylePresetDescription.textContent = description || fallback;
    }
    if (subtitleStyleCustomStatus) {
      const recommendation = style.recommended_max_visible_lines
        ? (getCurrentLocale() === "ru"
            ? ` Рекомендуется для ${style.recommended_max_visible_lines} видим${style.recommended_max_visible_lines === 1 ? "ой строки" : "ых строк"}.`
            : ` Recommended for ${style.recommended_max_visible_lines} visible line${style.recommended_max_visible_lines === 1 ? "" : "s"}.`)
        : "";
      subtitleStyleCustomStatus.textContent =
        style.built_in === false
          ? (getCurrentLocale() === "ru"
              ? `Редактируется пользовательский пресет "${localizedStyleLabel}".${recommendation}`
              : `Editing custom preset "${localizedStyleLabel}".${recommendation}`)
          : (getCurrentLocale() === "ru"
              ? `Редактируется встроенный пресет "${localizedStyleLabel}".${recommendation}`
              : `Editing built-in preset "${localizedStyleLabel}".${recommendation}`);
    }
    if (subtitleStyleCustomName) {
      subtitleStyleCustomName.value = style.built_in === false ? style.label || style.preset || "" : "";
    }

    renderFontPicker(styleFontFamily, style.base.font_family || "");
    if (styleFontSize) styleFontSize.value = String(style.base.font_size_px ?? 30);
    if (styleFontWeight) styleFontWeight.value = String(style.base.font_weight ?? 700);
    if (styleFillColor) styleFillColor.value = style.base.fill_color || "#ffffff";
    if (styleStrokeColor) styleStrokeColor.value = style.base.stroke_color || "#000000";
    if (styleStrokeWidth) styleStrokeWidth.value = String(style.base.stroke_width_px ?? 2);
    if (styleShadowColor) styleShadowColor.value = style.base.shadow_color || "#000000";
    if (styleShadowBlur) styleShadowBlur.value = String(style.base.shadow_blur_px ?? 10);
    if (styleShadowOffsetX) styleShadowOffsetX.value = String(style.base.shadow_offset_x_px ?? 0);
    if (styleShadowOffsetY) styleShadowOffsetY.value = String(style.base.shadow_offset_y_px ?? 3);
    if (styleBackgroundColor) styleBackgroundColor.value = style.base.background_color || "#000000";
    if (styleBackgroundOpacity) styleBackgroundOpacity.value = String(style.base.background_opacity ?? 0);
    if (styleBackgroundPaddingX) styleBackgroundPaddingX.value = String(style.base.background_padding_x_px ?? 12);
    if (styleBackgroundPaddingY) styleBackgroundPaddingY.value = String(style.base.background_padding_y_px ?? 4);
    if (styleBackgroundRadius) styleBackgroundRadius.value = String(style.base.background_radius_px ?? 10);
    if (styleLineSpacing) styleLineSpacing.value = String(style.base.line_spacing_em ?? 1.15);
    if (styleLetterSpacing) styleLetterSpacing.value = String(style.base.letter_spacing_em ?? 0);
    if (styleTextAlign) styleTextAlign.value = style.base.text_align || "center";
    if (styleLineGap) styleLineGap.value = String(style.base.line_gap_px ?? 8);
    if (styleEffect) styleEffect.value = style.base.effect || "none";

    const selectedSlot = getSelectedStyleLineSlot();
    const selectedSlotStyle = style.line_slots?.[selectedSlot] || { enabled: false };
    renderStyleLineSlotTabs();
    if (styleLineSlotDescription) {
      styleLineSlotDescription.textContent = getLineSlotDescription(selectedSlot);
    }
    if (styleLineSlotEnabled) styleLineSlotEnabled.checked = Boolean(selectedSlotStyle.enabled);
    renderFontPicker(styleLineSlotFontFamily, selectedSlotStyle.font_family || style.base.font_family || "");
    if (styleLineSlotFontSize) {
      styleLineSlotFontSize.value = String(selectedSlotStyle.font_size_px ?? style.base.font_size_px ?? 30);
    }
    if (styleLineSlotFontWeight) {
      styleLineSlotFontWeight.value = String(selectedSlotStyle.font_weight ?? style.base.font_weight ?? 700);
    }
    if (styleLineSlotFillColor) styleLineSlotFillColor.value = selectedSlotStyle.fill_color || style.base.fill_color || "#ffffff";
    if (styleLineSlotStrokeColor) {
      styleLineSlotStrokeColor.value = selectedSlotStyle.stroke_color || style.base.stroke_color || "#000000";
    }
    if (styleLineSlotStrokeWidth) {
      styleLineSlotStrokeWidth.value = String(selectedSlotStyle.stroke_width_px ?? style.base.stroke_width_px ?? 2);
    }
    if (styleLineSlotShadowColor) {
      styleLineSlotShadowColor.value = selectedSlotStyle.shadow_color || style.base.shadow_color || "#000000";
    }
    if (styleLineSlotShadowBlur) {
      styleLineSlotShadowBlur.value = String(selectedSlotStyle.shadow_blur_px ?? style.base.shadow_blur_px ?? 10);
    }
    if (styleLineSlotShadowOffsetX) {
      styleLineSlotShadowOffsetX.value = String(selectedSlotStyle.shadow_offset_x_px ?? style.base.shadow_offset_x_px ?? 0);
    }
    if (styleLineSlotShadowOffsetY) {
      styleLineSlotShadowOffsetY.value = String(selectedSlotStyle.shadow_offset_y_px ?? style.base.shadow_offset_y_px ?? 3);
    }
    if (styleLineSlotBackgroundColor) {
      styleLineSlotBackgroundColor.value = selectedSlotStyle.background_color || style.base.background_color || "#000000";
    }
    if (styleLineSlotBackgroundOpacity) {
      styleLineSlotBackgroundOpacity.value = String(
        selectedSlotStyle.background_opacity ?? style.base.background_opacity ?? 0
      );
    }
    if (styleLineSlotBackgroundPaddingX) {
      styleLineSlotBackgroundPaddingX.value = String(
        selectedSlotStyle.background_padding_x_px ?? style.base.background_padding_x_px ?? 12
      );
    }
    if (styleLineSlotBackgroundPaddingY) {
      styleLineSlotBackgroundPaddingY.value = String(
        selectedSlotStyle.background_padding_y_px ?? style.base.background_padding_y_px ?? 4
      );
    }
    if (styleLineSlotBackgroundRadius) {
      styleLineSlotBackgroundRadius.value = String(
        selectedSlotStyle.background_radius_px ?? style.base.background_radius_px ?? 10
      );
    }
    if (styleLineSlotLineSpacing) {
      styleLineSlotLineSpacing.value = String(selectedSlotStyle.line_spacing_em ?? style.base.line_spacing_em ?? 1.15);
    }
    if (styleLineSlotLetterSpacing) {
      styleLineSlotLetterSpacing.value = String(
        selectedSlotStyle.letter_spacing_em ?? style.base.letter_spacing_em ?? 0
      );
    }
    if (styleLineSlotTextAlign) {
      styleLineSlotTextAlign.value = selectedSlotStyle.text_align || style.base.text_align || "center";
    }
    if (styleLineSlotEffect) {
      styleLineSlotEffect.value = selectedSlotStyle.effect || style.base.effect || "none";
    }

    updateStyleLineSlotVisibility();
    syncFontCatalogUi();
  }

  function syncSubtitleStyleConfigFromControls() {
    if (!window.AppState.config) return;
    const currentStyle = normalizeSubtitleStyleConfig(window.AppState.config.subtitle_style || {});
    const selectedSlot = getSelectedStyleLineSlot();
    const currentSlot = currentStyle.line_slots?.[selectedSlot] || { enabled: false };
    const nextStyle = {
      preset: subtitleStylePreset?.value || currentStyle.preset || "clean_default",
      label: currentStyle.label,
      description: currentStyle.description,
      custom_presets: currentStyle.custom_presets || {},
      base: {
        ...currentStyle.base,
        font_family: styleFontFamily?.value || currentStyle.base.font_family,
        font_size_px: Math.max(12, parseIntegerOr(styleFontSize?.value ?? currentStyle.base.font_size_px, currentStyle.base.font_size_px)),
        font_weight: Math.max(300, Math.min(900, parseIntegerOr(styleFontWeight?.value ?? currentStyle.base.font_weight, currentStyle.base.font_weight))),
        fill_color: styleFillColor?.value || currentStyle.base.fill_color,
        stroke_color: styleStrokeColor?.value || currentStyle.base.stroke_color,
        stroke_width_px: Math.max(0, parseIntegerOr(styleStrokeWidth?.value ?? currentStyle.base.stroke_width_px, currentStyle.base.stroke_width_px)),
        shadow_color: styleShadowColor?.value || currentStyle.base.shadow_color,
        shadow_blur_px: Math.max(0, parseIntegerOr(styleShadowBlur?.value ?? currentStyle.base.shadow_blur_px, currentStyle.base.shadow_blur_px)),
        shadow_offset_x_px: parseIntegerOr(styleShadowOffsetX?.value ?? currentStyle.base.shadow_offset_x_px, currentStyle.base.shadow_offset_x_px),
        shadow_offset_y_px: parseIntegerOr(styleShadowOffsetY?.value ?? currentStyle.base.shadow_offset_y_px, currentStyle.base.shadow_offset_y_px),
        background_color: styleBackgroundColor?.value || currentStyle.base.background_color,
        background_opacity: Math.max(0, Math.min(100, parseIntegerOr(styleBackgroundOpacity?.value ?? currentStyle.base.background_opacity, currentStyle.base.background_opacity))),
        background_padding_x_px: Math.max(0, parseIntegerOr(styleBackgroundPaddingX?.value ?? currentStyle.base.background_padding_x_px, currentStyle.base.background_padding_x_px)),
        background_padding_y_px: Math.max(0, parseIntegerOr(styleBackgroundPaddingY?.value ?? currentStyle.base.background_padding_y_px, currentStyle.base.background_padding_y_px)),
        background_radius_px: Math.max(0, parseIntegerOr(styleBackgroundRadius?.value ?? currentStyle.base.background_radius_px, currentStyle.base.background_radius_px)),
        line_spacing_em: parseFloatOr(styleLineSpacing?.value ?? currentStyle.base.line_spacing_em, currentStyle.base.line_spacing_em),
        letter_spacing_em: parseFloatOr(styleLetterSpacing?.value ?? currentStyle.base.letter_spacing_em, currentStyle.base.letter_spacing_em),
        text_align: styleTextAlign?.value || currentStyle.base.text_align,
        line_gap_px: Math.max(0, parseIntegerOr(styleLineGap?.value ?? currentStyle.base.line_gap_px, currentStyle.base.line_gap_px)),
        effect: styleEffect?.value || currentStyle.base.effect,
      },
      line_slots: {
        ...(currentStyle.line_slots || {}),
        [selectedSlot]: {
          ...currentSlot,
          enabled: Boolean(styleLineSlotEnabled?.checked),
          font_family: styleLineSlotFontFamily?.value || currentStyle.base.font_family,
          font_size_px: Math.max(
            12,
            parseIntegerOr(styleLineSlotFontSize?.value ?? currentStyle.base.font_size_px, currentStyle.base.font_size_px)
          ),
          font_weight: Math.max(
            300,
            Math.min(
              900,
              parseIntegerOr(styleLineSlotFontWeight?.value ?? currentStyle.base.font_weight, currentStyle.base.font_weight)
            )
          ),
          fill_color: styleLineSlotFillColor?.value || currentStyle.base.fill_color,
          stroke_color: styleLineSlotStrokeColor?.value || currentStyle.base.stroke_color,
          stroke_width_px: Math.max(
            0,
            parseIntegerOr(styleLineSlotStrokeWidth?.value ?? currentStyle.base.stroke_width_px, currentStyle.base.stroke_width_px)
          ),
          shadow_color: styleLineSlotShadowColor?.value || currentStyle.base.shadow_color,
          shadow_blur_px: Math.max(
            0,
            parseIntegerOr(styleLineSlotShadowBlur?.value ?? currentStyle.base.shadow_blur_px, currentStyle.base.shadow_blur_px)
          ),
          shadow_offset_x_px: parseIntegerOr(
            styleLineSlotShadowOffsetX?.value ?? currentStyle.base.shadow_offset_x_px,
            currentStyle.base.shadow_offset_x_px
          ),
          shadow_offset_y_px: parseIntegerOr(
            styleLineSlotShadowOffsetY?.value ?? currentStyle.base.shadow_offset_y_px,
            currentStyle.base.shadow_offset_y_px
          ),
          background_color: styleLineSlotBackgroundColor?.value || currentStyle.base.background_color,
          background_opacity: Math.max(
            0,
            Math.min(
              100,
              parseIntegerOr(
                styleLineSlotBackgroundOpacity?.value ?? currentStyle.base.background_opacity,
                currentStyle.base.background_opacity
              )
            )
          ),
          background_padding_x_px: Math.max(
            0,
            parseIntegerOr(
              styleLineSlotBackgroundPaddingX?.value ?? currentStyle.base.background_padding_x_px,
              currentStyle.base.background_padding_x_px
            )
          ),
          background_padding_y_px: Math.max(
            0,
            parseIntegerOr(
              styleLineSlotBackgroundPaddingY?.value ?? currentStyle.base.background_padding_y_px,
              currentStyle.base.background_padding_y_px
            )
          ),
          background_radius_px: Math.max(
            0,
            parseIntegerOr(
              styleLineSlotBackgroundRadius?.value ?? currentStyle.base.background_radius_px,
              currentStyle.base.background_radius_px
            )
          ),
          line_spacing_em: parseFloatOr(
            styleLineSlotLineSpacing?.value ?? currentStyle.base.line_spacing_em,
            currentStyle.base.line_spacing_em
          ),
          letter_spacing_em: parseFloatOr(
            styleLineSlotLetterSpacing?.value ?? currentStyle.base.letter_spacing_em,
            currentStyle.base.letter_spacing_em
          ),
          text_align: styleLineSlotTextAlign?.value || currentStyle.base.text_align,
          effect: styleLineSlotEffect?.value || currentStyle.base.effect,
        },
      },
    };
    window.AppState.config.subtitle_style = normalizeSubtitleStyleConfig(nextStyle);
    updateStyleLineSlotVisibility();
    syncConfigText();
    renderSubtitlePreview();
  }

  function saveCurrentStyleAsCustomPreset() {
    if (!window.AppState.config) return;
    const rawName = subtitleStyleCustomName?.value || "";
    const presetKey = normalizeCustomPresetKey(rawName);
    if (!presetKey) {
      if (subtitleStyleCustomStatus) {
        subtitleStyleCustomStatus.textContent = getCurrentLocale() === "ru"
          ? "Сначала введите имя пользовательского пресета."
          : "Enter a custom preset name first.";
      }
      return;
    }
    const currentStyle = normalizeSubtitleStyleConfig(window.AppState.config.subtitle_style || {});
    const customPresets = {
      ...(currentStyle.custom_presets || {}),
    };
    customPresets[presetKey] = {
      ...currentStyle,
      preset: presetKey,
      label: rawName.trim() || presetKey,
      description: `User-created local subtitle style from ${currentStyle.label || currentStyle.preset}.`,
      built_in: false,
      custom_presets: {},
    };
    window.AppState.config.subtitle_style = normalizeSubtitleStyleConfig({
      ...currentStyle,
      preset: presetKey,
      label: rawName.trim() || presetKey,
      description: customPresets[presetKey].description,
      custom_presets: customPresets,
    });
    const updatedCatalog = {
      ...window.AppState.subtitleStylePresets,
      [presetKey]: customPresets[presetKey],
    };
    setSubtitleStylePresets(updatedCatalog);
    syncSubtitleStyleControlsFromConfig();
    syncConfigText();
    renderSubtitlePreview();
    if (subtitleStyleCustomStatus) {
      subtitleStyleCustomStatus.textContent = getCurrentLocale() === "ru"
        ? `Пользовательский пресет "${rawName.trim() || presetKey}" сохранён.`
        : `Saved custom preset "${rawName.trim() || presetKey}".`;
    }
  }

  function deleteCurrentCustomStylePreset() {
    if (!window.AppState.config) return;
    const currentStyle = normalizeSubtitleStyleConfig(window.AppState.config.subtitle_style || {});
    const currentPreset = currentStyle.preset || "";
    if (!currentPreset || !currentStyle.custom_presets?.[currentPreset]) {
      if (subtitleStyleCustomStatus) {
        subtitleStyleCustomStatus.textContent = getCurrentLocale() === "ru"
          ? "Выбран встроенный пресет, поэтому удалять нечего."
          : "Selected preset is built-in, so there is nothing custom to delete.";
      }
      return;
    }
    const customPresets = { ...(currentStyle.custom_presets || {}) };
    delete customPresets[currentPreset];
    window.AppState.config.subtitle_style = normalizeSubtitleStyleConfig({
      ...buildSubtitleStyleFromPreset("clean_default"),
      custom_presets: customPresets,
    });
    const updatedCatalog = { ...window.AppState.subtitleStylePresets };
    delete updatedCatalog[currentPreset];
    setSubtitleStylePresets(updatedCatalog);
    syncSubtitleStyleControlsFromConfig();
    syncConfigText();
    renderSubtitlePreview();
    if (subtitleStyleCustomStatus) {
      subtitleStyleCustomStatus.textContent = getCurrentLocale() === "ru"
        ? `Пользовательский пресет "${currentStyle.label || currentPreset}" удалён.`
        : `Deleted custom preset "${currentStyle.label || currentPreset}".`;
    }
  }

  function buildSubtitlePreviewPayload() {
    const config = window.AppState.config;
    if (!config) {
      return null;
    }
    const payload = window.AppState.subtitlePayload;
    if (payload) {
      return {
        ...payload,
        style: getResolvedSubtitleStyle(),
      };
    }

    const visibleItems = [];
    const displayOrder = Array.isArray(config.subtitle_output?.display_order)
      ? config.subtitle_output.display_order
      : [];
    const maxTranslations = Math.max(0, Math.min(5, Number(config.subtitle_output?.max_translation_languages || 0)));
    let translationsUsed = 0;
    displayOrder.forEach((code) => {
      if (code === "source") {
        if (config.subtitle_output?.show_source !== false) {
          visibleItems.push({
            kind: "source",
            lang: config.source_lang || "auto",
            style_slot: "source",
            text: getCurrentLocale() === "ru" ? "Предпросмотр исходной строки" : "Source subtitle preview",
          });
        }
        return;
      }
      if (config.subtitle_output?.show_translations === false || translationsUsed >= maxTranslations) {
        return;
      }
      visibleItems.push({
        kind: "translation",
        lang: code,
        style_slot: `translation_${translationsUsed + 1}`,
        text: getCurrentLocale() === "ru"
          ? `Предпросмотр перевода: ${getLanguageLabel(code)}`
          : `${getLanguageLabel(code)} subtitle preview`,
      });
      translationsUsed += 1;
    });

    return {
      preset: config.overlay?.preset || "single",
      compact: Boolean(config.overlay?.compact),
      completed_block_visible: visibleItems.length > 0,
      visible_items: visibleItems,
      active_partial_text: visibleItems.length === 0 && config.subtitle_output?.show_source !== false
        ? (getCurrentLocale() === "ru" ? "Предпросмотр live-partial" : "Live partial preview")
        : "",
      style: getResolvedSubtitleStyle(),
      sequence: 0,
    };
  }

  function renderSubtitlePreview() {
    if (!subtitleOutputPreview) return;
    const payload = buildSubtitlePreviewPayload();
    if (!payload) {
      subtitleOutputPreview.innerHTML = `<p class="muted">${escapeHtml(getCurrentLocale() === "ru" ? "Предпросмотр стиля субтитров появится после загрузки config." : "Subtitle style preview is unavailable until config loads.")}</p>`;
      return;
    }
    const renderResult = window.SubtitleStyleRenderer
      ? window.SubtitleStyleRenderer.render(subtitleOutputPreview, payload, {
          styleConfig: window.AppState.config?.subtitle_style || {},
          presets: getStylePresetCatalog(),
        })
      : { empty: true };
    if (renderResult.empty) {
      subtitleOutputPreview.innerHTML = `<p class="muted">${escapeHtml(getCurrentLocale() === "ru" ? "По текущим настройкам сейчас нет видимых строк субтитров." : "No visible subtitle lines for the current settings yet.")}</p>`;
      return;
    }

    const note = document.createElement("p");
    note.className = "subtitle-stage-note";
    note.textContent = window.AppState.subtitlePayload
      ? payload.completed_block_visible
        ? (getCurrentLocale() === "ru"
            ? `Живой блок субтитров${payload.sequence ? ` #${payload.sequence}` : ""}.`
            : `Live subtitle block${payload.sequence ? ` #${payload.sequence}` : ""}.`)
        : (getCurrentLocale() === "ru" ? "Предпросмотр live-partial." : "Live partial preview.")
      : (getCurrentLocale() === "ru"
          ? "Предпросмотр построен по текущему сохранённому порядку строк, схеме overlay и стилю субтитров."
          : "Preview built from the current saved subtitle output order, overlay layout, and subtitle style.");
    subtitleOutputPreview.appendChild(note);
  }

  function syncSubtitleLifecycleControlsFromConfig() {
    if (!window.AppState.config) return;
    const lifecycle = window.AppState.config.subtitle_lifecycle || {};
    if (subtitleCompletedSourceTtl) {
      subtitleCompletedSourceTtl.value = formatSecondsFromMs(
        lifecycle.completed_source_ttl_ms ?? lifecycle.completed_block_ttl_ms ?? 4500,
        4500
      );
    }
    if (subtitleCompletedTranslationTtl) {
      subtitleCompletedTranslationTtl.value = formatSecondsFromMs(
        lifecycle.completed_translation_ttl_ms ?? lifecycle.completed_block_ttl_ms ?? 4500,
        4500
      );
    }
    if (subtitleSyncSourceTranslationExpiry) {
      subtitleSyncSourceTranslationExpiry.checked = lifecycle.sync_source_and_translation_expiry !== false;
    }
    if (subtitleAllowEarlyReplace) {
      subtitleAllowEarlyReplace.checked = lifecycle.allow_early_replace_on_next_final !== false;
    }
  }

  function syncTranslationFormFromConfig() {
    if (!window.AppState.config) return;
    const translation = window.AppState.config.translation;
    if (translationEnabled) {
      translationEnabled.checked = translation.enabled;
    }
    if (translationProvider) {
      translationProvider.value = translation.provider;
    }

    const provider = translation.provider;
    const providerSettings = translation.provider_settings[provider] || {};
    const providerMeta = getProviderMeta(provider) || getProviderMeta("google_translate_v2") || PROVIDERS.google_translate_v2;
    const usesApiKey = providerMeta.fields.includes("api_key");
    const usesBaseUrl = providerMeta.fields.includes("base_url");
    const usesGasUrl = providerMeta.fields.includes("gas_url");
    const usesEndpoint = providerMeta.fields.includes("endpoint");
    const usesRegion = providerMeta.fields.includes("region");
    const usesApiUrl = providerMeta.fields.includes("api_url");
    const usesModel = providerMeta.fields.includes("model");
    const usesPrompt = providerMeta.fields.includes("custom_prompt");
    if (translationApiKey) {
      translationApiKey.value = providerSettings.api_key || "";
      translationApiKey.placeholder = usesApiKey
        ? t("translation.api_key")
        : (getCurrentLocale() === "ru" ? "Для этого провайдера не используется" : "Not used for this provider");
      translationApiKey.disabled = !usesApiKey;
    }
    if (translationBaseUrl) {
      translationBaseUrl.value = providerSettings.base_url || providerMeta.baseUrlPlaceholder || "";
      translationBaseUrl.placeholder = providerMeta.baseUrlPlaceholder || t("translation.base_url");
      translationBaseUrl.disabled = !usesBaseUrl;
    }
    if (translationGasUrl) {
      translationGasUrl.value = providerSettings.gas_url || "";
      translationGasUrl.placeholder = t("translation.gas_url");
      translationGasUrl.disabled = !usesGasUrl;
    }
    if (translationEndpoint) {
      translationEndpoint.value = providerSettings.endpoint || providerMeta.endpointPlaceholder || "";
      translationEndpoint.placeholder = providerMeta.endpointPlaceholder || t("translation.endpoint");
      translationEndpoint.disabled = !usesEndpoint;
    }
    if (translationRegion) {
      translationRegion.value = providerSettings.region || "";
      translationRegion.placeholder = usesRegion
        ? t("translation.region")
        : (getCurrentLocale() === "ru" ? "Для этого провайдера не используется" : "Not used for this provider");
      translationRegion.disabled = !usesRegion;
    }
    if (translationApiUrl) {
      translationApiUrl.value = providerSettings.api_url || providerMeta.apiUrlPlaceholder || "";
      translationApiUrl.placeholder = providerMeta.apiUrlPlaceholder || t("translation.provider_url");
      translationApiUrl.disabled = !usesApiUrl;
    }
    if (translationModel) {
      translationModel.value = providerSettings.model || "";
      translationModel.placeholder = t("translation.model");
      translationModel.disabled = !usesModel;
    }
    if (translationCustomPrompt) {
      translationCustomPrompt.value = providerSettings.custom_prompt || "";
      translationCustomPrompt.disabled = !usesPrompt;
    }
    if (translationProviderHint) {
      translationProviderHint.textContent = providerMeta.hint;
    }
    if (translationProviderStatus) {
      translationProviderStatus.textContent = providerMeta.status;
    }
    setElementVisibility(translationApiKeyRow, usesApiKey);
    setElementVisibility(translationBaseUrlRow, usesBaseUrl);
    setElementVisibility(translationGasUrlRow, usesGasUrl);
    setElementVisibility(translationEndpointRow, usesEndpoint || usesRegion);
    setElementVisibility(translationRegionRow, usesRegion);
    setElementVisibility(translationApiUrlRow, usesApiUrl);
    setElementVisibility(translationModelRow, usesModel);
    setElementVisibility(translationPromptRow, usesPrompt);
    renderTranslationOrder();
    if (subtitleShowSource) {
      subtitleShowSource.checked = window.AppState.config.subtitle_output.show_source;
    }
    if (subtitleShowTranslations) {
      subtitleShowTranslations.checked = window.AppState.config.subtitle_output.show_translations;
    }
    if (subtitleMaxTranslations) {
      subtitleMaxTranslations.value = String(
        Math.max(0, Math.min(5, window.AppState.config.subtitle_output.max_translation_languages || 0))
      );
    }
    if (overlayPresetSelect) {
      overlayPresetSelect.value = window.AppState.config.overlay?.preset || "single";
    }
    updateOverlayPresetHint();
    if (overlayCompactToggle) {
      overlayCompactToggle.checked = Boolean(window.AppState.config.overlay?.compact);
    }
    syncObsCcControlsFromConfig();
    const realtime = window.AppState.config.asr.realtime;
    const lifecycle = window.AppState.config.subtitle_lifecycle || {};
    if (rtVadMode) {
      rtVadMode.value = String(realtime.vad_mode ?? 2);
    }
    if (rtPartialEmitInterval) {
      rtPartialEmitInterval.value = String(realtime.partial_emit_interval_ms);
    }
    if (rtMinSpeech) {
      rtMinSpeech.value = String(realtime.min_speech_ms);
    }
    if (rtMaxSegment) {
      rtMaxSegment.value = String(lifecycle.hard_max_phrase_ms ?? realtime.max_segment_ms);
    }
    if (rtSilenceHold) {
      rtSilenceHold.value = String(realtime.silence_hold_ms);
    }
    if (rtFinalizationHold) {
      rtFinalizationHold.value = String(lifecycle.pause_to_finalize_ms ?? realtime.finalization_hold_ms);
    }
    if (rtChunkWindow) {
      rtChunkWindow.value = String(realtime.chunk_window_ms);
    }
    if (rtChunkOverlap) {
      rtChunkOverlap.value = String(realtime.chunk_overlap_ms);
    }
    if (rtEnergyGateEnabled) {
      rtEnergyGateEnabled.checked = Boolean(realtime.energy_gate_enabled);
    }
    if (rtMinRms) {
      rtMinRms.value = String(realtime.min_rms_for_recognition ?? 0.0018);
    }
    if (rtMinVoicedRatio) {
      rtMinVoicedRatio.value = String(realtime.min_voiced_ratio ?? 0.0);
    }
    if (rtFirstPartialMinSpeech) {
      rtFirstPartialMinSpeech.value = String(realtime.first_partial_min_speech_ms ?? realtime.min_speech_ms ?? 180);
    }
    if (rtPartialMinDelta) {
      rtPartialMinDelta.value = String(realtime.partial_min_delta_chars);
    }
    if (rtPartialCoalescing) {
      rtPartialCoalescing.value = String(realtime.partial_coalescing_ms);
    }
    if (asrRnnoiseEnabled) {
      asrRnnoiseEnabled.checked = Boolean(window.AppState.config.asr.rnnoise_enabled);
    }
    if (asrRnnoiseStrength) {
      asrRnnoiseStrength.value = String(window.AppState.config.asr.rnnoise_strength ?? 70);
      asrRnnoiseStrength.disabled = !Boolean(window.AppState.config.asr.rnnoise_enabled);
    }
    syncRnnoiseStrengthLabel();
    syncSimpleTuningControlsFromConfig();
    renderSubtitleDisplayOrder();
  }

  function setConfig(payload) {
    const normalized = ensureConfigShape(payload);
    enforceDesktopStartupMode(normalized);
    window.AppState.config = normalized;
    window.AppState.selectedAudioInputId = normalized.audio.input_device_id || null;
    if (!window.AppState.selectedStyleLineSlot) {
      window.AppState.selectedStyleLineSlot = "source";
    }
    if (!normalized.translation.target_languages.includes(window.AppState.selectedTranslationLanguage)) {
      window.AppState.selectedTranslationLanguage = normalized.translation.target_languages[0] || null;
    }
    if (!normalized.subtitle_output.display_order.includes(window.AppState.selectedSubtitleOrderItem)) {
      window.AppState.selectedSubtitleOrderItem = normalized.subtitle_output.display_order[0] || null;
    }
    if (profileNameInput) {
      profileNameInput.value = normalized.profile;
    }
    syncRecognitionControlsFromConfig();
    syncSubtitleLifecycleControlsFromConfig();
    syncTranslationFormFromConfig();
    syncSubtitleStyleControlsFromConfig();
    syncConfigText();
    renderSubtitlePreview();
  }

  function maybeReportGoogleKeyNormalization(previousPayload, savedPayload) {
    const previousKey = String(
      previousPayload?.translation?.provider_settings?.google_translate_v2?.api_key || ""
    );
    const savedKey = String(
      savedPayload?.translation?.provider_settings?.google_translate_v2?.api_key || ""
    );
    if (!previousKey || !savedKey || previousKey === savedKey) {
      return;
    }
    const previousProvider = String(previousPayload?.translation?.provider || "");
    const currentProvider = String(savedPayload?.translation?.provider || "");
    if (translationProviderStatus && (previousProvider === "google_translate_v2" || currentProvider === "google_translate_v2")) {
      const providerMeta = getProviderMeta("google_translate_v2") || PROVIDERS.google_translate_v2;
      translationProviderStatus.textContent = `${providerMeta.status} ${getCurrentLocale() === "ru" ? "Google key был нормализован и сохранён." : "Google key normalized and saved."}`;
    }
    log(getCurrentLocale() === "ru" ? "[translation] Google key нормализован и сохранён" : "[translation] Google key normalized and saved");
  }

  function syncTranslationConfigFromControls() {
    if (!window.AppState.config) return;
    const translation = window.AppState.config.translation;
    translation.enabled = Boolean(translationEnabled?.checked);
    if (translationProvider?.value && PROVIDERS[translationProvider.value]) {
      translation.provider = translationProvider.value;
    }
    const provider = translation.provider;
    const providerMeta = PROVIDERS[provider];
    translation.provider_settings[provider] = translation.provider_settings[provider] || {};
    translation.provider_settings[provider].api_key = providerMeta.fields.includes("api_key")
      ? translationApiKey?.value || ""
      : "";
    translation.provider_settings[provider].base_url = providerMeta.fields.includes("base_url")
      ? translationBaseUrl?.value || providerMeta.baseUrlPlaceholder || ""
      : "";
    translation.provider_settings[provider].gas_url = providerMeta.fields.includes("gas_url")
      ? translationGasUrl?.value || ""
      : "";
    translation.provider_settings[provider].endpoint = providerMeta.fields.includes("endpoint")
      ? translationEndpoint?.value || providerMeta.endpointPlaceholder || ""
      : "";
    translation.provider_settings[provider].region = providerMeta.fields.includes("region")
      ? translationRegion?.value || ""
      : "";
    translation.provider_settings[provider].api_url = providerMeta.fields.includes("api_url")
      ? translationApiUrl?.value || providerMeta.apiUrlPlaceholder || ""
      : "";
    translation.provider_settings[provider].model = providerMeta.fields.includes("model")
      ? translationModel?.value || ""
      : "";
    translation.provider_settings[provider].custom_prompt = providerMeta.fields.includes("custom_prompt")
      ? translationCustomPrompt?.value || ""
      : "";
    window.AppState.config.targets = [...translation.target_languages];
    const subtitleOrder = window.AppState.config.subtitle_output.display_order.filter(
      (item) => item === "source" || translation.target_languages.includes(item)
    );
    translation.target_languages.forEach((code) => {
      if (!subtitleOrder.includes(code)) {
        subtitleOrder.push(code);
      }
    });
    if (!subtitleOrder.includes("source")) {
      subtitleOrder.push("source");
    }
    window.AppState.config.subtitle_output.display_order = subtitleOrder;
    if (!subtitleOrder.includes(window.AppState.selectedSubtitleOrderItem)) {
      window.AppState.selectedSubtitleOrderItem = subtitleOrder[0] || null;
    }
    syncTranslationFormFromConfig();
    syncConfigText();
    renderSubtitlePreview();
  }

  function syncSubtitleOutputConfigFromControls() {
    if (!window.AppState.config) return;
    const subtitleOutput = window.AppState.config.subtitle_output;
    subtitleOutput.show_source = Boolean(subtitleShowSource?.checked);
    subtitleOutput.show_translations = Boolean(subtitleShowTranslations?.checked);
    subtitleOutput.max_translation_languages = Math.max(
      0,
      Math.min(5, Number.parseInt(subtitleMaxTranslations?.value || "0", 10) || 0)
    );
    window.AppState.config.overlay = window.AppState.config.overlay || { preset: "single", compact: false };
    if (overlayPresetSelect?.value) {
      window.AppState.config.overlay.preset = overlayPresetSelect.value;
    }
    window.AppState.config.overlay.compact = Boolean(overlayCompactToggle?.checked);
    syncTranslationFormFromConfig();
    syncConfigText();
    renderSubtitlePreview();
  }

  function syncRealtimeConfigFromControls() {
    if (!window.AppState.config) return;
    window.AppState.config.asr.rnnoise_enabled = Boolean(asrRnnoiseEnabled?.checked);
    window.AppState.config.asr.rnnoise_strength = Math.max(
      0,
      Math.min(100, parseIntegerOr(asrRnnoiseStrength?.value ?? "70", 70))
    );
    if (asrRnnoiseStrength) {
      asrRnnoiseStrength.disabled = !window.AppState.config.asr.rnnoise_enabled;
    }
    syncRnnoiseStrengthLabel();
    const realtime = window.AppState.config.asr.realtime;
    const lifecycle = window.AppState.config.subtitle_lifecycle;
    realtime.vad_mode = Math.max(
      0,
      Math.min(3, parseIntegerOr(rtVadMode?.value ?? "2", 2))
    );
    realtime.partial_emit_interval_ms = Math.max(
      60,
      parseIntegerOr(rtPartialEmitInterval?.value ?? "450", 450)
    );
    realtime.min_speech_ms = Math.max(
      0,
      parseIntegerOr(rtMinSpeech?.value ?? "180", 180)
    );
    realtime.max_segment_ms = Math.max(
      500,
      parseIntegerOr(rtMaxSegment?.value ?? "5500", 5500)
    );
    realtime.silence_hold_ms = Math.max(
      60,
      parseIntegerOr(rtSilenceHold?.value ?? "180", 180)
    );
    lifecycle.pause_to_finalize_ms = Math.max(
      realtime.silence_hold_ms,
      parseIntegerOr(rtFinalizationHold?.value ?? "350", 350)
    );
    realtime.finalization_hold_ms = lifecycle.pause_to_finalize_ms;
    realtime.chunk_window_ms = Math.max(
      0,
      parseIntegerOr(rtChunkWindow?.value ?? "0", 0)
    );
    realtime.chunk_overlap_ms = Math.max(
      0,
      Math.min(
        realtime.chunk_window_ms,
        parseIntegerOr(rtChunkOverlap?.value ?? "0", 0)
      )
    );
    realtime.energy_gate_enabled = rtEnergyGateEnabled ? rtEnergyGateEnabled.checked : true;
    realtime.min_rms_for_recognition = Math.max(
      0,
      Math.min(0.05, parseFloatOr(rtMinRms?.value ?? "0.0018", 0.0018))
    );
    realtime.min_voiced_ratio = Math.max(
      0,
      Math.min(1, parseFloatOr(rtMinVoicedRatio?.value ?? "0.0", 0.0))
    );
    realtime.first_partial_min_speech_ms = Math.max(
      realtime.min_speech_ms,
      parseIntegerOr(rtFirstPartialMinSpeech?.value ?? "300", 300)
    );
    realtime.partial_min_delta_chars = Math.max(
      0,
      parseIntegerOr(rtPartialMinDelta?.value ?? "12", 12)
    );
    realtime.partial_coalescing_ms = Math.max(
      0,
      parseIntegerOr(rtPartialCoalescing?.value ?? "160", 160)
    );
    lifecycle.hard_max_phrase_ms = Math.max(
      1000,
      parseIntegerOr(rtMaxSegment?.value ?? "5500", 5500)
    );
    lifecycle.completed_source_ttl_ms = parseSecondsToMs(
      subtitleCompletedSourceTtl?.value ?? "4.5",
      4500,
      500
    );
    lifecycle.completed_translation_ttl_ms = parseSecondsToMs(
      subtitleCompletedTranslationTtl?.value ?? "4.5",
      4500,
      500
    );
    lifecycle.completed_block_ttl_ms = Math.max(
      lifecycle.completed_source_ttl_ms,
      lifecycle.completed_translation_ttl_ms
    );
    lifecycle.allow_early_replace_on_next_final = subtitleAllowEarlyReplace ? subtitleAllowEarlyReplace.checked : true;
    lifecycle.sync_source_and_translation_expiry = subtitleSyncSourceTranslationExpiry
      ? subtitleSyncSourceTranslationExpiry.checked
      : true;
    realtime.max_segment_ms = lifecycle.hard_max_phrase_ms;
    syncTranslationFormFromConfig();
    syncConfigText();
  }

  function parseConfigEditor() {
    if (!configJson) return ensureConfigShape({});
    const parsed = ensureConfigShape(JSON.parse(configJson.value || "{}"));
    parsed.audio.input_device_id = window.AppState.selectedAudioInputId || null;
    setConfig(parsed);
    return window.AppState.config;
  }

  async function saveCurrentConfig() {
    const previousPayload = cloneConfig(window.AppState.config || {});
    let payload;
    try {
      payload = parseConfigEditor();
    } catch (_error) {
      setSaveStatus(getCurrentLocale() === "ru" ? "Сохранение отменено: в Local Config некорректный JSON." : "Save canceled: invalid JSON in Local Config.", "error");
      log(getCurrentLocale() === "ru" ? "[config] сохранение отменено: некорректный JSON" : "[config] invalid JSON, save canceled");
      return null;
    }

    setSaveButtonsBusy(true);
    try {
      const response = await window.Api.saveSettings(payload);
      const savedPayload = response.payload || payload;
      const restartReasons = getRestartRequiredReasons(previousPayload, savedPayload);
      setSubtitleStylePresets(response.subtitle_style_presets || window.AppState.subtitleStylePresets);
      setFontCatalog(response.font_catalog || window.AppState.fontCatalog);
      setConfig(savedPayload);
      maybeReportGoogleKeyNormalization(payload, savedPayload);
      setSaveStatus(
        buildSaveStatusMessage(Boolean(response.live_applied), restartReasons),
        restartReasons.length ? "warn" : response.live_applied ? "success" : "info"
      );
      const saveLogMessage = getCurrentLocale() === "ru"
        ? `[config] сохранено локально${response.live_applied ? " и применено сразу" : ""}${
            restartReasons.length ? `; ${formatList(restartReasons)} требуют ${window.AppState.runtime?.is_running ? "Стоп/Старт" : "следующий Старт"}` : ""
          }`
        : `[config] saved locally${response.live_applied ? " and applied live" : ""}${
            restartReasons.length ? `; ${formatList(restartReasons)} require ${window.AppState.runtime?.is_running ? "Stop/Start" : "next Start"}` : ""
          }`;
      log(saveLogMessage);
      return response;
    } catch (error) {
      const message = error instanceof Error ? error.message : (getCurrentLocale() === "ru" ? "Сохранение не удалось." : "Save failed.");
      setSaveStatus(getCurrentLocale() === "ru" ? `Сохранение не удалось: ${message}` : `Save failed: ${message}`, "error");
      log(getCurrentLocale() === "ru" ? `[config] ошибка сохранения -> ${message}` : `[config] save failed -> ${message}`);
      return null;
    } finally {
      setSaveButtonsBusy(false);
    }
  }

  function downloadJson(filename, payload) {
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  function setSelectedAudioInput(deviceId) {
    window.AppState.selectedAudioInputId = deviceId || null;
    if (audioInputSelect) {
      audioInputSelect.value = deviceId || "";
    }
    if (audioInputMeta) {
      const option = audioInputSelect?.selectedOptions?.[0];
      audioInputMeta.textContent = option?.dataset.meta || (getCurrentLocale() === "ru" ? "Устройство не выбрано." : "No device selected.");
    }
    if (window.AppState.config) {
      window.AppState.config.audio.input_device_id = window.AppState.selectedAudioInputId;
      syncConfigText();
    }
  }

  function renderAudioInputs(devices) {
    window.AppState.audioDevices = Array.isArray(devices) ? devices.slice() : [];
    if (audioInputsList) {
      audioInputsList.innerHTML = "";
    }
    if (audioInputSelect) {
      audioInputSelect.innerHTML = "";
    }

    if (!devices.length) {
      if (audioInputsList) {
        const li = document.createElement("li");
        li.className = "muted";
        li.textContent = getCurrentLocale() === "ru" ? "Локальные аудиовходы не найдены." : "No local input devices found.";
        audioInputsList.appendChild(li);
      }
      if (audioInputSelect) {
        const option = document.createElement("option");
        option.value = "";
        option.textContent = getCurrentLocale() === "ru" ? "Нет доступных устройств" : "No input devices";
        audioInputSelect.appendChild(option);
      }
      setSelectedAudioInput(null);
      updateRecognitionModeUi();
      log(getCurrentLocale() === "ru" ? "[audio] входные устройства не найдены" : "[audio] no input devices found");
      return;
    }

    devices.forEach((device) => {
      if (audioInputsList) {
        const li = document.createElement("li");
        li.textContent = `${device.name}${device.is_default ? (getCurrentLocale() === "ru" ? " (по умолчанию)" : " (default)") : ""}`;
        audioInputsList.appendChild(li);
      }
      if (audioInputSelect) {
        const option = document.createElement("option");
        option.value = device.id;
        option.textContent = `${device.name}${device.is_default ? (getCurrentLocale() === "ru" ? " (по умолчанию)" : " (default)") : ""}`;
        option.dataset.meta = getCurrentLocale() === "ru"
          ? `каналы: ${device.max_input_channels}, частота: ${device.default_samplerate || "n/a"} Гц`
          : `channels: ${device.max_input_channels}, rate: ${device.default_samplerate || "n/a"} Hz`;
        option.dataset.channels = String(device.max_input_channels ?? 0);
        option.dataset.rate = String(device.default_samplerate || "n/a");
        audioInputSelect.appendChild(option);
      }
    });

    const configuredDeviceId = window.AppState.config?.audio?.input_device_id;
      const selectedDeviceId = devices.some((item) => item.id === configuredDeviceId)
        ? configuredDeviceId
        : devices.find((item) => item.is_default)?.id || devices[0].id;
      setSelectedAudioInput(selectedDeviceId);
      updateRecognitionModeUi();
      log(getCurrentLocale() === "ru" ? `[audio] найдено входных устройств: ${devices.length}` : `[audio] detected ${devices.length} input device(s)`);
    }

  async function refreshProfiles() {
    const data = await window.Api.listProfiles();
    if (!profilesSelect) return;
    profilesSelect.innerHTML = "";
    data.profiles.forEach((name) => {
      const option = document.createElement("option");
      option.value = name;
      option.textContent = name;
      profilesSelect.appendChild(option);
    });
    const activeProfile = window.AppState.config?.profile;
    if (activeProfile && data.profiles.includes(activeProfile)) {
      profilesSelect.value = activeProfile;
    }
  }

  function addTranslationEntry(sequence, sourceText) {
    const existing = window.AppState.currentTranslationEntry;
    if (existing) {
      if (existing.sequence !== sequence) {
        window.AppState.currentTranslationEntry = null;
      } else {
        existing.sourceText = sourceText;
        return existing;
      }
    }
    const entry = {
      sequence,
      sourceText,
      translations: [],
      providerLabel: "",
      statusMessage: "",
    };
    window.AppState.currentTranslationEntry = entry;
    return entry;
  }

  function clearCurrentTranslationEntryIfStale(sequence) {
    const current = window.AppState.currentTranslationEntry;
    if (!current) return;
    if (typeof sequence === "number" && current.sequence === sequence) {
      return;
    }
    if (typeof sequence !== "number") {
      return;
    }
    if (sequence > current.sequence) {
      window.AppState.currentTranslationEntry = null;
    }
  }

  window.onTranscriptEvent = (payload) => {
    const text = payload?.segment?.text || payload?.text || "";
    if (payload.event === "partial") {
      window.AppState.transcript.partial = text;
    } else if (payload.event === "final") {
      window.AppState.transcript.partial = "";
      window.AppState.transcript.finals.unshift(text);
      window.AppState.transcript.finals = window.AppState.transcript.finals.slice(0, 12);
      clearCurrentTranslationEntryIfStale(payload.sequence);
      addTranslationEntry(payload.sequence, text);
      renderTranslationResults();
    }
    renderTranscript();
  };

  window.onTranscriptSegmentEvent = (_payload) => {
    // Reserved for future true streaming/partial-capable providers.
    // Current UI keeps using the stable transcript_update flow.
  };

  window.onTranslationEvent = (payload) => {
    const entry = addTranslationEntry(payload.sequence, payload.source_text);
    entry.translations = payload.translations || [];
    const meta = payload.provider ? getProviderMeta(payload.provider) : null;
    const providerLabelParts = [];
    if (payload.provider) {
      providerLabelParts.push(getCurrentLocale() === "ru" ? `Провайдер: ${meta?.label || payload.provider}` : `Provider: ${meta?.label || payload.provider}`);
    }
    if (payload.provider_group) {
      providerLabelParts.push(getCurrentLocale() === "ru" ? `Группа: ${meta?.group || payload.provider_group}` : `Group: ${meta?.group || payload.provider_group}`);
    }
    if (payload.local_provider) {
      providerLabelParts.push(getCurrentLocale() === "ru" ? "Локальный провайдер" : "Local provider");
    }
    if (payload.experimental) {
      providerLabelParts.push(getCurrentLocale() === "ru" ? "Экспериментально" : "Experimental");
    }
    if (payload.used_default_prompt) {
      providerLabelParts.push(getCurrentLocale() === "ru" ? "Prompt по умолчанию" : "Default prompt");
    }
    entry.providerLabel = providerLabelParts.join(" | ");
    entry.statusMessage = payload.status_message || "";
    renderTranslationResults();
  };

  window.onSubtitlePayloadEvent = (payload) => {
    window.AppState.subtitlePayload = payload;
    renderSubtitlePreview();
  };

  window.onRuntimeEvent = (payload) => {
    setRuntime(payload);
  };

  renderTranslationProviderOptions();
  renderTranslationLanguageOptions();
  renderRecognitionLanguageOptions();
  renderSubtitleStylePresetOptions();
  initializeTabs();

  if (audioInputSelect) {
    audioInputSelect.addEventListener("change", () => {
      setSelectedAudioInput(audioInputSelect.value || null);
    });
  }

  if (recognitionModeSelect) {
    recognitionModeSelect.addEventListener("change", () => {
      syncRecognitionConfigFromControls();
      log(`[asr] mode -> ${getRecognitionModeLabel(window.AppState.config?.asr?.mode || recognitionModeSelect.value)}`);
    });
  }

  if (recognitionLanguageSelect) {
    recognitionLanguageSelect.addEventListener("change", () => {
      syncRecognitionConfigFromControls();
      log(`[asr] browser recognition language -> ${recognitionLanguageSelect.value}`);
    });
  }

  if (translationEnabled) {
    translationEnabled.addEventListener("change", () => {
      syncTranslationConfigFromControls();
      log(`[translation] ${translationEnabled.checked ? "enabled" : "disabled"}`);
    });
  }

  if (translationProvider) {
    translationProvider.addEventListener("change", () => {
      syncTranslationConfigFromControls();
      log(`[translation] provider -> ${translationProvider.value}`);
    });
  }

  if (translationApiKey) {
    translationApiKey.addEventListener("input", syncTranslationConfigFromControls);
  }

  if (translationBaseUrl) {
    translationBaseUrl.addEventListener("input", syncTranslationConfigFromControls);
  }

  if (translationGasUrl) {
    translationGasUrl.addEventListener("input", syncTranslationConfigFromControls);
  }

  if (translationEndpoint) {
    translationEndpoint.addEventListener("input", syncTranslationConfigFromControls);
  }

  if (translationRegion) {
    translationRegion.addEventListener("input", syncTranslationConfigFromControls);
  }

  if (translationApiUrl) {
    translationApiUrl.addEventListener("input", syncTranslationConfigFromControls);
  }

  if (translationModel) {
    translationModel.addEventListener("input", syncTranslationConfigFromControls);
  }

  if (translationCustomPrompt) {
    translationCustomPrompt.addEventListener("input", syncTranslationConfigFromControls);
  }

  if (translationLangAddBtn) {
    translationLangAddBtn.addEventListener("click", () => {
      const code = translationLanguageSelect?.value;
      if (!code || !window.AppState.config) return;
      const targetLanguages = window.AppState.config.translation.target_languages;
      if (!targetLanguages.includes(code)) {
        targetLanguages.push(code);
      }
      window.AppState.selectedTranslationLanguage = code;
      syncTranslationConfigFromControls();
      log(`[translation] added target ${code}`);
    });
  }

  if (translationLangRemoveBtn) {
    translationLangRemoveBtn.addEventListener("click", () => {
      if (!window.AppState.config || !window.AppState.selectedTranslationLanguage) return;
      window.AppState.config.translation.target_languages =
        window.AppState.config.translation.target_languages.filter(
          (item) => item !== window.AppState.selectedTranslationLanguage
        );
      window.AppState.selectedTranslationLanguage = window.AppState.config.translation.target_languages[0] || null;
      syncTranslationConfigFromControls();
      log("[translation] removed target language");
    });
  }

  if (translationLangUpBtn) {
    translationLangUpBtn.addEventListener("click", () => {
      if (!window.AppState.config || !window.AppState.selectedTranslationLanguage) return;
      const items = window.AppState.config.translation.target_languages;
      const index = items.indexOf(window.AppState.selectedTranslationLanguage);
      if (index > 0) {
        [items[index - 1], items[index]] = [items[index], items[index - 1]];
        syncTranslationConfigFromControls();
        log("[translation] moved target up");
      }
    });
  }

  if (translationLangDownBtn) {
    translationLangDownBtn.addEventListener("click", () => {
      if (!window.AppState.config || !window.AppState.selectedTranslationLanguage) return;
      const items = window.AppState.config.translation.target_languages;
      const index = items.indexOf(window.AppState.selectedTranslationLanguage);
      if (index >= 0 && index < items.length - 1) {
        [items[index + 1], items[index]] = [items[index], items[index + 1]];
        syncTranslationConfigFromControls();
        log("[translation] moved target down");
      }
    });
  }

  if (subtitleShowSource) {
    subtitleShowSource.addEventListener("change", () => {
      syncSubtitleOutputConfigFromControls();
      log(`[subtitle] source visibility -> ${subtitleShowSource.checked ? "on" : "off"}`);
    });
  }

  if (subtitleShowTranslations) {
    subtitleShowTranslations.addEventListener("change", () => {
      syncSubtitleOutputConfigFromControls();
      log(`[subtitle] translation visibility -> ${subtitleShowTranslations.checked ? "on" : "off"}`);
    });
  }

  if (subtitleMaxTranslations) {
    subtitleMaxTranslations.addEventListener("input", () => {
      syncSubtitleOutputConfigFromControls();
    });
  }

  if (overlayPresetSelect) {
    overlayPresetSelect.addEventListener("change", () => {
      syncSubtitleOutputConfigFromControls();
      updateOverlayPresetHint();
      log(`[overlay] preset -> ${overlayPresetSelect.value}`);
    });
  }

  if (overlayCompactToggle) {
    overlayCompactToggle.addEventListener("change", () => {
      syncSubtitleOutputConfigFromControls();
      log(`[overlay] compact -> ${overlayCompactToggle.checked ? "on" : "off"}`);
    });
  }

  if (obsCcEnabled) {
    obsCcEnabled.addEventListener("change", () => {
      syncObsCcConfigFromControls();
      log(`[obs-cc] enabled -> ${obsCcEnabled.checked ? "on" : "off"}`);
    });
  }

  [
    obsCcHost,
    obsCcPort,
    obsCcPassword,
    obsCcOutputMode,
    obsCcDebugInputName,
    obsCcPartialThrottle,
    obsCcMinPartialDelta,
    obsCcFinalReplaceDelay,
    obsCcClearAfter,
  ]
    .filter(Boolean)
    .forEach((element) => {
      const eventName = element === obsCcOutputMode ? "change" : "input";
      element.addEventListener(eventName, () => {
        syncObsCcConfigFromControls();
      });
    });

  [obsCcDebugEnabled, obsCcDebugSendPartials, obsCcSendPartials, obsCcAvoidDuplicates]
    .filter(Boolean)
    .forEach((element) => {
      element.addEventListener("change", () => {
        syncObsCcConfigFromControls();
      });
    });

  if (subtitleOrderUpBtn) {
    subtitleOrderUpBtn.addEventListener("click", () => {
      if (!window.AppState.config || !window.AppState.selectedSubtitleOrderItem) return;
      const items = window.AppState.config.subtitle_output.display_order;
      const index = items.indexOf(window.AppState.selectedSubtitleOrderItem);
      if (index > 0) {
        [items[index - 1], items[index]] = [items[index], items[index - 1]];
        syncSubtitleOutputConfigFromControls();
        log("[subtitle] moved display item up");
      }
    });
  }

  if (subtitleOrderDownBtn) {
    subtitleOrderDownBtn.addEventListener("click", () => {
      if (!window.AppState.config || !window.AppState.selectedSubtitleOrderItem) return;
      const items = window.AppState.config.subtitle_output.display_order;
      const index = items.indexOf(window.AppState.selectedSubtitleOrderItem);
      if (index >= 0 && index < items.length - 1) {
        [items[index + 1], items[index]] = [items[index], items[index + 1]];
        syncSubtitleOutputConfigFromControls();
        log("[subtitle] moved display item down");
      }
    });
  }

  if (subtitleStylePreset) {
    subtitleStylePreset.addEventListener("change", () => {
      if (!window.AppState.config) return;
      const currentStyle = normalizeSubtitleStyleConfig(window.AppState.config.subtitle_style || {});
      const nextStyle = buildSubtitleStyleFromPreset(subtitleStylePreset.value);
      nextStyle.custom_presets = currentStyle.custom_presets || {};
      window.AppState.config.subtitle_style = normalizeSubtitleStyleConfig(nextStyle);
      syncSubtitleStyleControlsFromConfig();
      syncConfigText();
      renderSubtitlePreview();
      log(`[subtitle-style] preset -> ${subtitleStylePreset.value}`);
    });
  }

  if (styleLineSlotEnabled) {
    styleLineSlotEnabled.addEventListener("change", () => {
      syncSubtitleStyleConfigFromControls();
      log(
        `[subtitle-style] ${getSelectedStyleLineSlot()} override -> ${styleLineSlotEnabled.checked ? "on" : "off"}`
      );
    });
  }

  if (subtitleStyleSaveCustomBtn) {
    subtitleStyleSaveCustomBtn.addEventListener("click", () => {
      saveCurrentStyleAsCustomPreset();
      log("[subtitle-style] custom preset saved locally");
    });
  }

  if (subtitleStyleDeleteCustomBtn) {
    subtitleStyleDeleteCustomBtn.addEventListener("click", () => {
      deleteCurrentCustomStylePreset();
      log("[subtitle-style] custom preset deleted locally");
    });
  }

  if (fontRefreshBtn) {
    fontRefreshBtn.addEventListener("click", async () => {
      await refreshSystemFonts();
      log("[subtitle-style] system font refresh finished");
    });
  }

  [
    styleFontFamily,
    styleFontSize,
    styleFontWeight,
    styleFillColor,
    styleStrokeColor,
    styleStrokeWidth,
    styleShadowColor,
    styleShadowBlur,
    styleShadowOffsetX,
    styleShadowOffsetY,
    styleBackgroundColor,
    styleBackgroundOpacity,
    styleBackgroundPaddingX,
    styleBackgroundPaddingY,
    styleBackgroundRadius,
    styleLineSpacing,
    styleLetterSpacing,
    styleTextAlign,
    styleLineGap,
    styleEffect,
    styleLineSlotFontFamily,
    styleLineSlotFontSize,
    styleLineSlotFontWeight,
    styleLineSlotFillColor,
    styleLineSlotStrokeColor,
    styleLineSlotStrokeWidth,
    styleLineSlotShadowColor,
    styleLineSlotShadowBlur,
    styleLineSlotShadowOffsetX,
    styleLineSlotShadowOffsetY,
    styleLineSlotBackgroundColor,
    styleLineSlotBackgroundOpacity,
    styleLineSlotBackgroundPaddingX,
    styleLineSlotBackgroundPaddingY,
    styleLineSlotBackgroundRadius,
    styleLineSlotLineSpacing,
    styleLineSlotLetterSpacing,
    styleLineSlotTextAlign,
    styleLineSlotEffect,
  ]
    .filter(Boolean)
    .forEach((element) => {
      element.addEventListener("input", syncSubtitleStyleConfigFromControls);
      element.addEventListener("change", () => {
        syncSubtitleStyleConfigFromControls();
        log("[subtitle-style] updated locally");
      });
    });

  [
    rtVadMode,
    rtPartialEmitInterval,
    rtMinSpeech,
    rtMaxSegment,
    rtSilenceHold,
    rtFinalizationHold,
    rtChunkWindow,
    rtChunkOverlap,
    rtEnergyGateEnabled,
    rtMinRms,
    rtMinVoicedRatio,
    rtFirstPartialMinSpeech,
    rtPartialMinDelta,
    rtPartialCoalescing,
    subtitleCompletedSourceTtl,
    subtitleCompletedTranslationTtl,
    subtitleSyncSourceTranslationExpiry,
    subtitleAllowEarlyReplace,
  ]
    .filter(Boolean)
    .forEach((element) => {
      element.addEventListener("input", () => {
        syncRealtimeConfigFromControls();
      });
      element.addEventListener("change", () => {
        syncRealtimeConfigFromControls();
        log("[asr] realtime tuning updated locally");
      });
    });

  [
    simpleAppearanceSpeed,
    simpleFinishSpeed,
    simpleStability,
  ]
    .filter(Boolean)
    .forEach((element) => {
      element.addEventListener("input", () => {
        syncSimpleTuningConfigFromControls();
      });
      element.addEventListener("change", () => {
        syncSimpleTuningConfigFromControls();
        log("[asr] simple tuning updated locally");
      });
    });

  if (asrRnnoiseEnabled) {
    asrRnnoiseEnabled.addEventListener("change", () => {
      syncRealtimeConfigFromControls();
      log(
        `[asr] rnnoise -> ${asrRnnoiseEnabled.checked ? "on" : "off"}`
      );
    });
  }

  if (asrRnnoiseStrength) {
    asrRnnoiseStrength.addEventListener("input", () => {
      syncRealtimeConfigFromControls();
    });
    asrRnnoiseStrength.addEventListener("change", () => {
      syncRealtimeConfigFromControls();
      log(`[asr] rnnoise strength -> ${asrRnnoiseStrength.value}%`);
    });
  }

  if (uiLanguageSelect) {
    uiLanguageSelect.addEventListener("change", () => {
      window.I18n?.setLocale?.(uiLanguageSelect.value);
    });
  }

  window.addEventListener("sst:locale-changed", () => {
    applyLanguageToUi();
    if (window.AppState.audioDevices?.length) {
      renderAudioInputs(window.AppState.audioDevices);
    }
  });
  document.addEventListener("sst:desktop-context", (event) => {
    applyDesktopContext(event.detail || null);
  });

  applyLanguageToUi();
  try {
    const versionInfo = await window.Api.getVersionInfo();
    window.AppState.versionInfo = versionInfo || null;
    renderProjectVersionInfo(versionInfo);
  } catch (_error) {
    renderProjectVersionInfo(null);
  }

  const health = await window.Api.getHealth();
  if (healthBadge) {
    const asrSuffix = typeof health.asr_ready === "boolean"
      ? `, ${getCurrentLocale() === "ru" ? "ASR" : "asr"}: ${health.asr_ready ? (getCurrentLocale() === "ru" ? "готов" : "ready") : (getCurrentLocale() === "ru" ? "не готов" : "not ready")}`
      : "";
    healthBadge.textContent = t("runtime.badge.health", { value: `${health.status}${asrSuffix}` });
  }
  if (health?.asr_message) {
    log(`[asr] ${health.asr_message}`);
  }
  if (health?.translation_diagnostics?.summary) {
    log(`[translation] ${health.translation_diagnostics.summary}`);
  }
  renderDiagnostics(
    health?.asr_diagnostics || null,
    health?.translation_diagnostics || null,
    window.AppState.runtime?.metrics || null,
    health?.obs_caption_diagnostics || null
  );

  const obs = await window.Api.getObsUrl();
  if (overlayText) {
    overlayText.textContent = obs.overlay_url;
  }
  if (overlayLink) {
    overlayLink.textContent = obs.overlay_url;
    overlayLink.href = obs.overlay_url;
    overlayLink.addEventListener("click", async (event) => {
      if (!isDesktopMode()) {
        return;
      }
      event.preventDefault();
      const opened = await openExternalUrl(overlayLink.href || obs.overlay_url);
      if (!opened) {
        log(getCurrentLocale() === "ru"
          ? "[overlay] не удалось открыть локальный OBS overlay URL"
          : "[overlay] failed to open local OBS overlay URL");
      }
    });
  }

  const desktopContextPromise = window.DesktopBridge?.getContext?.();
  if (desktopContextPromise?.then) {
    desktopContextPromise.then((context) => {
      applyDesktopContext(context);
    }).catch(() => {
      // keep browser mode behavior unchanged if desktop bridge is unavailable
    });
  }

  const settings = await window.Api.loadSettings();
  window.AppState.uiLanguage = getCurrentLocale();
  applyLanguageToUi();
  setSubtitleStylePresets(settings.subtitle_style_presets || {});
  setFontCatalog(settings.font_catalog || {});
  setConfig(settings.payload);
  refreshSystemFonts().catch(() => {
    // keep font picker usable with project-local + fallback fonts only
  });
  await refreshProfiles();

  const audioInputs = await window.Api.getAudioInputs();
  renderAudioInputs(audioInputs.devices);
  renderTranscript();
  renderTranslationResults();
  renderSubtitlePreview();

  if (startBtn) {
    startBtn.addEventListener("click", async () => {
      const pendingBrowserPopup =
        (window.AppState.config?.asr?.mode || "local") === "browser_google" && !isDesktopMode()
          ? openBrowserAsrWindowPlaceholder()
          : null;
      const saveResponse = await saveCurrentConfig();
      if (!saveResponse) {
        if (pendingBrowserPopup && !pendingBrowserPopup.closed) {
          pendingBrowserPopup.close();
        }
        return;
      }
      const activeMode = window.AppState.config?.asr?.mode || "local";
      const deviceId = activeMode === "browser_google" ? null : window.AppState.selectedAudioInputId;
      setRuntime({
        ...(window.AppState.runtime || {}),
        is_running: false,
        status: "starting",
        status_message: activeMode === "browser_google"
          ? (getCurrentLocale() === "ru" ? "Подготавливается browser speech worker..." : "Preparing browser speech worker...")
          : (getCurrentLocale() === "ru" ? "Подготавливается ASR runtime..." : "Preparing ASR runtime..."),
        last_error: null,
      });
      try {
        const data = await window.Api.startRuntime(deviceId);
        setRuntime(data.runtime);
        if (activeMode === "browser_google") {
          await navigateBrowserAsrWindow();
        }
        const detail = data.runtime?.last_error
          ? ` | ${normalizeExternalMessage(data.runtime.last_error)}`
          : data.runtime?.status_message
            ? ` | ${data.runtime.status_message}`
            : "";
        log(`[ui] runtime start -> ${data.runtime.status}${deviceId ? ` (device ${deviceId})` : ""}${detail}`);
      } catch (error) {
        if (pendingBrowserPopup && !pendingBrowserPopup.closed) {
          pendingBrowserPopup.close();
        }
        const message = error instanceof Error ? error.message : (getCurrentLocale() === "ru" ? "Не удалось запустить runtime." : "Runtime start failed.");
        setRuntime({
          ...(window.AppState.runtime || {}),
          is_running: false,
          status: "error",
          status_message: null,
          last_error: message,
        });
        log(`[ui] runtime start failed -> ${message}`);
      }
    });
  }

  if (stopBtn) {
    stopBtn.addEventListener("click", async () => {
      const data = await window.Api.stopRuntime();
      setRuntime(data.runtime);
      window.AppState.transcript.partial = "";
      renderTranscript();
      log("[ui] runtime stopped");
    });
  }

  if (configSaveBtn) {
    configSaveBtn.addEventListener("click", async () => {
      await saveCurrentConfig();
    });
  }

  if (globalSaveBtn) {
    globalSaveBtn.addEventListener("click", async () => {
      await saveCurrentConfig();
    });
  }

  if (configExportBtn) {
    configExportBtn.addEventListener("click", () => {
      try {
        const payload = ensureConfigShape(parseConfigEditor());
        downloadJson("config.export.json", payload);
        log(getCurrentLocale() === "ru" ? "[config] экспорт выполнен" : "[config] exported");
      } catch (_error) {
        log(getCurrentLocale() === "ru" ? "[config] экспорт отменён: некорректный JSON" : "[config] invalid JSON, export canceled");
      }
    });
  }

  if (configImportBtn) {
    configImportBtn.addEventListener("click", async () => {
      const file = configImportInput?.files?.[0];
      if (!file) {
        log("[config] choose a JSON file first");
        return;
      }
      const text = await file.text();
      try {
        const payload = ensureConfigShape(JSON.parse(text));
        const response = await window.Api.saveSettings(payload);
        setSubtitleStylePresets(response.subtitle_style_presets || window.AppState.subtitleStylePresets);
        setFontCatalog(response.font_catalog || window.AppState.fontCatalog);
        setConfig(response.payload || payload);
        maybeReportGoogleKeyNormalization(payload, response.payload || payload);
        renderAudioInputs(audioInputs.devices);
        log(`[config] imported, saved${response.live_applied ? ", and applied live" : ""}`);
      } catch (_error) {
        log("[config] import failed (invalid JSON)");
      }
    });
  }

  if (profileLoadBtn) {
    profileLoadBtn.addEventListener("click", async () => {
      const name = profilesSelect?.value;
      if (!name) return;
      const data = await window.Api.loadProfile(name);
      const payload = ensureConfigShape(data.payload);
      const response = await window.Api.saveSettings(payload);
      setSubtitleStylePresets(response.subtitle_style_presets || window.AppState.subtitleStylePresets);
      setFontCatalog(response.font_catalog || window.AppState.fontCatalog);
      setConfig(response.payload || payload);
      maybeReportGoogleKeyNormalization(payload, response.payload || payload);
      await refreshProfiles();
      renderAudioInputs(audioInputs.devices);
      log(`[profiles] loaded '${name}'${response.live_applied ? " and applied live" : ""}`);
    });
  }

  if (profileSaveBtn) {
    profileSaveBtn.addEventListener("click", async () => {
      const name = profileNameInput?.value?.trim();
      if (!name) {
        log("[profiles] enter profile name first");
        return;
      }
      try {
        const payload = ensureConfigShape(parseConfigEditor());
        payload.profile = name;
        const response = await window.Api.saveProfile(name, payload);
        await refreshProfiles();
        if (profilesSelect) {
          profilesSelect.value = name;
        }
        setConfig(response.payload || payload);
        maybeReportGoogleKeyNormalization(payload, response.payload || payload);
        log(`[profiles] saved '${name}'`);
      } catch (_error) {
        log("[profiles] save failed (invalid JSON or name)");
      }
    });
  }

  if (profileDeleteBtn) {
    profileDeleteBtn.addEventListener("click", async () => {
      const name = profilesSelect?.value;
      if (!name) return;
      const result = await window.Api.deleteProfile(name);
      if (!result.deleted) {
        log(`[profiles] delete skipped for '${name}'`);
        return;
      }
      if (window.AppState.config?.profile === name) {
        window.AppState.config.profile = "default";
        const response = await window.Api.saveSettings(ensureConfigShape(window.AppState.config));
        setSubtitleStylePresets(response.subtitle_style_presets || window.AppState.subtitleStylePresets);
        setFontCatalog(response.font_catalog || window.AppState.fontCatalog);
        setConfig(response.payload || window.AppState.config);
      }
      await refreshProfiles();
      log(`[profiles] deleted '${name}'`);
    });
  }

  const runtimeStatus = await window.Api.getRuntimeStatus();
  setRuntime(runtimeStatus);
  setInterval(async () => {
    try {
      const status = await window.Api.getRuntimeStatus();
      setRuntime(status);
    } catch (_error) {
      // keep UI stable on transient polling failures
    }
  }, 1200);

  window.__appLog = log;
  window.__persistDashboardLog = persistDashboardLog;
  window.WsClient.connect();
})();
