#!/usr/bin/env python3
"""Render all OBC scattered-text or quest entries listed in obc-index.csv.

This runs in-process for speed; it does not fetch. Run fetch_obc.py first.

Examples:
    python scripts/render_obc_batch.py --doc-type lore
    python scripts/render_obc_batch.py --doc-type quest
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_obc as ro

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "manifests" / "obc-index.csv"
ENTRIES = ROOT / "raw" / "official_site" / "obc" / "entries"
META = ROOT / "raw" / "official_site" / "obc" / "meta"
DEFAULT_OUT = ROOT / "exports" / "obc-batch"
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

QUEST_SUBTYPES = {
    "魔神任务": "archon",
    "传说任务": "story",
    "世界任务": "world",
    "限时任务": "event",
    "其他任务": "other",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doc-type", choices=["lore", "quest"], required=True)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--index", type=Path, default=INDEX)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--include-loaded", action="store_true")
    args = parser.parse_args()

    with args.index.open(encoding="utf-8-sig", newline="") as fh:
        rows = [
            row
            for row in csv.DictReader(fh)
            if row["doc_type"] == args.doc_type
            and (args.include_loaded or row["status"] != "loaded")
        ]
    if args.limit:
        rows = rows[: args.limit]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    written = skipped = missing = failed = 0

    for row in rows:
        entry_id = row["content_id"]
        entry_path = ENTRIES / f"{entry_id}.json"
        if not entry_path.exists():
            missing += 1
            print(f"missing raw: {entry_id}", file=sys.stderr)
            continue
        out_path = args.out_dir / f"{args.doc_type}-{entry_id}.md"
        if out_path.exists() and not args.force:
            skipped += 1
            continue

        payload = json.loads(entry_path.read_text(encoding="utf-8"))
        page = ((payload.get("data") or {}).get("page") or {})
        if not page:
            failed += 1
            print(f"empty page: {entry_id}", file=sys.stderr)
            continue
        meta_path = META / f"{entry_id}.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else None

        region = (row.get("region") or "").strip() or "未知"
        version = (row.get("version") or "").strip()
        version_source = (row.get("version_source") or "unknown").strip()
        version_confidence = (row.get("version_confidence") or "unknown").strip()

        if args.doc_type == "lore":
            render_args = SimpleNamespace(
                doc_id=f"lore.obc.{entry_id}",
                title=row.get("title") or page.get("name") or "",
                region=region,
                version=version,
                version_source=version_source,
                version_confidence=version_confidence,
                spoiler=1,
                scope=[f"region:{region}"],
            )
            front, body = ro.render_lore(page, meta, entry_path, render_args)
        else:
            subtype = QUEST_SUBTYPES.get(row.get("category") or "", "other")
            render_args = SimpleNamespace(
                doc_id=f"quest.obc.{entry_id}",
                title=row.get("title") or page.get("name") or "",
                subtype=subtype,
                region=region,
                version=version,
                version_source=version_source,
                version_confidence=version_confidence,
                spoiler=1,
                scope=[f"quest:{subtype}"],
            )
            front, body = ro.render_quest(page, meta, entry_path, render_args)

        front_yaml = yaml.safe_dump(front, allow_unicode=True, sort_keys=False, width=120)
        text = f"---\n{front_yaml}---\n\n" + "\n".join(body).rstrip() + "\n"
        out_path.write_text(text, encoding="utf-8", newline="\n")
        try:
            rel_path = str(out_path.resolve().relative_to(ROOT)).replace("\\", "/")
        except ValueError:
            rel_path = str(out_path).replace("\\", "/")
        manifest.append(
            {
                "doc_id": front["id"],
                "entry_page_id": entry_id,
                "type": args.doc_type,
                "title": front["title"],
                "region": front.get("region") or "",
                "version": front.get("version") or "",
                "version_source": front.get("version_source") or "",
                "version_confidence": front.get("version_confidence") or "",
                "path": rel_path,
            }
        )
        written += 1
        if written % 50 == 0:
            print(f"rendered {written}/{len(rows)} ...")

    manifest_path = args.out_dir / f"{args.doc_type}-manifest.csv"
    with manifest_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(manifest[0].keys()) if manifest else ["doc_id"])
        writer.writeheader()
        writer.writerows(manifest)

    print(
        f"done {args.doc_type}: written={written} skipped={skipped} "
        f"missing={missing} failed={failed} manifest={manifest_path}"
    )
    return 1 if failed or missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
