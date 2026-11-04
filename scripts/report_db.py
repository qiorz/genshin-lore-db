#!/usr/bin/env python3
"""Write concise database reports to exports/obc-evaluation/."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "db" / "genshin_lore.sqlite3"
OUT = ROOT / "exports" / "obc-evaluation"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> int:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    counts = {
        table: con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("sources", "documents", "sections", "document_revisions", "ingest_runs")
    }
    by_type = {
        row["doc_type"]: row["n"]
        for row in con.execute(
            "SELECT doc_type, COUNT(*) AS n FROM documents GROUP BY doc_type ORDER BY n DESC"
        )
    }
    version = {}
    for doc_type in by_type:
        row = con.execute(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN version IS NOT NULL AND version <> '' THEN 1 ELSE 0 END) AS versioned "
            "FROM documents WHERE doc_type = ?",
            (doc_type,),
        ).fetchone()
        version[doc_type] = {
            "total": row["total"],
            "versioned": row["versioned"],
            "unknown": row["total"] - row["versioned"],
        }
    regions = [
        {"region": row["region"] or "未知", "n": row["n"]}
        for row in con.execute(
            "SELECT region, COUNT(*) AS n FROM documents GROUP BY region ORDER BY n DESC"
        )
    ]
    runs = [
        dict(row)
        for row in con.execute(
            "SELECT run_id, started_at, finished_at, status, documents_seen, "
            "documents_written, errors, notes FROM ingest_runs ORDER BY run_id DESC LIMIT 5"
        )
    ]
    quest_dialogue = con.execute(
        "SELECT "
        "SUM(CASE WHEN EXISTS(SELECT 1 FROM sections s WHERE s.doc_id=d.doc_id AND s.section_type='dialogue') THEN 1 ELSE 0 END) AS with_dialogue, "
        "SUM(CASE WHEN NOT EXISTS(SELECT 1 FROM sections s WHERE s.doc_id=d.doc_id AND s.section_type='dialogue') THEN 1 ELSE 0 END) AS without_dialogue "
        "FROM documents d WHERE d.doc_type='quest'"
    ).fetchone()
    payload = {
        "counts": counts,
        "by_type": by_type,
        "version_coverage": version,
        "quest_dialogue": dict(quest_dialogue) if quest_dialogue else {},
        "regions": regions,
        "recent_ingest_runs": runs,
    }
    (OUT / "summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = ["DB summary", "=========="]
    for key, value in counts.items():
        lines.append(f"{key}: {value}")
    lines.append("\nby type")
    lines.extend(f"  {key}: {value}" for key, value in by_type.items())
    lines.append("\nversion coverage")
    for key, value in version.items():
        lines.append(
            f"  {key}: {value['versioned']}/{value['total']} versioned, "
            f"{value['unknown']} unknown"
        )
    lines.append("\ntop regions")
    lines.extend(f"  {item['region']}: {item['n']}" for item in regions[:15])
    if quest_dialogue:
        lines.append("\nquest dialogue")
        lines.append(f"  with_dialogue: {quest_dialogue['with_dialogue']}")
        lines.append(f"  without_dialogue: {quest_dialogue['without_dialogue']}")
    lines.append("\nrecent ingest runs")
    for run in runs:
        lines.append(
            f"  #{run['run_id']} {run['status']} seen={run['documents_seen']} "
            f"written={run['documents_written']} errors={run['errors']}"
        )
    text = "\n".join(lines) + "\n"
    (OUT / "summary.txt").write_text(text, encoding="utf-8")
    (OUT / "db-summary.txt").write_text(text, encoding="utf-8")
    print(f"wrote {OUT / 'summary.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
