#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从正文里挖「人—组织—国家」三类关系，每条都带原话。

为什么不用模型总结：关系是知识层里最容易被写错的东西。宁可只要
「同一句里两个实体挨在一起、中间只有连接词或职务词」这种硬证据，
也不要「读起来大概是」的推断。

三类谓词与判据：
  member_of   人物 → 组织   例：「西风骑士团代理团长——琴」「九条裟罗，天领奉行九条家的养子」
  based_in    组织 → 国家   例：「西风骑士团是蒙德的……」
  located_in  地点 → 国家   例：「蒙德城位于蒙德」「璃月港是璃月最繁华的港口」

判据（缺一不可）：
  1. 同一句里同时出现两个名字；
  2. 两个名字之间的跨度 ≤ SPAN 个字；
  3. 中间要么全是连接词（的/是/正是/，/——/「」…），要么含明确的职务/归属词。
     含职务词记 confirmed，只有连接词记 likely。

跨度大、中间夹着别的谓语（「西风骑士团得知愚人众要抢天空之琴」）一律不收——
那句话没有断言任何归属。

用法：
    python scripts/mine_relations.py            # 干跑，打印样例与统计
    python scripts/mine_relations.py --apply    # 写 knowledge/seed-stage6.yaml
"""
from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_stage4 import sentences  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "db/genshin_lore.sqlite3"
CSV_OUT = ROOT / "knowledge/relation-candidates.csv"
YAML_OUT = ROOT / "knowledge/seed-stage6.yaml"
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

REL_BASE = 7000          # 本批关系 id 区间，避开人工的 2000 段与 involved_in 的 5000 段
SPAN = 16                # 两个名字之间的最大跨度（含连接词）

CONNECTORS = set("的是乃为，、·「」『』—-… 　 \t")
ROLE_WORDS = (
    "团长", "副团长", "代理团长", "成员", "队员", "骑士", "大贤者", "贤者", "学者",
    "研究员", "执行官", "席", "干部", "队长", "首领", "家主", "养子", "养女",
    "大小姐", "少爷", "祭司", "巫女", "大将", "部下", "属下", "门客", "学徒",
    "学生", "教授", "讲师", "研究员", "所长", "会长", "社长", "掌柜", "老板",
)
LOC_WORDS = ("位于", "地处", "坐落", "境内", "属于", "管辖", "下辖", "领内")
ORG_WORDS = ("总部", "驻地", "据点", "成立于", "隶属于", "效忠于", "麾下")


# 人工复核后剔除的候选：机器只看句式，看不出「这句话到底在说谁」。
# 每条都写明理由，便于以后改判据时复查。
DROP = {
    ("多托雷", "愚人众"): "引文重复损坏（「使用使用」），证据不可用",
    ("皮耶罗", "愚人众"): "同上",
    ("艾莉丝", "西风骑士团"): "这句是法尔伽在自述，艾莉丝只是被提到",
    ("雷电将军", "愚人众"): "原文说「成为执行官之前是雷电将军的原型机」，方向反了",
    ("五郎", "幕府"): "五郎是珊瑚宫一方，与幕府对阵",
    ("夏沃蕾", "花羽会"): "原文是「拉拢她加入」，尚未加入",
    ("琴", "西风教会"): "琴属骑士团，这句是在疏散教会成员",
    ("坎蒂丝", "盗宝团"): "盗宝团成员与坎蒂丝是两个人，只是同句出现",
    ("那维莱特", "特巡队"): "原文说的是「那维莱特改组的警方」，不是他属于特巡队",
    ("奈芙尔", "冒险家协会"): "奈芙尔是秘闻馆老板，原文在对比两家机构",
    ("旅行者", "千岩军"): "「你好旅行者，千岩军…」是问候语",
    ("旅行者", "冒险家协会"): "同上，接待用语",
    ("琴", "愚人众"): "这句在讨论天空之琴被谁拿走",
    ("米卡", "愚人众"): "原文是「逻辑链推测」，不是事实",
    ("琳妮特", "愚人众"): "「琳妮特的愚人众下属成员」指向不明",
    ("哥伦比娅", "愚人众执行官"): "原文写「前」执行官，按历史身份另记更合适",
    ("五郎", "八重堂"): "五郎是给八重堂投稿答疑，不是成员",
    ("欧洛伦", "烟谜主"): "「烟谜主怎么样了」没有断言归属",
    ("早柚", "神里家"): "早柚属社奉行；神里家是同一句里的另一层",
    ("辛焱", "千岩军"): "原文是千岩军要抓捕辛焱",
    ("申鹤", "万民堂"): "「自从去了万民堂」是常去，不是成员",
    ("提纳里", "盗宝团"): "这句是角色扮演的假身份",
    ("希诺宁", "悬木人"): "三个部族并列，串行了；希诺宁属回声之子",
    ("基尼奇", "回声之子"): "同上，基尼奇属悬木人",
    ("芭芭拉", "西风骑士团"): "芭芭拉属西风教会；这句把「祈礼牧师」挂到了骑士团",
    ("七七", "不卜庐"): "原文只说「借走了七七」，未断言受雇",
}

def gap_of(sent: str, a: str, b: str) -> tuple[int, str, int] | None:
    """取两个名字最近的一次**不重叠**共现，返回（跨度, 中间文本, 起始位置）。

    必须排除重叠：`蒙德` 是 `蒙德城` 的子串，否则「前往蒙德城」会被当成
    「蒙德城 位于 蒙德」的证据——那是子串匹配，不是原文断言。
    """
    pa = [(m.start(), m.start() + len(a)) for m in re.finditer(re.escape(a), sent)]
    pb = [(m.start(), m.start() + len(b)) for m in re.finditer(re.escape(b), sent)]
    best = None
    for i0, i1 in pa:
        for j0, j1 in pb:
            if i0 < j1 and j0 < i1:      # 两段有重叠 → 不算
                continue
            lo, hi = (i1, j0) if j0 >= i1 else (j1, i0)
            span = hi - lo
            if best is None or span < best[0]:
                best = (span, sent[lo:hi], min(i0, j0))
    return best



def strict_geo_match(sent: str, a: str, b: str, predicate: str) -> bool:
    """地点/组织 → 国家：只认相邻句式，不靠距离猜。

    认的句式（a=地点/组织，b=国家）：
      a + 位于|地处|坐落在|在 + b        「梅洛彼得堡位于枫丹」
      b + 境内|内 + 的? + a              「璃月境内的层岩巨渊」
      b + 的 + a                         「蒙德的晨曦酒庄」
      组织：a + 总部位于|总部设在|成立于|隶属于 + b
    「古城垣位于天衡山」「闻名璃月的餐馆」这类都会被排除。
    """
    ea, eb = re.escape(a), re.escape(b)
    if predicate == "based_in":
        # 只认「总部在哪儿」这类明确表述；「潜伏在稻妻的愚人众」不算
        pats = [rf"{ea}(?:的总部)?(?:位于|设在|坐落于|成立于|隶属于){eb}"]
    else:
        # 「在」太宽（「晨曦酒庄在蒙德酒业的地位」），只认位于/地处/坐落在
        pats = [rf"{ea}(?:位于|地处|坐落在){eb}",
                rf"{eb}(?:境内|内)的?{ea}",
                rf"{eb}的{ea}"]
    return any(re.search(p, sent) for p in pats)


def classify(mid: str, words: tuple[str, ...], allow_connector: bool) -> str | None:
    if any(w in mid for w in words):
        return "confirmed"
    if allow_connector and len(mid) <= 3 and all(ch in CONNECTORS for ch in mid):
        return "likely"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    ents = {r["entity_id"]: dict(r) for r in con.execute(
        "SELECT entity_id, canonical_name, entity_type FROM entities")}
    by_name = {e["canonical_name"]: e for e in ents.values()}

    chars = [e for e in ents.values() if e["entity_type"] == "character"]
    orgs = [e for e in ents.values() if e["entity_type"] == "organization"]
    locs = [e for e in ents.values() if e["entity_type"] == "location"]
    nations = [e for e in ents.values() if e["entity_type"] == "nation"]

    existing = {(r["subject_id"], r["predicate"], r["object_id"])
                for r in con.execute(
                    "SELECT subject_id, predicate, object_id FROM entity_relations "
                    "WHERE object_id IS NOT NULL")}

    plan = [
        ("member_of", "character", "organization", ROLE_WORDS, True),
        ("based_in", "organization", "nation", ORG_WORDS, False),
        ("located_in", "location", "nation", LOC_WORDS, False),
    ]
    want = {(s, o) for _p, s, o, _w, _c in plan}
    NATION_NAMES = [e["canonical_name"] for e in ents.values()
                    if e["entity_type"] == "nation"]
    # 补丁公告、物品描述不是叙事文本，不拿来当关系证据
    SKIP_DOC_TYPES = {"notice", "item", "weapon", "artifact"}

    # --- 倒排：先算每个实体出现在哪些段落，再只看「一段里有两个以上实体」的段落。
    # 逐对 LIKE 的复杂度是 191×35 次全表扫描，跑不完。
    print("建立实体 → 段落倒排…")
    mentions: dict[str, set[int]] = {}
    for e in ents.values():
        mentions[e["entity_id"]] = {r[0] for r in con.execute(
            "SELECT section_id FROM sections WHERE body LIKE ?",
            (f"%{e['canonical_name']}%",))}
    sec_entities: dict[int, list[str]] = {}
    for eid, secs in mentions.items():
        for sid in secs:
            sec_entities.setdefault(sid, []).append(eid)
    multi = {sid: ids for sid, ids in sec_entities.items() if len(ids) > 1}
    print(f"  含 ≥2 个实体的段落 {len(multi)} / {len(sec_entities)}")

    rows: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    stats = Counter()

    for sid, ids in multi.items():
        row = con.execute("SELECT doc_id, body FROM sections WHERE section_id=?", (sid,)).fetchone()
        if not row:
            continue
        doc_id, body = row["doc_id"], row["body"] or ""
        if doc_id.split(".")[0] in SKIP_DOC_TYPES:
            continue
        sents = [s for s in sentences(body)]
        for a_id in ids:
            a = ents[a_id]
            for b_id in ids:
                if a_id == b_id:
                    continue
                b = ents[b_id]
                if (a["entity_type"], b["entity_type"]) not in want:
                    continue
                predicate, words, allow_conn = next(
                    (p, w, c) for p, s, o, w, c in plan
                    if (s, o) == (a["entity_type"], b["entity_type"]))
                key = (a_id, predicate, b_id)
                if key in existing or key in seen:
                    continue
                if (a["canonical_name"], b["canonical_name"]) in DROP:
                    continue
                an, bn = a["canonical_name"], b["canonical_name"]
                hit = None
                for s in sents:
                    if an not in s or bn not in s:
                        continue
                    if predicate in ("located_in", "based_in"):
                        if any(neg in s for neg in ("不属于", "不是", "并非", "不在", "未属于", "不隶属")):
                            continue
                        if sum(1 for n in NATION_NAMES if n in s) > 1:
                            continue
                        if not strict_geo_match(s, an, bn, predicate):
                            continue
                        hit = (doc_id, s, "confirmed", "")
                        break
                    g = gap_of(s, an, bn)
                    if not g:
                        continue
                    span, mid, _pos = g
                    if span > SPAN:
                        continue
                    conf = classify(mid, words, allow_conn)
                    if not conf:
                        continue
                    # 「不属于蒙德」「不是稻妻人」——否定句不能当归属证据
                    if any(neg in s for neg in ("不属于", "不是", "并非", "不在", "未属于")):
                        continue

                    if predicate == "member_of" and bn in mid:
                        continue
                    hit = (doc_id, s, conf, mid)
                    break
                if hit:
                    seen.add(key)
                    rows.append({
                        "subject": a_id, "predicate": predicate, "object": b_id,
                        "doc": hit[0], "quote": hit[1], "confidence": hit[2],
                        "subject_name": an, "object_name": bn, "gap": hit[3],
                    })
    rows.sort(key=lambda r: (r["confidence"] != "confirmed", r["predicate"]))
    for r in rows:
        stats[r["predicate"]] += 1

    print(f"候选 {len(rows)} 条：" + " · ".join(f"{k} {v}" for k, v in stats.items()))

    with CSV_OUT.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["subject", "subject_name", "predicate", "object", "object_name",
                    "confidence", "gap", "doc_id", "quote"])
        for r in rows:
            w.writerow([r["subject"], r["subject_name"], r["predicate"], r["object"],
                        r["object_name"], r["confidence"], r["gap"], r["doc"], r["quote"]])
    print(f"候选清单 -> {CSV_OUT}")

    print("\n样例（每类 5 条）：")
    for pred in stats:
        for r in [x for x in rows if x["predicate"] == pred][:5]:
            print(f"  [{pred}] {r['subject_name']} → {r['object_name']}"
                  f"（{r['confidence']}）{r['quote'][:46]}")

    if args.apply:
        payload = {
            "version": 1, "batch": "2026-11-05-stage6", "status": "draft",
            "relations": [
                {"id": REL_BASE + i, "subject": r["subject"], "predicate": r["predicate"],
                 "object_id": r["object"], "confidence": r["confidence"], "spoiler": 1,
                 "doc": r["doc"], "quote": r["quote"]}
                for i, r in enumerate(rows, 1)
            ],
        }
        YAML_OUT.write_text(
            "# 第六批知识层种子 · 关系边（由 scripts/mine_relations.py 生成）\n"
            "# 判据：同句共现 + 跨度 ≤16 字 + 中间只有连接词或明确职务词。\n"
            "# 跨度大、中间夹着别的谓语的一律不收（那句话没断言归属）。\n"
            "# confidence=confirmed 表示中间有职务/归属词；likely 表示只有连接词。\n"
            + yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=200),
            encoding="utf-8",
        )
        print(f"已写入 {YAML_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
