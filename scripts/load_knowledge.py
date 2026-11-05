#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 knowledge/ 下的种子卡片灌进 SQLite 知识层。

数据源：自动读取 knowledge/seed*.yaml（按 seed.yaml 优先、其余按文件名排序）并合并
  seed.yaml          第一批：30 个实体 + 别名 + claims（已人工校对，reviewed）
  seed-stage2.yaml   第二批：关系边、提瓦特纪年事件、现实版本上线时间线
  seed-stage3.yaml   第三批：70 个扩量实体（半自动挖掘，draft）
  以后再加批次只需新增 seed-*.yaml，不必改本脚本。

设计要点（见 knowledge/README.md §8）：
  - 不硬编码 section_id。重导 corpus 后 section_id 会变，所以每条证据只写
    doc_id + 短引用，灌库时现场在 sections 里解析出当前 section_id / ordinal。
  - 解析不到就报错，绝不静默跳过；证据是知识层的命根子。
  - 幂等：所有主键固定（entity_id / claim_id / relation_id / event_id / entry_id）；
    重跑只更新不重复插入。event_sources 无唯一键，按 event_id 先删后插。
  - 不写 documents / sections，不碰原文层。
  - 现实版本上线日期（era=release）与提瓦特纪年（era=teyvat）严格分开，
    绝不互相换算，也绝不把「约五百年前」写成绝对年份。

用法：
    python scripts/load_knowledge.py            # 干跑，只校验并出报告
    python scripts/load_knowledge.py --apply    # 写入知识层表
