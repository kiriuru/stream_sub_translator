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
  // Independent toggle for subtitle-effect tracing so the OBS overlay can run
  // in clean debug=1 mode without the per-frame partial chatter, and vice
  // versa. Enable by adding ?debug-subtitles=1 to the overlay URL, or by
  // setting localStorage.sst_debug_subtitles = "1" once (persists across
  // reloads — handy when the overlay URL is locked behind OBS).
  const subtitleDebugFromUrl = params.get("debug-subtitles") === "1";
  let subtitleDebugFromStorage = false;
  try {
    subtitleDebugFromStorage = window.localStorage && window.localStorage.getItem("sst_debug_subtitles") === "1";
  } catch (_error) {
    subtitleDebugFromStorage = false;
  }
  const subtitleDebugMode = subtitleDebugFromUrl || subtitleDebugFromStorage;
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
    lifecycleState: "idle",
    lastRenderSignature: "",
    lastPayloadStyle: null,
  };

  const debugEntries = [];
  const staleGuards = {
    overlay_update: { lastCreatedAt: 0, lastSequence: 0 },
    transcript_update: { lastCreatedAt: 0, lastSequence: 0 },
  };
  let connectionId = 0;

  function sendUiTracePayload(payload) {
    const body = JSON.stringify(payload);
    fetch("/api/logs/ui-trace", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    }).catch(() => {
      if (typeof navigator?.sendBeacon === "function") {
        try {
          navigator.sendBeacon("/api/logs/ui-trace", new Blob([body], { type: "application/json" }));
        } catch (_error) {
          // ignore fallback errors
        }
      }
    });
  }

  function postOverlayUiTrace(event, fields) {
    sendUiTracePayload({
      surface: "overlay",
      phase: "overlay",
      event: event || "visual_state",
      fields: fields && typeof fields === "object" ? fields : undefined,
    });
  }

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

  // Ring buffer for the last subtitle-effect trace events so a developer can
  // inspect window.__sstOverlaySubtitleTrace from DevTools without re-running
  // the session. The buffer caps at 200 entries — enough to capture a typical
  // utterance worth of partial frames without growing unbounded.
  const SUBTITLE_TRACE_RING_LIMIT = 200;
  const subtitleTraceRing = [];
  if (subtitleDebugMode) {
    window.__sstOverlaySubtitleTrace = subtitleTraceRing;
  }

  function handleSubtitleRenderTrace(event) {
    if (!subtitleDebugMode || !event || typeof event !== "object") {
      return;
    }
    const enriched = { ts: Date.now(), ...event };
    subtitleTraceRing.push(enriched);
    if (subtitleTraceRing.length > SUBTITLE_TRACE_RING_LIMIT) {
      subtitleTraceRing.splice(0, subtitleTraceRing.length - SUBTITLE_TRACE_RING_LIMIT);
    }
    if (event.type === "partial_frame") {
      console.debug(
        `[overlay-subtitles] partial slot=${event.slot} transition=${event.transition} `
          + `shared=${event.shared_length} fresh=${event.fresh_chars} prev_len=${event.previous_text_length} `
          + `cur_len=${event.current_text_length} effect=${event.effect}`
      );
    } else if (event.type === "completed_frame") {
      console.debug(
        `[overlay-subtitles] completed slot=${event.slot} animated=${event.animated} `
          + `text_len=${event.text_length} effect=${event.effect}`
      );
    } else if (event.type === "render_summary") {
      const anomalyTags = (event.anomalies || []).map((a) => a.kind).join(",") || "none";
      console.debug(
        `[overlay-subtitles] summary rows=${event.rows} partials=${event.partial_entries} `
          + `completed=${event.completed_entries} state_carryover=${event.state_carryover} `
          + `since_last_ms=${event.ms_since_last_render} duration_ms=${event.render_duration_ms.toFixed(2)} `
          + `anomalies=${anomalyTags}`
      );
      // Backend persistence: only summaries (one POST per frame max) and only
      // when there is something worth investigating. Per-row partial events
      // would saturate the api-trace log on busy partials.
      if (event.anomalies && event.anomalies.length) {
        postOverlayUiTrace("subtitle_render_anomaly", {
          rows: event.rows,
          partial_entries: event.partial_entries,
          completed_entries: event.completed_entries,
          state_carryover: event.state_carryover,
          ms_since_last_render: event.ms_since_last_render,
          render_duration_ms: event.render_duration_ms,
          anomalies: event.anomalies,
        });
      }
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

  function clearOverlayPresentation(reason) {
    clearLegacyTranscriptState();
    overlayState.completedItems = [];
    overlayState.activePartialText = "";
    if (reason) {
      writeDebug("text hidden", reason);
    }
    render();
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
        lifecycle_state: "idle",
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
      // Forward the backend's lifecycle_state so composeRenderRows can
      // detect the "completed_with_partial" mix and mark the live partial
      // text (sitting inside visible_items[source]) as transient.
      // Without this, the renderer would treat every keystroke as a new
      // completed entry and re-render the whole source line each frame
      // while a translation is visible.
      lifecycle_state: overlayState.lifecycleState || "idle",
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
    } else {
      applyClasses();
      return;
    }
    if (window.SubtitleStyleRenderer && linesContainer) {
      window.SubtitleStyleRenderer.render(linesContainer, payload, {
        overlay: true,
        onRenderTrace: subtitleDebugMode ? handleSubtitleRenderTrace : null,
      });
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
    const createdAt = Number(payload?.created_at_ms) || 0;
    if (Number.isFinite(createdAt) && createdAt > 0 && createdAt < staleGuards.overlay_update.lastCreatedAt) {
      writeDebug("overlay payload", "ignored stale overlay_update");
      return;
    }
    if (Number.isFinite(createdAt) && createdAt > 0) {
      staleGuards.overlay_update.lastCreatedAt = createdAt;
    }
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
    // Capture the backend lifecycle so buildPresentationPayload() can pass
    // it through to the renderer's composeRenderRows — required for the
    // "completed_with_partial" transient-source classification.
    overlayState.lifecycleState = String(payload.lifecycle_state || "idle");
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
    postOverlayUiTrace("visual_state", {
      lifecycle_state: payload.lifecycle_state || "unknown",
      completed_block_visible: Boolean(payload.completed_block_visible),
      visible_item_count: itemTexts.length,
      active_partial: Boolean(overlayState.activePartialText),
      show_source: overlayState.showSource,
      show_translations: overlayState.showTranslations,
      preset: overlayState.preset,
      compact: overlayState.compact,
    });
    render();
  }

  function connect() {
    connectionId += 1;
    const currentConnectionId = connectionId;
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${protocol}://${location.host}/ws/events`);

    ws.addEventListener("open", () => {
      if (currentConnectionId !== connectionId) {
        try {
          ws.close();
        } catch (_error) {
          // ignore
        }
        return;
      }
      writeDebug("ws connected", `profile=${profile}, preset=${overlayState.preset}, debug=${debugMode ? "on" : "off"}`);
    });

    ws.addEventListener("message", (event) => {
      if (currentConnectionId !== connectionId) {
        return;
      }
      try {
        const data = JSON.parse(event.data);
        if (data.type === "transcript_update" && data.payload) {
          const createdAt = Number(data.payload?.created_at_ms) || 0;
          const sequence = Number(data.payload?.event_sequence ?? data.payload?.sequence) || 0;
          if (Number.isFinite(createdAt) && createdAt > 0 && createdAt < staleGuards.transcript_update.lastCreatedAt) {
            return;
          }
          if (Number.isFinite(sequence) && sequence > 0 && sequence < staleGuards.transcript_update.lastSequence) {
            return;
          }
          if (Number.isFinite(createdAt) && createdAt > 0) {
            staleGuards.transcript_update.lastCreatedAt = createdAt;
          }
          if (Number.isFinite(sequence) && sequence > 0) {
            staleGuards.transcript_update.lastSequence = sequence;
          }
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
      if (currentConnectionId !== connectionId) {
        return;
      }
      clearOverlayPresentation("websocket disconnected");
      writeDebug("ws disconnected", "reconnecting in 1s");
      setTimeout(connect, 1000);
    });

    ws.addEventListener("error", () => {
      try {
        ws.close();
      } catch (_error) {
        // ignore
      }
    });
  }

  writeDebug(
    "overlay boot",
    `profile=${profile}, preset=${preset}, compact=${overlayState.compact ? "on" : "off"}`
      + (subtitleDebugMode ? `, subtitle_debug=on (source=${subtitleDebugFromUrl ? "url" : "localStorage"})` : "")
  );
  render();
  connect();
})();
