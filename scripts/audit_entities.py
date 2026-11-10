#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""实体卡片的「厚薄」体检：关系 / 说法 / 时间线 / 别名 四项覆盖。

为什么要单独体检：实体数够不代表知识层厚。400 张卡里可能有六成
只有一句出处，点进去空空如也。这个脚本按类型统计覆盖，找出空白集中在哪。

统计口径：
  关系     entity_relations 里除 involved_in 之外的边，出边+入边都算
  说法     claims.subject_id
  时间线   通过 involved_in → timeline_entries 能反查到的条目
  别名     entity_names 里 is_primary=0 的行
  出处     entity_evidence 行数（顺带看锚点够不够）

用法：
    python scripts/audit_entities.py                 # 打印
    python scripts/audit_entities.py --write         # 另写 exports/review/entity-coverage.md
"""
from __future__ import annotations

import sqlite3
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "db/genshin_lore.sqlite3"
OUT = ROOT / "exports/review/entity-coverage.md"
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

TYPE_LABEL = {"character": "人物", "location": "地点", "concept": "概念",
              "organization": "组织", "creature": "生物", "event": "事件",
              "deity": "神明", "nation": "国家"}


def main() -> int:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    ents = list(con.execute("SELECT entity_id, canonical_name, entity_type FROM entities"))

    rel = {r[0]: r[1] for r in con.execute(
        """SELECT entity_id, COUNT(*) FROM (
               SELECT subject_id AS entity_id FROM entity_relations
                 WHERE predicate <> 'involved_in'
               UNION ALL
               SELECT object_id FROM entity_relations
                 WHERE object_id IS NOT NULL AND predicate <> 'involved_in')
           GROUP BY 1""")}
    clm = {r[0]: r[1] for r in con.execute(
        "SELECT subject_id, COUNT(*) FROM claims GROUP BY 1")}
    alias = {r[0]: r[1] for r in con.execute(
        "SELECT entity_id, COUNT(*) FROM entity_names WHERE is_primary=0 GROUP BY 1")}
    tl = {r[0]: r[1] for r in con.execute(
        """SELECT r.subject_id, COUNT(DISTINCT t.entry_id)
           FROM entity_relations r JOIN timeline_entries t ON t.event_id = r.object_literal
           WHERE r.predicate = 'involved_in' GROUP BY 1""")}
    ev = {r[0]: r[1] for r in con.execute(
        "SELECT entity_id, COUNT(*) FROM entity_evidence GROUP BY 1")}

    by_type = defaultdict(list)
    for e in ents:
        by_type[e["entity_type"]].append(e)

    lines = [f"# 实体卡片覆盖体检", "", f"> {date.today().isoformat()} · {len(ents)} 个实体", "",
             "| 类型 | 数量 | 有边 | 有说法 | 有时间线 | 有别名 | 平均边 | 平均说法 | 平均出处 |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for t, rows in sorted(by_type.items(), key=lambda kv: -len(kv[1])):
        n = len(rows)
        f = lambda d: sum(1 for e in rows if d.get(e["entity_id"]))
        avg = lambda d: sum(d.get(e["entity_id"], 0) for e in rows) / n
        lines.append(f"| {TYPE_LABEL.get(t, t)} | {n} | {f(rel)} | {f(clm)} | {f(tl)} | "
                     f"{f(alias)} | {avg(rel):.1f} | {avg(clm):.1f} | {avg(ev):.1f} |")

    total = len(ents)
    got = lambda d: sum(1 for e in ents if d.get(e["entity_id"]))
    empty4 = sum(1 for e in ents if not any([
        rel.get(e["entity_id"]), clm.get(e["entity_id"]),
        tl.get(e["entity_id"]), alias.get(e["entity_id"])]))
    lines += ["", f"- 有边：{got(rel)}/{total}（{got(rel)*100//total}%）",
              f"- 有说法：{got(clm)}/{total}（{got(clm)*100//total}%）",
              f"- 有时间线：{got(tl)}/{total}（{got(tl)*100//total}%）",
              f"- 有别名：{got(alias)}/{total}（{got(alias)*100//total}%）",
              f"- **四项全空：{empty4}/{total}**", ""]

    # 最空的 60 张（按四项总和排序）
    def thin(e):
        eid = e["entity_id"]
        return (rel.get(eid, 0) + clm.get(eid, 0) + tl.get(eid, 0) + alias.get(eid, 0))

    lines += ["## 最空的 40 张", "", "| 实体 | 类型 | 关系 | 说法 | 时间线 | 别名 | 出处 |",
              "|---|---|---:|---:|---:|---:|---:|"]
    for e in sorted(ents, key=thin)[:40]:
        eid = e["entity_id"]
        lines.append(f"| {e['canonical_name']} | {TYPE_LABEL.get(e['entity_type'], e['entity_type'])} "
                     f"| {rel.get(eid, 0)} | {clm.get(eid, 0)} | {tl.get(eid, 0)} "
                     f"| {alias.get(eid, 0)} | {ev.get(eid, 0)} |")

    text = "\n".join(lines) + "\n"
    print(text)
    if "--write" in sys.argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(text, encoding="utf-8")
        print(f"报告 -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
