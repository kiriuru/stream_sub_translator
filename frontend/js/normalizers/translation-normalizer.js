export function normalizeDisplayOrder(languages) {
  return (Array.isArray(languages) ? languages : [])
    .map((item) => String(item || "").trim().toLowerCase())
    .filter((item, index, array) => item && array.indexOf(item) === index);
}

export function normalizeTranslationResult(payload) {
  const current = payload && typeof payload === "object" ? payload : {};
  return {
    sequence: Number.isFinite(Number(current.sequence)) ? Number(current.sequence) : 0,
    source_text: String(current.source_text || ""),
    provider: String(current.provider || ""),
    provider_group: String(current.provider_group || ""),
    status_message: String(current.status_message || ""),
    experimental: current.experimental === true,
    local_provider: current.local_provider === true,
    used_default_prompt: current.used_default_prompt === true,
    is_complete: current.is_complete !== false,
    translations: (Array.isArray(current.translations) ? current.translations : []).map((item) => ({
      slot_id: String(item?.slot_id || "").toLowerCase(),
      label: String(item?.label || ""),
      target_lang: String(item?.target_lang || "").toLowerCase(),
      provider: String(item?.provider || ""),
      provider_group: String(item?.provider_group || ""),
      experimental: item?.experimental === true,
      local_provider: item?.local_provider === true,
      text: String(item?.text || ""),
      success: item?.success !== false,
      error: String(item?.error || ""),
      cached: item?.cached === true,
    })),
  };
}
