#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""候选概念挖掘：找出「跨多种文本类型反复出现、但还没被实体化」的名词短语。

为什么按「跨文档类型数」排序：
  只出现在任务里的词多半是剧情细节；同时出现在书、武器、圣遗物、任务、角色故事里的，
  才是需要跨文档串联的世界观概念——正是推论层该收录的对象。

两道关键过滤（第一版没做，结果全是「不会」「还有」这类虚词）：

  1. 词性：只保留名词（jieba.posseg 的 n* 词性）。
  2. PMI：二字组合必须「一起出现的频率远高于各自独立出现的概率」。
     「三轮+明月」的 PMI 很高，而「的我」「一个」这类偶然相邻的 PMI 接近 0。

用法：
    python scripts/mine_concepts.py                     # 输出前 40
    python scripts/mine_concepts.py --top 80 --write    # 写 manifests/concept-candidates.csv
"""
from __future__ import annotations

import argparse
import csv
import math
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

import jieba
import jieba.posseg as pseg

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "db" / "genshin_lore.sqlite3"
TERMS = ROOT / "manifests" / "terms.txt"
OUT = ROOT / "manifests" / "concept-candidates.csv"
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

CJK = re.compile(r"^[\u4e00-\u9fff·]+$")
# 少数高频通用名词：词性是对的，但没有指代价值
GENERIC = frozenset("""
世界 朋友 事情 地方 东西 人们 孩子 时候 身体 眼睛 声音 力量 记忆 感觉 样子 方法
问题 结果 原因 故事 传说 时间 心情 表情 眼神 语气 身影 声音 气息 气味 味道 颜色
工作 生活 日常生活 能力 技术 知识 智慧 生命 灵魂 意识 内心 心中 心里 身边 周围
""".split())


def load_known(con: sqlite3.Connection) -> set[str]:
    known: set[str] = set()
    for (name,) in con.execute("SELECT canonical_name FROM entities"):
        if name:
            known.add(name.strip())
    for (name,) in con.execute("SELECT name FROM entity_names"):
        if name:
            known.add(name.strip())
    return known


def ok_token(w: str) -> bool:
    if not (2 <= len(w) <= 6):
        return False
    if not CJK.match(w):
        return False
    return w not in GENERIC


def tokens_of(body: str) -> list[tuple[str, str]]:
    return [(w.strip(), f) for w, f in pseg.cut(body) if w and w.strip()]


def is_noun(flag: str) -> bool:
    return flag.startswith("n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--min-len", type=int, default=10)
    ap.add_argument("--pmi", type=float, default=2.5, help="二字组合的 PMI 下限")
    ap.add_argument("--min-docs", type=int, default=5, help="至少出现在几篇文档")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--db", type=Path, default=DB)
    args = ap.parse_args()

    jieba.load_userdict(str(TERMS))
    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    known = load_known(con)
    print(f"已有实体名/别名 {len(known)} 个", flush=True)

    rows_iter = con.execute("SELECT section_id, doc_id, body FROM sections")
    c1: Counter = Counter()          # 名词
    c2: Counter = Counter()          # 相邻名词拼接
    parts: dict[str, tuple[str, str]] = {}
    total = 0
    for _sid, _did, body in rows_iter:
        if not body or len(body) < args.min_len:
            continue
        total += 1
        toks = tokens_of(body)
        for w, f in toks:
            if is_noun(f) and ok_token(w):
                c1[w] += 1
        for (a, fa), (b, fb) in zip(toks, toks[1:]):
            if is_noun(fa) and is_noun(fb) and ok_token(a) and ok_token(b) and len(a) + len(b) <= 6:
                c2[a + b] += 1
                parts.setdefault(a + b, (a, b))
    print(f"第一轮：{total} 段；名词 {len(c1)} 种，二字组合 {len(c2)} 种", flush=True)

    # PMI：二字组合是否真的成词
    def pmi_of(ab: str) -> float:
        ca, cb = parts.get(ab, (None, None))
        if not ca:
            return -99.0
        na, nb, nab = c1.get(ca, 0), c1.get(cb, 0), c2[ab]
        if na < 2 or nb < 2:
            return -99.0
        return math.log(nab * total / (na * nb))

    cands: dict[str, float] = {}
    for w, n in c1.items():
        if n >= 3 and w not in known:
            cands[w] = 0.0
    for ab, n in c2.items():
        if n >= 3 and ab not in known:
            p = pmi_of(ab)
            if p >= args.pmi:
                cands[ab] = p
    print(f"候选 {len(cands)} 个（PMI >= {args.pmi}）", flush=True)

    # 第二轮：文档数 / 类型数
    cand_set = set(cands)
    docs: dict[str, set] = defaultdict(set)
    for _sid, did, body in con.execute("SELECT section_id, doc_id, body FROM sections"):
        if not body or len(body) < args.min_len:
            continue
        toks = tokens_of(body)
        hit: set[str] = set()
        for w, f in toks:
            if is_noun(f) and w in cand_set:
                hit.add(w)
        for (a, fa), (b, fb) in zip(toks, toks[1:]):
            ab = a + b
            if ab in cand_set and is_noun(fa) and is_noun(fb):
                hit.add(ab)
        for w in hit:
            docs[w].add(did)

    dtype = {r[0]: (r[1] or "?") for r in con.execute("SELECT doc_id, doc_type FROM documents")}
    title = {r[0]: (r[1] or "") for r in con.execute("SELECT doc_id, title FROM documents")}

    rows = []
    for w, p in cands.items():
        dset = docs.get(w) or set()
        if len(dset) < args.min_docs:
            continue
        types = {dtype.get(d, "?") for d in dset}
        rows.append({
            "concept": w,
            "sections": c1.get(w) or c2.get(w) or 0,
            "docs": len(dset),
            "types": len(types),
            "pmi": round(p, 2),
            "type_list": "、".join(sorted(types)),
            "samples": " | ".join(title.get(d, d) for d in sorted(dset)[:3]),
        })
    rows.sort(key=lambda r: (-r["types"], -r["docs"], -r["sections"]))

    print(f"\n{'概念':<12}{'段落':>6}{'文档':>6}{'类型':>5}{'PMI':>7}  类型分布")
    print("-" * 95)
    for r in rows[: args.top]:
        print(f"{r['concept']:<12}{r['sections']:>6}{r['docs']:>6}{r['types']:>5}{r['pmi']:>7}  {r['type_list']}")
        print(f"{'':14}{r['samples'][:76]}")

    if args.write and rows:
        with OUT.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"\n已写 {OUT}（{len(rows)} 行）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
