from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from backend.config.defaults import build_default_config


def _balanced_realtime_defaults() -> dict[str, Any]:
    asr = build_default_config(prefer_gpu_default=False).get("asr", {})
    realtime = asr.get("realtime", {}) if isinstance(asr, dict) else {}
    return deepcopy(realtime) if isinstance(realtime, dict) else {}


def repair_legacy_custom_asr_realtime(config_path: Path) -> bool:
    """
    Older desktop installs saved ``latency_preset: custom`` with aggressive gates that
  block Parakeet partials (energy gate + high partial_min_delta_chars). Reset to balanced.
    """
    if not config_path.is_file():
        return False
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(payload, dict):
        return False
    asr = payload.get("asr")
    if not isinstance(asr, dict):
        return False
    realtime = asr.get("realtime")
    if not isinstance(realtime, dict):
        return False
    preset = str(realtime.get("latency_preset", "") or "").strip().lower()
    if preset != "custom":
        return False
    energy_gate = bool(realtime.get("energy_gate_enabled"))
    partial_min_delta = int(realtime.get("partial_min_delta_chars", 0) or 0)
    vad_mode = int(realtime.get("vad_mode", 3) or 3)
    if not energy_gate and partial_min_delta < 4 and vad_mode >= 2:
        return False
    asr["realtime"] = _balanced_realtime_defaults()
    config_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True
