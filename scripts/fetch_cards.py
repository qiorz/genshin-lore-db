#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量抓取七圣召唤卡牌条目（233 角色牌 / 234 行动牌 / 235 魔物牌）。

先跑 fetch_obc.py --channel-id 231 233 234 235 拿清单，再用本脚本抓正文。
复用 fetch_entry：1 req/s、browser UA、已存在则跳过（可断点续抓）。

    python scripts/fetch_cards.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import fetch_obc as F  # noqa: E402

OUT = ROOT / "raw" / "official_site" / "obc"
CHANNELS = ("233", "234", "235")
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


def collect_ids() -> list[int]:
    ids: list[int] = []
    seen: set[int] = set()
    for cid in CHANNELS:
        p = OUT / "channel_lists" / f"{cid}.json"
        if not p.exists():
            raise SystemExit(f"缺少清单 {p}，先跑 fetch_obc.py --channel-id 231 233 234 235")
        data = json.loads(p.read_text(encoding="utf-8"))
        channel = ((data.get("data") or {}).get("list") or [{}])[0] or {}
        for entry in channel.get("list") or []:
            pid = entry.get("content_id")
            if pid and pid not in seen:
                seen.add(int(pid))
                ids.append(int(pid))
    return ids


def main() -> int:
    cfg = F.load_config(ROOT / "config" / "sources.toml")
    source = cfg["sources"]["obc"]
    session = F.make_session(cfg)

    ids = collect_ids()
    print(f"待抓 {len(ids)} 张卡牌", flush=True)

    t0 = time.time()
    failed: list[tuple[int, str]] = []
    for i, pid in enumerate(ids, 1):
        try:
            F.fetch_entry(session, cfg, source, pid, OUT, force=False)
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            failed.append((pid, str(exc)[:120]))
            print(f"  !! {pid} 失败: {exc}", flush=True)
            time.sleep(2)
        if i % 50 == 0:
            print(f"  进度 {i}/{len(ids)}  用时 {time.time()-t0:.0f}s  失败 {len(failed)}", flush=True)

    print(f"\nDONE 共 {len(ids)} 张，失败 {len(failed)}，用时 {time.time()-t0:.0f}s")
    for pid, err in failed[:20]:
        print(f"  失败 {pid}: {err}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
