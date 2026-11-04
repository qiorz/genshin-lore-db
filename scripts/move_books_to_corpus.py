#!/usr/bin/env python3
"""Move reviewed book drafts from exports/ to corpus/books/, organized by region.

The front matter is not changed. A corpus/books/index.csv is written for
navigation and later checks.
"""

from __future__ import annotations

import csv
import re
import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "exports" / "obc-evaluation"
TARGET = ROOT / "corpus" / "books"
BAD = re.compile(r'[<>:"/\\|?*]')


def safe_title(title: str) -> str:
    title = BAD.sub("-", title).strip().rstrip(".")
    title = re.sub(r"\s+", " ", title)
    return title[:90] or "untitled"


def main() -> int:
    TARGET.mkdir(parents=True, exist_ok=True)
    rows = []
    moved = 0
    for path in sorted(SOURCE.glob("book-*.md")):
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            print(f"skip (no front matter): {path}")
            continue
        front = yaml.safe_load(text.split("---", 2)[1]) or {}
        region = (front.get("region") or "未知").strip() or "未知"
        title = safe_title(front.get("title") or path.stem)
        target_dir = TARGET / region
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{title}.md"
        if target.exists():
            target = target_dir / f"{title}-{front.get('id', path.stem)}.md"
        shutil.move(str(path), str(target))
        rows.append(
            {
                "doc_id": front.get("id", ""),
                "title": front.get("title", ""),
                "region": region,
                "version": front.get("version", ""),
                "version_source": front.get("version_source", ""),
                "version_confidence": front.get("version_confidence", ""),
                "path": str(target.relative_to(ROOT)).replace("\\", "/"),
            }
        )
        moved += 1

    index = TARGET / "index.csv"
    with index.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["doc_id"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"moved {moved} books to {TARGET}")
    print(f"wrote {index}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
