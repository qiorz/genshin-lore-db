# knowledge · 知识层

> 这里是“解释层”，不是原文层。每条结论都应能回到 `corpus/` 的段落或 `db/` 的 `section_id`。

## 1. 目录

```text
knowledge/
├─ entities/
│  ├─ characters/        # 人物
│  ├─ nations/           # 国家/地区
│  ├─ organizations/     # 组织/阵营
│  ├─ locations/         # 地点
│  ├─ concepts/          # 概念/设定
│  └─ creatures/         # 非人存在/生物/龙
├─ events/               # 事件条目
├─ timelines/            # 时间线
├─ claims/               # 争议说法/考据
└─ glossary/             # 术语、别名、译名
```

## 2. 实体模板

```markdown
---
id: entity.example
type: character
canonical_name: 示例角色
canonical_name_en: Example
aliases:
  - 示例别名
spoiler_level: 1
status: draft
tags: [璃月, 七神]
---

## 简介

一句话说明“是谁/是什么”，不写剧情推测。

## 关键设定

- 身份：……
- 所属：……
- 相关事件：……

## 证据

- [[quest.archon.example]]：……
- [[book.example]]：……

## 待考

- ……
```

`type` 可选：

```text
character / nation / organization / location / deity /
creature / concept / event / item / title / other
```

## 3. 关系与 claims

关系适合“稳定、可复用”的断言：

```text
钟离 —member_of→ 往生堂
钟离 —is→ 摩拉克斯
璃月 —located_in→ 提瓦特
```

claims 适合“有视角、有争议、可能矛盾”的说法：

```markdown
---
id: claim.example
subject: entity.khaenriah
predicate: 覆灭原因
perspective: 某本书/某角色
confidence: disputed
status: open
sources:
  - doc_id: book.example
    section: "..."
---

## 说法

……

## 不同来源

- 来源 A：……
- 来源 B：……

## 备注

……
```

不要在实体页里把争议写成唯一结论；把不同说法放 claims，并在实体页链接过去。

## 4. 时间线

- 先相对顺序，后绝对年份；
- 每条标 `certainty`：`exact` / `approximate` / `relative` / `unknown`；
- 现实版本时间和提瓦特纪年分开；
- 不确定的年代用区间/约数，不要伪造精确年份；
- 每条尽量链接到事件/文档/段落。

## 5. Glossary

`glossary/` 放：

- 中文/英文/日文译名对照；
- 同一实体的不同写法（如“挪德卡莱/诺德卡莱”）；
- 易混概念（如“神之眼/神之心/邪眼”）；
- 简称/黑话/社区常用名。

格式：

```markdown
| 规范名 | 别名 | 语言 | 备注 |
|---|---|---|---|
| 挪德卡莱 | 诺德卡莱 | zh | 统一用“挪德卡莱” |
```

## 6. 规则

- 先有证据，再写结论；
- 区分“原文说”“某人说”“我认为”；
- 不用“官方设定”包装玩家推测；
- 不复制大段原文到知识层，用链接/短引用；
- 每个实体/事件/claim 有稳定 ID；
- 结论变化时保留旧说法（`superseded`），不要悄悄改历史；
- 涉及剧透的实体/关系标 `spoiler_level`。

## 7. 和数据库的关系

```text
knowledge/*.md  ←→  entities / entity_relations / claims / events / timeline_entries
corpus/*.md     ←→  documents / sections
```

知识层可以先用 Markdown 维护，等结构稳定后再导入数据库。不要为了“入库”把还没想清楚的结论硬塞进表里。

## 8. 第一批种子（2026-11-05）

`knowledge/seed.yaml` 是**供人工校对的第一批种子**，不是最终正文。
校对确认后按类拆进 `entities/` 与 `claims/` 的 Markdown；在此之前不要改它当结论用。

### 证据引用规范（重要）

`sections.section_id` 在**全量重导后会变**（loader 是 DELETE + INSERT），
所以知识层**不硬编码 section_id**。每条证据只写两样：

```yaml
doc: quest.obc.508097
quote: "所幸温迪阁下…嗯，也就是巴巴托斯大人也愿意帮忙"
```

`scripts/load_knowledge.py` 在灌库时用 `doc_id + quote 前缀` 现场查出当前
`section_id` / `ordinal` 并写入；查不到就报错，绝不静默跳过。
这样 `corpus/` 重导之后，重跑一次灌库脚本就能重新对齐证据。

### 与检索的关系

**知识层是额外增加的入口，不替换原文检索。**
`/` 与 `/search` 的结果卡片、高亮、筛选、分页保持原样；
实体卡片走独立页面 `/entities` 与 `/api/entities`，
搜索页底部只额外加一个默认折叠的「相关实体」提示区。
原文某一句话永远是这个库最根本的检索单位。

## 9. 第二批（2026-11-05）：关系 / 时间线 / 正式卡片

第一批 `seed.yaml` 已人工校对通过（`status: reviewed`），作为冻结记录不再改结论。
第二批内容全部放 `seed-stage2.yaml`。

### 权威源 → 查询层 → 阅读视图

```text
knowledge/seed.yaml + seed-stage2.yaml   可编辑的权威源（人工维护）
        ↓ scripts/load_knowledge.py --apply
db/genshin_lore.sqlite3                  查询层（entities / relations / claims / events / timeline）
        ↓ scripts/export_entity_cards.py --apply
knowledge/entities|claims|events|timelines/*.md   导出的阅读视图（生成物，不要手改）
```

要改结论就改 seed，依次重跑两个脚本。证据仍只用 `doc_id + 短引用`，
`corpus/` 全量重导后重跑灌库脚本即可重新对齐 `section_id`。

本批生成的 50 份 Markdown：30 张实体卡、10 张说法卡、8 张事件卡、2 张时间线汇总。

### 两条时间线互不换算（重要）

| `era` | 条数 | 含义 | `certainty` |
|---|---:|---|---|
| `release` | 53 | 现实世界官方版本更新说明的上线日期（1.1→7.2，无断档） | `exact` |
| `teyvat` | 8 | 提瓦特世界的事件先后（魔神战争、坎瑞亚灾变、世界树修复等） | `relative` / `approximate` |

- 现实版本线由 `load_knowledge.py` 从 `corpus/notices/` 的官方公告**自动生成**，不手写、不猜测；
- 提瓦特线**只有相对先后**：`sort_key` 是负数，只表示顺序，不代表任何年代数值；
- 原文写「约两千六百年前」「五百年前」的一律保留为约数文字，**不写 `absolute_year`**；
- 两者分开存放在同一张表的 `era` 字段，UI 分两个区块展示，绝不互相换算。

### 关系与说法的分工

- `entity_relations` 只收**稳定、可复用**的断言（谁属于哪个组织、哪国由哪位神明统御）；
- `claims` 收**有视角、有争议**的说法，置信度故意不统一；
- 角色台词、NPC 语音、编校推断分别标 `likely` / `speculative`，不自动等于设定；
- 例如「教令院推行虚空」用 `operated_by` 而非 `created_by`，因为原文没直述发明者。

### 复核入口

- Web UI：`/entities`、`/entity/<entity_id>`、`/timeline`；
- JSON：`/api/entities`、`/api/entity?id=...`、`/api/timeline?era=teyvat`；
- 报告：`exports/obc-evaluation/knowledge-seed-report.md`。
