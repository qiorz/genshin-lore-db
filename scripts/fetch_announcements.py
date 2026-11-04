# -*- coding: utf-8 -*-
"""抓取官方公告。

两个入口：
1. 游戏内公告 API（hk4e-api）：当前窗口的「游戏公告 / 活动公告 / 千星奇域」，含正文 HTML；
2. 米游社搜索：官方账号（uid 75276539）发布的历次「版本更新说明」，逐帖取正文。

用法：
    python scripts/fetch_announcements.py            # 抓取并写 raw/
    python scripts/fetch_announcements.py --probe    # 只列出搜到的版本说明，不抓正文
"""
import argparse
import json
import re
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
RAW_ANN = ROOT / "raw" / "official_site" / "announcements"
RAW_MYS = ROOT / "raw" / "miyoushe" / "posts"
OFFICIAL_UID = 75276539
INTERVAL = 1.0

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")

ANN_BASE = "https://hk4e-api.mihoyo.com/common/hk4e_cn/announcement/api/"
ANN_PARAMS = {
    "game": "hk4e", "game_biz": "hk4e_cn", "lang": "zh-cn", "bundle_id": "hk4e_cn",
    "platform": "pc", "region": "cn_gf01", "level": "60", "uid": "100000000",
}
MYS_SEARCH = "https://bbs-api.miyoushe.com/post/wapi/searchPosts"
MYS_FULL = "https://bbs-api.miyoushe.com/post/wapi/getPostFull"


def session() -> requests.Session:
    s = requests.Session()
    s.trust_env = False
    s.headers.update({"User-Agent": UA, "Referer": "https://www.miyoushe.com/ys/"})
    return s


def fetch_current(s: requests.Session) -> None:
    RAW_ANN.mkdir(parents=True, exist_ok=True)
    for name in ("getAnnList", "getAnnContent"):
        r = s.get(ANN_BASE + name, params=ANN_PARAMS, timeout=30)
        r.raise_for_status()
        payload = r.json()
        if payload.get("retcode") != 0:
            raise SystemExit(f"{name} failed: {payload.get('message')}")
        out = RAW_ANN / f"{name}.json"
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        data = payload["data"]
        total = len(data.get("list") or [])
        print(f"{name}: {total} items -> {out.relative_to(ROOT)}")
        time.sleep(INTERVAL)


def search_version_notes(s: requests.Session, max_pages: int = 30) -> list[dict]:
    """翻页搜索「版本更新说明」，只留官方账号发的帖子。"""
    found: dict[str, dict] = {}
    last_id = 0
    seen_last = set()
    for page in range(max_pages):
        r = s.get(MYS_SEARCH, params={"keyword": "版本更新说明", "gids": 2,
                                      "size": 20, "last_id": last_id}, timeout=30)
        r.raise_for_status()
        payload = r.json()
        if payload.get("retcode") != 0:
            print("search failed:", payload.get("message"))
            break
        data = payload.get("data") or {}
        posts = data.get("posts") or []
        for wrapper in posts:
            post = wrapper.get("post") or {}
            user = wrapper.get("user") or {}
            subject = post.get("subject") or ""
            if str(user.get("uid")) != str(OFFICIAL_UID):
                continue
            if "版本更新说明" not in subject:
                continue
            found[str(post.get("post_id"))] = {
                "post_id": str(post.get("post_id")),
                "title": subject,
                "created_at": post.get("created_at"),
                "uid": user.get("uid"),
            }
        nxt = data.get("last_id")
        print(f"  search page {page + 1}: {len(posts)} posts, total official {len(found)}, next {nxt}")
        if data.get("is_last") or nxt in seen_last or nxt is None:
            break
        seen_last.add(nxt)
        last_id = nxt
        time.sleep(INTERVAL)
    rows = sorted(found.values(), key=lambda x: x.get("created_at") or 0)
    return rows


def fetch_posts(s: requests.Session, rows: list[dict]) -> None:
    RAW_MYS.mkdir(parents=True, exist_ok=True)
    for i, row in enumerate(rows, 1):
        out = RAW_MYS / f"{row['post_id']}.json"
        if out.exists():
            print(f"[{i}/{len(rows)}] cached {row['post_id']}")
            continue
        r = s.get(MYS_FULL, params={"post_id": row["post_id"], "read": 1}, timeout=30)
        payload = r.json()
        if payload.get("retcode") != 0:
            print(f"[{i}/{len(rows)}] {row['post_id']} failed: {payload.get('message')}")
            continue
        out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        content = (((payload.get("data") or {}).get("post") or {}).get("post") or {}).get("content") or ""
        print(f"[{i}/{len(rows)}] {row['post_id']} {row['title'][:32]} html={len(content)}")
        time.sleep(INTERVAL)


