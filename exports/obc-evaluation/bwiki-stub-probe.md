# BWiki 空壳任务补全探测

生成时间：2026-11-04  
对象：`corpus/quests/_pending/` 的 32 条空壳任务（OBC 页面 0 剧情模块）  
结论：**BWiki 无法补全这批，保持 `_pending`。**

---

## 1. 方法

1. 用 BWiki `api.php?action=query&list=search` 按任务标题搜索；
2. 归一化（去空格、标点、书名号）后**只接受同名或包含关系**的页面；
3. 命中后拉 `action=parse&prop=wikitext`，检查是否存在 `==任务剧情==` 与 `{{人物对话}}` 模板；
4. 不采用「匹配不到就取第一条搜索结果」的回退。

> 原 `scripts/fill_quests_from_bwiki.py` 有这条回退，`quest.obc.4190` 因此把版本专题页当成了任务页。
> 已删除该回退：匹配不到直接返回 `None`，宁可不补。

## 2. 搜索结果

| 判定 | 数量 | 含义 |
|---|---:|---|
| `exact` | 10 | BWiki 有同名页面 |
| `guess` | 12 | 只搜到版本专题、过场提示等无关页 |
| `none` | 10 | 没有任何结果 |

逐条结果见 [`manifests/bwiki-probe.csv`](../manifests/bwiki-probe.csv)。

`guess` 的 12 条几乎全是**邀约事件**，BWiki 搜索返回「2.x 版本更新专题」这类聚合页。
这正是 4190 事故的成因，一律不采用。

## 3. 10 个同名页面的实际内容

| 页面 | wikitext | 对话模板 | 状态 |
|---|---:|---:|---|
| 雾与风的旅行 | 402 | 0 | 只有「任务接取」「任务流程」 |
| 渴望旅行的妖狸 | 256 | 0 | 「任务剧情」为空 |
| 被嫌弃的木刻 | 731 | 0 | 「任务剧情」为空 |
| 哐哐锵锵王山行 | 491 | 0 | 「任务剧情」为空 |
| 探索剑冢封印 | 445 | 0 | 只有「简介/描述/任务介绍」 |
| 好事多磨 | 227 | 0 | 「任务剧情」为空 |
| 坏蛋们 | 1008 | 0 | 挂 `{{待补充}}` |
| 智勇双拳 | 673 | 0 | 挂 `{{待补充}}` |
| 一份预期内的计划 | 658 | 0 | 挂 `{{待补充}}`，无章节 |
| 梦境与树 | 208 | 0 | 「任务剧情」为空 |

**10 个页面的 `{{人物对话}}` 模板数全部为 0，`任务剧情` 小节全部为空。**
即使页面存在，也提取不出任何台词。

## 4. 结论与后续

- 32 条空壳**不是抓取遗漏**，而是上游（OBC 与 BWiki）都没有正文；
- 保持 `_pending`，不猜、不拼；
- 若要真正补齐，只有一条路：从**游戏数据包**（AnimeGameData 的 `TalkConfig` / `QuestExcelConfigData`）按 quest id 取对话，属于新数据源接入，不在本轮范围；
- 这 32 条已经在库里（`doc_type=quest`、`status=draft`），检索不到台词但不影响其它字段。

## 5. 相关文件

- [`manifests/bwiki-probe.csv`](../manifests/bwiki-probe.csv)：32 条逐条搜索结果
- [`corpus/quests/_pending/README.md`](../corpus/quests/_pending/README.md)：空壳说明
- [`scripts/fill_quests_from_bwiki.py`](../scripts/fill_quests_from_bwiki.py)：已移除危险回退
