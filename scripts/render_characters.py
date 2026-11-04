#!/usr/bin/env python3
"""Render all OBC character entries into corpus/characters/.

Only story/description/vision/voice/birthday narrative modules are kept; stats,
constellations, builds and guides are skipped by render_obc.render_character.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import render_obc as ro

INDEX = ROOT / "manifests" / "character-index.csv"
ENTRIES = ROOT / "raw" / "official_site" / "obc" / "entries"
META = ROOT / "raw" / "official_site" / "obc" / "meta"
TARGET = ROOT / "corpus" / "characters"
BAD = re.compile(r'[<>:"/\\|?*]')
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


def safe_title(title: str) -> str:
    title = BAD.sub("-", title).strip().rstrip(".")
    title = re.sub(r"\s+", " ", title)
    return title[:90] or "untitled"


def main() -> int:
    TARGET.mkdir(parents=True, exist_ok=True)
    with INDEX.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    written = skipped = missing = 0
    index_rows = []
    for row in rows:
        entry_id = row["content_id"]
        entry_path = ENTRIES / f"{entry_id}.json"
        if not entry_path.exists():
            missing += 1
            print(f"missing raw {entry_id} {row['title']}", file=sys.stderr)
            continue
        payload = json.loads(entry_path.read_text(encoding="utf-8"))
        page = ((payload.get("data") or {}).get("page") or {})
        if not page:
            missing += 1
            continue
        meta_path = META / f"{entry_id}.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else None
        region = (row.get("region") or "").strip() or "未知"
        args = SimpleNamespace(
            doc_id=f"char.obc.{entry_id}",
            title=row["title"].strip(),
            region=region,
            version=(row.get("version") or "").strip(),
            version_source=(row.get("version_source") or "unknown").strip(),
            version_confidence=(row.get("version_confidence") or "unknown").strip(),
            spoiler=1,
            scope=[f"character:{region}"],
        )
        front, body = ro.render_character(page, meta, entry_path, args)
        if not body:
            skipped += 1
            print(f"no narrative {entry_id} {row['title']}", file=sys.stderr)
            continue
        target_dir = TARGET / region
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{safe_title(row['title'])}.md"
        if target.exists():
            target = target_dir / f"{safe_title(row['title'])}-{entry_id}.md"
        front_yaml = yaml.safe_dump(front, allow_unicode=True, sort_keys=False, width=120)
        text = f"---\n{front_yaml}---\n\n" + "\n".join(body).rstrip() + "\n"
        target.write_text(text, encoding="utf-8", newline="\n")
        index_rows.append(
            {
                "doc_id": front["id"],
                "title": front["title"],
                "region": front.get("region") or "",
                "version": front.get("version") or "",
                "element": row.get("element") or "",
                "weapon": row.get("weapon") or "",
                "star": row.get("star") or "",
                "path": str(target.relative_to(ROOT)).replace("\\", "/"),
            }
        )
        written += 1
    with (TARGET / "index.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(index_rows[0].keys()) if index_rows else ["doc_id"])
        writer.writeheader()
        writer.writerows(index_rows)
    print(f"written={written} skipped={skipped} missing={missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
