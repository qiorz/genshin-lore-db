# 交接文档 · 原神世界观数据库

> 更新时间：2026-11-04  
> 项目根目录：`D:\harn\2\genshin-lore-db`  
> 一句话状态：**书籍、任务、地图文本、角色主干已完成；武器/圣遗物/活动/成就与知识层还没做。**

---

## 1. 现在到哪一步

| 模块 | 数量 | 状态 |
|---|---:|---|
| 书籍 | 92 | 已归档 `corpus/books/` |
| 地图文本 / 散落文本 | 706 | 已入库，草稿在 `exports/obc-batch/` |
| 任务 | 1,101 | 1,051 条正文已归档 `corpus/quests/`；50 条待补 |
| 角色 | 138 | 136 条已归档 `corpus/characters/`；2 条无叙事 |
| 武器 | 252 | **0，未开始** |
| 圣遗物 | 63 | **0，未开始** |
| 活动 | 275 | **0，未开始** |
| 成就 | 1,626 | **0，未开始** |
| 知识层 | — | entities / relations / claims / timeline 全为 0 |

当前数据库：

```text
文档：2,035
段落：330,417
来源：9
数据库大小：约 243 MB
```

按类型：

```text
任务：1,101
散落文本：706
角色：136
书籍：92
```

版本覆盖：

| 类型 | 已标版本 | 未知 |
|---|---:|---:|
| 任务 | 1,101/1,101 | 0 |
| 角色 | 136/136 | 0 |
| 书籍 | 91/92 | 1（1158） |
| 散落文本 | 226/706 | 480 |

---

## 2. 最快入口

### Web UI（推荐日常使用）

```text
http://127.0.0.1:8765/
```

如果服务已停：

```powershell
cd D:\harn\2\genshin-lore-db
.\webui\start.ps1
```

健康检查：

```text
http://127.0.0.1:8765/health
```

特点：只读、搜索、类型/地区/版本/剧透筛选、文档页、来源、原始 Markdown。

### 命令行检索

```powershell
cd D:\harn\2\genshin-lore-db

.\tools\python\python.exe .\scripts\search.py 白之公主
.\tools\python\python.exe .\scripts\search.py 钟离 --type character
.\tools\python\python.exe .\scripts\search.py 层岩巨渊 --region 璃月 --spoiler 1
```

### SQLite

```powershell
.\tools\sqlite\sqlite3.exe -readonly .\db\genshin_lore.sqlite3
```

详细访问方式见 [`docs/06-访问与检索.md`](docs/06-访问与检索.md)。

---

## 3. 数据资产位置

```text
corpus/
├─ books/           92 本书
├─ quests/          1,051 条任务（按 archon/story/hangout/world/event/interlude/other）
└─ characters/      136 个角色（按地区）

exports/
├─ obc-batch/       706 条散落文本 + 50 条待补任务
└─ obc-evaluation/  统计、审计、抽样对照、补全报告

raw/
├─ official_site/obc/  OBC entry JSON、频道列表、meta
└─ bwiki/              BWiki 版本查询、任务补全缓存

db/
└─ genshin_lore.sqlite3

manifests/
├─ obc-index.csv        书籍/散落/任务 1,900 条
├─ character-index.csv  角色 138 条（136 已入库）
├─ coverage.csv         覆盖矩阵
└─ versions.csv         人工确认的版本
```

索引：

- [`corpus/books/index.csv`](corpus/books/index.csv)
- [`corpus/quests/index.csv`](corpus/quests/index.csv)
- [`corpus/characters/index.csv`](corpus/characters/index.csv)
- [`manifests/obc-index.csv`](manifests/obc-index.csv)
- [`manifests/character-index.csv`](manifests/character-index.csv)

---

## 4. 已完成的关键工作

### 4.1 书籍

- OBC 93 条，92 本唯一书；
- `503 林间风·故事拔萃节选` 是 `501` 的重复卷，跳过；
- `500 白之公主与六侏儒` 只有第一卷全文，已标待补；
- `1158 残破的笔记` 版本 unknown；
- 已按地区归档到 `corpus/books/`。

### 4.2 散落文本

