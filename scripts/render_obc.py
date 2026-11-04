#!/usr/bin/env python3
"""Render an 观测枢 entry_page JSON into a Markdown draft.

This is a pilot renderer, not a complete parser. It supports:
  - quest: interactive_dialogue modules (dialogue graph + options, one act per file)
  - book: material_base_info + collapse_panel volume text
  - character: story/description/voice modules only (no stats/guides)
  - lore: scattered map text (interactive text only, no map images)

Game version is looked up in manifests/versions.csv, then manifests/obc-index.csv.

Examples:
    python scripts/render_obc.py --entry raw/official_site/obc/entries/399.json \
        --type quest --doc-id quest.obc.399 --region 蒙德 \
        --out exports/obc-evaluation/quest-399.md
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
TZ = timezone(timedelta(hours=8))
DEFAULT_VERSIONS = ROOT / "manifests" / "versions.csv"
DEFAULT_INDEX = ROOT / "manifests" / "obc-index.csv"

CHARACTER_STORY_KEYS = (
    "角色故事",
    "更多描述",
    "角色详细",
    "神之眼",
    "神之心",
    "角色关联语音",
    "生日邮件",
)

QUEST_SUBTYPE_LABELS = {
    "archon": "魔神任务",
    "story": "传说任务",
    "world": "世界任务",
    "event": "限时任务",
    "interlude": "间章",
    "hangout": "邀约事件",
    "other": "其他任务",
}


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def as_json(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def html_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    # 只在块级元素边界断行；行内 span/ruby/a 不能断，否则会把一句话拆成几行。
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for tag in soup.find_all(["p", "li", "div", "h1", "h2", "h3", "h4", "blockquote", "tr"]):
        tag.append("\n")
    text = soup.get_text("")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def html_inline(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()


def html_paragraphs(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    blocks = soup.find_all(["p", "li", "h1", "h2", "h3", "h4", "blockquote"])
    lines: list[str] = []
    for block in blocks:
        text = block.get_text(" ", strip=True)
        if text and (not lines or lines[-1] != text):
            lines.append(text)
    if not lines:
        text = soup.get_text(" ", strip=True)
        if text:
            lines = [text]
    return "\n\n".join(lines)


def render_line(line: str) -> str:
    line = line.strip()
    if not line or line in {"。", "，", "、", "；", "：", "！", "？"}:
        return ""
    if line.startswith("◆"):
        return f"> **{line}**"
    match = re.match(r"^([^：:]{1,24})[：:]\s*(.+)$", line)
    if match and "◆" not in match.group(1):
        speaker, text = match.groups()
        return f"**{speaker}**：{text}"
    # Scene directions / narration: keep them visually distinct from spoken lines.
    return f"> *{line}*"


def dialogue_groups(data: dict) -> list[dict]:
    """OBC uses either a list of groups or a single graph with contents/root_id."""
    groups = data.get("list") or []
    if not groups and data.get("root_id") and data.get("contents"):
        groups = [data]
    return groups


def render_dialogue_group(group: dict) -> tuple[list[str], int, int]:
    contents = group.get("contents") or {}
    child_ids = group.get("child_ids") or {}
    root_id = group.get("root_id")
    out: list[str] = []
    nodes = 0
    options = 0
    seen: set[str] = set()

    def walk(node_id: str, path: set[str]) -> None:
        nonlocal nodes, options
        if not node_id or node_id in path or node_id not in contents:
            return
        # Shared branches often reconverge; render each node once.
        if node_id in seen:
            return
        seen.add(node_id)
        node = contents[node_id]
        nodes += 1

        option = html_text(node.get("option", ""))
        dialogue = html_text(node.get("dialogue", ""))
        if option:
            options += 1
            for line in option.splitlines():
                line = line.strip()
                if not line:
                    continue
                match = re.match(r"^([^：:]{1,24})[：:]\s*(.+)$", line)
                if match:
                    out.append(f"> 选项（{match.group(1)}）：{match.group(2)}")
                else:
                    out.append(f"> 选项：{line}")
        for line in dialogue.splitlines():
            rendered = render_line(line)
            if rendered:
                out.append(rendered)

        children = [c for c in (child_ids.get(node_id) or []) if c in contents]
        if len(children) > 1:
            out.append("")
            out.append("> **分支**")
        for index, child in enumerate(children, 1):
            if len(children) > 1:
                out.append(f"> **分支 {index}**")
            walk(child, path | {node_id})

    # 有些页面（多为地图文本）root_id 指向的容器节点并不在 contents 里，
    # 真正的分支节点成了「没有父节点的孤岛」。此时从孤岛起步，
    # 按 key 末位时间戳排序渲染，否则整篇会输出为空。
    if root_id not in contents:
        # 只统计「父节点真实存在」的边；指向缺失容器的边不算，
        # 否则所有节点都会被认为有父节点，roots 为空。
        child_nodes = {
            c
            for parent, kids in child_ids.items()
            if parent in contents
            for c in (kids or [])
        }
        roots = [k for k in contents if k not in child_nodes]

        def node_order(node_key: str) -> tuple[int, str]:
            digits = re.sub(r"\D", "", node_key)
            return (int(digits[-13:]) if digits else 0, node_key)

        for node_id in sorted(roots, key=node_order):
            walk(node_id, set())
        return out, nodes, options

    walk(root_id, set())
    return out, nodes, options


def source_block(meta: dict | None, page: dict, entry_path: Path) -> dict:
    entry_id = page.get("id") or entry_path.stem
    return {
        "source_id": "obc",
        "url": (meta or {}).get(
            "url",
            f"https://baike.mihoyo.com/ys/obc/content/{entry_id}/detail?bbs_presentation_style=no_header",
        ),
        "page_id": str(entry_id),
        "revision_id": str((meta or {}).get("page_version") or page.get("version") or ""),
        "retrieved_at": (meta or {}).get("retrieved_at") or now_iso(),
        "license": "site-policy",
    }


def dialogue_scene_title(module: dict) -> str:
    """Extract the subquest name from the first dialogue scene heading, if present."""
    for comp in module.get("components") or []:
        if comp.get("component_id") != "interactive_dialogue":
            continue
        data = as_json(comp.get("data")) or {}
        for group in dialogue_groups(data):
            root_id = group.get("root_id")
            node = (group.get("contents") or {}).get(root_id) or {}
            text = html_text(node.get("dialogue", ""))
            for line in text.splitlines():
                match = re.search(r"第\S+[幕章节].*\s([^\s（(]+)\s*[（(]", line)
                if match:
                    return match.group(1).strip()
    return ""


def render_quest(page: dict, meta: dict | None, entry_path: Path, args) -> tuple[dict, list[str]]:
    front = {
        "id": args.doc_id,
        "type": "quest",
        "subtype": args.subtype or "archon",
        "title": args.title or page.get("name") or "",
        "language": "zh-Hans",
        "region": args.region,
        "version": args.version,
        "version_source": args.version_source,
        "version_confidence": args.version_confidence,
        "canon_status": "community",
        "transcription": "near-verbatim",
        "spoiler": {"level": args.spoiler, "scope": args.scope or []},
        "source": [source_block(meta, page, entry_path)],
        "status": "draft",
        "notes": "观测枢 entry_page 试点导出；官方平台/社区编辑，非逐字官方文本；分支由 child_ids 展开；无场景字幕的模块用“剧情对话 N”编号。",
    }
    if not front.get("version"):
        front.pop("version", None)

    body = ["## 任务信息", ""]
    body.append(f"- 类型：{QUEST_SUBTYPE_LABELS.get(front['subtype'], front['subtype'])}")
    if args.region:
        body.append(f"- 地区：{args.region}")
    if args.version:
        body.append(f"- 版本：{args.version}")
    body.append("- 来源：米游社·观测枢")
    body.append("")

    dialogue_index = 0
    total_nodes = total_options = 0
    heading_counts: dict[str, int] = {}
    for module in page.get("modules") or []:
        for comp in module.get("components") or []:
            if comp.get("component_id") != "interactive_dialogue":
                continue
            data = as_json(comp.get("data")) or {}
            dialogue_index += 1
            heading = dialogue_scene_title(module) or f"剧情对话 {dialogue_index}"
            heading_counts[heading] = heading_counts.get(heading, 0) + 1
            if heading_counts[heading] > 1:
                heading = f"{heading} · 其{heading_counts[heading]}"
            body.append(f"## {heading}")
            body.append("")
            for group in dialogue_groups(data):
                lines, nodes, options = render_dialogue_group(group)
                body.extend(lines)
                body.append("")
                total_nodes += nodes
                total_options += options
    front["notes"] += f" 共 {dialogue_index} 个剧情模块、{total_nodes} 个对话节点、{total_options} 个选项。"
    return front, body


def render_book(page: dict, meta: dict | None, entry_path: Path, args) -> tuple[dict, list[str]]:
    front = {
        "id": args.doc_id,
        "type": "book",
        "title": args.title or page.get("name") or "",
        "language": "zh-Hans",
        "region": args.region,
        "version": args.version,
        "version_source": args.version_source,
        "version_confidence": args.version_confidence,
        "canon_status": "community",
        "transcription": "near-verbatim",
        "spoiler": {"level": args.spoiler, "scope": args.scope or []},
        "source": [source_block(meta, page, entry_path)],
        "status": "draft",
        "notes": "观测枢 entry_page 试点导出；官方平台/社区编辑，非逐字官方文本。",
    }
    if not front.get("version"):
        front.pop("version", None)

    body: list[str] = ["## 书籍信息", ""]
    for module in page.get("modules") or []:
        for comp in module.get("components") or []:
            if comp.get("component_id") != "material_base_info":
                continue
            data = as_json(comp.get("data")) or {}
            name = data.get("name") or module.get("name")
            materials = data.get("materials") or {}
            material_text = html_inline(materials.get("value", "")) if isinstance(materials, dict) else ""
            attrs = []
            for attr in data.get("attr") or []:
                key = (attr.get("key") or "").strip()
                values = [html_inline(v) for v in (attr.get("value") or [])]
                values = [v for v in values if v]
                if key and values:
                    attrs.append((key, values))
            if not (name or material_text or attrs):
                continue
            if name:
                body.append(f"### {name}")
            if data.get("star"):
                body.append(f"- 稀有度：{data['star']} 星")
            if material_text:
                body.append(f"- {materials.get('key', '获取方式')}：{material_text}")
            for key, values in attrs:
                body.append(f"- {key}：" + " ".join(values))
            body.append("")
    for module in page.get("modules") or []:
        for comp in module.get("components") or []:
            if comp.get("component_id") != "collapse_panel":
                continue
            data = as_json(comp.get("data")) or {}
            rich = data.get("rich_text") or ""
            if not html_text(rich):
                continue
            name = (module.get("name") or "").strip() or "正文"
            body.append(f"## {name}")
            body.append("")
            body.append(html_paragraphs(rich))
            body.append("")
    return front, body


def render_character(page: dict, meta: dict | None, entry_path: Path, args) -> tuple[dict, list[str]]:
    front = {
        "id": args.doc_id,
        "type": "character",
        "title": args.title or page.get("name") or "",
        "language": "zh-Hans",
        "region": args.region,
        "version": args.version,
        "version_source": args.version_source,
        "version_confidence": args.version_confidence,
        "canon_status": "community",
        "transcription": "near-verbatim",
        "spoiler": {"level": args.spoiler, "scope": args.scope or []},
        "source": [source_block(meta, page, entry_path)],
        "status": "draft",
        "notes": "观测枢 entry_page 试点导出；仅选角色故事/描述/神之眼/神之心/关联语音/生日邮件，不含属性、命之座与攻略。",
    }
    if not front.get("version"):
        front.pop("version", None)

    body: list[str] = []
    for module in page.get("modules") or []:
        name = (module.get("name") or "").strip()
        if not any(key in name for key in CHARACTER_STORY_KEYS):
            continue
        for comp in module.get("components") or []:
            if comp.get("component_id") != "collapse_panel":
                continue
            data = as_json(comp.get("data")) or {}
            rich = data.get("rich_text") or ""
            if not html_text(rich):
                continue
            body.append(f"## {name}")
            body.append("")
            body.append(html_paragraphs(rich))
            body.append("")
    return front, body


def render_lore(page: dict, meta: dict | None, entry_path: Path, args) -> tuple[dict, list[str]]:
    related = ""
    for module in page.get("modules") or []:
        if (module.get("name") or "").strip() != "相关任务":
            continue
        for comp in module.get("components") or []:
            if comp.get("component_id") == "collapse_panel":
                data = as_json(comp.get("data")) or {}
                related = html_text(data.get("rich_text", ""))
                break

    notes = "观测枢 地图文本试点；仅保留交互文本，跳过地图图片/坐标。"
    if related:
        notes += f" 相关任务：{related}"
    front = {
        "id": args.doc_id,
        "type": "lore",
        "subtype": "scattered",
        "title": args.title or page.get("name") or "",
        "language": "zh-Hans",
        "region": args.region,
        "version": args.version,
        "version_source": args.version_source,
        "version_confidence": args.version_confidence,
        "canon_status": "community",
        "transcription": "near-verbatim",
        "spoiler": {"level": args.spoiler, "scope": args.scope or []},
        "source": [source_block(meta, page, entry_path)],
        "status": "draft",
        "notes": notes,
    }
    if not front.get("version"):
        front.pop("version", None)

    body: list[str] = []
    seen_headings: dict[str, int] = {}
    for module in page.get("modules") or []:
        for comp in module.get("components") or []:
            if comp.get("component_id") != "interactive_dialogue":
                continue
            data = as_json(comp.get("data")) or {}
            heading = (module.get("name") or "交互文本").strip() or "交互文本"
            seen_headings[heading] = seen_headings.get(heading, 0) + 1
            if seen_headings[heading] > 1:
                heading = f"{heading} · 其{seen_headings[heading]}"
            body.append(f"## {heading}")
            body.append("")
            for group in dialogue_groups(data):
                lines, _, _ = render_dialogue_group(group)
                body.extend(lines)
                body.append("")
    return front, body


def _component_data(page: dict, component_id: str) -> list:
    found = []
    for module in page.get("modules") or []:
        for comp in module.get("components") or []:
            if comp.get("component_id") == component_id:
                found.append(as_json(comp.get("data")) or {})
    return found


def _module_text(page: dict, name_keyword: str, component_id: str = "collapse_panel") -> str:
    for module in page.get("modules") or []:
        if name_keyword not in (module.get("name") or ""):
            continue
        for comp in module.get("components") or []:
            if comp.get("component_id") != component_id:
                continue
            data = as_json(comp.get("data")) or {}
            return html_paragraphs(data.get("rich_text", ""))
    return ""


def _split_hr(html: str) -> tuple[str, str]:
    """把 good_desc 拆成 <hr> 前后两段：前段是精炼数值，后段是装备描述。"""
    if "<hr" not in html:
        return html, ""
    head, tail = re.split(r"<hr[^>]*>", html, maxsplit=1)
    return head, tail


def render_weapon(page: dict, meta: dict | None, entry_path: Path, args) -> tuple[dict, list[str]]:
    base = (_component_data(page, "equipment_base_info") or [{}])[0]
    category = (base.get("category") or "").strip()
    star = base.get("star")

    flavor = ""
    for data in _component_data(page, "good_desc"):
        raw = data.get("rich_text", "")
        if "<hr" in raw:
            # 有精炼数值段：只取 <hr> 之后的装备描述
            _stats, tail = _split_hr(raw)
            if tail.strip():
                flavor = html_paragraphs(tail)
        else:
            # 一星武器没有精炼段，整段就是装备描述
            if raw.strip():
                flavor = html_paragraphs(raw)

    story = _module_text(page, "相关故事")

    notes = "观测枢 entry_page 导出；只收装备描述与故事，不含精炼数值、属性、推荐角色。"
    front = {
        "id": args.doc_id,
        "type": "weapon",
        "subtype": category or None,
        "title": args.title or page.get("name") or "",
        "language": "zh-Hans",
        "region": args.region,
        "version": args.version,
        "version_source": args.version_source,
        "version_confidence": args.version_confidence,
        "canon_status": "community",
        "transcription": "near-verbatim",
        "spoiler": {"level": args.spoiler, "scope": args.scope or []},
        "source": [source_block(meta, page, entry_path)],
        "status": "draft",
        "notes": notes,
    }
    if not front.get("subtype"):
        front.pop("subtype", None)
    if not front.get("region"):
        front.pop("region", None)
    if not front.get("version"):
        front.pop("version", None)

    body: list[str] = ["## 武器信息", ""]
    body.append(f"- 类型：{category or '未知'}")
    if star:
        body.append(f"- 稀有度：{star} 星")
    if args.version:
        body.append(f"- 版本：{args.version}")
    body.append("- 来源：米游社·观测枢")

    if flavor:
        body.extend(["", "## 装备描述", "", flavor])
    if story:
        body.extend(["", "## 故事", "", story])
    return front, body


ARTIFACT_SLOTS = ["生之花", "死之羽", "时之沙", "空之杯", "理之冠"]


def render_artifact(page: dict, meta: dict | None, entry_path: Path, args) -> tuple[dict, list[str]]:
    rarity = ""
    for data in _component_data(page, "rich_base_info"):
        for item in data.get("list") or []:
            if "稀有度" in (item.get("key") or ""):
                values = item.get("value") or []
                if values:
                    rarity = html_inline(values[0])
                break
        if rarity:
            break

    slots: list[tuple[str, str, str, str]] = []
    for module in page.get("modules") or []:
        slot_name = (module.get("name") or "").strip()
        for comp in module.get("components") or []:
            if comp.get("component_id") != "artifact_list_v2":
                continue
            data = as_json(comp.get("data")) or {}
            # 有些页面模块名是空的，部位名在 name.key 里（如「生之花：」）
            if slot_name not in ARTIFACT_SLOTS:
                slot_name = ((data.get("name") or {}).get("key") or "").strip().rstrip("：: ")
            if slot_name not in ARTIFACT_SLOTS:
                continue
            name = html_inline(((data.get("name") or {}).get("value") or [""])[0])
            desc = html_paragraphs((((data.get("desc") or {}).get("value") or [""])[0]))
            story_html = "".join((data.get("story") or {}).get("value") or [])
            story = html_paragraphs(story_html)
            # 空占位（祭火之人等只有理之冠有内容）直接跳过，不留空标题
            if not name and not story.strip():
                continue
            slots.append((slot_name, name, desc, story))

    notes = "观测枢 entry_page 导出；只收五个部位的描述与故事，不含套装数值、推荐搭配。"
    if len(slots) < 5:
        notes += f" OBC 仅收录 {len(slots)} 个部位，其余部位在来源页为空。"
    front = {
        "id": args.doc_id,
        "type": "artifact",
        "subtype": "set",
        "title": args.title or page.get("name") or "",
        "language": "zh-Hans",
        "region": args.region,
        "version": args.version,
        "version_source": args.version_source,
        "version_confidence": args.version_confidence,
        "canon_status": "community",
        "transcription": "near-verbatim",
        "spoiler": {"level": args.spoiler, "scope": args.scope or []},
        "source": [source_block(meta, page, entry_path)],
        "status": "draft",
        "notes": notes,
    }
    if not front.get("region"):
        front.pop("region", None)
    if not front.get("version"):
        front.pop("version", None)

    body: list[str] = ["## 套装信息", ""]
    if rarity:
        body.append(f"- 稀有度：{rarity}")
    if args.version:
        body.append(f"- 版本：{args.version}")
    body.append("- 来源：米游社·观测枢")
    body.append(f"- 部件：{len(slots)}/5")

    for slot, name, desc, story in slots:
        heading = f"{slot} · {name}" if name else slot
        body.extend(["", f"## {heading}"])
        if desc:
            body.extend(["", f"> {desc}"])
        if story:
            body.extend(["", story])
    return front, body


EVENT_TEXT_MODULES = ("活动说明", "游戏内活动说明")
EVENT_DIALOGUE_MODULES = ("剧情", "彩蛋")
# 只认明确是叙述的字段；自定义小标题多为玩法规则，不收
EVENT_KEYWORDS = ("简介", "背景")


def render_event(page: dict, meta: dict | None, entry_path: Path, args) -> tuple[dict, list[str]]:
    """活动页：只收概述、活动简介、剧情对话/彩蛋；数值、奖励、攻略、公告表一律不收。"""
    title = args.title or page.get("name") or ""

    overview: list[tuple[str, str]] = []
    intro_lines: list[str] = []
    dialogue_blocks: list[tuple[str, list[str]]] = []

    for module in page.get("modules") or []:
        name = (module.get("name") or "").strip()
        comps = module.get("components") or []

        # 与页面同名的概述模块（官方公告格式含 〓 段落，属于奖励/规则，不收）
        if name and name == title:
            for comp in comps:
                if comp.get("component_id") == "collapse_panel":
                    text = html_paragraphs((as_json(comp.get("data")) or {}).get("rich_text", ""))
                    if text and "〓" not in text:
                        overview.append((name, text))

        # 活动说明里的「简介 / 说明」字段
        if name in EVENT_TEXT_MODULES:
            for comp in comps:
                if comp.get("component_id") != "rich_base_info":
                    continue
                data = as_json(comp.get("data")) or {}
                for item in data.get("list") or []:
                    key = (item.get("key") or "").strip("【】 ")
                    if not any(k in key for k in EVENT_KEYWORDS):
                        continue
                    for value in item.get("value") or []:
                        text = html_paragraphs(value)
                        if text:
                            intro_lines.append(text)

        # 剧情对话 / 角色对话彩蛋
        if any(k in name for k in EVENT_DIALOGUE_MODULES):
            for comp in comps:
                if comp.get("component_id") != "interactive_dialogue":
                    continue
                data = as_json(comp.get("data")) or {}
                lines: list[str] = []
                for group in dialogue_groups(data):
                    part, _, _ = render_dialogue_group(group)
                    lines.extend(part)
                if lines:
                    dialogue_blocks.append((name or "剧情对话", lines))

    notes = "观测枢活动页导出；只收活动概述、活动简介与剧情对话/彩蛋，不含奖励、攻略、公告表格。"
    front = {
        "id": args.doc_id,
        "type": "event",
        "subtype": args.subtype or "活动",
        "title": title,
        "language": "zh-Hans",
        "region": args.region,
        "version": args.version,
        "version_source": args.version_source,
        "version_confidence": args.version_confidence,
        "canon_status": "community",
        "transcription": "near-verbatim",
        "spoiler": {"level": args.spoiler, "scope": args.scope or []},
        "source": [source_block(meta, page, entry_path)],
        "status": "draft",
        "notes": notes,
    }
    if not front.get("region"):
        front.pop("region", None)
    if not front.get("version"):
        front.pop("version", None)

    body: list[str] = ["## 活动信息", ""]
    body.append(f"- 类型：{args.subtype or '活动'}")
    if args.version:
        body.append(f"- 版本：{args.version}")
    body.append("- 来源：米游社·观测枢")

    for name, text in overview:
        body.extend(["", f"## {name}", "", text])

    if intro_lines:
        body.extend(["", "## 活动简介", ""])
        for text in intro_lines:
            body.extend([text, ""])
        if body[-1] == "":
            body.pop()

    for name, lines in dialogue_blocks:
        body.extend(["", f"## {name}", ""])
        body.extend(lines)

    return front, body


def render_geography(page: dict, meta: dict | None, entry_path: Path, args) -> tuple[dict, list[str]]:
    """观景点/地点页：只收 collapse_panel 里的描述文字，跳过图片与考据。"""
    title = args.title or page.get("name") or ""
    texts: list[str] = []
    for module in page.get("modules") or []:
        for comp in module.get("components") or []:
            if comp.get("component_id") != "collapse_panel":
                continue
            data = as_json(comp.get("data")) or {}
            html = data.get("rich_text") or ""
            # 去掉内嵌图片块，避免把图片 URL 当正文
            html = re.sub(r'<span class="custom-image-view".*?</span>', "", html, flags=re.S)
            html = re.sub(r"<img[^>]*>", "", html, flags=re.I)
            text = html_paragraphs(html)
            if text:
                texts.append(text)

    # 首段常是居中的标题，去掉与标题重复的行
    cleaned: list[str] = []
    for text in texts:
        lines = [l for l in text.splitlines() if l.strip() and l.strip() != title]
        if lines:
            cleaned.append("\n\n".join(lines))

    notes = "观测枢观景点页导出；只收描述文字，跳过地图、图片与考据推荐。"
    front = {
        "id": args.doc_id,
        "type": "geography",
        "subtype": args.subtype or "观景点",
        "title": title,
        "language": "zh-Hans",
        "region": args.region,
        "version": args.version,
        "version_source": args.version_source,
        "version_confidence": args.version_confidence,
        "canon_status": "community",
        "transcription": "near-verbatim",
        "spoiler": {"level": args.spoiler, "scope": args.scope or []},
        "source": [source_block(meta, page, entry_path)],
        "status": "draft",
        "notes": notes,
    }
    if not front.get("region"):
        front.pop("region", None)
    if not front.get("version"):
        front.pop("version", None)

    body: list[str] = []
    for text in cleaned:
        body.extend(["## 描述", "", text, ""])
    while body and body[-1] == "":
        body.pop()
    return front, body


def render_item(page: dict, meta: dict | None, entry_path: Path, args) -> tuple[dict, list[str]]:
    """材料/食物/鱼/道具：只收「描述」与「背景故事」，不收效果、配方、分布、攻略。"""
    title = args.title or page.get("name") or ""
    blocks: list[tuple[str, str]] = []
    star = None

    for module in page.get("modules") or []:
        mname = (module.get("name") or "").strip()
        for comp in module.get("components") or []:
            cid = comp.get("component_id")
            data = as_json(comp.get("data")) or {}
            if cid == "material_base_info":
                if star is None and data.get("star"):
                    star = data.get("star")
                name = (data.get("name") or title).strip()
                desc_parts = []
                for attr in data.get("attr") or []:
                    key = (attr.get("key") or "").strip()
                    if "描述" not in key:
                        continue
                    for value in attr.get("value") or []:
                        text = html_paragraphs(value)
                        if text:
                            desc_parts.append(text)
                if desc_parts:
                    blocks.append((name, "\n\n".join(desc_parts)))
            elif cid == "good_desc" and ("背景" in mname or "故事" in mname):
                text = html_paragraphs(data.get("rich_text", ""))
                if text:
                    blocks.append((mname or "背景故事", text))

    # 单块且与标题同名时，用「描述」作小标题
    if len(blocks) == 1 and blocks[0][0] == title:
        blocks = [("描述", blocks[0][1])]

    notes = "观测枢物品页导出；只收描述/背景故事，不含使用效果、配方、获取途径与攻略。"
    front = {
        "id": args.doc_id,
        "type": "item",
        "subtype": args.subtype or "物品",
        "title": title,
        "language": "zh-Hans",
        "region": args.region,
        "version": args.version,
        "version_source": args.version_source,
        "version_confidence": args.version_confidence,
        "canon_status": "community",
        "transcription": "near-verbatim",
        "spoiler": {"level": args.spoiler, "scope": args.scope or []},
        "source": [source_block(meta, page, entry_path)],
        "status": "draft",
        "notes": notes,
    }
    if not front.get("region"):
        front.pop("region", None)
    if not front.get("version"):
        front.pop("version", None)

    body: list[str] = ["## 物品信息", ""]
    body.append(f"- 类型：{args.subtype or '物品'}")
    if star:
        body.append(f"- 稀有度：{star} 星")
    body.append("- 来源：米游社·观测枢")

    for heading, text in blocks:
        body.extend(["", f"## {heading}", "", text])
    return front, body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entry", type=Path, required=True)
    parser.add_argument("--type", choices=["quest", "book", "character", "lore", "weapon", "artifact", "event", "geography", "item"], required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--doc-id", required=True)
    parser.add_argument("--title")
    parser.add_argument("--subtype")
    parser.add_argument("--region", default="")
    parser.add_argument("--version", default="")
    parser.add_argument(
        "--version-source",
        default="unknown",
        choices=["obc-filter", "bwiki", "official", "manual", "derived-related-quest", "web", "unknown"],
    )
    parser.add_argument(
        "--version-confidence",
        default="unknown",
        choices=["confirmed", "likely", "inferred", "estimated", "unknown"],
    )
    parser.add_argument("--spoiler", type=int, default=1)
    parser.add_argument("--scope", action="append", default=[])
    parser.add_argument("--versions-manifest", type=Path, default=DEFAULT_VERSIONS)
    parser.add_argument("--index-manifest", type=Path, default=DEFAULT_INDEX)
    args = parser.parse_args()

    version_rows = {}
    if args.versions_manifest.exists():
        with args.versions_manifest.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                version_rows[str(row.get("entry_page_id", "")).strip()] = row
    index_rows = {}
    if args.index_manifest.exists():
        with args.index_manifest.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                index_rows[str(row.get("entry_page_id", "")).strip()] = row

    payload = json.loads(args.entry.read_text(encoding="utf-8"))
    page = ((payload.get("data") or {}).get("page") or {})
    if not page:
        raise SystemExit("entry JSON has no data.page")

    entry_id = str(page.get("id") or args.entry.stem)
    version_row = version_rows.get(entry_id) or index_rows.get(entry_id)
    if version_row:
        if not args.version:
            args.version = (version_row.get("version") or "").strip()
        if not args.region:
            args.region = (version_row.get("region") or "").strip()
        if args.version_source == "unknown":
            args.version_source = (version_row.get("version_source") or "unknown").strip()
        if args.version_confidence == "unknown":
            args.version_confidence = (version_row.get("version_confidence") or "unknown").strip()

    meta_path = args.entry.parent.parent / "meta" / f"{args.entry.stem}.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else None

    renderers = {
        "quest": render_quest,
        "book": render_book,
        "character": render_character,
        "lore": render_lore,
        "weapon": render_weapon,
        "artifact": render_artifact,
        "event": render_event,
        "geography": render_geography,
        "item": render_item,
    }
    front, body = renderers[args.type](page, meta, args.entry, args)

    front_yaml = yaml.safe_dump(front, allow_unicode=True, sort_keys=False, width=120)
    text = f"---\n{front_yaml}---\n\n" + "\n".join(body).rstrip() + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {args.out} ({len(text)} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
