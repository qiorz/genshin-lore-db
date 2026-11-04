#!/usr/bin/env python3
"""Fill scattered-text versions from related achievements or activities.

Uses the OBC achievement/activity channel lists. Only fills rows that are still
missing a version; quest-derived versions are never overwritten.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "manifests" / "obc-index.csv"
ENTRIES = ROOT / "raw" / "official_site" / "obc" / "entries"
LISTS = ROOT / "raw" / "official_site" / "obc" / "channel_lists"
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


def norm(text: str) -> str:
    return re.sub(r"[\s：:，,。.、·•「」『』《》【】（）()\-—…]+", "", text or "")


def load_index(path: Path, version_key: str) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    channel = payload["data"]["list"][0]
    result = {}
    for entry in channel.get("list") or []:
        title = norm(entry.get("title") or "")
        if not title:
            continue
        ext = entry.get("ext") or "{}"
        try:
            data = json.loads(ext)
            text = list(data.values())[0].get("filter", {}).get("text", "[]")
            facets = json.loads(text) if isinstance(text, str) else text
        except Exception:
            continue
        for facet in facets:
            if facet.startswith(version_key + "/"):
                result[title] = facet.split("/", 1)[1]
                break
    return result


def related_text(payload: dict) -> str:
    page = ((payload.get("data") or {}).get("page") or {})
    for module in page.get("modules") or []:
        if (module.get("name") or "").strip() != "相关任务":
            continue
        for comp in module.get("components") or []:
            if comp.get("component_id") != "collapse_panel":
                continue
            data = comp.get("data")
            if isinstance(data, str):
                data = json.loads(data)
            return BeautifulSoup((data or {}).get("rich_text") or "", "html.parser").get_text(" ", strip=True)
    return ""


def main() -> int:
    achievements = load_index(LISTS / "252.json", "上线版本")
    activities = load_index(LISTS / "105.json", "版本")
    with INDEX.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    fieldnames = list(rows[0].keys())

    filled = 0
    for row in rows:
        if row["doc_type"] != "lore" or row.get("version"):
            continue
        path = ENTRIES / f"{row['content_id']}.json"
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        related = related_text(payload)
        if not related:
            continue
        related_norm = norm(related)
        candidates = []
        for title, version in achievements.items():
            if len(title) >= 3 and title in related_norm:
                candidates.append((len(title), version))
        for title, version in activities.items():
            if len(title) >= 3 and title in related_norm:
                candidates.append((len(title), version))
        if not candidates:
            continue
        version = max(candidates, key=lambda item: item[0])[1]
        row["version"] = version
        row["version_source"] = "derived-related-quest"
        row["version_confidence"] = "inferred"
        filled += 1

    with INDEX.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"filled from achievements/activities: {filled}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
