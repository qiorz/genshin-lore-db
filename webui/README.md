# Web UI

本地只读检索界面，直接读 `db/genshin_lore.sqlite3`，不会修改数据库或 Markdown。

启动：

```powershell
cd D:\harn\2\genshin-lore-db
.\webui\start.ps1
```

或：

```powershell
.\tools\python\python.exe .\webui\app.py --host 127.0.0.1 --port 8765
```

打开：

```text
http://127.0.0.1:8765/
```

## 功能

- 搜索：3 字以上中文走 FTS5 trigram，2 字词自动回退 `LIKE`；
- 筛选：类型、地区、剧透等级、版本；
- 文档页：正文、版本、版本来源/置信度、来源链接、原始 Markdown；
- 类型页：书籍 / 任务 / 散落文本 / 角色；
- 只读：数据库以 `mode=ro` 打开，不写文件。

## 结构

```text
webui/
├─ app.py          stdlib http.server + sqlite3 + markdown
├─ start.ps1       启动脚本
├─ static/
│  └─ style.css
└─ README.md
```

没有 Flask/FastAPI 依赖，只多装了 `markdown` 用于渲染正文。

## API

```text
GET /health
GET /api/search?q=白之公主&type=book&region=蒙德&spoiler=2&version=1.0
GET /api/doc/quest.obc.2598
GET /raw/quest.obc.2598
```

`/api/search` 返回：

```json
{
  "query": "白之公主",
  "count": 2,
  "results": [
    {
      "doc_id": "book.obc.500",
      "title": "白之公主与六侏儒",
      "doc_type": "book",
      "region": "蒙德",
      "version": "1.0",
      "spoiler": 2,
      "speaker": null,
      "snippet": "白之公主与六侏儒",
      "source_url": "..."
    }
  ]
}
```

## 注意

- 只监听 `127.0.0.1`，不要改成 `0.0.0.0` 暴露到公网；
- 游戏文本版权归原权利方，UI 只用于本地个人检索；
- 正文字段以 Markdown 为准，数据库只是索引。
