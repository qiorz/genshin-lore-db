-- Replace the unicode61 FTS index with a trigram index.
-- Run only when sections_fts exists with the old tokenizer.

DROP TRIGGER IF EXISTS sections_fts_ai;
DROP TRIGGER IF EXISTS sections_fts_ad;
DROP TRIGGER IF EXISTS sections_fts_au;
DROP TABLE IF EXISTS sections_fts;

CREATE VIRTUAL TABLE sections_fts USING fts5(
    heading,
    body,
    body_segmented,
    speaker,
    content = 'sections',
    content_rowid = 'section_id',
    tokenize = 'trigram'
);

CREATE TRIGGER sections_fts_ai
AFTER INSERT ON sections
BEGIN
    INSERT INTO sections_fts(rowid, heading, body, body_segmented, speaker)
    VALUES (new.section_id, new.heading, new.body, new.body_segmented, new.speaker);
END;

CREATE TRIGGER sections_fts_ad
AFTER DELETE ON sections
BEGIN
    INSERT INTO sections_fts(sections_fts, rowid, heading, body, body_segmented, speaker)
    VALUES ('delete', old.section_id, old.heading, old.body, old.body_segmented, old.speaker);
END;

CREATE TRIGGER sections_fts_au
AFTER UPDATE ON sections
BEGIN
    INSERT INTO sections_fts(sections_fts, rowid, heading, body, body_segmented, speaker)
    VALUES ('delete', old.section_id, old.heading, old.body, old.body_segmented, old.speaker);
    INSERT INTO sections_fts(rowid, heading, body, body_segmented, speaker)
    VALUES (new.section_id, new.heading, new.body, new.body_segmented, new.speaker);
END;

INSERT INTO sections_fts(sections_fts) VALUES ('rebuild');
