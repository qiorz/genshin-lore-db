# exports/obc-batch · 已清空（2026-11-04）

**2026-11-04：706 条散落文本与 50 条任务草稿已全部迁出，本目录不再存放正文。**

迁移去向：

```text
lore-*.md   706 条 -> corpus/scattered/<地区>/
quest-*.md   19 条 -> corpus/quests/<subtype>/     （有正文）
quest-*.md   31 条 -> corpus/quests/_pending/      （OBC 无剧情对话）
```

保留文件：

```text
lore-manifest.csv   散落文本清单（迁移前的来源台账，保留作溯源）
quest-manifest.csv  任务清单（同上）
```

## 为什么还留着这个目录

这两份 manifest 是当时抓取的批次台账，记录了每条 OBC entry 的归类与状态，
和新生成的 `corpus/*/index.csv` 用途不同：前者是「抓了什么」，后者是「现在在哪」。
不参与建库，可随时删除。

## 正文位置

- 散落文本：`corpus/scattered/`
- 任务：`corpus/quests/`
- 空壳任务：`corpus/quests/_pending/`
