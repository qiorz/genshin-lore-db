#!/usr/bin/env python3
"""Update obc-index.csv status for a document type from the database.

Rows whose doc_id exists are marked loaded; others are marked
skipped-duplicate (use --missing-status to change this).
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "manifests" / "obc-index.csv"
DB = ROOT / "db" / "genshin_lore.sqlite3"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doc-type", required=True, choices=["book", "lore", "quest", "character"])
    parser.add_argument("--index", type=Path, default=INDEX)
    parser.add_argument("--missing-status", default="skipped-duplicate")
    args = parser.parse_args()

    con = sqlite3.connect(DB)
    ids = {
        row[0]
        for row in con.execute(
            "SELECT doc_id FROM documents WHERE doc_type = ?", (args.doc_type,)
        )
    }
    with args.index.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    fieldnames = list(rows[0].keys())
    loaded = missing = 0
    for row in rows:
        if row["doc_type"] != args.doc_type:
            continue
        prefix = "char" if args.doc_type == "character" else args.doc_type
        doc_id = f"{prefix}.obc.{row['content_id']}"
        if doc_id in ids:
            row["status"] = "loaded"
            loaded += 1
        else:
            row["status"] = args.missing_status
            missing += 1
    with args.index.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{args.doc_type}: loaded={loaded} missing={missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
