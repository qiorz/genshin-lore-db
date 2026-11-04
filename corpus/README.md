# corpus · 规范化正文

> 这里是“可读、可检索、可引用”的正文层。原始文件在 `raw/`，考据在 `knowledge/`。

## 1. 目录

```text
corpus/
├─ quests/
│  ├─ archon/        # 魔神任务
│  ├─ story/         # 传说任务
│  ├─ world/         # 世界任务
│  ├─ event/         # 活动剧情
│  ├─ hangout/       # 邀约事件
│  └─ interlude/     # 间章
├─ books/            # 游戏内书籍
├─ scattered/        # 散落文本：石碑、笔记、留言、书页、告示等
├─ characters/       # 角色故事/语音（不含攻略、配队、数值）
├─ weapons/          # 武器故事
├─ artifacts/        # 圣遗物故事
├─ items/            # 材料/食物/任务道具/摆设
├─ voices/           # 独立语音文本
├─ geography/        # 地理志/地区
├─ events/           # 活动设定（非任务正文）
├─ manga/            # 官方漫画文本
└─ notices/          # 公告/版本说明
```

## 2. 文件要求

- UTF-8，LF；
- 必须有 YAML front matter，字段见 [`../docs/02-数据规范.md`](../docs/02-数据规范.md)；
- 标题层级从 `##` 开始；
- 对话用 `**角色**：台词`；
- 选项用 `> 选项：`；
- 任务**一篇一幕**，子任务用 `##` 分节；
- 角色只保留游戏内故事/描述/语音，**不要攻略、配队、属性、数值**；
- 散落文本只保留交互文本，**不提取地图截图/图标**；需要图片时标 `needs_ocr`，不假装已解析；
- 原文和考据分开，考据放 `knowledge/` 或用 `> 注：` 明确标注；
- 不把攻略、配队、刷材料、地图采集点混进来；
- 不把多个任务/多本书塞进一个文件（除非是系列总览）。

## 3. 最小模板

```markdown
---
id: book.mondstadt.example
type: book
title: 示例书名
language: zh-Hans
region: 蒙德
version: "1.0"
canon_status: official
transcription: near-verbatim
spoiler:
  level: 1
  scope: [mondstadt]
source:
  - source_id: bwiki
    url: https://wiki.biligame.com/ys/示例书名
    revision_id: "123456"
    retrieved_at: 2026-11-04T01:30:00+08:00
status: draft
---

## 书籍信息

- 体裁：故事传说
- 卷数：共两卷

## 卷一 · 示例标题

（此处为正文）
```

## 4. 命名

```text
corpus/quests/archon/序章 第一幕「捕风的异乡人」.md
corpus/books/璃月/林间风.md
corpus/characters/璃月/钟离.md
```

- 文件名用中文标题，ID 放 front matter；
- 不用的 Windows 禁用字符；
- 不写“最终版”“新版”；
- 重命名后同步更新 `related` 和数据库链接。

## 5. 状态

- `draft`：已导入，未人工校对；
- `reviewed`：人工抽查过，来源/结构正确；
- `stable`：交叉校验过，且经过至少一次重新抓取确认；
- `deprecated`：被新版本/新页面取代，保留但不再作为主来源。

新文件一律从 `draft` 开始。

## 6. 不要做

- 不要在这里写“我认为”“可能”“考据结论”——放 `knowledge/`；
- 不要把 Wiki 的攻略段落一起复制；
- 不要为了通顺改写原文；
- 不要合并选项分支；
- 不要把图片里的文字凭记忆补进正文；要么 OCR + 校对，要么标 `needs_ocr`。
