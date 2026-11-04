# 交接文档 · 原神世界观数据库

> 更新时间：2026-11-04  
> 项目根目录：`D:\harn\2\genshin-lore-db`  
> 一句话状态：**书籍、任务、散落文本、角色主干全部归档进 `corpus/`，任务子类型已分清，重复组已判定；数据库可从 Markdown 全量重建。武器/圣遗物/活动/成就与知识层还没做。**

---

## 0. 变更记录

两轮改动都在 2026-11-04：第 0 步把正文收进 `corpus/`，第 1 步收任务尾巴。

### 第 1 步 · 收任务尾巴

| 动作 | 结果 |
|---|---|
| 修复散落文本空白页 | `render_obc.py` 支持「根节点缺失」的对话图，12 篇从 0 字恢复到 113–4300 字 |
| 重分类 | 19 条邀约 → `hangout`，4 条间章 → `interlude`，目录不再空 |
| 系列页标注 | 15 篇标题含「系列/合集/总览」的页 + 3 篇海灯节，加 `tags: [系列任务]`，共 18 篇 |
| 同名同文合并 | 好东西，坏品味 5→1、通知【明蕴镇】 2→1，来源并入主文档，删除冗余 5 篇 |
| 重复组判定 | 剩余 10 组逐组写判定，见 `manifests/duplicates.csv` |
| BWiki 补空壳 | 32 条探测完毕：BWiki 无可用正文，**0 条补全**，见 `exports/obc-evaluation/bwiki-stub-probe.md` |
| 修工具 | `fill_quests_from_bwiki.py` 删除「匹配不到就取第一条」的回退（4190 事故根因） |

**数量变化**：文档 2,035 → 2,030（合并 5 篇），段落 330,417 → 329,859，正文字符 7,322,802 → 7,303,488。
减少的部分全部来自重复合并，没有丢内容；散落文本反而新增了 12 篇被修复的正文。

**未做**：32 条空壳仍然补不了（上游没正文）；「一篇一幕」审计只做到系列页标注，没有拆分多幕文件。

### 第 2 步 · 武器与圣遗物（P1）

| 动作 | 结果 |
|---|---|
| 抓取 | OBC 武器 252 + 圣遗物 63，entry_page 全部落 `raw/`（此前只抓了频道列表） |
| 渲染器 | `render_obc.py` 新增 `render_weapon` / `render_artifact` |
| 归档 | `corpus/weapons/<武器类型>/` 252 篇，`corpus/artifacts/` 63 篇 |
| BWiki 对照 | 315 条全部找到同名页，版本 315/315 补齐；244 条故事与 OBC **完全一致** |
| BWiki 补缺 | `星锋剑` OBC 故事原文为「暂无」，用 BWiki 补全并挂第二条 source |
| 入库 | 文档 2,030 → 2,345，段落 329,859 → 339,809 |

**只收叙事**：武器取「装备描述（`<hr>` 之后）+ 相关故事」，圣遗物取五个部位的「描述 + 故事」；
精炼数值、属性、套装效果、推荐角色全部丢弃。

两个上游毛病记在 `corpus/artifacts/README.md`：
- 4 套「祭X之人」在 OBC 与 BWiki 都只有 `理之冠`，其余部位是空占位；
- 部分圣遗物页面模块名为空，部位名在 `name.key` 里，渲染器已做回退。

### 第 0 步 · 把正文收进 corpus

这次只做一件事：**让 `corpus/` 成为真正完整、可重建的权威正文层**。之前 706 条散落文本和 50 条任务只存在于 `exports/` 和 SQLite 里，一旦重装库就会丢。

#### 做了什么

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
| 散落文本 | 705 | 已归档 `corpus/scattered/<地区>/` |
| 任务（有正文） | 1,065 | 已归档 `corpus/quests/<subtype>/` |
| 任务（空壳） | 32 | 隔离在 `corpus/quests/_pending/` |
| 角色 | 136 | 已归档 `corpus/characters/` |
| 武器 | 252 | 已归档 `corpus/weapons/<类型>/`，版本 252/252 |
| 圣遗物 | 63 | 已归档 `corpus/artifacts/`，版本 63/63 |
| 活动 | 275 | **0，未开始** |
| 成就 | 1,626 | **0，未开始** |
| 知识层 | — | entities / relations / claims / timeline 全为 0 |

