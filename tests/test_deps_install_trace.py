from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from desktop.deps_install_trace import configure_deps_install_trace, deps_trace


class DepsInstallTraceTests(unittest.TestCase):
    def test_logs_bootstrap_phases(self) -> None:
        with TemporaryDirectory() as raw:
            logs_dir = Path(raw)
            configure_deps_install_trace(logs_dir)
            deps_trace("bootstrap", "ensure_base_environment_begin", installs="base")
            path = logs_dir / "deps-install-trace.jsonl"
            record = json.loads(path.read_text(encoding="utf-8").strip())
            self.assertEqual(record["phase"], "bootstrap")
            self.assertEqual(record["event"], "ensure_base_environment_begin")
