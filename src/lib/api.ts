import type { ConfigPayload, RuntimeStatus, VersionInfo } from "./types";

/** Dashboard HTTP calls hit the embedded Rust Axum server (`/api/*`), not Python. */

async function jsonFetch<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch (err) {
    const reason = err instanceof Error ? err.message : String(err);
    if (/failed to fetch|networkerror|load failed/i.test(reason)) {
      throw new Error(
        `${url} -> backend unavailable (${reason}). Is VoiceSub running at http://127.0.0.1:8765 ?`,
      );
    }
    throw err instanceof Error ? err : new Error(reason);
  }
  if (!res.ok) {
    let detail = "";
    try {
      const body = (await res.json()) as { message?: string };
      if (body?.message) detail = `: ${body.message}`;
    } catch {
      // ignore non-json error bodies
    }
    throw new Error(`${url} -> ${res.status}${detail}`);
  }
  return res.json() as Promise<T>;
}

export async function loadSettings(): Promise<{
  ok: boolean;
  payload: ConfigPayload;
  loaded_from?: string;
  subtitle_style_presets?: import("./types").StylePresetCatalog;
  font_catalog?: import("./types").FontCatalog;
}> {
  return jsonFetch("/api/settings/load");
}

export async function saveSettings(payload: ConfigPayload): Promise<{
  ok: boolean;
  message?: string;
  payload?: ConfigPayload;
  subtitle_style_presets?: import("./types").StylePresetCatalog;
  font_catalog?: import("./types").FontCatalog;
  live_applied?: boolean;
}> {
  return jsonFetch("/api/settings/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ payload }),
  });
}

export async function startRuntime(configPayload?: ConfigPayload): Promise<{ ok: boolean; runtime: RuntimeStatus }> {
  return jsonFetch("/api/runtime/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ config_payload: configPayload ?? null }),
  });
}

export async function stopRuntime(): Promise<{ ok: boolean; runtime: RuntimeStatus }> {
  return jsonFetch("/api/runtime/stop", { method: "POST" });
}

export async function fetchRuntimeStatus(): Promise<RuntimeStatus> {
  return jsonFetch("/api/runtime/status");
}

export async function fetchObsUrl(): Promise<{ overlay_url: string }> {
  return jsonFetch("/api/obs/url");
}

export async function fetchVersion(): Promise<VersionInfo> {
  return jsonFetch("/api/version");
}

export async function checkUpdates(): Promise<VersionInfo> {
  return jsonFetch("/api/updates/check", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
}

export async function fetchHealth(): Promise<Record<string, unknown>> {
  return jsonFetch("/api/health");
}

export async function listProfiles(): Promise<{ profiles: string[] }> {
  return jsonFetch("/api/profiles");
}

export async function loadProfile(name: string): Promise<{ name: string; payload: ConfigPayload }> {
  return jsonFetch(`/api/profiles/${encodeURIComponent(name)}`);
}

export async function saveProfile(
  name: string,
  payload: ConfigPayload,
): Promise<{ name: string; saved_to?: string; payload: ConfigPayload }> {
  return jsonFetch(`/api/profiles/${encodeURIComponent(name)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ payload }),
  });
}

export async function deleteProfile(name: string): Promise<{ name: string; deleted: boolean }> {
  const res = await fetch(`/api/profiles/${encodeURIComponent(name)}`, { method: "DELETE" });
  if (!res.ok) {
    throw new Error(`delete profile -> ${res.status}`);
  }
  return res.json() as Promise<{ name: string; deleted: boolean }>;
}

export async function downloadDiagnostics(): Promise<void> {
  const res = await fetch("/api/exports/diagnostics");
  if (!res.ok) {
    throw new Error(`diagnostics export -> ${res.status}`);
  }
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="([^"]+)"/);
  const filename = match?.[1] || "voicesub-diagnostics.zip";
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function postClientLog(channel: string, message: string, details?: Record<string, unknown>): Promise<void> {
  await fetch("/api/logs/client-event", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ channel, message, details }),
  }).catch(() => {});
}

export async function openTtsModule(): Promise<void> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("tts_open_window");
}

export async function openExternalUrl(url: string): Promise<void> {
  const trimmed = url.trim();
  if (!trimmed) {
    return;
  }
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    await invoke("open_external_https_url", { url: trimmed });
  } catch {
    window.open(trimmed, "_blank", "noopener,noreferrer");
  }
}

export async function openLocalUrl(url: string): Promise<void> {
  const trimmed = url.trim();
  if (!trimmed) {
    return;
  }
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    await invoke("open_local_http_url", { url: trimmed });
  } catch {
    window.open(trimmed, "_blank", "noopener,noreferrer");
  }
}

export async function listRecommendedOpenAiModels(): Promise<{ models: string[]; recommended?: boolean }> {
  return jsonFetch("/api/openai/recommended-models");
}
