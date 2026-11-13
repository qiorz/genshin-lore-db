-- 暗示层：记录文本中的影射、寓言对应、戏中戏。
--
-- 与 theories 的区别：
--   theories 是「从多条证据推出一个结论」；
--   allusions 是「一篇文本影射某个对象」——证据通常是单篇，但要判断它是
--   表面故事还是在说别的事。
--
-- 与 claims 的区别：
--   claims 是「谁相信什么」，allusions 是「故事在讲谁」。
--
-- 引文同样不硬编码 section_id：只存 doc_id + quote，灌库时现场解析
-- （见 scripts/load_allusions.py，复用 load_knowledge.resolve）。

CREATE TABLE IF NOT EXISTS allusions (
    allusion_id TEXT PRIMARY KEY,
    doc_id      TEXT REFERENCES documents(doc_id),
    title       TEXT NOT NULL,
    surface     TEXT,           -- 表面内容：这篇文本字面上讲了什么
    target      TEXT,           -- 影射对象：实际指向什么
    confidence  TEXT NOT NULL DEFAULT 'tentative' CHECK (confidence IN (
                    'explicit', 'strong', 'tentative'
                )),
    basis       TEXT,           -- 判断依据
    caveat      TEXT,           -- 反证、限制、为什么不能升级
    extra       TEXT,           -- 附带线索
    status      TEXT NOT NULL DEFAULT 'open' CHECK (status IN (
                    'open', 'rejected', 'resolved'
                )),
    quote       TEXT,           -- 用于解析 section_id 的引文
    section_id  INTEGER REFERENCES sections(section_id),
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_allusions_doc ON allusions(doc_id);
CREATE INDEX IF NOT EXISTS idx_allusions_status ON allusions(status);

-- 覆盖率视图：按置信度统计
CREATE VIEW IF NOT EXISTS v_allusion_coverage AS
SELECT
    confidence,
    status,
    COUNT(*) AS n
FROM allusions
GROUP BY confidence, status;
