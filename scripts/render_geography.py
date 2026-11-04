# -*- coding: utf-8 -*-
"""批量渲染观景点 + 生成区域结构化索引。"""
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


def load_items(channel: str) -> list[dict]:
    d = json.loads((ROOT / f"raw/official_site/obc/channel_lists/{channel}.json").read_text(encoding="utf-8"))
    return d["data"]["list"][0]["list"]


def parse_ext(item: dict, channel: str) -> dict:
    out: dict[str, str] = {}
    try:
        raw = json.loads(item.get("ext") or "{}")
        for part in json.loads(raw[f"c_{channel}"]["filter"]["text"]):
            key, _, value = part.partition("/")
            out[key.strip()] = value.strip()
    except Exception:  # noqa: BLE001
        pass
    return out


def safe(name: str) -> str:
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", (name or "").strip()).rstrip(". ")
    return s[:120] or "untitled"


rows = []
skipped = []
for item in load_items("253"):
    cid = str(item["content_id"])
    entry_path = ROOT / f"raw/official_site/obc/entries/{cid}.json"
    if not entry_path.exists():
        skipped.append((cid, item["title"], "no_entry"))
        continue
    page = json.loads(entry_path.read_text(encoding="utf-8"))["data"]["page"]
    meta_path = entry_path.parent.parent / "meta" / f"{cid}.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else None
    ext = parse_ext(item, "253")
    region = ext.get("地区") or "未知"
    args = SimpleNamespace(
        doc_id=f"geo.obc.{cid}", title=page.get("name") or item["title"], region=region,
        version="", version_source="unknown", version_confidence="unknown",
        spoiler=1, scope=["geography:观景点"], subtype="观景点",
    )
    front, body = R.render_geography(page, meta, entry_path, args)
    if not body:
        skipped.append((cid, item["title"], "no_text"))
        continue
    path = ROOT / "corpus/geography/观景点" / safe(region) / f"{safe(front['title'])}.md"
    rows.append((front, body, path))

print(f"观景点：可归档 {len(rows)}，跳过 {len(skipped)}")

if APPLY:
    for front, body, path in rows:
        path.parent.mkdir(parents=True, exist_ok=True)
        head = yaml.safe_dump(front, allow_unicode=True, sort_keys=False, width=120)
        path.write_text(f"---\n{head}---\n\n" + "\n".join(body).rstrip() + "\n", encoding="utf-8", newline="\n")
    with (ROOT / "corpus/geography/index.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["doc_id", "title", "subtype", "region", "path"])
        for front, _b, path in rows:
            w.writerow([front["id"], front["title"], front["subtype"], front["region"],
                        str(path.relative_to(ROOT)).replace("\\", "/")])
    print("wrote", len(rows), "viewpoints")

# ---------- 区域索引 ----------
SECTIONS = ("系列任务", "怪物分布", "地图资源", "机关", "NPC")
region_rows = []
for item in load_items("7"):
    cid = str(item["content_id"])
    entry_path = ROOT / f"raw/official_site/obc/entries/{cid}.json"
    if not entry_path.exists():
        continue
    page = json.loads(entry_path.read_text(encoding="utf-8"))["data"]["page"]
    name = page.get("name") or item["title"]
    for module in page.get("modules") or []:
        mname = (module.get("name") or "").strip()
        if mname not in SECTIONS:
            continue
        for comp in module.get("components") or []:
            if comp.get("component_id") != "rich_base_info":
                continue
            data = R.as_json(comp.get("data")) or {}
            for row in data.get("list") or []:
                items = [R.html_inline(v) for v in row.get("value") or []]
                text = "；".join(x for x in items if x)
                if not text or text == "暂无":
                    continue
                region_rows.append({
                    "region": name,
                    "section": mname,
                    "key": (row.get("key") or "").strip(),
                    "items": text,
                    "source_page_id": cid,
                })

print(f"区域索引：{len(region_rows)} 行")
if APPLY and region_rows:
    out = ROOT / "manifests/regions.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["region", "section", "key", "items", "source_page_id"])
        w.writeheader()
        w.writerows(region_rows)
    print("wrote", out, len(region_rows))
