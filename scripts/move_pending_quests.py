#!/usr/bin/env python3
"""Move any remaining dialogue-bearing quest drafts from exports to corpus."""

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
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT d.doc_id, d.normalized_path, d.title, d.subtype FROM documents d "
        "WHERE d.doc_type='quest' AND d.normalized_path LIKE 'exports/obc-batch/%' "
        "AND EXISTS(SELECT 1 FROM sections s WHERE s.doc_id=d.doc_id AND s.section_type='dialogue')"
    ).fetchall()
    moved_paths = []
    for row in rows:
        source = ROOT / row["normalized_path"]
        if not source.exists():
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
        moved_paths.append(str(target.resolve()))
    out = ROOT / "exports" / "obc-evaluation" / "moved-pending-paths.txt"
    out.write_text("\n".join(moved_paths), encoding="utf-8")
    print(f"moved {len(moved_paths)} pending quests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
