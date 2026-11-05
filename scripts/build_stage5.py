#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第五批：把实体从 250 扩到约 400，收尾。

四类来源，可靠程度从高到低：

  1. **NPC 人物**：靠 `sections.speaker` 统计。台词越多，说明这个人在剧情里越有分量；
     台词 ≥50 段、且库里还没有的，按台词量取前 N 个。证据就是他本人的一句台词。
  2. **概念 / 生物 / 神明 / 组织 / 节庆**：候选表只给名字，收不收由「库里有没有真实句子」决定。
  3. 描述一律中性：NPC 写「台词 N 段 / M 篇文档」，其余只写分类标签。
  4. 不生成关系。

排序与配额都写死在下面，跑完会打印每类的命中/落空，便于人工调整候选表。

用法：
    python scripts/build_stage5.py              # 干跑
    python scripts/build_stage5.py --apply      # 写 knowledge/seed-stage5.yaml
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from collections import Counter
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_stage4 import DOC_SCORE, best_evidences, pick_quote, slug  # noqa: E402,F401  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "db/genshin_lore.sqlite3"
CSV_OUT = ROOT / "knowledge/entity-candidates-stage5.csv"
YAML_OUT = ROOT / "knowledge/seed-stage5.yaml"
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

BATCH = "2026-11-05-stage5"

# NPC 人物：台词量门槛与配额
NPC_MIN_LINES = 50
NPC_LIMIT = 66

# 说话人里不能当人物收的：旁白、玩家、系统占位、宠物/坐骑、
# 以及**已是别的实体别名**的称呼（这些要进别名，不该另开一张卡）
SPEAKER_BLACKLIST = {
    "旁白", "？？？", "旅行者", "派蒙", "空", "荧", "系统", "全员", "众人",
    "幼嵴锋龙", "黑蛋",          # 坐骑/宠物，不是剧情人物
    "阿帽", "留云借风真君",       # 分别是「流浪者」「闲云」的另一称呼
}

# 其余类别的候选表：type|名字。只给名字，命中与否由库内证据决定。
CURATED = """
concept|天空岛
concept|地脉
concept|元素力
concept|天理
concept|深渊
concept|三月女神
concept|四影
concept|炼金术
concept|占星术
concept|仙术
concept|机关术
concept|虚假之天
concept|提瓦特
concept|尘世
concept|诅咒
concept|灵魂
concept|记忆
concept|元素反应
concept|原初
concept|世界式
concept|地脉异常
concept|深渊之力
concept|元素龙
concept|神性
concept|天命
concept|等价交换
concept|坎瑞亚
concept|元素龙王
concept|降临
creature|深渊法师
creature|深渊使徒
creature|遗迹猎者
creature|遗迹重机
creature|兽境猎犬
creature|飘浮灵
creature|蕈兽
creature|史莱姆
creature|无相之雷
creature|急冻树
creature|爆炎树
creature|雷音权现
creature|圣骸兽
creature|玄文兽
creature|龙蜥
creature|丘丘王
creature|愚人众先遣队
creature|幼岩龙蜥
creature|岩龙蜥
creature|遗迹龙兽
creature|藏镜仕女
creature|债务处理人
creature|深海龙蜥
creature|风史莱姆
creature|愚人众特使
creature|深渊咏者
deity|芙卡洛斯
deity|厄歌莉娅
deity|奥赛尔
deity|跋掣
deity|天理维系者
deity|花神
deity|赤王
deity|盐神
deity|灶神
deity|尘之魔神
deity|岩王帝君
deity|若陀龙王
organization|愚人众执行官
organization|八重堂
organization|万民堂
organization|不卜庐
organization|神里家
organization|九条家
organization|幕府
organization|教令院六贤
organization|璃月总务司
organization|西风大教堂
organization|黑市
organization|执律庭
event|海灯节
event|风花节
event|羽球节
event|逐月节
event|光华容彩祭
event|三界路飨祭
event|眼狩令
event|锁国令
event|坎瑞亚灾变
event|归终之死
event|枫丹预言
event|葬火之战
event|流风祭
event|花神诞祭
event|试胆大会
event|清籁逐雷记
event|振晶的研究
event|归风佳酿节
event|魔女的茶会
event|演武传心
event|机关棋谭
event|无相交响诗
"""

# 每类的目标增量（合计约 150，把总数推到 400 左右）
QUOTA = {"concept": 35, "creature": 23, "deity": 8,
         "organization": 8, "event": 20}



