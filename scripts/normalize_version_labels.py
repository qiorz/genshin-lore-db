#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 front matter 里的版本标签归一化成数字版本号。

问题：`version` 字段混有「月之一…月之八」（52 篇）和「常驻」（2 篇）。
前者项目已有 `manifests/version-labels.csv` 映射表，后者是玩法标签不是版本号。
混在版本下拉里会让「按 6.0 筛选」漏掉一批文档，属于筛选可用性问题。

规则：
  - 「月之X」→ 按映射表换成 6.0…6.7，原标签写进 notes 留痕；
  - 多版本列表（如 `1.0, 1.2, 2.0`）→ 取最早版本，完整列表留在 notes；
  - 版本区间（如 `2.3–2.4`）→ 取起始版本，原值留在 notes；
  - 其它非数字值（如「常驻」，是玩法标签）→ 移除 version，
    version_source/confidence 置 unknown，notes 说明原因。按项目约定不猜。
  - 已是 `X.Y` 的文档一律不动。

用法：
    python scripts/normalize_version_labels.py            # 干跑
    python scripts/normalize_version_labels.py --apply    # 写回 front matter + 同步各 index.csv
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
LABELS = ROOT / "manifests/version-labels.csv"
REPORT = ROOT / "manifests/version-normalization.csv"
CORPUS = ROOT / "corpus"
VERSION_RE = re.compile(r"^\d+\.\d+$")
MULTI_RE = re.compile(r"^(\d+\.\d+)(?:\s*[,，、]\s*\d+\.\d+)+$")
RANGE_RE = re.compile(r"^(\d+\.\d+)\s*[–\-—~至]\s*\d+\.\d+$")
SKIP_FILES = {"readme.md", "index.md"}
APPLY = "--apply" in sys.argv
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


def load_map() -> dict[str, str]:
    with LABELS.open(encoding="utf-8-sig", newline="") as fh:
        return {r["label"]: r["numeric_version"] for r in csv.DictReader(fh)}


def read_fm(text: str) -> tuple[dict, str]:
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("unterminated front matter")
    return yaml.safe_load(parts[1]), parts[2]


def main() -> int:
    mapping = load_map()
    changes: list[dict] = []
    for path in sorted(CORPUS.rglob("*.md")):
        if path.name.lower() in SKIP_FILES:
            continue
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            continue
        try:
            meta, body = read_fm(text)
        except Exception as exc:
            print(f"  skip {path.name}: {exc}")
            continue
        if not isinstance(meta, dict):
            continue
        raw = meta.get("version")
        if raw is None or VERSION_RE.match(str(raw)):
            continue
        label = str(raw)
        if label in mapping:
            new_version = mapping[label]
            action = "mapped"
            meta["version"] = new_version
            meta["notes"] = (str(meta.get("notes") or "").rstrip()
                             + f" 版本标签「{label}」按 manifests/version-labels.csv 归一化为 {new_version}。")
        elif MULTI_RE.match(label):
            new_version = MULTI_RE.match(label).group(1)
            action = "multi_first"
            meta["version"] = new_version
            meta["notes"] = (str(meta.get("notes") or "").rstrip()
                             + f" 原 version 为多版本列表「{label}」（分卷实装），取最早版本 {new_version} 用于筛选，完整列表见此备注。")
        elif RANGE_RE.match(label):
            new_version = RANGE_RE.match(label).group(1)
            action = "range_start"
            meta["version"] = new_version
            meta["notes"] = (str(meta.get("notes") or "").rstrip()
                             + f" 原 version 为版本区间「{label}」，取起始版本 {new_version} 用于筛选。")
        else:
            new_version = ""
            action = "removed"
            meta.pop("version", None)
            meta["version_source"] = "unknown"
            meta["version_confidence"] = "unknown"
            meta["notes"] = (str(meta.get("notes") or "").rstrip()
                             + f" 原 version 值「{label}」是玩法标签而非版本号，已移除（按约定不猜）。")
        changes.append({
            "doc_id": str(meta.get("id", "")),
            "title": str(meta.get("title", "")),
            "old_version": label,
            "new_version": new_version,
            "action": action,
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        })
        print(f"  {action:7} {meta.get('id')}: {label} -> {new_version or '(removed)'}")
        if APPLY:
            head = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=120)
            path.write_text(f"---\n{head}---\n{body}", encoding="utf-8", newline="\n")

    if APPLY and changes:
        by_id = {c["doc_id"]: c["new_version"] for c in changes}
        for index in sorted(CORPUS.rglob("index.csv")):
            with index.open(encoding="utf-8-sig", newline="") as fh:
                reader = csv.DictReader(fh)
                rows = list(reader)
                fieldnames = reader.fieldnames or []
            if "doc_id" not in fieldnames or "version" not in fieldnames:
                continue
            dirty = False
            for row in rows:
                if row.get("doc_id") in by_id:
                    row["version"] = by_id[row["doc_id"]]
                    dirty = True
            if dirty:
                with index.open("w", encoding="utf-8-sig", newline="") as fh:
                    w = csv.DictWriter(fh, fieldnames=fieldnames)
                    w.writeheader()
                    w.writerows(rows)
                print(f"  index updated: {index.relative_to(ROOT)}")
        with REPORT.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(changes[0].keys()))
            w.writeheader()
            w.writerows(changes)

    print(f"{'写入' if APPLY else '可归一化'} {len(changes)} 篇"
          + (f"，清单 {REPORT.relative_to(ROOT)}" if APPLY and changes else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
