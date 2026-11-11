#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 knowledge/curated-facts.yaml 的结论落成关系边与别名。

分工：
  - curated-facts.yaml 写「结论」（谁属于谁、谁叫什么别名）；
  - 本脚本负责**找出处**：在正文里找一句同时含两个名字的话，
    按句式硬度打分，够硬才写，不够硬就列出来让人补。

为什么分开：结论是人的判断（而且比机器准），出处是可验证的事实。
两者混在一起写，就会出现「先有结论、再凑证据」。

写出的东西：
  - knowledge/seed-stage8.yaml   relations（id 8000 段，按排序位置分配）
  - 实体所在 seed 的 aliases     （别名写回实体本身，与 apply_aliases.py 一致）

用法：
    python scripts/apply_curated.py            # 干跑，打印每条的证据与得分
    python scripts/apply_curated.py --apply    # 写文件
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_stage4 import sentences  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "db/genshin_lore.sqlite3"
FACTS = ROOT / "knowledge/curated-facts.yaml"
OUT = ROOT / "knowledge/seed-stage8.yaml"
OUT_ALIAS = ROOT / "knowledge/seed-stage9.yaml"
SEEDS = sorted((ROOT / "knowledge").glob("seed*.yaml"))
APPLY = "--apply" in sys.argv
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

REL_BASE = 8000        # 本批关系 id 起点
MIN_SCORE = 1.8        # 低于这个分数视为「没有可用出处」，不写入

PRED_LABELS = {
    "located_in": "位于", "based_in": "根据地在",
    "held_in": "举办于", "occurred_in": "发生于", "issued_in": "颁布于",
}


def score_sentence(s: str, a: str, b: str, predicate: str) -> float:
    """一句话能多硬地证明「a --predicate--> b」。0 表示不算证据。"""
    # 名字互为子串时（璃月港 / 璃月、蒙德城 / 蒙德），字面上永远「共现」，
    # 但那只是包含关系，不能当归属证据。这类只能走同篇兜底。
    if a in b or b in a:
        return 0.0
    ea, eb = re.escape(a), re.escape(b)
    hard = {
        "located_in": [rf"{ea}(?:位于|地处|坐落在|坐落于){eb}",
                       rf"{eb}(?:境内|内|的){ea}"],
        "based_in": [rf"{ea}(?:的总部)?(?:位于|设在|坐落于|成立于|隶属于){eb}"],
        "held_in": [rf"{ea}(?:在|于){eb}(?:举办|举行)",
                    rf"{eb}(?:举办|举行)的?{ea}"],
        "occurred_in": [rf"{ea}(?:发生在|发生于|爆发于|起源于){eb}"],
        "issued_in": [rf"{ea}(?:由|是){eb}(?:颁布|下达|推行)"],
    }.get(predicate, [])
    for pat in hard:
        if re.search(pat, s):
            return 4.0
    # 「X的Y」：地点/事件很硬（璃月的轻策庄、稻妻的锁国令），
    # 组织要弱一档——「蒙德的愚人众」说的是地盘，不是归属。
    if re.search(rf"{eb}的{ea}", s):
        return 3.0 if predicate in ("located_in", "held_in", "occurred_in",
                                    "issued_in") else 2.6
    if re.search(rf"{eb}(?:境内|内|地区)的?{ea}", s):
        return 3.5
    # 人物↔人物：句子里必须出现对应的亲属/师徒/从属词，方向由 facts 里写定。
    # 光共现不算——「提纳里的老师骂居勒什」两人都在句里，但它不说明任何关系。
    KIN = {
        "sibling_of": "妹妹|姐姐|哥哥|弟弟|义弟|义兄|义妹|义姐|兄长|胞弟|胞妹",
        "child_of": "女儿|儿子|母亲|父亲|养子|养女",
        "student_of": "弟子|学生|徒弟|师父|老师|师傅",
        "subordinate_to": "部下|属下|家臣|效忠|侍奉|主君|麾下",
    }.get(predicate)
    if KIN and re.search(KIN, s):
        return 3.5
    # 只挨得近，没有任何归属词：能证明「被一起提到」，不能证明归属
    if near(s, a, b, 8):
        return 2.2
    if near(s, a, b, 20):
        return 1.6
    return 0.0


