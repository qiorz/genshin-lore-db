# exports/obc-batch · 散落文本与任务草稿

本目录是观测枢的批量草稿，尚未正式进入 `corpus/`。

```text
lore-*.md          706 条散落文本
quest-*.md         50 条待补任务（1,051 条有正文的任务已在 corpus/quests/）
lore-manifest.csv 散落文本清单
quest-manifest.csv 任务清单
```

## 状态

- 散落文本和 50 条待补任务已导入 SQLite；1,051 条有正文任务在 `corpus/quests/`。
- `obc-index.csv` 中对应条目标 `loaded`。
- 50 条任务仍无对话正文，已在 `notes` 标记待补。
- 散落文本还没有移到 `corpus/scattered/`。

## 类型

- 散落文本：`type: lore`，`subtype: scattered`，只保留交互文本，不提取地图截图。
- 任务：`type: quest`，按 `任务类型` 映射 `archon/story/world/event/other`；对话分支去重；50 条系列页待补。

## 版本

- 任务：观测枢任务频道 `版本号`，1,101/1,101 有版本。
- 散落文本：从“相关任务/成就/活动”推导，226/706 有版本；其余 `unknown`。
- 书籍：BWiki SMW，已归档到 `corpus/books/`。

## 重新导入

```powershell
.\tools\python\python.exe scripts\load_markdown.py --dir exports\obc-batch --pattern 'lore-*.md'
.\tools\python\python.exe scripts\load_markdown.py --dir exports\obc-batch --pattern 'quest-*.md'
```



