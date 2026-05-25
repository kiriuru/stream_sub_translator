from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import unittest

from desktop.subprocess_trace import (
    SubprocessTraceLog,
    configure_subprocess_trace,
    logged_popen,
    subprocess_trace,
    summarize_subprocess_args,
    summarize_subprocess_env,
)


class SubprocessTraceTests(unittest.TestCase):
    def tearDown(self) -> None:
        import desktop.subprocess_trace as module

        module._instance = None

    def _fresh_logger(self, tmp: Path) -> SubprocessTraceLog:
        import desktop.subprocess_trace as module

        module._instance = None
        return configure_subprocess_trace(tmp)

    def test_summarize_argv_python_c(self) -> None:
        payload = summarize_subprocess_args([sys.executable, "-c", "print('ok')"])
        self.assertEqual(payload["mode"], "python_c")
        self.assertIn("code_preview", payload)

    def test_summarize_env_filters_prefixes(self) -> None:
        env = summarize_subprocess_env(
            {
                "SST_PROJECT_ROOT": "/tmp/proj",
                "UNRELATED": "skip",
                "PYTHONPATH": "/tmp/lib",
            }
        )
        self.assertEqual(env.get("SST_PROJECT_ROOT"), "/tmp/proj")
        self.assertEqual(env.get("PYTHONPATH"), "/tmp/lib")
        self.assertNotIn("UNRELATED", env)

    def test_logged_popen_writes_spawn_and_exit(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            logger = self._fresh_logger(tmp)
            text_lines: list[str] = []
            logger._text_log = text_lines.append  # type: ignore[method-assign]

            process = logged_popen(
                "test_child",
                [sys.executable, "-c", "import sys; sys.exit(42)"],
                cwd=str(tmp),
                watch_exit=True,
                description="unit test exit 42",
            )
            deadline = time.monotonic() + 10.0
            while process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.05)

            deadline = time.monotonic() + 5.0
            trace_path = tmp / "subprocess-trace.jsonl"
            while time.monotonic() < deadline:
                if trace_path.exists():
                    lines = [line for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip()]
                    events = {json.loads(line)["event"] for line in lines}
                    if {"spawn", "exit"}.issubset(events):
                        break
                time.sleep(0.05)

            self.assertTrue(trace_path.exists())
            records = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            events = [record["event"] for record in records]
            self.assertIn("spawn", events)
            self.assertIn("exit", events)
            exit_record = next(record for record in records if record["event"] == "exit")
            self.assertEqual(exit_record["fields"]["return_code"], 42)
            self.assertTrue(any("[subprocess]" in line for line in text_lines))

    def test_subprocess_trace_noop_without_configure(self) -> None:
        import desktop.subprocess_trace as module

        module._instance = None
        subprocess_trace("desktop", "ignored_event", pid=1)
        # Should not raise.

    def test_track_exit_dedupes(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            logger = self._fresh_logger(tmp)
            process = subprocess.Popen(
                [sys.executable, "-c", "pass"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            process.wait()
            logger.track_exit(role="dup", pid=process.pid, return_code=process.returncode, process=process)
            logger.track_exit(role="dup", pid=process.pid, return_code=process.returncode, process=process)
            records = [json.loads(line) for line in logger.path().read_text(encoding="utf-8").splitlines()]
            exit_events = [record for record in records if record.get("event") == "exit"]
            self.assertEqual(len(exit_events), 1)


if __name__ == "__main__":
    unittest.main()
