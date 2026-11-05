#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""人工复核状态的唯一入口。

为什么要单独一个文件：`knowledge/seed*.yaml` 有一部分是脚本生成的，
把 `status: reviewed` 直接写进去，下次重新生成就被覆盖了。
所以复核结论落在 `knowledge/review-state.yaml`，由灌库与导出脚本读取后覆盖状态。

用法：
    from knowledge_state import reviewed_ids
    ids = reviewed_ids(ROOT)
"""
from __future__ import annotations

from pathlib import Path

import yaml

STATE_NAME = "knowledge/review-state.yaml"


def reviewed_ids(root: Path) -> set[str]:
    path = root / STATE_NAME
    if not path.exists():
        return set()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {item["id"] for item in data.get("reviewed") or [] if item.get("id")}


def rejected_ids(root: Path) -> set[str]:
    path = root / STATE_NAME
    if not path.exists():
        return set()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {item["id"] for item in data.get("rejected") or [] if item.get("id")}
