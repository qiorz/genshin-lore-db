# corpus/quests/_pending · 待补任务

这里放 **32** 篇「OBC 页面本身没有剧情对话」的任务页。

```text
world  20
story  12   （全部是邀约事件）
```

## 特征

- 正文只有 `## 任务信息` 一节；
- `notes` 里标 `OBC 无剧情对话，疑似系列/总览页；待 BWiki 或子任务页补全。`；
- 它们在 SQLite 里仍作为 `doc_type=quest` 存在，`status=draft`，不影响检索，但搜不到台词；
- subtype 已归类（邀约的 12 条是 `hangout`，不是 `story`），补全后直接移入对应目录即可。

## 和 `corpus/quests/` 的区别

- `corpus/quests/<subtype>/` 只放**有正文**的任务；
- `_pending/` 只放**没正文**的空壳，补全后移到对应 subtype，并登记 `index.csv`；
- `index.csv` **不收录** `_pending/` 的文件。

## 为什么单独放

这些条目在 OBC 上是系列总览页（例如「风花节引导任务」「寝子是只猫系列任务」），
正文散在子任务页里。混在正文目录里会让「任务总数」虚高，
也会让检索结果里出现大量空文档。单独隔离后，正文目录的含义就明确了。

## 补全结论（2026-11-04）

**BWiki 补不了这批。** 32 条逐条探测：

- 10 条有同名页面，但 10 个页面的 `==任务剧情==` 全部为空，`{{人物对话}}` 模板数均为 0，其中 3 个挂 `{{待补充}}`；
- 12 条只能搜到「版本更新专题」等无关页（邀约事件多为此类），按新规则一律不采用；
- 10 条完全没有搜索结果。

报告：[`exports/obc-evaluation/bwiki-stub-probe.md`](../../../exports/obc-evaluation/bwiki-stub-probe.md)。

要真正补齐，只能接游戏数据包（`TalkConfig` / `QuestExcelConfigData`），属新数据源。

## 一条历史事故

`邀约事件·久岐忍 第一幕`：曾因 `fill_quests_from_bwiki.py` 的「匹配不到就取第一条搜索结果」回退，
把版本专题页当成任务页，塞进了凝光/云堇/加尔恰等其它邀约的整篇文本。
该回退已删除，本文档已回退为空壳。
