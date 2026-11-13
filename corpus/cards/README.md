# corpus/cards · 七圣召唤牌面

观测枢「231 卡牌图鉴」下三个频道的全部条目，共 **795** 张。

```text
角色牌  150   频道 233
行动牌  584   频道 234
魔物牌   61   频道 235
```

## 收了什么

| OBC 组件 | 内容 |
|---|---|
| `card_base_info` | 卡面名、生命值/费用、元素、武器、阵营、充能、获取方式 |
| `card_skill` | 技能名、类型（普通攻击/元素战技/元素爆发/天赋）、消耗、充能、效果文本 |
| `collapse_panel` | 卡牌故事、效果描述 |

不收卡图、不收攻略。

**数值是保留的**（生命/充能/费用）：七圣召唤的牌面文本本身包含这些字段，删掉就读不懂技能。
这与「主线剧情不收数值」的边界不同——卡牌是游戏机制文本，不是叙事正文。

## 命名与去重

文件名 = 卡牌标题（OBC 原名，如 `法尔伽【角色牌】.md`）。
同名卡牌会撞文件名（「元素幻变」系列、多张「月笼协奏」等），撞名时用 `content_id` 后缀区分。

## 已知取舍

- `region` 只写真实国家名（蒙德/璃月/稻妻/须弥/枫丹/纳塔/至冬/挪德卡莱/坎瑞亚）。
  丘丘人一类角色牌的「阵营」是**魔物**，不是地区，一律留空；694 张无地区（行动牌与魔物牌本就没有）。
- `version` 一律不写：OBC 卡牌频道没有版本字段，按「找不到就 unknown」处理，不猜。
- `doc_type` 用 `other` + `subtype=card`：`documents.doc_type` 的 CHECK 里没有 `card`，
  加它要重建 documents 表（外键/索引/触发器），风险不划算。筛选请用 `subtype='card'`。

## 渲染注意（改脚本前先看）

1. 技能描述是 HTML 片段（`<html><body><p>…`），必须转换；
2. **不要用 `render_obc.html_paragraphs`**：它用 `get_text(" ")` 是为英文分词，
   会把中文卡面拆成「装备给我方的 法尔伽」。`render_cards.py` 里的 `html_to_text()`
   是行内零分隔、块级换行；
3. OBC 的冒号在 `value` 上（`key="阵营"` + `value=["：璃月"]`），key 与 value 两头都要 strip。

## 复跑

```powershell
# 1. 抓清单（4 个请求）
tools\python\python.exe scripts\fetch_obc.py --channel-id 231 233 234 235
# 2. 抓条目（795 个请求，1 req/s，约 15 分钟；已存在会跳过，可断点续抓）
tools\python\python.exe scripts\fetch_cards.py
# 3. 渲染
tools\python\python.exe scripts\render_cards.py --apply
# 4. 入库（不要加 --no-segment，否则分词索引对卡牌失效）
tools\python\python.exe scripts\load_markdown.py --dir corpus\cards --bulk
```

索引：[`index.csv`](index.csv)（795 条）。
