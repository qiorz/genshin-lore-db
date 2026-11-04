-- Genshin Lore DB — optional full-text index (SQLite FTS5)
-- Run after schema.sql.
--
-- Requires SQLite compiled with FTS5. Python's bundled sqlite3 on Windows
-- usually has it; verify with:
--   python -c "import sqlite3; sqlite3.connect(':memory:').execute('CREATE VIRTUAL TABLE t USING fts5(x)')"
--
-- Chinese search strategy:
--   1. ingest fills sections.body_segmented with jieba-segmented text;
--   2. FTS5 indexes both raw body (for English) and segmented body (for Chinese);
--   3. queries should target body_segmented for Chinese, body for English;
--   4. fall back to LIKE '%term%' for two-character terms or when FTS is absent.

-- Chinese search uses FTS5 trigram tokenization: no jieba dependency, and
-- 3+ character substrings can be searched directly. Two-character terms fall
-- back to LIKE in scripts/search.py.

CREATE VIRTUAL TABLE IF NOT EXISTS sections_fts USING fts5(
    heading,
    body,
    body_segmented,
    speaker,
    content = 'sections',
    content_rowid = 'section_id',
    tokenize = 'trigram'
);

-- Keep the external-content index in sync with sections.
CREATE TRIGGER IF NOT EXISTS sections_fts_ai
AFTER INSERT ON sections
BEGIN
    INSERT INTO sections_fts(rowid, heading, body, body_segmented, speaker)
    VALUES (new.section_id, new.heading, new.body, new.body_segmented, new.speaker);
END;

CREATE TRIGGER IF NOT EXISTS sections_fts_ad
AFTER DELETE ON sections
BEGIN
    INSERT INTO sections_fts(sections_fts, rowid, heading, body, body_segmented, speaker)
    VALUES ('delete', old.section_id, old.heading, old.body, old.body_segmented, old.speaker);
END;

CREATE TRIGGER IF NOT EXISTS sections_fts_au
AFTER UPDATE ON sections
BEGIN
    INSERT INTO sections_fts(sections_fts, rowid, heading, body, body_segmented, speaker)
    VALUES ('delete', old.section_id, old.heading, old.body, old.body_segmented, old.speaker);
    INSERT INTO sections_fts(rowid, heading, body, body_segmented, speaker)
    VALUES (new.section_id, new.heading, new.body, new.body_segmented, new.speaker);
END;

-- Rebuild if sections were loaded before the FTS table/triggers existed.
INSERT INTO sections_fts(sections_fts) VALUES ('rebuild');
