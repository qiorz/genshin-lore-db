# -*- coding: utf-8 -*-
"""把官方公告渲染成 corpus/notices/ 下的 Markdown。

来源：
1. 米游社官方账号的历次「版本更新说明」（raw/miyoushe/posts/*.json）；
2. 游戏内公告 API 的当前窗口（raw/official_site/announcements/*.json）。

只收版本更新说明、全新内容一览与活动类公告；祈愿、礼包、装扮、签到、赛季、
声明等纯运营公告跳过，清单写入 manifests/notice-skip.csv。

用法：
    python scripts/render_notices.py            # 干跑
    python scripts/render_notices.py --apply    # 写文件并生成 index.csv
"""
import csv
import datetime
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import render_obc as R  # noqa: E402

APPLY = "--apply" in sys.argv
MYS = ROOT / "raw" / "miyoushe" / "posts"
ANN = ROOT / "raw" / "official_site" / "announcements"

# 当前窗口公告里，这些词出现在标题中就不收（纯运营/系统页）
SKIP_WORDS = (
    "祈愿", "礼包", "装扮", "上架", "开售", "签到", "赛季", "纪行",
    "七圣召唤", "创作赛", "声明", "调研", "FAQ", "社区", "防沉迷", "公平运营",
)
KEEP_TITLE = ("版本更新说明", "全新内容一览", "活动")

LUNA = {"一": "6.0", "二": "6.1", "三": "6.2", "四": "6.3",
        "五": "6.4", "六": "6.5", "七": "6.6", "八": "6.7"}


def safe(name: str) -> str:
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", (name or "").strip()).rstrip(". ")
    return s[:120] or "untitled"


def parse_version(title: str) -> str:
    m = re.search(r"(\d+\.\d+)版本更新说明", title)
    if m:
        return m.group(1)
    m = re.search(r"月之([一二三四五六七八])", title)
    if m:
        return LUNA.get(m.group(1), "")
    m = re.search(r"(\d+\.\d+)", title)
    if m:
        return m.group(1)
    return ""


def clean_html(html: str) -> list[str]:
    """把公告 HTML 转成按行文本：去掉图片和表格，〓标题〓 单独成行。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "table", "img"]):
        tag.decompose()
    text = R.html_paragraphs(str(soup))
    lines = []
    for raw in text.splitlines():
        line = raw.replace("\u3000", " ").strip()
        if not line:
            continue
        if re.fullmatch(r"[·・….]+", line):
            continue
        lines.append(line)
    return lines


def body_from_lines(lines: list[str]) -> list[str]:
    """把 〓xxx〓 变成 ### 小标题，其余按段落输出。"""
    body: list[str] = []
    for line in lines:
        m = re.match(r"^〓\s*(.+?)\s*〓$", line)
        if m:
            body.extend(["", f"### {m.group(1).strip()}", ""])
        else:
            body.append(line)
    # 压缩连续空行
    out: list[str] = []
    for line in body:
        if line == "" and out and out[-1] == "":
            continue
        out.append(line)
    while out and out[0] == "":
        out.pop(0)
    while out and out[-1] == "":
        out.pop()
    return out


def notice_doc(doc_id, title, subtype, version, release_date, source, body_lines, notes):
    front = {
        "id": doc_id,
        "type": "notice",
        "subtype": subtype,
        "title": title,
        "language": "zh-Hans",
        "version": version,
        "version_source": "official",
        "version_confidence": "confirmed" if version else "unknown",
        "release_date": release_date,
        "canon_status": "official",
        "transcription": "verbatim",
        "spoiler": {"level": 1, "scope": [f"notice:{subtype}"]},
        "source": [source],
        "status": "draft",
        "notes": notes,
    }
    if not front.get("version"):
        front.pop("version", None)
        front.pop("version_source", None)
        front.pop("version_confidence", None)

    body: list[str] = ["## 版本信息", ""]
    body.append(f"- 版本：{version or '未标注'}")
    body.append(f"- 上线日期：{release_date or '未知'}")
    body.append(f"- 类型：{subtype}")
    body.extend(["", "## 公告正文", ""])
    body.extend(body_lines)
    return front, body


rows = []
skipped = []

