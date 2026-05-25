from __future__ import annotations

import re
import unittest
from pathlib import Path


class DesktopManagedRuntimePackagingTests(unittest.TestCase):
    def test_spec_excludes_local_ai_stack(self) -> None:
        spec_text = (Path(__file__).resolve().parents[1] / "Stream Subtitle Translator.spec").read_text(
            encoding="utf-8"
        )
        self.assertIn("DESKTOP_MANAGED_RUNTIME_EXCLUDES", spec_text)
        self.assertIn('"torch"', spec_text)
        self.assertIn("excludes=DESKTOP_MANAGED_RUNTIME_EXCLUDES", spec_text)

    def test_backend_host_avoids_static_backend_imports(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "desktop" / "backend_host.py").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"^\s*from\s+backend\.", source, flags=re.MULTILINE))
        self.assertIn("importlib.import_module", source)

    def test_build_bootstrap_payload_only_lists_managed_runtime_paths(self) -> None:
        payload_module = (
            Path(__file__).resolve().parents[1] / "desktop" / "bootstrap_payload.py"
        ).read_text(encoding="utf-8")
        self.assertIn("iter_managed_payload_file_entries", payload_module)
        self.assertIn("BOOTSTRAP_RUNTIME_HIDDEN_EXE", payload_module)
        self.assertIn("BOOTSTRAP_RUNTIME_DIR", payload_module)


if __name__ == "__main__":
    unittest.main()
