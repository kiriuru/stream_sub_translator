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
      this.logger("[ws] connected", { source: "ws" });
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
      this.logger("[ws] disconnected; reconnecting...", { source: "ws" });
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
    const currentSequence = Number(payload.event_sequence ?? payload.sequence);
    const lastSequence = this.sequenceByType.get(eventType);
    if (Number.isFinite(currentSequence)) {
      if (Number.isFinite(lastSequence) && currentSequence < lastSequence) {
        return true;
      }
      this.sequenceByType.set(eventType, currentSequence);
    }
    const updatedAt = Number(payload.created_at_ms) || Date.parse(String(payload.updated_at || payload.timestamp || ""));
    const lastTimestamp = this.timestampByType.get(eventType);
    if (Number.isFinite(updatedAt)) {
      if (Number.isFinite(lastTimestamp) && updatedAt < lastTimestamp) {
        return true;
      }
      this.timestampByType.set(eventType, updatedAt);
    }
    return payload.stale === true;
  }

  handleMessage(rawData) {
    try {
      const message = JSON.parse(rawData);
      const type = normalizeEventType(message?.type);
      if (type === "hello") {
        return;
      }
      if (this.isStale(type, message?.payload)) {
        return;
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
