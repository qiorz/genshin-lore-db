#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Web UI 冒烟测试：把每个路由都打一遍，别只抽查一张卡。

为什么需要它：改 `render_entity` 时误把列表页的变量替换掉了，
`py_compile` 查不出来（NameError 是运行时才炸），抽查两张卡也正好没走到
`/entities`。结果首页正常、实体列表 500。

用法（服务需先启动）：
    python scripts/smoke_webui.py            # 默认 http://127.0.0.1:8765
    python scripts/smoke_webui.py --port 8766
"""
from __future__ import annotations

import sys
from pathlib import Path
import urllib.parse
import urllib.request

ROOT_PORT = 8765
for i, a in enumerate(sys.argv):
    if a == "--port" and i + 1 < len(sys.argv):
        ROOT_PORT = int(sys.argv[i + 1])

BASE = f"http://127.0.0.1:{ROOT_PORT}"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


def get(path: str) -> tuple[int, str]:
    try:
        with OPENER.open(BASE + path, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:400]
    except Exception as e:                       # noqa: BLE001
        return 0, str(e)


def main() -> int:
    failures: list[str] = []
    checked = 0

    def check(path: str, must: str | None = None, label: str = "") -> str:
        nonlocal checked
        checked += 1
        status, body = get(path)
        if status != 200:
            failures.append(f"{label or path} → HTTP {status} :: {body[:120]}")
            return ""
        if must and must not in body:
            failures.append(f"{label or path} → 200 但缺少「{must}」")
        return body

    # --- 固定路由 ---------------------------------------------------------
    check("/health")
    check("/", "GENSHIN LORE")
    check("/entities", "实体卡片")
    check("/entities?type=location", "实体卡片")
    check("/entities?q=" + urllib.parse.quote("风之国"), "实体卡片")
    check("/timeline", "时间线")
    check("/about", "关于")
    check("/api/entities")
    check("/api/timeline")
    check("/api/coverage")
    check("/api/search?q=" + urllib.parse.quote("钟离"), "results")

    # --- 每个实体详情页 ---------------------------------------------------
    # 从库里取全部 id：/api/entities 默认只返回 200 条，用它测不全
    import sqlite3
    db = Path(__file__).resolve().parent.parent / "db/genshin_lore.sqlite3"
    con = sqlite3.connect(db)
    ids = [r[0] for r in con.execute("SELECT entity_id FROM entities")]
    con.close()
    print(f"实体 {len(ids)} 个，逐个打开详情页…")
    for eid in ids:
        body = check("/entity/" + urllib.parse.quote(eid, safe=""),
                     "说法与置信度", label=f"/entity/{eid}")
        if body and "关系（" not in body:
            failures.append(f"/entity/{eid} → 缺少关系区块")

    # --- 文档页抽样 -------------------------------------------------------
    for doc in ("char.obc.1290", "quest.obc.399", "book.obc.521"):
        check("/doc/" + urllib.parse.quote(doc, safe=""))
        check("/api/doc/" + urllib.parse.quote(doc, safe=""))

    print(f"\n共检查 {checked} 个请求，失败 {len(failures)} 个")
    for f in failures[:20]:
        print("  ✗", f)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
