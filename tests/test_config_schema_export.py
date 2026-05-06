from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.core.config_schema_export import export_config_schema


class ConfigSchemaExportTests(unittest.TestCase):
    def test_export_writes_json_schema_with_config_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "config.schema.json"
            written_path = export_config_schema(target)

            self.assertEqual(written_path, target)
            schema = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(schema["type"], "object")
            self.assertIn("config_version", schema["properties"])
            self.assertIn("asr", schema["properties"])
            self.assertIn("translation", schema["properties"])


if __name__ == "__main__":
    unittest.main()
