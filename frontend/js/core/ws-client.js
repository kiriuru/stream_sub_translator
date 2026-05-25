function normalizeEventType(type) {
  const current = String(type || "").trim().toLowerCase();
  if (current === "runtime_update") {
    return "runtime_status";
  }
  if (current === "subtitle_payload_update") {
    return "overlay_update";
  }
  return current;
}

export class WsClient {
  constructor(options = {}) {
    this.url = options.url || null;
    this.onMessage = typeof options.onMessage === "function" ? options.onMessage : () => {};
    this.onStatus = typeof options.onStatus === "function" ? options.onStatus : () => {};
    this.logger = typeof options.logger === "function" ? options.logger : () => {};
    this.socket = null;
    this.reconnectTimer = null;
    this.backoffMs = 1000;
    this.maxBackoffMs = 10000;
    this.sequenceByType = new Map();
    this.timestampByType = new Map();
    this.manualClose = false;
    this.connectionId = 0;
  }

  connect() {
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return;
    }
    const targetUrl = this.url || `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/events`;
    this.manualClose = false;
    this.onStatus("connecting");
    this.connectionId += 1;
    const connectionId = this.connectionId;
    this.socket = new WebSocket(targetUrl);

    this.socket.addEventListener("open", () => {
      if (connectionId !== this.connectionId) {
        return;
      }
      this.backoffMs = 1000;
      this.onStatus("connected");
      this.logger("[ws] connected", {
        source: "ws",
        tracePhase: "ws",
        traceEvent: "client_connected",
        details: { url: targetUrl },
      });
      this.socket?.send("ping");
    });

    this.socket.addEventListener("message", (event) => {
      if (connectionId !== this.connectionId) {
        return;
      }
      this.handleMessage(event.data);
    });

    this.socket.addEventListener("close", () => {
      if (connectionId !== this.connectionId) {
        return;
      }
      this.onStatus("disconnected");
      this.logger("[ws] disconnected; reconnecting...", {
        source: "ws",
        tracePhase: "ws",
        traceEvent: "client_disconnected",
      });
      this.socket = null;
      if (!this.manualClose) {
        this.scheduleReconnect();
      }
    });

    this.socket.addEventListener("error", () => {
      if (connectionId !== this.connectionId) {
        return;
      }
      this.socket?.close();
    });
  }

  disconnect() {
    this.manualClose = true;
    if (this.reconnectTimer !== null) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.socket?.close();
    this.socket = null;
    this.onStatus("disconnected");
  }

  scheduleReconnect() {
    if (this.reconnectTimer !== null) {
      return;
    }
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, this.backoffMs);
    this.backoffMs = Math.min(this.maxBackoffMs, this.backoffMs * 2);
  }

  isStale(eventType, payload) {
    if (!payload || typeof payload !== "object") {
      return false;
    }
    if (payload.stale === true) {
      return true;
    }
    const currentSequence = Number(payload.event_sequence ?? payload.sequence);
    const lastSequence = this.sequenceByType.get(eventType);
    const updatedAt = Number(payload.created_at_ms) || Date.parse(String(payload.updated_at || payload.timestamp || ""));
    const lastTimestamp = this.timestampByType.get(eventType);
    const hasSequence = Number.isFinite(currentSequence);
    const hasLastSequence = Number.isFinite(lastSequence);
    const hasTimestamp = Number.isFinite(updatedAt);
    const hasLastTimestamp = Number.isFinite(lastTimestamp);

    // Timestamp is authoritative for staleness because backend sequence counters
    // intentionally reset to 0 on every runtime stop/start. Without trusting the
    // timestamp first, dashboards drop every event after a Stop/Start until the
    // new session sequences catch up to the previous high-water mark.
    if (hasTimestamp && hasLastTimestamp) {
      if (updatedAt < lastTimestamp) {
        return true;
      }
      if (updatedAt > lastTimestamp) {
        if (hasSequence) {
          this.sequenceByType.set(eventType, currentSequence);
        }
        this.timestampByType.set(eventType, updatedAt);
        return false;
      }
    }
    if (hasSequence && hasLastSequence && currentSequence < lastSequence) {
      return true;
    }
    if (hasSequence) {
      this.sequenceByType.set(eventType, currentSequence);
    }
    if (hasTimestamp) {
      this.timestampByType.set(eventType, updatedAt);
    }
    return false;
  }

  handleMessage(rawData) {
    try {
      const message = JSON.parse(rawData);
      const type = normalizeEventType(message?.type);
      if (type === "hello") {
        return;
      }
      if (this.isStale(type, message?.payload)) {
        this.logger("[ws] dropped stale event", {
          source: "ws",
          persist: false,
          uiTrace: true,
          tracePhase: "ws",
          traceEvent: "stale_drop",
          details: { type },
        });
        return;
      }
      if (type === "runtime_status") {
        const nextStatus = String(message?.payload?.status || "").trim().toLowerCase();
        if (nextStatus) {
          this.logger(`[runtime] status -> ${nextStatus}`, {
            source: "ws",
            tracePhase: "runtime",
            traceEvent: "ws_status",
            details: { status: nextStatus },
          });
        }
      }
      this.onMessage({
        ...message,
        type,
      });
    } catch (_error) {
      this.logger("[ws] received a non-JSON event payload", { source: "ws", persist: false });
    }
  }
}
