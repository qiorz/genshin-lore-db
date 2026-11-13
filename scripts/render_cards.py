#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把观测枢的七圣召唤卡牌条目渲染成 corpus/cards/ 下的 Markdown。

数据源：raw/official_site/obc/channel_lists/{233,234,235}.json 给出卡牌清单
       （content_id + title + ext.filter），entries/<content_id>.json 是正文。

收录范围：卡牌基础信息、技能/效果描述、卡牌故事。
不收图片、不收攻略。数值（生命/充能/费用）作为卡牌事实保留——
七圣召唤的"牌面文本"本身包含这些字段，删掉反而读不懂技能。

用法：
    python scripts/render_cards.py            # 干跑，只报告
    python scripts/render_cards.py --apply    # 写文件 + index.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from render_obc import as_json  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

OBC = ROOT / "raw" / "official_site" / "obc"
OUT = ROOT / "corpus" / "cards"
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

CHANNELS = {
    "233": "角色牌",
    "234": "行动牌",
    "235": "魔物牌",
}
BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
SUFFIX = re.compile(r"【(角色牌|行动牌|魔物牌|装备牌|支援牌|事件牌)】")
# 只有这些才是地理区域；丘丘人一类"阵营：魔物"不该写进 region
REGIONS = ("蒙德", "璃月", "稻妻", "须弥", "枫丹", "纳塔", "至冬", "挪德卡莱", "坎瑞亚")


def safe_filename(name: str) -> str:
    return BAD.sub("-", name).strip().rstrip(".")[:80] or "untitled"


