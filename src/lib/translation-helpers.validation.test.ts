import { describe, expect, it } from "vitest";
import {
  getDuplicateEnabledTargetLangs,
  getTranslationConfigErrors,
} from "./translation-helpers";
import type { ConfigPayload } from "./types";

const baseConfig: ConfigPayload = {
  translation: {
    enabled: true,
    provider: "google_translate_v2",
    lines: [
      {
        slot_id: "translation_1",
        enabled: true,
        target_lang: "en",
        provider: "google_translate_v2",
      },
      {
        slot_id: "translation_2",
        enabled: true,
        target_lang: "en",
        provider: "google_translate_v2",
      },
    ],
    provider_settings: {},
  },
};

describe("translation config validation", () => {
  it("detects duplicate enabled target languages", () => {
    expect(getDuplicateEnabledTargetLangs(baseConfig)).toEqual(["en"]);
  });

  it("reports missing api keys on save validation", () => {
    const errors = getTranslationConfigErrors(baseConfig);
    expect(errors.some((entry) => entry.startsWith("missing_provider_fields:"))).toBe(true);
  });

  it("skips validation when translation is disabled", () => {
    const disabled = {
      ...baseConfig,
      translation: { ...baseConfig.translation, enabled: false },
    };
    expect(getTranslationConfigErrors(disabled)).toEqual([]);
  });
});
