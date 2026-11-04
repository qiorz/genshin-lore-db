# 观测枢输出

本目录保留分析文件。92 本书在 [`corpus/books/`](../../corpus/books/index.csv)；1,069 条有正文任务在 [`corpus/quests/`](../../corpus/quests/index.csv)（另有 32 条空壳在 `_pending/`）；136 个角色在 [`corpus/characters/`](../../corpus/characters/index.csv)；706 条散落文本在 [`corpus/scattered/`](../../corpus/scattered/index.csv)。

> **注**：本目录下的 `coverage-audit.md`、`crosscheck.md`、`bwiki-quest-fill.txt` 等是 2026-11-04 迁移**之前**的审计快照，其中的 `1,051 / 50 条待补`、`exports/obc-batch 路径` 均为当时状态，不再更新。当前状态以 [`HANDOFF.md`](../../HANDOFF.md) 为准。

## 文件

| 文件 | 内容 | 版本 |
|---|---|---|
| `summary.txt` | 当前数据库的版本/来源/段落统计 | — |
| `summary.json` | 同上，机器可读 | — |
| `db-summary.txt` | 当前数据库的文档/版本/段落统计 | — |
| `channel_facets.txt` | 频道条目数、筛选器、版本字段统计 | — |
| `quest-399-modules.txt` | 任务页 88 个 module 的顺序与类型 | — |
| `quest-399-dialogue-headers.txt` | 11 个剧情模块的首段/场景字幕 | — |
| `compare_report.txt` | 观测枢 vs BWiki 的字数/样本对照 | — |
| `crosscheck.md` | 5 书 / 5 任务 / 5 散落文本抽样报告；任务 50 条无对话的结构问题 | — |
| `probe_v2.txt` | 版本字段、频道列表、散落文本搜索探测 | — |
| `bwiki-stub-probe.md` | 32 条空壳任务的 BWiki 同名页面探测结论（0 条可补） | 2026-11-04 |
| `search-*.txt` | SQLite FTS 检索测试结果 | — |

书籍目录：

```text
corpus/books/index.csv          # 92 本书的 doc_id / 标题 / 地区 / 版本 / 路径
corpus/books/<地区>/<书名>.md   # 按地区分目录
```

## 生成方式

```powershell
.\tools\python\python.exe scripts\fetch_obc.py --entry-page-id 399 501 516 3470 1290 507704 503070 501754 --force

.\tools\python\python.exe scripts\render_obc.py --entry raw\official_site\obc\entries\399.json `
    --type quest --doc-id quest.obc.399 --region 蒙德 `
    --out exports\obc-batch\quest-399.md

.\tools\python\python.exe scripts\render_obc.py --entry raw\official_site\obc\entries\507704.json `
    --type lore --doc-id lore.obc.507704 --region 挪德卡莱 `
    --out exports\obc-batch\lore-507704.md

.\tools\python\python.exe scripts\validate_frontmatter.py exports\obc-batch\quest-399.md
.\tools\python\python.exe scripts\load_markdown.py exports\obc-batch\quest-399.md
.\tools\python\python.exe scripts\search.py 钟离
```

## 已知问题（试点版）

1. **任务模块顺序**：观测枢的 88 个 module 不完全按剧情顺序；部分剧情模块没有场景字幕，标题回退为“剧情对话 N”，不伪造子任务名。
2. **对话图去重**：当前按 `seen` 去重，共同分支只渲染一次；完整图仍在 raw JSON。
3. **分支标记**：`> **分支**` / `> **分支 1**` 还比较粗糙，后续可以改成折叠块或 JSONL。
4. **角色过滤**：当前只按模块名保留故事/描述/神之心/关联语音，可能漏掉“神之眼”或其他命名变体；已去掉属性/命之座/配队。
5. **版本**：任务用观测枢频道筛选，书/角色用 BWiki；散落文本用“相关任务”推导，推导不到就 `unknown`，不猜。
6. **社区文本**：不是官方逐字原文，关键段落仍需与游戏内/BWiki/数据包对照。

## 下一步

- 706 条散落文本、1,101 条任务已入库；正文已于 2026-11-04 全部迁入 `corpus/scattered/` 与 `corpus/quests/`，`exports/obc-batch/` 已清空；
- 书籍已归档，后续只补《白之公主与六侏儒》其余卷和 1158 的版本；
- 任务尾巴（32 条空壳、13 组同文重复、一篇一幕审计）处理完，再做武器/圣遗物，最后做知识层。




