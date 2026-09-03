"""One-off patch: staff-only include_inactive on list views."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "apps"
PATTERN = re.compile(
    r"if request\.query_params\.get\(\"include_inactive\", \"\"\)\.lower\(\) not in \(\s*"
    r"\"1\",\s*\"true\",\s*\"yes\",\s*\):\s*\n\s*(\w+) = \1\.filter\(is_active=True\)\n",
    re.MULTILINE,
)

for path in ROOT.rglob("*views.py"):
    text = path.read_text(encoding="utf-8")
    if "include_inactive" not in text or "filter_active_for_list" in text:
        continue
    if "from apps.core.soft_delete import" in text:
        text = text.replace(
            "from apps.core.soft_delete import",
            "from apps.core.soft_delete import filter_active_for_list,",
            1,
        )
    new_text, n = PATTERN.subn(r"\1 = filter_active_for_list(request, \1)\n", text)
    if n:
        path.write_text(new_text, encoding="utf-8")
        print(f"Patched {path} ({n})")
