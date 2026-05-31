"""List CJK locale keys still identical to merged English catalog."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.test_i18n_dynamic_locales import _extract_en_catalog, _load_locale

USER_FACING_PREFIXES = (
    "overlay.",
    "translation.",
    "style.",
    "subtitles.",
    "obs.",
    "tuning.",
    "tools.advanced.",
    "asr.",
    "runtime.",
    "settings.",
)


def main() -> None:
    english = _extract_en_catalog()
    for locale in ("ja", "ko", "zh"):
        payload = _load_locale(locale)
        same = [
            k
            for k in english
            if k in payload
            and payload[k] == english[k]
            and any(k.startswith(p) for p in USER_FACING_PREFIXES)
            and len(english[k]) > 12
        ]
        print(f"\n{locale}: {len(same)} user-facing keys still English")
        for k in sorted(same):
            print(f"  {k}")


if __name__ == "__main__":
    main()
