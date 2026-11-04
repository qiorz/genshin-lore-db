# 交接文档 · 原神世界观数据库

> 更新时间：2026-11-04  
> 项目根目录：`D:\harn\2\genshin-lore-db`  
> 一句话状态：**书籍、任务、散落文本、角色主干全部归档进 `corpus/`，数据库可从 Markdown 全量重建；武器/圣遗物/活动/成就与知识层还没做。**

---

## 0. 本次变更（2026-11-04 · 第 0 步：把正文收进 corpus）

这次只做一件事：**让 `corpus/` 成为真正完整、可重建的权威正文层**。之前 706 条散落文本和 50 条任务只存在于 `exports/` 和 SQLite 里，一旦重装库就会丢。

### 做了什么

| 动作 | 结果 |
|---|---|
| 备份数据库 | `db/backup/genshin_lore-20261104-121411.sqlite3`（244 MB，校验 2,035 篇 / 330,417 段 / integrity ok） |
| 初始化 Git | 基线提交 `cb9647f`，仓库 36.95 MiB；`db/`、`tools/`、`logs/` 不进版本库 |
| 迁移散落文本 | 706 条 → `corpus/scattered/<地区>/`，新建 `index.csv`（706 行） |
| 迁移有正文任务 | 19 条 → `corpus/quests/<subtype>/`（原先误留在 exports 的「待补」，其实有正文） |
| 隔离空壳任务 | 31 条 → `corpus/quests/_pending/` |
| 更新任务索引 | `corpus/quests/index.csv`：1,051 → 1,069 行 |
| 重导入 | 只重导这 756 篇，未做全量重建 |

### 验证结果

重导入后与迁移前**逐篇一致**：

```text
文档：2,035（不变）
段落：330,417（不变）
正文字符：7,322,802（不变）
每篇 section 数：diff 无差异
normalized_path 指向 exports 的文档：0
PRAGMA integrity_check：ok
```

### 顺手修了两篇坏数据

这两篇是历史 BWiki 补全/合并脚本留下的，不是迁移造成，但重导入会如实反映，所以必须修：

1. **`quest.obc.500835 云云椒椒`**：文件正文被覆盖成「赤望所居，锦落云程」的内容（front matter 还挂着 500835 的来源）。已用 `raw/` 原始快照重新渲染恢复，6,495 字，332 段。
2. **`quest.obc.4190 邀约事件·久岐忍 第一幕`**：OBC 页面本身 0 剧情模块；BWiki 补全时匹配到错误页面，把凝光/云堇/加尔恰等其他邀约的整篇文本塞了进来，**里面没有一句久岐忍**。已回退为 OBC-only 空壳，移入 `_pending/`，等正确页面重补。

### 新增的 Git 约定

- `.gitattributes` 把 `raw/**` 标为 `binary`：`raw/**/meta/*.json` 记录了响应体 `sha256`，若 Git 做 CRLF→LF 转换，重新检出后哈希就对不上，破坏「原始快照不可变」。
- `corpus/**` 仍是 `text eol=lf`，换行符统一不影响正文语义。

---

## 1. 现在到哪一步

| 模块 | 数量 | 状态 |
|---|---:|---|
| 书籍 | 92 | 已归档 `corpus/books/` |
| 散落文本 | 706 | 已归档 `corpus/scattered/<地区>/` |
| 任务（有正文） | 1,069 | 已归档 `corpus/quests/<subtype>/` |
| 任务（空壳） | 32 | 隔离在 `corpus/quests/_pending/` |
| 角色 | 136 | 已归档 `corpus/characters/` |
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
数据库大小：约 244 MB
```

按类型：

```text
任务：1,101（1,069 有正文 + 32 空壳，均在库里）
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
├─ books/           92 本书（按地区）
├─ quests/          1,069 条有正文任务（按 archon/story/world/event/other）
│  └─ _pending/     32 条 OBC 无剧情对话的空壳页
├─ scattered/       706 条散落文本（按地区）
└─ characters/      136 个角色（按地区）

exports/
├─ obc-batch/       只剩 lore-manifest.csv / quest-manifest.csv 两份批次台账
└─ obc-evaluation/  统计、审计、抽样对照、补全报告

raw/
├─ official_site/obc/  OBC entry JSON（2,038）、频道列表、meta
└─ bwiki/              BWiki 版本查询、任务补全缓存

db/
├─ genshin_lore.sqlite3
└─ backup/          数据库快照（不进 Git）

