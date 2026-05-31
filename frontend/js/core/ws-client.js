import {
  createWsStaleGuardState,
  isWsEventStale,
  normalizeWsEventType,
} from "./ws-stale-guard-logic.js";

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
    this._staleGuard = createWsStaleGuardState();
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
    return isWsEventStale(this._staleGuard, eventType, payload);
  }

  handleMessage(rawData) {
    try {
      const message = JSON.parse(rawData);
      const type = normalizeWsEventType(message?.type);
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
