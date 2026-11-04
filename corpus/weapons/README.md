# corpus/weapons · 武器故事

观测枢武器词条 **252** 把，按武器类型分目录。只收**装备描述**与**故事**，不含精炼数值、属性、推荐角色。

```text
corpus/weapons/
├─ 单手剑/     59
├─ 双手剑/     45
├─ 弓/         50
├─ 法器/       55
├─ 长柄武器/   43
└─ index.csv
```

`index.csv` 字段：

```text
doc_id,title,subtype,version,version_source,version_confidence,path
```

## 内容来源

| 字段 | 来源 | 说明 |
|---|---|---|
| 装备描述 | OBC `装备描述` 组件 | 取 `<hr>` **之后**的一段；之前是精炼数值，丢弃 |
| 故事 | OBC `相关故事` 组件 | 完整故事正文 |
| 版本 | **BWiki** `|实装版本=` | OBC 武器频道没有版本字段 |

- 252/252 版本已标，`version_source: bwiki`、`version_confidence: confirmed`；
- 11 把一星武器没有精炼段（`good_desc` 里没有 `<hr>`），整段就是装备描述，已单独处理；
- `星锋剑`（509223）OBC 故事原文是「暂无」，已用 BWiki 补全并加第二条 `source`。

## 与 BWiki 对照

`manifests/equipment-bwiki-compare.csv` 记录每把武器的 OBC 故事与 BWiki 故事字数：

```text
315 篇（含圣遗物）中，244 篇两边内容完全一致（ratio = 1.0）
武器部分无 OBC 缺失，仅星锋剑需要补
```

对照用的 BWiki 字段：武器 `|故事=`、`|介绍=`、`|实装版本=`。

## 重新导入

```powershell
.\tools\python\python.exe scripts\load_markdown.py --dir corpus\weapons --bulk
```

> 武器/圣遗物是叙事文本，入库**用 jieba 分词**（不加 `--no-segment`），与 books、scattered 一致。
