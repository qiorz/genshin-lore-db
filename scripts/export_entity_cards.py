#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把知识层种子导出为便于人工阅读的 Markdown 卡片。

权威来源：knowledge/seed*.yaml（可编辑，自动合并所有批次）
查询层：  db/genshin_lore.sqlite3 的 entities / entity_relations / claims / timeline_entries
导出视图：knowledge/entities/**.md、knowledge/events/*.md、
          knowledge/claims/*.md、knowledge/timelines/*.md

这些 Markdown 是**生成物**，不要手改。要改结论就改 seed*.yaml，
重跑 `load_knowledge.py --apply` 再跑本脚本。

用法：
    python scripts/export_entity_cards.py            # 干跑，只报告文件数
    python scripts/export_entity_cards.py --apply    # 写出文件
"""
from __future__ import annotations

import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = ROOT / "knowledge"
SEED_FILES = sorted(SEED_DIR.glob("seed*.yaml"),
                    key=lambda p: (p.name != "seed.yaml", p.name))
DB = ROOT / "db/genshin_lore.sqlite3"
OUT = ROOT / "knowledge"
APPLY = "--apply" in sys.argv
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

TYPE_DIR = {
    "deity": "characters", "character": "characters",
    "nation": "nations", "organization": "organizations",
    "location": "locations", "creature": "creatures",
    "concept": "concepts", "item": "concepts", "title": "concepts",
    "event": "concepts", "other": "concepts",
}
PREDICATE_LABELS = {
    "deity_of": "神明／统御", "member_of": "成员所属",
    "subordinate_to": "效忠于", "operated_by": "由…运营",
    "legacy_of": "继承自", "manifestation_of": "化身／体现",
    "guardian_of": "守护", "origin_of": "出身自",
    "companion_of": "同行者", "created_by": "由…创造",
    "has": "拥有", "symbol_of": "象征", "located_in": "位于",
    "nearest_to": "最接近", "based_in": "根据地在",
    "granted_by": "授予对象", "involved_in": "涉及事件",
}
CONF_LABELS = {
    "confirmed": "已确认", "likely": "较可能", "speculative": "推测",
    "disputed": "有争议", "unreliable": "不可靠叙述",
}


def load_seeds() -> dict:
    """与 load_knowledge.py 用同一套合并规则，保证卡片与数据库一致。"""
    merged = {"entities": [], "claims": [], "events": []}
    for path in SEED_FILES:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        status = data.get("status", "draft")
        batch = data.get("batch", path.stem)
        for entity in data.get("entities") or []:
            entity = dict(entity)
            entity["_status"] = entity.get("status", status)
            entity["_batch"] = batch
            merged["entities"].append(entity)
        for key in ("claims", "events"):
            merged[key].extend(data.get(key) or [])
    return merged


def slug(entity_id: str) -> str:
    return re.sub(r"[^a-z0-9-]", "-", entity_id.removeprefix("entity.").lower())


def yaml_list(values) -> str:
    if not values:
        return " []"
    return "\n" + "\n".join(f"  - {v}" for v in values)


def doc_link(doc_id: str, ordinal: int | None = None) -> str:
    return f"[[{doc_id}]]" + (f" 第 {ordinal} 段" if ordinal is not None else "")


def main() -> int:
    data = load_seeds()
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    files: dict[Path, str] = {}

    # --- 实体卡片 -----------------------------------------------------------
    for item in data["entities"]:
        eid = item["id"]
        rels = con.execute(
            """SELECT r.predicate, r.object_literal, r.confidence, r.doc_id,
                      r.notes, e.canonical_name AS object_name, s.ordinal
               FROM entity_relations r
               LEFT JOIN entities e ON e.entity_id = r.object_id
               LEFT JOIN sections s ON s.section_id = r.section_id
               WHERE r.subject_id=? ORDER BY r.relation_id""",
            (eid,),
        ).fetchall()
        incoming = con.execute(
            """SELECT r.predicate, r.confidence, e.canonical_name AS subject_name, r.doc_id
               FROM entity_relations r
               JOIN entities e ON e.entity_id = r.subject_id
               WHERE r.object_id=? AND r.predicate<>'involved_in'
               ORDER BY r.relation_id""",
            (eid,),
        ).fetchall()
        claims = con.execute(
            """SELECT c.statement, c.confidence, c.status, c.doc_id, c.perspective, s.ordinal
               FROM claims c LEFT JOIN sections s ON s.section_id=c.section_id
               WHERE c.subject_id=? ORDER BY c.claim_id""",
            (eid,),
        ).fetchall()

        key_lines = []
        for r in rels:
            obj = r["object_name"] or r["object_literal"] or ""
            label = PREDICATE_LABELS.get(r["predicate"], r["predicate"])
            conf = CONF_LABELS.get(r["confidence"], r["confidence"])
            link = doc_link(r["doc_id"], r["ordinal"]) if r["doc_id"] else ""
            key_lines.append(f"- **{label}** → {obj}（{conf}）· {link}")
        for r in incoming:
            label = PREDICATE_LABELS.get(r["predicate"], r["predicate"])
            key_lines.append(f"- 反向：{r['subject_name']} —{label}→ 本实体"
                             f"（{CONF_LABELS.get(r['confidence'], r['confidence'])}）")

        claim_lines = []
        for c in claims:
            claim_lines.append(
                f"- {c['statement']}（{CONF_LABELS.get(c['confidence'], c['confidence'])} / "
                f"{c['status']}；{c['perspective'] or '未标视角'}）· "
                f"{doc_link(c['doc_id'], c['ordinal'])}"
            )

        evidence_lines = [f"- {doc_link(ev['doc'])}：{ev['quote']}"
                          for ev in item.get("evidence") or []]

        pending = ["- 关系与说法的完整证据见 `knowledge/seed*.yaml`；本卡片由脚本生成，不要手改。"]
        if not rels:
            pending.append("- 该实体暂无关系边，待补。")
        if not claims:
            pending.append("- 该实体暂无说法条目，待补。")

        aliases = [a["name"] for a in item.get("aliases") or []]
        body = "\n".join([
            "---",
            f"id: {eid}",
            f"type: {item['type']}",
            f"canonical_name: {item['name']}",
            f"canonical_name_en: {item.get('name_en') or ''}",
            "aliases:" + yaml_list(aliases),
            f"spoiler_level: {int(item.get('spoiler', 0))}",
            f"status: {item['_status']}",
            "tags: [知识层种子]",
            "---", "",
            "## 简介", "",
            item.get("description", ""), "",
            "## 关键设定", "",
            "\n".join(key_lines) or "- 暂无", "",
            f"## 说法（{len(claims)}）", "",
            "\n".join(claim_lines) or "- 暂无", "",
            f"## 证据（{len(evidence_lines)}）", "",
            "\n".join(evidence_lines) or "- 暂无", "",
            "## 待考", "",
            "\n".join(pending), "",
        ])
        files[OUT / "entities" / TYPE_DIR[item["type"]] / f"{slug(eid)}.md"] = body

    # --- 说法卡片 -----------------------------------------------------------
    for item in data["claims"]:
        cid = item["id"]
        body = "\n".join([
            "---",
            f"id: claim.{cid}",
            f"subject: {item['subject']}",
            f"predicate: {item['predicate']}",
            f"perspective: {item.get('perspective') or ''}",
            f"confidence: {item['confidence']}",
            f"status: {item['status']}",
            f"spoiler_level: {int(item.get('spoiler', 0))}",
            "---", "",
            "## 说法", "",
            item["statement"], "",
            "## 证据", "",
            f"- {doc_link(item['doc'])}：{item['quote']}", "",
            "## 备注", "",
            item.get("notes") or "无。", "",
            "> 置信度与视角是刻意的：角色台词不自动等于设定，矛盾说法按「矛盾是数据不是错误」保留。", "",
        ])
        files[OUT / "claims" / f"claim-{cid}.md"] = body

    # --- 事件卡片 -----------------------------------------------------------
    for item in data["events"]:
        evid = item["id"]
        participants = [f"- [[{e}]]" for e in item.get("entities") or []]
        body = "\n".join([
            "---",
            f"id: {evid}",
            f"name: {item['name']}",
            f"event_type: {item.get('event_type') or ''}",
            "era: teyvat",
            f"time_certainty: {item['time_certainty']}",
            f"spoiler_level: {int(item.get('spoiler', 0))}",
            "---", "",
            "## 事件", "",
            item.get("description", ""), "",
            "## 时间", "",
            f"- 相对位置：{item.get('relative_time')}",
            f"- 绝对年份：**未标注**（{item['certainty']}，原文为约数或仅相对顺序）",
            f"- `sort_key = {item['sort_key']}` 只表示先后，不代表年代数值。", "",
            "## 证据", "",
            f"- {doc_link(item['doc'])}：{item['quote']}", "",
            "## 涉及实体", "",
            "\n".join(participants) or "- 暂无", "",
        ])
        files[OUT / "events" / f"{slug(evid)}.md"] = body

    # --- 时间线汇总 ---------------------------------------------------------
    lore = con.execute(
        """SELECT t.*, e.name AS event_name FROM timeline_entries t
           LEFT JOIN events e ON e.event_id=t.event_id
           WHERE t.era='teyvat' ORDER BY t.sort_key"""
    ).fetchall()
    lines = [
        "---", "id: timeline.teyvat", "name: 提瓦特纪年（相对顺序）",
        "era: teyvat", "---", "",
        "# 提瓦特纪年 · 只有相对顺序", "",
        "> 这一条是**游戏内世界的事件顺序**，没有可信绝对年份时一律留空。",
        "> `sort_key` 是负数，只表示先后，不代表任何年代数值；",
        "> 与现实版本上线日期（`版本上线时间线.md`）**不可互相换算**。", "",
        "| 顺序 | 事件 | 相对时间 | 确定性 | 出处 |", "|---:|---|---|---|---|",
    ]
    for i, r in enumerate(lore, 1):
        src = doc_link(r["doc_id"]) if r["doc_id"] else "—"
        lines.append(f"| {i} | {r['label']} | {r['relative_time'] or '—'} | "
                     f"{r['certainty']} | {src} |")
    lines += ["", "## 待考", "", "- 全部 8 条均为相对顺序；后续如有官方明确纪年再补 absolute_year。", ""]
    files[OUT / "timelines" / "提瓦特纪年.md"] = "\n".join(lines)

    releases = con.execute(
        "SELECT * FROM timeline_entries WHERE era='release' ORDER BY sort_key, entry_id"
    ).fetchall()
    lines = [
        "---", "id: timeline.release", "name: 现实版本上线时间线",
        "era: release", "---", "",
        "# 现实版本上线时间线", "",
        "> 这是**现实世界的官方版本更新说明发布日期**（1.1 → 7.2），不是提瓦特纪年。",
        "> 数据来自 `corpus/notices/` 的官方公告，由 `load_knowledge.py` 自动生成，",
        "> 不手写、不猜测；`certainty = exact`。", "",
        "| 版本 | 上线日期 | 官方说明 |", "|---|---|---|",
    ]
    for r in releases:
        version = r["label"].split(" 版本上线", 1)[0]
        src = doc_link(r["doc_id"]) if r["doc_id"] else "—"
        lines.append(f"| {version} | {r['relative_time'] or '—'} | {src} |")
    lines += ["", f"共 {len(releases)} 个版本，覆盖 1.1 → 7.2，无断档。", ""]
    files[OUT / "timelines" / "版本上线时间线.md"] = "\n".join(lines)

    # --- 写出 ---------------------------------------------------------------
    groups: dict[str, int] = defaultdict(int)
    for path in files:
        groups[str(path.parent.relative_to(OUT))] += 1
    for k, v in sorted(groups.items()):
        print(f"  {k:28} {v:3} 个文件")
    print(f"合计 {len(files)} 个 Markdown 卡片，模式：{'写出' if APPLY else '干跑'}")
    if APPLY:
        for path, text in files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
        print("写出完成")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
