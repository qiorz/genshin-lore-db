#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四批：把实体从 100 扩到约 250（角色收全 + 地点/组织补齐）。

与第三批的区别（第三批是「挖候选」，这批是「收权威名单」）：

  1. **角色不再猜**。`documents` 里 `doc_type='character'` 的 136 篇角色页就是权威名单，
     一篇对应一个角色；只做三件事：同名去重、跳过「旅行者·元素」变体（属于同一个实体）、
     跳过库里已有的名字（比如温迪已经是 deity）。
  2. **地点/组织走候选表 + 库内校验**。候选表只提供名字，收不收由「库里有没有真实句子」决定；
     找不到就列进 skipped，绝不硬塞。候选表不写任何剧情结论。
  3. **描述只用结构化事实**。角色用 `manifests/character-index.csv` 里的
     地区/元素/武器/星级（游戏内标注，不是推测），其余一律中性分类标签。
  4. 仍然**不生成关系**。证据文档的 region 只说明这句话出自哪篇，不等于归属。

证据取自实体自己那一篇/那句话的原文，`doc_id + 短引用` 现场解析，抗 corpus 重导。

用法：
    python scripts/build_stage4.py            # 干跑：打印统计、命中/落空清单
    python scripts/build_stage4.py --apply    # 写 knowledge/seed-stage4.yaml
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

try:  # 可选依赖：只用来根据中文名生成稳定 entity_id
    from pypinyin import lazy_pinyin
except ImportError:  # pragma: no cover
    lazy_pinyin = None

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "db/genshin_lore.sqlite3"
CHAR_INDEX = ROOT / "manifests/character-index.csv"
CSV_OUT = ROOT / "knowledge/entity-candidates-stage4.csv"
YAML_OUT = ROOT / "knowledge/seed-stage4.yaml"
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

# 文档类型权重：叙事文本优先，攻略/运营噪声靠后
DOC_SCORE = {"quest": 3, "book": 3, "character": 3, "lore": 3,
             "geography": 2, "event": 2, "voice": 1,
             "artifact": -2, "weapon": -2, "item": -2, "notice": -3}

# 候选表：只给名字和分类，不给结论。命中与否由库内证据决定。
CURATED = """
location|蒙德城
location|风起地
location|星落湖
location|达达乌帕谷
location|奔狼领
location|摘星崖
location|风龙废墟
location|望风山地
location|璃月港
location|归离原
location|荻花洲
location|天衡山
location|层岩巨渊
location|群玉阁
location|无妄坡
location|渌华池
location|孤云阁
location|华光林
location|庆云顶
location|碧水原
location|灵矩关
location|鸣神岛
location|影向山
location|珊瑚宫
location|海祇岛
location|鹤观
location|清籁岛
location|神无冢
location|八酝岛
location|花见坂
location|天守阁
location|踏鞴砂
location|绀田村
location|木漏茶室
location|天云峠
location|净善宫
location|桓那兰那
location|化城郭
location|赤王陵
location|卡萨扎莱宫
location|缄默之殿
location|露景泉
location|佩特莉可镇
location|圣火竞技场
location|挪德卡莱
location|希汐岛
organization|天领奉行
organization|勘定奉行
organization|南十字船队
organization|千岩军
organization|冒险家协会
organization|盗宝团
organization|枫丹科学院
organization|蒸汽鸟报
organization|特巡队
organization|回声之子
organization|流泉之众
organization|花羽会
organization|悬木人
organization|沃陆之邦
organization|烟谜主
organization|执灯士
"""

SENT_END = set("。！？!?；\n")
OPEN_Q, CLOSE_Q = "「『（(《", "」』）)》"
TRIM = " \t\u3000*#>—-[]"


def norm(text: str) -> str:
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", text or "")


def clean(text: str) -> str:
    """去掉 Markdown 标记与首尾空白，避免把 `*「…` 这种带进证据。"""
    return (text or "").strip().strip(TRIM).strip()


def sentences(body: str) -> list[str]:
    """按句号切句，但不切断「」『』括号里的引文。

    直接 re.split 会把「…。」——某人 切成两半，导致证据以 `」` 开头。
    """
    out, buf, depth = [], [], 0
    for ch in (body or "").replace("\r", ""):
        if ch in OPEN_Q:
            depth += 1
        elif ch in CLOSE_Q:
            depth = max(0, depth - 1)
        if ch in SENT_END and depth == 0:
            seg = clean("".join(buf))
            if seg:
                out.append(seg)
            buf = []
            continue
        buf.append(ch)
    seg = clean("".join(buf))
    if seg:
        out.append(seg)
    return out


