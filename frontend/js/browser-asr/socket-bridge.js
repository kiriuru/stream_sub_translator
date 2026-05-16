/**
 * ASR worker WebSocket URL, listeners, and control-message parsing.
 */
(function attachSstBrowserAsrSocketBridge(global) {
  "use strict";

  const root = (global.SstBrowserAsr = global.SstBrowserAsr || {});

  root.buildAsrWorkerWebSocketUrl = function buildAsrWorkerWebSocketUrl() {
    const protocol = typeof location !== "undefined" && location.protocol === "https:" ? "wss" : "ws";
    const host = typeof location !== "undefined" ? location.host : "127.0.0.1";
    return `${protocol}://${host}/ws/asr_worker`;
  };

  root.parseBrowserAsrControlMessage = function parseBrowserAsrControlMessage(raw) {
    let message = null;
    try {
      message = JSON.parse(raw);
    } catch (_error) {
      return null;
    }
    if (!message || typeof message !== "object") {
      return null;
    }
    const type = String(message.type || "").trim().toLowerCase();
    if (type !== "browser_asr_control") {
      return null;
    }
    return {
      type,
      action: String(message.action || "").trim().toLowerCase(),
    };
  };

  root.attachSocketListeners = function attachSocketListeners(manager, socket) {
    if (!socket || socket.__sstAttached) {
      return;
    }
    socket.__sstAttached = true;

    socket.addEventListener("open", () => {
      if (manager.state.socket !== socket) {
        return;
      }
      manager.state.websocketReady = true;
      manager.state.socketDegraded = false;
      manager._refreshDegradedReason();
      manager._appendLog("websocket connected");
      manager._updateCounters();
      manager._emitWorkerStatus("socket-open");
      manager._emitHeartbeat("socket-open");
      if (
        manager.state.desiredRunning
        && manager.state.browserSupervisorState !== "running"
        && manager.state.browserSupervisorState !== "starting"
      ) {
        manager._scheduleRestart("websocket_reconnect");
      }
    });

    socket.addEventListener("close", () => {
      if (manager.state.socket !== socket) {
        return;
      }
      manager.state.websocketReady = false;
      manager.state.socketDegraded = Boolean(manager.state.desiredRunning);
      manager._refreshDegradedReason();
      manager._appendLog("websocket closed");
      manager._updateCounters();
      manager.state.socket = null;
      if (manager.state.desiredRunning) {
        manager._setStatus("socket-reconnecting");
        manager.state.reconnectTimer = window.setTimeout(
          () => manager.ensureSocketConnected(),
          manager.restartDelayByReasonMs.websocket_reconnect
        );
      }
    });

    socket.addEventListener("error", () => {
      if (manager.state.socket !== socket) {
        return;
      }
      manager.state.websocketReady = false;
      manager.state.socketDegraded = Boolean(manager.state.desiredRunning);
      manager._refreshDegradedReason();
      manager._appendLog("websocket error");
      manager._updateCounters();
    });

    socket.addEventListener("message", (event) => {
      if (manager.state.socket !== socket) {
        return;
      }
      manager._handleSocketMessage(event.data);
    });
  };
})(typeof window !== "undefined" ? window : globalThis);
