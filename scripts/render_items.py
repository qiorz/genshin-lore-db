# -*- coding: utf-8 -*-
"""批量渲染材料/食物/动物/道具，只收描述与背景故事。"""
import csv
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import render_obc as R  # noqa: E402

APPLY = "--apply" in sys.argv
CHANNELS = [("21", "食物"), ("13", "材料"), ("49", "动物"), ("267", "道具")]


def load_items(channel: str) -> list[dict]:
    d = json.loads((ROOT / f"raw/official_site/obc/channel_lists/{channel}.json").read_text(encoding="utf-8"))
    return d["data"]["list"][0]["list"]


def safe(name: str) -> str:
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", (name or "").strip()).rstrip(". ")
    return s[:120] or "untitled"


rows = []
skipped = []
for channel, subtype in CHANNELS:
    items = load_items(channel)
    print(f"{subtype}: {len(items)}")
    for item in items:
        cid = str(item["content_id"])
        entry_path = ROOT / f"raw/official_site/obc/entries/{cid}.json"
        if not entry_path.exists():
            skipped.append((cid, item["title"], subtype, "no_entry"))
            continue
        page = json.loads(entry_path.read_text(encoding="utf-8"))["data"]["page"]
        meta_path = entry_path.parent.parent / "meta" / f"{cid}.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else None
        args = SimpleNamespace(
            doc_id=f"item.obc.{cid}", title=page.get("name") or item["title"], region="",
            version="", version_source="unknown", version_confidence="unknown",
            spoiler=1, scope=[f"item:{subtype}"], subtype=subtype,
        )
        front, body = R.render_item(page, meta, entry_path, args)
        # 正文除固定的「## 物品信息」外还有别的小节，才算有描述
        if not any(line.startswith("## ") and line != "## 物品信息" for line in body):
            skipped.append((cid, item["title"], subtype, "no_description"))
            continue
        path = ROOT / "corpus/items" / subtype / f"{safe(front['title'])}.md"
        rows.append((front, body, path))

# 同子类型下同名（材料里有 12 组）：加 content_id 后缀，避免互相覆盖
counts: dict[str, int] = {}
for _front, _body, path in rows:
    counts[str(path)] = counts.get(str(path), 0) + 1

fixed = []
for front, body, path in rows:
    if counts[str(path)] > 1:
        cid = front["id"].rsplit(".", 1)[-1]
        path = path.with_name(f"{path.stem} (obc-{cid}).md")
    fixed.append((front, body, path))
rows = fixed

print(f"可归档 {len(rows)}，跳过 {len(skipped)}")

if APPLY:
    for front, body, path in rows:
        path.parent.mkdir(parents=True, exist_ok=True)
        head = yaml.safe_dump(front, allow_unicode=True, sort_keys=False, width=120)
        path.write_text(f"---\n{head}---\n\n" + "\n".join(body).rstrip() + "\n", encoding="utf-8", newline="\n")
    with (ROOT / "corpus/items/index.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["doc_id", "title", "subtype", "path"])
        for front, _b, path in rows:
            w.writerow([front["id"], front["title"], front["subtype"],
                        str(path.relative_to(ROOT)).replace("\\", "/")])
    with (ROOT / "manifests/item-skip.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["doc_id", "title", "subtype", "reason"])
        for cid, title, subtype, reason in skipped:
            w.writerow([f"item.obc.{cid}", title, subtype, reason])
    print("wrote", len(rows), "items")
else:
    for front, body, path in rows[:3]:
        print("   preview", front["id"], front["title"], front["subtype"], len("\n".join(body)))
