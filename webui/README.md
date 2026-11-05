# Web UI

本地只读检索界面，直接读 `db/genshin_lore.sqlite3`，不会修改数据库或 Markdown。

**最省事：双击这两个文件**

```text
webui\start-webui.cmd    启动
webui\stop-webui.cmd     停止
```

**或在本项目 PowerShell 里**

```powershell
cd D:\harn\2\genshin-lore-db
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force   # 仅需一次，只对当前窗口生效
.\webui\start.ps1                  # 后台启动，写 logs/webui-8765.pid
.\webui\stop.ps1                   # 精确停止
.\webui\start.ps1 -Port 8766       # 换端口（停止时也要 .\webui\stop.ps1 -Port 8766）
.\webui\start.ps1 -Foreground      # 前台运行，Ctrl+C 停止，不写 PID 文件
```

`.cmd` 里已经带了 `-ExecutionPolicy Bypass`，双击不用管执行策略；
直接在终端跑 `.ps1` 若报「禁止运行脚本」，按上面先设一次进程级策略即可（不改系统设置）。

打开：

```text
http://127.0.0.1:8765/
```

## 启停脚本怎么工作

| 行为 | 说明 |
|---|---|
| 幂等启动 | 先探 `/health`；已在跑就只打印地址和 PID，不会再开第二个进程 |
| 端口保护 | 端口被别的程序占用且 `/health` 不通时直接报错，建议换端口，不盲目启动 |
| 精确停止 | 从「端口监听进程 + PID 文件」取候选，**校验进程名是 python、命令行含 `app.py` 且 `--port` 匹配**才停 |
| 不误杀 | 绝不用 `taskkill /im python.exe`；身份不符会明确「拒绝停止 PID x」并保留该进程 |
| 兼容手启 | 服务若是手工 `python webui/app.py` 起的、没有 PID 文件，也能按端口找到并停掉 |
| 日志 / PID | `logs/webui-8765.log`、`logs/webui-8765.pid`；都不进 Git |
| 启动自检 | 启动后轮询 `/health` 最多 6 秒，失败会打印日志尾部并清理 PID 文件 |

`app.py` 新增了可选的 `--log-file`，后台启动时由它自己把访问日志写进文件；
前台运行不传该参数，输出照旧打到终端。

## 功能

- 搜索：3 字以上中文走 FTS5 trigram，2 字词自动回退 `LIKE`；
- 筛选：类型 / 地区 / 版本（下拉选 `X.Y`，前缀精确匹配，不再用 `%x%` 误匹配）；
- **字段覆盖率**：首页可展开查看各字段覆盖率；按地区或版本筛选时明确提示有多少「未标注」文档被排除；
- 剧透筛选已下线：全库仅 10 篇做过 2/3 级分级，不足以支撑筛选；文档页仍显示等级值；
- 文档页：正文、版本、版本来源/置信度、来源链接、原始 Markdown；
- 类型页：全部 12 种 `doc_type`（任务 / 书籍 / 散落文本 / 角色 / 武器 / 圣遗物 / 物品 / 地理 / 活动 / NPC 对话 / 官方公告 / 漫画）；
- 只读：数据库以 `mode=ro` 打开，不写文件。

## 字段覆盖率

覆盖率低不等于「数据缺失」：物品 / 武器 / 圣遗物 / 活动 / 公告本来就没有地区字段，
上游也没有给物品、NPC 对话、观景点版本号。按项目约定留空不猜，
所以界面把边界讲清楚，而不是把筛选器伪装成全覆盖。

| 字段 | 覆盖率 | 说明 |
|---|---:|---|
| 类型 | 100% | 全部文档都有 |
| 地区 | 60.7% | 剧情类 100% 已标注，非剧情类天然无该字段 |
| 版本 | 25.4% | 值已全部归一化为 `X.Y` |
| 上线日期 | 0.7% | 仅官方公告有 |
| 剧透分级 | 0.1% | 仅 10 篇书籍，筛选已下线 |

`GET /api/coverage` 返回同样的机器可读数据。

## 结构

```text
webui/
├─ app.py            stdlib http.server + sqlite3 + markdown
├─ start.ps1         后台启动（幂等、自检、写 PID）
├─ stop.ps1          精确停止（身份校验、不误杀）
├─ start-webui.cmd   双击启动入口
├─ stop-webui.cmd    双击停止入口
├─ static/
│  └─ style.css
└─ README.md
```

没有 Flask/FastAPI 依赖，只多装了 `markdown` 用于渲染正文。

## API

```text
GET /health
GET /api/coverage
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
