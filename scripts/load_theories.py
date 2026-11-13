#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""推论层灌库 + 卡片导出。

知识源：knowledge/theories.yaml（人工维护）
  每个结论 = 标题 + claim + 多条证据（doc_id + 短引用 + 证据强度）。
证据不存 section_id，灌库时按 doc_id + 引文现场解析（复用 load_knowledge.resolve），
所以 corpus 重切段落之后，重跑一次即可复原。

    python scripts/load_theories.py            # 干跑：只校验证据能否命中
    python scripts/load_theories.py --apply    # 写库 + 生成 knowledge/theories/*.md
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

from load_knowledge import norm, resolve  # noqa: E402

DB = ROOT / "db" / "genshin_lore.sqlite3"
SCHEMA = ROOT / "schema" / "theories.sql"
SOURCE = ROOT / "knowledge" / "theories.yaml"
OUT = ROOT / "knowledge" / "theories"

KIND_LABEL = {
    "direct": "直接陈述",
    "implied": "隐晦暗示",
    "corroboration": "旁证",
    "counter": "反证",
}


def load_theories() -> list[dict]:
    if not SOURCE.exists():
        raise SystemExit(f"缺少 {SOURCE}")
    data = yaml.safe_load(SOURCE.read_text(encoding="utf-8")) or {}
    theories = data.get("theories") or []
    seen = set()
    for t in theories:
        tid = t.get("id")
        if not tid:
            raise SystemExit("有 theory 缺 id")
        if tid in seen:
            raise SystemExit(f"theory id 重复：{tid}")
        seen.add(tid)
        if not t.get("claim"):
            raise SystemExit(f"{tid} 缺 claim")
        for ev in t.get("evidence") or []:
            if not ev.get("doc") or not ev.get("quote"):
                raise SystemExit(f"{tid} 有证据缺 doc/quote")
            if ev.get("kind", "direct") not in KIND_LABEL:
                raise SystemExit(f"{tid} 证据 kind 非法：{ev.get('kind')}")
    return theories


def resolve_all(con: sqlite3.Connection, theories: list[dict]) -> tuple[list, list]:
    cache: dict = {}
    resolved: list[tuple[dict, list]] = []
    errors: list[str] = []
    for t in theories:
        rows = []
        seen_sections: dict[int, int] = {}
        seen_quotes: dict[str, int] = {}
        for i, ev in enumerate(t.get("evidence") or [], 1):
            found = resolve(con, ev["doc"], ev["quote"], cache)
            if not found:
                errors.append(f"{t['id']}[{i}] 证据未命中 {ev['doc']} | {ev['quote'][:28]}")
                continue
            section_id, ordinal, body = found
            # 同一段被引用两次 = 虚增证据条数，直接跳过并报错（曾经踩过：同一段拆成两条 quote）
            if section_id in seen_sections:
                errors.append(
                    f"{t['id']}[{i}] 与第 {seen_sections[section_id]} 条命中同一段 "
                    f"({ev['doc']} 第 {ordinal} 段)，已跳过"
                )
                continue
            seen_sections[section_id] = i
            qkey = norm(ev["quote"])[:20]
            if qkey in seen_quotes:
                errors.append(f"{t['id']}[{i}] 引文与第 {seen_quotes[qkey]} 条重复，已跳过")
                continue
            seen_quotes[qkey] = i
            rows.append({
                "ordinal": i,
                "doc_id": ev["doc"],
                "section_id": section_id,
                "sec_ordinal": ordinal,
                "body": body,
                "quote": ev["quote"],
                "kind": ev.get("kind", "direct"),
                "note": ev.get("note") or "",
            })
        resolved.append((t, rows))
    return resolved, errors


