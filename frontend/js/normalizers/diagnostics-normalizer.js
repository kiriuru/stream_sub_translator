export function normalizeDiagnostics(payload) {
  const current = payload && typeof payload === "object" ? payload : {};
  return {
    provider: String(current.provider || ""),
    selected_device: String(current.selected_device || ""),
    selected_execution_provider: String(current.selected_execution_provider || ""),
    partials_supported: current.partials_supported === true,
    browser_worker: current.browser_worker && typeof current.browser_worker === "object"
      ? { ...current.browser_worker }
      : null,
    message: String(current.message || ""),
    fallback_reason: String(current.fallback_reason || ""),
    cpu_fallback_reason: String(current.cpu_fallback_reason || ""),
    rnnoise_message: String(current.rnnoise_message || ""),
    requested_device_policy: String(current.requested_device_policy || ""),
    torch_built_with_cuda: current.torch_built_with_cuda === true,
    degraded_mode: current.degraded_mode === true,
    raw: current,
  };
}
