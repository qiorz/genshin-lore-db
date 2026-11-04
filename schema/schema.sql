-- Genshin Lore DB — core schema (SQLite 3.35+)
-- Run after: PRAGMA foreign_keys = ON;
-- FTS is optional and lives in schema/fts.sql.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

BEGIN;

-- ---------------------------------------------------------------------------
-- 0. Metadata
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS meta (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO meta (key, value) VALUES
    ('schema_version', '1'),
    ('project', 'genshin-lore-db'),
    ('default_language', 'zh-Hans');

-- ---------------------------------------------------------------------------
-- 1. Sources and documents
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sources (
    source_id       TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    kind            TEXT NOT NULL CHECK (kind IN (
                        'official', 'official-community', 'official-wiki',
                        'wiki', 'datamine', 'fan', 'other'
                    )),
    base_url        TEXT,
    language        TEXT NOT NULL DEFAULT 'zh-Hans',
    license         TEXT,
    access_method   TEXT,
    priority        INTEGER NOT NULL DEFAULT 100,
    status          TEXT NOT NULL DEFAULT 'active' CHECK (status IN (
                        'active', 'limited', 'blocked', 'deprecated', 'unknown'
                    )),
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS documents (
    doc_id              TEXT PRIMARY KEY,
    doc_type            TEXT NOT NULL CHECK (doc_type IN (
                            'quest', 'book', 'character', 'weapon', 'artifact',
                            'item', 'voice', 'geography', 'event', 'manga',
                            'notice', 'lore', 'other'
                        )),
    subtype             TEXT,
    title               TEXT NOT NULL,
    title_en            TEXT,
    language            TEXT NOT NULL DEFAULT 'zh-Hans',
    region              TEXT,
    version             TEXT,
    version_source      TEXT NOT NULL DEFAULT 'unknown' CHECK (version_source IN (
                            'obc-filter', 'bwiki', 'official', 'manual',
                            'derived-related-quest', 'web', 'unknown'
                        )),
    version_confidence  TEXT NOT NULL DEFAULT 'unknown' CHECK (version_confidence IN (
                            'confirmed', 'likely', 'inferred', 'estimated', 'unknown'
                        )),
    release_date        TEXT,
    canon_status        TEXT NOT NULL DEFAULT 'unknown' CHECK (canon_status IN (
                            'official', 'official-secondary', 'community',
                            'datamine', 'fan', 'unknown'
                        )),
    transcription       TEXT NOT NULL DEFAULT 'unknown' CHECK (transcription IN (
                            'verbatim', 'near-verbatim', 'edited', 'summary', 'unknown'
                        )),
    spoiler_level       INTEGER NOT NULL DEFAULT 0 CHECK (spoiler_level BETWEEN 0 AND 3),
    status              TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
                            'draft', 'reviewed', 'stable', 'deprecated'
                        )),
    primary_source_id   TEXT REFERENCES sources(source_id) ON DELETE SET NULL,
    source_url          TEXT,
    source_page_id      TEXT,
    source_revision     TEXT,
    retrieved_at        TEXT,
    raw_path            TEXT,
    normalized_path     TEXT,
    content_hash        TEXT,
    char_count          INTEGER NOT NULL DEFAULT 0,
    notes               TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_documents_type
    ON documents(doc_type, subtype);
CREATE INDEX IF NOT EXISTS idx_documents_region
    ON documents(region);
CREATE INDEX IF NOT EXISTS idx_documents_version
    ON documents(version);
CREATE INDEX IF NOT EXISTS idx_documents_status
    ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_spoiler
    ON documents(spoiler_level);
CREATE INDEX IF NOT EXISTS idx_documents_source
    ON documents(primary_source_id);
CREATE INDEX IF NOT EXISTS idx_documents_hash
    ON documents(content_hash)
    WHERE content_hash IS NOT NULL;

-- 一篇文档可以有多个来源；第一个 is_primary=1。
CREATE TABLE IF NOT EXISTS document_sources (
    doc_id          TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    source_id       TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    url             TEXT NOT NULL,
    page_id         TEXT,
    revision_id     TEXT,
    retrieved_at    TEXT,
    license         TEXT,
    is_primary      INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0, 1)),
    notes           TEXT,
    PRIMARY KEY (doc_id, source_id, url)
);

CREATE INDEX IF NOT EXISTS idx_document_sources_source
    ON document_sources(source_id);

