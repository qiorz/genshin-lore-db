# corpus/scattered · 散落文本

地图上的石碑、告示板、留言、笔记、书页等交互文本，共 **705** 篇，按地区归档。
来自观测枢「地图文本」频道，只保留交互文本，不提取地图截图与坐标。

```text
corpus/scattered/
├─ 璃月/        141
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
corpus/scattered/璃月/通知【明蕴镇】 (obc-501764).md
corpus/scattered/璃月/告示【归离原】 (obc-501819).md
```

共 4 组同名、8 个文件使用该后缀（`通知【明蕴镇】` 原有 3 条，其中 501768 已合并进 501764）。

## 版本

- 226 篇从「相关任务/成就/活动」推导，`version_source: derived-related-quest`；
- **479 篇 `unknown`**，来源本身没有稳定版本字段，按约定不猜。

## 已知问题

无空白文档。

2026-11-04 之前有 12 篇正文为空（只有 `## 交互文本` 一行），原因是 `render_obc.py` 的对话解析只从 `root_id` 起步，
而这批页面的根容器节点并不在 `contents` 里，导致整篇输出为空。现已改为从「没有父节点的孤岛」起步、
按节点 key 末位时间戳排序渲染，12 篇全部恢复：

```text
乌有亭留言板 3,497 字 · 教令院公共留言板 4,300 字 · 有相当年头的记事【踏鞴砂】2,515 字
执灯人的长桌【皮拉米达城】563 字 · 寻人启事【蒙德城】201 字 · 其余 6 篇 113–294 字
```

## 重新导入

```powershell
.\tools\python\python.exe scripts\load_markdown.py --dir corpus\scattered --bulk
```

> 散落文本入库时**用 jieba 分词**（不加 `--no-segment`），与 books 一致；quests / characters 才用 `--no-segment`。