manifests/
├─ obc-index.csv        书籍/散落/任务 1,900 条
├─ character-index.csv  角色 138 条（136 已入库）
├─ coverage.csv         覆盖矩阵
└─ versions.csv         人工确认的版本
```

索引：

- [`corpus/books/index.csv`](corpus/books/index.csv)
- [`corpus/quests/index.csv`](corpus/quests/index.csv)
- [`corpus/scattered/index.csv`](corpus/scattered/index.csv)
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

- 706 条全部归档 `corpus/scattered/`，10 个地区目录；
- 只保留交互文本，跳过地图截图/坐标；
- 226 条从相关任务/成就/活动推导出版本；
- 480 条版本 unknown，按约定不猜；
- 4 组同名条目（共 9 个文件）用 ` (obc-<content_id>)` 后缀消歧；
- **10 篇正文为空**，原因见 §5.4。

### 4.3 任务

- 1,101 个 OBC entry，全部在库；
- 1,069 条有正文，归档 `corpus/quests/`；
- 32 条无正文，隔离在 `_pending/`；
- 183 条用了 BWiki 源补全；
- 修复了 OBC `interactive_dialogue` 的 graph-only 格式，恢复了 381 条任务的对话；
- 任务版本 1,101/1,101 已补齐；
- 迁移时把 19 条「其实有正文、但被误标待补」的任务从 exports 收进 corpus。

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
- 抽样对照、覆盖审计、补全报告都在 `exports/obc-evaluation/`；
- **Git 已初始化**，基线 `cb9647f`，`raw/` 按 binary 处理。

---

## 5. 已知缺口与质量问题

### 5.1 明确未做

| 模块 | OBC 条目 | 状态 |
|---|---:|---|
| 武器 | 252 | 0（**频道列表已抓，entry 未抓**） |
| 圣遗物 | 63 | 0（同上） |
| 活动 | 275 | 0（同上） |
| 成就 | 1,626 | 0（同上） |
| 材料/食物/道具 | 未统计 | 未做 |
| 地理/地区 | 未统计 | 未做 |
| 官方公告 | 未统计 | 未做 |
| 漫画 | 未统计 | 未做 |
| NPC 对话 | 未统计 | 未做 |
| 七圣召唤 | 未统计 | 未做 |
| 知识层 | — | 0 |

> 武器/圣遗物/活动/成就的**频道列表早就抓好了**，在 `raw/official_site/obc/channel_lists/`（5 / 218 / 105 / 252.json）。
> 缺的是「抓 entry + 写 renderer」，不是从零开始。

### 5.2 任务尾巴

- 32 条空壳任务在 `_pending/`，主要是邀约/活动系列页；
- 20 条邀约事件已入库，但 subtype 仍是 `event/story/other`，`hangout/` 目录是空的；
- 间章混在 `archon/`，`interlude/` 目录也是空的；
- 15 个 `系列/合集/总览` 页（如 `风沙轰鸣系列任务合集`）应与正文区分，尚未审计；
- 13 组同文重复尚未处理，典型是：
  - `危影重重·其一` 到 `其六` 六篇同文；
  - `好东西，坏品味` 五篇同文；
  - 旅行者多元素形态共用正文。

重复不一定是抓错，有些是 OBC 页面本身重复；但需要一次合并/去重。

### 5.3 版本与书籍

- `1158 残破的笔记` unknown；
- `500 白之公主与六侏儒` 只有第一卷；
- 480 条散落文本版本 unknown。

### 5.4 内容质量

- **10 篇散落文本正文为空**：`render_lore` 只识别 `interactive_dialogue` 组件，这几页的交互文本在别的模块里。是 renderer 缺口，不是数据缺失。清单见 `corpus/scattered/README.md`。
- **`quest.obc.4190`**：BWiki 补全匹配到错误页面，已回退为空壳，待重补。
- **`quest.obc.500835`**：曾被覆盖，已从 `raw/` 重渲染修复。
- 13 组同文重复（见 §5.2）。

### 5.5 审计数字

完整审计见：

- [`exports/obc-evaluation/coverage-audit.md`](exports/obc-evaluation/coverage-audit.md)
- [`exports/obc-evaluation/crosscheck.md`](exports/obc-evaluation/crosscheck.md)
- [`exports/obc-evaluation/bwiki-quest-fill.txt`](exports/obc-evaluation/bwiki-quest-fill.txt)

覆盖矩阵已更新到 `manifests/coverage.csv`：

- `books = done`
- `characters = done`
- `scattered_text = done`（正文已归档，480 条版本 unknown）
- `main_story / story_quests / world_quests / event_quests / hangouts / interludes = partial`
- 其余 `planned`

---

## 6. 关键设计决策

1. **OBC 做主源，BWiki 做校验/兜底**；不是官方逐字文本，front matter 标 `canon_status: community`、`transcription: near-verbatim`。
2. **Markdown 是正文权威副本，SQLite 是索引层**；不要手工改 DB 正文，改 Markdown 后重导入。
   > 但反过来也成立：如果 Markdown 被脚本写坏，DB 里的旧版可能是唯一好副本。**重导入前先备份 DB**，并用 `char_count` 对账。
3. **版本必须溯源**：
   - `obc-filter`：任务频道版本；
   - `bwiki`：书籍/角色实装版本；
   - `derived-related-quest`：散落文本从相关任务/成就/活动推导；
   - 找不到就 `unknown`，不猜。
4. **不收攻略/配队/数值/图片**；角色只收叙事模块。
5. **同文异址允许共存**：哈希索引非唯一，重复通过 `v_duplicate_hashes` 查看。
6. **Web UI 只读**，只监听 `127.0.0.1`，不公网暴露。
7. **FTS5 trigram**：3 字以上中文可搜，2 字回退 `LIKE`。
8. **空壳与正文分目录**：`corpus/quests/` 只放有正文的，`_pending/` 放 OBC 0 剧情的页面，避免「任务数」虚高。
9. **`raw/` 在 Git 里按 binary 处理**：meta 存了响应体 `sha256`，不能做换行符转换。

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
.\tools\python\python.exe .\scripts\validate_frontmatter.py --dir .\corpus\scattered --quiet
.\tools\python\python.exe .\scripts\validate_frontmatter.py --dir .\corpus\books --quiet
```

