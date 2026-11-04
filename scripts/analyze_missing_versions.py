import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(r"D:\harn\2\genshin-lore-db")
INDEX = ROOT / "manifests" / "obc-index.csv"
ENTRIES = ROOT / "raw" / "official_site" / "obc" / "entries"
OUT = ROOT / "exports" / "obc-evaluation" / "version-gaps.txt"
sys.stdout.reconfigure(encoding="utf-8")


def norm(text: str) -> str:
    return re.sub(r"[\s：:，,。.、··•「」『』《》【】（）()\-—…]+", "", text or "")


def related_text(payload: dict) -> str:
    page = ((payload.get("data") or {}).get("page") or {})
    for module in page.get("modules") or []:
        if (module.get("name") or "").strip() != "相关任务":
            continue
        for comp in module.get("components") or []:
            if comp.get("component_id") != "collapse_panel":
                continue
            data = comp.get("data")
            if isinstance(data, str):
                data = json.loads(data)
            rich = (data or {}).get("rich_text") or ""
            return BeautifulSoup(rich, "html.parser").get_text(" ", strip=True)
    return ""


rows = list(csv.DictReader(INDEX.open(encoding="utf-8-sig", newline="")))
lore = [r for r in rows if r["doc_type"] == "lore"]
quests = [r for r in rows if r["doc_type"] == "quest"]
missing_lore = [r for r in lore if not r["version"]]
missing_quest = [r for r in quests if not r["version"]]
quest_by_title = [(norm(r["title"]), r) for r in quests if r["title"]]

lines = []
lines.append(f"lore total={len(lore)} missing={len(missing_lore)}")
lines.append(f"quest total={len(quests)} missing={len(missing_quest)}")
lines.append("\nMISSING QUESTS")
for r in missing_quest:
    lines.append(f"{r['content_id']} | {r['title']} | region={r['region']} | label={r['version_label']} | category={r['category']}")

with_related = 0
without_related = 0
unmatched = []
for r in missing_lore:
    path = ENTRIES / f"{r['content_id']}.json"
    if not path.exists():
        continue
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        continue
    related = related_text(payload)
    if not related:
        without_related += 1
        continue
    with_related += 1
    related_norm = norm(related)
    hits = [(title, q) for title, q in quest_by_title if title and title in related_norm]
    if hits:
        title, q = max(hits, key=lambda item: len(item[0]))
        unmatched.append(f"{r['content_id']} | {r['title']} | related={related[:80]} | candidate={q['title']} / {q['version'] or 'NO_VERSION'}")
    else:
        unmatched.append(f"{r['content_id']} | {r['title']} | related={related[:100]} | NO_MATCH")

lines.append(f"\nmissing lore with related task={with_related}; without={without_related}")
lines.append("first 80 related/unmatched:")
lines.extend(unmatched[:80])

regions = Counter(r["region"] or "未知" for r in missing_lore)
lines.append("\nmissing lore by region:")
for k, v in regions.most_common():
    lines.append(f"{k}: {v}")

OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"wrote {OUT}")
