# corpus/events · 活动文本

观测枢「活动」频道 275 条中，**只有 47 条有叙事内容**，归档在这里。其余 228 条是公告、奖励、纪行、赛季之类系统页，不含故事，列入 `manifests/event-skip.csv`。

```text
corpus/events/
├─ 游戏活动/   47 篇
├─ README.md
└─ index.csv
```

`index.csv` 字段：

```text
doc_id,title,subtype,version,version_source,version_confidence,path
```

## 只收三样

| 内容 | 来源模块 | 说明 |
|---|---|---|
| 活动概述 | 与活动同名的 `collapse_panel` | 含 `〓` 的官方公告格式不收（那是奖励/规则） |
| 活动简介 | `活动说明` 里的「简介 / 背景」字段 | 参与条件、活动规则、奖励等字段一律不收 |
| 剧情 / 彩蛋 | 名字含「剧情」「彩蛋」的 `interactive_dialogue` | 完整对话与分支 |

奖励、攻略推荐、活动公告表、纪行内容、千星奇域赛季信息全部丢弃。

## 为什么只有 47/275

按模块逐页检查过：

- **27 条**有真正的剧情对话节点；
- **47 条**有活动简介；
- 其余 **228 条**的模块只有「基础信息 / 说明表 / 攻略推荐 / 活动公告」，没有叙事段落。

其中一大类是 **纪行（53 条）** 和 **千星奇域赛季**，它们本身就是奖励/赛季说明页。
**活动的剧情本体不在这里**——活动任务已经作为 `type: quest, subtype: event` 收在 `corpus/quests/event/`（288 条）。
所以「活动」这一层的定位是：活动简介 + 少见的彩蛋对话，不是活动剧情全集。

## 版本与分类

- `version` 来自频道列表 ext 的 `版本/`（如 `7.1`、`月之八`），47/47 有值；
- `subtype` 来自 `活动类型/`，本次归档的全部是 `游戏活动`；
- 跳过的 228 条按类型：游戏活动 168、纪行 53、其他 5、活动祈愿 1、未知 1。

## 重新生成

```powershell
.\tools\python\python.exe scripts\render_events.py --apply
```

> 该脚本同时刷新人气成就索引 `manifests/achievements.csv`，见 [`manifests/README.md`](../../manifests/README.md)。

入库：

```powershell
.\tools\python\python.exe scripts\load_markdown.py --dir corpus\events --bulk
```