def slug(name: str, doc_id: str) -> str:
    """中文名 → 稳定 ASCII id；没有 pypinyin 时退回文档号。"""
    if lazy_pinyin is None:
        return "entity." + doc_id.replace(".", "-")
    parts = [p for p in lazy_pinyin(name) if p.isalpha() or p.isdigit()]
    s = "-".join(p.lower() for p in parts)
    return "entity." + (s or doc_id.replace(".", "-"))


# 舞台指示、攻略旁白这类句子不是证据，直接排除
NOISE_MARKS = ("过场动画", "（可选）", "点击", "待更新", "见下方", "如上", "如下图",
               "时说的话", "版本前瞻", "（展开", "（点击")


def is_clean_quote(s: str) -> bool:
    if any(m in s for m in NOISE_MARKS):
        return False
    if s.startswith(("▌", "【")):      # 版式标题行（「▌空月归乡 · 哥伦比娅…」）
        return False
    if s.endswith(("：", ":")):        # 引出下文的提示句，本身不含信息
        return False
    han = sum(1 for ch in s if "\u4e00" <= ch <= "\u9fff")
    return han >= 8 and han / max(len(s), 1) >= 0.55


def pick_quote(body: str, name: str | None = None,
               lo: int = 12, hi: int = 70) -> str | None:
    """取一句长度适中、像人话的原话；给了 name 就要求句子里确实出现该名字。"""
    cands = [s for s in sentences(body) if lo <= len(s) <= hi and is_clean_quote(s)]
    if name:
        cands = [s for s in cands if name in s]
    return cands[0] if cands else None


def load_char_index() -> dict[str, dict]:
    if not CHAR_INDEX.exists():
        return {}
    out = {}
    with CHAR_INDEX.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            out[row["title"]] = row
    return out


def char_description(name: str, meta: dict) -> str:
    bits = [meta.get("region") or "", meta.get("element") or "",
            meta.get("weapon") or "", meta.get("star") or ""]
    bits = [b for b in bits if b]
    tag = " · ".join(bits)
    head = f"角色页标注：{tag}。" if tag else "角色页收录。"
    return head + "第四批扩量，描述只取游戏内标注，剧情设定请点证据原文核对"


