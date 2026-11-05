#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按版本更新说明的上线日期时间线，给「有 release_date 但没 version」的文档推导版本。

版本区间是确定的：1.1→7.2 共 53 篇官方版本更新说明，各自有明确上线日期。
公告发布日期落在哪个区间，就属于哪个版本。这不是猜，但仍是推导：
来源仍是官方公告（`version_source: official`），置信度标 `inferred`，
并在 `notes` 里写明推导依据。不新增枚举值，避免改动 DB 的 CHECK 约束。

上游本来就没有版本字段的类型（物品、NPC 对话、观景点、散落文本）不在处理范围内，
按项目约定保持留空，不硬填。

用法：
    python scripts/enrich_release_versions.py            # 干跑
    python scripts/enrich_release_versions.py --apply    # 写回 front matter + 更新 notices/index.csv
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
NOTICE_INDEX = ROOT / "corpus/notices/index.csv"
REPORT = ROOT / "manifests/metadata-enrichment.csv"
APPLY = "--apply" in sys.argv
SKIP_FILES = {"readme.md", "index.md"}
SOURCE = "official"
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


def load_timeline() -> list[tuple[str, str]]:
    with NOTICE_INDEX.open(encoding="utf-8-sig", newline="") as fh:
        rows = [r for r in csv.DictReader(fh)
                if r.get("version") and r.get("release_date")
                and r.get("subtype") == "版本更新说明"]
    timeline = sorted({(r["release_date"], r["version"]) for r in rows})
    if not timeline:
        raise SystemExit("版本时间线为空：检查 corpus/notices/index.csv")
    return timeline


def version_for_date(timeline: list[tuple[str, str]], date: str) -> str | None:
    found = None
    for start, version in timeline:
        if start <= date:
            found = version
        else:
            break
    return found


def read_fm(text: str) -> tuple[dict, str, str]:
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("unterminated front matter")
    return yaml.safe_load(parts[1]), parts[1], parts[2]


def main() -> int:
    timeline = load_timeline()
    print(f"版本时间线：{len(timeline)} 个版本，{timeline[0][0]} → {timeline[-1][0]}")

    changes: list[dict] = []
    for path in sorted((ROOT / "corpus").rglob("*.md")):
        if path.name.lower() in SKIP_FILES:
            continue
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            continue
        try:
            meta, _raw, body = read_fm(text)
        except Exception as exc:
            print(f"  skip {path.name}: {exc}")
            continue
        if not isinstance(meta, dict) or meta.get("version") or not meta.get("release_date"):
            continue
        date = str(meta["release_date"])
        version = version_for_date(timeline, date)
        if not version:
            print(f"  no window: {meta.get('id')} {date}")
            continue
        meta["version"] = version
        meta["version_source"] = SOURCE
        meta["version_confidence"] = "inferred"
        meta["notes"] = (str(meta.get("notes") or "").rstrip()
                         + f" 版本由官方版本更新说明的上线日期区间推导（{date} 落在 {version} 版本期内）。")
        changes.append({
            "doc_id": meta.get("id", ""),
            "title": meta.get("title", ""),
            "release_date": date,
            "inferred_version": version,
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        })
        print(f"  {meta.get('id')}: {date} -> {version}")
        if APPLY:
            head = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=120)
            path.write_text(f"---\n{head}---\n{body}", encoding="utf-8", newline="\n")

    if APPLY and changes:
        by_id = {c["doc_id"]: c["inferred_version"] for c in changes}
        rows = list(csv.DictReader(NOTICE_INDEX.open(encoding="utf-8-sig", newline="")))
        for row in rows:
            if row["doc_id"] in by_id and not row.get("version"):
                row["version"] = by_id[row["doc_id"]]
        with NOTICE_INDEX.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        with REPORT.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(changes[0].keys()))
            w.writeheader()
            w.writerows(changes)

    print(f"{'写入' if APPLY else '可推导'} {len(changes)} 篇"
          + (f"，清单 {REPORT.relative_to(ROOT)}" if APPLY and changes else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