CREATE TABLE IF NOT EXISTS document_aliases (
    doc_id          TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    alias           TEXT NOT NULL,
    language        TEXT NOT NULL DEFAULT 'zh-Hans',
    alias_type      TEXT NOT NULL DEFAULT 'title' CHECK (alias_type IN (
                        'title', 'subtitle', 'abbreviation', 'translation', 'other'
                    )),
    PRIMARY KEY (doc_id, alias, language)
);

-- 每次内容变化都追加一条；documents.content_hash 只保存当前版本。
CREATE TABLE IF NOT EXISTS document_revisions (
    revision_pk     INTEGER PRIMARY KEY,
    doc_id          TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    content_hash    TEXT NOT NULL,
    source_revision TEXT,
    retrieved_at    TEXT,
    raw_path        TEXT,
    change_summary  TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (doc_id, content_hash)
);

CREATE INDEX IF NOT EXISTS idx_document_revisions_doc
    ON document_revisions(doc_id, created_at);

CREATE TABLE IF NOT EXISTS tags (
    tag         TEXT PRIMARY KEY,
    category    TEXT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS document_tags (
    doc_id  TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    tag     TEXT NOT NULL REFERENCES tags(tag) ON DELETE CASCADE,
    PRIMARY KEY (doc_id, tag)
);

CREATE TABLE IF NOT EXISTS document_links (
    from_doc_id     TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    to_doc_id       TEXT REFERENCES documents(doc_id) ON DELETE SET NULL,
    to_title        TEXT,
    relation        TEXT NOT NULL DEFAULT 'related' CHECK (relation IN (
                        'related', 'prequel', 'sequel', 'translation_of',
                        'adaptation_of', 'source_of', 'other'
                    )),
    notes           TEXT,
    CHECK (to_doc_id IS NOT NULL OR to_title IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_document_links_from
    ON document_links(from_doc_id);
CREATE INDEX IF NOT EXISTS idx_document_links_to
    ON document_links(to_doc_id);

-- ---------------------------------------------------------------------------
-- 2. Sections: headings, paragraphs, dialogue, options
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sections (
    section_id      INTEGER PRIMARY KEY,
    doc_id          TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    parent_id       INTEGER REFERENCES sections(section_id) ON DELETE CASCADE,
    ordinal         INTEGER NOT NULL,
    heading         TEXT,
    section_type    TEXT NOT NULL DEFAULT 'text' CHECK (section_type IN (
                        'heading', 'text', 'dialogue', 'option',
                        'note', 'quote', 'table'
                    )),
    speaker         TEXT,
    body            TEXT NOT NULL DEFAULT '',
    body_segmented  TEXT,
    spoiler_level   INTEGER NOT NULL DEFAULT 0 CHECK (spoiler_level BETWEEN 0 AND 3),
    source_line     INTEGER,
    UNIQUE (doc_id, ordinal)
);

CREATE INDEX IF NOT EXISTS idx_sections_doc
    ON sections(doc_id, ordinal);
CREATE INDEX IF NOT EXISTS idx_sections_speaker
    ON sections(speaker);
CREATE INDEX IF NOT EXISTS idx_sections_type
    ON sections(section_type);

-- Required for fast ON DELETE CASCADE from sections.parent_id.
CREATE INDEX IF NOT EXISTS idx_sections_parent
    ON sections(parent_id);

-- ---------------------------------------------------------------------------
-- 3. Knowledge layer: entities, relations, claims
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS entities (
    entity_id       TEXT PRIMARY KEY,
    entity_type     TEXT NOT NULL CHECK (entity_type IN (
                        'character', 'nation', 'organization', 'location',
                        'deity', 'creature', 'concept', 'event', 'item',
                        'title', 'other'
                    )),
    canonical_name  TEXT NOT NULL,
    canonical_name_en TEXT,
    description     TEXT,
    spoiler_level   INTEGER NOT NULL DEFAULT 0 CHECK (spoiler_level BETWEEN 0 AND 3),
    status          TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
                        'draft', 'reviewed', 'stable', 'deprecated'
                    )),
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_entities_type
    ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_name
    ON entities(canonical_name);

CREATE TABLE IF NOT EXISTS entity_names (
    entity_id   TEXT NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    language    TEXT NOT NULL DEFAULT 'zh-Hans',
    name_type   TEXT NOT NULL DEFAULT 'alias' CHECK (name_type IN (
                    'canonical', 'alias', 'title', 'epithet',
                    'cryptic', 'romanization', 'translation'
                )),
    source_id   TEXT REFERENCES sources(source_id) ON DELETE SET NULL,
    is_primary  INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0, 1)),
    PRIMARY KEY (entity_id, name, language)
);

