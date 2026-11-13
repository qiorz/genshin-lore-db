-- 推论层：把散落在多篇文档里的隐晦线索串成可追溯的结论。
--
-- 为什么单开两张表，而不是塞进 claims：
--   claims 的一句说法只挂一个 section_id（单出处），且语义是「谁相信什么」。
--   推论恰恰相反：一个结论要靠多条证据（跨文档、跨类型）支撑，
--   其中有的直接陈述、有的只是暗示，还可能存在反证。
--
-- 证据同样不硬编码 section_id：只写 doc_id + 短引用，
-- 灌库时现场解析（见 scripts/load_theories.py，复用 load_knowledge.resolve）。
-- 这样 corpus 重切段落后 section_id 变了，重灌一次即可复原。

CREATE TABLE IF NOT EXISTS theories (
    theory_id       TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    claim           TEXT NOT NULL,
    confidence      TEXT NOT NULL DEFAULT 'speculative' CHECK (confidence IN (
                        'confirmed', 'likely', 'disputed', 'speculative', 'open'
                    )),
    status          TEXT NOT NULL DEFAULT 'open' CHECK (status IN (
                        'open', 'resolved', 'dropped'
                    )),
    spoiler_level   INTEGER NOT NULL DEFAULT 0 CHECK (spoiler_level BETWEEN 0 AND 3),
    aliases         TEXT,
    open_questions  TEXT,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS theory_evidence (
    theory_id   TEXT NOT NULL REFERENCES theories(theory_id) ON DELETE CASCADE,
    ordinal     INTEGER NOT NULL,
    doc_id      TEXT NOT NULL REFERENCES documents(doc_id),
    section_id  INTEGER REFERENCES sections(section_id),
    body        TEXT,
    quote       TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'direct' CHECK (kind IN (
                    'direct',        -- 原文直接陈述
                    'implied',       -- 隐晦暗示，需联想
                    'corroboration', -- 他处旁证/呼应
                    'counter'        -- 反证或矛盾
                )),
    note        TEXT,
    PRIMARY KEY (theory_id, ordinal)
);

CREATE INDEX IF NOT EXISTS idx_theory_evidence_doc ON theory_evidence(doc_id);
CREATE INDEX IF NOT EXISTS idx_theory_evidence_section ON theory_evidence(section_id);

-- 覆盖统计：一条结论有几条证据、跨几篇文档、几类文本、几条是反证
CREATE VIEW IF NOT EXISTS v_theory_coverage AS
SELECT t.theory_id,
       t.title,
       t.confidence,
       t.status,
       COUNT(e.ordinal)                                          AS evidence_count,
       COUNT(DISTINCT e.doc_id)                                  AS doc_count,
       COUNT(DISTINCT d.doc_type)                                AS type_count,
       SUM(CASE WHEN e.kind = 'counter'       THEN 1 ELSE 0 END) AS counter_count,
       SUM(CASE WHEN e.kind = 'implied'       THEN 1 ELSE 0 END) AS implied_count,
       SUM(CASE WHEN e.kind = 'corroboration' THEN 1 ELSE 0 END) AS corroboration_count
FROM theories t
LEFT JOIN theory_evidence e ON e.theory_id = t.theory_id
LEFT JOIN documents d       ON d.doc_id    = e.doc_id
GROUP BY t.theory_id;

-- 推论 ↔ 实体关联：让实体卡片能显示「相关推论」
CREATE TABLE IF NOT EXISTS theory_entities (
    theory_id   TEXT NOT NULL REFERENCES theories(theory_id) ON DELETE CASCADE,
    entity_id   TEXT NOT NULL REFERENCES entities(entity_id),
    PRIMARY KEY (theory_id, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_theory_entities_entity ON theory_entities(entity_id);
