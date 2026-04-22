from __future__ import annotations

import json
from pathlib import Path


class DictionaryManager:
    def __init__(self, data_dir: Path) -> None:
        self.file = data_dir / "dictionary_overrides.json"
        data_dir.mkdir(parents=True, exist_ok=True)
        if not self.file.exists():
            self.file.write_text(json.dumps({"overrides": {}, "excluded_terms": []}, indent=2), encoding="utf-8")

    def load(self) -> dict:
        return json.loads(self.file.read_text(encoding="utf-8"))

