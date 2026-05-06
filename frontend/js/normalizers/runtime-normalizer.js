export function normalizeRuntimeStatus(payload) {
  const current = payload && typeof payload === "object" ? payload : {};
  return {
    is_running: current.is_running === true,
    status: String(current.status || "idle"),
    status_message: current.status_message == null ? null : String(current.status_message),
    last_error: current.last_error == null ? null : String(current.last_error),
    event_sequence: Number.isFinite(Number(current.event_sequence ?? current.sequence))
      ? Number(current.event_sequence ?? current.sequence)
      : 0,
    created_at_ms: Number.isFinite(Number(current.created_at_ms)) ? Number(current.created_at_ms) : 0,
    asr_diagnostics: current.asr_diagnostics && typeof current.asr_diagnostics === "object" ? { ...current.asr_diagnostics } : null,
    translation_diagnostics: current.translation_diagnostics && typeof current.translation_diagnostics === "object" ? { ...current.translation_diagnostics } : null,
    obs_caption_diagnostics: current.obs_caption_diagnostics && typeof current.obs_caption_diagnostics === "object" ? { ...current.obs_caption_diagnostics } : null,
    metrics: current.metrics && typeof current.metrics === "object" ? { ...current.metrics } : null,
  };
}
