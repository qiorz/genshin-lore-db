# schema · 数据库结构

> SQLite 3.35+。核心表在 `schema.sql`，中文全文检索在 `fts.sql`（可选，但建议启用）。

---

## 1. 建库顺序

```text
1. schema/schema.sql     核心表 + 视图
2. schema/fts.sql        FTS5 全文索引 + 同步触发器
3. 导入 sources.csv      数据源
4. 导入 corpus/*.md      文档 + 段落
5. 导入 knowledge/*.md   实体、关系、事件、时间线
```

用 Python 标准库即可：

```python
import sqlite3
from pathlib import Path

con = sqlite3.connect("db/genshin_lore.sqlite3")
con.execute("PRAGMA foreign_keys = ON")
con.executescript(Path("schema/schema.sql").read_text(encoding="utf-8"))
try:
    con.executescript(Path("schema/fts.sql").read_text(encoding="utf-8"))
except sqlite3.OperationalError as e:
    print("FTS5 unavailable, skipped:", e)
con.commit()
```

注意：

- `PRAGMA foreign_keys = ON` 是**每个连接**都要设置的；
- `fts.sql` 需要 SQLite 编译时带 FTS5；
- 如果先导入数据、后建 FTS，`fts.sql` 末尾的 `rebuild` 会补索引；
- 不要在没有备份时直接改表结构；用迁移脚本。

---

## 2. 表的关系

```text
sources
  │
  ├──< documents >──< document_sources
  │        │
  │        ├──< sections >──< sections_fts (virtual)
  │        ├──< document_revisions
  │        ├──< document_aliases
  │        ├──< document_tags >── tags
  │        └──< document_links
  │
  ├──< entities >──< entity_names
  │        │
  │        ├──< entity_relations >── entities (object)
  │        └──< claims >── sections
  │
  ├──< events >──< event_sources
  │        └──< timeline_entries
  │
  └──< ingest_runs
```

---

## 3. 核心表说明

### `sources`

数据源主表。与 `manifests/sources.csv` 对应。

关键字段：

- `source_id`：短 ID，如 `obc`、`bwiki`、`miyoushe`；
- `kind`：`official` / `official-community` / `wiki` / `datamine` / `fan`；
- `license`：许可说明；
- `priority`：越小越优先；
- `status`：`active` / `limited` / `blocked` / `deprecated`。

### `documents`

一篇可引用的文档。**一行 = 一篇任务/书/角色/武器/地区/公告**。

关键字段：

- `doc_id`：稳定 ID，front matter 的 `id`；
- `doc_type` / `subtype`：类型；
- `version` / `version_source` / `version_confidence`：游戏版本及其来源/置信度；
- `canon_status`：内容权威性；
- `transcription`：转写保真度；
- `spoiler_level`：0–3；
- `primary_source_id` / `source_url` / `source_revision` / `retrieved_at`；
- `raw_path` / `normalized_path`；
- `content_hash` / `char_count`。

`content_hash` 有唯一索引（非空时），用于阻止完全重复的正文。

### `document_sources`

一篇文档的多来源。第一个 `is_primary=1` 为主来源。

用于：

- 观测枢主来源 + BWiki/官网校验；
- 同一文本的多个 Wiki 镜像；
- 记录不同抓取时间的 URL。

### `document_revisions`

正文变更历史。每次 `content_hash` 变化追加一条：

- `content_hash`；
- `source_revision`（Wiki revid）；
- `retrieved_at`；
- `raw_path`；
- `change_summary`。

`documents.content_hash` 只保存当前版本；历史在 `document_revisions`。

### `sections`

段落/台词/选项。**引用的最小单位**。

关键字段：

- `doc_id` + `ordinal`：顺序；
- `parent_id`：层级（章节 → 小节 → 台词 → 选项）；
- `section_type`：`heading` / `text` / `dialogue` / `option` / `note` / `quote` / `table`；
- `speaker`：说话者；
- `body`：原文；
- `body_segmented`：兼容列；trigram FTS 下通常等于 `body`，不再依赖 jieba；
- `spoiler_level`：段落级剧透；
- `source_line`：原始 wikitext/HTML 行号（可选）。

### `entities` / `entity_names`

知识层的对象与别名。

- `entity_type`：人物、国家、组织、地点、神、生物、概念、事件、物品、称号；
- `canonical_name`：中文规范名；
- `entity_names`：本名、称号、化名、译名、拼音。

### `entity_relations`

整理后的实体关系：

```text
subject_id + predicate + object_id / object_literal
```

带 `confidence`、`source_id`、`doc_id`、`section_id`。每条关系应能落到证据；不能落地的标 `speculative` 或 `unsourced`（可在 `notes` 说明）。

### `claims`

文本中的“说法”，允许矛盾：

```text
subject + predicate + object
+ statement
+ perspective（谁说的）
+ confidence / status
+ doc_id / section_id
```

