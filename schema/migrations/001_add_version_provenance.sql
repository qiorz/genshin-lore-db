-- Add version provenance to documents.
-- Game version is not the same as the 观测枢 page.version.

ALTER TABLE documents
    ADD COLUMN version_source TEXT NOT NULL DEFAULT 'unknown'
    CHECK (version_source IN (
        'obc-filter', 'bwiki', 'official', 'manual',
        'derived-related-quest', 'web', 'unknown'
    ));

ALTER TABLE documents
    ADD COLUMN version_confidence TEXT NOT NULL DEFAULT 'unknown'
    CHECK (version_confidence IN (
        'confirmed', 'likely', 'inferred', 'estimated', 'unknown'
    ));
