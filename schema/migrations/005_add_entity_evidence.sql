-- 第三批扩量实体（seed-stage3.yaml）只有「原文出处」，没有说法（claims）。
-- 之前这些出处只存在于种子 YAML 和生成的 Markdown 卡片里，没有进库，
-- 于是 WebUI 详情页的「关联原文」对 70 张卡片全部显示 0。
-- 这里补一张轻量表：实体 → 原文哪一篇、哪一段、哪一句。
-- 与 claims 的区别：claims 是带视角的断言；entity_evidence 只回答「原文提到过它」。

CREATE TABLE IF NOT EXISTS entity_evidence (
    evidence_id     INTEGER PRIMARY KEY,
    entity_id       TEXT NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    doc_id          TEXT REFERENCES documents(doc_id) ON DELETE SET NULL,
    section_id      INTEGER REFERENCES sections(section_id) ON DELETE SET NULL,
    quote           TEXT NOT NULL,
    is_primary      INTEGER NOT NULL DEFAULT 1 CHECK (is_primary IN (0, 1)),
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_entity_evidence_entity
    ON entity_evidence(entity_id, doc_id);
CREATE INDEX IF NOT EXISTS idx_entity_evidence_doc
    ON entity_evidence(doc_id);
