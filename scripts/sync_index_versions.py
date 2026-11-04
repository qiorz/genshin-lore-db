#!/usr/bin/env python3
"""Sync version provenance from manifests/obc-index.csv into front matter and DB.

This is useful after filling version labels or adding manual overrides, without
re-rendering whole documents.
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "manifests" / "obc-index.csv"
DB = ROOT / "db" / "genshin_lore.sqlite3"


def main() -> int:
    with INDEX.open(encoding="utf-8-sig", newline="") as fh:
        rows = {row["content_id"]: row for row in csv.DictReader(fh)}

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    docs = con.execute(
        "SELECT doc_id, doc_type, source_page_id, normalized_path, version, "
        "version_source, version_confidence FROM documents "
        "WHERE doc_type IN ('book','lore','quest') AND source_page_id IS NOT NULL"
    ).fetchall()

    db_updates = file_updates = 0
    for doc in docs:
        row = rows.get(str(doc["source_page_id"]))
        if not row:
            continue
        version = (row.get("version") or "").strip()
        if not version:
            continue
        source = (row.get("version_source") or "unknown").strip()
        confidence = (row.get("version_confidence") or "unknown").strip()
        if (
            doc["version"] != version
            or doc["version_source"] != source
            or doc["version_confidence"] != confidence
        ):
            con.execute(
                "UPDATE documents SET version=?, version_source=?, version_confidence=?, "
                "updated_at=datetime('now') WHERE doc_id=?",
                (version, source, confidence, doc["doc_id"]),
            )
            db_updates += 1

        if not doc["normalized_path"]:
            continue
        path = ROOT / doc["normalized_path"]
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            continue
        parts = text.split("---", 2)
        if len(parts) < 3:
            continue
        front = yaml.safe_load(parts[1]) or {}
        if (
            front.get("version") == version
            and front.get("version_source") == source
            and front.get("version_confidence") == confidence
        ):
            continue
        front["version"] = version
        front["version_source"] = source
        front["version_confidence"] = confidence
        yaml_text = yaml.safe_dump(front, allow_unicode=True, sort_keys=False, width=120)
        path.write_text(f"---\n{yaml_text}---{parts[2]}", encoding="utf-8", newline="\n")
        file_updates += 1

    con.commit()
    print(f"db_updates={db_updates} file_updates={file_updates}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
