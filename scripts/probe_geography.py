#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探测「地点/组织/事件 → 国家」的语料证据，供人工确认归属。

存在的意义：A1–A3 是「人工给结论、脚本找出处」，但人工记的地理未必对
（纳塔、挪德卡莱这些新地区尤其容易记混）。所以先让语料投票：

  - 某个地点在正文里和哪个国家同段出现最多
  - 有没有「X位于Y」「Y境内的X」这类硬句式

人看着这两列做决定，比凭记忆填表可靠。

用法：
    python scripts/probe_geography.py
"""
from __future__ import annotations

import csv
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "db/genshin_lore.sqlite3"
OUT = ROOT / "exports/review/geo-cooccurrence.csv"
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

# 段落按这些字符切句，用于挑一句像样的证据
SENT_SPLIT = re.compile(r"[。！？!?\n]")


def sentences(body: str) -> list[str]:
    return [s.strip() for s in SENT_SPLIT.split(body or "") if s and s.strip()]


def main() -> int:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    nations = [r["canonical_name"] for r in
               con.execute("SELECT canonical_name FROM entities WHERE entity_type='nation'")]
    targets = [dict(r) for r in con.execute(
        """SELECT entity_id, canonical_name, entity_type FROM entities
           WHERE entity_type IN ('location', 'organization', 'event')
           ORDER BY entity_type, canonical_name""")]

    nation_pat = re.compile("|".join(sorted(map(re.escape, nations), key=len, reverse=True)))
    name_pat = re.compile("|".join(sorted((re.escape(t["canonical_name"]) for t in targets),
                                         key=len, reverse=True)))
    by_name = {t["canonical_name"]: t for t in targets}

    # stat[(entity_name, nation)] = [段数, {doc_id: 最高分句子}]
    stat: dict[tuple[str, str], list] = {}
    total_docs: dict[str, set] = {t["canonical_name"]: set() for t in targets}

    rows = con.execute("SELECT doc_id, body FROM sections").fetchall()
    for row in rows:
        body = row["body"] or ""
        found_nat = set(nation_pat.findall(body))
        if not found_nat:
            continue
        found_ent = set(name_pat.findall(body))
        if not found_ent:
            continue
        for name in found_ent:
            total_docs[name].add(row["doc_id"])
            for nat in found_nat:
                key = (name, nat)
                slot = stat.setdefault(key, [0, None, 0.0])
                slot[0] += 1
                # 只在句子层面找证据，段落级太粗
                best = _best_sentence(body, name, nat)
                if best and best[0] > slot[2]:
                    slot[1] = (row["doc_id"], best[1])
                    slot[2] = best[0]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["entity", "type", "nation", "cooc_sections", "entity_sections",
                    "score", "doc_id", "quote"])
        out = []
        for (name, nat), (n, ev, score) in stat.items():
            out.append([name, by_name[name]["entity_type"], nat, n,
                        len(total_docs[name]), round(score, 1),
                        ev[0] if ev else "", ev[1] if ev else ""])
        out.sort(key=lambda r: (r[1], r[0], -r[3]))
        w.writerows(out)

    # 控制台：每个实体只显示最可能的那个国家
    print(f"{'实体':<12}{'类型':<13}{'最可能':<7}{'同段':>5}{'总篇':>5}{'分':>5}  证据")
    best_of: dict[str, list] = {}
    for r in out:
        cur = best_of.get(r[0])
        if cur is None or (r[5], r[3]) > (cur[5], cur[3]):
            best_of[r[0]] = r
    for name in sorted(best_of, key=lambda n: (best_of[n][1], n)):
        r = best_of[name]
        print(f"{r[0]:<12}{r[1]:<13}{r[2]:<7}{r[3]:>5}{r[4]:>5}{r[5]:>5}  {r[7][:44]}")
    print(f"\n明细写入 {OUT.relative_to(ROOT)}")
    return 0


def _best_sentence(body: str, name: str, nation: str) -> tuple[float, str] | None:
    """在段落里找一句同时含实体名与国家名的句子，按句式硬度打分。"""
    best = None
    for s in sentences(body):
        if name not in s or nation not in s:
            continue
        score = 1.0
        if re.search(rf"{re.escape(name)}(?:位于|地处|坐落在|坐落于|设在|总部位于|总部设在)", s):
            score = 4.0
        elif re.search(rf"{re.escape(nation)}(?:境内|内|的){re.escape(name)}", s):
            score = 3.5
        elif re.search(rf"{re.escape(nation)}的{re.escape(name)}", s):
            score = 3.0
        elif _near(s, name, nation, 6):
            score = 2.5
        elif _near(s, name, nation, 15):
            score = 1.8
        if best is None or score > best[0]:
            best = (score, s)
    return best


def _near(s: str, a: str, b: str, gap: int) -> bool:
    for m in re.finditer(re.escape(a), s):
        i = s.find(b, max(0, m.start() - gap), m.end() + gap)
        if i >= 0:
            return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
