#!/usr/bin/env python3
"""Build manifests/character-index.csv from the OBC character channel list."""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANNEL = ROOT / "raw" / "official_site" / "obc" / "channel_lists" / "25.json"
OUT = ROOT / "manifests" / "character-index.csv"
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

REGION_MAP = {
    "枫丹廷": "枫丹",
    "枫丹": "枫丹",
    "蒙德城": "蒙德",
    "蒙德": "蒙德",
    "璃月港": "璃月",
    "璃月": "璃月",
    "稻妻城": "稻妻",
    "稻妻": "稻妻",
    "须弥城": "须弥",
    "须弥": "须弥",
    "纳塔": "纳塔",
    "挪德卡莱": "挪德卡莱",
    "至冬": "至冬",
    "未知": "未知",
}


def facets(entry: dict) -> dict[str, str]:
    ext = entry.get("ext") or "{}"
    try:
        data = json.loads(ext)
        text = list(data.values())[0].get("filter", {}).get("text", "[]")
        values = json.loads(text) if isinstance(text, str) else text
    except Exception:
        return {}
    result = {}
    for value in values:
        if "/" in value:
            key, val = value.split("/", 1)
            result[key] = val
    return result


def main() -> int:
    payload = json.loads(CHANNEL.read_text(encoding="utf-8"))
    channel = (payload.get("data") or {}).get("list") or []
    entries = (channel[0].get("list") or []) if channel else []
    rows = []
    for entry in entries:
        f = facets(entry)
        region = REGION_MAP.get(f.get("地区", ""), f.get("地区", ""))
        rows.append(
            {
                "content_id": str(entry.get("content_id")),
                "title": (entry.get("title") or "").strip(),
                "doc_type": "character",
                "region": region,
                "element": f.get("元素", ""),
                "weapon": f.get("武器", ""),
                "star": f.get("星级", ""),
                "version": "",
                "version_source": "unknown",
                "version_confidence": "unknown",
                "status": "planned",
                "url": f"https://baike.mihoyo.com/ys/obc/content/{entry.get('content_id')}/detail?bbs_presentation_style=no_header",
            }
        )
    with OUT.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["content_id"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {OUT} rows={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
