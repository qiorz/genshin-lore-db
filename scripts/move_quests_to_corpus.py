#!/usr/bin/env python3
"""Move quest drafts with dialogue into corpus/quests/, organized by subtype."""

from __future__ import annotations

import csv
import re
import shutil
import sqlite3
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "db" / "genshin_lore.sqlite3"
TARGET = ROOT / "corpus" / "quests"
BAD = re.compile(r'[<>:"/\\|?*]')


def safe_title(title: str) -> str:
    title = BAD.sub("-", title).strip().rstrip(".")
    title = re.sub(r"\s+", " ", title)
    return title[:90] or "untitled"


def main() -> int:
    TARGET.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT d.doc_id, d.normalized_path, d.title, d.subtype, d.region, d.version "
        "FROM documents d WHERE d.doc_type='quest' AND EXISTS("
        " SELECT 1 FROM sections s WHERE s.doc_id=d.doc_id AND s.section_type='dialogue'"
        ") ORDER BY d.doc_id"
    ).fetchall()
    moved = 0
    index_rows = []
    for row in rows:
        source = ROOT / row["normalized_path"]
        if not source.exists():
            print(f"missing source: {source}")
            continue
        text = source.read_text(encoding="utf-8")
        front = yaml.safe_load(text.split("---", 2)[1]) or {}
        subtype = (front.get("subtype") or "other").strip() or "other"
        target_dir = TARGET / subtype
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{safe_title(front.get('title') or row['title'])}.md"
        if target.exists():
            target = target_dir / f"{safe_title(front.get('title') or row['title'])}-{row['doc_id']}.md"
        shutil.move(str(source), str(target))
        index_rows.append(
            {
                "doc_id": row["doc_id"],
                "title": front.get("title") or row["title"],
                "subtype": subtype,
                "region": front.get("region") or "",
                "version": front.get("version") or "",
                "path": str(target.relative_to(ROOT)).replace("\\", "/"),
            }
        )
        moved += 1
    with (TARGET / "index.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(index_rows[0].keys()) if index_rows else ["doc_id"])
        writer.writeheader()
        writer.writerows(index_rows)
    print(f"moved {moved} quests to {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
