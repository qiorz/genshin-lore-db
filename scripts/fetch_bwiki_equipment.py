# -*- coding: utf-8 -*-
"""抓取 BWiki 武器/圣遗物页面字段，缓存到 raw/bwiki/equipment/。"""
import hashlib
import json
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "raw/bwiki/equipment"
CACHE.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "scripts"))
from fill_quests_from_bwiki import clean  # noqa: E402

SLOTS = ["生之花", "死之羽", "时之沙", "空之杯", "理之冠"]


def field(wt: str, name: str) -> str:
    m = re.search(r"\n\s*\|\s*" + re.escape(name) + r"\s*=", wt)
    if not m:
        return ""
    start = m.end()
    nxt = re.search(r"\n\s*\|[^\[\]{}]{1,20}=", wt[start:])
    end = start + nxt.start() if nxt else len(wt)
    value = wt[start:end].strip()
    # 模板结束符之后是导航模板，不能算进字段
    value = re.split(r"\}\}|\{\{", value, maxsplit=1)[0].strip()
    return value


def titles():
    out = []
    for cid, kind in (("5", "weapon"), ("218", "artifact")):
        d = json.loads((ROOT / f"raw/official_site/obc/channel_lists/{cid}.json").read_text(encoding="utf-8"))
        for item in d["data"]["list"][0]["list"]:
            out.append((str(item["content_id"]), item["title"], kind))
    return out


session = requests.Session()
session.trust_env = False
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Referer": "https://wiki.biligame.com/ys/",
})

rows = titles()
print("total", len(rows), flush=True)
ok = miss = 0
for i, (cid, title, kind) in enumerate(rows, 1):
    cache = CACHE / f"{cid}.json"
    if cache.exists():
        ok += 1
        continue
    try:
        r = session.get(
            "https://wiki.biligame.com/ys/api.php",
            params={"action": "parse", "page": title, "prop": "wikitext|revid", "format": "json", "formatversion": 2},
            timeout=30,
        ).json()
    except Exception as exc:  # noqa: BLE001
        print("ERR", title, exc, flush=True)
        continue
    parse = r.get("parse") or {}
    wt = parse.get("wikitext") or ""
    if not wt:
        cache.write_text(json.dumps({"title": title, "found": False}, ensure_ascii=False), encoding="utf-8")
        miss += 1
        continue
    payload = {
        "title": title,
        "found": True,
        "revid": parse.get("revid"),
        "version": clean(field(wt, "实装版本")),
        "kind": kind,
    }
    if kind == "weapon":
        payload["desc"] = clean(field(wt, "介绍"))
        payload["story"] = clean(field(wt, "故事"))
    else:
        for slot in SLOTS:
            payload[f"{slot}_desc"] = clean(field(wt, f"{slot}描述"))
            payload[f"{slot}_story"] = clean(field(wt, f"{slot}故事"))
    cache.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    ok += 1
    if i % 20 == 0:
        print(f"{i}/{len(rows)} ok={ok} miss={miss}", flush=True)
    time.sleep(0.4)

print(f"done ok={ok} miss={miss}", flush=True)
