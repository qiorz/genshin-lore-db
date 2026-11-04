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


def fts_query(text: str) -> str:
    text = (text or "").strip()
    if len(text) < 3:
        return ""
    escaped = text.replace('"', '""')
    return f'"{escaped}"'


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
    match = fts_query(args.query)
    if match:
        try:
            rows = con.execute(
                f"""
                SELECT d.doc_id, d.title, d.doc_type, d.region, d.version,
                       s.speaker, s.body, s.section_id,
                       COALESCE(ds.url, d.source_url) AS source_url
                FROM sections_fts f
                JOIN sections s ON s.section_id = f.rowid
                JOIN documents d ON d.doc_id = s.doc_id
                LEFT JOIN document_sources ds
                    ON ds.doc_id = d.doc_id AND ds.is_primary = 1
                WHERE sections_fts MATCH ? AND {where}
                ORDER BY d.spoiler_level, d.doc_id, s.ordinal
                LIMIT ?
                """,
                [match, *params, args.limit],
            ).fetchall()
        except sqlite3.OperationalError as exc:
            print(f"FTS query failed, falling back to LIKE: {exc}", file=sys.stderr)

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
