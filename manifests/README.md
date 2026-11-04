# manifests · 清单与索引

| 文件 | 作用 |
|---|---|
| `sources.csv` | 数据源登记：类型、入口、许可、访问方式、优先级 |
| `coverage.csv` | 覆盖矩阵：要收什么、优先级、来源提示 |
| `seed-pilot.csv` | 首批试点清单 |
| `versions.csv` | 逐条版本标记：`entry_page_id → version / source / confidence` |
| `version-labels.csv` | 观测枢“月之一/月之四……”→ 数字版本映射 |
| `obc-index.csv` | 观测枢书籍 93 + 散落文本 706 + 任务 1,101 的频道索引 |
| `character-index.csv` | 观测枢角色 138 的频道索引（136 已入库） |
| `tag-vocabulary.md` | 标签词表 |
| `terms.txt` | jieba 自定义词典 |

## 版本约定

```text
version_source:
  obc-filter             观测枢任务频道 ext 的“版本号”
  bwiki                  BWiki 的“所属版本/实装版本”
  derived-related-quest  从散落文本的“相关任务”推导
  official / manual / web
  unknown

version_confidence:
  confirmed / likely / inferred / estimated / unknown
```

规则：找不到就留空 + `unknown`，不猜。

## `obc-index.csv`

从观测枢频道列表生成，每行一条：

```text
channel_id,content_id,entry_page_id,doc_type,title,region,category,
version_label,version,version_source,version_confidence,
activity_limited,url,status
```

当前数量：

```text
book     93
lore    706
quest  1101
total  1900
```

当前已加载（`status=loaded`）：书籍 92/93（`503` 为《林间风》重复卷，标 `skipped-duplicate`）、散落文本 706/706、任务 1,101/1,101。

书籍版本由 `scripts/resolve_versions_bwiki.py` 用 BWiki SMW 批量补：93 本中 92 本有 `实装版本`；`残破的笔记`（1158）仍为 `unknown`。散落文本大多没有版本字段，能通过“相关任务”推导的才标 `inferred`。