def upsert(con: sqlite3.Connection, resolved: list[tuple[dict, list]]) -> None:
    for t, rows in resolved:
        con.execute(
            """
            INSERT INTO theories (theory_id, title, claim, confidence, status,
                                  spoiler_level, aliases, open_questions, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(theory_id) DO UPDATE SET
                title=excluded.title, claim=excluded.claim, confidence=excluded.confidence,
                status=excluded.status, spoiler_level=excluded.spoiler_level,
                aliases=excluded.aliases, open_questions=excluded.open_questions,
                notes=excluded.notes
            """,
            (
                t["id"], t["title"], t["claim"], t.get("confidence", "speculative"),
                t.get("status", "open"), int(t.get("spoiler_level", 0)),
                "、".join(t.get("aliases") or []),
                "\n".join(t.get("open_questions") or []),
                t.get("notes") or "",
            ),
        )
        con.execute("DELETE FROM theory_evidence WHERE theory_id=?", (t["id"],))
        # 推论 → 实体关联：让实体卡片能反向显示「相关推论」
        con.execute("DELETE FROM theory_entities WHERE theory_id=?", (t["id"],))
        for eid in t.get("entities") or []:
            eid = str(eid).strip()
            if not eid:
                continue
            if con.execute("SELECT 1 FROM entities WHERE entity_id=?", (eid,)).fetchone():
                con.execute(
                    "INSERT OR IGNORE INTO theory_entities (theory_id, entity_id) VALUES (?,?)",
                    (t["id"], eid),
                )
            else:
                print(f"  !! 推论 {t['id']} 关联了不存在的实体：{eid}", flush=True)
        for row in rows:
            con.execute(
                """INSERT INTO theory_evidence
                   (theory_id, ordinal, doc_id, section_id, body, quote, kind, note)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (t["id"], row["ordinal"], row["doc_id"], row["section_id"],
                 row["body"], row["quote"], row["kind"], row["note"]),
            )


def export_cards(con: sqlite3.Connection, resolved: list[tuple[dict, list]]) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    written = 0
    for t, rows in resolved:
        titles = {}
        for doc_id, title, dtype in con.execute("SELECT doc_id, title, doc_type FROM documents"):
            titles[doc_id] = (title, dtype)
        kinds: dict[str, int] = {}
        for row in rows:
            kinds[row["kind"]] = kinds.get(row["kind"], 0) + 1
        lines = [
            "---",
            f"id: {t['id']}",
            "type: theory",
            f"title: {t['title']}",
            f"confidence: {t.get('confidence', 'speculative')}",
            f"status: {t.get('status', 'open')}",
            f"spoiler_level: {int(t.get('spoiler_level', 0))}",
            f"evidence_count: {len(rows)}",
            f"doc_count: {len({r['doc_id'] for r in rows})}",
            f"kind_summary: {'、'.join(f'{KIND_LABEL[k]}{v}' for k, v in kinds.items())}",
            "aliases:",
        ]
        for a in t.get("aliases") or []:
            lines.append(f"  - {a}")
        lines += [
            "---",
            "",
            f"# {t['title']}",
            "",
            "> 生成物，不要手改。改 `knowledge/theories.yaml` 后重跑 "
            "`scripts/load_theories.py --apply`。",
            "",
            "## 结论",
            "",
            t["claim"].strip(),
            "",
            "## 证据",
            "",
        ]
        for idx, row in enumerate(rows, 1):
            title, dtype = titles.get(row["doc_id"], (row["doc_id"], "?"))
            # 用重排后的序号，而不是原始 ordinal——校验跳过的条目会让编号出现跳号
            lines.append(
                f"### {idx}. {title}（{KIND_LABEL.get(row['kind'], row['kind'])}）"
            )
            lines.append("")
            lines.append(f"> {row['body'].strip()[:300]}")
            lines.append("")
            cite = f"`{row['doc_id']}` · 第 {row['sec_ordinal']} 段"
            if row["note"]:
                cite += f" · {row['note']}"
            lines.append(cite)
            lines.append("")
        if t.get("open_questions"):
            lines += ["## 待考", ""]
            for q in t["open_questions"]:
                lines.append(f"- {q}")
            lines.append("")
        target = OUT / f"{t['id']}.md"
        target.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n")
        written += 1
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="写库并导出卡片")
    ap.add_argument("--db", type=Path, default=DB)
    args = ap.parse_args()

    theories = load_theories()
    print(f"读到 {len(theories)} 条推论")

    if not args.apply:
        con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
        resolved, errors = resolve_all(con, theories)
        total = sum(len(r) for _, r in resolved)
        print(f"证据 {total} 条，未命中 {len(errors)} 条")
        for t, rows in resolved:
            kinds: dict[str, int] = {}
            for r in rows:
                kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
            detail = "、".join(f"{KIND_LABEL[k]} {v}" for k, v in kinds.items())
            print(f"  {t['id']}: {len(rows)} 条证据（{detail}），"
                  f"跨 {len({r['doc_id'] for r in rows})} 篇文档")
        for e in errors:
            print(f"  !! {e}")
        print("\n(dry-run，加 --apply 写库)")
        return 1 if errors else 0

    con = sqlite3.connect(args.db)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    resolved, errors = resolve_all(con, theories)
    upsert(con, resolved)
    con.commit()
    cards = export_cards(con, resolved)
    print(f"写入 {len(resolved)} 条推论、{sum(len(r) for _, r in resolved)} 条证据")
    print(f"导出卡片 {cards} 张 -> {OUT}")
    for e in errors:
        print(f"  !! 未入库的证据: {e}")
    con.close()
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
