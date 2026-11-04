#!/usr/bin/env python3
"""Derive scattered-text versions from their "相关任务" field.

Run after fetching lore entries and before rendering them. Updates
manifests/obc-index.csv in place for doc_type=lore rows.
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
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


def norm(text: str) -> str:
    text = text or ""
    text = re.sub(r"[\s：:，,。.、·•「」『』《》【】（）()\-—…]+", "", text)
    return text


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
            rich = (data or {}).get("rich_text") or ""
            return BeautifulSoup(rich, "html.parser").get_text(" ", strip=True)
    return ""


def quest_keys(title: str) -> set[str]:
    keys = {norm(title)}
    for match in re.findall(r"「([^」]+)」", title):
        value = norm(match)
        if value:
            keys.add(value)
    return {key for key in keys if len(key) >= 2}


def candidates(text: str) -> set[str]:
    values = {norm(text)}
    for part in re.split(r"[：:\n；;]", text):
        part = re.sub(r"^(世界任务|魔神任务|传说任务|版本活动任务|活动任务|活动|每日委托|成就)", "", part.strip())
        value = norm(part)
        if len(value) >= 2:
            values.add(value)
    return {value for value in values if len(value) >= 2}


def main() -> int:
    with INDEX.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    fieldnames = list(rows[0].keys())
    quests = []
    for row in rows:
        if row["doc_type"] != "quest" or not row["version"]:
            continue
        keys = quest_keys(row["title"])
        if keys:
            quests.append((keys, row["version"]))

    matched = 0
    missing = 0
    for row in rows:
        if row["doc_type"] != "lore":
            continue
        path = ENTRIES / f"{row['content_id']}.json"
        if not path.exists():
            missing += 1
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            missing += 1
            continue
        related = related_text(payload)
        if not related:
            continue
        values = candidates(related)
        hits = []
        for keys, version in quests:
            for key in keys:
                if any(key in value or value in key for value in values):
                    hits.append((len(key), version))
                    break
        if not hits:
            continue
        version = max(hits, key=lambda item: item[0])[1]
        row["version"] = version
        row["version_source"] = "derived-related-quest"
        row["version_confidence"] = "inferred"
        matched += 1

    with INDEX.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"scattered versions matched: {matched}; missing raw: {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
