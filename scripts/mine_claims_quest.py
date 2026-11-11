#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从任务对话里提「谁对谁说了什么」——只收评价词紧贴实体的情况。

为什么规则这么紧：说法层最怕把「顺带提到」当成「评价」。
「蒙德的市民们也很喜欢用」不是对蒙德的评价，但它含「蒙德」也含「喜欢」。
所以要求评价词与被评价的实体**在同一个短分句内、相距 ≤6 字**，
并且实体后面不能紧跟「的/上/里/中/们」——那说明它在修饰别的名词。

即便这样，仍会有 20~30% 的噪声（「都怪托马放了很多奇怪的东西」里
「奇怪」修饰的是「东西」）。所以这批统一标 `speculative`，
notes 里写清是机器提取、未逐条核对——说法可以存疑，但不能假装确定。

用法：
    python scripts/mine_claims_quest.py            # 干跑，打印样例
    python scripts/mine_claims_quest.py --apply    # 写 seed-stage10.yaml
"""
from __future__ import annotations

import csv
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "db/genshin_lore.sqlite3"
CSV_OUT = ROOT / "knowledge/claim-candidates-quest.csv"
YAML_OUT = ROOT / "knowledge/seed-stage10.yaml"
APPLY = "--apply" in sys.argv
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

CLAIM_BASE = 6000

# 只留真正的评价/态度词。「看来」「果然」单用太像推测副词，已剔除。
EVAL = ("觉得", "认为", "可惜", "遗憾", "厉害", "讨厌", "喜欢", "不错", "糟糕",
        "了不起", "可靠", "危险", "奇怪", "有趣", "无聊", "可怕", "温柔", "严格",
        "聪明", "愚蠢", "可笑", "荒唐", "值得", "佩服", "失望", "敬佩", "信任",
        "怀疑", "担心", "羡慕", "嫉妒", "尊敬", "迂腐", "无能", "了不起")
# 这些说话人不是「某个人」：旅行者/派蒙是玩家视角，？？？是未具名
BAD_SPEAKER = {"？？？", "旅行者", "空", "荧", "派蒙", "主持人", ""}
# 实体后面跟这些 = 它在修饰别的词，不是被评价的对象
TAIL_BAD = ("的", "上", "里", "中", "们", "内", "城", "港")
SPLIT = re.compile(r"[。！？!?…；\n]")


def main() -> int:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    ents = {r["canonical_name"]: r["entity_id"] for r in con.execute(
        "SELECT canonical_name, entity_id FROM entities")}
    pat = re.compile("|".join(sorted(map(re.escape, ents), key=len, reverse=True)))

    rows = con.execute(
        """SELECT s.speaker, s.body, s.doc_id, d.title
           FROM sections s JOIN documents d ON d.doc_id = s.doc_id
           WHERE d.doc_type = 'quest'
             AND s.speaker IS NOT NULL AND s.speaker <> ''"""
    ).fetchall()

    hits: list[dict] = []
    seen: set[tuple[str, str]] = set()
    stats = Counter()

    for r in rows:
        stats["段落"] += 1
        sp, body = r["speaker"], r["body"] or ""
        if sp in BAD_SPEAKER:
            stats["说话人是玩家/未具名"] += 1
            continue
        if not (12 <= len(body) <= 120):
            stats["长度不合适"] += 1
            continue
        names = set(pat.findall(body))
        if len(names) != 1:
            stats["同段出现多个实体 或 没有实体"] += 1
            continue
        name = names.pop()
        if name == sp or name in sp:
            stats["说的是自己"] += 1
            continue

        found = None
        for clause in SPLIT.split(body):
            clause = clause.strip()
            if not (6 <= len(clause) <= 34) or name not in clause:
                continue
            pos = clause.find(name)
            if clause[pos + len(name):pos + len(name) + 1] in TAIL_BAD:
                continue
            # 「不觉得」「你觉得…吗」是在问对方，不是自己的评价
            if "不觉得" in clause:
                continue
            if re.search(r"觉得[^。]{0,24}[？?吗]", clause):
                continue
            for w in EVAL:
                j = clause.find(w)
                if j < 0:
                    continue
                dist = (j - pos - len(name)) if j > pos else (pos - j - len(w))
                if dist <= 6:
                    found = (clause, w)
                    break
            if found:
                break
        if not found:
            stats["没有紧邻的评价词"] += 1
            continue
        if (name, sp) in seen:
            stats["同实体同说话人已收"] += 1
            continue
        seen.add((name, sp))
        hits.append({
            "entity": name, "speaker": sp, "statement": body.strip(),
            "clause": found[0], "trigger": found[1], "doc": r["doc_id"],
        })

    hits.sort(key=lambda x: (x["entity"], x["speaker"]))
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    with CSV_OUT.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["entity", "speaker", "statement", "clause", "trigger", "doc_id"])
        for h in hits:
            w.writerow([h["entity"], h["speaker"], h["statement"], h["clause"],
                        h["trigger"], h["doc"]])

    print(f"候选 {len(hits)} 条，涉及 {len({h['entity'] for h in hits})} 个实体，"
          f"{len({h['speaker'] for h in hits})} 个说话人")
    print("过滤统计：" + "、".join(f"{k} {v}" for k, v in stats.most_common()))
    print("\n样例 20 条：")
    for h in hits[:20]:
        print(f"  {h['entity']:<8}←{h['speaker']:<8}{h['statement'][:54]}")
    print(f"\n明细写入 {CSV_OUT.relative_to(ROOT)}")

    if not APPLY:
        print("（干跑，加 --apply 才写入种子）")
        return 0

    lines = [
        "# 第十批知识层种子 · 任务对话里的说法（由 scripts/mine_claims_quest.py 生成）",
        "# 判据：说话人明确 + 同段只有一个实体 + 评价词与实体在 6 字内 + 实体不是定语。",
        "# confidence=speculative：机器提取，未逐条核对；perspective 记说话人。",
        "# 噪声估计两到三成（「奇怪」可能修饰的是别的东西），所以不标 likely。",
        "version: 1",
        "batch: 2026-11-11-stage10",
        "status: draft",
        "claims:",
    ]
    for i, h in enumerate(hits, 1):
        lines.append(f"- id: {CLAIM_BASE + i}")
        lines.append(f"  subject: {ents[h['entity']]}")
        lines.append("  predicate: 评价")
        lines.append("  object: ''")
        lines.append(f"  statement: {h['statement']}")
        lines.append(f"  perspective: {h['speaker']}")
        lines.append("  confidence: speculative")
        lines.append("  status: open")
        lines.append("  spoiler: 1")
        lines.append(f"  doc: {h['doc']}")
        lines.append(f"  quote: {h['statement']}")
        lines.append(f"  notes: 任务对话机器提取；触发词「{h['trigger']}」；未逐条核对")
    YAML_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已写入 {YAML_OUT.relative_to(ROOT)}（{len(hits)} 条）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
