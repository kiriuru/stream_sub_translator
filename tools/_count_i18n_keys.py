import re
from pathlib import Path

text = Path("frontend/js/i18n/locales/en.js").read_text(encoding="utf-8")
m = re.search(r"Object\.assign\(TRANSLATIONS\.en, \{(.*?)\}\);", text, re.S)
block = m.group(1)
pairs = re.findall(r'"((?:[^"\\]|\\.)+)"\s*:\s*"((?:[^"\\]|\\.)*)"', block)
print("keys", len(pairs))
for k, v in pairs[:3]:
    print(k, "=>", v[:40])
