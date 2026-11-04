# -*- coding: utf-8 -*-
"""批量渲染 NPC 对话 / 角色逸闻 / 角色彩蛋。

来源：观测枢三个频道的频道列表（含地区标签）与各自的 entry_page 快照。
只收对话正文、情报、赠礼对话语音文字与逸闻简介；
商品列表、奖励、挑战规则、地图、生日邮件一律不收。

用法：
    python scripts/render_npcs.py            # 干跑
    python scripts/render_npcs.py --apply   # 写文件 + index.csv + npc-skip.csv
"""
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
CHANNELS = [
    ("20", "NPC对话"),
    ("261", "角色逸闻"),
    ("279", "角色彩蛋"),
]
REGION_ALIAS = {"诺德卡莱": "挪德卡莱"}


def load_channel(channel: str) -> list[dict]:
    path = ROOT / f"raw/official_site/obc/channel_lists/{channel}.json"
    return json.loads(path.read_text(encoding="utf-8"))["data"]["list"][0]["list"]


def safe(name: str) -> str:
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", (name or "").strip()).rstrip(". ")
    return s[:120] or "untitled"


def region_of(entry: dict, channel: str) -> str:
    ext = entry.get("ext") or {}
    if isinstance(ext, str):
        try:
            ext = json.loads(ext)
        except json.JSONDecodeError:
            ext = {}
    filt = (ext.get(f"c_{channel}") or {}).get("filter") or {}
    raw = filt.get("text") if isinstance(filt, dict) else None
    try:
        tags = json.loads(raw) if isinstance(raw, str) else (raw or [])
    except json.JSONDecodeError:
        tags = []
    for tag in tags:
        if isinstance(tag, str) and tag.startswith("地区/"):
            name = tag.split("/", 1)[1].strip()
            return REGION_ALIAS.get(name, name)
    return ""


rows = []
skipped = []
for channel, subtype in CHANNELS:
    entries = load_channel(channel)
    print(f"{subtype}（频道 {channel}）: {len(entries)} 条")
    for item in entries:
        cid = str(item["content_id"])
        title = (item.get("title") or "").strip()
        entry_path = ROOT / f"raw/official_site/obc/entries/{cid}.json"
        if not entry_path.exists():
            skipped.append((cid, title, subtype, "no_entry"))
            continue
        payload = json.loads(entry_path.read_text(encoding="utf-8"))
        page = (payload.get("data") or {}).get("page") or {}
        if not page:
            skipped.append((cid, title, subtype, "empty_page"))
            continue
        meta_path = entry_path.parent.parent / "meta" / f"{cid}.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else None
        region = region_of(item, channel)
        args = SimpleNamespace(
            doc_id=f"voice.obc.{cid}",
            title=page.get("name") or title,
            region=region,
            version="",
            version_source="unknown",
            version_confidence="unknown",
            spoiler=1,
            scope=[f"voice:{subtype}"],
            subtype=subtype,
        )
        front, body = R.render_npc(page, meta, entry_path, args)
        sections = [line for line in body if line.startswith("## ") and line != "## 基本信息"]
        if not sections:
            skipped.append((cid, title, subtype, "no_dialogue"))
            continue
        chars = len("".join(line for line in body if not line.startswith("#")))
        path = ROOT / "corpus/voices" / subtype / (region or "未分类") / f"{safe(front['title'])}.md"
        rows.append((front, body, path, region, len(sections), chars))

# 同子类型同地区下同名条目（3 组）加 content_id 后缀，避免互相覆盖
counts: dict[str, int] = {}
for _f, _b, path, *_ in rows:
    counts[str(path)] = counts.get(str(path), 0) + 1
fixed = []
for front, body, path, region, nsections, chars in rows:
    if counts[str(path)] > 1:
        cid = front["id"].rsplit(".", 1)[-1]
        path = path.with_name(f"{path.stem} (obc-{cid}).md")
    fixed.append((front, body, path, region, nsections, chars))
rows = fixed

print(f"可归档 {len(rows)}，跳过 {len(skipped)}")
by_sub: dict[str, int] = {}
for front, _b, _p, *_ in rows:
    by_sub[front["subtype"]] = by_sub.get(front["subtype"], 0) + 1
print("  按子类型:", by_sub)
print("  正文总字符:", sum(r[5] for r in rows))
skip_reasons: dict[str, int] = {}
for _cid, _t, _s, reason in skipped:
    skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
print("  跳过原因:", skip_reasons)

if APPLY:
    for front, body, path, *_ in rows:
        path.parent.mkdir(parents=True, exist_ok=True)
        head = yaml.safe_dump(front, allow_unicode=True, sort_keys=False, width=120)
        path.write_text(f"---\n{head}---\n\n" + "\n".join(body).rstrip() + "\n",
                        encoding="utf-8", newline="\n")
    with (ROOT / "corpus/voices/index.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["doc_id", "title", "subtype", "region", "sections", "chars", "path"])
        for front, _b, path, region, nsections, chars in rows:
            w.writerow([front["id"], front["title"], front["subtype"], region,
                        nsections, chars, str(path.relative_to(ROOT)).replace("\\", "/")])
    with (ROOT / "manifests/npc-skip.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["doc_id", "title", "subtype", "reason"])
        for cid, title, subtype, reason in skipped:
            w.writerow([f"voice.obc.{cid}", title, subtype, reason])
    print("wrote", len(rows), "voice docs")
else:
    for front, body, path, region, nsections, chars in rows[:3]:
        print("   preview", front["id"], front["title"], region, nsections, chars, path.relative_to(ROOT))
