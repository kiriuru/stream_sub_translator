from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from desktop.bootstrap_payload import BOOTSTRAP_RUNTIME_DIR, BOOTSTRAP_RUNTIME_HIDDEN_EXE
from desktop.build_bootstrap_payload import build_bootstrap_payload


class BuildBootstrapPayloadTests(unittest.TestCase):
    def test_payload_contains_only_managed_runtime_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            source_dist = tmp / "dist"
            source_dist.mkdir(parents=True, exist_ok=True)
            (source_dist / "Stream Subtitle Translator.exe").write_text("runtime", encoding="utf-8")
            runtime_dir = source_dist / BOOTSTRAP_RUNTIME_DIR
            runtime_dir.mkdir(parents=True, exist_ok=True)
            (runtime_dir / "backend" / "run.py").parent.mkdir(parents=True, exist_ok=True)
            (runtime_dir / "backend" / "run.py").write_text("print('ok')", encoding="utf-8")

            # These must never be embedded into payload.zip even if they exist beside app-runtime.
            (source_dist / ".venv" / "Scripts").mkdir(parents=True, exist_ok=True)
            (source_dist / ".venv" / "Scripts" / "python.exe").write_text("venv", encoding="utf-8")
            (source_dist / ".python" / "python.exe").parent.mkdir(parents=True, exist_ok=True)
            (source_dist / ".python" / "python.exe").write_text("python", encoding="utf-8")
            (source_dist / "user-data" / "config.json").parent.mkdir(parents=True, exist_ok=True)
            (source_dist / "user-data" / "config.json").write_text("{}", encoding="utf-8")

            output_dir = tmp / "payload-out"
            build_bootstrap_payload(source_dist=source_dist, output_dir=output_dir)

            manifest = json.loads((output_dir / "payload.manifest.json").read_text(encoding="utf-8"))
            paths = {str(item["path"]).replace("\\", "/") for item in manifest.get("files", [])}

            self.assertIn(BOOTSTRAP_RUNTIME_HIDDEN_EXE, paths)
            self.assertTrue(any(path.startswith(f"{BOOTSTRAP_RUNTIME_DIR}/") for path in paths))
            self.assertFalse(any(path.startswith(".venv/") for path in paths))
            self.assertFalse(any(path.startswith(".python/") for path in paths))
            self.assertFalse(any(path.startswith("user-data/") for path in paths))
            self.assertNotIn("Stream Subtitle Translator.exe", paths)


if __name__ == "__main__":
    unittest.main()
