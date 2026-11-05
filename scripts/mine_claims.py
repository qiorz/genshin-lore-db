#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从「角色关联语音」里提取 claims：谁在什么立场下说了什么。

为什么从 Markdown 而不是库：导入时按标题切段，`## 角色关联语音` 下面
「说话人名字 → 若干段话」的结构被拍平了，`sections.speaker` 是空的。
原始 Markdown 还在，署名也还在，直接从那里读最省事。

结构长这样：
    ## 角色关联语音
    角色
    关于娜维娅...
    杜林
    有机会的话，我还想去感谢星轨王城的国王…
    芙宁娜
    【关于娜维娅·甜点】你尝过娜维娅烤的马卡龙吗？…

抽取规则：
  - 独立成行、无标点、长度 ≤8 的行 = 说话人（`角色`/`关于X...` 这类跳过）；
  - 之后直到下一个说话人的段落 = 他的话；
  - `【关于X·主题】…` → 主语 X、谓词=主题；其余段落 → 主语=本页角色、谓词=评价；
  - 要求主语是库里已有的实体；普通段落还必须提到主语并带评价词，否则是闲话，不收。

用法：
    python scripts/mine_claims.py            # 干跑
    python scripts/mine_claims.py --apply    # 写 knowledge/seed-stage7.yaml
"""
from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "db/genshin_lore.sqlite3"
CSV_OUT = ROOT / "knowledge/claim-candidates.csv"
YAML_OUT = ROOT / "knowledge/seed-stage7.yaml"
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

CLAIM_BASE = 4000          # 人工 claims 占 1000 段，本批用 4000 段
MAX_STATEMENT = 240
EVAL_WORDS = ("认为", "觉得", "看来", "似乎", "据说", "听说", "其实", "并不",
              "不是", "应该", "一定", "从来", "总是", "最", "太", "像", "可惜")
NOT_SPEAKER = {"角色", "角色关联语音", "语音", "关于"}
TOPIC = re.compile(r"【关于(.+?)(?:[·・](.+?))?】(.+)", re.S)


def blocks(text: str) -> list[str]:
    return [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]


def is_speaker_line(line: str) -> bool:
    if not line or len(line) > 8 or line in NOT_SPEAKER or line.endswith("..."):
        return False
    return not re.search(r"[。！？，、；：【」』（）()]", line)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    ents = {r["canonical_name"]: dict(r) for r in con.execute(
        "SELECT entity_id, canonical_name, entity_type, spoiler_level FROM entities")}
    doc_ids = {}
    for r in con.execute("SELECT doc_id, title FROM documents WHERE doc_type='character'"):
        doc_ids.setdefault(r["title"], r["doc_id"])

    rows, seen = [], set()
    total_blocks = skipped = 0
    for path in sorted((ROOT / "corpus/characters").rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        if "## 角色关联语音" not in text:
            continue
        page = path.stem
        doc_id = doc_ids.get(page)
        if not doc_id:
            continue
        body = text.split("## 角色关联语音", 1)[1].split("\n## ", 1)[0]
        speaker = None
        for b in blocks(body):
            line = b.replace("\n", "").strip()
            if is_speaker_line(line):
                speaker = line
                continue
            total_blocks += 1
            m = TOPIC.match(line)
            if m:
                subject, topic, statement = m.group(1), m.group(2) or "评价", m.group(3)
            else:
                subject, topic, statement = page, "评价", line
            if not speaker or speaker == subject or len(statement) < 20:
                skipped += 1
                continue
            if subject not in ents:
                skipped += 1
                continue
            # 普通段落：必须提到主语且有评价语气，否则只是闲聊
            if not m and (subject not in statement
                          or not any(w in statement for w in EVAL_WORDS)):
                skipped += 1
                continue
            key = (subject, speaker, statement[:40])
            if key in seen:
                skipped += 1
                continue
            seen.add(key)
            rows.append({
                "subject": ents[subject]["entity_id"], "subject_name": subject,
                "predicate": topic.strip(), "statement": statement,
                "perspective": speaker, "doc": doc_id,
                "spoiler": ents[subject]["spoiler_level"] or 1,
                "page": page,
            })

    print(f"扫描段落 {total_blocks}，保留 {len(rows)}，跳过 {skipped}")
    print("谓词分布前 8：", Counter(r["predicate"] for r in rows).most_common(8))

    with CSV_OUT.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["subject_id", "subject", "predicate", "perspective", "doc_id",
                    "statement"])
        for r in rows:
            w.writerow([r["subject"], r["subject_name"], r["predicate"],
                        r["perspective"], r["doc"], r["statement"]])
    print(f"候选清单 -> {CSV_OUT}")

    print("\n样例：")
    for r in rows[:5]:
        print(f"  [{r['subject_name']}·{r['predicate']}] {r['perspective']}："
              f"{r['statement'][:52]}")

    if args.apply:
        payload = {
            "version": 1, "batch": "2026-11-05-stage7", "status": "draft",
            "claims": [
                {"id": CLAIM_BASE + i, "subject": r["subject"],
                 "predicate": r["predicate"], "object": "",
                 "statement": r["statement"], "perspective": r["perspective"],
                 "confidence": "likely", "status": "open", "spoiler": r["spoiler"],
                 "doc": r["doc"],
                 "quote": r["statement"][:MAX_STATEMENT]}
                for i, r in enumerate(rows, 1)
            ],
        }
        YAML_OUT.write_text(
            "# 第七批知识层种子 · claims（由 scripts/mine_claims.py 生成）\n"
            "# 来源：corpus/characters 的「角色关联语音」，署名按说话人分行还原。\n"
            "# confidence=likely：这是某个角色的说法，不是旁白定论；perspective 记说话人。\n"
            "# 普通段落必须提到主语并带评价词才收，纯闲聊不收。\n"
            + yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=200),
            encoding="utf-8")
        print(f"已写入 {YAML_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