"""
from __future__ import annotations

import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = ROOT / "knowledge"
SEED_FILES = sorted(SEED_DIR.glob("seed*.yaml"),
                    key=lambda p: (p.name != "seed.yaml", p.name))
DB = ROOT / "db/genshin_lore.sqlite3"
REPORT = ROOT / "exports/obc-evaluation/knowledge-seed-report.md"
APPLY = "--apply" in sys.argv
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

ENTITY_TYPES = {"character", "nation", "organization", "location", "deity",
                "creature", "concept", "event", "item", "title", "other"}
NAME_TYPES = {"canonical", "alias", "title", "epithet", "cryptic",
              "romanization", "translation"}
CONFIDENCE = {"confirmed", "likely", "speculative", "disputed", "unreliable"}
STATUS = {"open", "accepted", "disputed", "rejected", "superseded"}
CERTAINTY = {"exact", "approximate", "relative", "unknown"}
ENTITY_STATUS = {"draft", "reviewed", "stable", "deprecated"}

# 时间线条目 ID 的固定区间，保证幂等
TL_LORE_BASE = 3000
TL_RELEASE_BASE = 90000
REL_INVOLVED_BASE = 5000


def load_seeds() -> dict:
    """合并所有 seed*.yaml；给每条实体附加所属批次与该批的 status。"""
    merged = {"entities": [], "claims": [], "relations": [],
              "events": [], "release_timeline": {}, "batches": []}
    for path in SEED_FILES:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        batch = data.get("batch", path.stem)
        status = data.get("status", "draft")
        merged["batches"].append((path.name, batch, status))
        for entity in data.get("entities") or []:
            entity = dict(entity)
            entity["_status"] = entity.get("status", status)
            entity["_batch"] = batch
            merged["entities"].append(entity)
        for key in ("claims", "relations", "events"):
            merged[key].extend(data.get(key) or [])
        if data.get("release_timeline"):
            merged["release_timeline"] = data["release_timeline"]
    return merged


def norm(text: str) -> str:
    """只保留中文/字母/数字，抗标点与 Markdown 标记差异。"""
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", text or "")


def resolve(con: sqlite3.Connection, doc_id: str, quote: str, cache: dict):
    key = (doc_id, quote)
    if key in cache:
        return cache[key]
    target = norm(quote)[:14]
    rows = con.execute(
        "SELECT section_id, ordinal, body FROM sections WHERE doc_id=? ORDER BY ordinal",
        (doc_id,),
    ).fetchall()
    for section_id, ordinal, body in rows:
        if target and target in norm(body or ""):
            cache[key] = (section_id, ordinal, body or "")
            return cache[key]
    cache[key] = None
    return None


def source_of(con: sqlite3.Connection, doc_id: str) -> str | None:
    row = con.execute(
        "SELECT primary_source_id FROM documents WHERE doc_id=?", (doc_id,)
    ).fetchone()
    return row[0] if row else None


def release_rows(con: sqlite3.Connection) -> list[sqlite3.Row]:
    """53 篇官方版本更新说明 → 现实版本上线时间线。"""
    return con.execute(
        """SELECT doc_id, version, release_date, title, primary_source_id
           FROM documents
           WHERE doc_type='notice' AND version IS NOT NULL AND version<>''
             AND release_date IS NOT NULL AND release_date<>''
             AND title LIKE '%更新说明%'
           ORDER BY release_date, doc_id"""
    ).fetchall()


def main() -> int:
    data = load_seeds()
    entities = data["entities"]
    claims = data["claims"]
    relations = data["relations"]
    events = data["events"]
    release_cfg = data["release_timeline"]
    errors: list[str] = []
    cache: dict = {}
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")

    known_ids = {e["id"] for e in entities}
    id_counts = Counter(e["id"] for e in entities)
    for eid, n in id_counts.items():
        if n > 1:
            errors.append(f"重复 entity_id {eid}（{n} 次）")
    status_counts = Counter(e["_status"] for e in entities)
    for st in status_counts:
        if st not in ENTITY_STATUS:
            errors.append(f"非法 entity status {st}")

    for item in entities:
        eid = item["id"]
        if item.get("type") not in ENTITY_TYPES:
            errors.append(f"{eid}: 非法 entity_type {item.get('type')}")
        for alias in item.get("aliases") or []:
            if alias.get("kind") not in NAME_TYPES:
                errors.append(f"{eid}: 非法 name_type {alias.get('kind')}")
        for ev in item.get("evidence") or []:
            if not resolve(con, ev["doc"], ev["quote"], cache):
                errors.append(f"{eid}: 证据未命中 {ev['doc']} | {ev['quote'][:28]}")

    for item in claims:
        if item.get("subject") not in known_ids:
            errors.append(f"claim {item['id']}: 未知 subject {item.get('subject')}")
        if item.get("confidence") not in CONFIDENCE:
            errors.append(f"claim {item['id']}: 非法 confidence {item.get('confidence')}")
        if item.get("status") not in STATUS:
            errors.append(f"claim {item['id']}: 非法 status {item.get('status')}")
        if not resolve(con, item["doc"], item["quote"], cache):
            errors.append(f"claim {item['id']}: 证据未命中 {item['doc']} | {item['quote'][:28]}")

    for item in relations:
        rid = item["id"]
        if item.get("subject") not in known_ids:
            errors.append(f"relation {rid}: 未知 subject {item.get('subject')}")
        if item.get("object_id") and item["object_id"] not in known_ids:
            errors.append(f"relation {rid}: 未知 object_id {item['object_id']}")
        if not item.get("object_id") and not item.get("object_literal"):
            errors.append(f"relation {rid}: object_id / object_literal 至少填一个")
        if item.get("confidence") not in CONFIDENCE:
            errors.append(f"relation {rid}: 非法 confidence {item.get('confidence')}")
        if not resolve(con, item["doc"], item["quote"], cache):
            errors.append(f"relation {rid}: 证据未命中 {item['doc']} | {item['quote'][:28]}")

    for item in events:
        evid = item["id"]
        if item.get("time_certainty") not in CERTAINTY or item.get("certainty") not in CERTAINTY:
            errors.append(f"event {evid}: 非法 certainty {item.get('certainty')}")
        for eid in item.get("entities") or []:
            if eid not in known_ids:
                errors.append(f"event {evid}: 未知参与实体 {eid}")
        if not resolve(con, item["doc"], item["quote"], cache):
            errors.append(f"event {evid}: 证据未命中 {item['doc']} | {item['quote'][:28]}")

    releases = release_rows(con)
    if release_cfg and not releases:
        errors.append("release_timeline: 没有找到官方版本更新说明")
    if release_cfg.get("certainty") not in CERTAINTY or release_cfg.get("era") != "release":
        errors.append("release_timeline: era 必须为 release，certainty 必须合法")

    alias_count = sum(len(e.get("aliases") or []) for e in entities)
    ev_count = (sum(len(e.get("evidence") or []) for e in entities) + len(claims)
                + len(relations) + len(events))
    involved_count = sum(len(e.get("entities") or []) for e in events)
    missed = sum(1 for x in errors if "证据未命中" in x)
    print(f"实体 {len(entities)} · 别名 {alias_count} · claims {len(claims)} · "
          f"关系 {len(relations)}+{involved_count} · 纪年事件 {len(events)} · "
          f"版本上线 {len(releases)} · 证据 {ev_count}")
    print(f"证据解析成功 {ev_count - missed}/{ev_count}")
    for err in errors:
        print("  ERROR", err)

    if APPLY and not errors:
        # --- 第一批：实体 / 别名 / 说法 -------------------------------------
        for item in entities:
            eid = item["id"]
            con.execute(
                """INSERT INTO entities
                   (entity_id, entity_type, canonical_name, canonical_name_en,
                    description, spoiler_level, status, updated_at)
                   VALUES (?,?,?,?,?,?,?,datetime('now'))
                   ON CONFLICT(entity_id) DO UPDATE SET
                     entity_type=excluded.entity_type,
                     canonical_name=excluded.canonical_name,
                     canonical_name_en=excluded.canonical_name_en,
                     description=excluded.description,
                     spoiler_level=excluded.spoiler_level,
                     status=excluded.status,
                     updated_at=datetime('now')""",
                (eid, item["type"], item["name"], item.get("name_en"),
                 item.get("description", ""), int(item.get("spoiler", 0)), item["_status"]),
            )
            names = [(item["name"], "canonical", 1)]
            names += [(a["name"], a.get("kind", "alias"), 0) for a in item.get("aliases") or []]
            for name, kind, primary in names:
                con.execute(
                    """INSERT OR REPLACE INTO entity_names
                       (entity_id, name, language, name_type, source_id, is_primary)
                       VALUES (?,?,'zh-Hans',?,NULL,?)""",
                    (eid, name, kind, primary),
                )
            # 出处单独一条条存：详情页要能点回原文那一句。
            # 无稳定主键，按 entity 先删后插，保证幂等。
            con.execute("DELETE FROM entity_evidence WHERE entity_id=?", (eid,))
            for ev in item.get("evidence") or []:
                found = resolve(con, ev["doc"], ev["quote"], cache)
                con.execute(
                    """INSERT INTO entity_evidence
                       (entity_id, doc_id, section_id, quote, is_primary)
                       VALUES (?,?,?,?,1)""",
                    (eid, ev["doc"], found[0] if found else None, ev["quote"]),
                )
        for item in claims:
            found = resolve(con, item["doc"], item["quote"], cache)
            con.execute(
                """INSERT INTO claims
                   (claim_id, subject_id, subject_literal, predicate, object_id,
                    object_literal, statement, perspective, confidence, status,
                    source_id, doc_id, section_id, spoiler_level, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(claim_id) DO UPDATE SET
                     subject_id=excluded.subject_id,
                     predicate=excluded.predicate,
                     object_literal=excluded.object_literal,
                     statement=excluded.statement,
                     perspective=excluded.perspective,
                     confidence=excluded.confidence,
                     status=excluded.status,
                     doc_id=excluded.doc_id,
                     section_id=excluded.section_id,
                     spoiler_level=excluded.spoiler_level,
                     notes=excluded.notes""",
                (int(item["id"]), item.get("subject"), None, item["predicate"],
                 None, str(item.get("object", "")), item["statement"],
                 item.get("perspective"), item["confidence"], item["status"],
                 source_of(con, item["doc"]), item["doc"],
                 found[0] if found else None, int(item.get("spoiler", 0)),
                 item.get("notes")),
            )

        # --- 第二批：关系边 -------------------------------------------------
        def write_relation(rid, subject, predicate, object_id, object_literal,
                           confidence, spoiler, doc_id, quote, notes):
            found = resolve(con, doc_id, quote, cache)
            con.execute(
                """INSERT INTO entity_relations
                   (relation_id, subject_id, predicate, object_id, object_literal,
                    qualifier, confidence, source_id, doc_id, section_id,
                    spoiler_level, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(relation_id) DO UPDATE SET
                     subject_id=excluded.subject_id,
                     predicate=excluded.predicate,
                     object_id=excluded.object_id,
                     object_literal=excluded.object_literal,
                     confidence=excluded.confidence,
                     source_id=excluded.source_id,
                     doc_id=excluded.doc_id,
                     section_id=excluded.section_id,
                     spoiler_level=excluded.spoiler_level,
                     notes=excluded.notes""",
                (rid, subject, predicate, object_id, object_literal, None,
                 confidence, source_of(con, doc_id), doc_id,
                 found[0] if found else None, int(spoiler), notes),
            )

        for item in relations:
            write_relation(int(item["id"]), item["subject"], item["predicate"],
                           item.get("object_id"), item.get("object_literal"),
                           item["confidence"], item.get("spoiler", 0),
                           item["doc"], item["quote"], item.get("notes"))

        # --- 第二批：纪年事件 + 时间线 + 参与关系 ---------------------------
        involved_id = REL_INVOLVED_BASE
        for idx, item in enumerate(events, 1):
            evid = item["id"]
            found = resolve(con, item["doc"], item["quote"], cache)
            con.execute(
                """INSERT INTO events
                   (event_id, name, event_type, era, time_certainty, description, spoiler_level)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(event_id) DO UPDATE SET
                     name=excluded.name, event_type=excluded.event_type,
                     era=excluded.era, time_certainty=excluded.time_certainty,
                     description=excluded.description,
                     spoiler_level=excluded.spoiler_level""",
                (evid, item["name"], item.get("event_type"), "teyvat",
                 item["time_certainty"], item.get("description", ""),
                 int(item.get("spoiler", 0))),
            )
            con.execute("DELETE FROM event_sources WHERE event_id=?", (evid,))
            con.execute(
                """INSERT INTO event_sources (event_id, doc_id, section_id, source_id, notes)
                   VALUES (?,?,?,?,?)""",
                (evid, item["doc"], found[0] if found else None,
                 source_of(con, item["doc"]), item.get("relative_time")),
            )
            con.execute(
                """INSERT INTO timeline_entries
                   (entry_id, event_id, sort_key, label, relative_time, absolute_year,
                    era, certainty, source_id, doc_id, section_id, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(entry_id) DO UPDATE SET
                     event_id=excluded.event_id, sort_key=excluded.sort_key,
                     label=excluded.label, relative_time=excluded.relative_time,
                     era=excluded.era, certainty=excluded.certainty,
                     doc_id=excluded.doc_id, section_id=excluded.section_id,
                     notes=excluded.notes""",
                (TL_LORE_BASE + idx, evid, float(item["sort_key"]), item["label"],
                 item.get("relative_time"), None, "teyvat", item["certainty"],
                 source_of(con, item["doc"]), item["doc"],
                 found[0] if found else None,
                 "sort_key 只表示相对先后，不代表任何绝对年份。"),
            )
            for eid in item.get("entities") or []:
                involved_id += 1
                write_relation(involved_id, eid, "involved_in", None, evid,
                               "likely", item.get("spoiler", 0),
                               item["doc"], item["quote"],
                               "由事件参与关系自动生成，见 timeline_entries / event_sources。")

        # --- 第二批：现实版本上线时间线 -------------------------------------
        for row in releases:
            version = row["version"]
            try:
                entry_id = TL_RELEASE_BASE + int(round(float(version) * 10))
            except ValueError:
                continue
            con.execute(
                """INSERT INTO timeline_entries
                   (entry_id, event_id, sort_key, label, relative_time, absolute_year,
                    era, certainty, source_id, doc_id, section_id, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(entry_id) DO UPDATE SET
                     sort_key=excluded.sort_key, label=excluded.label,
                     relative_time=excluded.relative_time, era=excluded.era,
                     certainty=excluded.certainty, doc_id=excluded.doc_id,
                     notes=excluded.notes""",
                (entry_id, None, float(version),
                 f"{version} 版本上线 · {row['title']}", row["release_date"], None,
                 "release", release_cfg["certainty"], row["primary_source_id"],
                 row["doc_id"], None,
                 release_cfg.get("note", "")),
            )

        con.commit()
        for table in ("entities", "entity_names", "claims", "entity_relations",
                      "events", "event_sources", "timeline_entries"):
            n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table:20} {n}")

    # --- 报告 ---------------------------------------------------------------
    conf = Counter(c.get("confidence") for c in claims)
    rel_conf = Counter(r.get("confidence") for r in relations)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 知识层种子 · 灌库报告", "",
        f"> {datetime.now().astimezone().isoformat(timespec='seconds')} · "
        f"模式：{'写入' if APPLY else '干跑'} · "
        "来源：" + "、".join(f"`knowledge/{n}`" for n, _, _ in data["batches"]), "",
        "| 项 | 值 |", "|---|---|",
        f"| 实体 | {len(entities)}（" +
        "、".join(f"{k} {v}" for k, v in status_counts.most_common()) + "） |",
        f"| 种子批次 | {len(data['batches'])} |",
        f"| 别名（不含规范名） | {alias_count} |",
        f"| claims | {len(claims)} |",
        f"| 关系边 | {len(relations)} 条人工 + {involved_count} 条事件参与 |",
        f"| 提瓦特纪年事件 | {len(events)}（era=teyvat，只有相对顺序） |",
        f"| 现实版本上线 | {len(releases)}（era=release，官方公告日期） |",
        f"| 证据引用 | {ev_count} |",
        f"| 证据解析成功 | {ev_count - missed} |",
        f"| 校验错误 | {len(errors)} |", "",
        "claims 置信度：" + "、".join(f"{k} {v}" for k, v in conf.most_common()) + "  ",
        "关系置信度：" + "、".join(f"{k} {v}" for k, v in rel_conf.most_common()), "",
        "## 两条时间线互不换算", "",
        "- `era=release`：现实世界版本上线日期，取自米游社官方版本更新说明，certainty=exact；",
        "- `era=teyvat`：提瓦特纪年，只有相对先后，sort_key 为负数不代表年份，",
        "  原文里的「约两千六百年前」「五百年前」保留为约数文字，不写成 absolute_year。", "",
        "## 证据样例（点得回原文）", "",
    ]
    for item in claims[:3] + relations[:2]:
        found = resolve(con, item["doc"], item["quote"], cache)
        label = item.get("statement") or f"{item['subject']} —{item['predicate']}→"
        if found:
            lines.append(f"- `{item['doc']}` 第 {found[1]} 段 / section {found[0]}：{label}")
    if errors:
        lines += ["", "## 错误", ""] + [f"- {e}" for e in errors]
    lines += ["", "证据只用 `doc_id + 短引用` 定位，重导 corpus 后重跑本脚本即可重新对齐；",
              "不硬编码 section_id。原文层（documents / sections）不受影响。"]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"report -> {REPORT.relative_to(ROOT)}")
    con.close()
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
