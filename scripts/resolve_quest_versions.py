#!/usr/bin/env python3
"""Resolve missing quest versions from BWiki search + page fields."""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "manifests" / "obc-index.csv"
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


def norm(text: str) -> str:
    return re.sub(r"[\s：:，,。.、·•「」『』《》【】（）()\-—…]+", "", text or "")


def page_version(text: str) -> str:
    for key in ("所属版本", "实装版本", "版本"):
        match = re.search(r"\|" + key + r"=([^\n|}]*)", text)
        if match:
            value = match.group(1).strip()
            if value:
                return value
    return ""


def main() -> int:
    session = requests.Session()
    session.trust_env = False
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
            "Referer": "https://wiki.biligame.com/ys/",
        }
    )
    with INDEX.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    fieldnames = list(rows[0].keys())

    resolved = 0
    unresolved = []
    for row in rows:
        if row["doc_type"] != "quest" or row.get("version"):
            continue
        title = row["title"]
        search = session.get(
            "https://wiki.biligame.com/ys/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": title,
                "srlimit": 5,
                "format": "json",
            },
            timeout=30,
        ).json()
        results = (search.get("query") or {}).get("search") or []
        chosen = None
        wanted = norm(title)
        for result in results:
            candidate = result["title"]
            normalized = norm(candidate)
            if normalized == wanted or wanted in normalized or normalized in wanted:
                chosen = candidate
                break
        if not chosen and results:
            chosen = results[0]["title"]
        if not chosen:
            unresolved.append((row["content_id"], title, "no search result"))
            continue
        parse = session.get(
            "https://wiki.biligame.com/ys/api.php",
            params={
                "action": "parse",
                "page": chosen,
                "prop": "wikitext",
                "format": "json",
                "formatversion": 2,
            },
            timeout=30,
        ).json()
        text = ((parse.get("parse") or {}).get("wikitext") or "")
        version = page_version(text)
        if version:
            row["version"] = version
            row["version_source"] = "bwiki"
            row["version_confidence"] = "confirmed"
            resolved += 1
        else:
            unresolved.append((row["content_id"], title, f"page={chosen}, no version field"))

    with INDEX.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"resolved={resolved} unresolved={len(unresolved)}")
    for item in unresolved:
        print("  ", item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
