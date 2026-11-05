# -*- coding: utf-8 -*-
"""语料层共享规则：元数据行识别 + 台词归一化。

`load_markdown.py` 用它把结构性元数据行排除出 sections/FTS；
`audit_corpus.py` 用它做跨文档重复与串内容检测。两边必须保持一致。
"""
from __future__ import annotations

import re

# 只列「结构性字段」。叙述性字段（描述、角色介绍、编者注、任务过程等）必须保留，
# 例如书籍的 `## 书籍信息` 里混有卷次描述，整节跳过会丢正文。
META_BULLET_RE = re.compile(
    r"^-\s*(?:类型|地区|版本|版本来源|版本置信度|来源|稀有度|部件|上线日期|"
    r"获得方式|性别|位置|职业|功能|物种|角色名|生日|所属|套装|星级)[：:]"
)

_PUNCT_RE = re.compile(
    r"[\s\*>_#\[\]（）()，。！？、：:「」『』…·．,.:;!?\"'~—\-]+"
)


def is_meta_bullet(line: str) -> bool:
    """是否为「- 类型：…」这类不属于正文的结构性字段。"""
    return bool(META_BULLET_RE.match(line.strip()))


def normalize_line(line: str) -> str:
    """把一行台词/旁白归一化，用于跨来源比对。

    去掉 Markdown 标记与标点，但**保留说话人文字**，
    这样 OBC 的 `派蒙：…` 与 corpus 的 `**派蒙**：…` 能对上，
    又不会把不同说话人的同一句话误合并。
    """
    text = line.strip().lstrip(">").strip()
    text = text.replace("**", "").replace("*", "")
    return _PUNCT_RE.sub("", text)