### 重新导入（注意分词模式不同）

```powershell
# 角色、任务：不分词
.\tools\python\python.exe .\scripts\load_markdown.py --dir .\corpus\characters --bulk --no-segment
.\tools\python\python.exe .\scripts\load_markdown.py --dir .\corpus\quests --bulk --no-segment

# 书籍、散落文本：要分词（不要加 --no-segment）
.\tools\python\python.exe .\scripts\load_markdown.py --dir .\corpus\books --bulk
.\tools\python\python.exe .\scripts\load_markdown.py --dir .\corpus\scattered --bulk
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

### 备份

```powershell
.\tools\sqlite\sqlite3.exe .\db\genshin_lore.sqlite3 ".backup .\db\backup\genshin_lore-$(Get-Date -Format yyyyMMdd-HHmmss).sqlite3"
```

### Web UI

```powershell
.\webui\start.ps1
# 或
.\tools\python\python.exe .\webui\app.py --host 127.0.0.1 --port 8765
```

---

## 8. 下一步计划

### P0：收任务尾巴（原计划，仍未做）

- 32 条空壳任务：按子任务页拆分，或补 BWiki 正文；
- 13 组同文重复：区分「多地点同文」（保留 + 标注）和「页面级重复」（合并 + alias）；
- 做一次「一篇一幕」审计，确认 1,069 条是真正的任务正文，而不是系列总览页；
- 补 subtype：20 条邀约 → `hangout`，间章 → `interlude`，让空目录有意义。

### P1：武器 + 圣遗物（性价比最高）

- 武器 252 条、圣遗物 63 套；
- **频道列表已就位**，只需：抓 entry → 写 `render_weapon` / `render_artifact` → 归档 → 导入；
- 单条短、信息密度高，适合批量；
- 只收故事，不收数值。

### P2：活动 + 成就

- 活动 275 条：先抽 5 条验证结构，多数可能只有简介 + 活动任务列表，价值低于武器/圣遗物；
- 成就 1,626 条：**不建议生成 1,626 个 Markdown**，建议抽成 `manifests/achievements.csv`（名称/描述/成就集/版本/是否隐藏），作为版本与事件索引，不进正文层。

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

建议在武器/圣遗物入库后，先起 `entities` 的**人物、地区、组织**三张核心表，而不是等全量文本做完。

---

## 9. 交接注意事项

- **Git 已初始化**，基线 `cb9647f`。`db/*.sqlite3`、`tools/`、`logs/*.log` 不进版本库；`raw/` 在库里但按 `binary` 处理。
- 数据库约 244 MB，`raw/` 约 136 MB，`tools/` 约 94 MB；仓库当前 36.95 MiB。
- **重导入前先 `.backup` 一份 DB**：Markdown 可能被历史脚本写坏，DB 反而留着好副本（见 §5.4）。
- 不要手工改 SQLite 正文；改 Markdown 后重新 `load_markdown.py`。
- 批量导入大文档时，确保 `idx_sections_parent` 存在；否则级联删除会很慢。
- FTS 触发器存在时逐条导入会慢；大批量可先 drop triggers，导入后 rebuild（当前 schema 已有 trigram 迁移）。
- 32 条空壳任务和 480 条 unknown 版本不是「漏跑」，是来源本身没有稳定字段/正文，已明确标记。
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
- [散落文本说明](corpus/scattered/README.md)
- [待补任务说明](corpus/quests/_pending/README.md)