# ---------- 1. 米游社版本更新说明 ----------
for f in sorted(MYS.glob("*.json")):
    payload = json.loads(f.read_text(encoding="utf-8"))
    post = (((payload.get("data") or {}).get("post") or {}).get("post")) or {}
    title = (post.get("subject") or "").strip()
    if "更新说明" not in title:
        skipped.append((f"notice.mys.{post.get('post_id')}", title, "非版本更新说明"))
        continue
    ts = post.get("created_at")
    date = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d") if ts else ""
    version = parse_version(title)
    source = {
        "source_id": "miyoushe",
        "url": f"https://www.miyoushe.com/ys/article/{post.get('post_id')}",
        "page_id": str(post.get("post_id")),
        "retrieved_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "license": "site-policy",
    }
    lines = clean_html(post.get("content") or "")
    if len("".join(lines)) < 50:
        skipped.append((f"notice.mys.{post.get('post_id')}", title, "正文为空"))
        continue
    front, body = notice_doc(
        f"notice.mys.{post.get('post_id')}", title, "版本更新说明", version, date, source,
        body_from_lines(lines),
        "米游社原神官方账号发布的版本更新说明；只去掉图片与表格，正文保持原文。"
        "含补偿、更新时间、客户端方式等运营段落，作为版本时间线佐证保留，不作叙事正文使用。",
    )
    path = ROOT / "corpus/notices" / "版本更新说明" / f"{date or 'unknown'}-{safe(title)}.md"
    rows.append((front, body, path))

# ---------- 2. 游戏内公告当前窗口 ----------
list_path = ANN / "getAnnList.json"
content_path = ANN / "getAnnContent.json"
if list_path.exists() and content_path.exists():
    listing = json.loads(list_path.read_text(encoding="utf-8"))["data"]
    contents = json.loads(content_path.read_text(encoding="utf-8"))["data"]["list"]
    by_id = {str(c["ann_id"]): c for c in contents}
    labels = {str(t["id"]): t.get("mi18n_name") or t.get("name") for t in listing.get("type_list") or []}
    seen_titles = {f["title"] for f, _b, _p in rows}

    for group in listing.get("list") or []:
        subtype = labels.get(str(group.get("type_id")), group.get("type_label") or "公告")
        for item in group.get("list") or []:
            ann_id = str(item.get("ann_id"))
            title = (item.get("title") or "").strip()
            if not any(k in title for k in KEEP_TITLE):
                skipped.append((f"notice.ann.{ann_id}", title, "非叙事类公告"))
                continue
            # 「全新内容一览」虽然标题含「祈愿」，但它是新版本内容汇总，要收
            if any(w in title for w in SKIP_WORDS) and "全新内容一览" not in title:
                skipped.append((f"notice.ann.{ann_id}", title, "运营/系统类公告"))
                continue
            if title in seen_titles:
                skipped.append((f"notice.ann.{ann_id}", title, "与米游社版本说明重复"))
                continue
            content = by_id.get(ann_id) or {}
            html = content.get("content") or ""
            lines = clean_html(html)
            if len("".join(lines)) < 50:
                reason = "纯图片公告，无文本正文" if "<img" in html else "正文为空或过短"
                skipped.append((f"notice.ann.{ann_id}", title, reason))
                continue
            date = (item.get("start_time") or "")[:10]
            version = parse_version(title)
            source = {
                "source_id": "official_site",
                "url": f"https://hk4e-api.mihoyo.com/common/hk4e_cn/announcement/api/getAnnContent?ann_id={ann_id}",
                "page_id": ann_id,
                "retrieved_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
                "license": "site-policy",
            }
            front, body = notice_doc(
                f"notice.ann.{ann_id}", title, subtype, version, date, source,
                body_from_lines(lines),
                "游戏内公告接口导出；只去掉图片与表格，正文保持原文。",
            )
            path = ROOT / "corpus/notices" / safe(subtype) / f"{date or 'unknown'}-{safe(title)}.md"
            rows.append((front, body, path))

print(f"通知：可归档 {len(rows)}，跳过 {len(skipped)}")
by_sub = {}
for front, _b, _p in rows:
    by_sub[front["subtype"]] = by_sub.get(front["subtype"], 0) + 1
print("  按子类型:", by_sub)
print("  版本范围:", sorted({f["version"] for f, _b, _p in rows if f.get("version")})[:6], "…",
      sorted({f["version"] for f, _b, _p in rows if f.get("version")})[-3:])
for s in skipped[:6]:
    print("   skip", s[1][:34], s[2])

if APPLY:
    for front, body, path in rows:
        path.parent.mkdir(parents=True, exist_ok=True)
        head = yaml.safe_dump(front, allow_unicode=True, sort_keys=False, width=120)
        path.write_text(f"---\n{head}---\n\n" + "\n".join(body).rstrip() + "\n",
                        encoding="utf-8", newline="\n")
    with (ROOT / "corpus/notices/index.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["doc_id", "title", "subtype", "version", "release_date", "path"])
        for front, _b, path in rows:
            w.writerow([front["id"], front["title"], front["subtype"],
                        front.get("version", ""), front.get("release_date", ""),
                        str(path.relative_to(ROOT)).replace("\\", "/")])
    with (ROOT / "manifests/notice-skip.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["doc_id", "title", "reason"])
        w.writerows(skipped)
    print("wrote", len(rows), "notices")
else:
    for front, body, path in rows[:2]:
        print("=== preview", front["id"], front["title"][:40])
        print("\n".join(body)[:500])
