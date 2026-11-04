-- Deleting a document's sections cascades through sections.parent_id. Without
-- an index on parent_id SQLite scans the whole sections table for each delete,
-- which makes reloading a large document take minutes.

CREATE INDEX IF NOT EXISTS idx_sections_parent
    ON sections(parent_id);
