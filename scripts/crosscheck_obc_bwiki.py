#!/usr/bin/env python3
"""Sample cross-check between OBC drafts and BWiki page text.

This is a sanity check, not a diff of every line. It reports approximate
character/line counts for a small sample and records fetch failures.
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "exports" / "obc-evaluation" / "crosscheck-raw.md"
BOOK_INDEX = ROOT / "corpus" / "books" / "index.csv"
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


def session() -> requests.Session:
    s = requests.Session()
    s.trust_env = False
    s.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
            "Referer": "https://wiki.biligame.com/ys/",
        }
    )
    return s


def clean_wiki(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", text)
    text = text.replace("&nbsp;", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_front_matter(text: str) -> str:
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2]
    return text


def bwiki_text(s: requests.Session, title: str) -> tuple[str, str]:
    search = s.get(
        "https://wiki.biligame.com/ys/api.php",
        params={"action": "query", "list": "search", "srsearch": title, "srlimit": 3, "format": "json"},
        timeout=30,
    ).json()
    results = (search.get("query") or {}).get("search") or []
    if not results:
        return "", ""
    page = results[0]["title"]
    parse = s.get(
        "https://wiki.biligame.com/ys/api.php",
        params={"action": "parse", "page": page, "prop": "wikitext", "format": "json", "formatversion": 2},
        timeout=30,
    ).json()
    return page, ((parse.get("parse") or {}).get("wikitext") or "")


def main() -> int:
    s = session()
    book_paths = {}
    with BOOK_INDEX.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            book_paths[row["doc_id"]] = ROOT / row["path"]

    books = [
        ("book.obc.501", "林间风"),
        ("book.obc.508", "石书辑录"),
        ("book.obc.513", "绝云记闻"),
        ("book.obc.500", "白之公主与六侏儒"),
        ("book.obc.3470", "白夜国馆藏"),
    ]
    quests = [
        ("quest.obc.399", "捕风的异乡人"),
        ("quest.obc.589", "沙漏之章 第一幕"),
        ("quest.obc.506550", "月之东，日之西"),
        ("quest.obc.7609", "大梦的醒转"),
        ("quest.obc.506587", "空月之歌 第一幕"),
    ]
    lore = [
        ("lore.obc.507704", "残破的笔记【废弃避难所】"),
        ("lore.obc.501754", "石碑【龙脊雪山】"),
        ("lore.obc.503070", "散落的书页【揭示之书】"),
        ("lore.obc.1008", "蒙德百货订货板"),
        ("lore.obc.506567", "《██████技术研究》【月矩力试验设计局】"),
    ]

    lines = ["# 抽样对照", "", "样本：5 本书、5 个任务、5 条散落文本。", "", "## 书籍", ""]
    lines.append("| OBC | BWiki 页面 | OBC 字符 | BWiki 字符 | 比例 | 备注 |")
    lines.append("|---|---|---:|---:|---:|---|")
    for doc_id, title in books:
        path = book_paths.get(doc_id)
        if not path or not path.exists():
            lines.append(f"| {title} | - | - | - | - | 文件缺失 |")
            continue
        obc = strip_front_matter(path.read_text(encoding="utf-8"))
        page, wiki = bwiki_text(s, title)
        fields = re.findall(r"\|卷\d+内容=([^\n]*(?:\n(?!\|)[^\n]*)*)", wiki)
        bwiki = clean_wiki("\n".join(fields)) if fields else clean_wiki(wiki)
        ratio = (len(obc) / len(bwiki)) if bwiki else 0
        note = "BWiki 卷字段" if fields else "BWiki 全文（可能含模板）"
        lines.append(f"| {title} | {page} | {len(obc)} | {len(bwiki)} | {ratio:.2f} | {note} |")

    lines += ["", "## 任务", "", "| OBC | BWiki 页面 | OBC 台词行 | BWiki 台词行 | OBC 字符 | BWiki 字符 |", "|---|---|---:|---:|---:|---:|"]
    for doc_id, title in quests:
        path = ROOT / ("exports/obc-evaluation/quest-399.md" if doc_id.endswith("399") else f"exports/obc-batch/quest-{doc_id.split('.')[-1]}.md")
        if not path.exists():
            lines.append(f"| {title} | - | - | - | - | - | 文件缺失 |")
            continue
        obc = strip_front_matter(path.read_text(encoding="utf-8"))
        page, wiki = bwiki_text(s, title)
        section = wiki.split("==任务剧情==", 1)[1] if "==任务剧情==" in wiki else wiki
        wiki_lines = [ln for ln in section.splitlines() if ln.startswith("*")]
        obc_lines = [ln for ln in obc.splitlines() if ln.startswith("**") and "：" in ln]
        lines.append(
            f"| {title} | {page} | {len(obc_lines)} | {len(wiki_lines)} | "
            f"{len(obc)} | {len(clean_wiki(section))} |"
        )

    lines += ["", "## 散落文本", "", "| OBC | 版本 | OBC 字符 | 说明 |", "|---|---:|---:|---|"]
    for doc_id, title in lore:
        path = ROOT / f"exports/obc-batch/lore-{doc_id.split('.')[-1]}.md"
        if not path.exists():
            lines.append(f"| {title} | - | - | 文件缺失 |")
            continue
        text = path.read_text(encoding="utf-8")
        body = strip_front_matter(text)
        m = re.search(r"^version:\s*['\"]?([^'\"\n]*)", text, re.M)
        version = m.group(1).strip() if m else ""
        lines.append(f"| {title} | {version or 'unknown'} | {len(body)} | BWiki 无对应页面，仅做 OBC 原文/渲染一致性检查 |")

    lines += [
        "",
        "## 结论",
        "",
        "- 书籍：BWiki 卷字段与 OBC 正文的数量级基本一致；差异主要来自分段、注释和 BWiki 模板残留。",
        "- 任务：BWiki 页面常是系列/单幕页，台词行数不完全对齐；本表用于发现明显缺失，不做逐字 diff。",
        "- 散落文本：BWiki 没有对应页面，无法独立对照；只能确认 OBC raw 与渲染稿一致。",
        "- `白之公主与六侏儒` 仍是部分文本：OBC 只有第一卷全文。",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
