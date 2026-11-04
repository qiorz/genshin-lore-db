#!/usr/bin/env python3
"""Try to resolve the remaining related-task versions via BWiki search."""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "manifests" / "obc-index.csv"
ENTRIES = ROOT / "raw" / "official_site" / "obc" / "entries"
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


def norm(text: str) -> str:
    return re.sub(r"[\s：:，,。.、·•「」『』《》【】（）()\-—…]+", "", text or "")


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


def task_title(related: str) -> str:
    match = re.search(r"(?:世界任务|魔神任务|传说任务|版本活动任务|活动任务|活动|每日委托)[：:]\s*([^：:\n；;]+)", related)
    if not match:
        return ""
    return match.group(1).strip()


def page_version(text: str) -> str:
    for key in ("所属版本", "实装版本", "版本"):
        m = re.search(r"\|" + key + r"=([^\n|}]*)", text)
        if m and m.group(1).strip():
            return m.group(1).strip()
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
    fields = list(rows[0].keys())
    filled = 0
    unresolved = []
    for row in rows:
        if row["doc_type"] != "lore" or row.get("version"):
            continue
        path = ENTRIES / f"{row['content_id']}.json"
        if not path.exists():
            continue
        related = related_text(json.loads(path.read_text(encoding="utf-8")))
        title = task_title(related)
        if not title:
            continue
        search = session.get(
            "https://wiki.biligame.com/ys/api.php",
            params={"action": "query", "list": "search", "srsearch": title, "srlimit": 3, "format": "json"},
            timeout=30,
        ).json()
        results = (search.get("query") or {}).get("search") or []
        chosen = None
        wanted = norm(title)
        for result in results:
            candidate = result["title"]
            if wanted and (wanted in norm(candidate) or norm(candidate) in wanted):
                chosen = candidate
                break
        if not chosen and results:
            chosen = results[0]["title"]
        if not chosen:
            unresolved.append((row["content_id"], title, "no page"))
            continue
        parse = session.get(
            "https://wiki.biligame.com/ys/api.php",
            params={"action": "parse", "page": chosen, "prop": "wikitext", "format": "json", "formatversion": 2},
            timeout=30,
        ).json()
        version = page_version(((parse.get("parse") or {}).get("wikitext") or ""))
        if not version:
            unresolved.append((row["content_id"], title, f"page={chosen}, no version"))
            continue
        row["version"] = version
        row["version_source"] = "derived-related-quest"
        row["version_confidence"] = "inferred"
        filled += 1

    with INDEX.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"filled={filled} unresolved={len(unresolved)}")
    for item in unresolved[:20]:
        print("  ", item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
