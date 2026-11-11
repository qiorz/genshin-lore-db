#!/usr/bin/env python3
"""Local read-only Web UI for the Genshin lore database.

Run:
    python webui/app.py --port 8765
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sqlite3
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlencode, unquote, urlparse

import markdown

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "db" / "genshin_lore.sqlite3"
STATIC = Path(__file__).resolve().parent / "static"
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

TYPE_LABELS = {
    "book": "书籍",
    "quest": "任务",
    "lore": "散落文本",
    "character": "角色",
    "weapon": "武器",
    "artifact": "圣遗物",
    "item": "物品",
    "geography": "地理",
    "event": "活动",
    "voice": "NPC 对话",
    "notice": "官方公告",
    "manga": "漫画",
}
TYPE_ORDER = [
    "quest", "book", "lore", "character", "weapon", "artifact",
    "item", "geography", "event", "voice", "notice", "manga",
]
SUBTYPE_LABELS = {
    "archon": "魔神任务",
    "story": "传说任务",
    "hangout": "邀约事件",
    "world": "世界任务",
    "event": "限时任务",
    "interlude": "间章",
    "other": "其他任务",
    "scattered": "散落文本",
}
# 剧透筛选已下线：全库仅 10 篇做过 2/3 级分级，不足以支撑筛选。
# 后端仍接受 spoiler 参数（兼容旧链接与 /api/search），文档页照常显示等级值。
PAGE_SIZE = 20


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def first(args: dict[str, list[str]], key: str, default: str = "") -> str:
    values = args.get(key) or []
    return values[0].strip() if values else default


def number(value: str, default: int = 0, low: int = 0, high: int = 99) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, parsed))


def stats(con: sqlite3.Connection) -> dict:
    by_type = {row["doc_type"]: row["n"] for row in con.execute(
        "SELECT doc_type, COUNT(*) AS n FROM documents GROUP BY doc_type"
    )}
    sections = con.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
    pending = con.execute(
        "SELECT COUNT(*) FROM documents WHERE doc_type='quest' AND notes LIKE '%OBC 无剧情对话%'"
    ).fetchone()[0]
    return {"by_type": by_type, "sections": sections, "pending": pending}


def regions(con: sqlite3.Connection) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT region, COUNT(*) AS n FROM documents "
        "WHERE region IS NOT NULL AND region <> '' "
        "GROUP BY region ORDER BY n DESC, region LIMIT 30"
    ).fetchall()


COVERAGE_NOTES = {
    "type": "全部文档都有类型，可放心使用类型筛选。",
    "region": "物品 / 武器 / 圣遗物 / 活动 / 公告没有地区字段，属正常；任务、书籍、角色、散落文本、观景点、NPC 对话已 100% 标注。",
    "version": "所有值已归一化为 X.Y：月之一…月之八按 version-labels.csv 映射为 6.0–6.7，多版本书籍取最早版本（原值留在 notes）。物品 / NPC 对话 / 观景点上游无版本字段；479 条散落文本无可推导来源，按约定留空不猜。",
    "release_date": "仅官方公告有明确上线日期，其余类型留空。",
    "spoiler": "仅少数书籍做过 2/3 级分级，其余均为 1。分级不足以支撑筛选，剧透下拉已下线。",
}


def coverage(con: sqlite3.Connection) -> dict:
    """字段覆盖率：让「筛选会漏掉什么」变成明示信息，而不是隐藏陷阱。"""
    total = con.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    fields: dict[str, dict] = {}
    for key, col in (("type", "doc_type"), ("region", "region"),
                     ("version", "version"), ("release_date", "release_date")):
        n = con.execute(
            f"SELECT COUNT(*) FROM documents WHERE {col} IS NOT NULL AND {col} <> ''"
        ).fetchone()[0]
        fields[key] = {"filled": n, "total": total, "pct": round(100 * n / total, 1),
                       "note": COVERAGE_NOTES[key]}
    graded = con.execute("SELECT COUNT(*) FROM documents WHERE spoiler_level <> 1").fetchone()[0]
    fields["spoiler"] = {"filled": graded, "total": total,
                         "pct": round(100 * graded / total, 1),
                         "note": COVERAGE_NOTES["spoiler"]}
    return {"total": total, "fields": fields}


def versions(con: sqlite3.Connection) -> list[str]:
    rows = [r[0] for r in con.execute(
        "SELECT DISTINCT version FROM documents WHERE version IS NOT NULL AND version <> ''")]

    def key(value: str):
        try:
            return (0, tuple(int(part) for part in value.split(".")))
        except ValueError:
            return (1, value)

    return sorted(rows, key=key)


ENTITY_TYPE_LABELS = {
    "character": "人物", "deity": "神明", "nation": "国家/地区",
    "organization": "组织", "location": "地点", "creature": "生物",
    "concept": "概念", "event": "事件", "item": "物品",
    "title": "称号", "other": "其他",
}
CONFIDENCE_LABELS = {
    "confirmed": "已确认", "likely": "较可信", "speculative": "推测",
    "disputed": "有争议", "unreliable": "不可靠",
}
PREDICATE_LABELS = {
    "deity_of": "神明／统御", "member_of": "成员所属",
    "subordinate_to": "效忠于", "operated_by": "由…运营",
    "legacy_of": "继承自", "manifestation_of": "化身／体现",
    "guardian_of": "守护", "origin_of": "出身自",
    "companion_of": "同行者", "created_by": "由…创造",
    "has": "拥有", "symbol_of": "象征", "located_in": "位于",
    "nearest_to": "最接近", "based_in": "根据地在",
    "granted_by": "授予对象", "involved_in": "涉及事件",
    # 第八批：归属类，与 located_in（地点）/based_in（组织）分开
    "held_in": "举办于", "occurred_in": "发生于", "issued_in": "颁布于",
    "part_of": "隶属",
    # 人物↔人物：方向统一为「本实体是对方的…」
    "sibling_of": "兄弟姐妹", "child_of": "子女", "student_of": "师从",
}
STATUS_LABELS = {
    "open": "待定", "accepted": "已采信", "disputed": "有争议",
    "rejected": "已驳回", "superseded": "已被推翻",
}

CERTAINTY_LABELS = {
    "exact": "确切", "approximate": "约数", "relative": "仅相对顺序",
    "unknown": "未知",
}


def find_entities(con: sqlite3.Connection, query: str, limit: int = 200,
                  entity_type: str = "") -> list[sqlite3.Row]:
    # 加括号是必要的：A OR B AND type 会被 SQL 解析成 A OR (B AND type)。
    type_filter = " AND e.entity_type = ?" if entity_type else ""
    type_param = [entity_type] if entity_type else []
    if query:
        return con.execute(
            f"""SELECT DISTINCT e.* FROM entities e
                LEFT JOIN entity_names n ON n.entity_id = e.entity_id
                WHERE (e.canonical_name LIKE ? OR n.name LIKE ?){type_filter}
                ORDER BY e.spoiler_level, e.canonical_name LIMIT ?""",
            [f"%{query}%", f"%{query}%", *type_param, limit],
        ).fetchall()
    return con.execute(
        f"SELECT e.* FROM entities e WHERE 1=1{type_filter} "
        "ORDER BY e.spoiler_level, e.canonical_name LIMIT ?",
        [*type_param, limit],
    ).fetchall()


def knowledge_stats(con: sqlite3.Connection) -> dict:
    count = lambda table: con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return {
        "entities": count("entities"), "names": count("entity_names"),
        "relations": count("entity_relations"), "claims": count("claims"),
        "timeline": count("timeline_entries"),
        "draft": con.execute(
            "SELECT COUNT(*) FROM entities WHERE status <> 'reviewed'"
        ).fetchone()[0],
    }


def entity_names(con: sqlite3.Connection, entity_id: str) -> list[str]:
    return [r[0] for r in con.execute(
        "SELECT name FROM entity_names WHERE entity_id=? AND is_primary=0 ORDER BY name",
        (entity_id,),
    )]


def entity_claims(con: sqlite3.Connection, entity_id: str) -> list[sqlite3.Row]:
    return con.execute(
        """SELECT c.*, d.title AS doc_title FROM claims c
           LEFT JOIN documents d ON d.doc_id = c.doc_id
           WHERE c.subject_id = ? ORDER BY c.claim_id""",
        (entity_id,),
    ).fetchall()


def entity_evidence_rows(con: sqlite3.Connection, entity_id: str) -> list[sqlite3.Row]:
    """实体级原文出处：原文哪一篇、哪一句。与 claims 分开，不带断言含义。"""
    return con.execute(
        """SELECT ev.*, d.title AS doc_title, s.ordinal AS ordinal
           FROM entity_evidence ev
           LEFT JOIN documents d ON d.doc_id = ev.doc_id
           LEFT JOIN sections s ON s.section_id = ev.section_id
           WHERE ev.entity_id = ?
           ORDER BY ev.is_primary DESC, ev.doc_id, ev.evidence_id""",
        (entity_id,),
    ).fetchall()


def entity_relation_rows(con: sqlite3.Connection, entity_id: str) -> tuple[list, list]:
    """出边（本实体 → 其它）与入边（其它 → 本实体），事件参与关系单独展示。"""
    outgoing = con.execute(
        """SELECT r.*, e.canonical_name AS object_name, d.title AS doc_title
           FROM entity_relations r
           LEFT JOIN entities e ON e.entity_id = r.object_id
           LEFT JOIN documents d ON d.doc_id = r.doc_id
           WHERE r.subject_id=? AND r.predicate<>'involved_in'
           ORDER BY r.relation_id""",
        (entity_id,),
    ).fetchall()
    incoming = con.execute(
        """SELECT r.*, e.canonical_name AS subject_name, d.title AS doc_title
           FROM entity_relations r
           JOIN entities e ON e.entity_id = r.subject_id
           LEFT JOIN documents d ON d.doc_id = r.doc_id
           WHERE r.object_id=? AND r.predicate<>'involved_in'
           ORDER BY r.relation_id""",
        (entity_id,),
    ).fetchall()
    return outgoing, incoming


def entity_timeline_rows(con: sqlite3.Connection, entity_id: str) -> list[sqlite3.Row]:
    """通过 predicate=involved_in 的 object_literal（event_id）反查时间线条目。"""
    return con.execute(
        """SELECT DISTINCT t.entry_id, t.label, t.relative_time, t.era,
                  t.certainty, t.doc_id, t.sort_key, d.title AS doc_title
           FROM entity_relations r
           JOIN timeline_entries t ON t.event_id = r.object_literal
           LEFT JOIN documents d ON d.doc_id = t.doc_id
           WHERE r.subject_id=? AND r.predicate='involved_in'
           ORDER BY t.era DESC, t.sort_key""",
        (entity_id,),
    ).fetchall()


def entity_release(con: sqlite3.Connection, entity_id: str):
    """角色实装版本：实体名/别名 → 角色页标题 → documents.version → release 时间线。

    用 entity_names 而不是 canonical_name，是因为「雷电将军」这类实体名与
    角色页标题（「雷电影」）并不相同，靠别名才接得上。

    1.0 没有对应的版本更新说明（公测首发），relative_time 为空，属正常。
    """
    return con.execute(
        """SELECT d.version, d.doc_id, t.relative_time, t.label, t.sort_key
           FROM entity_names n
           JOIN documents d ON d.title = n.name
                AND d.doc_type = 'character'
                AND d.version IS NOT NULL AND d.version <> ''
           LEFT JOIN timeline_entries t
                ON t.era = 'release'
               AND ABS(t.sort_key - CAST(d.version AS REAL)) < 0.001
           WHERE n.entity_id = ?
           ORDER BY CAST(d.version AS REAL) DESC
           LIMIT 1""",
        (entity_id,),
    ).fetchone()


def timeline_rows(con: sqlite3.Connection, era: str) -> list[sqlite3.Row]:
    return con.execute(
        """SELECT t.*, d.title AS doc_title, e.name AS event_name
           FROM timeline_entries t
           LEFT JOIN documents d ON d.doc_id = t.doc_id
           LEFT JOIN events e ON e.event_id = t.event_id
           WHERE t.era=? ORDER BY t.sort_key, t.entry_id""",
        (era,),
    ).fetchall()


def make_snippet(text: str, query: str, width: int = 180) -> str:
    clean = re.sub(r"\s+", " ", re.sub(r"\*\*|\*", "", text or "")).strip()
    if not clean:
        return ""
    if query:
        pos = clean.lower().find(query.lower())
        if pos >= 0:
            start = max(0, pos - width // 3)
            end = min(len(clean), pos + len(query) + width)
            before = clean[start:pos]
            hit = clean[pos:pos + len(query)]
            after = clean[pos + len(query):end]
            prefix = "…" if start else ""
            suffix = "…" if end < len(clean) else ""
            return f"{prefix}{esc(before)}<mark>{esc(hit)}</mark>{esc(after)}{suffix}"
    return esc(clean[:width]) + ("…" if len(clean) > width else "")


def base_where(type_: str, region: str, max_spoiler: int | None, version: str) -> tuple[str, list]:
    filters = ["1=1"]
    params: list = []
    if type_ in TYPE_LABELS:
        filters.append("d.doc_type = ?")
        params.append(type_)
    if region:
        filters.append("d.region = ?")
        params.append(region)
    if max_spoiler is not None:
        filters.append("d.spoiler_level <= ?")
        params.append(max_spoiler)
    if version:
        # 前缀匹配：下拉传 "3.0" 精确命中，手输 "3" 可筛 3.x；
        # 不用 %version%，否则 "1.0" 会误命中 "11.0" 之类的值。
        filters.append("d.version LIKE ?")
        params.append(f"{version}%")
    return " AND ".join(filters), params


def search_docs(
    con: sqlite3.Connection,
    query: str,
    type_: str,
    region: str,
    max_spoiler: int | None,
    version: str,
    limit: int = 500,
) -> list[dict]:
    where, params = base_where(type_, region, max_spoiler, version)
    rows: list[sqlite3.Row] = []
    if query:
        title_rows = con.execute(
            f"""
            SELECT d.doc_id, d.title, d.doc_type, d.region, d.version,
                   d.spoiler_level, NULL AS speaker, d.title AS body,
                   NULL AS section_id,
                   COALESCE(ds.url, d.source_url) AS source_url
            FROM documents d
            LEFT JOIN document_sources ds
                ON ds.doc_id = d.doc_id AND ds.is_primary = 1
            WHERE d.title LIKE ? AND {where}
            ORDER BY d.spoiler_level, d.doc_id
            LIMIT 100
            """,
            [f"%{query}%", *params],
        ).fetchall()
        rows.extend(title_rows)

        if len(query) >= 3:
            match = '"' + query.replace('"', '""') + '"'
            try:
                fts_rows = con.execute(
                    f"""
                    SELECT d.doc_id, d.title, d.doc_type, d.region, d.version,
                           d.spoiler_level, s.speaker, s.body, s.section_id,
                           COALESCE(ds.url, d.source_url) AS source_url
                    FROM sections_fts f
                    JOIN sections s ON s.section_id = f.rowid
                    JOIN documents d ON d.doc_id = s.doc_id
                    LEFT JOIN document_sources ds
                        ON ds.doc_id = d.doc_id AND ds.is_primary = 1
                    WHERE sections_fts MATCH ? AND {where}
                    ORDER BY bm25(sections_fts), d.doc_id, s.ordinal
                    LIMIT ?
                    """,
                    [match, *params, limit],
                ).fetchall()
                rows.extend(fts_rows)
            except sqlite3.OperationalError:
                pass

        if len(query) < 3 or not any(row["section_id"] for row in rows):
            like = f"%{query}%"
            like_rows = con.execute(
                f"""
                SELECT d.doc_id, d.title, d.doc_type, d.region, d.version,
                       d.spoiler_level, s.speaker, s.body, s.section_id,
                       COALESCE(ds.url, d.source_url) AS source_url
                FROM sections s
                JOIN documents d ON d.doc_id = s.doc_id
                LEFT JOIN document_sources ds
                    ON ds.doc_id = d.doc_id AND ds.is_primary = 1
                WHERE (s.body LIKE ? OR s.body_segmented LIKE ?) AND {where}
                ORDER BY d.spoiler_level, d.doc_id, s.ordinal
                LIMIT ?
                """,
                [like, like, *params, limit],
            ).fetchall()
            rows.extend(like_rows)
    else:
        rows = con.execute(
            f"""
            SELECT d.doc_id, d.title, d.doc_type, d.region, d.version,
                   d.spoiler_level, NULL AS speaker, d.title AS body,
                   NULL AS section_id,
                   COALESCE(ds.url, d.source_url) AS source_url
            FROM documents d
            LEFT JOIN document_sources ds
                ON ds.doc_id = d.doc_id AND ds.is_primary = 1
            WHERE {where}
            ORDER BY d.doc_type, d.doc_id
            LIMIT 60
            """,
            params,
        ).fetchall()

    results: list[dict] = []
    seen = set()
    for row in rows:
        doc_id = row["doc_id"]
        if doc_id in seen:
            continue
        seen.add(doc_id)
        body = row["body"] or ""
        results.append(
            {
                "doc_id": doc_id,
                "title": row["title"],
                "doc_type": row["doc_type"],
                "region": row["region"] or "未标注",
                "version": row["version"] or "未标注",
                "spoiler": row["spoiler_level"],
                "speaker": row["speaker"],
                "snippet": make_snippet(body, query),
                "source_url": row["source_url"],
            }
        )
    return results


def get_doc(con: sqlite3.Connection, doc_id: str) -> dict | None:
    row = con.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
    if not row:
        return None
    sources = con.execute(
        """
        SELECT ds.source_id, ds.url, ds.page_id, ds.revision_id, ds.retrieved_at,
               ds.is_primary, s.name AS source_name
        FROM document_sources ds
        LEFT JOIN sources s ON s.source_id = ds.source_id
        WHERE ds.doc_id = ?
        ORDER BY ds.is_primary DESC, ds.source_id
        """,
        (doc_id,),
    ).fetchall()
    path = ROOT / (row["normalized_path"] or "")
    section_count = con.execute(
        "SELECT COUNT(*) FROM sections WHERE doc_id = ?", (doc_id,)
    ).fetchone()[0]
    body = ""
    body_html = ""
    error = ""
    if path.exists() and path.is_file():
        text = path.read_text(encoding="utf-8")
        if text.startswith("---"):
            parts = text.split("---", 2)
            body = parts[2] if len(parts) >= 3 else text
        else:
            body = text
        body_html = markdown.markdown(body, extensions=["extra", "sane_lists", "nl2br"])
    else:
        error = f"正文文件不存在：{row['normalized_path']}"
    return {"row": row, "sources": sources, "body": body, "body_html": body_html, "error": error, "section_count": section_count}


def badge(doc_type: str) -> str:
    label = TYPE_LABELS.get(doc_type, doc_type)
    return f'<span class="badge badge-{esc(doc_type)}">{esc(label)}</span>'


def layout(title: str, content: str, active: str = "") -> str:
    nav = [
        ("/", "检索", "home"),
        ("/search?type=book", "书籍", "book"),
        ("/search?type=quest", "任务", "quest"),
        ("/search?type=lore", "散落文本", "lore"),
        ("/search?type=character", "角色", "character"),
        ("/entities", "实体卡片", "entities"),
        ("/timeline", "时间线", "timeline"),
        ("/about", "关于", "about"),
    ]
    links = "".join(
        f'<a class="{"active" if active == key else ""}" href="{href}">{label}</a>'
        for href, label, key in nav
    )
    return f"""<!doctype html>
