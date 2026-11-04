#!/usr/bin/env python3
"""Remove the 'OBC 无剧情对话' warning from quests that now have dialogue."""

from __future__ import annotations

import re
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
        "WHERE d.doc_type='quest' AND EXISTS("
        " SELECT 1 FROM sections s WHERE s.doc_id=d.doc_id AND s.section_type='dialogue'"
        ")"
    ).fetchall()
    cleaned = 0
    for row in rows:
        notes = (row["notes"] or "")
        notes = notes.replace(NOTE, "")
        notes = re.sub(r"共 0 个剧情模块、0 个对话节点、0 个选项。", "", notes)
        notes = re.sub(r"\s+", " ", notes).strip()
        con.execute(
            "UPDATE documents SET notes=?, updated_at=datetime('now') WHERE doc_id=?",
            (notes, row["doc_id"]),
        )
        path = ROOT / row["normalized_path"] if row["normalized_path"] else None
        if path and path.exists():
            text = path.read_text(encoding="utf-8")
            if text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    front = yaml.safe_load(parts[1]) or {}
                    current = front.get("notes") or ""
                    current = current.replace(NOTE, "")
                    current = re.sub(r"共 0 个剧情模块、0 个对话节点、0 个选项。", "", current)
                    front["notes"] = re.sub(r"\s+", " ", current).strip()
                    yaml_text = yaml.safe_dump(front, allow_unicode=True, sort_keys=False, width=120)
                    path.write_text(f"---\n{yaml_text}---{parts[2]}", encoding="utf-8", newline="\n")
        cleaned += 1
    con.commit()
    print(f"cleaned {cleaned} filled quest notes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
