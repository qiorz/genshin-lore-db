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
