#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""暗示层灌库。

知识源：knowledge/allusions.yaml（人工维护）
  每条 = 标题 + 表面内容 + 影射对象 + 置信度 + 依据 + caveat。

与 load_theories.py 的差别：
  - allusions 的「引文」多半写在 basis 里，不是独立字段，所以 section_id 常解不出来；
    这里允许 section_id 为空（still 有 doc_id 可回溯到文档），并在报告里统计缺失率。
  - 单独支持可选的 quote 字段：写了就解析，能提高溯源精度。

    python scripts/load_allusions.py            # 干跑：只统计
    python scripts/load_allusions.py --apply    # 写库
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

from load_knowledge import resolve  # noqa: E402

DB = ROOT / "db" / "genshin_lore.sqlite3"
SCHEMA = ROOT / "schema" / "allusions.sql"
SOURCE = ROOT / "knowledge" / "allusions.yaml"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    data = yaml.safe_load(SOURCE.read_text(encoding="utf-8")) or {}
    items = data.get("allusions") or []
    if not items:
        print("没有读到任何条目")
        return 1

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA.read_text(encoding="utf-8"))

    cache: dict[tuple[str, str], tuple[int, int] | None] = {}
    rows = []
    errors = []
    no_quote = 0
    unresolved = 0

    for it in items:
        aid = str(it.get("id") or "").strip()
        if not aid:
            errors.append("有一条缺 id")
            continue
        doc = (it.get("doc") or "").strip() or None
        quote = (it.get("quote") or "").strip()
        section_id = None
        if doc and not con.execute("SELECT 1 FROM documents WHERE doc_id=?", (doc,)).fetchone():
            errors.append(f"{aid}: doc 不存在 {doc}")
            doc = None
        if doc and quote:
            hit = resolve(con, doc, quote, cache)
            if hit:
                section_id = hit[0]
            else:
                unresolved += 1
                errors.append(f"{aid}: 引文未命中 {doc} | {quote[:30]}")
        elif doc:
            no_quote += 1

        rows.append((
            aid, doc, it.get("title") or aid, it.get("surface"),
            it.get("target"), it.get("confidence") or "tentative",
            it.get("basis"), it.get("caveat"), it.get("extra"),
            it.get("status") or "open", quote or None, section_id,
        ))

    print(f"读到 {len(rows)} 条")
    print(f"  有 doc 但无 quote（无法定位段落）：{no_quote}")
    print(f"  有 quote 但未命中：{unresolved}")
    print(f"  错误：{len(errors)}")
    for e in errors[:8]:
        print("   ", e)

    if args.apply and not errors:
        con.executemany(
            """INSERT INTO allusions (allusion_id, doc_id, title, surface, target,
                                      confidence, basis, caveat, extra, status, quote, section_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(allusion_id) DO UPDATE SET
                 doc_id=excluded.doc_id, title=excluded.title, surface=excluded.surface,
                 target=excluded.target, confidence=excluded.confidence,
                 basis=excluded.basis, caveat=excluded.caveat, extra=excluded.extra,
                 status=excluded.status, quote=excluded.quote,
                 section_id=excluded.section_id""",
            rows,
        )
        con.commit()
        print("写入完成")
    elif args.apply:
        print("有错误，未写库")
    else:
        print("(dry-run，加 --apply 写库)")

    for r in con.execute("SELECT confidence, status, n FROM v_allusion_coverage ORDER BY n DESC"):
        print(f"  {r['confidence']:<10}{r['status']:<10}{r['n']}")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
