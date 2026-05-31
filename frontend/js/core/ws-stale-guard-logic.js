/**
 * Shared WebSocket event staleness guards for dashboard WsClient and OBS overlay.
 * Timestamp is authoritative when runtime stop/start resets sequence counters to 0.
 */

export function normalizeWsEventType(type) {
  const current = String(type || "").trim().toLowerCase();
  if (current === "runtime_update") {
    return "runtime_status";
  }
  if (current === "subtitle_payload_update") {
    return "overlay_update";
  }
  return current;
}

export function createWsStaleGuardState() {
  return {
    sequenceByType: new Map(),
    timestampByType: new Map(),
  };
}

export function isWsEventStale(guardState, eventType, payload) {
  if (!payload || typeof payload !== "object") {
    return false;
  }
  if (payload.stale === true) {
    return true;
  }
  const currentSequence = Number(payload.event_sequence ?? payload.sequence);
  const lastSequence = guardState.sequenceByType.get(eventType);
  const updatedAt =
    Number(payload.created_at_ms) || Date.parse(String(payload.updated_at || payload.timestamp || ""));
  const lastTimestamp = guardState.timestampByType.get(eventType);
  const hasSequence = Number.isFinite(currentSequence);
  const hasLastSequence = Number.isFinite(lastSequence);
  const hasTimestamp = Number.isFinite(updatedAt);
  const hasLastTimestamp = Number.isFinite(lastTimestamp);

  if (hasTimestamp && hasLastTimestamp) {
    if (updatedAt < lastTimestamp) {
      return true;
    }
    if (updatedAt > lastTimestamp) {
      if (hasSequence) {
        guardState.sequenceByType.set(eventType, currentSequence);
      }
      guardState.timestampByType.set(eventType, updatedAt);
      return false;
    }
  }
  if (hasSequence && hasLastSequence && currentSequence < lastSequence) {
    return true;
  }
  if (hasSequence) {
    guardState.sequenceByType.set(eventType, currentSequence);
  }
  if (hasTimestamp) {
    guardState.timestampByType.set(eventType, updatedAt);
  }
  return false;
}
