from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
JS_ROOT = PROJECT_ROOT / "frontend" / "js"
BROWSER_ASR_LOGIC_DIR = JS_ROOT / "browser-asr"


class BrowserAsrSessionLogicTests(unittest.TestCase):
    def test_logic_modules_exist(self) -> None:
        expected = [
            "session-defaults.js",
            "session-state.js",
            "log-throttle-logic.js",
            "transcript-logic.js",
            "restart-timing-logic.js",
            "degraded-reason-logic.js",
            "health-signals-logic.js",
            "worker-payload-logic.js",
            "recognition-result-logic.js",
            "recognition-error-logic.js",
            "recognition-handlers.js",
            "watchdog-logic.js",
            "socket-bridge.js",
            "overlap-logic.js",
            "visibility-wait-logic.js",
            "mic-permission-bridge.js",
            "wake-lock-bridge.js",
            "network-preflight-bridge.js",
            "recognition-lifecycle.js",
        ]
        missing = [name for name in expected if not (BROWSER_ASR_LOGIC_DIR / name).exists()]
        self.assertEqual(missing, [])

    def test_google_asr_loads_logic_before_session_manager(self) -> None:
        html = (PROJECT_ROOT / "frontend" / "google_asr.html").read_text(encoding="utf-8")
        policy_pos = html.find("browser-web-speech-recognition-policy.js")
        defaults_pos = html.find("browser-asr/session-defaults.js")
        manager_pos = html.find("browser-asr-session-manager.js")
        self.assertGreater(policy_pos, 0)
        self.assertGreater(defaults_pos, policy_pos)
        self.assertGreater(manager_pos, defaults_pos)
        self.assertIn("browser-asr/transcript-logic.js", html)
        self.assertIn("browser-asr/recognition-handlers.js", html)
        self.assertIn("browser-asr/socket-bridge.js", html)
        self.assertIn("browser-asr/recognition-lifecycle.js", html)

    def test_session_manager_delegates_to_sst_browser_asr_namespace(self) -> None:
        manager_js = (JS_ROOT / "browser-asr-session-manager.js").read_text(encoding="utf-8")
        self.assertIn("global.SstBrowserAsr", manager_js)
        self.assertIn("ASR.buildWorkerPayload", manager_js)
        self.assertIn("ASR.normalizeTranscriptText", manager_js)
        self.assertIn("ASR.restartDelayForReason", manager_js)
        self.assertIn("ASR.wireRecognitionHandlers", manager_js)
        self.assertIn("ASR.evaluateWatchdogTick", manager_js)
        self.assertIn("ASR.attachSocketListeners", manager_js)
        self.assertIn("ASR.performControlledStart", manager_js)
        self.assertIn("ASR.acquireWakeLock", manager_js)
        self.assertIn("ASR.transitionToStopping", manager_js)

    def test_transcript_logic_pure_helpers(self) -> None:
        script = r"""
const root = {};
(function (global) {
  const transcript = `
    (function (g) {
      const r = g.SstBrowserAsr = g.SstBrowserAsr || {};
      r.normalizeTranscriptText = function (v) {
        return String(v || "").trim().replace(/\\s+/g, " ");
      };
      r.shouldSuppressDuplicatePartial = function (state, text) {
        const n = r.normalizeTranscriptText(text);
        if (!n) return true;
        if (n === state.currentSegmentLastPartialText) {
          state.duplicatePartialSuppressed = Number(state.duplicatePartialSuppressed || 0) + 1;
          return true;
        }
        return false;
      };
    })(root);
  `;
  eval(transcript);
})(root);
const state = { currentSegmentLastPartialText: "hello", duplicatePartialSuppressed: 0 };
const dup = root.SstBrowserAsr.shouldSuppressDuplicatePartial(state, "hello");
const ok = root.SstBrowserAsr.normalizeTranscriptText("  a   b  ") === "a b";
console.log(JSON.stringify({ dup, ok, count: state.duplicatePartialSuppressed }));
"""
        completed = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout.strip())
        self.assertTrue(payload["dup"])
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["count"], 1)

    def test_logic_scripts_parse_with_node_check(self) -> None:
        for path in sorted(BROWSER_ASR_LOGIC_DIR.glob("*.js")):
            completed = subprocess.run(
                ["node", "--check", str(path.resolve())],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, msg=f"{path.name}: {completed.stderr.strip()}")


if __name__ == "__main__":
    unittest.main()
