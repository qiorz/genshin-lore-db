#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全库体检：只读扫描 corpus/ 与 SQLite，输出 CSV 清单 + Markdown 摘要。

设计目标：能自动抓出 `quest.obc.5299` 那类「A 任务的正文里混进了 B 任务」的问题，
而不是靠用户偶然发现。核心信号是「同一句长台词同时出现在多篇文档」，
再结合 region / version / doc_type 差异给出风险等级。

检查项
  1. front matter 必填字段、doc_id 唯一性、文件可读性
  2. corpus ↔ DB 对账：文档数、normalized_path、char_count、source_id、FTS 行数
  3. 跨文档重复台词 + 疑似串内容文档对
  4. 元数据字段覆盖率（version / region / release_date / spoiler）
  5. 空壳与极短正文文档

用法
    python scripts/audit_corpus.py
    python scripts/audit_corpus.py --strict          # 有 ERROR 时退出码 1（可接 CI）
    python scripts/audit_corpus.py --no-db          # 只扫 Markdown（用于回归测试）
    python scripts/audit_corpus.py --corpus /tmp/x --out-dir /tmp/y --no-db
"""
from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from corpus_rules import is_meta_bullet, normalize_line  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "db" / "genshin_lore.sqlite3"
DEFAULT_CORPUS = ROOT / "corpus"
DEFAULT_OUT = ROOT / "exports" / "obc-evaluation" / "audit"
SKIP_FILES = {"readme.md", "index.md"}
REQUIRED_FIELDS = (
    "id", "type", "title", "language", "canon_status", "transcription",
    "spoiler", "source", "status",
)
MIN_LINE_CHARS = 20      # 短于这个长度的台词不作为重复证据
MIN_SHARED_LINES = 5     # 文档对共享多少句才列为疑似串内容
MAX_PAIR_DOCS = 30       # 一句出现在超过 30 篇时不再两两配对（多半是模板句）
MIN_BODY_CHARS = 100     # 正文低于此字数视为空壳/极短

sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


def read_fm(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        raise ValueError("missing YAML front matter")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("unterminated YAML front matter")
    meta = yaml.safe_load(parts[1])
    if not isinstance(meta, dict):
        raise ValueError("front matter is not a mapping")
    return meta, parts[2].lstrip("\n")


def load_docs(corpus: Path, findings: list[dict]) -> list[dict]:
    docs: list[dict] = []
    for path in sorted(corpus.rglob("*.md")):
        if path.name.lower() in SKIP_FILES:
            continue
        rel = str(path.relative_to(corpus)).replace("\\", "/")
        try:
            meta, body = read_fm(path.read_text(encoding="utf-8"))
        except Exception as exc:
            findings.append({"level": "ERROR", "check": "front_matter",
                             "doc_id": rel, "detail": f"{type(exc).__name__}: {exc}"})
            continue
        for key in REQUIRED_FIELDS:
            if not meta.get(key):
                findings.append({"level": "ERROR", "check": "required_field",
                                 "doc_id": str(meta.get("id", rel)), "detail": f"missing {key}"})
        docs.append({
            "path": path,
            "rel": rel,
            "meta": meta,
            "body": body,
            "id": str(meta.get("id", "")),
        })
    seen: dict[str, str] = {}
    for doc in docs:
        if doc["id"] in seen:
            findings.append({"level": "ERROR", "check": "duplicate_doc_id",
                             "doc_id": doc["id"], "detail": f"also in {seen[doc['id']]}"})
        seen[doc["id"]] = doc["rel"]
    return docs


def content_lines(body: str):
    """可用于重复检测的长台词；跳过标题、空行与结构性元数据行。"""
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or is_meta_bullet(line):
            continue
        norm = normalize_line(line)
        if len(norm) >= MIN_LINE_CHARS:
            yield norm


def check_duplicates(docs: list[dict], out: Path, findings: list[dict]) -> dict:
    line_docs: dict[str, set[str]] = defaultdict(set)
    body_chars: dict[str, int] = {}
    doc_lines: dict[str, list[str]] = {}
    for doc in docs:
        seq = list(content_lines(doc["body"]))
        doc_lines[doc["id"]] = seq
        body_chars[doc["id"]] = sum(len(n) for n in seq)
        for norm in seq:
            line_docs[norm].add(doc["id"])

    duplicates = {k: v for k, v in line_docs.items() if len(v) >= 2}
    with (out / "duplicate-lines.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["chars", "doc_count", "doc_ids", "sample"])
        for norm, ids in sorted(duplicates.items(), key=lambda x: (-len(x[1]), -len(x[0]))):
            w.writerow([len(norm), len(ids), " ".join(sorted(ids)[:12]), norm[:120]])

    pair_count: dict[tuple[str, str], int] = defaultdict(int)
    pair_sample: dict[tuple[str, str], str] = {}
    for norm, ids in duplicates.items():
        if len(ids) > MAX_PAIR_DOCS:
            continue
        ordered = sorted(ids)
        for i, a in enumerate(ordered):
            for b in ordered[i + 1:]:
                key = (a, b)
                pair_count[key] += 1
                pair_sample.setdefault(key, norm[:100])

    meta_by_id = {d["id"]: d["meta"] for d in docs}
    line_sets = {k: set(v) for k, v in doc_lines.items()}

    def run_len(x: str, y: str) -> int:
        """x 中连续多少行也能在 y 里找到；整段复制会有很长的连续块。"""
        ys = line_sets.get(y, set())
        best = cur = 0
        for line in doc_lines.get(x, []):
            if line in ys:
                cur += 1
                if cur > best:
                    best = cur
            else:
                cur = 0
        return best

    suspects = []
    for (a, b), shared in pair_count.items():
        if shared < MIN_SHARED_LINES:
            continue
        run = max(run_len(a, b), run_len(b, a))
        ma, mb = meta_by_id.get(a, {}), meta_by_id.get(b, {})
        ra, rb = ma.get("region") or "", mb.get("region") or ""
        va, vb = str(ma.get("version") or ""), str(mb.get("version") or "")
        ta, tb = ma.get("type") or "", mb.get("type") or ""
        cross_region = bool(ra and rb and ra != rb)
        # 零散共享句（常用语、模板句）不算串内容；只有连续块才可疑。
        if run >= 8 and cross_region:
            risk = "high"
        elif run >= 8:
            risk = "medium"
        elif shared >= 15:
            risk = "medium"
        else:
            risk = "low"
        suspects.append({
            "doc_a": a, "doc_b": b, "shared_lines": shared, "longest_run": run,
            "risk": risk,
            "region_a": ra, "region_b": rb, "version_a": va, "version_b": vb,
            "type_a": ta, "type_b": tb, "sample": pair_sample.get((a, b), ""),
        })
    suspects.sort(key=lambda r: ({"high": 0, "medium": 1, "low": 2}[r["risk"]],
                                 -r["longest_run"]))
    with (out / "suspect-pairs.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(suspects[0].keys()) if suspects else
                           ["doc_a", "doc_b", "shared_lines", "risk"])
        w.writeheader()
        w.writerows(suspects)

    for row in suspects:
        if row["risk"] == "high":
            findings.append({
                "level": "WARN", "check": "suspect_contiguous_copy",
                "doc_id": row["doc_a"],
                "detail": (f"与 {row['doc_b']} 有 {row['longest_run']} 句连续雷同（共 {row['shared_lines']} 句），"
                           f"地区 {row['region_a']} / {row['region_b']}；样例：{row['sample'][:40]}"),
            })

    with (out / "empty-docs.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["doc_id", "title", "doc_type", "body_chars", "path"])
        for doc in docs:
            chars = body_chars.get(doc["id"], 0)
            if chars < MIN_BODY_CHARS:
                w.writerow([doc["id"], doc["meta"].get("title", ""),
                            doc["meta"].get("type", ""), chars,
                            str(doc["path"].relative_to(ROOT)).replace("\\", "/")])

    short_by_type: dict[str, int] = defaultdict(int)
    for doc in docs:
        if body_chars.get(doc["id"], 0) < MIN_BODY_CHARS:
            short_by_type[str(doc["meta"].get("type", ""))] += 1
    return {
        "unique_lines": len(line_docs),
        "duplicate_groups": len(duplicates),
        "suspect_pairs": len(suspects),
        "high_risk_pairs": sum(1 for r in suspects if r["risk"] == "high"),
        "long_runs": sum(1 for r in suspects if r["longest_run"] >= 8),
        "empty_docs": sum(short_by_type.values()),
        "empty_quests": short_by_type.get("quest", 0),
        "empty_by_type": dict(sorted(short_by_type.items(), key=lambda x: -x[1])),
    }


def check_fields(docs: list[dict], out: Path) -> dict:
    gaps = defaultdict(int)
    with (out / "field-gaps.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["doc_id", "doc_type", "missing_version", "missing_region",
                    "missing_release_date", "spoiler_level"])
        for doc in docs:
            m = doc["meta"]
            mv = not bool(m.get("version"))
            mr = not bool(m.get("region"))
            md = not bool(m.get("release_date"))
            gaps["version"] += mv
            gaps["region"] += mr
            gaps["release_date"] += md
            gaps["spoiler_non_1"] += (m.get("spoiler") or {}).get("level", 0) != 1
            if mv or mr or md:
                w.writerow([doc["id"], m.get("type", ""), int(mv), int(mr), int(md),
                            (m.get("spoiler") or {}).get("level", "")])
    return dict(gaps)


def check_db(docs: list[dict], db: Path, findings: list[dict]) -> dict:
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    total = con.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    sections = con.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
    fts = con.execute("SELECT COUNT(*) FROM sections_fts").fetchone()[0]
    integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
    rows = {r["doc_id"]: r for r in con.execute(
        "SELECT doc_id, char_count, normalized_path, primary_source_id FROM documents")}
    sources = {r[0] for r in con.execute("SELECT source_id FROM sources")}
    by_path = {d["rel"]: d for d in docs}

    mismatch = 0
    for doc_id, row in rows.items():
        rel = (row["normalized_path"] or "").replace("\\", "/")
        if rel.startswith("corpus/"):
            rel = rel[len("corpus/"):]
        doc = by_path.get(rel)
        if doc is None:
            continue
        if int(row["char_count"] or 0) != len(doc["body"]):
            mismatch += 1
            if mismatch <= 10:
                findings.append({"level": "ERROR", "check": "char_count",
                                 "doc_id": doc_id,
                                 "detail": f"DB {row['char_count']} vs MD {len(doc['body'])}"})
        for src in doc["meta"].get("source") or []:
            if src.get("source_id") not in sources:
                findings.append({"level": "ERROR", "check": "unknown_source",
                                 "doc_id": doc_id, "detail": str(src.get("source_id"))})
    if total != len(docs):
        findings.append({"level": "ERROR", "check": "doc_count",
                         "doc_id": "-", "detail": f"DB {total} vs corpus {len(docs)}"})
    if mismatch:
        findings.append({"level": "ERROR", "check": "char_count",
                         "doc_id": "-", "detail": f"{mismatch} 篇字符数不符"})
    if integrity != "ok":
        findings.append({"level": "ERROR", "check": "integrity",
                         "doc_id": "-", "detail": integrity})
    if fts != sections:
        findings.append({"level": "WARN", "check": "fts_count",
                         "doc_id": "-", "detail": f"sections {sections} vs fts {fts}（meta 行未索引时会不等）"})
    con.close()
    return {"db_docs": total, "sections": sections, "fts_rows": fts,
            "integrity": integrity, "char_count_mismatch": mismatch}


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["level", "check", "doc_id", "detail"])
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--no-db", action="store_true")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    findings: list[dict] = []
    docs = load_docs(args.corpus, findings)
    dup = check_duplicates(docs, args.out_dir, findings)
    fields = check_fields(docs, args.out_dir)
    db = check_db(docs, args.db, findings) if not args.no_db else {}

    errors = [f for f in findings if f["level"] == "ERROR"]
    warns = [f for f in findings if f["level"] == "WARN"]
    write_csv(args.out_dir / "findings.csv", findings)

    lines = [
        "# 全库体检报告", "",
        f"> 生成时间：{datetime.now().astimezone().isoformat(timespec='seconds')}  ",
        f"> 语料：`{args.corpus}`　文档 {len(docs):,} 篇  ",
        f"> 数据库：`{args.db}`" if db else "> 数据库：跳过（`--no-db`）", "",
        "## 总览", "",
        "| 项 | 值 |", "|---|---|",
        f"| 文档 | {len(docs):,} |",
        f"| 归一化长台词 | {dup['unique_lines']:,} |",
        f"| 跨文档重复台词组 | {dup['duplicate_groups']:,} |",
        f"| 疑似重复文档对 | {dup['suspect_pairs']:,} |",
        f"| 其中连续块 ≥8 句 | {dup['long_runs']:,}（跨地区高风险 {dup['high_risk_pairs']}） |",
        f"| 短正文（<{MIN_BODY_CHARS} 字） | {dup['empty_docs']:,}，其中任务 {dup['empty_quests']} 篇 |",
        f"| version 缺失 | {fields.get('version', 0):,} |",
        f"| region 缺失 | {fields.get('region', 0):,} |",
        f"| release_date 缺失 | {fields.get('release_date', 0):,} |",
        f"| spoiler ≠ 1 | {fields.get('spoiler_non_1', 0):,} |",
    ]
    if db:
        lines += [f"| SQLite 文档 / 段落 / FTS 行 | {db['db_docs']:,} / {db['sections']:,} / {db['fts_rows']:,} |",
                  f"| integrity_check | {db['integrity']} |",
                  f"| char_count 不符 | {db['char_count_mismatch']} |"]
    lines += ["", f"**ERROR {len(errors)} 条，WARN {len(warns)} 条。**", "",
              "## 需复核的连续重复块（Top 15）", ""]
    with (args.out_dir / "suspect-pairs.csv").open(encoding="utf-8-sig", newline="") as fh:
        top = [r for r in csv.DictReader(fh) if r["risk"] == "high"][:15]
    if top:
        lines += ["| 文档 A | 文档 B | 连续块 | 共享句 | 地区 | 样例 |",
                  "|---|---|---:|---:|---|---|"]
        for r in top:
            lines.append(f"| `{r['doc_a']}` | `{r['doc_b']}` | {r['longest_run']} | "
                         f"{r['shared_lines']} | {r['region_a']} / {r['region_b']} | {r['sample'][:40]} |")
    else:
        lines.append("无。")
    short = "、".join(f"{k} {v}" for k, v in dup["empty_by_type"].items())
    lines += ["", f"短正文按类型：{short}。`item` / `geography` / `lore` 本来就是铭牌式短文本，"
              "不是缺陷；真正需要关注的是 `quest`（含 32 条已知 `_pending` 空壳）。"]
    lines += ["", "## 明细文件", "",
              "- `findings.csv`：全部 ERROR / WARN",
              "- `duplicate-lines.csv`：同一句出现在多篇文档的台词",
              "- `suspect-pairs.csv`：文档对共享台词数与风险等级",
              "- `empty-docs.csv`：正文少于 100 字的文档",
              "- `field-gaps.csv`：缺失版本/地区/日期的文档", "",
              "判定口径：只统计归一化后 ≥20 字的台词，跳过标题与 `- 类型：…` 等结构性字段；"
              "文档对共享 ≥5 句才列入，另算「最长连续雷同块」。连续块 ≥8 句且跨地区标 `high`。"
              "`longest_run` 按行计（含文档内重复行），`shared_lines` 按唯一台词计，前者可能更大。"
              "**高风险不等于错误**：同角色洞天对话在不同频道重复收录、系列任务共用台词都会命中，"
              "清单是人工复核线索，不是自动判定。`duplicate-lines.csv` 里 50 篇同款的公告模板句"
              "属已知取舍（版本说明按 verbatim 全文保留）。"]
    (args.out_dir / "audit-summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"docs={len(docs):,}  duplicate_groups={dup['duplicate_groups']:,}  "
          f"suspect_pairs={dup['suspect_pairs']:,} (high={dup['high_risk_pairs']})  "
          f"empty={dup['empty_docs']:,}  ERROR={len(errors)}  WARN={len(warns)}")
    print(f"report -> {args.out_dir / 'audit-summary.md'}")
    for f in errors[:5]:
        print(f"  ERROR {f['check']}: {f['doc_id']} {f['detail'][:90]}")
    return 1 if (args.strict and errors) else 0


if __name__ == "__main__":
    raise SystemExit(main())