CREATE INDEX IF NOT EXISTS idx_entity_names_name
    ON entity_names(name);

CREATE TABLE IF NOT EXISTS entity_relations (
    relation_id     INTEGER PRIMARY KEY,
    subject_id      TEXT NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    predicate       TEXT NOT NULL,
    object_id       TEXT REFERENCES entities(entity_id) ON DELETE CASCADE,
    object_literal  TEXT,
    qualifier       TEXT,
    confidence      TEXT NOT NULL DEFAULT 'confirmed' CHECK (confidence IN (
                        'confirmed', 'likely', 'speculative', 'disputed', 'unreliable'
                    )),
    source_id       TEXT REFERENCES sources(source_id) ON DELETE SET NULL,
    doc_id          TEXT REFERENCES documents(doc_id) ON DELETE SET NULL,
    section_id      INTEGER REFERENCES sections(section_id) ON DELETE SET NULL,
    spoiler_level   INTEGER NOT NULL DEFAULT 0 CHECK (spoiler_level BETWEEN 0 AND 3),
    notes           TEXT,
    CHECK (object_id IS NOT NULL OR object_literal IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_relations_subject
    ON entity_relations(subject_id, predicate);
CREATE INDEX IF NOT EXISTS idx_relations_object
    ON entity_relations(object_id, predicate);
CREATE INDEX IF NOT EXISTS idx_relations_doc
    ON entity_relations(doc_id);

CREATE TABLE IF NOT EXISTS claims (
    claim_id        INTEGER PRIMARY KEY,
    subject_id      TEXT REFERENCES entities(entity_id) ON DELETE SET NULL,
    subject_literal TEXT,
    predicate       TEXT NOT NULL,
    object_id       TEXT REFERENCES entities(entity_id) ON DELETE SET NULL,
    object_literal  TEXT,
    statement       TEXT NOT NULL,
    perspective     TEXT,
    confidence      TEXT NOT NULL DEFAULT 'likely' CHECK (confidence IN (
                        'confirmed', 'likely', 'speculative', 'disputed', 'unreliable'
                    )),
    status          TEXT NOT NULL DEFAULT 'open' CHECK (status IN (
                        'open', 'accepted', 'disputed', 'rejected', 'superseded'
                    )),
    source_id       TEXT REFERENCES sources(source_id) ON DELETE SET NULL,
    doc_id          TEXT REFERENCES documents(doc_id) ON DELETE SET NULL,
    section_id      INTEGER REFERENCES sections(section_id) ON DELETE SET NULL,
    spoiler_level   INTEGER NOT NULL DEFAULT 0 CHECK (spoiler_level BETWEEN 0 AND 3),
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (subject_id IS NOT NULL OR subject_literal IS NOT NULL),
    CHECK (object_id IS NOT NULL OR object_literal IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_claims_subject
    ON claims(subject_id, predicate);
CREATE INDEX IF NOT EXISTS idx_claims_doc
    ON claims(doc_id);
CREATE INDEX IF NOT EXISTS idx_claims_status
    ON claims(status, confidence);

-- ---------------------------------------------------------------------------
-- 4. Events and timeline
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS events (
    event_id        TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    event_type      TEXT,
    era             TEXT,
    start_year      INTEGER,
    end_year        INTEGER,
    time_certainty  TEXT NOT NULL DEFAULT 'unknown' CHECK (time_certainty IN (
                        'exact', 'approximate', 'relative', 'unknown'
                    )),
    description     TEXT,
    spoiler_level   INTEGER NOT NULL DEFAULT 0 CHECK (spoiler_level BETWEEN 0 AND 3),
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS event_sources (
    event_source_id INTEGER PRIMARY KEY,
    event_id        TEXT NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
    doc_id          TEXT REFERENCES documents(doc_id) ON DELETE SET NULL,
    section_id      INTEGER REFERENCES sections(section_id) ON DELETE SET NULL,
    source_id       TEXT REFERENCES sources(source_id) ON DELETE SET NULL,
    notes           TEXT
);

CREATE INDEX IF NOT EXISTS idx_event_sources_event
    ON event_sources(event_id);

CREATE TABLE IF NOT EXISTS timeline_entries (
    entry_id        INTEGER PRIMARY KEY,
    event_id        TEXT REFERENCES events(event_id) ON DELETE CASCADE,
    sort_key        REAL NOT NULL,
    label           TEXT NOT NULL,
    relative_time   TEXT,
    absolute_year   INTEGER,
    era             TEXT,
    certainty       TEXT NOT NULL DEFAULT 'unknown' CHECK (certainty IN (
                        'exact', 'approximate', 'relative', 'unknown'
                    )),
    source_id       TEXT REFERENCES sources(source_id) ON DELETE SET NULL,
    doc_id          TEXT REFERENCES documents(doc_id) ON DELETE SET NULL,
    section_id      INTEGER REFERENCES sections(section_id) ON DELETE SET NULL,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_timeline_sort
    ON timeline_entries(sort_key);

-- ---------------------------------------------------------------------------
-- 5. Operations: ingest runs, coverage, reading progress
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ingest_runs (
    run_id              INTEGER PRIMARY KEY,
    source_id           TEXT REFERENCES sources(source_id) ON DELETE SET NULL,
    started_at          TEXT NOT NULL,
    finished_at         TEXT,
    status              TEXT NOT NULL CHECK (status IN (
                            'running', 'success', 'partial', 'failed'
                        )),
    documents_seen      INTEGER NOT NULL DEFAULT 0,
    documents_written   INTEGER NOT NULL DEFAULT 0,
    errors              INTEGER NOT NULL DEFAULT 0,
    log_path            TEXT,
    notes               TEXT
);

CREATE TABLE IF NOT EXISTS coverage_targets (
    target_id       TEXT PRIMARY KEY,
    category        TEXT NOT NULL,
    scope           TEXT,
    priority        INTEGER NOT NULL DEFAULT 100,
    target_count    INTEGER,
    current_count   INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
                        'pending', 'in-progress', 'done', 'blocked', 'na'
                    )),
    source_hint     TEXT,
    notes           TEXT,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reading_progress (
    scope           TEXT PRIMARY KEY,
    status          TEXT NOT NULL DEFAULT 'unstarted' CHECK (status IN (
                        'unstarted', 'in-progress', 'completed'
                    )),
    last_doc_id     TEXT REFERENCES documents(doc_id) ON DELETE SET NULL,
    last_section_id INTEGER REFERENCES sections(section_id) ON DELETE SET NULL,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- 6. Views
-- ---------------------------------------------------------------------------

CREATE VIEW IF NOT EXISTS v_document_stats AS
SELECT
    d.doc_id,
    d.title,
    d.doc_type,
    d.subtype,
    d.region,
    d.version,
    d.status,
    d.spoiler_level,
    COUNT(s.section_id) AS section_count,
    COALESCE(SUM(LENGTH(s.body)), 0) AS char_count
FROM documents d
LEFT JOIN sections s ON s.doc_id = d.doc_id
GROUP BY d.doc_id, d.title, d.doc_type, d.subtype,
         d.region, d.version, d.status, d.spoiler_level;

CREATE VIEW IF NOT EXISTS v_duplicate_hashes AS
SELECT
    content_hash,
    COUNT(*) AS n,
    GROUP_CONCAT(doc_id, ', ') AS docs
FROM documents
WHERE content_hash IS NOT NULL
GROUP BY content_hash
HAVING COUNT(*) > 1;

CREATE VIEW IF NOT EXISTS v_missing_sources AS
SELECT doc_id, title, doc_type, status
FROM documents
WHERE primary_source_id IS NULL
   OR source_url IS NULL
   OR retrieved_at IS NULL;

CREATE VIEW IF NOT EXISTS v_unresolved_links AS
SELECT from_doc_id, to_title, relation
FROM document_links
WHERE to_doc_id IS NULL;

CREATE VIEW IF NOT EXISTS v_entity_overview AS
SELECT
    e.entity_id,
    e.entity_type,
    e.canonical_name,
    e.spoiler_level,
    COUNT(DISTINCT r.relation_id) AS outgoing_relations,
    COUNT(DISTINCT n.name) AS alias_count
FROM entities e
LEFT JOIN entity_relations r ON r.subject_id = e.entity_id
LEFT JOIN entity_names n ON n.entity_id = e.entity_id
GROUP BY e.entity_id, e.entity_type, e.canonical_name, e.spoiler_level;

PRAGMA user_version = 1;

COMMIT;
