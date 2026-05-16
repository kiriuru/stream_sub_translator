/**
 * Parse Web Speech recognition result events (no DOM).
 */
(function attachSstBrowserAsrRecognitionResult(global) {
  "use strict";

  const root = (global.SstBrowserAsr = global.SstBrowserAsr || {});

  root.parseRecognitionResultEvent = function parseRecognitionResultEvent(event) {
    let interimText = "";
    let finalText = "";
    const resultIndex = Number(event?.resultIndex || 0);
    const results = event?.results;
    if (!results || typeof results.length !== "number") {
      return { interimText, finalText, resultIndex };
    }
    for (let index = resultIndex; index < results.length; index += 1) {
      const result = results[index];
      const transcript = String(result?.[0]?.transcript || "").trim();
      if (!transcript) {
        continue;
      }
      if (result.isFinal) {
        finalText = `${finalText} ${transcript}`.trim();
      } else {
        interimText = `${interimText} ${transcript}`.trim();
      }
    }
    return { interimText, finalText, resultIndex };
  };
})(typeof window !== "undefined" ? window : globalThis);
