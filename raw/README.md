# raw · 原始快照

> 规则：**只增不改。** 这是证据层，不是工作区。

## 1. 目录

```text
raw/
├─ bwiki/
│  ├─ wikitext/      # MediaWiki 原始 wikitext
│  ├─ html/          # action=parse 渲染后的 HTML
│  ├─ smw/           # Semantic MediaWiki ask 结果（版本映射）
│  └─ meta/          # 每次抓取的元数据
├─ miyoushe/
│  ├─ posts/         # 帖子 JSON
│  ├─ html/          # 正文 HTML（如果单独保存）
│  └─ meta/
├─ official_site/
│  ├─ obc/
│  │  ├─ entries/    # 观测枢 entry_page JSON
│  │  ├─ meta/       # entry 元数据
│  │  ├─ search/     # 搜索快照
│  │  └─ channel_tree.json
│  └─ meta/
├─ genshin_db/
│  ├─ ...            # 按包版本保存的 JSON 片段
│  └─ meta/
└─ fandom/
   ├─ ...
   └─ meta/
```

## 2. 命名

```text
<page_id>-<revid>.wikitext
<page_id>-<revid>.html
<post_id>-<retrieved_at>.json
```

如果站点没有稳定 ID，用：

```text
<slug>-<sha256前8位>.html
```

不要用 `latest`、`final`、`new` 这种会过期的名字。

## 3. `meta.json`

每次抓取至少记录：

```json
{
  "source_id": "bwiki",
  "url": "https://wiki.biligame.com/ys/...",
  "status": 200,
  "fetched_at": "2026-11-04T01:30:00+08:00",
  "content_type": "application/json",
  "page_id": 8578,
  "revision_id": 123456,
  "sha256": "...",
  "http_headers": {
    "etag": "...",
    "last_modified": "..."
  },
  "notes": ""
}
```

可加：

- `redirect_chain`；
- `encoding`；
- `error`（失败时）；
- `parser_version`。

## 4. 规则

- 不覆盖旧文件；同一页面新版本用新 `revid`/时间戳；
- 不把清洗后的文本放这里；
- 不把图片/大二进制默认提交到版本库，必要时放 `raw/**/images/` 并在 `.gitignore` 排除；
- 失败也保存响应（如果服务器返回了内容），并记录 `status`；
- 抓取前检查 `robots.txt`；
- 默认 1 请求/秒，遇到 429/567 退避；
- 不要在这里手改原文；要修正去 `corpus/` 并记录原因。

## 5. 校验

每个文件都应有对应的 `meta.json`。没有元数据的原始文件，视为不可追溯，不能直接作为 `stable` 文档的唯一来源。

批量校验时检查：

- `sha256` 与文件一致；
- `url` 可访问（抽样）；
- `revision_id` 存在（Wiki）；
- `fetched_at` 格式正确；
- 没有 0 字节文件。
