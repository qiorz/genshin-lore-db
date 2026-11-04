# -*- coding: utf-8 -*-
"""批量渲染武器与圣遗物：OBC 正文 + BWiki 版本，写入 corpus/ 并生成索引与对照表。"""
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
BWIKI = ROOT / "raw/bwiki/equipment"


def norm(t: str) -> str:
    return re.sub(r"[\s：:，,。.、·•「」『』《》【】（）()\-—…～~！？!?\"'‘’“”]+", "", t or "")


def load_items(channel: str) -> list[dict]:
    d = json.loads((ROOT / f"raw/official_site/obc/channel_lists/{channel}.json").read_text(encoding="utf-8"))
    return d["data"]["list"][0]["list"]


def safe(name: str) -> str:
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", (name or "").strip()).rstrip(". ")
    return s[:120] or "untitled"


def render_one(cid: str, entry_path: Path, doc_type: str, title: str, bwiki: dict, category: str = ""):
    payload = json.loads(entry_path.read_text(encoding="utf-8"))
    page = payload["data"]["page"]
    meta_path = entry_path.parent.parent / "meta" / f"{cid}.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else None

    version = (bwiki or {}).get("version") or ""
    scope = [f"weapon:{category}"] if doc_type == "weapon" else ["artifact:set"]
    args = SimpleNamespace(
        doc_id=f"{doc_type}.obc.{cid}",
        title=title,
        region="",
        version=version,
        version_source="bwiki" if version else "unknown",
        version_confidence="confirmed" if version else "unknown",
        spoiler=1,
        scope=scope,
    )
    renderer = R.render_weapon if doc_type == "weapon" else R.render_artifact
    front, body = renderer(page, meta, entry_path, args)

    # OBC 故事为空或写着「暂无」时，用 BWiki 补，并挂第二条 source。
    # 放在流水线里，重跑 --apply 不会把补充覆盖掉。
    obc_story = ""
    if doc_type == "weapon":
        for module in page.get("modules") or []:
            if "相关故事" in (module.get("name") or ""):
                for comp in module.get("components") or []:
                    obc_story += R.html_paragraphs((R.as_json(comp.get("data")) or {}).get("rich_text", ""))
    bw_story = (bwiki or {}).get("story") or ""
    if doc_type == "weapon" and len(norm(obc_story)) < 20 and len(norm(bw_story)) > 40:
        if "## 故事" in body:
            body = body[: body.index("## 故事")]
        body = body + ["", "## 故事（BWiki 补充）", "", bw_story]
        front["source"] = list(front["source"]) + [{
            "source_id": "bwiki",
            "url": f"https://wiki.biligame.com/ys/{title}",
            "page_id": title,
            "revision_id": str(bwiki.get("revid") or ""),
            "retrieved_at": "2026-11-04T13:10:00+08:00",
            "license": "site-policy",
        }]
        front["notes"] = (front.get("notes") or "").rstrip() + " OBC 故事原文为空或「暂无」，已用 BWiki 补全。"

    return front, body, page, obc_story


index_rows = []
report_rows = []

for channel, doc_type in (("5", "weapon"), ("218", "artifact")):
    items = load_items(channel)
    print(f"{doc_type}: {len(items)}")
    for item in items:
        cid = str(item["content_id"])
        entry_path = ROOT / f"raw/official_site/obc/entries/{cid}.json"
        if not entry_path.exists():
            report_rows.append({"doc_id": f"{doc_type}.obc.{cid}", "title": item["title"], "status": "no_entry"})
            print("  missing entry", cid)
            continue
        bwiki_path = BWIKI / f"{cid}.json"
        bwiki = json.loads(bwiki_path.read_text(encoding="utf-8")) if bwiki_path.exists() else {}
        if bwiki and not bwiki.get("found"):
            bwiki = {}

        page_head = json.loads(entry_path.read_text(encoding="utf-8"))["data"]["page"]
        category = ""
        if doc_type == "weapon":
            base = (R._component_data(page_head, "equipment_base_info") or [{}])[0]
            category = (base.get("category") or "").strip() or "未知"
        title = page_head.get("name") or item["title"]

        front, body, page, obc_story_weapon = render_one(cid, entry_path, doc_type, title, bwiki, category)

        if doc_type == "weapon":
            out = ROOT / "corpus/weapons" / safe(category) / f"{safe(title)}.md"
        else:
            out = ROOT / "corpus/artifacts" / f"{safe(title)}.md"

        # 对照：OBC 故事 vs BWiki 故事
        obc_story = obc_story_weapon
        if doc_type == "artifact":
            for module in page.get("modules") or []:
                slot_name = (module.get("name") or "").strip()
                for comp in module.get("components") or []:
                    if comp.get("component_id") != "artifact_list_v2":
                        continue
                    data = R.as_json(comp.get("data")) or {}
                    if slot_name not in R.ARTIFACT_SLOTS:
                        slot_name = ((data.get("name") or {}).get("key") or "").strip().rstrip("：: ")
                    if slot_name not in R.ARTIFACT_SLOTS:
                        continue
                    obc_story += "".join((data.get("story") or {}).get("value") or [])
        bw_story = bwiki.get("story") or ""
        if doc_type == "artifact":
            bw_story = "".join(bwiki.get(f"{s}_story") or "" for s in R.ARTIFACT_SLOTS)
        a, b = len(norm(obc_story)), len(norm(bw_story))
        ratio = round(a / b, 2) if b else None

        report_rows.append({
            "doc_id": front["id"],
            "title": title,
            "type": doc_type,
            "version": bwiki.get("version") or "",
            "bwiki_found": bool(bwiki),
            "obc_chars": a,
            "bwiki_chars": b,
            "ratio": ratio,
            "path": str(out.relative_to(ROOT)).replace("\\", "/"),
        })

        if APPLY:
            out.parent.mkdir(parents=True, exist_ok=True)
            text = "---\n" + yaml.safe_dump(front, allow_unicode=True, sort_keys=False, width=120) + "---\n\n"
            out.write_text(text + "\n".join(body).rstrip() + "\n", encoding="utf-8", newline="\n")

        index_rows.append([
            front["id"], title, front.get("subtype") or "",
            bwiki.get("version") or "",
            front["version_source"], front["version_confidence"],
            str(out.relative_to(ROOT)).replace("\\", "/"),
        ])

if APPLY:
    for sub, path in (("weapons", "corpus/weapons/index.csv"), ("artifacts", "corpus/artifacts/index.csv")):
        rows = [r for r in index_rows if r[0].startswith(sub[:-1])]
        with (ROOT / path).open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["doc_id", "title", "subtype", "version", "version_source", "version_confidence", "path"])
            w.writerows(rows)
        print("wrote", path, len(rows))

    with (ROOT / "manifests/equipment-bwiki-compare.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["doc_id", "title", "type", "version", "bwiki_found", "obc_chars", "bwiki_chars", "ratio", "path"])
        w.writeheader()
        w.writerows(report_rows)
    print("wrote manifests/equipment-bwiki-compare.csv", len(report_rows))
else:
    print("dry-run; would write", len(index_rows), "docs")
    for r in report_rows[:5]:
        print("  ", r)
