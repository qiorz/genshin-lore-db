#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从任务对话与叙述文本里提「谁对谁说了什么」——两个来源，两套判据。

来源一 · 任务对话里的评价
    要求评价词与实体**主谓紧邻**（中间只允许程度副词），并且实体不是定语
    （后面不能跟「的/上/里/中/们」）。
    为什么这么紧：「蒙德的市民们也很喜欢用」含「蒙德」也含「喜欢」，
    但它不是对蒙德的评价。放宽到「同句」时准头只有五成，紧到主谓相邻
    才到七成以上——代价是只剩六十来条。

来源二 · 传闻与争议句式
    「据说 / 传说 / 有人说 / 听闻 / 据称…」+ 实体，距离 ≤15 字。
    这一类的价值不在「是谁说的」，而在**它本身不确定**：
    「有人说他出身贫寒，对名与利有几近贪婪的渴望」——这种说法正该标低置信度。

两类的 confidence 不同：评价是某个角色的主观看法（likely），
传闻连说话人都不知道（speculative）。混在一起标，就等于把两者都当定论。

用法：
    python scripts/mine_claims_dialogue.py            # 干跑
    python scripts/mine_claims_dialogue.py --apply    # 写 seed-stage10.yaml
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
CSV_OUT = ROOT / "knowledge/claim-candidates-dialogue.csv"
YAML_OUT = ROOT / "knowledge/seed-stage10.yaml"
APPLY = "--apply" in sys.argv
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

CLAIM_BASE = 6000

EVAL = ("觉得", "认为", "可惜", "遗憾", "厉害", "讨厌", "喜欢", "不错", "糟糕",
        "了不起", "可靠", "危险", "奇怪", "有趣", "无聊", "可怕", "温柔", "严格",
        "聪明", "愚蠢", "可笑", "荒唐", "值得", "佩服", "失望", "敬佩", "信任",
        "怀疑", "担心", "羡慕", "嫉妒", "尊敬", "迂腐", "无能", "伟大", "腐败",
        "落后", "优秀", "出色", "差劲", "窝囊", "天真", "狡猾", "阴险", "卑鄙",
        "高尚", "善良", "残忍", "冷酷", "傲慢", "谦虚", "勤奋", "懒惰", "古怪",
        "神秘", "过分", "离谱", "豪爽", "爽快", "大方", "小气", "吝啬")
ADV = ("果然", "确实", "实在", "真是", "真的", "很", "太", "挺", "最", "不",
       "有点", "有些", "非常", "特别", "相当", "十分", "一向", "向来", "总是",
       "从不", "太不", "不太")
RUMOR = ("据说", "传说", "有人说", "有人认为", "听闻", "传言", "据传", "据称",
         "号称", "被称为", "据我所知", "听说")
BAD_SPEAKER = {"？？？", "旅行者", "空", "荧", "派蒙", "主持人", ""}
SPLIT = re.compile(r"[。！？!?…；\n]")
TAIL_BAD = ("的", "上", "里", "中", "们", "内", "城", "港")


def clauses(body: str) -> list[str]:
    return [c.strip() for c in SPLIT.split(body) if c.strip()]


