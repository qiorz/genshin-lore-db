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
knowledge/seed*.yaml                     可编辑的权威源（人工维护，按批新增）
        ↓ scripts/load_knowledge.py --apply
db/genshin_lore.sqlite3                  查询层（entities / relations / claims / events / timeline）
        ↓ scripts/export_entity_cards.py --apply
knowledge/entities|claims|events|timelines/*.md   导出的阅读视图（生成物，不要手改）
```

要改结论就改 seed，依次重跑两个脚本。证据仍只用 `doc_id + 短引用`，
`corpus/` 全量重导后重跑灌库脚本即可重新对齐 `section_id`。

本批生成的 50 份 Markdown：30 张实体卡、10 张说法卡、8 张事件卡、2 张时间线汇总
（第三批扩量后实体卡共 100 张，第四批到 250 张，见 §10–§11）。

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

## 10. 第三批（2026-11-05）：实体扩量到 100

用户要求把实体扩到 100。扩量方式是**证据驱动**，不是照着名单硬填：

| 环节 | 做法 |
|---|---|
| 挖候选 | `scripts/mine_entities.py` 拿词表去 `corpus/` 里反查真实段落，按文档类型打分（任务/书籍/角色 3 分，公告 −3 分），噪声词扣分，名字出现在段首加分 |
| 人工取舍 | 结果落 `entity-candidates.csv`，收谁不收谁由人过目 |
| 入库 | `seed-stage3.yaml` 70 个实体，每条都有 `doc_id` + 原话，干跑 147/147 命中 |
| 描述口径 | 只写中性分类标签（「证据出自某地区文档的人物条目」），**不写剧情结论**；具体设定点出处核对 |
| 别名 | 只收**同一段原文里同时出现**的称呼（皇女/博士/丑角/仆人/战争之国），不从百科列表抄 |

### 新表 `entity_evidence`

`claims` 回答「谁在什么立场说了什么」，扩量实体多数还没有这种断言，
但它们确实被原文提到过。于是单开一张轻量表：

```text
entity_evidence(entity_id, doc_id, section_id, quote, is_primary)
```

- 详情页「关联原文」逐句列出原话 + 可点回 `section_id` 所在段落；
- 与 `claims` 严格分开：这里只证明「原文提到过它」，不承载任何结论；
- 无稳定主键，灌库时按 `entity_id` 先删后插，保证幂等；
- 迁移文件：`schema/migrations/005_add_entity_evidence.sql`。

### 待复核

70 张新卡 `status=draft`（卡片与列表页都标「待复核」）。别名和出处可信，
**描述需要人工抽样复核**；复核通过的卡片改成 `status: reviewed` 再重跑灌库脚本即可。

## 11. 第四批（2026-11-05）：实体 100 → 250

目标数由用户定为「最终约 400、先到 250」。这一批与第三批的方法不同：

| 类别 | 名单来源 | 是否靠猜 |
|---|---|---|
| 角色 | `documents` 里 136 篇 `doc_type='character'` 角色页，一篇一人 | 否，页面本身即权威名单 |
| 地点 / 组织 | `build_stage4.py` 内的候选表（只给名字） | 收不收由「库里有没有含这个名字的真实句子」决定，落空即 skip |
| 描述 | 角色取 `manifests/character-index.csv` 的地区/元素/武器/星级；其余为中性分类标签 | 否，只写游戏内标注 |

结果：character 37→125、location 16→63、organization 11→26，合计 250；
`entity_evidence` 103→253，每条都解析到了 `section_id`。

### 两个踩过的坑

1. **按 `。` 切句会切坏引文**。「…。」——某人 会被切成两半，证据开头变成 `」`。
   现在先跟踪「」『』括号深度，深度为 0 时才断句；同时过滤「过场动画」「【纯标题】」这类
   舞台指示，避免拿旁白当证据。
2. **`entity_id` 需要拼音**。中文名转 `entity.ban-ni-te` 依赖 `pypinyin`（生成脚本的依赖，
   不是运行时依赖）；没装时退回文档号，功能不受影响但 id 难读。

### 复核顺序建议

不要把 220 张 draft 卡平铺着复核。先按「会不会被别处引用」排序：
角色 125 张里，先看 88 张第四批新增的（第三批那 70 张已抽过）；
地点 63 张里先看层岩巨渊、挪德卡莱这类会出现在多篇任务里的。复核通过的改 `status: reviewed`，
重跑 `load_knowledge.py --apply` 即生效。

## 12. 复核流程（190 张待核）

卡片攒到 250 张后，复核成了瓶颈。这里定了两件事：**先看哪些**、**看完记在哪**。

### 先看哪些

`python scripts/review_queue.py --top 30` 会输出 `exports/review/entity-review-queue.md`。

排序不是拍脑袋：先看「出现在多少篇**任务**正文里」，再看「出现在多少篇文档里」。
理由很实际——`枫丹` 出现在 268 篇任务里，它要是类型写错，错的是整库的引用关系；
一个只在两篇观景点文本里出现的 NPC，错了也没人引用。

脚本同时做三项**机械校验**，不用人判断：

1. 引文是否真的在它声称的那一篇里；
2. 名字是否真的出现在引文里；
3. 人物的类型是否与来源角色页一致。

人只需要判断：**类型对不对、名字是不是通行写法、别名该不该补**。

### 看完记在哪

结论写 `knowledge/review-state.yaml`，**不写进 `seed-*.yaml`**：

```yaml
reviewed:
  - id: entity.fontaine
    date: 2026-11-05
    note: 抽检：类型/名字通行写法/引文命中，三者一致
rejected: []
```

原因很直接：`seed-stage3.yaml`、`seed-stage4.yaml` 是生成物，重新生成会覆盖手写状态。
`load_knowledge.py` 与 `export_entity_cards.py` 都读这份清单，命中即 `status: reviewed`。

```bash
python scripts/review_queue.py --mark entity.fontaine --note "类型/名字/引文一致"
python scripts/review_queue.py --unmark entity.fontaine
python scripts/load_knowledge.py --apply      # 库里状态跟着变
python scripts/export_entity_cards.py --apply # 卡片也跟着变
```

### 首轮结果

按队列核了前 30 张，三处问题已修：`枫丹科学院` 分类由地点改组织、
第三批描述里的「证据出自{region}地区文档」去掉（会读成归属）、
`▌…` 版式标题与「…：」提示句不再当证据。

## 13. 第五批：收尾到 400

第 13 步定过上限 400，这一批把它填满。四类来源的可靠程度不同，做法也不同：

| 类别 | 名单从哪来 | 关键判断 |
|---|---|---|
| NPC 人物 | `sections.speaker` 的台词量统计，≥50 段 | 台词多 ≈ 剧情分量足；比人工列名单客观，也不必认识每个 NPC |
| 概念 / 生物 / 神明 / 组织 / 事件 | 脚本里的候选表，只给名字 | 收不收看库里有没有含这个名字的**可用句子**；落空即 skip |
| 描述 | NPC 写「台词 N 段，出现在 M 篇文档」，其余写分类标签 | 不写剧情结论 |

### 泛用词不建卡

`契约`、`仪式`、`血亲`、`祭司`、`誓约`、`圣遗物`、`神谕`、`梦境`、`花海`、`终末`
这十个词看似「概念」，但在任何一句话里都能命中，收进来只会稀释检索。
判断标准：**这个词能不能指向一组具体设定的原文**。不能，就不收。

### 两个清理工具

- `load_knowledge.py --prune`：删掉「库里存在、但任何 seed 都没有」的实体。
  改候选表把某个泛用词去掉后，它不会自动消失，需要显式剪枝。
- `scripts/prune_cards.py`：删掉过期卡与同 id 多目录的重复副本。
  实体换 `entity_type` 后卡片会写到新目录，旧的那份不会自动删。

> 卡片是 `entity_type` 分目录的，所以「改类型」天然会产生残留文件；
> 每次改完类型，跑一次 `prune_cards.py` 再提交。

### 最终形状

```text
character 191 · location 62 · concept 43 · organization 35
creature 29 · event 18 · deity 14 · nation 8     合计 400
entity_evidence 403 · entity_names 434
```
