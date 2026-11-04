# corpus/quests · 任务正文

当前收录 **1,065** 篇有正文的任务/系列任务，另 **32** 篇 OBC 无剧情的空壳页在 `_pending/` 等补。按 subtype 分目录：

```text
corpus/quests/
├─ archon/     魔神任务（46）
├─ interlude/  间章（4）
├─ story/      传说任务（92）
├─ hangout/    邀约事件（7）
├─ world/      世界任务（622）
├─ event/      限时/活动任务（288）
├─ other/      其他（6）
├─ _pending/   32 篇 OBC 无剧情对话的空壳页
└─ index.csv
```

`index.csv` 字段：

```text
doc_id,title,subtype,region,version,path
```

## 分类规则

- **hangout**：标题以 `邀约事件·` 开头。注意 `「八重堂」的邀约` 是世界任务，不在此列。
- **interlude**：标题含 `间章` 的魔神任务。第 1 步之前它们混在 `archon/`。
- **系列页**：一个文件内含多幕（`雾海纪行系列任务` 4 幕、`清籁逐雷记系列任务` 4 幕等）。
  这类页加 `tags: [系列任务]`，目前 18 篇（标题含「系列/合集/总览」15 篇 + 海灯节轶事 3 篇）。
- **`_pending/`**：OBC 页面 0 剧情模块的系列/总览页，`notes` 标 `OBC 无剧情对话...`。

## 已知问题

- **32 条空壳补不了**：OBC 无正文，BWiki 同名页面的「任务剧情」也为空（3 个挂 `{{待补充}}`）。
  探测报告：[`exports/obc-evaluation/bwiki-stub-probe.md`](../../exports/obc-evaluation/bwiki-stub-probe.md)。
  要补齐只能接游戏数据包（`TalkConfig` / `QuestExcelConfigData`）。
- **多幕文件未拆分**：规范允许「一个系列一篇」，若要严格「一篇一幕」，需先定合成 doc_id 规则。
- **同文重复**：剩 10 组，逐组判定见 [`manifests/duplicates.csv`](../../manifests/duplicates.csv)。
  已合并 `好东西，坏品味` 5→1（4 个 OBC 条目内容一致，来源并入主文档）。

## 历史修复

- `quest.obc.500835 云云椒椒`：曾被历史脚本覆盖成「赤望所居，锦落云程」的正文，已用 `raw/` 原始快照重渲染恢复（6,495 字）。
- `quest.obc.4190 邀约事件·久岐忍`：OBC 页面本身无剧情，曾因 BWiki 匹配错误被塞入凝光/云堇/加尔恰等整篇文本。已回退为空壳并移入 `_pending/`。

## 重新导入

```powershell
.\tools\python\python.exe scripts\load_markdown.py --dir corpus\quests --bulk --no-segment
```
