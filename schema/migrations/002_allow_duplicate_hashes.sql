-- Exact text can occur at multiple locations (same inscription, different
-- entries) and still be a distinct document. Keep a non-unique hash index for
-- duplicate reporting instead of rejecting the second document.

DROP INDEX IF EXISTS idx_documents_hash_unique;
CREATE INDEX IF NOT EXISTS idx_documents_hash
    ON documents(content_hash)
    WHERE content_hash IS NOT NULL;
