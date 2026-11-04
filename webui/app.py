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
}
TYPE_ORDER = ["book", "quest", "lore", "character"]
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
SPOILER_LABELS = {0: "无剧透", 1: "轻度", 2: "中度", 3: "重度"}
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
        filters.append("d.version LIKE ?")
        params.append(f"%{version}%")
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
                "region": row["region"] or "未知",
                "version": row["version"] or "未知",
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


def search_form(q: str, type_: str, region: str, spoiler: str, version: str, region_rows: list) -> str:
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
    spoiler_options = ['<option value="">全部剧透等级</option>']
    for level, label in SPOILER_LABELS.items():
        selected = " selected" if spoiler == str(level) else ""
        spoiler_options.append(f'<option value="{level}"{selected}>{level} · {label}</option>')
    return f"""
    <form class="search-form" action="/search" method="get">
      <input type="search" name="q" value="{esc(q)}" placeholder="搜索书名、任务、人物、地名、台词…" autofocus>
      <button type="submit">检索</button>
    </form>
    <div class="filters">
      <form id="filter-form" action="/search" method="get" class="filter-form">
        <input type="hidden" name="q" value="{esc(q)}">
        <select name="type">{''.join(type_options)}</select>
        <select name="region">{''.join(region_options)}</select>
        <select name="spoiler">{''.join(spoiler_options)}</select>
        <input type="text" name="version" value="{esc(version)}" placeholder="版本，如 4.0">
        <button type="submit" class="ghost">筛选</button>
      </form>
    </div>
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
        results = search_docs(con, q, type_, region, max_spoiler, version)
    finally:
        con.close()

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
      {search_form(q, type_, region, spoiler_raw, version, region_rows)}
      <div class="stats-line">{counts} · 段落 {st['sections']:,} · 待补任务 {st['pending']}</div>
    </section>
    <section class="results-head">
      <div><h2>{heading}</h2><p>{summary}</p></div>
      <a class="ghost" href="/">重置</a>
    </section>
    <section class="results">{''.join(cards)}</section>
    {pager}
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


def render_about() -> str:
    con = connect()
    try:
        st = stats(con)
        pending = con.execute(
            "SELECT COUNT(*) FROM documents WHERE doc_type='quest' AND notes LIKE '%OBC 无剧情对话%'"
        ).fetchone()[0]
    finally:
        con.close()
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
        <li>筛选：类型、地区、剧透等级、版本；</li>
        <li>文档页：正文、版本、来源、原始 Markdown；</li>
        <li>本页面只读，不会修改数据库或 Markdown。</li>
      </ul>
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
    args = parser.parse_args()
    if not DB.exists():
        raise SystemExit(f"database not found: {DB}")
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