def main() -> int:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    ents = {r["canonical_name"]: r["entity_id"] for r in con.execute(
        "SELECT canonical_name, entity_id FROM entities")}
    pat = re.compile("|".join(sorted(map(re.escape, ents), key=len, reverse=True)))
    adv = "|".join(map(re.escape, sorted(ADV, key=len, reverse=True)))

    hits: list[dict] = []
    stats = Counter()

    # ---- 来源一：任务对话的评价 -----------------------------------------
    seen: set[tuple[str, str]] = set()
    rows = con.execute(
        """SELECT s.speaker, s.body, s.doc_id FROM sections s
           JOIN documents d ON d.doc_id = s.doc_id
           WHERE d.doc_type = 'quest'
             AND s.speaker IS NOT NULL AND s.speaker <> ''"""
    ).fetchall()
    for r in rows:
        stats["对话段"] += 1
        sp, body = r["speaker"], r["body"] or ""
        if sp in BAD_SPEAKER or not (12 <= len(body) <= 120):
            continue
        names = set(pat.findall(body))
        if len(names) != 1:
            continue
        name = names.pop()
        if name == sp or name in sp:
            continue
        found = None
        for cl in clauses(body):
            if not (6 <= len(cl) <= 34) or name not in cl:
                continue
            pos = cl.find(name)
            if cl[pos + len(name):pos + len(name) + 1] in TAIL_BAD:
                continue
            if "不觉得" in cl or re.search(r"觉得[^。]{0,24}[？?吗]", cl):
                continue
            # 「麻烦你」「麻烦您」是请求，不是评价
            if "麻烦" in cl and re.search(r"麻烦(你|您|大)", cl):
                continue
            for w in EVAL:
                if re.search(rf"{re.escape(name)}(?:[^\u4e00-\u9fff]{{0,2}}|{adv}){{0,2}}"
                             rf"{re.escape(w)}(?![的地])", cl):
                    found = (cl, w)
                    break
            if found:
                break
        if not found or (name, sp) in seen:
            continue
        seen.add((name, sp))
        hits.append({"entity": name, "speaker": sp, "statement": body.strip(),
                     "trigger": found[1], "doc": r["doc_id"],
                     "confidence": "likely", "source": "任务对话评价"})
    print(f"来源一（任务对话评价）：{len(hits)} 条")

    # ---- 来源二：传闻与争议 ---------------------------------------------
    rumor_rows = con.execute(
        """SELECT s.speaker, s.body, s.doc_id FROM sections s
           JOIN documents d ON d.doc_id = s.doc_id
           WHERE d.doc_type IN ('quest','book','character')
             AND (s.body LIKE '%据说%' OR s.body LIKE '%传说%'
                  OR s.body LIKE '%有人说%' OR s.body LIKE '%有人认为%'
                  OR s.body LIKE '%听闻%' OR s.body LIKE '%传言%'
                  OR s.body LIKE '%据传%' OR s.body LIKE '%据称%')"""
    ).fetchall()
    n1 = len(hits)
    covered = {h["entity"] for h in hits}
    for r in rumor_rows:
        body = r["body"] or ""
        if not (15 <= len(body) <= 150):
            continue
        names = set(pat.findall(body))
        if len(names) != 1:
            continue
        name = names.pop()
        if name in covered:            # 同一实体已有评价，不重复收传闻
            stats["传闻-该实体已有评价"] += 1
            continue
        found = None
        for cl in clauses(body):
            if name not in cl or not (8 <= len(cl) <= 60):
                continue
            pos = cl.find(name)
            for w in RUMOR:
                j = cl.find(w)
                if j < 0:
                    continue
                dist = (pos - j - len(w)) if pos > j else (j - pos - len(name))
                if dist <= 15:
                    found = (cl, w)
                    break
            if found:
                break
        if not found:
            continue
        covered.add(name)
        hits.append({"entity": name,
                     "speaker": r["speaker"] or "（旁白）",
                     "statement": body.strip(), "trigger": found[1],
                     "doc": r["doc_id"], "confidence": "speculative",
                     "source": "传闻/争议"})
    print(f"来源二（传闻/争议）：{len(hits) - n1} 条")

    hits.sort(key=lambda x: (x["source"], x["entity"]))
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    with CSV_OUT.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["entity", "speaker", "confidence", "source", "trigger",
                    "statement", "doc_id"])
        for h in hits:
            w.writerow([h["entity"], h["speaker"], h["confidence"], h["source"],
                        h["trigger"], h["statement"], h["doc"]])

    print(f"\n合计 {len(hits)} 条，涉及 {len({h['entity'] for h in hits})} 个实体")
    print("样例：")
    for h in hits[:16]:
        print(f"  [{h['confidence'][:4]}] {h['entity']:<8}←{h['speaker']:<8}"
              f"{h['statement'][:50]}")
    print(f"\n明细写入 {CSV_OUT.relative_to(ROOT)}")

    if not APPLY:
        print("（干跑，加 --apply 才写入种子）")
        return 0

    # 用 safe_dump 而不是手拼字符串：statement 里会出现 `*斜体*`、`:`、`#`
    # 这类字符，手拼会写出非法 YAML（踩过：`*与奇科娅一起…`）。
    payload = {
        "version": 1,
        "batch": "2026-11-11-stage10",
        "status": "draft",
        "claims": [
            {
                "id": CLAIM_BASE + i,
                "subject": ents[h["entity"]],
                "predicate": "评价",
                "object": "",
                "statement": h["statement"],
                "perspective": h["speaker"],
                "confidence": h["confidence"],
                "status": "open",
                "spoiler": 1,
                "doc": h["doc"],
                "quote": h["statement"],
                "notes": f"{h['source']}；触发词「{h['trigger']}」；未逐条核对",
            }
            for i, h in enumerate(hits, 1)
        ],
    }
    header = (
        "# 第十批知识层种子 · 对话与传闻里的说法（由 scripts/mine_claims_dialogue.py 生成）\n"
        "# 两个来源：任务对话里的评价（主谓紧邻，likely）、传闻句式（speculative）。\n"
        "# 都未逐条人工核对；页面按 confidence 区分「较可信 / 存疑」。\n"
    )
    YAML_OUT.write_text(
        header + yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=200),
        encoding="utf-8",
    )
    print(f"已写入 {YAML_OUT.relative_to(ROOT)}（{len(hits)} 条）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
