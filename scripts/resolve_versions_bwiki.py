#!/usr/bin/env python3
"""Resolve game versions from BWiki's Semantic MediaWiki API and merge them
into manifests/obc-index.csv.

Example:
    python scripts/resolve_versions_bwiki.py --category 书籍 --property 书籍名
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDEX = ROOT / "manifests" / "obc-index.csv"
RAW = ROOT / "raw" / "bwiki" / "smw"
TZ = timezone(timedelta(hours=8))
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

COUNTRY_MAP = {
    "0": "提瓦特",
    "1": "蒙德",
    "2": "璃月",
    "3": "稻妻",
    "4": "须弥",
    "5": "枫丹",
    "6": "纳塔",
    "7": "挪德卡莱",
    "8": "至冬",
}


def norm(text: str) -> str:
    text = text or ""
    text = text.replace("《", "").replace("》", "")
    text = text.replace("「", "").replace("」", "")
    text = text.replace("『", "").replace("』", "")
    text = re.sub(r"\s+", "", text)
    return text.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--category", default="书籍")
    parser.add_argument("--property", dest="prop", default="书籍名")
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--doc-type", default="book")
    args = parser.parse_args()

    session = requests.Session()
    session.trust_env = False
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
            "Referer": "https://wiki.biligame.com/ys/",
        }
    )
    query = f"[[分类:{args.category}]]|?{args.prop}|?实装版本|?国家|limit=1000"
    url = "https://wiki.biligame.com/ys/api.php"
    params = {"action": "ask", "query": query, "format": "json"}
    resp = session.get(url, params=params, timeout=120)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("error"):
        raise SystemExit(payload["error"])

    results = (payload.get("query") or {}).get("results") or {}
    versions: dict[str, str] = {}
    countries: dict[str, str] = {}
    for page_title, item in results.items():
        printouts = item.get("printouts") or {}
        title_values = printouts.get(args.prop) or [page_title]
        title = str(title_values[0]) if title_values else page_title
        raw_value = printouts.get("实装版本") or []
        if isinstance(raw_value, list) and raw_value:
            versions[norm(title)] = str(raw_value[0]).strip()
        else:
            versions[norm(title)] = ""
        country_values = printouts.get("国家") or []
        if isinstance(country_values, list) and country_values:
            countries[norm(title)] = COUNTRY_MAP.get(str(country_values[0]).strip(), "")

    RAW.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(TZ).strftime("%Y%m%d-%H%M%S")
    raw_path = RAW / f"{args.category}-{stamp}.json"
    raw_path.write_bytes(resp.content)
    (RAW / f"{args.category}-{stamp}.meta.json").write_text(
        json.dumps(
            {
                "source_id": "bwiki",
                "url": url,
                "api_params": params,
                "retrieved_at": datetime.now(TZ).isoformat(timespec="seconds"),
                "sha256": hashlib.sha256(resp.content).hexdigest(),
                "count": len(results),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    with args.index.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    fieldnames = list(rows[0].keys())

    matched = 0
    unmatched = []
    for row in rows:
        if row.get("doc_type") != args.doc_type:
            continue
        key = norm(row.get("title", ""))
        base = re.split(r"[·•【]", key, maxsplit=1)[0].strip()
        version = versions.get(key) or (versions.get(base) if base and base != key else None)
        country = countries.get(key) or (countries.get(base) if base and base != key else None)
        if country and not row.get("region"):
            row["region"] = country
        if version:
            row["version"] = version
            row["version_source"] = "bwiki"
            row["version_confidence"] = "confirmed"
            matched += 1
        else:
            unmatched.append((row.get("content_id"), row.get("title")))

    with args.index.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"BWiki {args.category}: {len(results)} entries, matched {matched}, unmatched {len(unmatched)}")
    for item in unmatched[:15]:
        print("  unmatched:", item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
