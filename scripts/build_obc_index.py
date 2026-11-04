#!/usr/bin/env python3
"""Build a prioritized index of OBC books, scattered text, and quests.

Reads raw channel lists and writes manifests/obc-index.csv. Game version for
quests comes from the channel's "版本号" filter; unresolved labels stay empty.
Existing non-empty versions are preserved, so a rebuild does not wipe versions
added by resolve_versions_bwiki.py or manual fixes.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw" / "official_site" / "obc" / "channel_lists"
OUT = ROOT / "manifests" / "obc-index.csv"
VERSION_LABELS = ROOT / "manifests" / "version-labels.csv"

CHANNELS = {
    68: "book",
    251: "lore",
    43: "quest",
}


def load_labels() -> dict[str, str]:
    labels: dict[str, str] = {}
    if VERSION_LABELS.exists():
        with VERSION_LABELS.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                labels[row["label"].strip()] = row["numeric_version"].strip()
    return labels


def facets(ext: str | None) -> dict[str, str]:
    if not ext:
        return {}
    try:
        parsed = json.loads(ext)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    first = next(iter(parsed.values()), {})
    text = (first.get("filter") or {}).get("text")
    if isinstance(text, str):
        try:
            items = json.loads(text)
        except json.JSONDecodeError:
            items = []
    elif isinstance(text, list):
        items = text
    else:
        items = []
    result = {}
    for item in items:
        if isinstance(item, str) and "/" in item:
            key, value = item.split("/", 1)
            result[key] = value
    return result


def main() -> int:
    labels = load_labels()
    rows = []
    for channel_id, doc_type in CHANNELS.items():
        path = RAW / f"{channel_id}.json"
        if not path.exists():
            print(f"missing {path}")
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        channel = ((payload.get("data") or {}).get("list") or [{}])[0] or {}
        for item in channel.get("list") or []:
            content_id = item.get("content_id")
            if not content_id:
                continue
            f = facets(item.get("ext"))
            version_label = f.get("版本号", "")
            if re.fullmatch(r"\d+\.\d+", version_label):
                version = version_label
                confidence = "confirmed"
                source = "obc-filter"
            elif version_label in labels:
                version = labels[version_label]
                confidence = "inferred"
                source = "obc-filter"
            else:
                version = ""
                confidence = "unknown"
                source = "unknown"
            region = f.get("任务区域") or f.get("地区") or ""
            category = f.get("任务类型") or f.get("书籍类型") or f.get("分类") or ""
            rows.append(
                {
                    "channel_id": channel_id,
                    "content_id": content_id,
                    "entry_page_id": content_id,
                    "doc_type": doc_type,
                    "title": item.get("title") or "",
                    "region": region,
                    "category": category,
                    "version_label": version_label,
                    "version": version,
                    "version_source": source,
                    "version_confidence": confidence,
                    "activity_limited": f.get("活动限定", ""),
                    "url": f"https://baike.mihoyo.com/ys/obc/content/{content_id}/detail",
                    "status": "planned",
                }
            )

    order = {"book": 0, "lore": 1, "quest": 2}
    rows.sort(key=lambda r: (order.get(r["doc_type"], 9), r["region"], r["title"]))

    # Preserve versions added by resolve_versions_bwiki.py or manual fixes.
    existing: dict[str, dict] = {}
    if OUT.exists():
        with OUT.open(encoding="utf-8-sig", newline="") as fh:
            for old in csv.DictReader(fh):
                existing[str(old.get("entry_page_id", ""))] = old
    for row in rows:
        old = existing.get(str(row.get("entry_page_id", "")))
        if not old:
            continue
        if not row["version"] and old.get("version"):
            row["version"] = old["version"]
            row["version_source"] = old.get("version_source") or "unknown"
            row["version_confidence"] = old.get("version_confidence") or "unknown"
        if old.get("status") in ("loaded", "skipped-duplicate"):
            row["status"] = old["status"]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    counts = Counter(row["doc_type"] for row in rows)
    versions = Counter(row["version"] for row in rows if row["version"])
    print(f"wrote {OUT} ({len(rows)} rows)")
    print("types:", dict(counts))
    print("top versions:", versions.most_common(8))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
