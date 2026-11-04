#!/usr/bin/env python3
"""Mark quest entries that have no dialogue sections as incomplete series pages."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "db" / "genshin_lore.sqlite3"
NOTE = "OBC 无剧情对话，疑似系列/总览页；待 BWiki 或子任务页补全。"


def main() -> int:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT d.doc_id, d.normalized_path, d.notes FROM documents d "
        "WHERE d.doc_type='quest' AND NOT EXISTS ("
        "  SELECT 1 FROM sections s WHERE s.doc_id=d.doc_id AND s.section_type='dialogue'"
        ")"
    ).fetchall()
    updated = 0
    for row in rows:
        notes = row["notes"] or ""
        if NOTE not in notes:
            con.execute(
                "UPDATE documents SET notes=?, updated_at=datetime('now') WHERE doc_id=?",
                (notes + (" " if notes else "") + NOTE, row["doc_id"]),
            )
        path = ROOT / row["normalized_path"] if row["normalized_path"] else None
        if path and path.exists():
            text = path.read_text(encoding="utf-8")
            if text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    front = yaml.safe_load(parts[1]) or {}
                    current = front.get("notes") or ""
                    if NOTE not in current:
                        front["notes"] = current + (" " if current else "") + NOTE
                        yaml_text = yaml.safe_dump(front, allow_unicode=True, sort_keys=False, width=120)
                        path.write_text(f"---\n{yaml_text}---{parts[2]}", encoding="utf-8", newline="\n")
        updated += 1
    con.commit()
    print(f"marked {updated} quest documents without dialogue")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