`status`：

- `open`：待判断；
- `accepted`：目前接受；
- `disputed`：有争议；
- `rejected`：已否定；
- `superseded`：被新说法取代。

`confidence`：

- `confirmed`：原文明确、可直接核对；
- `likely`：多数来源支持；
- `speculative`：推测；
- `disputed`：来源互相矛盾；
- `unreliable`：叙述者本身不可靠。

### `events` / `timeline_entries`

- `events`：事件本身；
- `timeline_entries`：在时间轴上的位置；
- `certainty`：`exact` / `approximate` / `relative` / `unknown`。

不要用 `documents.version` 当世界观时间；那是现实版本号。

### 运营表

- `ingest_runs`：每次抓取/导入的记录；
- `coverage_targets`：覆盖目标与当前计数；
- `reading_progress`：阅读进度/剧透过滤状态。

---

## 4. FTS5 与中文

### 为什么用 trigram

SQLite 默认 `unicode61` 会把连续汉字当成一个 token，查询“钟离”可能匹配不到“钟离说”。

当前使用 FTS5 `trigram`：

```text
3 字以上中文子串直接 MATCH；
2 字词由 search.py 回退到 LIKE。
```

`body_segmented` 保留为兼容列，trigram 下通常等于 `body`，不再要求 jieba。

### 查询示例

```sql
-- 中文：3 字以上
SELECT d.title, s.speaker, s.body
FROM sections_fts f
JOIN sections s ON s.section_id = f.rowid
JOIN documents d ON d.doc_id = s.doc_id
WHERE sections_fts MATCH 'body:"白之公主"'
LIMIT 20;
```

```sql
-- 英文/原文：查 body
SELECT d.title, s.body
FROM sections_fts f
JOIN sections s ON s.section_id = f.rowid
JOIN documents d ON d.doc_id = s.doc_id
WHERE sections_fts MATCH 'body:"Archon War"'
LIMIT 20;
```

```sql
-- 兜底：两字词或 FTS 不可用时
SELECT d.title, s.speaker, s.body
FROM sections s
JOIN documents d ON d.doc_id = s.doc_id
WHERE s.body LIKE '%钟离%'
LIMIT 20;
```

### 自定义词典

原神专名很多，建议维护：

```text
manifests/terms.txt
```

一行一个词，例如：

```text
原神
提瓦特
坎瑞亚
葬火之战
魔神战争
世界树
神之眼
邪眼
愚人众
深渊教团
```

`manifests/terms.txt` 仍保留为人工专名表，trigram 检索不依赖它；如以后换回分词方案可继续使用。

---

## 5. 常用查询

### 按类型/地区/版本

```sql
SELECT doc_id, title, doc_type, region, version, status
FROM documents
WHERE doc_type = 'quest'
  AND region = '璃月'
ORDER BY version, doc_id;
```

### 按剧透等级

```sql
SELECT doc_id, title, spoiler_level
FROM documents
WHERE spoiler_level <= 1
ORDER BY doc_type, title;
```

### 某实体出现的段落

```sql
SELECT d.title, s.speaker, s.body, s.section_id
FROM sections s
JOIN documents d ON d.doc_id = s.doc_id
WHERE s.body LIKE '%钟离%'
ORDER BY d.doc_id, s.ordinal
LIMIT 50;
```

### 覆盖统计

```sql
SELECT doc_type, region, status, COUNT(*) AS n
FROM documents
GROUP BY doc_type, region, status
ORDER BY doc_type, region;
```

### 缺来源的文档

```sql
SELECT * FROM v_missing_sources;
```

### 重复正文

```sql
SELECT * FROM v_duplicate_hashes;
```

---

## 6. 迁移与备份

- 每次改 `schema.sql`，新增 `schema/migrations/00X-*.sql`；
- 已应用：`001_add_version_provenance.sql`（`version_source` / `version_confidence`）；
- 已应用：`002_allow_duplicate_hashes.sql`（同文异址可共存）；
- 已应用：`003_fts_trigram.sql`（FTS5 改为 trigram，去掉 jieba 依赖）；
- 已应用：`004_index_sections_parent.sql`（`sections.parent_id` 索引，修复重载大文档的级联删除性能）；
- 升级前备份 `db/genshin_lore.sqlite3`；
- 不要直接删除表；先导出，再迁移；
- `content_hash` 是内容身份，不要手动改；
- `doc_id` 一旦被引用，不要改；需要改时加别名并保留旧 ID。

---

## 7. 相关文档

- 数据规范：[`../docs/02-数据规范.md`](../docs/02-数据规范.md)
- 总体设计：[`../docs/00-总体设计.md`](../docs/00-总体设计.md)
- 数据源：[`../docs/01-数据源与合规.md`](../docs/01-数据源与合规.md)
