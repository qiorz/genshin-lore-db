#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""主题线索探测：给定一个推论的「主题 + 别名/隐喻」，把全库相关段落按文档归组列出来。

为什么需要它：很多世界观线索不用术语写。例如「三月女神」在原文里叫「三轮明月」
「三姐妹」「月夜的君王」——按术语搜「三月」只会命中《空月之歌》的任务文本，
搜不到《竹林月夜》那本书。所以推论的第一步不是检索，是「先知道它可能叫什么」。

本脚本只做证据收集，不做任何推断；结论由人写在 knowledge/theories.yaml。

用法：
    python scripts/probe_topic.py --topic 三月女神 \
        --alias 三轮明月 --alias 三姐妹 --alias 月夜的君王

    python scripts/probe_topic.py --topic 三月女神 --alias-file manifests/topics/三月女神.txt
    python scripts/probe_topic.py --topic 三月女神 --alias 三轮明月 --json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "db" / "genshin_lore.sqlite3"
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


def load_aliases(args) -> list[str]:
    aliases = list(args.alias or [])
    if args.alias_file:
        for line in args.alias_file.read_text(encoding="utf-8").splitlines():
            w = line.strip()
            if w and not w.startswith("#"):
                aliases.append(w)
    seen: list[str] = []
    for a in aliases:
        if a and a not in seen:
            seen.append(a)
    return seen


def entity_aliases(con, entity_id: str) -> tuple[str, list[str]]:
    """从库里取实体的规范名与别名——省得为了扫一个概念去手抄词表。"""
    name_row = con.execute(
        "SELECT canonical_name FROM entities WHERE entity_id=?", (entity_id,)
    ).fetchone()
    if not name_row:
        raise SystemExit(f"实体不存在：{entity_id}")
    names = [r[0] for r in con.execute(
        "SELECT name FROM entity_names WHERE entity_id=? ORDER BY is_primary DESC, name",
        (entity_id,)).fetchall() if r[0]]
    canonical = name_row[0]
    if canonical not in names:
        names.insert(0, canonical)
    return canonical, names


def probe(con, aliases: list[str], limit_per_doc: int) -> list[dict]:
    where = " OR ".join("s.body LIKE ?" for _ in aliases)
    params = [f"%{a}%" for a in aliases]
    rows = con.execute(
        f"""
        SELECT s.section_id, s.doc_id, s.ordinal, s.body, s.speaker,
               d.title, d.doc_type, d.region
        FROM sections s
        JOIN documents d ON d.doc_id = s.doc_id
        WHERE {where}
        ORDER BY d.doc_type, d.title, s.ordinal
        """,
        params,
    ).fetchall()

    grouped: dict[str, list[dict]] = defaultdict(list)
    doc_meta: dict[str, dict] = {}
    for row in rows:
        body = row["body"] or ""
        hits = [a for a in aliases if a in body]
        if not hits:
            continue
        doc_meta[row["doc_id"]] = {
            "title": row["title"],
            "doc_type": row["doc_type"],
            "region": row["region"],
        }
        grouped[row["doc_id"]].append({
            "section_id": row["section_id"],
            "ordinal": row["ordinal"],
            "body": body,
            "speaker": row["speaker"],
            "hits": hits,
        })

    out = []
    for doc_id, items in grouped.items():
        meta = doc_meta[doc_id]
        out.append({
            "doc_id": doc_id,
            "title": meta["title"],
            "doc_type": meta["doc_type"],
            "region": meta["region"],
            "items": items[:limit_per_doc],
            "total": len(items),
        })
    out.sort(key=lambda d: (-len(d["items"]), d["doc_type"], d["title"]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--topic", help="推论主题，如「三月女神」")
    ap.add_argument("--entity", help="实体 ID（如 entity.vision）：自动读取规范名+别名当扫描词")
    ap.add_argument("--alias", action="append", default=[], help="别名/隐喻，可重复")
    ap.add_argument("--alias-file", type=Path, help="每行一个别名")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--limit", type=int, default=6, help="每篇文档最多列几段")
    ap.add_argument("--min-quote", type=int, default=12, help="段落最短字符数")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row

    aliases = load_aliases(args)
    topic = args.topic or ""
    if args.entity:
        canonical, ent_aliases = entity_aliases(con, args.entity)
        topic = topic or canonical
        for a in ent_aliases:
            if a not in aliases:
                aliases.append(a)
    if not aliases:
        raise SystemExit("至少给一个 --alias / --alias-file / --entity")
    docs = probe(con, aliases, args.limit)

    if args.json:
        print(json.dumps({"topic": args.topic, "aliases": aliases, "documents": docs},
                         ensure_ascii=False, indent=2))
        return 0

    total_seg = sum(d["total"] for d in docs)
    types = sorted({d["doc_type"] for d in docs})
    print(f"主题：{topic}")
    print(f"别名：{'、'.join(aliases)}")
    print(f"命中：{total_seg} 段 / {len(docs)} 篇文档 / {len(types)} 种类型（{'、'.join(types)}）\n")

    for doc in docs:
        print(f"[{doc['doc_type']}] {doc['title']}  ({doc['doc_id']})  命中 {doc['total']} 段")
        for item in doc["items"]:
            body = " ".join((item["body"] or "").split())
            if len(body) < args.min_quote:
                continue
            speaker = f"{item['speaker']}：" if item["speaker"] else ""
            mark = "◆" if len(item["hits"]) > 1 else "·"
            print(f"  {mark} #{item['ordinal']:<4} {speaker}{body[:150]}")
            print(f"            （命中：{'、'.join(item['hits'])}）")
        if doc["total"] > len(doc["items"]):
            print(f"  … 另有 {doc['total'] - len(doc['items'])} 段未列出（--limit 调整）")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
