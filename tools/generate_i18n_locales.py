"""Generate ja/ko/zh locale bundles from the full English catalog (en.js + dynamic-locales)."""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EN_JS = ROOT / "frontend" / "js" / "i18n" / "locales" / "en.js"
DYNAMIC_JS = ROOT / "frontend" / "js" / "i18n" / "dynamic-locales.js"
OUT_DIR = ROOT / "frontend" / "js" / "i18n" / "locales"
BUNDLE_SCRIPT = ROOT / "tools" / "build_i18n_locale_bundle.py"

TARGETS = {
    "ja": "ja",
    "ko": "ko",
    "zh": "zh-CN",
}

SKIP_PREFIXES = ("def:", "http://", "https://")
MAX_WORKERS = 8


def _parse_object_block(text: str, label: str) -> dict[str, str]:
    match = re.search(rf"{label}\s*=\s*(\{{.*\}});", text, re.S)
    if not match:
        raise SystemExit(f"Could not parse {label} object")
    return dict(re.findall(r'"((?:[^"\\]|\\.)+)"\s*:\s*"((?:[^"\\]|\\.)*)"', match.group(1)))


def load_dynamic_en() -> dict[str, str]:
    text = DYNAMIC_JS.read_text(encoding="utf-8")
    match = re.search(r"en:\s*(\{.*?\})\s*,\s*\n\s*ru:\s*\{", text, re.S)
    if not match:
        raise SystemExit("Could not parse dynamic-locales.js en block")
    return dict(re.findall(r'"((?:[^"\\]|\\.)+)"\s*:\s*"((?:[^"\\]|\\.)*)"', match.group(1)))


def load_english_catalog() -> dict[str, str]:
    catalog = _parse_object_block(EN_JS.read_text(encoding="utf-8"), r"window\.__SST_I18N_LOCALES\.en")
    catalog.update(load_dynamic_en())
    return catalog


def should_translate(value: str) -> bool:
    value = value.strip()
    if not value:
        return False
    if any(value.startswith(prefix) for prefix in SKIP_PREFIXES):
        return False
    return bool(re.search(r"[A-Za-z]", value))


def google_translate(text: str, target: str) -> str:
    query = urllib.parse.quote(text)
    url = (
        "https://translate.googleapis.com/translate_a/single"
        f"?client=gtx&sl=en&tl={target}&dt=t&q={query}"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "stream-sub-translator-i18n/1.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    chunks = payload[0] if isinstance(payload, list) and payload else []
    return "".join(part[0] for part in chunks if isinstance(part, list) and part and part[0])


def translate_unique(values: list[str], target: str) -> dict[str, str]:
    cache: dict[str, str] = {value: value for value in values if not should_translate(value)}
    pending = [value for value in values if value not in cache]

    def _task(value: str) -> tuple[str, str]:
        try:
            return value, google_translate(value, target)
        except Exception:
            return value, value

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [pool.submit(_task, value) for value in pending]
        done = 0
        for future in as_completed(futures):
            source, translated = future.result()
            cache[source] = translated
            done += 1
            if done % 50 == 0:
                print(f"  {target}: {done}/{len(pending)}", flush=True)
    return cache


def write_locale(locale: str, mapping: dict[str, str]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{locale}.js"
    body = json.dumps(mapping, ensure_ascii=False, indent=2)
    path.write_text(
        "\n".join(
            [
                "(function () {",
                "  window.__SST_I18N_LOCALES = window.__SST_I18N_LOCALES || {};",
                f"  window.__SST_I18N_LOCALES.{locale} = {body};",
                "})();",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"wrote {path} ({len(mapping)} keys)", flush=True)


def apply_locale_overrides(locale: str, mapping: dict[str, str]) -> None:
    mapping["language.en"] = "English"
    mapping["language.ru"] = {"ja": "ロシア語", "ko": "러시아어", "zh": "俄语"}[locale]
    mapping["language.ja"] = {"ja": "日本語", "ko": "일본어", "zh": "日语"}[locale]
    mapping["language.ko"] = {"ja": "韓国語", "ko": "한국어", "zh": "韩语"}[locale]
    mapping["language.zh"] = {"ja": "中国語", "ko": "중국어", "zh": "中文"}[locale]
    mapping[f"language.{locale}"] = {"ja": "日本語", "ko": "한국어", "zh": "中文"}[locale]
    mapping["tools.source_replacement.builtin"] = {
        "ja": "組み込み禁止語リスト（英語・ロシア語・日本語・韓国語・中国語）",
        "ko": "내장 금지어 목록 (영어, 러시아어, 일본어, 한국어, 중국어)",
        "zh": "内置违禁词列表（英语、俄语、日语、韩语、中文）",
    }[locale]


def main() -> None:
    english = load_english_catalog()
    unique_values = sorted(set(english.values()), key=len)
    print(f"english keys: {len(english)}, unique values: {len(unique_values)}", flush=True)
    for locale, target in TARGETS.items():
        print(f"translating {locale}...", flush=True)
        value_map = translate_unique(unique_values, target)
        mapping = {key: value_map.get(value, value) for key, value in english.items()}
        apply_locale_overrides(locale, mapping)
        write_locale(locale, mapping)

    import subprocess
    import sys

    subprocess.run([sys.executable, str(BUNDLE_SCRIPT)], check=True, cwd=str(ROOT))
    print("locales-bundle.js refreshed", flush=True)


if __name__ == "__main__":
    main()
