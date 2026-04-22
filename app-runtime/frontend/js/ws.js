(function () {
  const logBox = () => document.getElementById("log-box");

  function pushLog(message, options = {}) {
    if (typeof window.__appLog === "function") {
      window.__appLog(message, options);
      return;
    }
    const el = logBox();
    if (!el) return;
    if ("value" in el) {
      el.value += `${message}\n`;
    } else {
      el.textContent += `${message}\n`;
    }
    el.scrollTop = el.scrollHeight;
  }

  function connect() {
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${protocol}://${location.host}/ws/events`);

    ws.addEventListener("open", () => {
      window.AppState.wsConnected = true;
      pushLog("[ws] connected", { source: "ws" });
      ws.send("ping");
    });

    ws.addEventListener("message", (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "hello") {
          return;
        }
        if (data.type === "transcript_update" && typeof window.onTranscriptEvent === "function") {
          if (data.payload?.event === "final") {
            pushLog("[asr] final transcript received", { source: "ws", persist: false });
          }
          window.onTranscriptEvent(data.payload);
          return;
        }
        if (data.type === "transcript_segment_event") {
          if (typeof window.onTranscriptSegmentEvent === "function") {
            window.onTranscriptSegmentEvent(data.payload);
          }
          return;
        }
        if (data.type === "runtime_update" && typeof window.onRuntimeEvent === "function") {
          const nextStatus = String(data.payload?.status || "").trim();
          if (nextStatus) {
            pushLog(`[runtime] status -> ${nextStatus}`, { source: "ws" });
          }
          window.onRuntimeEvent(data.payload);
          return;
        }
        if (data.type === "translation_update" && typeof window.onTranslationEvent === "function") {
          const translationCount = Array.isArray(data.payload?.translations) ? data.payload.translations.length : 0;
          pushLog(`[translation] update (${translationCount})`, { source: "ws", persist: false });
          window.onTranslationEvent(data.payload);
          return;
        }
        if (data.type === "subtitle_payload_update" && typeof window.onSubtitlePayloadEvent === "function") {
          const lifecycle = String(data.payload?.lifecycle_state || "unknown");
          pushLog(`[overlay] payload -> ${lifecycle}`, { source: "ws", persist: false });
          window.onSubtitlePayloadEvent(data.payload);
          return;
        }
        pushLog("[ws] unhandled event received", { source: "ws", persist: false });
      } catch (_error) {
        pushLog("[ws] received a non-JSON event payload", { source: "ws", persist: false });
      }
    });

    ws.addEventListener("close", () => {
      window.AppState.wsConnected = false;
      pushLog("[ws] disconnected; reconnecting...", { source: "ws" });
      setTimeout(connect, 1000);
    });

    ws.addEventListener("error", () => ws.close());
  }

  window.WsClient = { connect, pushLog };
})();
