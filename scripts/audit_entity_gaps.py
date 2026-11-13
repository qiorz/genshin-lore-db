#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""实体证据缺口：找出「正文里反复出现，但知识层只收了寥寥几条证据」的实体。

思路：400 个实体是「第五批扩量」批量生成的，很多卡片只有 3 条最直接的证据，
而正文里同一个概念可能散落在书、武器、圣遗物、任务各处。
「提及数 ÷ 已收证据数」越大，说明这张卡越像占位符、越值得做一次推论。

用法：
    python scripts/audit_entity_gaps.py --top 30
    python scripts/audit_entity_gaps.py --write      # 写 exports/review/entity-gaps.csv
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "db" / "genshin_lore.sqlite3"
OUT = ROOT / "exports" / "review" / "entity-gaps.csv"
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--min-mentions", type=int, default=20, help="正文提及段落数下限")
    ap.add_argument("--type", dest="types", default="",
                    help="只看这些实体类型（逗号分隔）：concept,organization,event,nation,deity...")
    ap.add_argument("--skip", default="旅行者,派蒙", help="跳过的实体名（逗号分隔）")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--db", type=Path, default=DB)
    args = ap.parse_args()

    want_types = {t.strip() for t in args.types.split(",") if t.strip()}
    skip_names = {n.strip() for n in args.skip.split(",") if n.strip()}

    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row

    ents = con.execute("SELECT entity_id, canonical_name, entity_type FROM entities").fetchall()
    names: dict[str, list[str]] = {}
    for row in con.execute("SELECT entity_id, name FROM entity_names"):
        names.setdefault(row["entity_id"], []).append(row["name"])
    for e in ents:
        ls = names.get(e["entity_id"], [])
        if e["canonical_name"] not in ls:
            ls.insert(0, e["canonical_name"])
        names[e["entity_id"]] = ls

    evidence = {r[0]: r[1] for r in con.execute(
        "SELECT entity_id, COUNT(*) FROM entity_evidence GROUP BY 1")}
    rels = {}
    for r in con.execute(
        """SELECT entity_id, COUNT(*) FROM (
               SELECT subject_id AS entity_id FROM entity_relations
               UNION ALL SELECT object_id FROM entity_relations WHERE object_id IS NOT NULL)
           GROUP BY 1"""):
        rels[r[0]] = r[1]
    claims = {r[0]: r[1] for r in con.execute(
        "SELECT subject_id, COUNT(*) FROM claims WHERE subject_id IS NOT NULL GROUP BY 1")}

    rows = []
    for e in ents:
        eid = e["entity_id"]
        if want_types and e["entity_type"] not in want_types:
            continue
        if e["canonical_name"] in skip_names:
            continue
        cand = [n for n in names.get(eid, []) if len(n) >= 2]
        # 用一个代表性的名字查提及（别名全并会让长名实体虚高，取最长的规范名）
        probe = e["canonical_name"] if len(e["canonical_name"]) >= 2 else (cand[0] if cand else "")
        if not probe:
            continue
        like = f"%{probe}%"
        seg = con.execute("SELECT COUNT(*) FROM sections WHERE body LIKE ?", (like,)).fetchone()[0]
        if seg < args.min_mentions:
            continue
        docs = con.execute(
            "SELECT COUNT(DISTINCT s.doc_id), COUNT(DISTINCT d.doc_type) "
            "FROM sections s JOIN documents d ON d.doc_id=s.doc_id WHERE s.body LIKE ?",
            (like,)).fetchone()
        ev = evidence.get(eid, 0)
        rows.append({
            "entity_id": eid,
            "name": e["canonical_name"],
            "entity_type": e["entity_type"],
            "mentions": seg,
            "mention_docs": docs[0],
            "mention_types": docs[1],
            "evidence": ev,
            "relations": rels.get(eid, 0),
            "claims": claims.get(eid, 0),
            "gap": round(seg / max(ev, 1), 1),
        })

    rows.sort(key=lambda r: (-r["gap"], -r["mentions"]))

    print(f"{'实体':<14}{'类型':<8}{'提及段':>7}{'文档':>6}{'类型数':>7}{'证据':>6}{'关系':>5}{'缺口比':>8}")
    print("-" * 78)
    for r in rows[: args.top]:
        print(f"{r['name']:<14}{r['entity_type']:<8}{r['mentions']:>7}{r['mention_docs']:>6}"
              f"{r['mention_types']:>7}{r['evidence']:>6}{r['relations']:>5}{r['gap']:>8}")
    print(f"\n共 {len(rows)} 个实体满足「提及 >= {args.min_mentions} 段」")

    if args.write and rows:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with OUT.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"已写 {OUT}（{len(rows)} 行）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
