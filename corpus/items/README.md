# corpus/items · 材料 / 食物 / 动物 / 道具

观测枢四个物品频道共 **2,622** 条，按频道分目录。只收**描述**与**背景故事**，不含使用效果、配方、获取途径、分布、攻略。

```text
corpus/items/
├─ 材料/     2,058
├─ 食物/       325
├─ 动物/       227
├─ 道具/        12
└─ index.csv
```

`index.csv` 字段：

```text
doc_id,title,subtype,path
```

## 内容来源

| 字段 | 来源 | 说明 |
|---|---|---|
| 描述 | OBC `material_base_info.attr["描述"]` | 材料/食物/道具的主描述 |
| 背景故事 | OBC `good_desc`（模块名含「背景」或「故事」） | 鱼类、部分动物的长文本 |
| 稀有度 | OBC `material_base_info.star` | 写入正文「物品信息」，不进 front matter |

**丢弃**的字段：`用途`、`主要分布`、`使用效果`、`配方`、`获取方式`（`materials.key`）、`相关信息` 表格、`<名称>分布` 折叠面板、攻略推荐。这些是玩法信息，不是叙事。

- 食物页常带三个品质变体（奇怪 / 正常 / 美味），按 `material_base_info` 的顺序各成一节；
- 12 组同名材料（如 `「镇物」`、`铁钥匙`、`藏宝图`）用 ` (obc-<content_id>)` 后缀消歧；
- 2,622 条全部有描述，`manifests/item-skip.csv` 为空。

## 版本

**2,622 条版本全部为 `unknown`**。观测枢的物品频道没有版本筛选字段（只有食物类型、星级、获取方式、动物类型等），BWiki 的材料页也没有统一的 `实装版本`。

按项目约定**不猜版本**：物品的世界观价值主要在文本本身，版本时间线的边际收益低。将来若要补，只能接游戏数据包或逐页查 BWiki。

## 已知问题

- 食物频道的 `食物类型`（恢复类/攻击类/防御类等）没有入库，目前 subtype 只到「食物」这一层；
- `材料` 里混有任务道具、活动道具（如 `「真视药剂」特化版`），没有进一步细分。

## 重新导入

```powershell
.\tools\python\python.exe scripts\load_markdown.py --dir corpus\items --bulk
```

> 物品是叙事文本，入库**用 jieba 分词**（不加 `--no-segment`），与 books、scattered、weapons 一致。

生成命令：

```powershell
.\tools\python\python.exe scripts\render_items.py --apply
```
