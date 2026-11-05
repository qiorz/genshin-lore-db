# 原神世界观数据库（Genshin Lore DB）

> 目标：把分散在游戏内文本、米游社、Wiki 中的原神叙事资料，整理成一个**本地、可检索、可追溯、可校正**的私人研究库。
>
> 当前状态：**书籍 92 篇、任务 1,065 篇、散落文本 705 条、角色 136 个、武器 252 把、圣遗物 63 套、活动 47 篇、观景点 264 篇、材料/食物/动物/道具 2,622 条、NPC 对话/逸闻/彩蛋 2,401 篇、官方公告 55 篇，全部归档在 `corpus/` 下；另有 32 条 OBC 无剧情的空壳任务隔离在 `corpus/quests/_pending/`，1,558 条成就做成 CSV 索引。数据库共 7,734 篇文档、453,939 个段落，可随时从 Markdown 全量重建。**
>
> 本地 Web UI：**http://127.0.0.1:8765/**（启动方式见 [`webui/README.md`](webui/README.md)）

---

## 1. 这个库要解决什么问题

单纯把网页另存下来，很快会遇到四个问题：

1. **找不到**：剧情、书籍、角色故事、武器故事散在不同页面，关键词搜索又会被攻略和重复内容淹没。
2. **对不上**：同一件事在不同任务、不同角色口中说法不同，甚至互相矛盾。
3. **回不去**：看到一条结论，想核对“这句话到底是谁说的、出自哪个任务哪一步”，却找不到原文。
4. **会过期**：游戏版本更新、Wiki 改版、页面被删，旧文本就丢了。

所以这个库不只是“文本合集”，而是三层东西：

- **原文层**：可回溯的原始快照；
- **阅读层**：清洗、分段、可搜索的 Markdown 正文；
- **知识层**：人物、国家、组织、事件、时间线，以及“谁在什么立场下说了什么”的论断与证据。

---

## 2. 设计原则

1. **证据与推论分开。**
   原文、Wiki 转写、玩家考据分别标注，不把“推测”写成“设定”。
2. **原文快照不可变。**
   `raw/` 里的抓取结果只增不改；清洗后的内容放 `corpus/`，两者用 checksum 关联。
3. **最小引用单位是“段落/台词”，不是“整篇文章”。**
   数据库里每段有 `section_id`，可以精确回到某一句。
4. **矛盾是数据，不是错误。**
   用 `claims` 表记录“谁相信什么”，允许 `disputed`、`rumor`、`unreliable`，而不是强行合并成唯一答案。
5. **版本化。**
   同时记录“游戏实装版本”“抓取时间”“Wiki 修订号”，能看出文本何时变化。
6. **中文优先，英文辅助。**
   以简中官方文本为主，英文名作为别名和交叉检索，不混用翻译。
7. **本地优先。**
   Markdown + SQLite，不依赖在线服务；Obsidian 可以直接打开，脚本可以离线跑。
8. **先叙事，后全量。**
   先做主线、书籍、角色故事等“高信息密度文本”；材料描述、NPC 闲谈、全部道具文本后置。

---

## 3. 四层结构

```text
官方站点 / 米游社 / 观测枢 / BWiki / 社区数据
                │
                │  抓取 + 保存原始响应 + 记录 URL/时间/修订号
                ▼
raw/            原始快照（HTML / JSON / wikitext，只增不改）
                │
                │  解析 + 清洗 + 分段 + 补来源
                ▼
corpus/         规范化正文（Markdown + YAML front matter，人可读）
                │
                │  分词 + 入库 + 建立引用
                ▼
db/             SQLite：documents / sections / entities / claims / FTS
                │
                ├──► Obsidian：阅读、双链、图谱
                ├──► CLI / SQL：精确检索、覆盖统计
                └──► exports/：按主题导出
```

`knowledge/` 是人工整理层，不直接由爬虫生成：实体、关系、事件、时间线、考据笔记。它引用 `corpus/` 和 `db/` 里的证据，而不是替代证据。

---

## 4. 目录说明

```text
genshin-lore-db/
├─ README.md                  <- 本文件
├─ NOTICE.md                  <- 版权与使用边界
├─ docs/                      <- 方案、数据源、规范、路线图
├─ raw/                       <- 原始抓取快照（按来源分）
├─ corpus/                    <- 清洗后的正文（按文本类型分）
│  ├─ quests/                 <- 魔神、传说、世界、活动、邀约、间章
│  ├─ books/                  <- 游戏内书籍
│  ├─ scattered/              <- 散落文本：石碑、笔记、留言、书页
│  ├─ characters/             <- 角色故事/语音（不含攻略、配队、数值）
│  ├─ weapons/                <- 武器故事
│  ├─ artifacts/              <- 圣遗物故事
│  ├─ items/                  <- 材料、食物、任务道具、摆设
│  ├─ voices/                 <- NPC 对话 / 角色逸闻 / 角色彩蛋（2,401 篇）
│  ├─ geography/              <- 地理志、地区文本
│  ├─ events/                 <- 活动剧情/活动设定
│  ├─ notices/                <- 官方公告、版本说明（55 篇）
│  └─ manga/                  <- 官方漫画文本（未做）
├─ knowledge/                 <- 人工知识层
│  ├─ entities/               <- 人物、国家、组织、地点、概念、生物
│  ├─ events/                 <- 事件条目
│  ├─ timelines/              <- 时间线与年代
│  ├─ claims/                 <- 关键论断、矛盾说法、考据
│  └─ glossary/               <- 术语、别名、译名对照
├─ schema/                    <- SQLite 表结构、front matter JSON Schema
├─ manifests/                 <- 数据源清单、覆盖矩阵、试点清单
├─ scripts/                   <- 抓取、解析、入库、校验脚本
├─ config/                    <- 抓取与项目配置
├─ db/                        <- SQLite 数据库文件（本地生成）
├─ exports/                   <- 按主题导出的阅读版/表格
└─ tools/                     <- 本地便携工具链（不提交到版本库）
```

