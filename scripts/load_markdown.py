#!/usr/bin/env python3
"""Load normalized Markdown files into the SQLite lore database.

This is a deliberately small first-pass loader:
  - reads YAML front matter
  - splits the body on level-2 headings
  - recognizes dialogue (`**speaker**：...`), options (`> 选项...`), and quotes
  - writes documents / document_sources / sections / tags
  - segments Chinese with jieba for FTS

It is idempotent per doc_id: re-running replaces the document's sections.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jieba
import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "db" / "genshin_lore.sqlite3"
DEFAULT_TERMS = ROOT / "manifests" / "terms.txt"
TZ = timezone(timedelta(hours=8))
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

SPEAKER_RE = re.compile(r"^\*\*([^*]+)\*\*[：:]\s*(.*)$")
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")


def read_front_matter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        raise ValueError("missing YAML front matter")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("unterminated YAML front matter")
    meta = yaml.safe_load(parts[1])
    if not isinstance(meta, dict):
        raise ValueError("front matter is not a mapping")
    return meta, parts[2].lstrip("\n")


def segment(text: str) -> str:
    return " ".join(token for token in jieba.cut_for_search(text) if token.strip())


def classify_line(line: str) -> tuple[str, str, str]:
    """Return (section_type, speaker, body)."""
    stripped = line.strip()
    if not stripped:
        return "blank", "", ""
    match = SPEAKER_RE.match(stripped)
    if match:
        return "dialogue", match.group(1).strip(), match.group(2).strip()
    if stripped.startswith("> 选项"):
        body = re.sub(r"^>\s*选项(?:（[^）]*）)?[：:]\s*", "", stripped)
        return "option", "", body
    if stripped.startswith(">"):
        return "quote", "", stripped.lstrip("> ").strip()
    return "text", "", stripped


def build_sections(body: str, spoiler_level: int) -> list[dict]:
    sections: list[dict] = []
    current_heading_id: int | None = None
    ordinal = 0
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph, ordinal
        if paragraph:
            text = "\n".join(paragraph).strip()
            if text:
                ordinal += 1
                sections.append(
                    {
                        "ordinal": ordinal,
                        "parent_heading": current_heading_id,
                        "heading": None,
                        "section_type": "text",
                        "speaker": None,
                        "body": text,
                        "spoiler_level": spoiler_level,
                    }
                )
            paragraph = []

    for line_no, line in enumerate(body.splitlines(), 1):
        heading = HEADING_RE.match(line)
        if heading:
            flush_paragraph()
            ordinal += 1
            sections.append(
                {
                    "ordinal": ordinal,
                    "parent_heading": current_heading_id,
                    "heading": heading.group(1).strip(),
                    "section_type": "heading",
                    "speaker": None,
                    "body": "",
                    "spoiler_level": spoiler_level,
                    "source_line": line_no,
                }
            )
            current_heading_id = ordinal
            continue

        if not line.strip():
            flush_paragraph()
            continue

        section_type, speaker, text = classify_line(line)
        if section_type in {"dialogue", "option", "quote"}:
            flush_paragraph()
            ordinal += 1
            sections.append(
                {
                    "ordinal": ordinal,
                    "parent_heading": current_heading_id,
                    "heading": None,
                    "section_type": section_type,
                    "speaker": speaker or None,
                    "body": text,
                    "spoiler_level": spoiler_level,
                    "source_line": line_no,
                }
            )
            continue

        if section_type == "text":
            paragraph.append(text)
            continue

    flush_paragraph()
    return sections


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--dir", action="append", type=Path, default=[])
    parser.add_argument("--pattern", default="*.md")
    parser.add_argument("--file-list", type=Path, help="one path per line")
    parser.add_argument("--bulk", action="store_true", help="one transaction; use after dropping FTS triggers")
    parser.add_argument("--no-segment", action="store_true", help="store raw body in body_segmented for trigram FTS")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--terms", type=Path, default=DEFAULT_TERMS)
    args = parser.parse_args()

    paths = list(args.paths)
    if args.file_list:
        paths.extend(
            Path(line.strip())
            for line in args.file_list.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    for directory in args.dir:
        if not directory.exists():
            raise SystemExit(f"directory not found: {directory}")
        paths.extend(sorted(directory.rglob(args.pattern)))
    if not paths:
        raise SystemExit("no Markdown files given; pass paths or --dir")

    if args.terms.exists():
        jieba.load_userdict(str(args.terms))

    con = sqlite3.connect(args.db)
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA temp_store = MEMORY")
    if args.bulk:
        con.execute("PRAGMA synchronous = OFF")
        con.execute("PRAGMA wal_autocheckpoint = 0")
        con.execute("PRAGMA cache_size = -200000")
    started_at = datetime.now(TZ).isoformat(timespec="seconds")

    loaded = 0
    section_total = 0
    for path in paths:
        print(f"reading {path.name}", flush=True)
        meta, body = read_front_matter(path.read_text(encoding="utf-8"))
        doc_id = meta["id"]
        source = (meta.get("source") or [{}])[0]
        source_id = source.get("source_id")
        source_row = con.execute(
            "SELECT 1 FROM sources WHERE source_id = ?", (source_id,)
        ).fetchone()
        if not source_row:
            raise SystemExit(f"{path}: unknown source_id {source_id!r}")

        content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
        spoiler = meta.get("spoiler") or {}
        spoiler_level = int(spoiler.get("level") or 0)
        sections = build_sections(body, spoiler_level)
        if not sections:
            print(f"skip {doc_id}: no sections parsed")
            continue

        try:
            normalized_path = str(path.resolve().relative_to(ROOT)).replace("\\", "/")
        except ValueError:
            normalized_path = str(path).replace("\\", "/")

        con.execute(
            """
            INSERT INTO documents (
                doc_id, doc_type, subtype, title, title_en, language, region,
                version, version_source, version_confidence, release_date,
                canon_status, transcription, spoiler_level, status,
                primary_source_id, source_url, source_page_id,
                source_revision, retrieved_at, normalized_path, content_hash,
                char_count, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(doc_id) DO UPDATE SET
                doc_type = excluded.doc_type,
                subtype = excluded.subtype,
                title = excluded.title,
                title_en = excluded.title_en,
                language = excluded.language,
                region = excluded.region,
                version = excluded.version,
                version_source = excluded.version_source,
                version_confidence = excluded.version_confidence,
                release_date = excluded.release_date,
                canon_status = excluded.canon_status,
                transcription = excluded.transcription,
                spoiler_level = excluded.spoiler_level,
                status = excluded.status,
                primary_source_id = excluded.primary_source_id,
                source_url = excluded.source_url,
                source_page_id = excluded.source_page_id,
                source_revision = excluded.source_revision,
                retrieved_at = excluded.retrieved_at,
                normalized_path = excluded.normalized_path,
                content_hash = excluded.content_hash,
                char_count = excluded.char_count,
                notes = excluded.notes,
                updated_at = datetime('now')
            """,
            (
                doc_id,
                meta["type"],
                meta.get("subtype"),
                meta["title"],
                meta.get("title_en"),
                meta.get("language", "zh-Hans"),
                meta.get("region"),
                str(meta["version"]) if meta.get("version") is not None else None,
                meta.get("version_source", "unknown"),
                meta.get("version_confidence", "unknown"),
                meta.get("release_date"),
                meta.get("canon_status", "unknown"),
                meta.get("transcription", "unknown"),
                spoiler_level,
                meta.get("status", "draft"),
                source_id,
                source.get("url"),
                source.get("page_id"),
                source.get("revision_id"),
                source.get("retrieved_at"),
                normalized_path,
                content_hash,
                len(body),
                meta.get("notes"),
            ),
        )

        con.execute("DELETE FROM sections WHERE doc_id = ?", (doc_id,))
        con.execute("DELETE FROM document_sources WHERE doc_id = ?", (doc_id,))
        con.execute("DELETE FROM document_tags WHERE doc_id = ?", (doc_id,))

        for source_index, item in enumerate(meta.get("source") or []):
            con.execute(
                """
                INSERT OR REPLACE INTO document_sources
                    (doc_id, source_id, url, page_id, revision_id, retrieved_at,
                     license, is_primary, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc_id,
                    item.get("source_id"),
                    item.get("url", ""),
                    item.get("page_id"),
                    item.get("revision_id"),
                    item.get("retrieved_at"),
                    item.get("license"),
                    1 if source_index == 0 else 0,
                    item.get("notes"),
                ),
            )

        all_tags = list(meta.get("tags") or [])
        all_tags += list((meta.get("spoiler") or {}).get("scope") or [])
        for tag in dict.fromkeys(all_tags):
            con.execute(
                "INSERT OR IGNORE INTO tags (tag, category) VALUES (?, ?)",
                (tag, "doc"),
            )
            con.execute(
                "INSERT OR IGNORE INTO document_tags (doc_id, tag) VALUES (?, ?)",
                (doc_id, tag),
            )

        con.execute(
            """
            INSERT OR IGNORE INTO document_revisions
                (doc_id, content_hash, source_revision, retrieved_at, change_summary)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                doc_id,
                content_hash,
                source.get("revision_id"),
                source.get("retrieved_at"),
                "loaded from corpus",
            ),
        )

        heading_map: dict[int, int] = {}
        for item in sections:
            parent_id = heading_map.get(item.get("parent_heading"))
            body_text = item.get("body") or ""
            try:
                con.execute(
                    """
                    INSERT INTO sections
                        (doc_id, parent_id, ordinal, heading, section_type, speaker,
                         body, body_segmented, spoiler_level, source_line)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        doc_id,
                        parent_id,
                        item["ordinal"],
                        item.get("heading"),
                        item["section_type"],
                        item.get("speaker"),
                        body_text,
                        body_text if args.no_segment else (segment(body_text) if body_text else None),
                        item.get("spoiler_level", spoiler_level),
                        item.get("source_line"),
                    ),
                )
            except Exception as exc:
                print(
                    f"FAILED section ordinal={item.get('ordinal')} "
                    f"type={item.get('section_type')} len={len(body_text)} "
                    f"parent={parent_id} sample={body_text[:80]!r}: {exc}",
                    file=sys.stderr,
                )
                raise
            if item["section_type"] == "heading":
                heading_map[item["ordinal"]] = con.execute(
                    "SELECT last_insert_rowid()"
                ).fetchone()[0]

        if not args.bulk:
            con.commit()
        loaded += 1
        section_total += len(sections)
        print(f"loaded {doc_id}: {len(sections)} sections, {len(body)} chars")

    print(f"done: {loaded} document(s), {section_total} section(s)")
    con.execute(
        """
        INSERT INTO ingest_runs
            (source_id, started_at, finished_at, status, documents_seen,
             documents_written, errors, notes)
        VALUES (NULL, ?, ?, 'success', ?, ?, 0, ?)
        """,
        (
            started_at,
            datetime.now(TZ).isoformat(timespec="seconds"),
            len(paths),
            loaded,
            "load_markdown.py",
        ),
    )
    con.commit()
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
