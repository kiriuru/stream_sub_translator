/**
 * Log burst throttling for recognition start / appendLog.
 */
(function attachSstBrowserAsrLogThrottle(global) {
  "use strict";

  const root = (global.SstBrowserAsr = global.SstBrowserAsr || {});

  root.shouldThrottleAppendLog = function shouldThrottleAppendLog(throttleState, throttleKey, minGapMs, nowMs) {
    if (!throttleKey || !minGapMs) {
      return false;
    }
    const map = throttleState instanceof Map ? throttleState : null;
    if (!map) {
      return false;
    }
    const last = Number(map.get(throttleKey) || 0);
    return Boolean(last && nowMs - last < minGapMs);
  };

  root.recordThrottledAppendLog = function recordThrottledAppendLog(throttleState, throttleKey, nowMs) {
    if (!throttleState || !(throttleState instanceof Map) || !throttleKey) {
      return;
    }
    throttleState.set(throttleKey, nowMs);
  };

  root.recognitionStartBurstThrottle = function recognitionStartBurstThrottle(reason, recognitionStartLogMinGapMs) {
    const raw = String(reason || "")
      .trim()
      .toLowerCase()
      .replace(/-/g, "_");
    const burst = raw === "no_speech" || raw === "nospeech" || raw === "normal_onend";
    const gapMs = Math.max(500, Number(recognitionStartLogMinGapMs || 4200));
    if (!burst) {
      return { gapMs, key: null };
    }
    return { gapMs, key: `recognition-start:${raw}` };
  };
})(typeof window !== "undefined" ? window : globalThis);
