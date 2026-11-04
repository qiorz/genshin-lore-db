#!/usr/bin/env python3
"""Fetch pages and search results from 米游社·观测枢 (baike.mihoyo.com).

The public web app calls an internal JSON API; this script uses the same
public endpoints with a normal browser User-Agent and a 1 request/second
default. Raw responses are stored unchanged under raw/official_site/obc/.

Examples:
    python scripts/fetch_obc.py --entry-page-id 399 501 1290 --force
    python scripts/fetch_obc.py --channel-tree
    python scripts/fetch_obc.py --channel-id 68 251 43 --force
    python scripts/fetch_obc.py --search 钟离 --menu-id 25
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 fallback
    tomllib = None

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config" / "sources.toml"
DEFAULT_OUT = ROOT / "raw" / "official_site" / "obc"
TZ = timezone(timedelta(hours=8))
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


def load_config(path: Path) -> dict:
    if tomllib is None:
        raise SystemExit("Python 3.11+ is required for tomllib.")
    with path.open("rb") as fh:
        return tomllib.load(fh)


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_name(text: str) -> str:
    ascii_name = re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-")
    if ascii_name:
        return ascii_name[:60]
    return "search-" + hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def make_session(cfg: dict) -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    session.headers.update(
        {
            "User-Agent": cfg["http"]["user_agent"],
            "Referer": "https://baike.mihoyo.com/ys/obc/",
        }
    )
    return session


def get_json(
    session: requests.Session,
    url: str,
    params: dict,
    cfg: dict,
    *,
    retries: int,
) -> tuple[requests.Response, dict]:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, params=params, timeout=cfg["http"]["timeout_seconds"])
            if resp.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"HTTP {resp.status_code}")
            resp.raise_for_status()
            payload = resp.json()
            if payload.get("retcode") not in (0, None):
                raise requests.HTTPError(
                    f"retcode={payload.get('retcode')} message={payload.get('message')}"
                )
            return resp, payload
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt >= retries:
                break
            sleep_for = cfg["http"]["backoff_seconds"] * attempt
            print(f"  retry {attempt}/{retries} in {sleep_for:.1f}s: {exc}", file=sys.stderr)
            time.sleep(sleep_for)
    raise RuntimeError(f"request failed: {url} ({last_error})")


def write_meta(path: Path, meta: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_entry(
    session: requests.Session,
    cfg: dict,
    source: dict,
    entry_id: int,
    out_dir: Path,
    *,
    force: bool,
) -> None:
    raw_path = out_dir / "entries" / f"{entry_id}.json"
    meta_path = out_dir / "meta" / f"{entry_id}.json"
    if raw_path.exists() and not force:
        print(f"skip existing entry {entry_id} ({raw_path})")
        return

    url = f"{source['hoyowiki_base']}/wapi/entry_page"
    params = {
        "entry_page_id": entry_id,
        "app_sn": source["app_sn"],
        "lang": source["lang"],
    }
    resp, payload = get_json(
        session, url, params, cfg, retries=cfg["http"]["max_retries"]
    )
    page = ((payload.get("data") or {}).get("page") or {})
    menus = page.get("menus") or []
    menu_name = page.get("menu_name") or (menus[0].get("name") if menus else "")

    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(resp.content)
    meta = {
        "source_id": "obc",
        "entry_page_id": entry_id,
        "name": page.get("name"),
        "menu_id": page.get("menu_id"),
        "menu_name": menu_name,
        "page_version": page.get("version"),
        "url": f"https://baike.mihoyo.com/ys/obc/content/{entry_id}/detail?bbs_presentation_style=no_header",
        "api_url": url,
        "api_params": params,
        "http_status": resp.status_code,
        "retrieved_at": now_iso(),
        "sha256": sha256_bytes(resp.content),
        "content_type": resp.headers.get("Content-Type"),
        "notes": "Official platform, community-maintained; not a verbatim official transcript.",
    }
    write_meta(meta_path, meta)
    print(f"saved entry {entry_id}: {page.get('name')} ({len(resp.content)} bytes)")
    time.sleep(cfg["http"]["request_interval_seconds"])


def fetch_channel_tree(
    session: requests.Session, cfg: dict, source: dict, out_dir: Path, *, force: bool
) -> None:
    path = out_dir / "channel_tree.json"
    if path.exists() and not force:
        print(f"skip existing channel tree ({path})")
        return
    url = f"{source['api_base']}/v1/getChannelTree"
    params = {"app_sn": source["app_sn"], "lang": source["lang"]}
    resp, payload = get_json(session, url, params, cfg, retries=cfg["http"]["max_retries"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(resp.content)
    write_meta(
        out_dir / "meta" / "channel_tree.json",
        {
            "source_id": "obc",
            "url": url,
            "api_url": url,
            "api_params": params,
            "http_status": resp.status_code,
            "retrieved_at": now_iso(),
            "sha256": sha256_bytes(resp.content),
        },
    )
    print(f"saved channel tree ({len(resp.content)} bytes)")
    time.sleep(cfg["http"]["request_interval_seconds"])


def fetch_channel_list(
    session: requests.Session,
    cfg: dict,
    source: dict,
    channel_id: int,
    out_dir: Path,
    *,
    force: bool,
) -> None:
    path = out_dir / "channel_lists" / f"{channel_id}.json"
    if path.exists() and not force:
        print(f"skip existing channel list {channel_id} ({path})")
        return
    url = f"{source['api_base']}/v1/home/content/list"
    params = {
        "channel_id": channel_id,
        "page_num": 1,
        "page_size": 1000,
        "app_sn": source["app_sn"],
        "lang": source["lang"],
    }
    resp, payload = get_json(session, url, params, cfg, retries=cfg["http"]["max_retries"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(resp.content)
    channel = ((payload.get("data") or {}).get("list") or [{}])[0] or {}
    entries = channel.get("list") or []
    write_meta(
        out_dir / "meta" / f"channel-{channel_id}.json",
        {
            "source_id": "obc",
            "channel_id": channel_id,
            "channel_name": channel.get("name"),
            "url": url,
            "api_url": url,
            "api_params": params,
            "http_status": resp.status_code,
            "retrieved_at": now_iso(),
            "sha256": sha256_bytes(resp.content),
            "entry_count": len(entries),
        },
    )
    print(f"saved channel {channel_id} {channel.get('name')}: {len(entries)} entries")
    time.sleep(cfg["http"]["request_interval_seconds"])


def search(
    session: requests.Session,
    cfg: dict,
    source: dict,
    keyword: str,
    out_dir: Path,
    *,
    menu_id: int | None,
    force: bool,
) -> None:
    slug = safe_name(keyword)
    path = out_dir / "search" / f"{slug}.json"
    if path.exists() and not force:
        print(f"skip existing search {keyword} ({path})")
        return
    url = f"{source['hoyowiki_base']}/wapi/search"
    params = {
        "keyword": keyword,
        "page_num": 1,
        "page_size": 20,
        "app_sn": source["app_sn"],
        "lang": source["lang"],
    }
    if menu_id is not None:
        params["menu_id"] = menu_id
    resp, payload = get_json(session, url, params, cfg, retries=cfg["http"]["max_retries"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(resp.content)
    items = ((payload.get("data") or {}).get("list") or [])
    print(f"saved search {keyword}: {len(items)} result(s)")
    for item in items[:10]:
        print(f"  {item.get('entry_page_id')}  {item.get('name')}")
    time.sleep(cfg["http"]["request_interval_seconds"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--entry-page-id", type=int, nargs="+", default=[])
    parser.add_argument("--channel-tree", action="store_true")
    parser.add_argument("--channel-id", type=int, nargs="+", default=[])
    parser.add_argument("--search", action="append", default=[])
    parser.add_argument("--menu-id", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--workers", type=int, default=1, help="并发数；每个 worker 各自保持请求间隔")
    args = parser.parse_args()

    cfg = load_config(args.config)
    if "obc" not in cfg.get("sources", {}):
        raise SystemExit("config/sources.toml has no [sources.obc] section")
    source = cfg["sources"]["obc"]
    out_dir = args.out_dir

    session = make_session(cfg)
    if args.channel_tree:
        fetch_channel_tree(session, cfg, source, out_dir, force=args.force)
    for channel_id in args.channel_id:
        fetch_channel_list(session, cfg, source, channel_id, out_dir, force=args.force)
    if args.workers > 1 and args.entry_page_id:
        # 每个 worker 独立 session、各自保持 request_interval_seconds，
        # 总速率仍由配置控制，只是把网络等待重叠起来。
        from concurrent.futures import ThreadPoolExecutor

        sessions = [make_session(cfg) for _ in range(args.workers)]
        ids = list(args.entry_page_id)

        def work(pair):
            index, entry_id = pair
            fetch_entry(
                sessions[index % len(sessions)], cfg, source, entry_id, out_dir, force=args.force
            )

        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(work, enumerate(ids)))
    else:
        for entry_id in args.entry_page_id:
            fetch_entry(session, cfg, source, entry_id, out_dir, force=args.force)
    for keyword in args.search:
        search(
            session,
            cfg,
            source,
            keyword,
            out_dir,
            menu_id=args.menu_id,
            force=args.force,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
