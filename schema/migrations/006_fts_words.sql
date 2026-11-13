-- 006_fts_words.sql
-- 两字词检索：新增按词匹配的 FTS5 表（unicode61），索引 jieba 预分词的 body_segmented。
--
-- 为什么需要第二张表：
--   sections_fts 用 trigram 分词器，3 字以上可做任意子串匹配，但 2 字词
--   凑不出三元组，MATCH 恒为 0 条（脚本里只能回退 LIKE 全表扫描，约 200ms 且无相关性排序）。
--   unicode61 按空格切词，配合 jieba 把正文预先切好存进 body_segmented，
--   搜索时同样用 jieba 切查询词，2 字词就能走索引并用 bm25 排序。
--
-- 两张表并存：
--   sections_fts       trigram     → 标题/正文 ≥3 字的任意子串，精确
--   sections_fts_words unicode61   → 按词匹配，覆盖 2 字词
--
-- 依赖：body_segmented 必须是 jieba 分词结果（空格分隔），不能是原文。
--       导入时不要再用 --no-segment；词典见 manifests/terms.txt。

CREATE VIRTUAL TABLE IF NOT EXISTS sections_fts_words USING fts5(
    body_segmented,
    content = 'sections',
    content_rowid = 'section_id',
    tokenize = "unicode61 remove_diacritics 2"
);

CREATE TRIGGER IF NOT EXISTS sections_fts_words_ai
AFTER INSERT ON sections
BEGIN
    INSERT INTO sections_fts_words(rowid, body_segmented)
    VALUES (new.section_id, new.body_segmented);
END;

CREATE TRIGGER IF NOT EXISTS sections_fts_words_ad
AFTER DELETE ON sections
BEGIN
    INSERT INTO sections_fts_words(sections_fts_words, rowid, body_segmented)
    VALUES ('delete', old.section_id, old.body_segmented);
END;

CREATE TRIGGER IF NOT EXISTS sections_fts_words_au
AFTER UPDATE ON sections
BEGIN
    INSERT INTO sections_fts_words(sections_fts_words, rowid, body_segmented)
    VALUES ('delete', old.section_id, old.body_segmented);
    INSERT INTO sections_fts_words(rowid, body_segmented)
    VALUES (new.section_id, new.body_segmented);
END;