<html lang="zh-Hans">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · 原神世界观数据库</title>
<link rel="stylesheet" href="/static/style.css">
</head>
<body>
<header class="site-header">
  <a class="brand" href="/"><span class="brand-mark">◇</span><span>原神世界观数据库</span></a>
  <nav>{links}</nav>
</header>
<main>{content}</main>
<footer class="site-footer">
  <span>本地只读 · OBC / BWiki 社区文本 · 非官方逐字文本</span>
  <span>Genshin Lore DB</span>
</footer>
</body>
</html>"""


def search_form(q: str, type_: str, region: str, spoiler: str, version: str,
                region_rows: list, version_rows: list, cov: dict) -> str:
    type_options = ['<option value="">全部类型</option>']
    for key in TYPE_ORDER:
        selected = " selected" if type_ == key else ""
        type_options.append(f'<option value="{key}"{selected}>{TYPE_LABELS[key]}</option>')
    region_options = ['<option value="">全部地区</option>']
    for row in region_rows:
        selected = " selected" if region == row["region"] else ""
        region_options.append(
            f'<option value="{esc(row["region"])}"{selected}>{esc(row["region"])} ({row["n"]})</option>'
        )
    version_options = ['<option value="">全部版本</option>']
    for value in version_rows:
        selected = " selected" if version == value else ""
        version_options.append(f'<option value="{esc(value)}"{selected}>{esc(value)}</option>')
    fields = cov["fields"]
    cov_summary = (f"字段覆盖率：地区 {fields['region']['pct']}% · "
                   f"版本 {fields['version']['pct']}% · "
                   f"上线日期 {fields['release_date']['pct']}% · "
                   f"剧透分级 {fields['spoiler']['pct']}%")
    cov_labels = [("type", "类型"), ("region", "地区"), ("version", "版本"),
                  ("release_date", "上线日期"), ("spoiler", "剧透分级")]
    cov_items = "".join(
        f"<li><strong>{label}</strong> {fields[key]['pct']}%"
        f"（{fields[key]['filled']:,}/{fields[key]['total']:,}）："
        f"{esc(fields[key]['note'])}</li>"
        for key, label in cov_labels
    )
    return f"""
    <form class="search-form" action="/search" method="get">
      <input type="search" name="q" value="{esc(q)}" placeholder="搜索书名、任务、人物、地名、台词…" autofocus>
      <button type="submit">检索</button>
    </form>
    <div class="filters">
      <form id="filter-form" action="/search" method="get" class="filter-form">
        <input type="hidden" name="q" value="{esc(q)}">
        <input type="hidden" name="spoiler" value="{esc(spoiler)}">
        <select name="type">{''.join(type_options)}</select>
        <select name="region">{''.join(region_options)}</select>
        <select name="version">{''.join(version_options)}</select>
        <button type="submit" class="ghost">筛选</button>
      </form>
    </div>
    <details class="coverage-note">
      <summary>{esc(cov_summary)}<span class="cov-hint">筛选边界说明</span></summary>
      <ul>{cov_items}</ul>
    </details>
    """


def page_url(q: str, type_: str, region: str, spoiler: str, version: str, page: int) -> str:
    params = {"q": q, "type": type_, "region": region, "spoiler": spoiler, "version": version, "page": str(page)}
    return "/search?" + urlencode({k: v for k, v in params.items() if v})


def render_search(args: dict[str, list[str]]) -> str:
    q = first(args, "q")
    type_ = first(args, "type")
    region = first(args, "region")
    spoiler_raw = first(args, "spoiler")
    version = first(args, "version")
    max_spoiler = int(spoiler_raw) if spoiler_raw.isdigit() else None
    page = max(1, number(first(args, "page", "1"), 1, 1, 100))
    con = connect()
    try:
        st = stats(con)
        region_rows = regions(con)
        version_rows = versions(con)
        cov = coverage(con)
        entity_hits = find_entities(con, q, limit=5) if q else []
        results = search_docs(con, q, type_, region, max_spoiler, version)
    finally:
        con.close()

    # 额外补充区：默认折叠，放在结果列表之后，不改动任何原有结果卡片。
    related_html = ""
    if entity_hits:
        items = "".join(
            f'<li><a href="/entities?q={quote(row["canonical_name"], safe="")}">'
            f'{esc(row["canonical_name"])}</a>'
            f'<span class="entity-kind">{esc(ENTITY_TYPE_LABELS.get(row["entity_type"], row["entity_type"]))}</span></li>'
            for row in entity_hits
        )
        related_html = (
            f'<details class="related-entities"><summary>相关实体卡片（{len(entity_hits)}）'
            f' · 补充阅读，不影响上方原文结果</summary>'
            f'<ul>{items}</ul><p>卡片含别名与带出处的说法；完整列表见 '
            f'<a href="/entities">实体卡片</a>。</p></details>'
        )

    filter_notice = ""
    active = []
    if region:
        active.append(("地区", cov["fields"]["region"]))
    if version:
        active.append(("版本", cov["fields"]["version"]))
    if active:
        parts = [
            f"{label}覆盖 {f['filled']:,}/{f['total']:,} 篇（{f['pct']}%），"
            f"另有 <strong>{f['total'] - f['filled']:,}</strong> 篇未标注{label}的文档不在结果内"
            for label, f in active
        ]
        filter_notice = ('<div class="filter-notice">本次按'
                         + "、".join(label for label, _ in active)
                         + "筛选：" + "；".join(parts) + "。</div>")

    total = len(results)
    start = (page - 1) * PAGE_SIZE
    page_results = results[start:start + PAGE_SIZE]
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    cards = []
    for item in page_results:
        source = ""
        if item["source_url"]:
            source = f'<a class="source" href="{esc(item["source_url"])}" target="_blank" rel="noreferrer">来源 ↗</a>'
        speaker = f'<span class="speaker">{esc(item["speaker"])}</span> ' if item["speaker"] else ""
        cards.append(
            f"""
            <article class="result-card">
              <div class="result-top">
                {badge(item["doc_type"])}
                <span class="meta">{esc(item["region"])} · {esc(item["version"])}</span>
                <span class="spoiler">剧透 {esc(item["spoiler"])}</span>
              </div>
              <h2><a href="/doc/{quote(item["doc_id"], safe="")}">{esc(item["title"])}</a></h2>
              <p class="snippet">{speaker}{item["snippet"]}</p>
              <div class="result-bottom">{source}<span class="doc-id">{esc(item["doc_id"])}</span></div>
            </article>
            """
        )
    if not cards:
        cards.append('<div class="empty">没有找到结果。试试缩短关键词，或清除筛选条件。</div>')

    pager = ""
    if pages > 1:
        prev = f'<a href="{page_url(q, type_, region, spoiler_raw, version, page - 1)}">上一页</a>' if page > 1 else "<span>上一页</span>"
        nxt = f'<a href="{page_url(q, type_, region, spoiler_raw, version, page + 1)}">下一页</a>' if page < pages else "<span>下一页</span>"
        pager = f'<div class="pager">{prev}<span>{page} / {pages}</span>{nxt}</div>'

    counts = " · ".join(
        f"{TYPE_LABELS[key]} {st['by_type'].get(key, 0):,}" for key in TYPE_ORDER if st["by_type"].get(key)
    )
    heading = f"搜索「{esc(q)}」" if q else "检索全库"
    summary = f"{total:,} 条结果" if q else f"{sum(st['by_type'].values()):,} 篇文档 · {st['sections']:,} 个段落"
    if q and total == 0:
        summary = "0 条结果"

    content = f"""
    <section class="hero">
      <div class="hero-kicker">GENSHIN LORE · LOCAL INDEX</div>
      <h1>原神世界观数据库</h1>
      <p>书籍、任务、散落文本、角色故事。正文在 Markdown，检索走 SQLite FTS5。</p>
      {search_form(q, type_, region, spoiler_raw, version, region_rows, version_rows, cov)}
      <div class="stats-line">{counts} · 段落 {st['sections']:,} · 待补任务 {st['pending']}</div>
    </section>
    <section class="results-head">
      <div><h2>{heading}</h2><p>{summary}</p></div>
      <a class="ghost" href="/">重置</a>
    </section>
    {filter_notice}
    <section class="results">{''.join(cards)}</section>
    {pager}
    {related_html}
    """
    return layout("检索", content, "home")


def render_doc(doc_id: str) -> str:
    con = connect()
    try:
        doc = get_doc(con, doc_id)
    finally:
        con.close()
    if not doc:
        return layout("未找到", '<section class="empty-page"><h1>未找到文档</h1><p>这个 doc_id 不在数据库里。</p><a href="/">返回检索</a></section>', "home")

    row = doc["row"]
    title = row["title"]
    subtype = SUBTYPE_LABELS.get(row["subtype"], row["subtype"] or "")
    meta_bits = [badge(row["doc_type"])]
    if subtype:
        meta_bits.append(f'<span class="chip">{esc(subtype)}</span>')
    meta_bits.append(f'<span class="chip">{esc(row["region"] or "未知")}</span>')
    meta_bits.append(f'<span class="chip">版本 {esc(row["version"] or "未知")}</span>')
    meta_bits.append(f'<span class="chip">剧透 {esc(row["spoiler_level"])}</span>')
    if row["version_source"]:
        meta_bits.append(f'<span class="chip subtle">{esc(row["version_source"])} / {esc(row["version_confidence"])}</span>')

    sources = []
    for source in doc["sources"]:
        label = source["source_name"] or source["source_id"]
        if source["url"]:
            sources.append(
                f'<li><a href="{esc(source["url"])}" target="_blank" rel="noreferrer">{esc(label)} ↗</a>'
                f'<span class="source-meta">page {esc(source["page_id"])} · rev {esc(source["revision_id"])}</span></li>'
            )
        else:
            sources.append(f"<li>{esc(label)}</li>")

    note = ""
    if row["notes"]:
        note = f'<div class="note"><strong>校注</strong><p>{esc(row["notes"])}</p></div>'
    error = f'<div class="note error">{esc(doc["error"])}</div>' if doc["error"] else ""
    raw_link = f'<a class="ghost" href="/raw/{quote(doc_id, safe="")}">查看 Markdown</a>'
    content = f"""
    <article class="doc-page">
      <div class="doc-head">
        <div class="doc-meta">{''.join(meta_bits)}</div>
        <h1>{esc(title)}</h1>
        <div class="doc-path">{esc(row["normalized_path"] or "")}</div>
        <div class="doc-actions">{raw_link}<a class="ghost" href="/">返回检索</a></div>
      </div>
      {error}
      {note}
      <div class="doc-grid">
        <div class="prose">{doc["body_html"]}</div>
        <aside class="doc-side">
          <h3>文档信息</h3>
          <dl>
            <dt>doc_id</dt><dd>{esc(doc_id)}</dd>
            <dt>类型</dt><dd>{esc(row["doc_type"])} / {esc(row["subtype"] or "—")}</dd>
            <dt>地区</dt><dd>{esc(row["region"] or "未知")}</dd>
            <dt>版本</dt><dd>{esc(row["version"] or "未知")}</dd>
            <dt>版本来源</dt><dd>{esc(row["version_source"] or "unknown")} / {esc(row["version_confidence"] or "unknown")}</dd>
            <dt>收录状态</dt><dd>{esc(row["status"] or "—")}</dd>
            <dt>字数 / 段数</dt><dd>{int(row["char_count"] or 0):,} / {int(doc["section_count"] or 0):,}</dd>
          </dl>
          <h3>来源</h3>
          <ul class="sources">{''.join(sources) or '<li>无来源记录</li>'}</ul>
        </aside>
      </div>
    </article>
    """
    return layout(title, content, "home")


def render_entities(args: dict[str, list[str]]) -> str:
    q = first(args, "q")
    etype = first(args, "type")
    con = connect()
    try:
        ks = knowledge_stats(con)
        rows = find_entities(con, q, limit=500, entity_type=etype)
        # 列表页只判断「有没有」上线版本，不取具体内容——一次查完，
        # 不给 400 张卡各查一遍。详情页才用 entity_release()。
        has_release = {r[0] for r in con.execute(
            """SELECT DISTINCT n.entity_id FROM entity_names n
               JOIN documents d ON d.title = n.name AND d.doc_type = 'character'
               WHERE d.version IS NOT NULL AND d.version <> ''""")}
        cards = []
        for row in rows:
            names = entity_names(con, row["entity_id"])
            claims = entity_claims(con, row["entity_id"])
            outgoing, incoming = entity_relation_rows(con, row["entity_id"])
            tl_rows = entity_timeline_rows(con, row["entity_id"])
            alias_html = "".join(f'<span class="alias">{esc(n)}</span>' for n in names)
            claim_items = []
            for c in claims:
                link = (f'<a href="/doc/{quote(c["doc_id"], safe="")}">'
                        f'{esc(c["doc_title"] or c["doc_id"])}</a>') if c["doc_id"] else "—"
                claim_items.append(
                    f'<li><span class="claim-text">{esc(c["statement"])}</span>'
                    f'<span class="claim-tags">'
                    f'{esc(CONFIDENCE_LABELS.get(c["confidence"], c["confidence"]))} · {esc(c["status"])}</span>'
                    f'<span class="claim-src">出处：{link}</span></li>'
                )
            cards.append(f"""
            <article class="entity-card">
              <div class="entity-head">
                <h2><a href="/entity/{quote(row['entity_id'], safe='')}">{esc(row['canonical_name'])}</a></h2>
                <span class="entity-kind">{esc(ENTITY_TYPE_LABELS.get(row['entity_type'], row['entity_type']))}</span>
              </div>
              <p class="entity-desc">{esc(row['description'] or '')}</p>
              <div class="aliases">{alias_html or '<span class="none">暂无别名</span>'}</div>
              <p class="entity-meta">关系 {len(outgoing) + len(incoming)} 条 · 说法 {len(claims)} 条 ·
                相关时间线 {len(tl_rows) + (1 if row["entity_id"] in has_release else 0)} 条 ·
                {'<span class="entity-status draft">待复核</span>' if row['status'] != 'reviewed' else '<span class="entity-status reviewed">已校对</span>'} ·
                <a href="/entity/{quote(row['entity_id'], safe='')}">查看详情 →</a></p>
              <h3>带出处的说法（{len(claims)}）</h3>
              <ul class="claim-list">{''.join(claim_items) or '<li class="none">暂无</li>'}</ul>
            </article>""")
    finally:
        con.close()
    content = f"""
    <section class="hero">
      <div class="hero-kicker">KNOWLEDGE LAYER · SEED</div>
      <h1>实体卡片</h1>
      <p>额外的一层：把同一个人物的不同叫法、带出处的说法收在一起。原文检索不受影响。</p>
      <form class="search-form" action="/entities" method="get">
        <input type="search" name="q" value="{esc(q)}" placeholder="搜名字或别名，如 巴巴托斯 / 岩王帝君" autofocus>
        <select name="type" class="entity-type-select">
          <option value="">全部类型</option>
          {''.join(f'<option value="{k}"{" selected" if etype == k else ""}>{v}</option>' for k, v in ENTITY_TYPE_LABELS.items())}
        </select>
        <button type="submit">查找</button>
      </form>
      <div class="stats-line">当前显示 {len(rows)} / {ks['entities']} 个实体 · {ks['names']} 个别名 ·
        {ks['relations']} 条关系 · {ks['claims']} 条说法 · {ks['timeline']} 条时间线 ·
        <a href="/timeline">时间线</a> · <a href="/">回到原文检索</a></div>
      <p class="entity-hint">前 30 个实体已人工校对；扩量的 {ks['draft']} 个为半自动收录，
        描述只是分类标签（不是剧情结论），状态标「待复核」，别名与出处均有库内证据。</p>
    </section>
    <section class="entity-list">{''.join(cards) or '<div class="empty">没有匹配的实体。</div>'}</section>
    """
    return layout("实体卡片", content, "entities")


def render_entity_detail(entity_id: str) -> str | None:
    con = connect()
    try:
        row = con.execute(
            "SELECT * FROM entities WHERE entity_id=?", (entity_id,)
        ).fetchone()
        if not row:
            return None
        names = entity_names(con, entity_id)
        claims = entity_claims(con, entity_id)
        evidence = entity_evidence_rows(con, entity_id)
        # 全库提及：卡片只锚定一两条证据，但这个名字在正文里出现多少次是另一回事，
        # 两个数字必须同时显示，否则「176 篇提及 / 1 条关联原文」会被当成数据缺失。
        mention_docs, mention_sections, mention_quests = con.execute(
            """SELECT COUNT(DISTINCT s.doc_id), COUNT(*),
                      COUNT(DISTINCT CASE WHEN d.doc_type = 'quest' THEN s.doc_id END)
               FROM sections s JOIN documents d ON d.doc_id = s.doc_id
               WHERE s.body LIKE ?""",
            (f"%{row['canonical_name']}%",),
        ).fetchone()
        outgoing, incoming = entity_relation_rows(con, entity_id)
        tl_rows = entity_timeline_rows(con, entity_id)
        release = entity_release(con, entity_id)
    finally:
        con.close()

    def rel_items(rows, direction: str) -> str:
        items = []
        for r in rows:
            obj = (r["object_name"] or r["object_literal"] or "") if direction == "out" \
                else (r["subject_name"] or "")
            label = PREDICATE_LABELS.get(r["predicate"], r["predicate"])
            conf = CONFIDENCE_LABELS.get(r["confidence"], r["confidence"])
            link = (f'<a href="/doc/{quote(r["doc_id"], safe="")}">'
                    f'{esc(r["doc_title"] or r["doc_id"])}</a>') if r["doc_id"] else "—"
            arrow = f"本实体 —{esc(label)}→ {esc(obj)}" if direction == "out" \
                else f"{esc(obj)} —{esc(label)}→ 本实体"
            items.append(f'<li><span class="claim-text">{arrow}</span>'
                         f'<span class="claim-tags">{esc(conf)}</span>'
                         f'<span class="claim-src">出处：{link}</span></li>')
        return "".join(items) or '<li class="none">暂无</li>'

    claim_items = []
    for c in claims:
        link = (f'<a href="/doc/{quote(c["doc_id"], safe="")}">'
                f'{esc(c["doc_title"] or c["doc_id"])}</a>') if c["doc_id"] else "—"
        # 卡片上只给前 110 字，全文在原文里；否则一张卡会被一条长语音撑爆
        text = c["statement"] or ""
        shown = text if len(text) <= 110 else text[:110] + "…"
        claim_items.append(
            f'<li><span class="claim-text" title="{esc(text[:400])}">{esc(shown)}</span>'
            f'<span class="claim-tags">{esc(CONFIDENCE_LABELS.get(c["confidence"], c["confidence"]))}'
            f' · {esc(STATUS_LABELS.get(c["status"], c["status"]))}</span>'
            f'<span class="claim-src">{esc(c["perspective"] or "未标视角")} · 出处：{link}</span></li>'
        )

    tl_items = []
    if release:
        # 排在提瓦特纪年之前：这是「现实版本」这条线，与剧情年代无关
        when = release["relative_time"] or "公测首发，无版本更新说明"
        ver = f'{release["version"]} 版本上线'
        tl_items.append(
            f'<li><span class="claim-text">{esc(ver)}</span>'
            f'<span class="claim-tags">现实版本 · 确切</span>'
            f'<span class="claim-src">{esc(when)} · 出处：'
            f'<a href="/doc/{quote(release["doc_id"], safe="")}">{esc(release["doc_id"])}</a>'
            f'</span></li>'
        )
    for t in tl_rows:
        link = (f'<a href="/doc/{quote(t["doc_id"], safe="")}">'
                f'{esc(t["doc_title"] or t["doc_id"])}</a>') if t["doc_id"] else "—"
        tl_items.append(
            f'<li><span class="claim-text">{esc(t["label"])}</span>'
            f'<span class="claim-tags">{esc("现实版本" if t["era"] == "release" else "提瓦特纪年")}'
            f' · {esc(CERTAINTY_LABELS.get(t["certainty"], t["certainty"]))}</span>'
            f'<span class="claim-src">{esc(t["relative_time"] or "—")} · 出处：{link}</span></li>'
        )

    # 「关联原文」= 实体出处 ∪ 关系/说法的出处。
    # 出处逐句列出（带原话），关系和说法只补文档链接，不重复列同一篇。
    ev_docs = {e["doc_id"] for e in evidence if e["doc_id"]}
    docs = sorted(ev_docs | {r["doc_id"] for r in list(outgoing) + list(incoming) + list(claims)
                             if r["doc_id"]})
    ev_items = []
    for e in evidence:
        if not e["doc_id"]:
            continue
        link = f'<a href="/doc/{quote(e["doc_id"], safe="")}">{esc(e["doc_title"] or e["doc_id"])}</a>'
        q = e["quote"] or ""
        shown = q if q.startswith("「") else f"「{q}」"
        ev_items.append(f'<li><span class="claim-text">{esc(shown)}</span>'
                        f'<span class="claim-src">出处：{link}</span></li>')
    rest = [d for d in docs if d not in ev_docs]
    titles = {r["doc_id"]: r["doc_title"] for r in
              list(outgoing) + list(incoming) + list(claims) + list(evidence)
              if r["doc_id"]}
    ev_items += [f'<li><a href="/doc/{quote(d, safe="")}">'
                 f'{esc(titles.get(d) or d)}</a></li>' for d in rest]
    doc_links = "".join(ev_items) or '<li class="none">暂无</li>'

    alias_html = "".join(f'<span class="alias">{esc(n)}</span>' for n in names) \
        or '<span class="none">暂无别名</span>'
    content = f"""
    <section class="hero">
      <div class="hero-kicker">KNOWLEDGE LAYER · ENTITY</div>
      <h1>{esc(row['canonical_name'])}</h1>
      <p>{esc(row['description'] or '')}</p>
      <div class="stats-line">
        {esc(ENTITY_TYPE_LABELS.get(row['entity_type'], row['entity_type']))} ·
        剧透等级 {row['spoiler_level']} · status {esc(row['status'])} ·
        全库提及 {mention_docs} 篇（任务 {mention_quests} 篇 / 共 {mention_sections} 段）·
        <a href="/?q={quote(row['canonical_name'], safe='')}">检索这些原文 →</a> ·
        <a href="/entities">全部实体</a> · <a href="/timeline">时间线</a> ·
        <a href="/">回到原文检索</a>
      </div>
    </section>
    <div class="detail-grid">
      <article class="detail-card">
        <h2>别名（{len(names)}）</h2>
        <div class="aliases">{alias_html}</div>
        <p class="detail-note">搜任何一个别名都能找到这张卡；别名只指向卡片，不改写原文。</p>
      </article>
      <article class="detail-card">
        <h2>关联原文（{len(docs)}）</h2>
        <ul class="detail-docs">{doc_links}</ul>
        <p class="detail-note">这里只列卡片的锚定出处（每张卡至少一条，优先取整篇在讲它的文档）；
          全库还有 {mention_docs} 篇提到过「{esc(row['canonical_name'])}」，点上方的「检索这些原文」看全部。</p>
      </article>
    </div>
    <article class="detail-card wide">
      <h2>关系（{len(outgoing) + len(incoming)}）</h2>
      <h3>本实体指向</h3>
      <ul class="claim-list">{rel_items(outgoing, 'out')}</ul>
      <h3>其它实体指向本实体</h3>
      <ul class="claim-list">{rel_items(incoming, 'in')}</ul>
      <p class="detail-note">关系只收稳定可复用的断言；有视角、有争议的说法放在下面，不混成定论。</p>
    </article>
    <article class="detail-card wide">
      <h2>说法与置信度（{len(claims)}）</h2>
      <ul class="claim-list">{''.join(claim_items) or '<li class="none">暂无</li>'}</ul>
    </article>
    <article class="detail-card wide">
      <h2>相关时间线（{len(tl_rows) + (1 if release else 0)}）</h2>
      <ul class="claim-list">{''.join(tl_items) or '<li class="none">暂无</li>'}</ul>
      <p class="detail-note">现实版本上线日期与提瓦特纪年是两条独立时间线，不互相换算。</p>
    </article>
    """
    return layout(f"实体 · {row['canonical_name']}", content, "entities")


def render_timeline(args: dict[str, list[str]]) -> str:
    era = first(args, "era")
    if era not in ("release", "teyvat"):
        era = ""
    con = connect()
    try:
        releases = timeline_rows(con, "release")
        lore = timeline_rows(con, "teyvat")
    finally:
        con.close()

    def table(rows, kind: str) -> str:
        body = []
        for r in rows:
            link = (f'<a href="/doc/{quote(r["doc_id"], safe="")}">'
                    f'{esc(r["doc_title"] or r["doc_id"])}</a>') if r["doc_id"] else "—"
            when = r["relative_time"] or "—"
            cert = CERTAINTY_LABELS.get(r["certainty"], r["certainty"])
            if kind == "release":
                version = (r["label"] or "").split(" 版本上线", 1)[0]
                body.append(f"<tr><td>{esc(version)}</td><td>{esc(when)}</td>"
                            f"<td>{esc(cert)}</td><td>{link}</td></tr>")
            else:
                body.append(f"<tr><td>{esc(r['label'])}</td><td>{esc(when)}</td>"
                            f"<td>{esc(cert)}</td><td>{link}</td></tr>")
        head = ("<tr><th>版本</th><th>上线日期</th><th>确定性</th><th>官方说明</th></tr>"
                if kind == "release" else
                "<tr><th>事件（按相对先后）</th><th>相对时间</th><th>确定性</th><th>出处</th></tr>")
        return (f'<table class="timeline-table"><thead>{head}</thead>'
                f'<tbody>{"".join(body)}</tbody></table>')

    blocks = ""
    if era != "teyvat":
        blocks += f"""
    <section class="era-block">
      <h2>现实版本上线（{len(releases)}）</h2>
      <p class="timeline-note">现实世界的官方版本更新说明发布日期，1.1 → 7.2 无断档。
      这是发布历史，<strong>不是提瓦特纪年</strong>；确定性为「确切」。</p>
      {table(releases, 'release')}
    </section>"""
    if era != "release":
        blocks += f"""
    <section class="era-block">
      <h2>提瓦特纪年（{len(lore)}，只有相对顺序）</h2>
      <p class="timeline-note">游戏内世界的事件顺序。原文写「约两千六百年前」「五百年前」的，
      保留约数文字而不伪造绝对年份；排序用的负数只是先后编号，不代表任何年代数值。
      <strong>与上面的现实版本日期不可换算。</strong></p>
      {table(lore, 'teyvat')}
    </section>"""

    content = f"""
    <section class="hero">
      <div class="hero-kicker">KNOWLEDGE LAYER · TIMELINE</div>
      <h1>时间线</h1>
      <p>两条互不换算的时间线：现实世界的版本上线，与提瓦特世界里的事件先后。</p>
      <div class="stats-line">
        <a href="/timeline">全部</a> ·
        <a href="/timeline?era=release">只看版本上线</a> ·
        <a href="/timeline?era=teyvat">只看提瓦特纪年</a> ·
        <a href="/entities">实体卡片</a> · <a href="/">回到原文检索</a>
      </div>
    </section>
    {blocks}
    """
    return layout("时间线", content, "timeline")


def render_about() -> str:
    con = connect()
    try:
        st = stats(con)
        cov = coverage(con)
        pending = con.execute(
            "SELECT COUNT(*) FROM documents WHERE doc_type='quest' AND notes LIKE '%OBC 无剧情对话%'"
        ).fetchone()[0]
    finally:
        con.close()
    labels = [("type", "类型"), ("region", "地区"), ("version", "版本"),
              ("release_date", "上线日期"), ("spoiler", "剧透分级")]
    cov_rows = "".join(
        f"<tr><td>{label}</td><td>{cov['fields'][key]['filled']:,} / {cov['fields'][key]['total']:,}</td>"
        f"<td>{cov['fields'][key]['pct']}%</td><td>{esc(cov['fields'][key]['note'])}</td></tr>"
        for key, label in labels
    )
    content = f"""
    <section class="about">
      <div class="hero-kicker">ABOUT THIS DATABASE</div>
      <h1>一个本地、可检索的原神文本库</h1>
      <p class="lead">正文是 Markdown，SQLite 只做索引与检索。数据来自米游社观测枢和 BWiki，属于社区整理文本，不是官方逐字文本。</p>
      <div class="about-grid">
        <div><strong>{sum(st['by_type'].values()):,}</strong><span>文档</span></div>
        <div><strong>{st['sections']:,}</strong><span>段落</span></div>
        <div><strong>{st['by_type'].get('book', 0):,}</strong><span>书籍</span></div>
        <div><strong>{st['by_type'].get('quest', 0):,}</strong><span>任务</span></div>
        <div><strong>{pending:,}</strong><span>待补任务</span></div>
      </div>
      <h2>当前结构</h2>
      <pre><code>corpus/books/       书籍正文