def search_by_version(s: requests.Session) -> list[dict]:
    """按版本号逐个搜索，避免搜索结果只按热度返回最近几条。"""
    keywords = [f"{major}.{minor}版本更新说明" for major in range(1, 8) for minor in range(0, 10)]
    keywords += [f"月之{n}版本更新说明" for n in ["一", "二", "三", "四", "五", "六", "七", "八"]]
    found: dict[str, dict] = {}
    for kw in keywords:
        try:
            r = s.get(MYS_SEARCH, params={"keyword": kw, "gids": 2, "size": 20, "last_id": 0},
                      timeout=30)
            payload = r.json()
        except Exception as exc:
            print(f"  {kw}: {type(exc).__name__}")
            time.sleep(INTERVAL)
            continue
        posts = ((payload.get("data") or {}).get("posts")) or []
        hit = 0
        for wrapper in posts:
            post = wrapper.get("post") or {}
            user = wrapper.get("user") or {}
            subject = post.get("subject") or ""
            if str(user.get("uid")) != str(OFFICIAL_UID) or "版本更新说明" not in subject:
                continue
            found[str(post.get("post_id"))] = {
                "post_id": str(post.get("post_id")),
                "title": subject,
                "created_at": post.get("created_at"),
                "uid": str(user.get("uid")),
            }
            hit += 1
        print(f"  {kw}: {hit} official")
        time.sleep(INTERVAL * 0.6)
    return sorted(found.values(), key=lambda x: x.get("created_at") or 0)


COMPILATION_POST = "75791879"  # 玩家整理的「历次版本更新说明」，只用来发现历史公告的 post_id


def discover_from_compilation(s: requests.Session) -> list[dict]:
    """从整理帖里取出「X.Y 版本名」的链接，作为历史公告候选。"""
    r = s.get(MYS_FULL, params={"post_id": COMPILATION_POST, "read": 1}, timeout=30)
    payload = r.json()
    if payload.get("retcode") != 0:
        print("  整理帖读取失败:", payload.get("message"))
        return []
    post = (((payload.get("data") or {}).get("post") or {}).get("post")) or {}
    html = post.get("content") or ""
    rows = []
    for para in re.findall(r"<p[^>]*>(.*?)</p>", html, re.S):
        ids = re.findall(r"article/(\d+)", para)
        if not ids:
            continue
        label = re.sub(r"<[^>]+>", "", para).strip()
        if not re.match(r"^(\d+\.\d|月之)", label):
            continue
        rows.append({"post_id": ids[0], "label": label[:60], "created_at": None,
                     "uid": str(OFFICIAL_UID)})
    print(f"  整理帖候选 {len(rows)} 条")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--probe", action="store_true", help="只搜索版本说明，不抓正文")
    ap.add_argument("--skip-current", action="store_true", help="跳过游戏内公告")
    args = ap.parse_args()

    s = session()
    if not args.skip_current:
        fetch_current(s)

    print("搜索米游社「版本更新说明」（关键词翻页）…")
    rows = search_version_notes(s, max_pages=8)
    print(f"  翻页得到 {len(rows)} 条")

    print("按版本号补搜…")
    by_version = search_by_version(s)
    print(f"  版本号搜到 {len(by_version)} 条")
    merged = {r["post_id"]: r for r in rows}
    for r in by_version:
        merged.setdefault(r["post_id"], r)
    rows = sorted(merged.values(), key=lambda x: x.get("created_at") or 0)

    print("从整理帖补历史链接…")
    candidates = discover_from_compilation(s)
    known = set(merged)
    extra = [c for c in candidates if c["post_id"] not in known]
    print(f"  新增候选 {len(extra)} 条")

    (ROOT / "raw" / "miyoushe").mkdir(parents=True, exist_ok=True)
    (ROOT / "raw" / "miyoushe" / "version-notes.json").write_text(
        json.dumps(rows + extra, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"官方版本说明合计 {len(rows)} 条（另 {len(extra)} 条候选待按标题核验）")
    for row in rows[-5:]:
        print("  ", row["post_id"], row["title"][:50])
    if args.probe:
        return 0

    fetch_posts(s, rows + extra)
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
