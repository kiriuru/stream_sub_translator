"""Re-translate CJK locale keys that still match English after bulk generation."""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LOCALES_DIR = ROOT / "frontend" / "js" / "i18n" / "locales"
TARGETS = {"ja": "ja", "ko": "ko", "zh": "zh-CN"}

from tests.test_i18n_dynamic_locales import _extract_en_catalog  # noqa: E402


def load_locale(code: str) -> dict[str, str]:
    path = LOCALES_DIR / f"{code}.js"
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"window\.__SST_I18N_LOCALES\.{code}\s*=\s*(\{{.*\}});", text, re.S)
    return json.loads(match.group(1))


def write_locale(code: str, mapping: dict[str, str]) -> None:
    path = LOCALES_DIR / f"{code}.js"
    body = json.dumps(mapping, ensure_ascii=False, indent=2)
    path.write_text(
        "\n".join(
            [
                "(function () {",
                "  window.__SST_I18N_LOCALES = window.__SST_I18N_LOCALES || {};",
                f"  window.__SST_I18N_LOCALES.{code} = {body};",
                "})();",
                "",
            ]
        ),
        encoding="utf-8",
    )


def google_translate(text: str, target: str, *, attempts: int = 4) -> str:
    query = urllib.parse.quote(text)
    url = (
        "https://translate.googleapis.com/translate_a/single"
        f"?client=gtx&sl=en&tl={target}&dt=t&q={query}"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "stream-sub-translator-i18n/1.0"})
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
            chunks = payload[0] if isinstance(payload, list) and payload else []
            return "".join(part[0] for part in chunks if isinstance(part, list) and part and part[0])
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
            time.sleep(1.5 * (attempt + 1))
    if last_error:
        raise last_error
    return ""


def main() -> None:
    english = _extract_en_catalog()
    for locale, target in TARGETS.items():
        mapping = load_locale(locale)
        changed = 0
        for key, en_value in english.items():
            if mapping.get(key) != en_value:
                continue
            if not en_value.strip() or not re.search(r"[A-Za-z]", en_value):
                continue
            translated = google_translate(en_value, target)
            if translated and translated != en_value:
                mapping[key] = translated
                changed += 1
        write_locale(locale, mapping)
        print(f"{locale}: retried {changed} keys")

    import subprocess
    import sys

    subprocess.run([sys.executable, str(ROOT / "tools" / "build_i18n_locale_bundle.py")], check=True)


if __name__ == "__main__":
    main()
