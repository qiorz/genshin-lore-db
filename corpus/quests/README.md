# corpus/quests · 任务正文

当前收录 **1,051** 篇有对话正文的任务/系列任务，按 subtype 分目录：

```text
corpus/quests/
├─ archon/     魔神任务
├─ story/      传说任务
├─ hangout/    邀约事件
├─ world/      世界任务
├─ event/      限时/活动任务
├─ interlude/  间章
├─ other/      其他
└─ index.csv
```

`index.csv` 字段：

```text
doc_id,title,subtype,region,version,path
```

说明：

- 1,051 篇来自 OBC 任务频道，graph-only 对话已恢复；
- 163 篇的 OBC 缺正文部分用 BWiki 子任务页补全，front matter 增加 `source_id: bwiki`；
- 剩余 **63** 条仍无正文，留在 `exports/obc-batch/`，标 `OBC 无剧情对话...`，补完后再移入这里；
- 版本均来自 OBC 任务频道，1,101/1,101 有版本。

重新导入：

```powershell
.\tools\python\python.exe scripts\load_markdown.py --dir corpus\quests --bulk --no-segment
```

