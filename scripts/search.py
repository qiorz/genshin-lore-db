#!/usr/bin/env python3
"""Search the local lore database.

Examples:
    python scripts/search.py 钟离
    python scripts/search.py 坎瑞亚 --type book --spoiler 1
    python scripts/search.py 葬火之战 --limit 5
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "db" / "genshin_lore.sqlite3"


_JIEBA = None


def _load_jieba():
    """按需加载 jieba 与自定义词典（只用得到两字查询时才付出这 1 秒）。"""
    global _JIEBA
    if _JIEBA is None:
        import jieba

        terms = ROOT / "manifests" / "terms.txt"
        if terms.exists():
            jieba.load_userdict(str(terms))
        _JIEBA = jieba
    return _JIEBA


def fts_candidates(text: str) -> list[tuple[str, str]]:
    """按优先级给出 (表名, MATCH 表达式) 候选。

    两字词先试整词匹配：词典内的词（钟离、璃月…）分词后就是一个 token，
    直接命中，省掉 jieba 启动的近 1 秒。整词没结果时再由调用方补一次
    分词匹配（见 segmented_match），最后才是 LIKE 兜底。
    """
    text = (text or "").strip()
    quoted = '"' + text.replace('"', '""') + '"'
    if len(text) >= 3:
        return [("sections_fts", quoted)]
    if len(text) == 2:
        return [("sections_fts_words", quoted)]
    return []


def segmented_match(text: str) -> str:
    """两字词整词没命中时，用 jieba 切成词再拼 phrase 试一次。"""
    jieba = _load_jieba()
    toks = [t for t in jieba.cut_for_search(text) if t.strip()]
    if len(toks) <= 1:
        return ""
    return '"' + " ".join(t.replace('"', '""') for t in toks) + '"'


def snippet(text: str, query: str, width: int = 120) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return ""
    pos = text.find(query)
    if pos == -1:
        return text[:width] + ("…" if len(text) > width else "")
    start = max(0, pos - width // 3)
    end = min(len(text), start + width)
    return ("…" if start else "") + text[start:end] + ("…" if end < len(text) else "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--type", dest="doc_type")
    parser.add_argument("--region")
    parser.add_argument("--spoiler", type=int, default=3)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.db.exists() is False:
        raise SystemExit(f"database not found: {args.db}")

    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row
    filters = ["d.spoiler_level <= ?"]
    params: list[object] = [args.spoiler]
    if args.doc_type:
        filters.append("d.doc_type = ?")
        params.append(args.doc_type)
    if args.region:
        filters.append("d.region = ?")
        params.append(args.region)
    where = " AND ".join(filters)

    rows: list[sqlite3.Row] = []

    def run_fts(table: str, match_expr: str) -> list[sqlite3.Row]:
        return con.execute(
            f"""
            SELECT d.doc_id, d.title, d.doc_type, d.region, d.version,
                   s.speaker, s.body, s.section_id,
                   COALESCE(ds.url, d.source_url) AS source_url
            FROM {table} f
            JOIN sections s ON s.section_id = f.rowid
            JOIN documents d ON d.doc_id = s.doc_id
            LEFT JOIN document_sources ds
                ON ds.doc_id = d.doc_id AND ds.is_primary = 1
            WHERE {table} MATCH ? AND {where}
            ORDER BY d.spoiler_level, bm25({table}), d.doc_id, s.ordinal
            LIMIT ?
            """,
            [match_expr, *params, args.limit],
        ).fetchall()

    for table, fts_match in fts_candidates(args.query):
        try:
            rows = run_fts(table, fts_match)
        except sqlite3.OperationalError as exc:
            print(f"FTS query failed, falling back to LIKE: {exc}", file=sys.stderr)
        if rows:
            break

    # 两字词整词没命中（不在词典里、被切成两个 token），再用 jieba 切一次查询词。
    if not rows and len(args.query.strip()) == 2:
        seg_expr = segmented_match(args.query.strip())
        if seg_expr:
            try:
                rows = run_fts("sections_fts_words", seg_expr)
            except sqlite3.OperationalError:
                pass

    if not rows:
        rows = con.execute(
            f"""
            SELECT d.doc_id, d.title, d.doc_type, d.region, d.version,
                   s.speaker, s.body, s.section_id,
                   COALESCE(ds.url, d.source_url) AS source_url
            FROM sections s
            JOIN documents d ON d.doc_id = s.doc_id
            LEFT JOIN document_sources ds
                ON ds.doc_id = d.doc_id AND ds.is_primary = 1
            WHERE (s.body LIKE ? OR s.body_segmented LIKE ?) AND {where}
            ORDER BY d.spoiler_level, d.doc_id, s.ordinal
            LIMIT ?
            """,
            [f"%{args.query}%", f"%{args.query}%", *params, args.limit],
        ).fetchall()

    # Titles are not in the section FTS index; add title matches explicitly.
    title_rows = con.execute(
        f"""
        SELECT d.doc_id, d.title, d.doc_type, d.region, d.version,
               NULL AS speaker, d.title AS body, NULL AS section_id,
               COALESCE(ds.url, d.source_url) AS source_url
        FROM documents d
        LEFT JOIN document_sources ds
            ON ds.doc_id = d.doc_id AND ds.is_primary = 1
        WHERE d.title LIKE ? AND {where}
        ORDER BY d.spoiler_level, d.doc_id
        LIMIT ?
        """,
        [f"%{args.query}%", *params, args.limit],
    ).fetchall()
    combined: list[sqlite3.Row] = []
    seen_keys: set[tuple[str, object]] = set()
    for row in list(title_rows) + list(rows):
        key = (row["doc_id"], row["section_id"])
        if key in seen_keys:
            continue
        seen_keys.add(key)
        combined.append(row)
    rows = combined[: args.limit]

    if args.json:
        print(
            json.dumps(
                [dict(row) for row in rows],
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if not rows:
        print(f"no matches for: {args.query}")
        return 0

    for row in rows:
        speaker = f"{row['speaker']}：" if row["speaker"] else ""
        print(f"[{row['doc_type']}] {row['title']}  ({row['doc_id']})")
        print(f"  {speaker}{snippet(row['body'], args.query)}")
        if row["source_url"]:
            print(f"  {row['source_url']}")
        print()
    print(f"{len(rows)} result(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
