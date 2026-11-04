# corpus/quests · 任务正文

当前收录 **1,069** 篇有对话正文的任务/系列任务，另 **32** 篇 OBC 无剧情的空壳页在 `_pending/` 等补。按 subtype 分目录：

```text
corpus/quests/
├─ archon/     魔神任务（50）
├─ story/      传说任务（99，含邀约事件）
├─ hangout/    邀约事件（暂未单独归类，见下）
├─ world/      世界任务（626）
├─ event/      限时/活动任务（288）
├─ interlude/  间章（暂未单独归类，见下）
├─ other/      其他（6）
├─ _pending/   32 篇 OBC 无剧情对话的空壳页
└─ index.csv
```

`index.csv` 字段：

```text
doc_id,title,subtype,region,version,path
```

说明：

- 正文来自 OBC 任务频道，graph-only 对话已恢复；
- 183 篇的 OBC 缺正文部分用 BWiki 子任务页补全，front matter 增加 `source_id: bwiki`；
- **`_pending/` 的 32 篇是 OBC 页面本身 0 剧情模块的系列/总览页**，`notes` 标 `OBC 无剧情对话...`，补全后再移入对应 subtype；
- 版本均来自 OBC 任务频道，1,101/1,101 有版本；
- `hangout/` 与 `interlude/` 目录暂时为空：20 条邀约事件已入库但 subtype 仍标为 `event/story/other`，间章混在 `archon/`，归类待做。

## 两篇结构异常（已修复）

- `quest.obc.500835 云云椒椒`：曾被历史脚本覆盖成「赤望所居，锦落云程」的正文，已用 `raw/` 原始快照重渲染恢复（6,495 字）。
- `quest.obc.4190 邀约事件·久岐忍`：OBC 页面本身无剧情，曾被 BWiki 补全塞入凝光/云堇/加尔恰等其他邀约的整篇文本。已回退为 OBC-only 空壳并移入 `_pending/`，待按正确 BWiki 页面重补。

重新导入：

```powershell
.\tools\python\python.exe scripts\load_markdown.py --dir corpus\quests --bulk --no-segment
```
