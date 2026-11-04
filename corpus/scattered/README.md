# corpus/scattered · 散落文本

地图上的石碑、告示板、留言、笔记、书页等交互文本，共 **706** 篇，按地区归档。
来自观测枢「地图文本」频道，只保留交互文本，不提取地图截图与坐标。

```text
corpus/scattered/
├─ 璃月/        142
├─ 纳塔/        117
├─ 枫丹/        103
├─ 须弥/        103
├─ 挪德卡莱/     87
├─ 蒙德/         53
├─ 稻妻/         45
├─ 至冬/         42
├─ 活动区域/     13   限时活动地图上的文本
├─ 未知/          1
└─ index.csv
```

`index.csv` 字段：

```text
doc_id,title,region,version,version_source,version_confidence,path
```

## 命名

文件名 = `title`，仅替换 Windows 非法字符。同一地区出现同名条目时，全部加 content_id 后缀消歧，例如：

```text
corpus/scattered/璃月/通知【明蕴镇】 (obc-501234).md
corpus/scattered/璃月/告示【归离原】 (obc-501819).md
```

共 4 组同名、9 个文件使用该后缀。

## 版本

- 226 篇从「相关任务/成就/活动」推导，`version_source: derived-related-quest`；
- **480 篇 `unknown`**，来源本身没有稳定版本字段，按约定不猜。

## 已知问题

- **10 篇正文为空**（只有 `## 交互文本` 一行）：寻人启事【蒙德城】、寻人启事【璃月】、往生堂告示板【璃月港】、告示【归离原】、小仓屋告示板【稻妻城】、有相当年头的记事【踏鞴砂】、「木南料亭」新菜告知【稻妻城】、九十九物广告板【稻妻城】、训练场公告【安饶之野】、执灯人的长桌【皮拉米达城】。
  原因：`render_lore` 只识别 `interactive_dialogue` 组件，这几页的正文在别的模块里。修复需要补 renderer，不是数据缺失。
- 另有约 44 篇正文极短（<50 字），多为单行留言，属正常。

## 重新导入

```powershell
.\tools\python\python.exe scripts\load_markdown.py --dir corpus\scattered --bulk
```

> 散落文本入库时**用 jieba 分词**（不加 `--no-segment`），与 books 一致；quests / characters 才用 `--no-segment`。
