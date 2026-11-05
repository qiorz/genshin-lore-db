#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给待复核的实体排优先级，并登记复核结论。

为什么需要排序：220 张 `status=draft` 平铺着复核看不完。真正该先看的是
**会被别处引用**的实体——出现在越多篇文档里，它的类型/名字错得越贵。

排序口径（都可复算，不掺主观权重）：
  1. `quest_docs`：出现在多少篇任务正文里（剧情主干，优先级最高）；
  2. `doc_count`：出现在多少篇文档里（覆盖广度）；
  3. 同分时按证据文档的正文长度降序，长的通常信息更多。

同时做三项**机械校验**（不需要人判断的部分）：
  - 引文是否真的出现在它声称的那一篇里；
  - 名字是否真的出现在引文里；
  - 角色的类型是否与来源文档 `doc_type='character'` 一致。

用法：
    python scripts/review_queue.py                 # 生成队列（默认前 30），打印摘要
    python scripts/review_queue.py --top 50        # 只看前 50
    python scripts/review_queue.py --mark entity.x --note "类型/名字/引文一致"
    python scripts/review_queue.py --unmark entity.x
"""
from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "db/genshin_lore.sqlite3"
STATE = ROOT / "knowledge/review-state.yaml"
OUT_DIR = ROOT / "exports/review"
CSV_OUT = OUT_DIR / "entity-review-queue.csv"
MD_OUT = OUT_DIR / "entity-review-queue.md"
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

TYPE_LABEL = {"character": "人物", "location": "地点", "organization": "组织",
              "concept": "概念", "nation": "国家", "creature": "生物",
              "deity": "神明", "event": "事件", "item": "物品",
              "title": "称号", "other": "其他"}


def norm(text: str) -> str:
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", text or "")


def load_state() -> dict:
    if not STATE.exists():
        return {"reviewed": [], "rejected": []}
    data = yaml.safe_load(STATE.read_text(encoding="utf-8")) or {}
    data.setdefault("reviewed", [])
    data.setdefault("rejected", [])
    return data


def save_state(data: dict) -> None:
    STATE.write_text(
        "# 人工复核记录。只记 id 与结论，不改由脚本生成的 seed-*.yaml。\n"
        "# build_stage4.py 会读这里，把命中的实体写成 status: reviewed。\n"
        + yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=200),
        encoding="utf-8",
    )


def collect(con: sqlite3.Connection) -> list[dict]:
    """待复核实体 + 主证据 + 提及统计。

    注意：一个实体现在可能有多条 entity_evidence（高频实体给了 3 个锚点），
    所以不能直接 LEFT JOIN，否则同一个实体会出现多行、排队会重复。
    这里先取「主锚点」一张表，再按 entity_id 对回。
    """
    entities = con.execute(
        """SELECT entity_id, canonical_name, entity_type, description, status
           FROM entities WHERE status <> 'reviewed' ORDER BY entity_id"""
    ).fetchall()

    ev_map: dict[str, tuple[str, int | None, str]] = {}
    for row in con.execute(
        """SELECT entity_id, doc_id, section_id, quote FROM entity_evidence
           ORDER BY is_primary DESC, evidence_id"""
    ):
        ev_map.setdefault(row["entity_id"], (row["doc_id"], row["section_id"], row["quote"]))

    doc_meta = {r["doc_id"]: (r["doc_type"], r["title"])
                for r in con.execute("SELECT doc_id, doc_type, title FROM documents")}
    sec_speaker = {r["section_id"]: r["speaker"]
                   for r in con.execute("SELECT section_id, speaker FROM sections")}

    out = []
    for r in entities:
        name = r["canonical_name"]
        doc_id, section_id, quote = ev_map.get(r["entity_id"], ("", None, ""))
        ev_type, ev_title = doc_meta.get(doc_id, ("", ""))
        docs, sections = con.execute(
            """SELECT COUNT(DISTINCT doc_id), COUNT(*) FROM sections WHERE body LIKE ?""",
            (f"%{name}%",),
        ).fetchone()
        quests = con.execute(
            """SELECT COUNT(DISTINCT s.doc_id) FROM sections s
               JOIN documents d ON d.doc_id = s.doc_id
               WHERE d.doc_type = 'quest' AND s.body LIKE ?""",
            (f"%{name}%",),
        ).fetchone()[0]
        quote_hit = None
        if quote and doc_id:
            quote_hit = bool(con.execute(
                "SELECT COUNT(*) FROM sections WHERE doc_id=? AND body LIKE ?",
                (doc_id, f"%{quote[:20]}%"),
            ).fetchone()[0])
        out.append({
            "entity_id": r["entity_id"], "name": name, "type": r["entity_type"],
            "description": r["description"] or "", "doc_id": doc_id,
            "ev_type": ev_type, "ev_title": ev_title,
            "quote": quote, "doc_count": docs, "quest_docs": quests,
            "section_count": sections,
            "quote_in_doc": bool(quote_hit),
            # 人物的证据常常是他自己的台词，说话人匹配也算命中
            "quote_has_name": bool(quote and (name in quote
                                              or sec_speaker.get(section_id) == name)),
            # 只有证据取自角色页的角色才谈得上「类型一致」
            "type_ok": (r["entity_type"] != "character")
                       or (not doc_id.startswith("char."))
                       or (ev_type == "character"),
        })
    out.sort(key=lambda x: (-x["quest_docs"], -x["doc_count"], -x["section_count"]))
    return out


def write_reports(items: list[dict], top: int) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_OUT.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["rank", "entity_id", "name", "type", "quest_docs", "doc_count",
                    "sections", "quote_in_doc", "quote_has_name", "type_ok",
                    "evidence_doc", "quote", "description"])
        for i, x in enumerate(items, 1):
            w.writerow([i, x["entity_id"], x["name"], TYPE_LABEL.get(x["type"], x["type"]),
                        x["quest_docs"], x["doc_count"], x["section_count"],
                        "是" if x["quote_in_doc"] else "否",
                        "是" if x["quote_has_name"] else "否",
                        "是" if x["type_ok"] else "否",
                        x["doc_id"], x["quote"], x["description"]])

    lines = [
        "# 实体复核队列",
        "",
        f"> 生成于 {date.today().isoformat()} · 待复核 {len(items)} 张 · 下表为前 {min(top, len(items))} 张",
        "",
        "排序口径：先按「出现在多少篇**任务**正文里」，再按「出现在多少篇文档里」。",
        "理由：被越多任务引用的实体，名字或类型写错的代价越大。",
        "",
        "机械校验三项（脚本自动做，不需人判断）：",
        "",
        "1. 引文是否真的在它声称的那一篇里；",
        "2. 名字是否真的出现在引文里；",
        "3. 人物的类型是否与来源文档（`doc_type=character`）一致。",
        "",
        "人工只需判断：类型对不对、名字是不是通行写法、别名该不该补。",
        "",
        "| # | 名称 | 类型 | 任务 | 文档 | 引文在文中 | 引文含名 | 类型一致 |",
        "|---:|---|---|---:|---:|:---:|:---:|:---:|",
    ]
    for i, x in enumerate(items[:top], 1):
        mark = lambda b: "✓" if b else "✗"
        lines.append(
            f"| {i} | {x['name']} | {TYPE_LABEL.get(x['type'], x['type'])} | "
            f"{x['quest_docs']} | {x['doc_count']} | {mark(x['quote_in_doc'])} | "
            f"{mark(x['quote_has_name'])} | {mark(x['type_ok'])} |"
        )
    lines += ["", "## 逐条证据", ""]
    for i, x in enumerate(items[:top], 1):
        lines += [
            f"### {i}. {x['name']}（{TYPE_LABEL.get(x['type'], x['type'])}）",
            "",
            f"- 实体：`{x['entity_id']}`",
            f"- 出处：`{x['doc_id']}` {x['ev_title']}",
            f"- 原话：{x['quote']}",
            f"- 描述：{x['description']}",
            "",
        ]
    MD_OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--mark", help="把某个 entity_id 记为已复核")
    ap.add_argument("--note", default="", help="配合 --mark 记录结论")
    ap.add_argument("--unmark", help="撤销某个 entity_id 的复核记录")
    args = ap.parse_args()

    state = load_state()
    if args.mark:
        ids = {x["id"] for x in state["reviewed"]}
        if args.mark not in ids:
            state["reviewed"].append({"id": args.mark, "date": date.today().isoformat(),
                                      "note": args.note})
            save_state(state)
            print(f"已记入复核：{args.mark} {args.note}")
        else:
            print(f"已在复核列表中：{args.mark}")
        return 0
    if args.unmark:
        before = len(state["reviewed"])
        state["reviewed"] = [x for x in state["reviewed"] if x["id"] != args.unmark]
        save_state(state)
        print(f"已撤销 {args.unmark}（{before} -> {len(state['reviewed'])}）")
        return 0

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    items = collect(con)
    con.close()
    write_reports(items, args.top)

    bad = [x for x in items if x["quote_in_doc"] is False or x["type_ok"] is False
           or x["quote_has_name"] is False]
    print(f"待复核 {len(items)} 张 · 机械校验异常 {len(bad)} 张")
    for x in bad[:10]:
        print(f"  ! {x['name']}（{x['entity_id']}）"
              f"{'' if x['quote_in_doc'] else ' 引文未命中'}"
              f"{'' if x['type_ok'] else ' 类型不符'}"
              f"{'' if x['quote_has_name'] else ' 引文不含名'}")
    print(f"\n前 {min(args.top, len(items))} 张：")
    for i, x in enumerate(items[:args.top], 1):
        print(f"  {i:>2}. {x['name']:<10}{TYPE_LABEL.get(x['type'], x['type']):<4}"
              f"任务 {x['quest_docs']:>3} 篇 · 文档 {x['doc_count']:>3} 篇")
    print(f"\n报告 -> {MD_OUT}\n清单 -> {CSV_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