当前数据库：

```text
文档：2,345
段落：339,809
来源：9
数据库大小：约 250 MB
```

按类型：

```text
任务：1,097（1,065 有正文 + 32 空壳，均在库里）
散落文本：705
武器：252
圣遗物：63
角色：136
书籍：92
```

任务子类型：

```text
world 642 · event 288 · story 92 · archon 46 · hangout 19 · interlude 4 · other 6
（其中 32 条空壳分布在 world 20 / story 12，含 12 条邀约）
```

版本覆盖：

| 类型 | 已标版本 | 未知 |
|---|---:|---:|
| 任务 | 1,097/1,097 | 0 |
| 角色 | 136/136 | 0 |
| 书籍 | 91/92 | 1（1158） |
| 散落文本 | 226/705 | 479 |
| 武器 | 252/252 | 0（全部来自 BWiki） |
| 圣遗物 | 63/63 | 0（全部来自 BWiki） |

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
├─ quests/          1,065 条有正文任务（archon 46 / story 92 / world 622 / event 288 / hangout 7 / interlude 4 / other 6）
│  └─ _pending/     32 条 OBC 无剧情对话的空壳页
├─ scattered/       705 条散落文本（按地区）
├─ weapons/         252 把武器（按类型：单手剑/双手剑/弓/法器/长柄武器）
├─ artifacts/       63 套圣遗物（平铺，每套一篇）
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

- 705 条归档 `corpus/scattered/`，10 个地区目录；
- 只保留交互文本，跳过地图截图/坐标；
- 226 条从相关任务/成就/活动推导出版本；
- 479 条版本 unknown，按约定不猜；
- 4 组同名条目（共 9 个文件）用 ` (obc-<content_id>)` 后缀消歧；
- 12 篇原本正文为空的页面已修复（见 §5.4）；
- 1 组同文重复（通知【明蕴镇】）已合并。

### 4.3 任务

- 1,097 个 OBC entry，全部在库；
- 1,065 条有正文，归档 `corpus/quests/`；
- 32 条无正文，隔离在 `_pending/`；
- 183 条用了 BWiki 源补全；
- 修复了 OBC `interactive_dialogue` 的 graph-only 格式，恢复了 381 条任务的对话；
- 任务版本 1,097/1,097 已补齐；
- 迁移时把 19 条「其实有正文、但被误标待补」的任务从 exports 收进 corpus；
- 第 1 步把 19 条邀约归入 `hangout/`、4 条间章归入 `interlude/`；
- 5 篇同名同文的任务/散落文本已合并，OBC 条目 id 保留在 `source` 里。

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

### 4.6 武器与圣遗物

- 武器 252 把（单手剑 59 / 双手剑 45 / 弓 50 / 法器 55 / 长柄武器 43），归档 `corpus/weapons/<类型>/`；
- 圣遗物 63 套，归档 `corpus/artifacts/`，每套五节（生之花/死之羽/时之沙/空之杯/理之冠）；
- 只收叙事：武器取「`<hr>` 之后的装备描述 + 相关故事」，圣遗物取「部位描述 + 部位故事」；
- **版本全部来自 BWiki**（OBC 这两个频道没有版本字段），252/252、63/63；
- BWiki 同名页 315/315 全部命中，244/315 的故事与 OBC 逐字一致；
- `星锋剑` OBC 原文「暂无」，已用 BWiki 补全；
- 4 套「祭X之人」在两边都只有 `理之冠`，文档标 `部件：1/5`；
- 部分圣遗物模块名为空，部位名在 `name.key` 里，渲染器已回退处理。

---

## 5. 已知缺口与质量问题

### 5.1 明确未做

| 模块 | OBC 条目 | 状态 |
|---|---:|---|
| 武器 | 252 | done（252 篇，BWiki 版本全补齐） |
| 圣遗物 | 63 | done（63 套，4 套仅 1 部位） |
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

