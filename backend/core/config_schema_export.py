from __future__ import annotations

import json
from pathlib import Path

from backend.schemas.config_schema import ConfigSchema


DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "config.schema.json"


def export_config_schema(output_path: Path | None = None) -> Path:
    target_path = output_path or DEFAULT_OUTPUT_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    schema = ConfigSchema.model_json_schema()
    target_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    return target_path


def main() -> None:
    path = export_config_schema()
    print(path)


if __name__ == "__main__":
    main()