### 为什么正文按“类型”而不是按“来源”放？

同一段剧情可能来自 BWiki、米游社、官方页或数据包。按来源放会制造四份正文，难以对照；按类型放，一份正文可以挂多个来源。来源信息放在 front matter 和 `document_sources` 表里。

---

## 5. 首批范围（建议）

先做一条“从抓取到可检索”的竖切，而不是一上来全量：

| 优先级 | 内容 | 理由 |
|---|---|---|
| P0 | 魔神任务（主线） | 世界观主干，引用频率最高 |
| P0 | 游戏内书籍 | 大量历史、神话、寓言，信息密度高 |
| P0 | 角色资料/角色故事 | 角色视角的一手叙述，常含关键设定 |
| P1 | 传说任务、世界任务 | 补充地区史与人物关系 |
| P1 | 武器/圣遗物故事 | 碎片化但常含远古设定 |
| P1 | 活动剧情 | 限时内容，错过就难补 |
| P2 | 材料/食物/道具描述 | 数量大、单条短，适合批量生成 |
| P2 | NPC 全部对话 | 噪声大、重复多，最后再做 |
| P2 | 漫画、PV 文本 | 跨媒介，需单独标注 |

> 进度：上表除「漫画、PV 文本」外已全部落地；官方公告与 NPC 对话于第 6 步补齐。
> 详见 [`HANDOFF.md`](HANDOFF.md)。

详细试点清单见 [`docs/04-首批试点.md`](docs/04-首批试点.md)。

---

## 6. 推荐的使用方式

### 阅读

用 Obsidian 打开项目根目录。`corpus/` 是正文库，`knowledge/` 是知识库；front matter 会变成属性，`[[双链]]` 可以连接人物、地区、事件。

### 检索

- 轻量：用编辑器的全局搜索，或 `scripts/Search-Corpus.ps1`；
- 结构化：用 SQLite + FTS5，按人物、地区、版本、剧透等级过滤；
- 语义：后续可选，不作为第一版依赖。

### 核对

每条正文都应有：

```yaml
source:
  - source_id: obc
    url: https://baike.mihoyo.com/ys/obc/content/399/detail
    retrieved_at: 2026-11-04T01:42:05+08:00
    revision_id: "1761787170"
```

数据库里 `sections` 表保存每一段，`claims` 表保存“某角色/某本书声称某事”，两者用 `section_id` 关联。

---

## 7. 现在能做什么、还不能做什么

**现在可以：**

- 打开数据库 `db/genshin_lore.sqlite3`（含 9 个来源、2,035 篇文档、330,417 个段落）；
- 用 `scripts/fetch_obc.py` 抓观测枢 entry_page / 搜索 / 频道树；
- 用 `scripts/render_obc.py` 把 entry_page 渲染成 Markdown 草稿（任务/书籍/角色/散落文本）；
- 用 `scripts/build_obc_index.py` 生成书籍/散落文本/任务索引；
- 用 `scripts/resolve_versions_bwiki.py` 批量补书籍版本；
- 用 `scripts/load_markdown.py` 导入 SQLite（含版本来源/置信度）；
- 用 `scripts/search.py 钟离` 做中文全文检索；
- 用 `scripts/check_env.ps1` 检查工具链；
- 用 `scripts/Search-Corpus.ps1` 在已有 Markdown 中搜索。

**现在还不能：**

- 一键抓取观测枢全部频道；
- 自动把图片里的对话 OCR 成文本；
- 自动判断设定真伪；
- 保证观测枢/BWiki 页面结构永久稳定。

---

## 8. 下一步