- 706 条全部入库；
- 只保留交互文本，跳过地图截图/坐标；
- 226 条从相关任务/成就/活动推导出版本；
- 480 条版本 unknown，按约定不猜。

### 4.3 任务

- 1,101 个 OBC entry；
- 1,051 条有正文，已归档 `corpus/quests/`；
- 50 条仍无正文，留在 `exports/obc-batch/`；
- 181 条用了 BWiki 源补全；
- 修复了 OBC `interactive_dialogue` 的 graph-only 格式，恢复了 381 条任务的对话；
- 任务版本 1,101/1,101 已补齐。

### 4.4 角色

- OBC 138 条，136 条入库；
- 2 条 `奇偶·男性/女性` 没有叙事模块，跳过；
- 只收：更多描述、角色详细、角色故事 1–5、神之眼/神之心、角色关联语音、生日邮件；
- 不含属性、命之座、配队、攻略、数值、图片；
- 版本来自 BWiki，136/136。

### 4.5 基础设施

- FTS5 改为 **trigram**，不依赖 jieba；
- 3 字以上中文直接 `MATCH`，2 字词回退 `LIKE`；
- 新增 `sections.parent_id` 索引，修复重载大任务时的级联删除性能；
- Web UI：`http.server + sqlite3 + markdown`，只读，无 Flask/FastAPI 依赖；
- 抽样对照、覆盖审计、补全报告都在 `exports/obc-evaluation/`。

---

## 5. 已知缺口与质量问题

### 5.1 明确未做

| 模块 | OBC 条目 | 状态 |
|---|---:|---|
| 武器 | 252 | 0 |
| 圣遗物 | 63 | 0 |
| 活动 | 275 | 0 |
| 成就 | 1,626 | 0 |
| 材料/食物/道具 | 未统计 | 未做 |
| 地理/地区 | 未统计 | 未做 |
| 官方公告 | 未统计 | 未做 |
| 漫画 | 未统计 | 未做 |
| NPC 对话 | 未统计 | 未做 |
| 七圣召唤 | 未统计 | 未做 |
| 知识层 | — | 0 |

### 5.2 任务尾巴

- 50 条任务无正文，主要是邀约/活动系列页；
- `1,051` 条任务里仍可能混有系列页/子任务页，尚未做最终“一篇一幕”审计；
- 13 组同文重复，典型是：
  - `危影重重·其一` 到 `其六` 六篇同文；
  - `好东西，坏品味` 五篇同文；
  - 旅行者多元素形态共用正文。

重复不一定是抓错，有些是 OBC 页面本身重复；但需要一次合并/去重。

### 5.3 版本与书籍

- `1158 残破的笔记` unknown；
- `500 白之公主与六侏儒` 只有第一卷；
- 480 条散落文本版本 unknown。

### 5.4 审计数字

完整审计见：

- [`exports/obc-evaluation/coverage-audit.md`](exports/obc-evaluation/coverage-audit.md)
- [`exports/obc-evaluation/crosscheck.md`](exports/obc-evaluation/crosscheck.md)
- [`exports/obc-evaluation/bwiki-quest-fill.txt`](exports/obc-evaluation/bwiki-quest-fill.txt)

覆盖矩阵已更新到 `manifests/coverage.csv`：

- `books = done`
- `characters = done`
- `main_story / story_quests / world_quests / event_quests / hangouts / interludes = partial`
- `scattered_text = partial`
- 其余 `planned`

---

## 6. 关键设计决策

1. **OBC 做主源，BWiki 做校验/兜底**；不是官方逐字文本，front matter 标 `canon_status: community`、`transcription: near-verbatim`。
2. **Markdown 是正文权威副本，SQLite 是索引层**；不要手工改 DB 正文，改 Markdown 后重导入。
3. **版本必须溯源**：
   - `obc-filter`：任务频道版本；
   - `bwiki`：书籍/角色实装版本；
   - `derived-related-quest`：散落文本从相关任务/成就/活动推导；
   - 找不到就 `unknown`，不猜。
4. **不收攻略/配队/数值/图片**；角色只收叙事模块。
5. **同文异址允许共存**：哈希索引非唯一，重复通过 `v_duplicate_hashes` 查看。
6. **Web UI 只读**，只监听 `127.0.0.1`，不公网暴露。
7. **FTS5 trigram**：3 字以上中文可搜，2 字回退 `LIKE`。

