#!/usr/bin/env python3
"""Fill OBC quest pages that have no dialogue from BWiki subquest transcripts.

OBC sometimes only has a series/overview page; BWiki has the individual
subquest pages with `==任务剧情==`. This script fetches those pages, converts
the transcript to Markdown, and appends it under the original quest doc.

Run with --limit first; inspect the output before a full run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import requests
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "db" / "genshin_lore.sqlite3"
ENTRIES = ROOT / "raw" / "official_site" / "obc" / "entries"
CACHE = ROOT / "raw" / "bwiki" / "quest-transcripts"
REPORT = ROOT / "exports" / "obc-evaluation" / "bwiki-quest-fill.txt"
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
TZ = datetime.now().astimezone().tzinfo


def norm(text: str) -> str:
    return re.sub(r"[\s：:，,。.、·•「」『』《》【】（）()\-—…]+", "", text or "")


def clean(text: str) -> str:
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\{\{任务描述\|([^{}]*)\}\}", lambda m: m.group(1).rsplit("|", 1)[-1], text)
    text = re.sub(r"\{\{颜色\|[^|}]+\|([^{}]*)\}\}", r"\1", text)
    text = re.sub(r"\{\{黑幕\|([^{}]*)\}\}", r"\1", text)
    text = re.sub(r"\{\{ruby\|([^|{}]+)\|[^{}]*\}\}", r"\1", text)
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", text)
    text = text.replace("'''", "").replace("''", "")
    text = text.replace("&nbsp;", " ")
    return re.sub(r"[ \t]+", " ", text).strip()


def children(page: dict) -> list[str]:
    names: list[str] = []
    for module in page.get("modules") or []:
        if not any(c.get("component_id") == "base_info" for c in module.get("components") or []):
            continue
        name = (module.get("name") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def parse_transcript(wikitext: str) -> list[str]:
    match = re.search(r"==\s*任务剧情\s*==(.*?)(?=\n==[^=]|\Z)", wikitext, re.S)
    if not match:
        return []
    section = match.group(1)
    lines: list[str] = []
    for raw in section.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("==="):
            heading = clean(line.strip("="))
            if heading:
                lines.extend(["", f"### {heading}", ""])
            continue
        if line.startswith("::"):
            text = clean(line[2:])
            if text:
                lines.append(f"> *{text}*")
            continue
        if line.startswith("{{任务描述|"):
            text = clean(line)
            if text:
                lines.append(f"> *{text}*")
            continue
        if not line.startswith("*"):
            continue
        text = clean(line[1:].strip())
        if not text:
            continue
        match_line = re.match(r"^([^：:]{1,24})[：:]\s*(.+)$", text)
        if match_line:
            speaker, spoken = match_line.groups()
            lines.append(f"**{speaker.strip()}**：{spoken.strip()}")
        else:
            lines.append(f"> *{text}*")
    return lines


def parse_full(wikitext: str) -> list[str]:
    """Fallback for event pages whose dialogue is not under ==任务剧情==."""
    lines: list[str] = []
    for raw in wikitext.splitlines():
        line = raw.strip()
        if not line.startswith("*") or line.startswith("**"):
            continue
        text = clean(line[1:].strip())
        if not text or text.startswith(("[[", "#", "{{", "|", "END")):
            continue
        match = re.match(r"^([^：:]{1,24})\s*[：:]\s*(.+)$", text)
        if match:
            speaker, spoken = match.groups()
            lines.append(f"**{speaker.strip()}**：{spoken.strip()}")
    return lines


def parse_hangout(wikitext: str) -> list[str]:
    """Hangout pages use {{人物对话|左|speaker|text}} instead of bullet lines."""
    lines: list[str] = []
    for raw in wikitext.splitlines():
        line = raw.strip()
        heading = re.match(r"^=+\s*(.+?)\s*=+$", line)
        if heading:
            title = clean(heading.group(1))
            if title:
                lines.extend(["", f"### {title}", ""])
            continue
        for match in re.finditer(r"\{\{人物对话\|([^{}]*)\}\}", line):
            parts = [part.strip() for part in match.group(1).split("|")]
            if len(parts) < 3:
                continue
            speaker = clean(parts[1])
            text = clean("|".join(parts[2:]))
            if speaker and text:
                lines.append(f"**{speaker}**：{text}")
    return lines


def bwiki_page(session: requests.Session, title: str) -> dict | None:
    digest = hashlib.sha1(title.encode("utf-8")).hexdigest()[:16]
    cache = CACHE / f"{digest}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    search = session.get(
        "https://wiki.biligame.com/ys/api.php",
        params={"action": "query", "list": "search", "srsearch": title, "srlimit": 3, "format": "json"},
        timeout=30,
    ).json()
    results = (search.get("query") or {}).get("search") or []
    wanted = norm(title)
    chosen = None
    for result in results:
        candidate = result["title"]
        if wanted and (wanted == norm(candidate) or wanted in norm(candidate)):
            chosen = candidate
            break
    if not chosen and results:
        chosen = results[0]["title"]
    if not chosen:
        return None
    parse = session.get(
        "https://wiki.biligame.com/ys/api.php",
        params={"action": "parse", "page": chosen, "prop": "wikitext|revid", "format": "json", "formatversion": 2},
        timeout=30,
    ).json()
    data = parse.get("parse") or {}
    payload = {"title": title, "page": chosen, "revid": data.get("revid") or "", "wikitext": data.get("wikitext") or ""}
    CACHE.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    time.sleep(0.8)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    docs = con.execute(
        "SELECT doc_id, source_page_id, normalized_path, title, notes FROM documents d "
        "WHERE d.doc_type='quest' AND NOT EXISTS("
        " SELECT 1 FROM sections s WHERE s.doc_id=d.doc_id AND s.section_type='dialogue'"
        ") ORDER BY doc_id"
    ).fetchall()
    if args.limit:
        docs = docs[: args.limit]

    session = requests.Session()
    session.trust_env = False
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
            "Referer": "https://wiki.biligame.com/ys/",
        }
    )

    report = []
    filled_paths = []
    filled = 0
    for doc in docs:
        entry_path = ENTRIES / f"{doc['source_page_id']}.json"
        if not entry_path.exists():
            report.append((doc["doc_id"], doc["title"], "no raw"))
            continue
        page = json.loads(entry_path.read_text(encoding="utf-8"))["data"]["page"]
        names = children(page) or []
        for bracketed in re.findall(r"「([^」]+)」", doc["title"]):
            if bracketed not in names:
                names.append(bracketed)
        if doc["title"] not in names:
            names.append(doc["title"])
        queries = names[:6]
        initial = bwiki_page(session, doc["title"])
        if initial:
            for line in initial["wikitext"].splitlines():
                if "详细对话" not in line and "任务剧情" not in line:
                    continue
                for link in re.findall(r"\[\[([^\]|#]+)(?:\|[^\]]*)?\]\]", line):
                    link = link.strip()
                    if 2 <= len(link) <= 50 and link not in queries:
                        queries.append(link)
        queries = queries[:10]
        chunks: list[str] = []
        used: list[dict] = []
        seen_pages: set[str] = set()
        for name in queries:
            payload = bwiki_page(session, name)
            if not payload or payload["page"] in seen_pages:
                continue
            lines = parse_transcript(payload["wikitext"])
            if len([line for line in lines if line.startswith("**")]) < 2:
                lines = parse_hangout(payload["wikitext"])
            if len([line for line in lines if line.startswith("**")]) < 2:
                lines = parse_full(payload["wikitext"])
            if len([line for line in lines if line.startswith("**")]) < 2:
                continue
            seen_pages.add(payload["page"])
            chunks.extend(["", f"## {name}", ""])
            chunks.extend(lines)
            used.append(payload)
        if not chunks:
            report.append((doc["doc_id"], doc["title"], "no BWiki transcript"))
            continue

        path = ROOT / doc["normalized_path"]
        text = path.read_text(encoding="utf-8")
        parts = text.split("---", 2)
        front = yaml.safe_load(parts[1]) or {}
        old_body = parts[2]
        # Rebuild task-info from front matter; old body may already be missing it.
        labels = {
            "archon": "魔神任务",
            "story": "传说任务",
            "world": "世界任务",
            "event": "限时任务",
            "other": "其他任务",
        }
        info_lines = [
            "## 任务信息",
            "",
            f"- 类型：{labels.get(front.get('subtype'), front.get('subtype'))}",
        ]
        if front.get("region"):
            info_lines.append(f"- 地区：{front['region']}")
        if front.get("version"):
            info_lines.append(f"- 版本：{front['version']}")
        info_lines.append("- 来源：米游社·观测枢；BWiki")
        info = "\n".join(info_lines)
        body = info + "\n" + "\n".join(chunks).rstrip() + "\n"
        front["source"] = [
            source for source in (front.get("source") or []) if source.get("source_id") != "bwiki"
        ]
        seen_sources = set()
        for bwiki_source in used:
            if bwiki_source["page"] in seen_sources:
                continue
            front["source"].append(
                {
                    "source_id": "bwiki",
                    "url": "https://wiki.biligame.com/ys/" + quote(bwiki_source["page"]),
                    "page_id": bwiki_source["page"],
                    "revision_id": str(bwiki_source["revid"]),
                    "retrieved_at": datetime.now(TZ).isoformat(timespec="seconds"),
                    "license": "site-policy",
                }
            )
            seen_sources.add(bwiki_source["page"])
        front["notes"] = re.sub(
            r"(?:\s*BWiki 补全任务剧情：\d+ 个子任务页。)+", "", front.get("notes") or ""
        ).strip()
        front["notes"] += f" BWiki 补全任务剧情：{len(used)} 个子任务页。"
        yaml_text = yaml.safe_dump(front, allow_unicode=True, sort_keys=False, width=120)
        path.write_text(f"---\n{yaml_text}---\n\n{body}", encoding="utf-8", newline="\n")
        filled += 1
        filled_paths.append(str(path.resolve()))
        report.append((doc["doc_id"], doc["title"], f"filled {len(used)}/{len(names)}"))
        if filled % 5 == 0:
            print(f"filled {filled}/{len(docs)} ...", flush=True)

    REPORT.write_text(
        "\n".join(f"{doc_id} | {title} | {status}" for doc_id, title, status in report),
        encoding="utf-8",
    )
    (ROOT / "exports" / "obc-evaluation" / "bwiki-filled-paths.txt").write_text(
        "\n".join(filled_paths), encoding="utf-8"
    )
    print(f"filled={filled} total={len(docs)} report={REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
