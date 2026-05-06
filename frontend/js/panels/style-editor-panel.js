import { subscribe } from "../core/store.js";
import { clone, getCurrentLocale } from "../dashboard/helpers.js";

function normalizeStyle(config, presets) {
  return window.SubtitleStyleRenderer
    ? window.SubtitleStyleRenderer.normalizeStyleConfig(config || {}, presets || {})
    : (config || {});
}

function buildStyleFromPreset(presets, presetName) {
  return window.SubtitleStyleRenderer
    ? window.SubtitleStyleRenderer.buildStyleFromPreset(presets || {}, presetName)
    : {};
}

export function mountStyleEditorPanel(root, { store, actions, logger }) {
  const elements = {
    preset: root.querySelector("#subtitle-style-preset"),
    customName: root.querySelector("#subtitle-style-custom-name"),
    saveCustomBtn: root.querySelector("#subtitle-style-save-custom-btn"),
    deleteCustomBtn: root.querySelector("#subtitle-style-delete-custom-btn"),
    description: root.querySelector("#subtitle-style-preset-description"),
    status: root.querySelector("#subtitle-style-custom-status"),
    fontRefreshBtn: root.querySelector("#font-refresh-btn"),
    projectFontsDir: root.querySelector("#project-fonts-dir"),
    fontSourceStatus: root.querySelector("#font-source-status"),
    fields: {
      font_family: root.querySelector("#style-font-family"),
      font_size_px: root.querySelector("#style-font-size"),
      font_weight: root.querySelector("#style-font-weight"),
      fill_color: root.querySelector("#style-fill-color"),
      stroke_color: root.querySelector("#style-stroke-color"),
      stroke_width_px: root.querySelector("#style-stroke-width"),
      shadow_color: root.querySelector("#style-shadow-color"),
      shadow_blur_px: root.querySelector("#style-shadow-blur"),
      shadow_offset_x_px: root.querySelector("#style-shadow-offset-x"),
      shadow_offset_y_px: root.querySelector("#style-shadow-offset-y"),
      background_color: root.querySelector("#style-background-color"),
      background_opacity: root.querySelector("#style-background-opacity"),
      background_padding_x_px: root.querySelector("#style-background-padding-x"),
      background_padding_y_px: root.querySelector("#style-background-padding-y"),
      background_radius_px: root.querySelector("#style-background-radius"),
      line_spacing_em: root.querySelector("#style-line-spacing"),
      letter_spacing_em: root.querySelector("#style-letter-spacing"),
      text_align: root.querySelector("#style-text-align"),
      line_gap_px: root.querySelector("#style-line-gap"),
      effect: root.querySelector("#style-effect"),
    },
  };

  function updateStyle(mutator) {
    actions.mutateConfig((draft) => {
      const style = normalizeStyle(draft.subtitle_style, store.getState().subtitleStylePresets);
      const nextStyle = clone(style);
      mutator(nextStyle);
      draft.subtitle_style = normalizeStyle(nextStyle, store.getState().subtitleStylePresets);
    });
  }

  function render(snapshot) {
    const presets = snapshot.subtitleStylePresets || {};
    const style = normalizeStyle(snapshot.config?.subtitle_style, presets);
    if (elements.preset) {
      if (!elements.preset.options.length) {
        const entries = Object.entries(presets);
        entries.forEach(([presetName, preset]) => {
          const option = document.createElement("option");
          option.value = presetName;
          option.textContent = preset.label || presetName;
          elements.preset.appendChild(option);
        });
      }
      elements.preset.value = style.preset || "clean_default";
    }
    if (elements.description) {
      elements.description.textContent = style.description || (getCurrentLocale() === "ru" ? "Выберите пресет и подстройте его локально." : "Choose a preset and tweak it locally.");
    }
    if (elements.status) {
      elements.status.textContent = style.built_in === false
        ? (getCurrentLocale() === "ru" ? `Редактируется пользовательский пресет "${style.label || style.preset}".` : `Editing custom preset "${style.label || style.preset}".`)
        : (getCurrentLocale() === "ru" ? `Редактируется встроенный пресет "${style.label || style.preset}".` : `Editing built-in preset "${style.label || style.preset}".`);
    }
    if (elements.projectFontsDir) {
      elements.projectFontsDir.textContent = snapshot.fontCatalog?.project_fonts_dir || "fonts";
    }
    if (elements.fontSourceStatus) {
      elements.fontSourceStatus.textContent = getCurrentLocale() === "ru"
        ? `Шрифтов проекта: ${snapshot.fontCatalog?.project_local?.length || 0}. Системных шрифтов: ${snapshot.fontCatalog?.system?.length || 0}.`
        : `Project-local fonts: ${snapshot.fontCatalog?.project_local?.length || 0}. System fonts: ${snapshot.fontCatalog?.system?.length || 0}.`;
    }
    Object.entries(elements.fields).forEach(([key, element]) => {
      if (!element) {
        return;
      }
      element.value = String(style.base?.[key] ?? "");
    });
  }

  elements.preset?.addEventListener("change", () => {
    updateStyle((style) => {
      const nextStyle = buildStyleFromPreset(store.getState().subtitleStylePresets, elements.preset.value);
      nextStyle.custom_presets = style.custom_presets || {};
      Object.assign(style, nextStyle);
    });
    logger(`[subtitle-style] preset -> ${elements.preset.value}`);
  });
  Object.entries(elements.fields).forEach(([key, element]) => {
    if (!element) {
      return;
    }
    element.addEventListener("input", () => {
      updateStyle((style) => {
        style.base[key] = element.value;
      });
    });
    element.addEventListener("change", () => {
      updateStyle((style) => {
        style.base[key] = element.value;
      });
      logger("[subtitle-style] updated locally");
    });
  });
  elements.saveCustomBtn?.addEventListener("click", async () => {
    const name = String(elements.customName?.value || "").trim();
    if (!name) {
      return;
    }
    updateStyle((style) => {
      const key = `custom_${name.toLowerCase().replace(/[^a-z0-9]+/g, "_")}`;
      const customPresets = clone(style.custom_presets || {});
      customPresets[key] = {
        ...style,
        preset: key,
        label: name,
        built_in: false,
        custom_presets: {},
      };
      style.custom_presets = customPresets;
      style.preset = key;
      style.label = name;
      style.built_in = false;
    });
    await actions.saveCurrentConfig();
    logger("[subtitle-style] custom preset saved and persisted");
  });
  elements.deleteCustomBtn?.addEventListener("click", async () => {
    updateStyle((style) => {
      if (!style.custom_presets?.[style.preset]) {
        return;
      }
      const customPresets = clone(style.custom_presets);
      delete customPresets[style.preset];
      const nextStyle = buildStyleFromPreset(store.getState().subtitleStylePresets, "clean_default");
      Object.assign(style, nextStyle, { custom_presets: customPresets });
    });
    await actions.saveCurrentConfig();
    logger("[subtitle-style] custom preset deleted and persisted");
  });
  elements.fontRefreshBtn?.addEventListener("click", async () => {
    await actions.refreshSystemFonts();
    logger("[subtitle-style] system font refresh finished");
  });

  render(store.getState());
  const unsubscribe = subscribe(render);
  return () => unsubscribe();
}
