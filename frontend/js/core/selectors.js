export function selectConfig(snapshot) {
  return snapshot?.config ?? null;
}

export function selectRuntime(snapshot) {
  return snapshot?.runtime ?? null;
}

export function selectUi(snapshot) {
  return snapshot?.ui ?? {};
}

export function selectDiagnostics(snapshot) {
  return snapshot?.diagnostics ?? null;
}

export function selectTranslation(snapshot) {
  return snapshot?.translation ?? null;
}

export function selectAsrMode(snapshot) {
  return String(snapshot?.config?.asr?.mode || "local");
}

export function selectProfiles(snapshot) {
  return Array.isArray(snapshot?.profiles) ? snapshot.profiles : [];
}