def html_to_text(html: str) -> str:
    """卡牌文本专用：行内标签不加分隔符，块级元素之间换行。

    render_obc.html_paragraphs 用 get_text(" ") 是为了英文分词，用在中文卡面上会把
    「装备给我方的法尔伽」拆成「装备给我方的 法尔伽」。这里改成行内零分隔。
    """
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    for tag in soup.find_all(["p", "li", "h1", "h2", "h3", "h4", "blockquote", "div"]):
        tag.append(soup.new_string("\n"))
    raw = soup.get_text("")
    lines = [re.sub(r"[ \t\u00a0]+", " ", ln).strip() for ln in raw.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def load_listing() -> dict[int, dict]:
    """content_id -> {card_type, title, filters}"""
    out: dict[int, dict] = {}
    for cid, label in CHANNELS.items():
        p = OBC / "channel_lists" / f"{cid}.json"
        if not p.exists():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        channel = ((data.get("data") or {}).get("list") or [{}])[0] or {}
        for entry in channel.get("list") or []:
            pid = entry.get("content_id")
            if not pid:
                continue
            filters: list[str] = []
            ext = as_json(entry.get("ext"))
            if isinstance(ext, dict):
                for payload in ext.values():
                    if isinstance(payload, dict):
                        fobj = payload.get("filter")
                        if isinstance(fobj, str):
                            fobj = as_json(fobj)
                        if isinstance(fobj, dict):
                            fobj = as_json(fobj.get("text"))
                        if isinstance(fobj, list):
                            filters = [str(x) for x in fobj]
            out[int(pid)] = {
                "card_type": label,
                "title": entry.get("title") or "",
                "filters": filters,
            }
    return out


def collect_modules(page: dict) -> tuple[dict, list[dict], list[tuple[str, str]]]:
    """返回 (基础信息, 技能列表, [(模块名, 富文本)])"""
    base: dict = {}
    skills: list[dict] = []
    panels: list[tuple[str, str]] = []
    for mod in page.get("modules") or []:
        mod_name = (mod.get("name") or "").strip()
        for comp in mod.get("components") or []:
            cid = comp.get("component_id")
            obj = as_json(comp.get("data"))
            if cid == "card_base_info" and isinstance(obj, dict):
                if (obj.get("name") or "").strip() and not base:
                    base = obj
            elif cid == "card_skill" and isinstance(obj, dict):
                for item in obj.get("list") or []:
                    if not isinstance(item, dict):
                        continue
                    desc = as_json(item.get("desc")) or {}
                    values = [html_to_text(str(v)) for v in (desc.get("value") or [])]
                    values = [v for v in values if v]
                    name = (item.get("tab_name") or "").strip()
                    if name in ("", "默认标题") and not values:
                        continue
                    skills.append({
                        "name": name,
                        "type": (item.get("skill_type") or "").strip(),
                        "cost": item.get("life") or 0,
                        "cost_bg": item.get("life_bg") or 0,
                        "energy": item.get("energy") or 0,
                        "desc_key": (desc.get("key") or "").strip(),
                        "values": values,
                    })
            elif cid == "collapse_panel" and isinstance(obj, dict):
                rich = obj.get("rich_text") or ""
                text = html_to_text(rich)
                if text.strip():
                    panels.append((mod_name, text))
    return base, skills, panels


def render(pid: int, listing: dict, page: dict, meta: dict) -> tuple[dict, list[str], str]:
    base, skills, panels = collect_modules(page)

    title = (page.get("name") or listing["title"]).strip()
    attrs: list[tuple[str, list[str]]] = []
    for attr in base.get("attr") or []:
        if not isinstance(attr, dict):
            continue
        key = str(attr.get("key") or "").strip().rstrip("：:").strip()
        # OBC 的 value 常带前导冒号（"：璃月"），key 有冒号时则没有 —— 两头都清
        values = [str(v).strip().lstrip("：:").strip()
                  for v in (attr.get("value") or []) if str(v).strip()]
        values = [v for v in values if v]
        if key and values:
            attrs.append((key, values))
    region = ""
    for key, values in attrs:
        if key == "阵营" and values[0] in REGIONS:
            region = values[0]
            break

    front: dict = {
        "id": f"card.obc.{pid}",
        "type": "other",
        "subtype": "card",
        "title": title,
        "language": "zh-Hans",
    }
    if region:
        front["region"] = region
    front.update({
        "version_source": "unknown",
        "version_confidence": "unknown",
        "canon_status": "community",
        "transcription": "near-verbatim",
        "spoiler": {"level": 1, "scope": ["card"]},
        "source": [{
            "source_id": "obc",
            "url": f"https://baike.mihoyo.com/ys/obc/content/{pid}/detail?bbs_presentation_style=no_header",
            "page_id": str(pid),
            "revision_id": str(meta.get("page_version") or ""),
            "retrieved_at": str(meta.get("retrieved_at") or ""),
            "license": "site-policy",
        }],
        "status": "draft",
        "notes": f"观测枢 entry_page 导出；七圣召唤{listing['card_type']}；"
                 "卡面数值与技能描述来自 OBC 结构化组件，未收录图片与攻略。",
    })

    body: list[str] = ["## 卡牌信息", "", f"- 卡牌类型：{listing['card_type']}"]
    if base.get("name") and base["name"].strip() != title:
        body.append(f"- 卡面名称：{base['name'].strip()}")
    if base.get("life"):
        label = "费用" if listing["card_type"] == "行动牌" else "生命值"
        body.append(f"- {label}：{base['life']}")
    for key, values in attrs:
        if key in ("元素", "武器", "阵营", "充能", "获取方式"):
            body.append(f"- {key}：{' '.join(values)}")
    body.append("")

    if skills:
        body += ["## 技能" if listing["card_type"] != "行动牌" else "## 效果", ""]
        for skill in skills:
            head = skill["name"] or "未命名"
            if skill["type"]:
                head = f"{head}（{skill['type']}）"
            body.append(f"### {head}")
            body.append("")
            facts = []
            if skill["cost"]:
                facts.append(f"- 消耗：{skill['cost']}")
            if skill["energy"]:
                facts.append(f"- 充能：{skill['energy']}")
            if facts:
                body += facts
                body.append("")
            if skill["values"]:
                body.append("\n\n".join(skill["values"]))
                body.append("")

    for name, text in panels:
        heading = name or "正文"
        if "故事" in heading:
            body += ["## 卡牌故事", "", text, ""]
        elif "效果" in heading:
            body += ["## 效果描述", "", text, ""]
        else:
            body += [f"## {heading}", "", text, ""]

    # 卡牌里没有其它叙事模块时至少保留来源说明
    if len(body) <= 5:
        body += ["## 说明", "", "该卡牌条目在观测枢上只有基础信息，没有技能或故事文本。", ""]

    return front, body, listing["card_type"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="写文件并生成 index.csv")
    args = ap.parse_args()

    import yaml

    listing = load_listing()
    if not listing:
        raise SystemExit("没有卡牌清单，先跑 fetch_obc.py --channel-id 233 234 235")

    rows: list[dict] = []
    missing = 0
    counts: dict[str, int] = {}
    used_targets: dict[Path, int] = {}
    for pid, info in sorted(listing.items()):
        entry_path = OBC / "entries" / f"{pid}.json"
        if not entry_path.exists():
            missing += 1
            continue
        payload = json.loads(entry_path.read_text(encoding="utf-8"))
        page = (payload.get("data") or {}).get("page") or {}
        if not page:
            missing += 1
            continue
        meta_path = OBC / "meta" / f"{pid}.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}

        front, body, card_type = render(pid, info, page, meta)
        counts[card_type] = counts.get(card_type, 0) + 1
        text = f"---\n{yaml.safe_dump(front, allow_unicode=True, sort_keys=False, width=120)}---\n\n" \
               + "\n".join(body).rstrip() + "\n"
        # 卡牌同名不是孤例（如「元素幻变」系列、声援系列），撞名时用 content_id 区分
        stem = safe_filename(front["title"])
        target = OUT / card_type / f"{stem}.md"
        if target in used_targets:
            target = OUT / card_type / f"{stem}-{pid}.md"
        used_targets[target] = pid
        rows.append({
            "doc_id": front["id"],
            "title": front["title"],
            "subtype": "card",
            "region": front.get("region") or "",
            "version": "",
            "path": str(target.relative_to(ROOT)).replace("\\", "/"),
        })
        if args.apply:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8", newline="\n")

    print(f"清单 {len(listing)} 张，已抓 {len(rows)} 张，缺条目 {missing} 张")
    for k, v in sorted(counts.items()):
        print(f"  {k}: {v}")

    if args.apply:
        OUT.mkdir(parents=True, exist_ok=True)
        with (OUT / "index.csv").open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["doc_id", "title", "subtype", "region", "version", "path"])
            w.writeheader()
            w.writerows(rows)
        print(f"已写入 {OUT}")
        print(f"index.csv {len(rows)} 条")
    else:
        print("(dry-run，加 --apply 写文件)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
