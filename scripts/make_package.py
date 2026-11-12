#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把项目打成一个可迁移的 zip。

打进去的：源码、文档、主库、corpus、raw 原始 JSON、便携 Python、git 历史。
不打的：db/backup（1.6 GB 历史备份）、logs、缓存、临时文件。

为什么排除 `db/backup`：那里面是历次改动前的快照，占 1.6 GB，
对「换个设备继续开发」没有价值；真要回滚，git 里也有代码历史。

用法：
    python scripts/make_package.py                 # 输出到项目同级目录
    python scripts/make_package.py --out D:/tmp     # 指定输出目录
"""
from __future__ import annotations

import sys
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

EXCLUDE_DIRS = {
    "db/backup", "logs", "__pycache__", ".pytest_cache", "node_modules",
    ".idea", ".vscode", "webui/__pycache__", "scripts/__pycache__",
}
EXCLUDE_NAMES = {"jieba.cache", ".DS_Store", "Thumbs.db"}
EXCLUDE_SUFFIX = {".pyc", ".pyo", ".tmp", ".bak", ".pid", ".log"}
EXCLUDE_PREFIX = (".cmp-", ".probe", ".retry_", ".ids-")


def main() -> int:
    out_dir = ROOT.parent
    for i, a in enumerate(sys.argv):
        if a == "--out" and i + 1 < len(sys.argv):
            out_dir = Path(sys.argv[i + 1])
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"genshin-lore-db-{date.today().strftime('%Y%m%d')}.zip"

    files: list[Path] = []
    skipped: list[str] = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT).as_posix()
        if any(rel == d or rel.startswith(d + "/") for d in EXCLUDE_DIRS):
            continue
        if p.name in EXCLUDE_NAMES or p.suffix.lower() in EXCLUDE_SUFFIX:
            continue
        if p.name.startswith(EXCLUDE_PREFIX):
            continue
        files.append(p)

    total = sum(f.stat().st_size for f in files)
    print(f"待打包 {len(files):,} 个文件 / {total/1048576:.1f} MB → {dst}", flush=True)

    done = 0
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p in files:
            rel = p.relative_to(ROOT).as_posix()
            zf.write(p, arcname=f"genshin-lore-db/{rel}")
            done += 1
            if done % 5000 == 0:
                print(f"  {done:,} / {len(files):,}", flush=True)

    size = dst.stat().st_size
    print(f"完成：{dst}")
    print(f"  压缩后 {size/1048576:.1f} MB（原 {total/1048576:.1f} MB，"
          f"压到 {size/total*100:.0f}%）")
    if skipped:
        print("  跳过：" + "、".join(skipped[:5]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
