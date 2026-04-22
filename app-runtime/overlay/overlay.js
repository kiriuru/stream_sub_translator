(function () {
  if (window.I18n) {
    window.I18n.apply(document);
    document.title = window.I18n.t("document.title.overlay");
    window.addEventListener("sst:locale-changed", () => {
      window.I18n.apply(document);
      document.title = window.I18n.t("document.title.overlay");
    });
  }

  const params = new URLSearchParams(location.search);
  const profile = params.get("profile") || "default";
  const compact = params.get("compact") === "1";
  const debugMode = params.get("debug") === "1";
  const presetParam = params.get("preset") || "";
  const preset = ["single", "dual-line", "stacked", "compact"].includes(presetParam) ? presetParam : "single";

  const root = document.getElementById("overlay-root");
  const linesContainer = document.getElementById("overlay-lines");

  const overlayState = {
    preset: preset === "compact" ? "stacked" : preset,
    compact: compact || presetParam === "compact",
    partial: "",
    finals: [],
    completedItems: [],
    activePartialText: "",
    showSource: true,
    showTranslations: true,
    hasOverlayLifecycle: false,
    lastRenderSignature: "",
    lastPayloadStyle: null,
  };

  const debugEntries = [];

  function sendClientLogPayload(payload) {
    const body = JSON.stringify(payload);
    fetch("/api/logs/client-event", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    }).catch(() => {
      if (typeof navigator?.sendBeacon === "function") {
        try {
          navigator.sendBeacon(
            "/api/logs/client-event",
            new Blob([body], { type: "application/json" })
          );
        } catch (_error) {
          // ignore fallback errors
        }
      }
    });
  }

  function postOverlayLog(message, details) {
    const payload = {
      channel: "overlay",
      source: "overlay",
      message: String(message || "").trim(),
    };
    if (!payload.message) {
      return;
    }
    if (details != null) {
      payload.details = typeof details === "object" ? details : { details: String(details) };
    }
    sendClientLogPayload(payload);
  }

  function shouldPersistOverlayLog(message) {
    const normalized = String(message || "").trim().toLowerCase();
    return [
      "overlay boot",
      "overlay payload",
      "ws connected",
      "ws disconnected",
      "text shown",
      "text hidden",
      "text updated",
    ].includes(normalized);
  }

  function writeDebug(message, details) {
    const timestamp = new Date().toLocaleTimeString();
    const suffix = details
      ? ` | ${typeof details === "string" ? details : JSON.stringify(details)}`
      : "";
    const line = `[${timestamp}] ${message}${suffix}`;
    console.log(`[overlay] ${line}`);
    if (shouldPersistOverlayLog(message)) {
      postOverlayLog(message, details);
    }
    if (debugMode) {
      debugEntries.unshift(line);
    }
  }

  function applyClasses() {
    if (!root) {
      return;
    }
    root.className = `overlay ${overlayState.preset}${overlayState.compact ? " compact" : ""}`;
  }

  function clearLegacyTranscriptState() {
    overlayState.partial = "";
    overlayState.finals = [];
  }

  function buildPresentationPayload() {
    const completedItems = overlayState.completedItems.map((item) => ({
      kind: item.kind || "source",
      text: item.text || "",
    }));
    if (!overlayState.hasOverlayLifecycle) {
      const legacyVisibleItems = overlayState.finals.length > 0
        ? overlayState.finals.slice(0, 3).map((text) => ({ kind: "source", text }))
        : [];
      return {
        preset: overlayState.preset,
        compact: overlayState.compact,
        completed_block_visible: legacyVisibleItems.length > 0,
        visible_items: legacyVisibleItems,
        active_partial_text: overlayState.partial,
        show_source: true,
        show_translations: true,
        style: overlayState.lastPayloadStyle || {},
      };
    }
    return {
      preset: overlayState.preset,
      compact: overlayState.compact,
      completed_block_visible: completedItems.length > 0,
      visible_items: completedItems,
      active_partial_text: overlayState.activePartialText,
      show_source: overlayState.showSource,
      show_translations: overlayState.showTranslations,
      style: overlayState.lastPayloadStyle || {},
    };
  }

  function render() {
    const payload = buildPresentationPayload();
    const rows = window.SubtitleStyleRenderer
      ? window.SubtitleStyleRenderer.composeRenderRows(payload)
      : [];
    const renderedTexts = rows.flatMap((row) => row.entries || []).map((entry) => entry.text);
    const signature = JSON.stringify({
      preset: overlayState.preset,
      compact: overlayState.compact,
      completedItems: overlayState.completedItems,
      activePartialText: overlayState.activePartialText,
      style: overlayState.lastPayloadStyle,
      rendered: rows,
    });
    if (signature !== overlayState.lastRenderSignature) {
      const previousHadText = overlayState.lastRenderSignature && overlayState.lastRenderSignature !== JSON.stringify({
        preset: overlayState.preset,
        compact: overlayState.compact,
        completedItems: [],
        activePartialText: "",
        rendered: [],
      });
      if (renderedTexts.length === 0 && previousHadText) {
        writeDebug("text hidden", "overlay became empty");
      } else if (renderedTexts.length > 0 && !previousHadText) {
        writeDebug("text shown", renderedTexts.join(" || "));
      } else if (renderedTexts.length > 0) {
        writeDebug("text updated", renderedTexts.join(" || "));
      }
      overlayState.lastRenderSignature = signature;
    }
    if (window.SubtitleStyleRenderer && linesContainer) {
      window.SubtitleStyleRenderer.render(linesContainer, payload, { overlay: true });
    } else if (linesContainer) {
      linesContainer.textContent = renderedTexts.join("\n");
    }
    applyClasses();
  }

  function applyTranscript(payload) {
    if (overlayState.hasOverlayLifecycle) {
      return;
    }
    overlayState.completedItems = [];
    overlayState.activePartialText = "";
    if (payload.event === "partial") {
      overlayState.partial = payload.text || "";
      writeDebug("transcript partial", overlayState.partial || "<empty>");
    } else if (payload.event === "final") {
      overlayState.partial = "";
      if (payload.text) {
        overlayState.finals.unshift(payload.text);
        overlayState.finals = overlayState.finals.slice(0, 4);
      }
      writeDebug("transcript final", payload.text || "<empty>");
    }
    render();
  }

  function applyOverlayPayload(payload) {
    overlayState.hasOverlayLifecycle = true;
    clearLegacyTranscriptState();
    if (payload.preset && ["single", "dual-line", "stacked"].includes(payload.preset)) {
      overlayState.preset = payload.preset;
    }
    if (typeof payload.compact === "boolean") {
      overlayState.compact = payload.compact;
    }
    const visibleItems = Array.isArray(payload.visible_items) ? payload.visible_items : [];
    const itemTexts = visibleItems.map((item) => item.text).filter(Boolean);
    overlayState.showSource = payload.show_source !== false;
    overlayState.showTranslations = payload.show_translations !== false;
    overlayState.lastPayloadStyle = payload.style && typeof payload.style === "object" ? payload.style : {};

    overlayState.activePartialText = overlayState.showSource
      ? String(payload.active_partial_text || "")
      : "";
    writeDebug("overlay payload", JSON.stringify({
      state: payload.lifecycle_state || "unknown",
      completed: Boolean(payload.completed_block_visible),
      partial: overlayState.activePartialText ? "yes" : "no",
      items: itemTexts.length,
      preset: payload.preset || overlayState.preset,
      show_source: overlayState.showSource,
      show_translations: overlayState.showTranslations,
      max_translation_languages: Number(payload.max_translation_languages || 0),
      display_order: Array.isArray(payload.display_order) ? payload.display_order : [],
      visible_texts: itemTexts,
    }));

    if (payload.completed_block_visible && itemTexts.length > 0) {
      overlayState.completedItems = visibleItems
        .filter((item) => item && item.text)
        .map((item) => ({ kind: item.kind || "source", text: item.text }));
    } else {
      overlayState.completedItems = [];
    }
    render();
  }

  function connect() {
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${protocol}://${location.host}/ws/events`);

    ws.addEventListener("open", () => {
      writeDebug("ws connected", `profile=${profile}, preset=${overlayState.preset}, debug=${debugMode ? "on" : "off"}`);
    });

    ws.addEventListener("message", (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "transcript_update" && data.payload) {
          applyTranscript(data.payload);
          return;
        }
        if (data.type === "overlay_update" && data.payload) {
          applyOverlayPayload(data.payload);
        }
      } catch (_error) {
        // ignore malformed messages in skeleton stage
      }
    });

    ws.addEventListener("close", () => {
      writeDebug("ws disconnected", "reconnecting in 1s");
      setTimeout(connect, 1000);
    });

    ws.addEventListener("error", () => ws.close());
  }

  writeDebug("overlay boot", `profile=${profile}, preset=${preset}, compact=${overlayState.compact ? "on" : "off"}`);
  render();
  connect();
})();