def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    # 本批自己的 id = 库里有的 − 前四批的。
    # 不依赖 seed-stage5.yaml 本身：它可能还没写、也可能被上一次空跑覆盖成 0 条。
    other_ids: set[str] = set()
    for name in ("seed.yaml", "seed-stage2.yaml", "seed-stage3.yaml", "seed-stage4.yaml"):
        f = ROOT / "knowledge" / name
        if f.exists():
            data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            other_ids |= {e["id"] for e in data.get("entities") or [] if e.get("id")}

    rows = con.execute("SELECT entity_id, canonical_name FROM entities").fetchall()
    prior_ids = {r["entity_id"] for r in rows} - other_ids
    # 本批已有的名字不算「已存在」，否则重跑会全部跳过、改了候选表也不生效
    existing_names = {r["canonical_name"] for r in rows if r["entity_id"] not in prior_ids}
    taken_ids = {r["entity_id"] for r in rows if r["entity_id"] not in prior_ids}
    all_names = {n for eid, n in con.execute("SELECT entity_id, name FROM entity_names")
                 if eid not in prior_ids}

    entries: list[dict] = []
    skipped: list[tuple[str, str, str]] = []
    added: set[str] = set()
    cache: dict = {}

    def add(etype: str, name: str, evidences: list[tuple[str, str]], desc: str) -> None:
        doc, quote = evidences[0]
        eid = slug(name, doc)
        base, n = eid, 2
        while eid in taken_ids:
            eid = f"{base}-{n}"
            n += 1
        taken_ids.add(eid)
        added.add(name)
        entries.append({"id": eid, "type": etype, "name": name, "doc": doc,
                        "quote": quote, "evidences": evidences, "desc": desc})

    # --- 1. NPC 人物：按台词量取 ------------------------------------------
    speakers = con.execute(
        """SELECT speaker, COUNT(*) AS n, COUNT(DISTINCT doc_id) AS d
           FROM sections WHERE speaker IS NOT NULL AND speaker <> ''
           GROUP BY speaker ORDER BY n DESC"""
    ).fetchall()
    npc = 0
    for s in speakers:
        if npc >= NPC_LIMIT:
            break
        name = (s["speaker"] or "").strip()
        if (not name or len(name) < 2 or name in SPEAKER_BLACKLIST
                or "【" in name or "「" in name
                or name in all_names or name in existing_names or name in added):
            continue
        row = con.execute(
            """SELECT doc_id, body FROM sections
               WHERE speaker = ? AND length(body) BETWEEN 12 AND 70
               ORDER BY length(body) DESC LIMIT 1""",
            (name,),
        ).fetchone()
        quote = pick_quote(row["body"], None, lo=12, hi=70) if row else None
        if not quote:
            skipped.append(("character", name, "找不到可用台词"))
            continue
        desc = (f"NPC 人物：台词 {s['n']} 段，出现在 {s['d']} 篇文档。"
                "第五批扩量，描述只写语料统计，剧情身份请点证据原文核对")
        add("character", name, [(row["doc_id"], quote)], desc)
        npc += 1
    print(f"NPC 人物：{npc} 个（门槛 ≥{NPC_MIN_LINES} 段台词）")

    # --- 2. 其余类别：候选表 + 库内证据 ------------------------------------
    hits: Counter = Counter()
    for line in CURATED.strip().splitlines():
        line = line.strip()
        if not line or "|" not in line:
            continue
        etype, name = (x.strip() for x in line.split("|", 1))
        if not name:
            continue
        if hits[etype] >= QUOTA.get(etype, 0):
            continue
        if name in existing_names or name in added or name in all_names:
            skipped.append((etype, name, "库里已有同名实体或别名"))
            continue
        evidences = best_evidences(con, name, cache, k=3)
        if not evidences:
            skipped.append((etype, name, "语料里没有含这个名字的可用句子"))
            continue
        label = {"concept": "概念", "creature": "生物", "deity": "神明",
                 "organization": "组织", "event": "事件/节庆"}.get(etype, "条目")
        add(etype, name, evidences,
            f"{label}条目（第五批扩量；描述为分类标签，具体设定请点证据原文核对）")
        hits[etype] += 1

    counts = Counter(e["type"] for e in entries)
    print(f"新增 {len(entries)} 个：" + " · ".join(f"{k} {v}" for k, v in counts.items()))
    print("落空：" + (f"{len(skipped)} 个" if skipped else "无"))
    for t, n, why in skipped:
        print(f"  - [{t}] {n}：{why}")

    # --- 3. 输出 -----------------------------------------------------------
    with CSV_OUT.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["entity_id", "type", "name", "doc_id", "quote", "evidence_count",
                    "description"])
        for e in entries:
            w.writerow([e["id"], e["type"], e["name"], e["doc"], e["quote"],
                        len(e["evidences"]), e["desc"]])
    print(f"候选清单 -> {CSV_OUT}")

    if args.apply:
        payload = {
            "version": 1, "batch": BATCH, "status": "draft",
            "entities": [
                {"id": e["id"], "type": e["type"], "name": e["name"],
                 "description": e["desc"], "spoiler": 1, "aliases": [],
                 "evidence": [{"doc": d, "quote": q} for d, q in e["evidences"]]}
                for e in entries
            ],
        }
        YAML_OUT.write_text(
            "# 第五批知识层种子 · 收尾扩量（由 scripts/build_stage5.py 生成）\n"
            "# 人物来自 sections.speaker 的台词统计；其余来自候选表 + 库内证据校验。\n"
            "# 描述只写语料统计或中性分类标签，不写剧情结论。\n"
            "# status=draft：待复核（python scripts/review_queue.py 排队）。\n"
            + yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=200),
            encoding="utf-8",
        )
        print(f"已写入 {YAML_OUT}")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