corpus/quests/      任务正文
exports/obc-batch/  散落文本与待补任务
db/genshin_lore.sqlite3  索引</code></pre>
      <h2>使用方式</h2>
      <ul>
        <li>搜索框：3 字以上中文走 FTS5 trigram，2 字词自动回退 LIKE；</li>
        <li>筛选：类型、地区、版本（下拉选精确值）；剧透分级数据不足，筛选已下线；</li>
        <li>按地区/版本筛选时会明确提示有多少「未标注」文档被排除；</li>
        <li>文档页：正文、版本、来源、原始 Markdown；</li>
        <li>字段覆盖率也可通过 <code>/api/coverage</code> 读取；</li>
        <li>本页面只读，不会修改数据库或 Markdown。</li>
      </ul>
      <h2>筛选字段覆盖率</h2>
      <p>覆盖率不是「缺数据」的同义词：有些类型本来就没有该字段。留空按约定不猜。</p>
      <table class="cov-table">
        <thead><tr><th>字段</th><th>已标注</th><th>覆盖率</th><th>说明</th></tr></thead>
        <tbody>{cov_rows}</tbody>
      </table>
      <h2>声明</h2>
      <p>游戏文本版权归米哈游及原权利方所有。本库用于个人研究、检索和考据，不对外公开发布全文。</p>
    </section>
    """
    return layout("关于", content, "about")


class Handler(BaseHTTPRequestHandler):
    server_version = "GenshinLoreUI/1.0"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        args = parse_qs(parsed.query)
        try:
            if path == "/health":
                self.send_json({"ok": True, "db": str(DB), "docs": self._docs()})
                return
            if path in ("/", "/search"):
                self.send_html(render_search(args))
                return
            if path == "/entities":
                self.send_html(render_entities(args))
                return
            if path.startswith("/entity/"):
                page = render_entity_detail(unquote(path[len("/entity/"):]))
                if page is None:
                    self.send_html(layout("未找到", '<section class="empty-page"><h1>未找到实体</h1>'
                                          '<p>这个 entity_id 不在知识层里。</p>'
                                          '<a href="/entities">返回实体卡片</a></section>'), 404)
                else:
                    self.send_html(page)
                return
            if path == "/timeline":
                self.send_html(render_timeline(args))
                return
            if path == "/about":
                self.send_html(render_about())
                return
            if path.startswith("/doc/"):
                doc_id = path[len("/doc/"):]
                con = connect()
                try:
                    exists = con.execute("SELECT 1 FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
                finally:
                    con.close()
                if not exists:
                    self.send_html(layout("未找到", '<section class="empty-page"><h1>未找到文档</h1><p>这个 doc_id 不在数据库里。</p><a href="/">返回检索</a></section>'), 404)
                    return
                self.send_html(render_doc(doc_id))
                return
            if path.startswith("/raw/"):
                self.send_raw(path[len("/raw/"):])
                return
            if path == "/api/entities":
                self.send_json(self._api_entities(args))
                return
            if path == "/api/entity":
                self.send_json(self._api_entity(args))
                return
            if path == "/api/timeline":
                self.send_json(self._api_timeline(args))
                return
            if path == "/api/coverage":
                con = connect()
                try:
                    self.send_json(coverage(con))
                finally:
                    con.close()
                return
            if path.startswith("/api/search"):
                self.send_json(self._api_search(args))
                return
            if path.startswith("/api/doc/"):
                self.send_json(self._api_doc(path[len("/api/doc/"):]))
                return
            if path.startswith("/static/"):
                self.send_static(path[len("/static/"):])
                return
            if path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return
            self.send_html(layout("404", '<section class="empty-page"><h1>404</h1><p>没有这个页面。</p><a href="/">返回检索</a></section>'), "404")
        except Exception:
            traceback.print_exc()
            self.send_html(layout("错误", '<section class="empty-page"><h1>服务器错误</h1><p>请查看终端日志。</p></section>'), 500)

    def _docs(self) -> int:
        con = connect()
        try:
            return con.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        finally:
            con.close()

    def _api_entities(self, args: dict[str, list[str]]) -> dict:
        q = first(args, "q")
        etype = first(args, "type")
        con = connect()
        try:
            out = []
            for row in find_entities(con, q, limit=200, entity_type=etype):
                item = dict(row)
                item["aliases"] = entity_names(con, row["entity_id"])
                item["claims"] = [dict(c) for c in entity_claims(con, row["entity_id"])]
                outgoing, incoming = entity_relation_rows(con, row["entity_id"])
                item["relations_out"] = [dict(r) for r in outgoing]
                item["relations_in"] = [dict(r) for r in incoming]
                item["timeline"] = [dict(t) for t in
                                    entity_timeline_rows(con, row["entity_id"])]
                out.append(item)
        finally:
            con.close()
        return {"query": q, "type": etype, "count": len(out), "results": out}

    def _api_entity(self, args: dict[str, list[str]]) -> dict:
        entity_id = first(args, "id")
        con = connect()
        try:
            row = con.execute(
                "SELECT * FROM entities WHERE entity_id=?", (entity_id,)
            ).fetchone()
            if not row:
                return {"error": "entity not found", "id": entity_id}
            item = dict(row)
            item["aliases"] = entity_names(con, entity_id)
            item["claims"] = [dict(c) for c in entity_claims(con, entity_id)]
            item["evidence"] = [dict(e) for e in entity_evidence_rows(con, entity_id)]
            item["mention_docs"], item["mention_sections"], item["mention_quests"] = con.execute(
                """SELECT COUNT(DISTINCT s.doc_id), COUNT(*),
                          COUNT(DISTINCT CASE WHEN d.doc_type = 'quest' THEN s.doc_id END)
                   FROM sections s JOIN documents d ON d.doc_id = s.doc_id
                   WHERE s.body LIKE ?""",
                (f"%{row['canonical_name']}%",),
            ).fetchone()
            rel = entity_release(con, entity_id)
            item["release"] = dict(rel) if rel else None
            outgoing, incoming = entity_relation_rows(con, entity_id)
            item["relations_out"] = [dict(r) for r in outgoing]
            item["relations_in"] = [dict(r) for r in incoming]
            item["timeline"] = [dict(t) for t in entity_timeline_rows(con, entity_id)]
        finally:
            con.close()
        return item

    def _api_timeline(self, args: dict[str, list[str]]) -> dict:
        era = first(args, "era")
        con = connect()
        try:
            out = {}
            for key in ("release", "teyvat"):
                if era and era != key:
                    continue
                out[key] = [dict(r) for r in timeline_rows(con, key)]
        finally:
            con.close()
        return {"era": era or "all", "counts": {k: len(v) for k, v in out.items()},
                "note": "era=release 是现实世界版本上线日期；era=teyvat 是提瓦特纪年，只有相对顺序。两者不可换算。",
                "eras": out}

    def _api_search(self, args: dict[str, list[str]]) -> dict:
        q = first(args, "q")
        type_ = first(args, "type")
        region = first(args, "region")
        spoiler_raw = first(args, "spoiler")
        max_spoiler = int(spoiler_raw) if spoiler_raw.isdigit() else None
        version = first(args, "version")
        con = connect()
        try:
            results = search_docs(con, q, type_, region, max_spoiler, version, limit=100)
        finally:
            con.close()
        return {"query": q, "count": len(results), "results": results}

    def _api_doc(self, doc_id: str) -> dict:
        con = connect()
        try:
            doc = get_doc(con, doc_id)
        finally:
            con.close()
        if not doc:
            return {"error": "not found"}
        row = dict(doc["row"])
        return {"document": row, "sources": [dict(s) for s in doc["sources"]], "markdown": doc["body"]}

    def send_html(self, content: str, status: int = 200) -> None:
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, payload: dict | list, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def send_raw(self, doc_id: str) -> None:
        con = connect()
        try:
            doc = get_doc(con, doc_id)
        finally:
            con.close()
        if not doc:
            self.send_text("not found", 404)
            return
        self.send_text(doc["body"] if doc["body"] else doc["error"], 200)

    def send_text(self, text: str, status: int = 200) -> None:
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_static(self, name: str) -> None:
        path = (STATIC / name).resolve()
        if STATIC.resolve() not in path.parents or not path.exists() or not path.is_file():
            self.send_text("not found", 404)
            return
        data = path.read_bytes()
        content_type = "text/css; charset=utf-8" if path.suffix == ".css" else "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=300")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[webui] {self.address_string()} {fmt % args}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--log-file", default=None,
                        help="后台启动时把 stdout/stderr 追加写入该文件")
    args = parser.parse_args()
    if not DB.exists():
        raise SystemExit(f"database not found: {DB}")
    if args.log_file:
        log_path = Path(args.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log = log_path.open("a", encoding="utf-8", buffering=1)
        sys.stdout = log
        sys.stderr = log
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Genshin Lore UI: http://{args.host}:{args.port}/", flush=True)
    print(f"DB: {DB}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