def usable(s: str, a: str) -> bool:
    """这句能不能当证据拿去展示。

    语料里有大量版式行：「璃月 天衡山」「【璃月总务司公告】」「蒙德观光指南·风起地」，
    它们是索引/标题，不是叙述。拿它们当出处，页面上等于没有证据。
    """
    s = s.strip()
    if len(s) < 10 or s == a:
        return False
    if s.startswith(("编者注", "根据指引", "前往", "※", "*")):
        return False
    if "编者注" in s or "获取方式" in s:
        return False
    # 无标点、无引号的短行 = 标题（与 build_stage4.looks_like_heading 同一判据）
    if len(s) < 30 and not any(ch in s for ch in "。！？…，、；：「」『』"):
        return False
    return True


def near(s: str, a: str, b: str, gap: int) -> bool:
    """两个名字相邻出现。**重叠不算** —— 「璃月港」里含「璃月」，
    那不是共现，只是子串；按共现处理会得到「璃月港位于璃月」这种空证据。
    """
    pa = [(m.start(), m.end()) for m in re.finditer(re.escape(a), s)]
    pb = [(m.start(), m.end()) for m in re.finditer(re.escape(b), s)]
    for i0, i1 in pa:
        for j0, j1 in pb:
            if i0 < j1 and j0 < i1:
                continue
            dist = (j0 - i1) if j0 >= i1 else (i0 - j1)
            if dist <= gap:
                return True
    return False


