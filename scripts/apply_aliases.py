#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把复核通过的别名写进对应 seed 文件。

`aliases` 属于实体本身，所以写回它所在的那一批 seed（stage1/3/4/5），
而不是另开一份表——否则灌库、导出卡片、Web UI 三处都要各读一遍。

这里只保留**有辨识度的称号**：像「女仆」「堂主」「宫司」这种职务词，
搜出来会命中一大片，反而降低检索质量，一律不收。

用法：
    python scripts/apply_aliases.py            # 只报告
    python scripts/apply_aliases.py --apply    # 写入 seed
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SEEDS = sorted((ROOT / "knowledge").glob("seed*.yaml"))
APPLY = "--apply" in sys.argv
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

# 复核通过：正名|别名。只收能唯一指认这个人的称号。
KEEP = """
玛薇卡|火神
莱欧斯利|公爵
钟离|岩王爷
赛诺|大风纪官
那维莱特|最高审判官
桑多涅|木偶
北斗|大姐头
可莉|火花骑士
云堇|云先生
刻晴|玉衡星
刻晴|玉衡
凝光|天权星
凝光|天权
琴|蒲公英骑士
神里绫华|白鹭公主
阿贝多|白垩之子
芭芭拉|闪耀偶像
雷利尔|猎月人
迪希雅|炽鬃之狮
优菈|浪花骑士
奥赛尔|漩涡之魔神
娜维娅|刺玫会会长
跋掣|旋涡的余威
菈乌玛|咏月使
甘雨|半仙
"""

pairs = [tuple(x.strip() for x in line.split("|", 1))
         for line in KEEP.strip().splitlines() if "|" in line]

added = 0
for path in SEEDS:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    ents = data.get("entities") or []
    changed = False
    for item in ents:
        have = {a["name"] for a in item.get("aliases") or []}
        for cname, alias in pairs:
            if item.get("name") == cname and alias not in have:
                item.setdefault("aliases", []).append({"name": alias, "kind": "alias"})
                have.add(alias)
                added += 1
                changed = True
    if changed and APPLY:
        header = "".join(line + "\n" for line in
                         path.read_text(encoding="utf-8").split("\n")[:8]
                         if line.startswith("#"))
        path.write_text(header + yaml.safe_dump(data, allow_unicode=True,
                                                sort_keys=False, width=200),
                        encoding="utf-8")
        print(f"写入 {path.name}")

print(f"别名 {len(pairs)} 条，新增 {added} 条" + ("" if APPLY else "（加 --apply 才写入）"))
