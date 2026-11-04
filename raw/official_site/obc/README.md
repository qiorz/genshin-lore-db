# raw/official_site/obc · 米游社·观测枢快照

## 目录

```text
obc/
├─ entries/          # entry_page JSON，文件名 = entry_page_id
├─ meta/             # 每个 entry/频道列表的 URL、抓取时间、sha256、page_version
├─ search/           # 搜索接口快照
├─ channel_lists/    # 频道条目列表（书籍/地图文本/任务）
├─ channel_tree.json # 完整频道树
└─ channel_tree.txt  # 可读版频道树
```

## 关键接口

```text
GET https://act-api-takumi-static.mihoyo.com/hoyowiki/genshin/wapi/entry_page
    ?entry_page_id=399&app_sn=ys_obc&lang=zh-cn

GET https://act-api-takumi-static.mihoyo.com/hoyowiki/genshin/wapi/search
    ?keyword=钟离&menu_id=25&page_num=1&page_size=20&app_sn=ys_obc&lang=zh-cn

GET https://act-api-takumi-static.mihoyo.com/common/blackboard/ys_obc/v1/getChannelTree
    ?app_sn=ys_obc&lang=zh-cn

GET https://act-api-takumi-static.mihoyo.com/common/blackboard/ys_obc/v1/home/content/list
    ?channel_id=68&page_num=1&page_size=1000&app_sn=ys_obc&lang=zh-cn
```

## 已保存条目

| entry_page_id | 内容 | 用途 |
|---|---|---|
| 399 | 序章第一幕「捕风的异乡人」 | 任务对话图 |
| 501 | 《林间风》 | 书籍分卷 |
| 503 | 《林间风·故事拔萃节选》 | 单卷对照 |
| 516 | 《碎梦奇珍》 | 多篇短故事 |
| 517 | 《神霄折戟录》 | 多卷书籍结构 |
| 500 | 《白之公主与六侏儒》 | 多卷童话（OBC 仅第一卷全文） |
| 508 | 《石书辑录》 | 璃月历史 |
| 513 | 《绝云记闻》 | 璃月志怪 |
| 606 | 《璃月风土志》 | 璃月民俗 |
| 496 | 《温妮莎传奇》 | 蒙德历史 |
| 534 | 《提瓦特游览指南》 | 地区见闻 |
| 1146 | 《竹林月夜》 | 璃月志怪 |
| 3228 | 《「东王」史辩》 | 须弥历史 |
| 4616 | 《浮槃歌卷》 | 须弥学术 |
| 1290 | 钟离 | 角色故事/语音 |
| 3470 | 《白夜国馆藏》 | 多卷、跨版本书籍 |
| 501754 | 石碑【龙脊雪山】 | 散落文本 |
| 503070 | 散落的书页【揭示之书】 | 散落文本 |
| 507704 | 残破的笔记【废弃避难所】 | 散落文本 |

频道列表：`channel_lists/68.json`（书籍 93）、`251.json`（地图文本 706）、`43.json`（任务 1,101）。

## 注意

- 这些 JSON 是**原始响应**，不要手改；
- 内容由社区编辑维护，不是官方逐字文本；
- `page.version` 是页面编辑版本，不是游戏版本；
- 重新抓取时用 `scripts/fetch_obc.py --force`，并保留旧快照或另存时间戳；
- 请求默认 1 次/秒，别并发扫全站。
