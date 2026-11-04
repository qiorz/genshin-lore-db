# corpus/notices · 官方公告

> 更新时间：2026-11-04 · 55 篇 · 子类型：`版本更新说明/`（53）、`活动公告/`（2）

## 收什么

| 来源 | 数量 | 说明 |
|---|---:|---|
| 米游社原神官方账号 `getPostFull` | 53 | 1.1 → 7.2 全部版本更新说明，连续无断档 |
| 官网游戏内公告 API `getAnnList` / `getAnnContent` | 2 | 当前窗口里带叙事内容的活动公告 |

原始数据：`raw/miyoushe/posts/*.json`（53 篇）、`raw/official_site/announcements/*.json`（29 条当前窗口），
帖子清单在 `raw/miyoushe/version-notes.json`（53 行，由 `scripts/fetch_announcements.py` 搜索+整理帖链接合并而来）。

## 筛选规则

- 米游社只收标题含「更新说明」的帖子；1.1–7.2 共 53 篇，日期、版本均来自帖子本身，不猜。
- 游戏内公告只收标题含 `版本更新说明` / `全新内容一览` / `活动` 且不属于运营类的条目。
- 27 条跳过，逐条原因在 [`../../manifests/notice-skip.csv`](../../manifests/notice-skip.csv)：
  祈愿/礼包/装扮/签到/赛季/纪行/创作赛/声明等运营公告、与米游社重复的同版本说明、
  以及纯图片无正文的「全新内容一览」。
- 版本映射：6.x 用「月之一…月之八」→ 6.0…6.7，见 `manifests/version-labels.csv`；
  7.2 标题缺「版本」二字也照常解析。

## 只去掉什么

正文按 `verbatim` 保留：只删除 `<img>`、`<table>`、`script/style`，把 `〓小标题〓` 转成 `###`。
补偿内容、更新时间、客户端更新方式等运营段落**仍在文里**——公告是一份完整官方文件，
拆开会破坏溯源；它在本库中的定位是**版本时间线佐证**，不作叙事正文统计。
这一取舍写在每篇 front matter 的 `notes` 里。

## 与别处的边界

- 活动剧情本体在 `corpus/quests/event/`（288 条），不在这里；
- 活动页的简介/彩蛋在 `corpus/events/`（47 篇）；
- 本目录只保留**官方发布的公告文件**本身。

## 重建

```powershell
.\tools\python\python.exe .\scripts\render_notices.py --apply
.\tools\python\python.exe .\scripts\validate_frontmatter.py --dir .\corpus\notices --quiet
.\tools\python\python.exe .\scripts\load_markdown.py --dir .\corpus\notices --bulk
```

生成 `index.csv`（doc_id / title / subtype / version / release_date / path）。
