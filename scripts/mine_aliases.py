#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从正文里挖别名：只收「原文把两个叫法摆在一起」的情况。

三种可靠形态：
  1. 「别名」正名        ——「仆人」阿蕾奇诺 / 「白鹭公主」神里绫华
  2. 正名——「别名」      ——西风骑士团代理团长——琴（这种是头衔不是别名，看情况）
  3. 人称/被称为/又称/又名 + 别名

不靠谱的一律不收：同一段里各说各的、隔了半句的、只是话题相关的。
每个候选都带原话与出处，人工过一遍再写进种子。

用法：
    python scripts/mine_aliases.py            # 干跑
    python scripts/mine_aliases.py --apply    # 写 knowledge/alias-candidates.yaml
"""
from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_stage4 import sentences  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "db/genshin_lore.sqlite3"
CSV_OUT = ROOT / "knowledge/alias-candidates.csv"
YAML_OUT = ROOT / "knowledge/alias-candidates.yaml"
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

QUOTED = re.compile(r"[「『]([^「」『』]{2,8})[」』]")
HINTS = ("人称", "被称为", "又称", "又名", "外号", "绰号")
# 这些不是别名，是称呼/泛称
STOP = {"大人", "先生", "小姐", "阁下", "女士", "少爷", "大小姐", "诸位", "各位",
        "旅行者", "客人", "朋友", "陌生人", "小家伙", "小家伙们", "年轻人",
        "老爷子", "老婆婆", "老人家", "小丫头", "小子",
        # 职务/角色词，不是别名
        "大将", "军师", "守护者", "姐姐", "哥哥", "大盗", "魔女", "骑士", "团长",
        "老板", "店长", "队长", "首领", "祭司", "学者", "研究员", "商人", "诗人",
        # 指示代词与口头碎片
        "那个", "这个", "这些", "那些", "他们", "她们", "我们", "你们", "什么",
        "怎么", "时候", "地方", "东西", "回收", "邪气"}
# 别名词只在这些类型上找：地点/概念不会有「称号」
ALIAS_TYPES = {"character", "deity", "creature", "organization"}



# 人工词表：官方称谓/称号。**只给「正名 → 可能的别称」，收不收由语料决定**——
# 每个别称必须在库里出现 ≥2 次才收，且不能已经是别的实体的正式名。
CURATED = """
钟离|摩拉克斯
钟离|岩王帝君
钟离|岩王爷
温迪|巴巴托斯
温迪|风神
纳西妲|小吉祥草王
纳西妲|布耶尔
纳西妲|草神
雷电影|巴尔泽布
雷电影|雷神
雷电影|影
那维莱特|水龙王
阿蕾奇诺|仆人
哥伦比娅|少女
桑多涅|木偶
多托雷|博士
皮耶罗|丑角
达达利亚|公子
流浪者|散兵
凝光|天权星
凝光|天权
刻晴|玉衡星
刻晴|玉衡
迪希雅|炽鬃之狮
赛诺|大风纪官
神里绫华|白鹭公主
北斗|大姐头
珊瑚宫心海|军师
八重神子|宫司
甘雨|半仙
魈|夜叉
胡桃|堂主
可莉|火花骑士
琴|蒲公英骑士
凯亚|骑兵队长
丽莎|图书管理员
安柏|侦察骑士
诺艾尔|女仆
菲谢尔|皇女
芭芭拉|闪耀偶像
香菱|万民堂大厨
重云|驱邪方士
行秋|飞云商会二少爷
七七|僵尸
迪奥娜|猫尾酒馆调酒师
阿贝多|白垩之子
优菈|浪花骑士
申鹤|凡人
云堇|云先生
夜兰|兰姐
提纳里|大巡林官
柯莱|见习巡林员
多莉|百货商人
坎蒂丝|守护者
妮露|祖拜尔剧场之星
赛索斯|缄默
那维莱特|最高审判官
芙宁娜|芙芙
娜维娅|刺玫会会长
莱欧斯利|公爵
千织|千织屋店主
希格雯|护士长
克洛琳德|决斗代理人
阿蕾奇诺|父亲
玛薇卡|火神
茜特菈莉|大祭司
恰斯卡|调停人
基尼奇|马力卜
"""

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    ents = [dict(r) for r in con.execute(
        "SELECT entity_id, canonical_name, entity_type FROM entities")]
    known = {r[0] for r in con.execute("SELECT name FROM entity_names")}
    has_alias = {r[0] for r in con.execute(
        "SELECT DISTINCT entity_id FROM entity_names WHERE is_primary=0")}

    cands: dict[tuple[str, str], dict] = {}
    for e in ents:
        if e["entity_id"] in has_alias:
            continue                      # 已有别名的不重复挖
        if e["entity_type"] not in ALIAS_TYPES:
            continue
        name = e["canonical_name"]
        if len(name) < 2:
            continue
        rows = con.execute(
            """SELECT doc_id, body FROM sections WHERE body LIKE ? LIMIT 400""",
            (f"%{name}%",)).fetchall()
        for r in rows:
            for s in sentences(r["body"] or ""):
                if name not in s:
                    continue
                for m in QUOTED.finditer(s):
                    alias = m.group(1).strip()
                    # 别名只能是 2–6 个汉字：带省略号/标点的多是台词碎片
                    if not re.fullmatch(r"[\u4e00-\u9fff]{2,6}", alias):
                        continue
                    if (alias == name or alias in known or alias in STOP
                            or name in alias):
                        continue
                    # 形态一/二：别名与正名相邻（中间最多 2 个字，如「」的、——）
                    after = s[m.end():m.end() + 3]
                    before = s[max(0, m.start() - 3):m.start()]
                    # 只认「「别名」正名」紧挨着的写法；隔了半句的不算
                    adjacent = after.startswith(name)
                    hinted = any(h in s for h in HINTS)
                    if not (adjacent or hinted):
                        continue
                    key = (e["entity_id"], alias)
                    item = cands.setdefault(key, {
                        "entity_id": e["entity_id"], "name": name,
                        "type": e["entity_type"], "alias": alias,
                        "count": 0, "doc": r["doc_id"], "quote": s,
                    })
                    item["count"] += 1
    # 人工词表：逐条到库里数出现次数，≥2 次才收
    curated_rows = []
    by_name = {e["canonical_name"]: e for e in ents}
    for line in CURATED.strip().splitlines():
        if "|" not in line:
            continue
        cname, alias = (x.strip() for x in line.split("|", 1))
        e = by_name.get(cname)
        if not e or alias in known or alias in STOP or alias in {r["alias"] for r in cands.values()
                                                                if r["entity_id"] == e["entity_id"]}:
            continue
        hit = con.execute(
            """SELECT doc_id, body FROM sections WHERE body LIKE ?
               AND body LIKE ? LIMIT 1""",
            (f"%{alias}%", f"%{cname}%"),
        ).fetchone()
        cnt = con.execute("SELECT COUNT(*) FROM sections WHERE body LIKE ?",
                          (f"%{alias}%",)).fetchone()[0]
        if cnt < 2 or not hit:
            continue
        curated_rows.append({
            "entity_id": e["entity_id"], "name": cname, "type": e["entity_type"],
            "alias": alias, "count": cnt, "doc": hit["doc_id"],
            "quote": next((s for s in sentences(hit["body"]) if alias in s),
                          (hit["body"] or "")[:60]),
            "source": "curated",
        })
    for r in cands.values():
        r["source"] = "mined"
    rows = [r for r in cands.values() if r["count"] >= 2] + curated_rows
    rows.sort(key=lambda x: -x["count"])
    print(f"候选 {len(rows)} 条，涉及 {len({r['entity_id'] for r in rows})} 个实体")

    with CSV_OUT.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["entity_id", "name", "type", "alias", "count", "doc_id", "quote",
                    "source"])
        for r in rows:
            w.writerow([r["entity_id"], r["name"], r["type"], r["alias"],
                        r["count"], r["doc"], r["quote"], r.get("source", "")])
    print(f"候选清单 -> {CSV_OUT}")
    for r in rows[:20]:
        print(f"  {r['name']} ← 「{r['alias']}」×{r['count']}  {r['quote'][:40]}")

    if args.apply:
        YAML_OUT.write_text(
            "# 别名候选（人工确认后再并进对应 seed 的 aliases）\n"
            + yaml.safe_dump({"candidates": rows}, allow_unicode=True,
                             sort_keys=False, width=200),
            encoding="utf-8")
        print(f"已写入 {YAML_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