def best_evidence(con, name: str, cache: dict) -> tuple[str, str, int] | None:
    """在语料里找最能说明「这个名字真实存在」的一篇 + 一句话。"""
    if name in cache:
        return cache[name]
    rows = con.execute(
        """SELECT s.doc_id, d.doc_type, d.title, s.body
           FROM sections s JOIN documents d ON d.doc_id = s.doc_id
           WHERE s.body LIKE ?""",
        (f"%{name}%",),
    ).fetchall()
    best = None
    for doc_id, doc_type, title, body in rows:
        score = DOC_SCORE.get(doc_type, 0)
        if name in (title or ""):
            score += 2                      # 整篇就在讲它，比顺带一提强
        quote = pick_quote(body, name, lo=14, hi=80)
        if not quote:
            continue
        # 名字出现在句首=当主语用；出现在「的」前面多半只是形容词（「枫丹的密码盘」）
        head_bonus = 1 if quote.startswith(name) or quote.find(name) <= 4 else 0
        key = (score + head_bonus, -len(quote))
        if best is None or key > best[2]:
            best = (doc_id, quote, key)
    cache[name] = best
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="写 seed-stage4.yaml")
    args = ap.parse_args()

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    # 本批已生成过的 id 要排除在「库里已有」之外，否则重跑会全部跳过、
    # 也无法修正上一版的分类错误。做法：读上一次的 seed-stage4.yaml 拿 id 白名单。
    prior_ids: set[str] = set()
    if YAML_OUT.exists():
        prev = yaml.safe_load(YAML_OUT.read_text(encoding="utf-8")) or {}
        prior_ids = {e["id"] for e in prev.get("entities") or [] if e.get("id")}

    rows = con.execute("SELECT entity_id, canonical_name FROM entities").fetchall()
    existing = {r["canonical_name"] for r in rows if r["entity_id"] not in prior_ids}
    taken_ids = {r["entity_id"] for r in rows if r["entity_id"] not in prior_ids}
    meta = load_char_index()

    entries: list[dict] = []
    skipped: list[tuple[str, str, str]] = []
    cache: dict = {}
    added_names: set[str] = set()

    # --- 1. 角色：以角色页为权威名单 ---------------------------------------
    seen_names: set[str] = set()
    for row in con.execute(
        "SELECT doc_id, title, region FROM documents WHERE doc_type='character' ORDER BY doc_id"
    ):
        name = (row["title"] or "").strip()
        if not name or "·" in name:          # 旅行者·火 这类元素变体并入 entity.traveler
            continue
        if name in seen_names or name in existing:
            continue
        seen_names.add(name)
        quote = None
        for sec in con.execute(
            "SELECT body FROM sections WHERE doc_id=? ORDER BY ordinal", (row["doc_id"],)
        ):
            quote = pick_quote(sec["body"] or "", name, lo=10, hi=80)
            if quote:
                break
        if not quote:
            skipped.append(("character", name, "角色页里找不到含名字的可用原句"))
            continue
        added_names.add(name)
        entries.append({
            "type": "character", "name": name, "doc": row["doc_id"], "quote": quote,
            "desc": char_description(name, meta.get(name, {})),
        })

    # --- 2. 地点 / 组织：候选表 + 库内证据 ---------------------------------
    for line in CURATED.strip().splitlines():
        etype, name = line.split("|", 1)
        name = name.strip()
        if name in existing or name in added_names:
            skipped.append((etype, name, "库里已有同名实体" if name in existing else "候选表内重名，保留首次出现的分类"))
            continue
        hit = best_evidence(con, name, cache)
        if not hit:
            skipped.append((etype, name, "语料里没有含这个名字的段落"))
            continue
        doc_id, quote, _key = hit
        label = "地点" if etype == "location" else "组织"
        added_names.add(name)
        entries.append({
            "type": etype, "name": name, "doc": doc_id, "quote": quote,
            "desc": f"{label}条目。第四批扩量，描述为分类标签，具体设定请点证据原文核对",
        })

    # --- 3. 生成 id 并去重 -------------------------------------------------
    for e in entries:
        eid = slug(e["name"], e["doc"])
        base, n = eid, 2
        while eid in taken_ids:
            eid = f"{base}-{n}"
            n += 1
        taken_ids.add(eid)
        e["id"] = eid

    counts = Counter(e["type"] for e in entries)
    print(f"新增 {len(entries)} 个实体：" + " · ".join(f"{k} {v}" for k, v in counts.items()))
    print(f"跳过 {len(skipped)} 个：")
    for t, n, why in skipped:
        print(f"  - [{t}] {n}：{why}")
    print("\n样例：")
    for e in entries[-6:]:
        print(f"  {e['id']} | {e['name']} | {e['doc']} | {e['quote'][:32]}")

    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    with CSV_OUT.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["entity_id", "type", "name", "doc_id", "quote", "description"])
        for e in entries:
            w.writerow([e["id"], e["type"], e["name"], e["doc"], e["quote"], e["desc"]])
    print(f"\n候选清单 -> {CSV_OUT}")

    if args.apply:
        payload = {
            "version": 1,
            "batch": "2026-11-05-stage4",
            "status": "draft",
            "entities": [
                {
                    "id": e["id"], "type": e["type"], "name": e["name"],
                    "description": e["desc"], "spoiler": 1, "aliases": [],
                    "evidence": [{"doc": e["doc"], "quote": e["quote"]}],
                }
                for e in entries
            ],
        }
        YAML_OUT.write_text(
            "# 第四批知识层种子 · 角色收全 + 地点/组织补齐（由 scripts/build_stage4.py 生成）\n"
            "# 角色名单来自 corpus 的 136 篇角色页；地点/组织来自候选表，命中与否由库内证据决定。\n"
            "# 描述只用游戏内标注或中性分类标签，不写剧情结论；具体设定请点证据原文核对。\n"
            "# status=draft：待人工抽样复核后再标 reviewed。\n"
            + yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=200),
            encoding="utf-8",
        )
        print(f"已写入 {YAML_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