- 32 条空壳任务在 `_pending/`，主要是邀约/活动系列页；**BWiki 也补不了**（见 §5.4）；
- 邀约/间章归类已完成：`hangout/` 7 篇有正文（另 12 条空壳 subtype 已改 hangout），`interlude/` 4 篇；
- 18 篇系列页已加 `tags: [系列任务]`（标题含「系列/合集/总览」的 15 篇 + 海灯节 3 篇）；
- **多幕文件未拆分**：`雾海纪行系列任务`（4 幕）、`清籁逐雷记系列任务`（4 幕）等仍是「一篇多幕」。
  规范第 84 行允许「一个系列一篇，超长再拆」，所以先保留，没有强行切成合成的 doc_id；
- 同文重复已处理，剩 10 组逐组判定见 `manifests/duplicates.csv`：
  - 已合并 2 组（`好东西，坏品味` 5→1、`通知【明蕴镇】` 2→1）；
  - 保留 8 组：旅行者形态 4 组、危影重重 1 组、海灯节 1 组、空壳页 2 组，原因写在 CSV 里。

### 5.3 版本与书籍

- `1158 残破的笔记` unknown；
- `500 白之公主与六侏儒` 只有第一卷；
- 479 条散落文本版本 unknown。

### 5.4 内容质量

- **散落文本空白页已修复**：`render_obc.py` 之前只从 `root_id` 起步，遇到「根节点不在 contents 里」的页面会输出空正文。现在改为从无父节点的孤岛起步、按节点 key 时间戳排序。12 篇恢复，最长 4,300 字。
- **`quest.obc.4190`**：BWiki 补全匹配到错误页面，已回退为空壳；原脚本「匹配不到就取第一条」的回退已删除。
- **`quest.obc.500835`**：曾被覆盖，已从 `raw/` 重渲染修复。
- **32 条空壳**：OBC 无正文，BWiki 同名页面的「任务剧情」也全部为空（3 个挂 `{{待补充}}`）。探测报告见 `exports/obc-evaluation/bwiki-stub-probe.md`。

### 5.5 审计数字

完整审计见：

- [`exports/obc-evaluation/coverage-audit.md`](exports/obc-evaluation/coverage-audit.md)
- [`exports/obc-evaluation/crosscheck.md`](exports/obc-evaluation/crosscheck.md)
- [`exports/obc-evaluation/bwiki-quest-fill.txt`](exports/obc-evaluation/bwiki-quest-fill.txt)

覆盖矩阵已更新到 `manifests/coverage.csv`：

- `books = done`
- `characters = done`
- `scattered_text = done`（正文已归档，479 条版本 unknown）
- `hangouts = partial`（19 条已入库并归类，12 条无正文）
- `interludes = done`（4 条已归类）
- `main_story / story_quests / world_quests / event_quests = partial`
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

### P0：收任务尾巴（基本完成）

已完成：subtype 归类、系列页标注、同文重复判定与合并、空白散落文本修复、BWiki 补全探测。

剩下的两件：

- **32 条空壳**：OBC 与 BWiki 都没有正文，只能从游戏数据包（`TalkConfig` / `QuestExcelConfigData`）取，属新数据源接入；
- **多幕文件拆分**：`雾海纪行`、`清籁逐雷记` 等 11 个系列页是一篇多幕。规范允许「一个系列一篇」，若要严格「一篇一幕」，得设计合成 doc_id 的规则（如 `quest.obc.2942.act1`），会影响 `source.page_id` 的一一对应，需要先定规范再动手。

### P1：武器 + 圣遗物（已完成）

- 252 把武器 + 63 套圣遗物已归档入库，版本由 BWiki 补齐；
- 对照结果：244/315 与 BWiki 故事完全一致，仅 `星锋剑` 需用 BWiki 补；
- 详细说明见 `corpus/weapons/README.md`、`corpus/artifacts/README.md`。

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
  - 例外：合并重复文档需要删除 DB 行，必须 `PRAGMA foreign_keys = ON` 才能级联清掉 sections / sources / tags。用 `sqlite3` CLI 时要显式加这一句，默认是关的。
- 删改文档后记得同步 `corpus/*/index.csv`，否则索引会指向不存在的文件。
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
- [重复组判定](manifests/duplicates.csv)
- [BWiki 空壳探测](exports/obc-evaluation/bwiki-stub-probe.md)
