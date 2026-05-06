export function normalizeModelStatus(payload) {
  const current = payload && typeof payload === "object" ? payload : {};
  return {
    status: String(current.status || "unknown"),
    message: String(current.message || ""),
    provider: String(current.provider || ""),
    loaded: current.loaded === true,
    available: current.available !== false,
    degraded: current.degraded === true,
    details: current.details && typeof current.details === "object" ? { ...current.details } : {},
  };
}
