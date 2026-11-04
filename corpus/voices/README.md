# corpus/voices · NPC 对话 / 角色逸闻 / 角色彩蛋

> 更新时间：2026-11-04 · 2,401 篇 · 约 231 万字正文

## 目录

```text
corpus/voices/
├─ NPC对话/<地区>/     2,275 篇（10 个地区 + 未分类）
├─ 角色逸闻/<地区>/       62 篇
├─ 角色彩蛋/<地区>/       64 篇
└─ index.csv            doc_id / title / subtype / region / sections / chars / path
```

地区来自观测枢频道列表 `ext.filter` 的「地区/XX」标签；`279 角色彩蛋` 里写作
「诺德卡莱」的已统一为「挪德卡莱」。频道没有版本字段，按约定 `version` 一律不写、不猜。

## 数据来源

| 频道 | 名称 | 条目 | 归档 |
|---:|---|---:|---:|
| 20 | NPC&商店 | 2,385 | 2,275 |
| 261 | 角色逸闻 | 69 | 62 |
| 279 | 角色彩蛋 | 71 | 64 |
| | **合计** | **2,525** | **2,401** |

原始快照：`raw/official_site/obc/entries/*.json` + `raw/official_site/obc/meta/*.json`，
频道列表：`raw/official_site/obc/channel_lists/{20,261,279}.json`。
2,525 条 entry 全部落盘，抓取断点续跑补了最后一轮 883 条。

124 条没有任何可提取对话，逐条记在 [`../../manifests/npc-skip.csv`](../../manifests/npc-skip.csv)，
原因统一为 `no_dialogue`（页面只有商品/地图/空占位模块）。

## 收什么 / 不收什么

**收**

- `npc_base_info` 的短字段（性别/位置/职业/功能/角色介绍/编者注）→ `## 基本信息`；
- 所有 `interactive_dialogue` 模块 → 按对话图展开，含分支与选项，格式沿用任务文档；
- `collapse_panel` 里的 `秘闻馆情报` / `秘文馆情报` / `好感套装对话` / `赠礼对话`；
- `rich_base_info` 里 `逸闻纪事·X` / `剧情彩蛋` 的「名称 / 简介 / 描述」。

**不收**

- 商品列表、价格、声望奖励、探索度、锻造/合成表、`相关任务` 空面板；
- `挑战目标or特殊规则`、七圣召唤平衡性调整等玩法规则；
- 地图图片、角色展示图、生日邮件（生日邮件已在 `corpus/characters/` 收录，避免重复）；
- 语音占位行「语音汉语/英语/日语/韩语：[当前音频暂无文件名]」——
  洞天与赠礼对话节点里混有这类非台词行，渲染时已按行剔除。

同一模块名在页面里常出现多次（例如 5 段「逸闻纪事对话」），按出现顺序加
`· 其二 / 其三` 后缀，避免小节重名。3 组同名条目用 ` (obc-<content_id>)` 消歧。

## 质量说明

- `canon_status: community`、`transcription: near-verbatim`：观测枢是官方平台、社区编辑，不是逐字官方文本；
- 角色逸闻/彩蛋里含 `七圣召唤对话`、`幻想真境剧诗对话`、`角色洞天对话` 等玩法内台词，
  它们仍是角色台词，按同一规则收录；
- 正文最长的是情报官/调查小队类 NPC（4 万字以上），最短只有一句开场白。

## 重建

```powershell
.\tools\python\python.exe .\scripts\render_npcs.py --apply
.\tools\python\python.exe .\scripts\validate_frontmatter.py --dir .\corpus\voices --quiet
.\tools\python\python.exe .\scripts\load_markdown.py --dir .\corpus\voices --bulk --no-segment
```
