# -*- coding: utf-8 -*-
"""批量渲染活动页 + 生成成就 CSV 索引。"""
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
    """从频道列表 ext 里取筛选器：活动类型/版本、成就集/上线版本。"""
    out: dict[str, str] = {}
    try:
        raw = json.loads(item.get("ext") or "{}")
        text = raw[f"c_{channel}"]["filter"]["text"]
        for part in json.loads(text):
            key, _, value = part.partition("/")
            out[key.strip()] = value.strip()
    except Exception:  # noqa: BLE001
        pass
    return out


def safe(name: str) -> str:
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", (name or "").strip()).rstrip(". ")
    return s[:120] or "untitled"


def render_event(cid: str, item: dict):
    entry_path = ROOT / f"raw/official_site/obc/entries/{cid}.json"
    if not entry_path.exists():
        return None
    payload = json.loads(entry_path.read_text(encoding="utf-8"))
    page = payload["data"]["page"]
    meta_path = entry_path.parent.parent / "meta" / f"{cid}.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else None

    ext = parse_ext(item, "105")
    subtype = ext.get("活动类型") or "活动"
    version = ext.get("版本") or ""
    args = SimpleNamespace(
        doc_id=f"event.obc.{cid}",
        title=page.get("name") or item["title"],
        region="",
        version=version,
        version_source="obc-filter" if version else "unknown",
        version_confidence="confirmed" if version else "unknown",
        spoiler=1,
        scope=[f"event:{subtype}"],
        subtype=subtype,
    )
    front, body = R.render_event(page, meta, entry_path, args)
    return front, body, page


# ---------- 活动 ----------
event_rows = []
skipped = []
for item in load_items("105"):
    cid = str(item["content_id"])
    result = render_event(cid, item)
    if not result:
        skipped.append((cid, item["title"], "no_entry"))
        continue
    front, body, page = result
    # 除固定的「## 活动信息」外还有别的小节，才算有叙事内容
    has_content = any(line.startswith("## ") and line != "## 活动信息" for line in body)
    if not has_content:
        skipped.append((cid, item["title"], "no_narrative"))
        continue
    path = ROOT / "corpus/events" / safe(front["subtype"]) / f"{safe(front['title'])}.md"
    event_rows.append((front, body, path))

print(f"活动：可归档 {len(event_rows)}，跳过 {len(skipped)}")
for s in skipped[:8]:
    print("   skip", s)
if APPLY:
    for front, body, path in event_rows:
        path.parent.mkdir(parents=True, exist_ok=True)
        head = yaml.safe_dump(front, allow_unicode=True, sort_keys=False, width=120)
        path.write_text(f"---\n{head}---\n\n" + "\n".join(body).rstrip() + "\n", encoding="utf-8", newline="\n")
    with (ROOT / "manifests/event-skip.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["doc_id", "title", "reason"])
        for cid, title, reason in skipped:
            w.writerow([f"event.obc.{cid}", title, reason])
    with (ROOT / "corpus/events/index.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["doc_id", "title", "subtype", "version", "version_source", "version_confidence", "path"])
        for front, _b, path in event_rows:
            w.writerow([front["id"], front["title"], front["subtype"], front.get("version", ""),
                        front["version_source"], front["version_confidence"],
                        str(path.relative_to(ROOT)).replace("\\", "/")])
    print("wrote", len(event_rows), "events")
else:
    for front, body, path in event_rows[:3]:
        print("   preview", front["id"], front["title"], front["subtype"], len("\n".join(body)))

# ---------- 成就 ----------
ach_rows = []
seen = set()
stats = {"table_pages": 0, "single_pages": 0}


def add(name, desc, aset, version, cid, page_title):
    name = (name or "").strip()
    desc = (desc or "").strip()
    if not name or name in seen:
        return
    seen.add(name)
    ach_rows.append({
        "name": name,
        "description": desc,
        "set": aset,
        "version": version,
        "source_page_id": cid,
        "source_page_title": page_title,
    })


for item in load_items("252"):
    cid = str(item["content_id"])
    entry_path = ROOT / f"raw/official_site/obc/entries/{cid}.json"
    if not entry_path.exists():
        continue
    page = json.loads(entry_path.read_text(encoding="utf-8"))["data"]["page"]
    ext = parse_ext(item, "252")
    ext_set = ext.get("成就集") or ""
    version = ext.get("上线版本") or ""
    page_title = page.get("name") or item["title"]

    rows_found = 0
    for module in page.get("modules") or []:
        for comp in module.get("components") or []:
            if comp.get("component_id") != "multi_table":
                continue
            data = R.as_json(comp.get("data")) or {}
            for table in data.get("tables") or []:
                header = [R.html_inline(h) for h in (table.get("header") or [])]
                try:
                    i_name = header.index("名称")
                    i_desc = header.index("描述")
                except ValueError:
                    i_name, i_desc = 0, 1
                for row in table.get("row") or []:
                    if len(row) <= max(i_name, i_desc):
                        continue
                    add(R.html_inline(row[i_name]), R.html_inline(row[i_desc]), ext_set, version, cid, page_title)
                    rows_found += 1
    if rows_found:
        stats["table_pages"] += 1
        continue

    # 单个成就页：描述在 material_base_info.attr，成就集在 materials
    info = (R._component_data(page, "material_base_info") or [{}])[0]
    materials = info.get("materials") or {}
    aset = ext_set
    if isinstance(materials.get("value"), str):
        aset = R.html_inline(materials["value"]) or ext_set
    desc = ""
    for row in info.get("attr") or []:
        key = (row.get("key") or "").strip()
        values = row.get("value") or []
        if "成就描述" in key:  # 有些页面把标签写在 key 里，value 直接是描述
            desc = " ".join(R.html_inline(v) for v in values).strip()
            break
        for value in values:
            text = R.html_inline(value)
            if "成就描述" in text:
                desc = text.split("：", 1)[1].strip() if "：" in text else text
                break
        if desc:
            break
    add(page_title, desc, aset, version, cid, page_title)
    stats["single_pages"] += 1

# 回填：表格行可能先出现在没有版本/隐藏标记的成就集页，按成就名回查自己的条目
by_title = {item["title"]: item for item in load_items("252")}
for row in ach_rows:
    item = by_title.get(row["name"])
    if not item:
        continue
    ext = parse_ext(item, "252")
    if not row["version"]:
        row["version"] = ext.get("上线版本") or ""
    if not row["set"]:
        row["set"] = ext.get("成就集") or ""
    row["hidden"] = ext.get("隐藏成就") or ""
    row["daily"] = ext.get("每日委托成就") or ""

for row in ach_rows:
    row.setdefault("hidden", "")
    row.setdefault("daily", "")

print(f"成就：{len(ach_rows)} 条（去重后）；成就集页 {stats['table_pages']}，单条页 {stats['single_pages']}")
if APPLY and ach_rows:
    out = ROOT / "manifests/achievements.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["name", "description", "set", "version", "hidden", "daily", "source_page_id", "source_page_title"])
        w.writeheader()
        w.writerows(ach_rows)
    print("wrote", out, len(ach_rows))
