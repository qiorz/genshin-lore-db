# corpus/geography · 地理与观景点

观测枢「观景点」频道 264 条，按地区归档。区域（71 个）没有散文正文，只做成结构化索引 `manifests/regions.csv`。

```text
corpus/geography/
├─ 观景点/
│  ├─ 须弥/       52
│  ├─ 纳塔/       42
│  ├─ 挪德卡莱/   40
│  ├─ 璃月/       40
│  ├─ 枫丹/       37
│  ├─ 稻妻/       18
│  ├─ 至冬/       16
│  ├─ 蒙德/       13
│  ├─ 空之神殿/    5
│  └─ 未知/        1
├─ index.csv
└─ README.md
```

`index.csv` 字段：`doc_id,title,subtype,region,path`

## 只收描述

观景点页面结构简单：一个 `collapse_panel` 放描述，另有「观景点位置」（地图）与「考据与原摄」（攻略推荐）。只取前者，图片块和考据全部丢弃。

首行常是地点本名（如「晨曦酒庄」下的「曙光初照的庄园」），保留，因为它比观景点标题更有地理信息。

典型长度：中位 50 字，最长 147 字。它们不是长篇设定，是景点铭牌式的短描写。

## 区域：为什么没有正文

71 个区域页（`永凝冻土`、`霜殛寒峰`…）的模块只有：

```text
同名 collapse_panel   只有区域名，4 个字
地图 base_info        图片
系列任务 rich_base_info   任务链接列表
怪物分布 / 地图资源 / 机关 / NPC  条目列表
描述 map_desc          空
```

没有一句散文。但它们记录了「这个区域有哪些任务、怪物、BOSS、素材、机关」，
对知识层和检索很有用，所以做成 [`manifests/regions.csv`](../../manifests/README.md)：

```text
region,section,key,items,source_page_id
至冬·永凝冻土,怪物分布,BOSS,不灭衍生造物,...
```

790 行，71 个区域，section 分布：地图资源 275、怪物分布 207、系列任务 171、机关 135、NPC 2。

## 版本

观景点频道没有版本字段，`version` 留空、`version_source: unknown`，按约定不猜。

## 重新生成

```powershell
.\tools\python\python.exe scripts\render_geography.py --apply
.\tools\python\python.exe scripts\load_markdown.py --dir corpus\geography --bulk
```
