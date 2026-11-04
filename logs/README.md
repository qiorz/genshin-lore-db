# logs · 运行日志

抓取、解析、入库的日志放这里。

## 命名

```text
logs/
├─ fetch-bwiki-2026-11-04.log
├─ parse-bwiki-2026-11-04.log
├─ load-corpus-2026-11-04.log
└─ validate-2026-11-04.log
```

## 规则

- 不记录大段原文，只记录页面名、URL、`doc_id`、行号、错误摘要；
- 失败要记录 HTTP 状态、重试次数、异常类型；
- 不记录 Cookie/Token；
- 日志按天/按运行分文件，不要无限追加；
- 需要长期保留的统计结果放 `exports/`，不要只留在日志里。