1. **书籍已归档**：92 本在 `corpus/books/`，`503` 重复卷跳过。
2. **正文层已闭合**：705 条散落文本在 `corpus/scattered/`，1,065 条有正文任务在 `corpus/quests/`，32 条 OBC 空壳任务隔离在 `corpus/quests/_pending/`；`exports/obc-batch/` 已清空。Git 已初始化，数据库有备份。
3. **任务结构已理清**：邀约归 `hangout/`、间章归 `interlude/`，18 篇系列页加 `系列任务` 标签，重复组逐组判定（`manifests/duplicates.csv`）。
4. **剩余尾巴**：32 条空壳只能从游戏数据包补（BWiki 也没有）；11 个多幕系列页是否拆分需先定规范。
5. **补缺口**：《白之公主与六侏儒》其余卷、书籍 1158 版本、479 条散落文本版本；任务版本已补齐。
6. **武器/圣遗物已完成**：252 把武器 + 63 套圣遗物入库，版本由 BWiki 补齐，244/315 与 BWiki 逐字一致。
7. **活动/成就已处理**：275 条活动里 47 条有叙事，已归档；1,558 条成就做成 CSV，不进正文层。
8. **地理/物品已完成**：观景点 264 篇、区域做成 `regions.csv`；材料/食物/动物/道具 2,622 条入库（版本全部 unknown）。
9. **剩下 P3**：官方公告、漫画、NPC 对话、七圣召唤。
10. **最后做知识层**：实体、关系、时间线、claims，不要反过来先画图。

具体拆解见 [`docs/03-实施路线图.md`](docs/03-实施路线图.md)。

---

## 9. 重要声明

- 原神游戏文本、名称、图像的版权归米哈游（HoYoverse）及原权利方所有。
- 观测枢是官方平台，但条目由社区编辑；按“个人研究使用”处理，不公开全文。
- 本库用于**个人学习、研究、整理**，不应公开分发全文或做成公开镜像站。
- Wiki 文本另有许可（如 CC BY-SA），公开引用时必须遵守对应条款并署名。
- 抓取应遵守 robots.txt、站点条款和合理频率；不绕过登录、付费或访问控制。
- 如果你要公开分享，建议只分享**索引、统计、自己写的考据和短引用**，不要分享全文。

详见 [`NOTICE.md`](NOTICE.md)。

---

## 10. 文档索引

- [`HANDOFF.md`](HANDOFF.md)：交接文档：当前进度、缺口、命令与下一步计划
- [`docs/00-总体设计.md`](docs/00-总体设计.md)：架构、关键决策、成功标准
- [`docs/01-数据源与合规.md`](docs/01-数据源与合规.md)：各来源的用途、访问方式、实测状态
- [`docs/02-数据规范.md`](docs/02-数据规范.md)：ID、front matter、分段、剧透、版本规范
- [`docs/03-实施路线图.md`](docs/03-实施路线图.md)：分阶段任务与验收标准
- [`docs/04-首批试点.md`](docs/04-首批试点.md)：15–20 篇试点清单
- [`docs/05-观测枢评估.md`](docs/05-观测枢评估.md)：官方平台观测枢的 API、结构与主源评估
- [`docs/06-访问与检索.md`](docs/06-访问与检索.md)：CLI、Obsidian、SQLite、Python、Web UI 的访问方式
- [`webui/README.md`](webui/README.md)：本地 Web UI 的启动、路由与 API
- [`exports/obc-evaluation/coverage-audit.md`](exports/obc-evaluation/coverage-audit.md)：当前覆盖审计与缺口清单
- [`schema/README.md`](schema/README.md)：数据库表说明与建库顺序
- [`manifests/sources.csv`](manifests/sources.csv)：数据源清单
- [`manifests/coverage.csv`](manifests/coverage.csv)：覆盖矩阵
- [`manifests/obc-index.csv`](manifests/obc-index.csv)：书籍/散落文本/任务的 1,900 条频道索引
- [`manifests/character-index.csv`](manifests/character-index.csv)：138 个角色频道索引（136 个已入库）
- [`manifests/versions.csv`](manifests/versions.csv)：游戏版本标记与来源
- [`exports/obc-evaluation/README.md`](exports/obc-evaluation/README.md)：非书草稿、分析文件与已知问题
- [`exports/obc-batch/`](exports/obc-batch/)：已清空，只剩两份批次台账 CSV
- [`corpus/quests/index.csv`](corpus/quests/index.csv)：1,069 条任务正文索引
- [`corpus/scattered/index.csv`](corpus/scattered/index.csv)：706 条散落文本索引
- [`corpus/scattered/README.md`](corpus/scattered/README.md)：散落文本归档规则、命名与已知问题
- [`corpus/weapons/README.md`](corpus/weapons/README.md)：武器故事归档、版本来源与 BWiki 对照
- [`corpus/artifacts/README.md`](corpus/artifacts/README.md)：圣遗物 5 部位结构、仅 1 部位的套装说明
- [`corpus/events/README.md`](corpus/events/README.md)：活动只收简介与彩蛋、47/275 的原因
- [`corpus/geography/README.md`](corpus/geography/README.md)：观景点正文、区域做成 CSV 的原因
- [`corpus/items/README.md`](corpus/items/README.md)：材料/食物/动物/道具只收描述、版本为何未知
- [`manifests/achievements.csv`](manifests/achievements.csv)：1,558 条成就索引
- [`manifests/regions.csv`](manifests/regions.csv)：71 个区域的任务/怪物/素材索引
- [`corpus/quests/_pending/README.md`](corpus/quests/_pending/README.md)：32 条空壳任务说明
- [`corpus/characters/index.csv`](corpus/characters/index.csv)：136 个角色正文索引
- [`corpus/books/index.csv`](corpus/books/index.csv)：92 本书的版本/地区索引