---

## 7. 常用命令

### 检索

```powershell
.\tools\python\python.exe .\scripts\search.py 芙宁娜
.\tools\python\python.exe .\scripts\search.py 葬火之战 --type book --limit 5
.\tools\python\python.exe .\scripts\search.py 钟离 --type character --json
```

### 校验

```powershell
.\tools\python\python.exe .\scripts\validate_frontmatter.py --dir .\corpus\characters --quiet
.\tools\python\python.exe .\scripts\validate_frontmatter.py --dir .\corpus\quests --quiet
.\tools\python\python.exe .\scripts\validate_frontmatter.py --dir .\corpus\books --quiet
```

### 重新导入

```powershell
# 角色
.\tools\python\python.exe .\scripts\load_markdown.py --dir .\corpus\characters --bulk --no-segment

# 任务
.\tools\python\python.exe .\scripts\load_markdown.py --dir .\corpus\quests --bulk --no-segment
```

### 统计与审计

```powershell
.\tools\python\python.exe .\scripts\report_db.py
.\tools\python\python.exe .\scripts\audit_coverage.py
```

### 数据库检查

```powershell
.\tools\sqlite\sqlite3.exe -readonly .\db\genshin_lore.sqlite3 "PRAGMA integrity_check;"
.\tools\sqlite\sqlite3.exe -readonly .\db\genshin_lore.sqlite3 "SELECT COUNT(*) FROM sections;"
```

### Web UI

```powershell
.\webui\start.ps1
# 或
.\tools\python\python.exe .\webui\app.py --host 127.0.0.1 --port 8765
```

---

## 8. 下一步计划

### P0：收任务尾巴

- 50 条待补任务：邀约/活动模板；
- 13 组同文重复：合并/去重；
- 做一次“一篇一幕”审计，确认 1,051 条任务是真正的任务正文，而不是系列总览页。

### P1：武器 + 圣遗物

- 武器 252 条；
- 圣遗物 63 套；
- 单条短、信息密度高，适合批量；
- 只收故事，不收数值。

### P2：活动 + 成就

- 活动 275 条；
- 成就 1,626 条；
- 主要补版本、事件、地区、世界观碎片。

### P3：其他文本

- 材料/食物/道具；
- 地理/地点；
- 官方公告；
- 漫画；
- NPC 对话；
- 七圣召唤。

### P4：知识层

- entities；
- entity_relations；
- claims；
- events / timeline。

**不要先做知识层再补文本**，否则实体关系会反复返工。

---

## 9. 交接注意事项

- 数据库约 243 MB，`raw/` 约 123 MB，`tools/` 约 94 MB；不要随手提交到 Git。
- 当前项目没有初始化 Git；交接前建议备份：
  - `db/genshin_lore.sqlite3`
  - `corpus/`
  - `manifests/`
  - `schema/`
  - `scripts/`
- 不要手工改 SQLite 正文；改 Markdown 后重新 `load_markdown.py`。
- 批量导入大文档时，确保 `idx_sections_parent` 存在；否则级联删除会很慢。
- FTS 触发器存在时逐条导入会慢；大批量可先 drop triggers，导入后 rebuild（当前 schema 已有 trigram 迁移）。
- 50 条待补任务和 480 条 unknown 版本不是“漏跑”，是来源本身没有稳定字段/正文，已明确标记。
- 游戏文本版权归原权利方；本库仅本地个人研究使用，Web UI 不要公网部署。

---

## 10. 相关文档

- [README](README.md)
- [总体设计](docs/00-总体设计.md)
- [数据源与合规](docs/01-数据源与合规.md)
- [数据规范](docs/02-数据规范.md)
- [实施路线图](docs/03-实施路线图.md)
- [观测枢评估](docs/05-观测枢评估.md)
- [访问与检索](docs/06-访问与检索.md)
- [覆盖审计](exports/obc-evaluation/coverage-audit.md)
- [抽样对照](exports/obc-evaluation/crosscheck.md)
- [数据库统计](exports/obc-evaluation/summary.txt)
- [Web UI 说明](webui/README.md)
