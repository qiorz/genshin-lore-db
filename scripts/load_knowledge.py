#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 knowledge/seed.yaml 的第一批实体卡片灌进 SQLite 知识层。

设计要点（见 knowledge/README.md §8）：
  - 不硬编码 section_id。重导 corpus 后 section_id 会变，所以每条证据只写
    doc_id + 短引用，灌库时现场在 sections 里解析出当前 section_id / ordinal。
  - 解析不到就报错，绝不静默跳过；证据是知识层的命根子。
  - 幂等：entity_id / claim_id 固定，重跑只更新不重复插入。
  - 不写 documents / sections，不碰原文层。

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
SEED = ROOT / "knowledge/seed.yaml"
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


def main() -> int:
    seed = yaml.safe_load(SEED.read_text(encoding="utf-8"))
    entities = seed.get("entities") or []
    claims = seed.get("claims") or []
    errors: list[str] = []
    cache: dict = {}
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")

    known_ids = set()
    for item in entities:
        eid = item["id"]
        known_ids.add(eid)
        if item.get("type") not in ENTITY_TYPES:
            errors.append(f"{eid}: 非法 entity_type {item.get('type')}")
        for alias in item.get("aliases") or []:
            if alias.get("kind") not in NAME_TYPES:
                errors.append(f"{eid}: 非法 name_type {alias.get('kind')}")
        if not con.execute("SELECT 1 FROM documents WHERE doc_id=?", (item["evidence"][0]["doc"],)).fetchone():
            errors.append(f"{eid}: 证据文档不存在 {item['evidence'][0]['doc']}")
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

    alias_count = sum(len(e.get("aliases") or []) for e in entities)
    ev_count = sum(len(e.get("evidence") or []) for e in entities) + len(claims)
    print(f"实体 {len(entities)} · 别名 {alias_count} · claims {len(claims)} · 证据 {ev_count}")
    print(f"证据解析成功 {ev_count - sum(1 for x in errors if '证据未命中' in x)}/{ev_count}")
    for err in errors:
        print("  ERROR", err)

    if APPLY and not errors:
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
                     updated_at=datetime('now')""",
                (eid, item["type"], item["name"], item.get("name_en"),
                 item.get("description", ""), int(item.get("spoiler", 0)), "draft"),
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
        for item in claims:
            found = resolve(con, item["doc"], item["quote"], cache)
            source = con.execute(
                "SELECT primary_source_id FROM documents WHERE doc_id=?", (item["doc"],)
            ).fetchone()
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
                 source[0] if source else None, item["doc"],
                 found[0] if found else None, int(item.get("spoiler", 0)),
                 item.get("notes")),
            )
        con.commit()
        print(f"写入完成：entities={con.execute('SELECT COUNT(*) FROM entities').fetchone()[0]} "
              f"entity_names={con.execute('SELECT COUNT(*) FROM entity_names').fetchone()[0]} "
              f"claims={con.execute('SELECT COUNT(*) FROM claims').fetchone()[0]}")

    conf = Counter(c.get("confidence") for c in claims)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 知识层第一批种子 · 灌库报告", "",
        f"> {datetime.now().astimezone().isoformat(timespec='seconds')} · "
        f"模式：{'写入' if APPLY else '干跑'} · 来源 `knowledge/seed.yaml`", "",
        "| 项 | 值 |", "|---|---|",
        f"| 实体 | {len(entities)} |",
        f"| 别名（不含规范名） | {alias_count} |",
        f"| claims | {len(claims)} |",
        f"| 证据引用 | {ev_count} |",
        f"| 证据解析成功 | {ev_count - sum(1 for x in errors if '证据未命中' in x)} |",
        f"| 校验错误 | {len(errors)} |", "",
        "claims 置信度：" + "、".join(f"{k} {v}" for k, v in conf.most_common()), "",
        "## 证据样例（点得回原文）", "",
    ]
    for item in claims[:5]:
        found = resolve(con, item["doc"], item["quote"], cache)
        if found:
            lines.append(f"- `{item['doc']}` 第 {found[1]} 段 / section {found[0]}："
                         f"{item['statement']}（{item['confidence']} / {item['status']}）")
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
