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
| `regions.csv` | 区域结构化索引：任务/怪物/资源/机关/NPC（790 行，71 区域） |
| `achievements.csv` | 成就索引：名称/描述/成就集/版本/隐藏/每日委托（1,558 条） |
| `event-skip.csv` | 未归档的活动页及原因（228 条，均为无叙事内容） |
| `item-skip.csv` | 未归档的物品及原因（**0 条**，2,622 条全部有描述） |
| `duplicates.csv` | 同文重复组判定 |
| `equipment-bwiki-compare.csv` | 武器/圣遗物的 OBC 与 BWiki 字数对照 |
| `bwiki-probe.csv` | 32 条空壳任务的 BWiki 同名页探测结果 |
| `tag-vocabulary.md` | 标签词表 |
| `terms.txt` | jieba 自定义词典 |

## `achievements.csv`

成就**不进正文层**：1,558 条，每行一个成就，来源是观测枢「成就」频道的 1,626 个页面。

```text
name,description,set,version,hidden,daily,source_page_id,source_page_title
```

- 页面有两种形态：94 个「成就集页」含 `成就列表` 表格（一次给出多行），1,532 个「单条页」只讲一个成就；
- 描述取自 `material_base_info` 的「成就描述」字段，成就集取自「成就集」字段；
- `hidden` / `daily` 来自频道列表 ext 的「隐藏成就」「每日委托成就」；
- 14 条的 `hidden`/`daily` 为空：它们在成就集表格里出现，但频道里没有同名条目可回查。

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
