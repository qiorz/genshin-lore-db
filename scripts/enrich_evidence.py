#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给已有种子补足锚点证据（不改实体集合，只改 evidence 列表）。

背景：第四、五批的高频实体已经给了 3 个锚点，但第三批（`seed-stage3.yaml`）
每个实体只写了一条。于是「枫丹」这类被 794 篇文档提到的实体，卡片上只有一句
看起来并不典型的引文，读者会以为数据缺失。

本脚本只做一件事：对指定种子里证据少于 k 条的实体，从语料里补到 k 条。
- 不动 id / 类型 / 名称 / 描述；
- 已有多条的不动；
- 找不到更多就保持原样，不硬凑。

用法：
    python scripts/enrich_evidence.py knowledge/seed-stage3.yaml          # 报告
    python scripts/enrich_evidence.py knowledge/seed-stage3.yaml --apply  # 改写
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_stage4 import best_evidences  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "db/genshin_lore.sqlite3"
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

APPLY = "--apply" in sys.argv
RESORT = "--resort" in sys.argv
files = [a for a in sys.argv[1:] if a.endswith(".yaml")]
if not files:
    print("用法：python scripts/enrich_evidence.py knowledge/seed-stage3.yaml [--apply]")
    raise SystemExit(2)
TARGET = 3

con = sqlite3.connect(DB)
cache: dict = {}
total_add = 0

for rel in files:
    path = ROOT / rel if not Path(rel).is_absolute() else Path(rel)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entities = data.get("entities") or []
    changed = 0
    resorted = 0

    # 重排：主锚点应该是「原文把名字当专名引用」的那条，而不是最早写进去的那条
    if RESORT:
        reordered = 0
        for item in entities:
            evs = item.get("evidence") or []
            if len(evs) < 2:
                continue
            name = item["name"]
            titles = {r[0]: (r[1] or "") for r in con.execute(
                "SELECT doc_id, title FROM documents WHERE doc_id IN (%s)"
                % ",".join("?" * len(evs)), [e["doc"] for e in evs])}
            def key(e):
                q = e.get("quote") or ""
                # 三种情况分开排：原词被括注（最好）> 没括注 > 只是更长词的前缀
                # （「原初一滴」对「原初」就是第三种，不能当主锚点）
                if f"「{name}」" in q:
                    rank = 0
                elif f"「{name}" in q:
                    rank = 2
                else:
                    rank = 1
                return (rank,
                        0 if name in titles.get(e["doc"], "") else 1,
                        len(q))
            ordered = sorted(evs, key=key)
            if ordered != evs:
                item["evidence"] = ordered
                reordered += 1
        resorted = reordered
        print(f"{path.name}: 重排 {reordered} 个实体的锚点顺序")

    for item in entities:
        have = item.get("evidence") or []
        if len(have) >= TARGET:
            continue
        if item.get("type") == "character":
            continue          # 人物的锚点就是他自己那一页，不必再补任务里的顺带提及
        name = item["name"]
        picked = best_evidences(con, name, cache, k=TARGET)
        if not picked:
            continue
        keep_docs = {e["doc"] for e in have}
        merged = list(have) + [{"doc": d, "quote": q} for d, q in picked
                               if d not in keep_docs]
        trimmed = merged[:TARGET]
        if len(trimmed) > len(have):
            item["evidence"] = trimmed
            changed += 1
            total_add += len(trimmed) - len(have)
    print(f"{path.name}: {len(entities)} 个实体，补足 {changed} 个")
    if APPLY and (changed or resorted):
        # 保留文件头的说明注释，只重写 YAML 主体
        header = "".join(
            line + "\n" for line in
            path.read_text(encoding="utf-8").split("\n")[:6] if line.startswith("#")
        )
        path.write_text(
            header + yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=200),
            encoding="utf-8",
        )

print(f"共新增 {total_add} 条证据" + ("" if APPLY else "（加 --apply 才写入）"))
