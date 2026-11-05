#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""清理 `knowledge/entities/` 下的过期/重复卡片。

为什么需要：卡片是按 `entity_type` 分目录写的。一个实体从 location 改成
organization 后，旧目录里的那份不会被自动删掉，于是同一个 id 有两张卡。
实体被剪掉（`load_knowledge.py --prune`）后，它的卡也会留在磁盘上。

用 YAML 解析 front matter 判断 id，不用正则——之前用 `re.search(r"^id:\\s*(\\S+)")`
在 `python -c` 里跑，反斜杠被 shell 吃掉，导致「重复 0 张」的假阴性。

用法：
    python scripts/prune_cards.py            # 只报告
    python scripts/prune_cards.py --apply    # 删除过期与重复副本
"""
from __future__ import annotations

import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "db/genshin_lore.sqlite3"
CARD_DIR = ROOT / "knowledge/entities"
APPLY = "--apply" in sys.argv
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


def front_matter(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        return yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return None


def main() -> int:
    con = sqlite3.connect(DB)
    ids = {r[0] for r in con.execute("SELECT entity_id FROM entities")}
    types = dict(con.execute("SELECT entity_id, entity_type FROM entities"))
    con.close()

    by_id: dict[str, list[Path]] = defaultdict(list)
    no_fm: list[Path] = []
    for path in sorted(CARD_DIR.rglob("*.md")):
        if path.name == "README.md":
            continue
        fm = front_matter(path)
        if not fm or not fm.get("id"):
            no_fm.append(path)
            continue
        by_id[fm["id"]].append(path)

    stale = [p for eid, paths in by_id.items() if eid not in ids for p in paths]
    dupes: list[Path] = []
    for eid, paths in by_id.items():
        if len(paths) < 2:
            continue
        want = types.get(eid)
        keep = next((p for p in paths if p.parent.name == f"{want}s"), paths[0])
        dupes += [p for p in paths if p != keep]

    print(f"卡片 {sum(len(v) for v in by_id.values())} 张 · 实体 {len(ids)} 个")
    print(f"过期（库里没有该 id）：{len(stale)}")
    for p in stale:
        print("  -", p.relative_to(ROOT))
    print(f"重复副本（同 id 多目录）：{len(dupes)}")
    for p in dupes:
        print("  -", p.relative_to(ROOT))
    if no_fm:
        print(f"无 front matter（跳过，需人工看）：{len(no_fm)}")
        for p in no_fm:
            print("  ?", p.relative_to(ROOT))

    if APPLY and (stale or dupes):
        for p in stale + dupes:
            p.unlink()
        print(f"已删除 {len(stale) + len(dupes)} 个文件")
    elif stale or dupes:
        print("（加 --apply 才会真的删）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
