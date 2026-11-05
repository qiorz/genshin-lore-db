# -*- coding: utf-8 -*-
"""重填 quest.obc.5299「第三章 第二幕 千朵玫瑰带来的黎明」的「尾声」节。

事故：BWiki 补全脚本用子任务名「尾声」搜索，模糊命中蒙德序章第三幕的
「尾声的尾声」页面，把整段蒙德剧情写进了 3.0 须弥任务的 `## 尾声`。

观测枢原始快照 5299 的 collapse_panel 里本来就有 8 段「剧情对话」，
其中模块 17（以「最终妮露的舞蹈给大家带来了黎明」开头）正是「尾声」正文。
其余 7 段与 BWiki 补全的 7 个子任务页一一对应，只有这一段覆盖率为 0。
所以这里直接用 OBC 原文重填，不再依赖 BWiki。

用法：
    python scripts/repair_quest_5299_epilogue.py           # 干跑，打印替换预览
    python scripts/repair_quest_5299_epilogue.py --apply   # 写回 Markdown
"""
import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "corpus/quests/archon/第三章 第二幕 「千朵玫瑰带来的黎明」.md"
RAW = ROOT / "raw/official_site/obc/entries/5299.json"
ANCHOR = "最终妮露的舞蹈给大家带来了黎明"
APPLY = "--apply" in sys.argv


def as_json(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}
    return value or {}


def find_epilogue_rich(page: dict) -> str:
    for module in page.get("modules") or []:
        if (module.get("name") or "").strip() != "剧情对话":
            continue
        for comp in module.get("components") or []:
            if comp.get("component_id") != "collapse_panel":
                continue
            rich = as_json(comp.get("data")).get("rich_text") or ""
            if ANCHOR in rich:
                return rich
    raise SystemExit("未在原始快照里找到「尾声」剧情对话块")


def render_epilogue(rich: str) -> list[str]:
    """把 OBC 的纯文本对话块转成 corpus 的 Markdown 约定。"""
    soup = BeautifulSoup(rich, "html.parser")
    out: list[str] = []
    for p in soup.find_all("p"):
        text = re.sub(r"\s+", " ", p.get_text("", strip=True)).strip()
        if not text or text.startswith("PS："):
            continue
        if re.fullmatch(r"[-—\s]{6,}", text):
            out.append("")
            continue
        strongs = p.find_all("strong")
        if len(strongs) == 1 and strongs[0].get_text(strip=True) == text:
            if len(text) <= 20 and "。" not in text:
                out.extend(["", f"### {text}", ""])
            else:
                out.append(f"> *{text}*")
            continue
        spoken = re.match(r"^([^：:]{1,24})[：:]\s*(.+)$", text)
        underline = p.find("u")
        if underline and spoken:
            out.append(f"> 选项（{spoken.group(1).strip()}）：{underline.get_text('', strip=True)}")
        elif spoken:
            out.append(f"**{spoken.group(1).strip()}**：{spoken.group(2).strip()}")
        else:
            out.append(f"> *{text}*")
    compact: list[str] = []
    for line in out:
        if line == "" and (not compact or compact[-1] == ""):
            continue
        compact.append(line)
    while compact and compact[-1] == "":
        compact.pop()
    while compact and compact[0] == "":
        compact.pop(0)
    return compact


def main() -> int:
    page = json.loads(RAW.read_text(encoding="utf-8"))["data"]["page"]
    lines = render_epilogue(find_epilogue_rich(page))
    print(f"尾声正文：{len(lines)} 行，{sum(len(x) for x in lines)} 字符")
    for line in lines[:12]:
        print("   ", line[:110])

    text = DOC.read_text(encoding="utf-8")
    pattern = re.compile(r"^## 尾声\s*\n.*?(?=^## )", re.M | re.S)
    match = pattern.search(text)
    if not match:
        raise SystemExit("文档里没有找到 `## 尾声` 节")
    old = match.group(0)
    print(f"原节：{len(old.splitlines())} 行，{len(old)} 字符")

    section = "## 尾声\n\n" + "\n".join(lines).rstrip() + "\n\n"
    new_text = pattern.sub(lambda _m: section, text, count=1)
    new_text = re.sub(
        r"^notes: .*$",
        "notes: 观测枢 entry_page 试点导出；官方平台/社区编辑，非逐字官方文本；"
        "分支由 child_ids 展开；无场景字幕的模块用“剧情对话 N”编号。"
        " BWiki 补全任务剧情：7 个子任务页；「尾声」正文取自观测枢原始快照的「剧情对话」折叠面板"
        "（BWiki 无对应子页）；已剔除 BWiki 短名错配误收的序章第三幕「尾声的尾声」内容。",
        new_text,
        count=1,
        flags=re.M,
    )
    print(f"新节：{len(section.splitlines())} 行，{len(section)} 字符")
    if "听安柏说，琴团长正在大教堂等你" in new_text:
        raise SystemExit("替换后仍残留蒙德序章内容，已中止")
    if not APPLY:
        print("（干跑，未写文件；加 --apply 生效）")
        return 0
    DOC.write_text(new_text, encoding="utf-8", newline="\n")
    print(f"wrote {DOC.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
