function redactPayload(value) {
  return window.SSTRedaction?.redactObject ? window.SSTRedaction.redactObject(value) : value;
}

function redactText(value) {
  return window.SSTRedaction?.redactText ? window.SSTRedaction.redactText(value) : String(value || "");
}

function extractFilename(response) {
  const header = String(response.headers.get("content-disposition") || "");
  const match = header.match(/filename=\"?([^\";]+)\"?/i);
  return match ? match[1] : null;
}

function buildApiError(message, response, payload) {
  const error = new Error(redactText(message || "Request failed."));
  error.name = "ApiError";
  error.status = response?.status ?? 0;
  error.payload = payload ?? null;
  error.code = payload?.error?.code || null;
  error.recommendedAction = payload?.error?.recommended_action || null;
  return error;
}

async function parseResponse(response) {
  const contentType = String(response.headers.get("content-type") || "").toLowerCase();
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return response.text();
}

function withTimeout(signal, timeoutMs) {
  const controller = new AbortController();
  let timeoutId = null;

  const abort = () => controller.abort();
  if (signal) {
    if (signal.aborted) {
      controller.abort();
    } else {
      signal.addEventListener("abort", abort, { once: true });
    }
  }
  if (timeoutMs > 0) {
    timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
  }

  return {
    signal: controller.signal,
    cleanup() {
      if (signal) {
        signal.removeEventListener("abort", abort);
      }
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
    },
  };
}

export function createApiClient(options = {}) {
  const baseHeaders = options.baseHeaders || {};
  const busyHook = typeof options.onBusyChange === "function" ? options.onBusyChange : null;

  async function request(method, path, body, requestOptions = {}) {
    const timeoutMs = Number(requestOptions.timeout || 0);
    const busyKey = requestOptions.busyKey || null;
    const timeout = withTimeout(requestOptions.signal, timeoutMs);

    if (busyHook && busyKey) {
      busyHook(busyKey, true);
    }

    try {
      const headers = {
        ...baseHeaders,
        ...(requestOptions.headers || {}),
      };
      const init = {
        method,
        headers,
        signal: timeout.signal,
      };
      if (body !== undefined && body !== null) {
        init.body = body instanceof FormData ? body : JSON.stringify(body);
        if (!(body instanceof FormData)) {
          init.headers["Content-Type"] = "application/json";
        }
      }

      const response = await fetch(path, init);
      const payload = await parseResponse(response);
      if (!response.ok) {
        const message = payload?.error?.message || payload?.message || `HTTP ${response.status}`;
        throw buildApiError(message, response, redactPayload(payload));
      }
      return payload;
    } catch (error) {
      if (error?.name === "AbortError") {
        throw buildApiError("Request timed out or was aborted.", null, null);
      }
      throw error;
    } finally {
      timeout.cleanup();
      if (busyHook && busyKey) {
        busyHook(busyKey, false);
      }
    }
  }

  return {
    apiGet(path, requestOptions = {}) {
      return request("GET", path, null, requestOptions);
    },
    apiPost(path, body, requestOptions = {}) {
      return request("POST", path, body, requestOptions);
    },
    async apiDownload(path, requestOptions = {}) {
      const response = await fetch(path, { method: "GET", signal: requestOptions.signal || null });
      if (!response.ok) {
        throw buildApiError(`Download failed: HTTP ${response.status}`, response, null);
      }
      return {
        blob: await response.blob(),
        filename: extractFilename(response),
      };
    },
    apiUpload(path, file, requestOptions = {}) {
      const form = new FormData();
      form.append("file", file);
      return request("POST", path, form, requestOptions);
    },
  };
}

export function createDashboardApi(client) {
  return {
    getVersionInfo() {
      return client.apiGet("/api/version");
    },
    getHealth() {
      return client.apiGet("/api/health");
    },
    getObsUrl() {
      return client.apiGet("/api/obs/url");
    },
    getRemoteState() {
      return client.apiGet("/api/remote/state");
    },
    createRemotePair(ttlSeconds) {
      return client.apiPost("/api/remote/pair/create", { ttl_seconds: ttlSeconds || 300 });
    },
    verifyRemotePair(sessionId, pairCode) {
      return client.apiPost("/api/remote/pair/verify", {
        session_id: sessionId || "",
        pair_code: pairCode || "",
      });
    },
    sendRemoteHeartbeat(sessionId, role) {
      return client.apiPost("/api/remote/heartbeat", {
        session_id: sessionId || "",
        role: role || "controller",
      });
    },
    startRemoteWorkerRuntime() {
      return client.apiPost("/api/remote/worker/runtime/start", null);
    },
    stopRemoteWorkerRuntime() {
      return client.apiPost("/api/remote/worker/runtime/stop", null);
    },
    getRemoteWorkerRuntimeStatus() {
      return client.apiGet("/api/remote/worker/runtime/status");
    },
    getRemoteWorkerHealth() {
      return client.apiGet("/api/remote/worker/health");
    },
    syncRemoteWorkerSettings() {
      return client.apiPost("/api/remote/worker/settings/sync", null);
    },
    getAudioInputs() {
      return client.apiGet("/api/devices/audio-inputs");
    },
    startRuntime(deviceId) {
      return client.apiPost("/api/runtime/start", { device_id: deviceId || null }, { busyKey: "runtime" });
    },
    stopRuntime() {
      return client.apiPost("/api/runtime/stop", null, { busyKey: "runtime" });
    },
    getRuntimeStatus() {
      return client.apiGet("/api/runtime/status");
    },
    loadSettings() {
      return client.apiGet("/api/settings/load");
    },
    saveSettings(payload) {
      return client.apiPost("/api/settings/save", { payload }, { busyKey: "save" });
    },
    listProfiles() {
      return client.apiGet("/api/profiles");
    },
    loadProfile(name) {
      return client.apiGet(`/api/profiles/${encodeURIComponent(name)}`);
    },
    saveProfile(name, payload) {
      return client.apiPost(`/api/profiles/${encodeURIComponent(name)}`, { payload }, { busyKey: "save" });
    },
    async deleteProfile(name) {
      const response = await fetch(`/api/profiles/${encodeURIComponent(name)}`, { method: "DELETE" });
      if (!response.ok) {
        throw buildApiError(`HTTP ${response.status}`, response, null);
      }
      return response.json();
    },
    postClientLog(payload) {
      return client.apiPost("/api/logs/client-event", payload);
    },
    downloadDiagnosticsBundle() {
      return client.apiDownload("/api/exports/diagnostics");
    },
  };
}