def main() -> int:
    facts = yaml.safe_load(FACTS.read_text(encoding="utf-8")) or {}
    rel_facts = facts.get("relations") or []
    alias_facts = facts.get("aliases") or []
    drop_aliases = facts.get("drop_aliases") or []

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    ents = {r["canonical_name"]: dict(r) for r in
            con.execute("SELECT entity_id, canonical_name, entity_type FROM entities")}
    etype = {v["entity_id"]: v["entity_type"] for v in ents.values()}

    # 已有关系：不重复写。**必须排除本脚本自己的产物** ——
    # 否则第二次运行会把上一版的 107 条全判成「已有」，生成空文件（踩过一次）。
    existing = set()
    existing_pairs = set()
    GEO_PREDS = {"located_in", "based_in", "held_in", "occurred_in", "issued_in"}
    for path in SEEDS:
        if path == OUT:
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for r in data.get("relations") or []:
            existing.add((r["subject"], r["predicate"], r.get("object_id")))
            if r["predicate"] in GEO_PREDS and r.get("object_id"):
                # 同一对实体只留一条归属边：stage6 已经把「西风骑士团→蒙德」
                # 记成 located_in，这批再加 based_in 就会在页面上出现两条。
                existing_pairs.add((r["subject"], r.get("object_id")))

    # ---- 1. 逐条找证据 ----------------------------------------------------
    picked: list[dict] = []
    missing: list[str] = []
    errors: list[str] = []

    cache: dict[tuple[str, str], list[tuple[str, float, str, str]]] = {}

    def evidence_for(a: str, b: str, predicate: str) -> tuple[str, float, str, str] | None:
        """返回 (doc_id, score, quote, doc_type)，取不到返回 None。"""
        key = (a, b)
        if key not in cache:
            rows = con.execute(
                """SELECT s.doc_id, d.doc_type, s.body FROM sections s
                   JOIN documents d ON d.doc_id = s.doc_id
                   WHERE s.body LIKE ? AND s.body LIKE ?""",
                (f"%{a}%", f"%{b}%"),
            ).fetchall()
            cands = []
            for row in rows:
                best = (0.0, "")
                for s in sentences(row["body"] or ""):
                    if a not in s or b not in s or not usable(s, a):
                        continue
                    sc = score_sentence(s, a, b, predicate)
                    if sc > best[0]:
                        best = (sc, s)
                if best[0] > 0:
                    cands.append((row["doc_id"], best[0], best[1], row["doc_type"]))
            cache[key] = cands
        cands = cache[key]
        if not cands:
            return None
        # 叙事文本优先于公告；同分取分高、再取短句
        cands = sorted(cands, key=lambda x: (x[3] == "notice", -x[1], len(x[2])))
        return cands[0]

    def document_fallback(a: str, b: str) -> tuple[str, float, str, str] | None:
        """同句找不到时，退一步用「同篇」——但必须目标国在同篇里排第一且领先。

        `星落湖` 这类地点在原文里出现 18 段，却没有一句同时写「蒙德」，
        因为叙事不需要每句都重复国名。同篇证据弱一档，所以：
          - 只在同篇提及其它国家都不多于目标国时才用；
          - 打 1.5 分（低于 MIN_SCORE），由调用方显式接受并标 likely；
          - notes 里必须写明「同篇提及，非同一句」。
        """
        docs = {r[0] for r in con.execute(
            "SELECT DISTINCT doc_id FROM sections WHERE body LIKE ?", (f"%{a}%",))}
        if not docs:
            return None
        tally: dict[str, int] = {}
        for nat in ents:
            if ents[nat]["entity_type"] != "nation" or nat == b:
                continue
            n = sum(1 for d in docs if con.execute(
                "SELECT 1 FROM sections WHERE doc_id=? AND body LIKE ? LIMIT 1",
                (d, f"%{nat}%")).fetchone())
            if n:
                tally[nat] = n
        mine = sum(1 for d in docs if con.execute(
            "SELECT 1 FROM sections WHERE doc_id=? AND body LIKE ? LIMIT 1",
            (d, f"%{b}%")).fetchone())
        rival = max(tally.values()) if tally else 0
        if mine < 2 or mine <= rival:
            return None
        # 取一句合格的、提到 a 的原话，作为「它确实出现在这一篇」的凭据。
        # 不要取最短段——那多半是「前往庆云顶」这种任务指引。
        best = None
        for row in con.execute(
            """SELECT s.doc_id, d.doc_type, s.body FROM sections s
               JOIN documents d ON d.doc_id = s.doc_id
               WHERE s.body LIKE ? AND d.doc_type NOT IN ('notice')""",
            (f"%{a}%",),
        ):
            for s in sentences(row["body"] or ""):
                if a not in s or not usable(s, a):
                    continue
                key = abs(len(s) - 36)          # 越接近「一句话的长度」越好
                if best is None or key < best[0]:
                    best = (key, row["doc_id"], s, row["doc_type"])
        if not best:
            return None
        return (best[1], 1.5, best[2], best[3])

    for item in rel_facts:
        a, b, pred = item["subject"], item["object"], item["predicate"]
        if a not in ents or b not in ents:
            errors.append(f"名字不在库里：{a} / {b}")
            continue
        a_id, b_id = ents[a]["entity_id"], ents[b]["entity_id"]
        if (a_id, pred, b_id) in existing or (a_id, b_id) in existing_pairs:
            missing.append(f"{a} --{PRED_LABELS.get(pred, pred)}--> {b}（已有归属边，跳过）")
            continue
        hit = evidence_for(a, b, pred)
        weak = False
        if not hit or hit[1] < MIN_SCORE:
            fb = document_fallback(a, b)
            if fb:
                hit, weak = fb, True
        if not hit or hit[1] < 1.0:
            missing.append(f"{a} --{PRED_LABELS.get(pred, pred)}--> {b}（无语料共现）")
            continue
        doc_id, score, quote, dtype = hit
        note = item.get("note")
        if weak:
            note = (note + "；" if note else "") + "同篇提及，非同一句"
        picked.append({
            "subject": a_id, "predicate": pred, "object_id": b_id,
            "confidence": "confirmed" if score >= 2.6 else "likely",
            "spoiler": 1, "doc": doc_id, "quote": quote,
            "notes": note, "_a": a, "_b": b, "_score": score, "_weak": weak,
        })

    # ---- 2. 别名校验 ------------------------------------------------------
    own_names = {}
    for r in con.execute("SELECT entity_id, name FROM entity_names"):
        own_names.setdefault(r["name"], []).append(r["entity_id"])

    alias_ok: list[dict] = []
    alias_skip: list[str] = []
    for item in alias_facts:
        who, alias = item["subject"], item["alias"]
        if who not in ents:
            errors.append(f"别名的主体不在库里：{who}")
            continue
        eid = ents[who]["entity_id"]
        if alias in own_names.get(alias, []) and eid in own_names[alias]:
            alias_skip.append(f"{who} ← {alias}（已是别名）")
            continue
        # 别名不能是正名的子串，反之亦然：那种「别名」检索上没有增量
        if alias in who or who in alias:
            alias_skip.append(f"{who} ← {alias}（与正名互为子串，无检索增量）")
            continue
        others = [x for x in own_names.get(alias, []) if x != eid]
        if others:
            alias_skip.append(f"{who} ← {alias}（已被 {others[0]} 占用）")
            continue
        cnt = con.execute("SELECT COUNT(*) FROM sections WHERE body LIKE ?",
                          (f"%{alias}%",)).fetchone()[0]
        if cnt < 2:
            alias_skip.append(f"{who} ← {alias}（语料仅 {cnt} 次）")
            continue
        # 不要求「与正名同篇」：国家别称往往单独出现（「岩之国的神明」），
        # 强制同篇会把 岩之国 / 雷之国 / 驱邪方士 这类正解全挡掉。
        # 但要求频次 ≥2，避免只出现一次的偶然写法。
        alias_ok.append({"who": who, "alias": alias, "eid": eid, "count": cnt})

    # ---- 3. 报告 ----------------------------------------------------------
    print(f"关系：{len(picked)} 条可用 / {len(rel_facts)} 条结论")
    for r in sorted(picked, key=lambda x: (x["predicate"], x["_a"])):
        tag = " 同篇" if r["_weak"] else ""
        print(f"  {r['_a']:<10}{PRED_LABELS.get(r['predicate'], r['predicate']):<5}"
              f"{r['_b']:<6}{r['_score']:>4.1f}{tag:<4}  {r['quote'][:44]}")
    if missing:
        print(f"\n未写入 {len(missing)} 条：")
        for m in missing:
            print("  ·", m)
    if errors:
        print(f"\n错误 {len(errors)} 条：")
        for e in errors:
            print("  !", e)

    print(f"\n别名：{len(alias_ok)} 条可用 / {len(alias_facts)} 条")
    for a in alias_ok:
        print(f"  {a['who']:<10}← {a['alias']:<8}{a['count']:>5} 次")
    if alias_skip:
        print(f"跳过 {len(alias_skip)} 条：")
        for s in alias_skip:
            print("  ·", s)

    if not APPLY:
        print("\n（干跑，加 --apply 才写入）")
        return 0 if not errors else 1

    # ---- 4. 写 seed-stage8.yaml -----------------------------------------
    ordered = sorted(picked, key=lambda x: (x["subject"], x["predicate"], x["object_id"]))
    lines = [
        "# 第八批知识层种子 · 归属关系（由 scripts/apply_curated.py 生成）",
        "# 结论来自 knowledge/curated-facts.yaml；出处是脚本在正文里找到的原话。",
        "# confidence=confirmed 表示句子里有明确归属词；likely 表示只有「X的Y」或近距离共现。",
        "# id 按 (subject, predicate, object) 排序位置分配，改内容会重排——",
        "# 重排产生的旧 id 由 load_knowledge.py --prune 清掉。",
        "version: 1",
        f"batch: {facts.get('batch', '2026-11-10-curated')}",
        "status: draft",
        "relations:",
    ]
    for i, r in enumerate(ordered, 1):
        rid = REL_BASE + i
        lines.append(f"- id: {rid}")
        lines.append(f"  subject: {r['subject']}")
        lines.append(f"  predicate: {r['predicate']}")
        lines.append(f"  object_id: {r['object_id']}")
        lines.append(f"  confidence: {r['confidence']}")
        lines.append(f"  spoiler: {r['spoiler']}")
        lines.append(f"  doc: {r['doc']}")
        lines.append(f"  quote: {r['quote']}")
        if r.get("notes"):
            lines.append(f"  notes: {r['notes']}")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n已写入 {OUT.relative_to(ROOT)}（{len(ordered)} 条）")

    # ---- 5. 别名写独立批次 ---------------------------------------------
    # 不写回实体 seed：stage3/4/5 是 build_stage*.py 的产物，重跑一次就覆盖。
    # 之前 apply_aliases.py 这么干，19 条别名只剩库里残留（种子里已经没了）。
    alias_lines = [
        "# 第九批知识层种子 · 别名（由 scripts/apply_curated.py 生成）",
        "# 别名单独成批：实体批次会被 build_stage*.py 重写，别名写在里面会丢。",
        "# 结论源：knowledge/curated-facts.yaml；每条都在语料里出现过 ≥2 次。",
        "version: 1",
        f"batch: {facts.get('batch', '2026-11-10-curated')}",
        "status: draft",
        "aliases:",
    ]
    for a in sorted(alias_ok, key=lambda x: (x["eid"], x["alias"])):
        alias_lines.append(f"- entity: {a['eid']}")
        alias_lines.append(f"  name: {a['alias']}")
        alias_lines.append("  kind: alias")
    OUT_ALIAS.write_text("\n".join(alias_lines) + "\n", encoding="utf-8")
    print(f"已写入 {OUT_ALIAS.relative_to(ROOT)}（{len(alias_ok)} 条）")
    return 0 if not errors else 1

    # ---- 4. 写 seed-stage8.yaml -----------------------------------------
    ordered = sorted(picked, key=lambda x: (x["subject"], x["predicate"], x["object_id"]))
    lines = [
        "# 第八批知识层种子 · 归属关系（由 scripts/apply_curated.py 生成）",
        "# 结论来自 knowledge/curated-facts.yaml；出处是脚本在正文里找到的原话。",
        "# confidence=confirmed 表示句子里有明确归属词；likely 表示只有「X的Y」或近距离共现。",
        "# id 按 (subject, predicate, object) 排序位置分配，改内容会重排——",
        "# 重排产生的旧 id 由 load_knowledge.py --prune 清掉。",
        "version: 1",
        f"batch: {facts.get('batch', '2026-11-10-curated')}",
        "status: draft",
        "relations:",
    ]
    for i, r in enumerate(ordered, 1):
        rid = REL_BASE + i
        lines.append(f"- id: {rid}")
        lines.append(f"  subject: {r['subject']}")
        lines.append(f"  predicate: {r['predicate']}")
        lines.append(f"  object_id: {r['object_id']}")
        lines.append(f"  confidence: {r['confidence']}")
        lines.append(f"  spoiler: {r['spoiler']}")
        lines.append(f"  doc: {r['doc']}")
        lines.append(f"  quote: {r['quote']}")
        if r.get("notes"):
            lines.append(f"  notes: {r['notes']}")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n已写入 {OUT.relative_to(ROOT)}（{len(ordered)} 条）")

    # ---- 5. 别名写回实体所在 seed ---------------------------------------
    by_eid: dict[str, list[dict]] = {}
    for a in alias_ok:
        by_eid.setdefault(a["eid"], []).append({"name": a["alias"], "kind": "alias"})
    want_drop = {(ents[d["subject"]]["entity_id"], d["alias"])
                 for d in drop_aliases if d["subject"] in ents}

    touched = 0
    for path in SEEDS:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        ents_here = data.get("entities") or []
        changed = False
        for item in ents_here:
            eid = item.get("id")
            if eid in by_eid:
                have = {a["name"] for a in item.get("aliases") or []}
                for a in by_eid[eid]:
                    if a["name"] not in have:
                        item.setdefault("aliases", []).append(a)
                        changed = True
            if item.get("aliases"):
                keep = [a for a in item["aliases"] if (eid, a["name"]) not in want_drop]
                if len(keep) != len(item["aliases"]):
                    item["aliases"] = keep
                    changed = True
        if changed:
            header = "".join(line + "\n" for line in
                             path.read_text(encoding="utf-8").split("\n")[:8]
                             if line.startswith("#"))
            path.write_text(header + yaml.safe_dump(data, allow_unicode=True,
                                                    sort_keys=False, width=200),
                            encoding="utf-8")
            touched += 1
            print(f"更新 {path.name}")
    print(f"别名改动写入 {touched} 个 seed 文件")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
