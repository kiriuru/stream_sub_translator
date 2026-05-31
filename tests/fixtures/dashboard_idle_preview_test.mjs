globalThis.window = {
  I18n: {
    t(key) {
      return String(key || "").split(".").pop() || key;
    },
  },
};

const {
  buildPreviewPayload,
  hasRenderableOverlayContent,
  shouldUseLiveOverlayPreview,
} = await import("../../frontend/js/dashboard/action-helpers.js");

const getResolvedSubtitleStyle = () => ({ slots: {} });

const config = {
  overlay: { preset: "single", compact: false },
  subtitle_output: {
    show_source: true,
    show_translations: true,
    max_translation_languages: 1,
    display_order: ["source", "en"],
  },
  source_lang: "en",
  translation: {
    lines: [{ slot_id: "en", target_lang: "en", label: "EN", enabled: true }],
  },
  subtitle_style: {},
};

const idleEmptyReplay = {
  config,
  runtime: { is_running: false },
  overlay: {
    payload: {
      visible_items: [],
      completed_block_visible: true,
      active_partial_text: "",
    },
  },
  subtitleStylePresets: {},
};

if (hasRenderableOverlayContent(idleEmptyReplay.overlay.payload)) {
  console.error("empty replay payload must not count as renderable");
  process.exit(1);
}

if (shouldUseLiveOverlayPreview(idleEmptyReplay)) {
  console.error("idle empty replay must not use live overlay preview");
  process.exit(1);
}

const placeholder = buildPreviewPayload(idleEmptyReplay, { getResolvedSubtitleStyle });
if (!placeholder?.visible_items?.length) {
  console.error("expected idle style placeholder visible_items");
  process.exit(1);
}

const runningEmpty = {
  ...idleEmptyReplay,
  runtime: { is_running: true },
};

if (!shouldUseLiveOverlayPreview(runningEmpty)) {
  console.error("running overlay payload must stay on live path");
  process.exit(1);
}

console.log("ok");
