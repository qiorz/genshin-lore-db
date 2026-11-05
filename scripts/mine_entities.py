#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 corpus/ 的正文段落里为「实体扩量」挖掘带真实出处的候选。

思路（半自动，但证据 100% 来自库）：
  1. 内置一份**候选专名词表**（只提供名字和分类，不提供任何剧情结论）；
  2. 每个词在 `sections` 里找叙事段落证据，按规则打分、过滤攻略/运营噪声；
  3. 模拟 `load_knowledge.resolve` 的定位逻辑，确认短引用确实指回含该名字的段落；
  4. 别名只有在「正名 + 别名」同段共现时才收；
  5. **本批不生成关系**。「证据文档的 region」只说明这句话出现在哪篇文档，
     不等于该实体属于哪个国家，据此推 located_in 会造出错误结论；
  6. 输出候选清单 CSV 供人工复核 + `knowledge/seed-stage3.yaml`。

候选词表只是「待查名字」，词本身有没有资格进库完全由库内证据决定。
描述一律用中性分类标签，不写剧情断言；具体设定请点证据回原文核对。

用法：
    python scripts/mine_entities.py                    # 干跑，打印统计与样例
    python scripts/mine_entities.py --apply --target 70
"""
from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "db/genshin_lore.sqlite3"
SEEDS = sorted((ROOT / "knowledge").glob("seed*.yaml"))
CSV_OUT = ROOT / "knowledge/entity-candidates.csv"
YAML_OUT = ROOT / "knowledge/seed-stage3.yaml"
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

# 格式： type | entity_id | 规范名 | 候选别名（逗号分隔，需同段共现才收）
CANDIDATES = """
character|entity.jean|琴|
character|entity.lisa|丽莎|
character|entity.kaeya|凯亚|
character|entity.amber|安柏|
character|entity.barbara|芭芭拉|
character|entity.razor|雷泽|
character|entity.fischl|菲谢尔|皇女
character|entity.bennett|班尼特|
character|entity.noelle|诺艾尔|
character|entity.diona|迪奥娜|
character|entity.albedo|阿贝多|
character|entity.sucrose|砂糖|
character|entity.mona|莫娜|
character|entity.rosaria|罗莎莉亚|
character|entity.eula|优菈|
character|entity.mika|米卡|
character|entity.varka|法尔伽|
character|entity.xiangling|香菱|
character|entity.xingqiu|行秋|
character|entity.chongyun|重云|
character|entity.ningguang|凝光|
character|entity.beidou|北斗|
character|entity.xinyan|辛焱|
character|entity.keqing|刻晴|
character|entity.qiqi|七七|
character|entity.xiao|魈|护法夜叉大将军
character|entity.yunjin|云堇|
character|entity.yanfei|烟绯|
character|entity.shenhe|申鹤|
character|entity.yaoyao|瑶瑶|
character|entity.baizhu|白术|
character|entity.yelan|夜兰|
character|entity.hutao|胡桃|
character|entity.ganyu|甘雨|
character|entity.xianyun|闲云|
character|entity.gaming|嘉明|
character|entity.ayaka|神里绫华|
character|entity.ayato|神里绫人|
character|entity.yoimiya|宵宫|
character|entity.sayu|早柚|
character|entity.sara|九条裟罗|
character|entity.thoma|托马|
character|entity.gorou|五郎|
character|entity.kokomi|珊瑚宫心海|
character|entity.yae-miko|八重神子|
character|entity.itto|荒泷一斗|
character|entity.kuki|久岐忍|
character|entity.heizou|鹿野院平藏|
character|entity.kirara|绮良良|
character|entity.chiori|千织|
character|entity.raiden-shogun|雷电将军|
character|entity.collei|柯莱|
character|entity.tighnari|提纳里|
character|entity.cyno|赛诺|
character|entity.candace|坎蒂丝|
character|entity.dori|多莉|
character|entity.nilou|妮露|
character|entity.alhaitham|艾尔海森|
character|entity.dehya|迪希雅|
character|entity.kaveh|卡维|
character|entity.faruzan|珐露珊|
character|entity.layla|莱依拉|
character|entity.lyney|林尼|
character|entity.lynette|琳妮特|
character|entity.freminet|菲米尼|
character|entity.neuvillette|那维莱特|
character|entity.charlotte|夏洛蒂|
character|entity.navia|娜维娅|
character|entity.clorinde|克洛琳德|
character|entity.sigewinne|希格雯|
character|entity.emilie|艾梅莉埃|
character|entity.mualani|玛拉妮|
character|entity.kinich|基尼奇|
character|entity.kachina|卡齐娜|
character|entity.xilonen|希诺宁|
character|entity.chasca|恰斯卡|
character|entity.ororon|欧洛伦|
character|entity.mavuika|玛薇卡|
character|entity.varesa|瓦雷莎|
character|entity.iansan|伊安珊|
character|entity.dottore|多托雷|博士
character|entity.pierro|皮耶罗|丑角
character|entity.signora|罗莎琳|女士
character|entity.arlecchino|阿蕾奇诺|仆人
character|entity.enjou|渊上|
character|entity.madame-ping|萍姥姥|
nation|entity.fontaine|枫丹|正义之国
nation|entity.natlan|纳塔|战争之国
nation|entity.nod-krai|挪德卡莱|
location|entity.mondstadt-city|蒙德城|
location|entity.dawn-winery|晨曦酒庄|
location|entity.dragonspine|龙脊雪山|
location|entity.windrise|风起地|
location|entity.starsnatch-cliff|摘星崖|
location|entity.thousand-winds-temple|千风神殿|
location|entity.liyue-harbor|璃月港|
location|entity.jueyun-karst|绝云间|
location|entity.qingce-village|轻策庄|
location|entity.chasm|层岩巨渊|
location|entity.wangshu-inn|望舒客栈|
location|entity.jade-chamber|群玉阁|
location|entity.golden-house|黄金屋|
location|entity.guili-plains|归离原|
location|entity.inazuma-city|稻妻城|
location|entity.grand-narukami-shrine|鸣神大社|
location|entity.ritou|离岛|
location|entity.tatarasuna|踏鞴砂|
location|entity.tsurumi-island|鹤观|
location|entity.seirai-island|清籁岛|
location|entity.watatsumi-island|海祇岛|
location|entity.enkanomiya|渊下宫|
location|entity.yashiori-island|八酝岛|
location|entity.sumeru-city|须弥城|
location|entity.aaru-village|阿如村|
location|entity.port-ormos|奥摩斯港|
location|entity.vanarana|桓那兰那|
location|entity.caravan-ribhad|喀万驿|
location|entity.fontaine-city|枫丹廷|
location|entity.opera-epiclese|欧庇克莱歌剧院|
location|entity.fortress-of-meropide|梅洛彼得堡|
location|entity.poisson|白淞镇|
location|entity.celestia|天空岛|
location|entity.sumeru-desert|须弥沙漠|
organization|entity.adventurers-guild|冒险家协会|
organization|entity.church-of-favonius|西风教会|
organization|entity.treasure-hoarders|盗宝团|
organization|entity.eremites|镀金旅团|
organization|entity.qixing|璃月七星|
organization|entity.millelith|千岩军|
organization|entity.yashiro-commission|社奉行|
organization|entity.tenryou-commission|天领奉行|
organization|entity.house-of-hearth|壁炉之家|
organization|entity.thirty-men|三十人团|
organization|entity.crux|死兆星号|
organization|entity.sangonomiya|珊瑚宫|
concept|entity.delusion|邪眼|
concept|entity.constellation|命之座|
concept|entity.leyline|地脉|
concept|entity.forbidden-knowledge|禁忌知识|
concept|entity.archon-residue|魔神残渣|
concept|entity.seelie|仙灵|
concept|entity.ruin-guard|遗迹守卫|
concept|entity.abyss-mage|深渊法师|
concept|entity.adepti|仙人|
concept|entity.adeptal-energy|仙力|
concept|entity.loom-of-fate|命运的织机|
concept|entity.heavenly-principles|天理|
concept|entity.sustainer|天理的维系者|
concept|entity.descender|降临者|
concept|entity.archon-war-concept|魔神战争|
concept|entity.serenitea-pot|尘歌壶|
concept|entity.spiral-abyss|深境螺旋|
concept|entity.genius-invokation|七圣召唤|
concept|entity.scarlet-king|赤王|
concept|entity.goddess-of-flowers|花神|
concept|entity.eternity|永恒|
creature|entity.azhdaha|若陀龙王|
creature|entity.apep|阿佩普|
creature|entity.hilichurl|丘丘人|
creature|entity.aranara|兰那罗|
creature|entity.slime|史莱姆|
creature|entity.fungus|蕈兽|
creature|entity.whopperflower|骗骗花|
creature|entity.crystalfly|晶蝶|
creature|entity.oceanid|纯水精灵|
creature|entity.thunder-manifestation|雷音权现|
creature|entity.bathysmal-vishap|深海龙蜥|
creature|entity.rifthound|兽境猎犬|
"""

# 攻略 / 运营 / 数值类噪声，命中即扣分（不是完全排除，避免误杀叙事里的正常词）
NOISE = ("原石", "兑换码", "活动时间", "祈愿", "攻击力", "生命值", "暴击率",
         "暴击伤害", "元素充能", "充值", "礼包", "概率提升", "食谱", "配方",
         "合成材料", "突破材料", "精炼等级", "UID", "维护补偿", "下载", "更新包",
         "♪", "◆", "※", "关卡奖励", "满级", "伤害加成")
DOC_SCORE = {"quest": 2, "book": 3, "character": 3, "lore": 3, "voice": 2,
             "geography": 2, "item": 0, "weapon": -1, "artifact": -1,
             "event": -1, "notice": -3}
# 目录 / 舞台提示 / 过场标记不是叙事正文
STAGE_MARKERS = ("过场动画", "（初遇", "任务信息", "剧情梗概", "幕 第")
TYPE_LABEL = {"character": "人物", "deity": "神明", "nation": "国度",
              "organization": "组织", "location": "地点", "concept": "设定/概念",
              "creature": "非人存在", "item": "物品", "title": "称号",
              "event": "事件", "other": "条目"}
REGION_ENTITY = {"蒙德": "entity.mondstadt", "璃月": "entity.liyue",
                 "稻妻": "entity.inazuma", "须弥": "entity.sumeru",
                 "至冬": "entity.snezhnaya", "枫丹": "entity.fontaine",
                 "纳塔": "entity.natlan"}
# 各类型的目标配额，合计 70；不足的名额按分数补给其它类型
QUOTA = {"character": 30, "location": 16, "concept": 11,
         "organization": 6, "creature": 5, "nation": 2}


def norm(text: str) -> str:
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", text or "")


def clean_quote(body: str, width: int = 76) -> str:
    t = re.sub(r"<[^>]+>", "", body or "")
    t = re.sub(r"\*\*|\*|`", "", t)
    t = re.sub(r"^\s*[-#>]\s*", "", t.strip())
    t = re.sub(r"\s+", " ", t).strip()
    return t[:width]


def parse_candidates() -> list[dict]:
    rows = []
    for order, line in enumerate(CANDIDATES.strip().splitlines()):
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3 or not parts[1] or not parts[2]:
            continue
        rows.append({
            "type": parts[0], "id": parts[1], "name": parts[2], "order": order,
            "aliases": [a for a in (parts[3] if len(parts) > 3 else "").split(",") if a],
        })
    return rows


def score_row(row, name: str) -> float:
    doc_id, ordinal, stype, body, doc_type, region, title = row
    score = DOC_SCORE.get(doc_type, 0)
    score += 2 if stype in ("dialogue", "quote") else (1 if stype == "text" else 0)
    n = len(body or "")
    if 30 <= n <= 160:
        score += 2
    elif n < 22 or n > 230:
        score -= 2
    score -= 3 * sum(1 for w in NOISE if w in (body or ""))
    score -= 6 * sum(1 for w in STAGE_MARKERS if w in (body or ""))
    # 名字出现在段落前半，通常是介绍性句子，证据质量更好
    pos = (body or "").find(name)
    if 0 <= pos <= 30:
        score += 1
    return float(score)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", type=int, default=70, help="本批新增实体数")
    ap.add_argument("--apply", action="store_true", help="写出 CSV 与 seed-stage3.yaml")
    args = ap.parse_args()

    # 已有名字（规范名 + 别名）用于排除重复
    existing: set[str] = set()
    for seed_path in SEEDS:
        if seed_path.name == "seed-stage3.yaml":
            continue
        data = yaml.safe_load(seed_path.read_text(encoding="utf-8")) or {}
        for e in data.get("entities") or []:
            existing.add(e["name"])
            existing.update(a["name"] for a in e.get("aliases") or [])

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    section_cache: dict[str, list] = {}

    def resolve_check(doc_id: str, quote: str):
        if doc_id not in section_cache:
            section_cache[doc_id] = con.execute(
                "SELECT ordinal, body FROM sections WHERE doc_id=? ORDER BY ordinal",
                (doc_id,),
            ).fetchall()
        target = norm(quote)[:14]
        for ordinal, body in section_cache[doc_id]:
            if target and target in norm(body or ""):
                return ordinal, body or ""
        return None

    found: list[dict] = []
    all_rows: list[dict] = []
    candidates = parse_candidates()
    for cand in candidates:
        name = cand["name"]
        if name in existing or "?" in cand["id"] or " " in cand["id"]:
            all_rows.append({**cand, "matched": 0, "score": "", "doc_id": "",
                             "reason": "已收录或 ID 非法"})
            continue
        if len(name) < 2:
            all_rows.append({**cand, "matched": 0, "score": "", "doc_id": "",
                             "reason": "单字候选易被普通词误命中，跳过"})
            continue
        rows = con.execute(
            """SELECT s.doc_id, s.ordinal, s.section_type, s.body,
                      d.doc_type, d.region, d.title
               FROM sections s JOIN documents d ON d.doc_id=s.doc_id
               WHERE s.body LIKE ? AND s.section_type IN ('dialogue','quote','text')
                 AND length(s.body) BETWEEN 18 AND 260
               LIMIT 200""",
            (f"%{name}%",),
        ).fetchall()
        # 每篇文档最多留 2 条候选，避免所有证据都挤在同一篇任务里
        per_doc: dict[str, list] = defaultdict(list)
        for row in rows:
            per_doc[row["doc_id"]].append(row)
        spread = []
        for group in per_doc.values():
            group.sort(key=lambda r: score_row(r, name), reverse=True)
            spread.extend(group[:2])
        ranked = sorted(spread, key=lambda r: score_row(r, name), reverse=True)
        picked = None
        for row in ranked:
            quote = clean_quote(row["body"])
            hit = resolve_check(row["doc_id"], quote)
            if hit and name in hit[1]:
                picked = {"doc": row["doc_id"], "quote": quote,
                          "doc_type": row["doc_type"], "region": row["region"] or "",
                          "score": score_row(row, name), "ordinal": hit[0]}
                break
        if not picked:
            all_rows.append({**cand, "matched": 0, "score": "", "doc_id": "",
                             "reason": "无叙事证据或短引用定位失败"})
            continue
        aliases = []
        for alias in cand["aliases"]:
            pair = con.execute(
                """SELECT 1 FROM sections WHERE body LIKE ? AND body LIKE ?
                   AND length(body) BETWEEN 15 AND 260 LIMIT 1""",
                (f"%{name}%", f"%{alias}%"),
            ).fetchone()
            if pair:
                aliases.append({"name": alias, "kind": "alias"})
        # 词表顺序体现重要性（经典角色在前），给一个不超过 2 分的温和加权，
        # 不改变「证据质量优先」的大方向，但避免琴/丽莎被轮询挤到备选。
        bonus = 2.0 * (1 - cand["order"] / max(1, len(candidates)))
        cand.update({"matched": 1, "score": picked["score"], "doc_id": picked["doc"],
                     "rank": picked["score"] + bonus,
                     "reason": "", "evidence": picked, "aliases": aliases})
        found.append(cand)
        all_rows.append(cand)

    # 按类型配额 + 组内「地区轮询」，避免 30 个角色全挤在蒙德/璃月
    by_type: dict[str, list] = defaultdict(list)
    for c in found:
        by_type[c["type"]].append(c)
    for group in by_type.values():
        group.sort(key=lambda c: (-c["rank"], c["id"]))

    def region_round_robin(group: list, quota: int) -> list:
        by_region: dict[str, list] = defaultdict(list)
        for c in group:
            by_region[c["evidence"]["region"] or "未标注"].append(c)
        keys = sorted(by_region)
        out = []
        while len(out) < quota and any(by_region[k] for k in keys):
            for k in keys:
                if by_region[k] and len(out) < quota:
                    out.append(by_region[k].pop(0))
        return out

    chosen: list[dict] = []
    forced_ids = {"entity.fontaine", "entity.natlan"}
    chosen.extend([c for c in found if c["id"] in forced_ids])
    used = {c["id"] for c in chosen}
    for typ, quota in QUOTA.items():
        for c in region_round_robin(
                [x for x in by_type.get(typ, []) if x["id"] not in used], quota):
            chosen.append(c)
            used.add(c["id"])
    # 名额不足时按分数补齐
    if len(chosen) < args.target:
        rest = sorted((c for c in found if c["id"] not in used),
                      key=lambda c: (-c["rank"], c["id"]))
        chosen.extend(rest[:args.target - len(chosen)])
    else:
        chosen = chosen[:args.target]
    chosen.sort(key=lambda c: (c["type"], c["id"]))

    for c in all_rows:
        c["chosen"] = 1 if c.get("matched") and c["id"] in {x["id"] for x in chosen} else 0

    # --- 输出候选 CSV -------------------------------------------------------
    fields = ["id", "name", "type", "matched", "chosen", "score", "doc_id",
              "doc_type", "region", "aliases", "quote", "reason"]
    csv_rows = []
    for c in all_rows:
        ev = c.get("evidence") or {}
        csv_rows.append({
            "id": c["id"], "name": c["name"], "type": c["type"],
            "matched": c["matched"], "chosen": c["chosen"],
            "score": c["score"], "doc_id": c["doc_id"],
            "doc_type": ev.get("doc_type", ""), "region": ev.get("region", ""),
            "aliases": ",".join(a["name"] if isinstance(a, dict) else a
                                for a in c.get("aliases") or []),
            "quote": ev.get("quote", ""), "reason": c.get("reason", ""),
        })

    # --- 生成 seed-stage3.yaml（本批只加实体，不自动生成关系）----------------
    # 不用「证据文档的 region」推归属：那只是「这句话出现在哪篇文档」，
    # 不等于「这个实体属于哪国」，会造出「神里绫华 located_in 须弥」这类错误。
    entities_yaml = []
    for c in chosen:
        ev = c["evidence"]
        region = ev["region"]
        label = TYPE_LABEL.get(c["type"], "条目")
        # 不再写「证据出自{region}地区文档」：话虽属实，但读起来像在说
        # 「这个实体属于该地区」——枫丹的证据恰好出自一篇纳塔文档，会误导。
        # 地区信息保留在证据链接里，描述只留分类标签。
        desc = f"{label}条目（第三批扩量；描述为分类标签，具体设定请点证据原文核对）"
        entities_yaml.append({
            "id": c["id"], "type": c["type"], "name": c["name"],
            "description": desc, "spoiler": 1,
            "aliases": c["aliases"],
            "evidence": [{"doc": ev["doc"], "quote": ev["quote"]}],
        })

    payload = {
        "version": 1, "batch": "2026-11-05-stage3", "status": "draft",
        "entities": entities_yaml,
    }

    print(f"候选词 {len(all_rows)} · 有叙事证据 {len(found)} · 本批入选 {len(chosen)} · "
          f"本批不生成关系")
    print("按类型：" + "、".join(
        f"{k} {sum(1 for c in chosen if c['type'] == k)}" for k in QUOTA))
    print("证据文档类型：" + "、".join(
        f"{k} {sum(1 for c in chosen if c['evidence']['doc_type'] == k)}"
        for k in sorted({c["evidence"]["doc_type"] for c in chosen})))
    print("\n入选样例（前 12）：")
    for c in chosen[:12]:
        print(f"  {c['name']:8} [{c['type']:12}] {c['evidence']['doc']:22} "
              f"| {c['evidence']['quote'][:44]}")
    print("\n未入选但有证据（前 8，留作下次扩量）：")
    extra = [c for c in found if c["id"] not in {x["id"] for x in chosen}]
    for c in extra[:8]:
        print(f"  {c['name']:8} [{c['type']:12}] score={c['score']:.0f} {c['doc_id']}")

    if args.apply:
        CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
        with CSV_OUT.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(csv_rows)
        YAML_OUT.write_text(
            "# 第三批知识层种子 · 实体扩量（由 scripts/mine_entities.py 生成）\n"
            "# 候选名字来自词表，但每条证据都来自 corpus/ 中真实存在的叙事段落。\n"
            "# 描述只是中性分类标签，不是剧情结论；具体设定请点出处核对。\n"
            "# status=draft：本批为半自动扩量，待人工抽样复核后再标 reviewed。\n"
            + yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=1000),
            encoding="utf-8", newline="\n")
        print(f"\n写出：{CSV_OUT.relative_to(ROOT)}、{YAML_OUT.relative_to(ROOT)}")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
