import csv
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "db" / "genshin_lore.sqlite3"
CHANNELS = ROOT / "raw" / "official_site" / "obc" / "channel_lists"
OUT = ROOT / "exports" / "obc-evaluation" / "coverage-audit.md"
sys.stdout.reconfigure(encoding="utf-8")

channel_meta = {
    "5": ("武器", "weapon"),
    "25": ("角色", "character"),
    "43": ("任务", "quest"),
    "68": ("书籍", "book"),
    "105": ("活动", "activity"),
    "218": ("圣遗物", "artifact"),
    "251": ("地图文本", "lore"),
    "252": ("成就", "achievement"),
}

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
counts = {r["doc_type"]: r["n"] for r in con.execute("SELECT doc_type, COUNT(*) n FROM documents GROUP BY doc_type")}
sections = con.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
sources = con.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
pending = con.execute("SELECT COUNT(*) FROM documents WHERE doc_type='quest' AND notes LIKE '%OBC 无剧情对话%'").fetchone()[0]
bwiki_quests = con.execute("SELECT COUNT(*) FROM documents d WHERE d.doc_type='quest' AND EXISTS(SELECT 1 FROM document_sources ds WHERE ds.doc_id=d.doc_id AND ds.source_id='bwiki')").fetchone()[0]
unknown_lore = con.execute("SELECT COUNT(*) FROM documents WHERE doc_type='lore' AND (version IS NULL OR version='')").fetchone()[0]
knowledge = {
    table: con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    for table in ("entities", "entity_relations", "claims", "events", "timeline_entries")
}
dupes = con.execute(
    "SELECT content_hash, COUNT(*) n, GROUP_CONCAT(doc_id) docs FROM documents "
    "GROUP BY content_hash HAVING n > 1 ORDER BY n DESC"
).fetchall()

channel_counts = {}
for channel_id, (name, key) in channel_meta.items():
    path = CHANNELS / f"{channel_id}.json"
    if not path.exists():
        channel_counts[key] = None
        continue
    payload = json.loads(path.read_text(encoding="utf-8"))
    channel = (payload.get("data") or {}).get("list") or []
    channel_counts[key] = len((channel[0].get("list") or [])) if channel else 0

rows = [
    ("书籍", "books", 93, counts.get("book", 0), "92 唯一书；503 重复卷跳过；500 只有第一卷；1158 版本 unknown"),
    ("地图文本", "scattered_text", channel_counts.get("lore"), counts.get("lore", 0), "706 条全部入库；480 条版本 unknown"),
    ("任务", "quests", 1101, counts.get("quest", 0), f"1,051 有正文；{pending} 条待补；{bwiki_quests} 条有 BWiki 源"),
    ("角色", "characters", channel_counts.get("character"), counts.get("character", 0), "136/138；2 条「奇偶」无叙事，未入库"),
    ("武器", "weapons", channel_counts.get("weapon"), 0, "未开始"),
    ("圣遗物", "artifacts", channel_counts.get("artifact"), 0, "未开始"),
    ("活动", "activities", channel_counts.get("activity"), 0, "未开始；活动任务只散落在任务频道"),
    ("成就", "achievements", channel_counts.get("achievement"), 0, "未开始；仅用版本字段辅助推导"),
]

lines = [
    "# 数据库覆盖审计",
    "",
    f"生成时间：{datetime.now().astimezone().isoformat(timespec='seconds')}",
    "",
    "## 当前总量",
    "",
    "```text",
    f"文档：{sum(counts.values()):,}",
    f"段落：{sections:,}",
    f"来源：{sources}",
    f"书籍：{counts.get('book',0):,}",
    f"任务：{counts.get('quest',0):,}（待补 {pending}）",
    f"散落文本：{counts.get('lore',0):,}（版本 unknown {unknown_lore}）",
    f"角色：{counts.get('character',0):,}",
    "```",
    "",
    "## 对照 OBC 频道",
    "",
    "| 类别 | OBC 条目 | 已入库 | 状态 |",
    "|---|---:|---:|---|",
]
for label, _key, total, loaded, note in rows:
    total_text = f"{total:,}" if isinstance(total, int) else "—"
    lines.append(f"| {label} | {total_text} | {loaded:,} | {note} |")

lines += [
    "",
    "## 明显缺口",
    "",
    "### P0：任务还有尾巴",
    "",
    "- 角色 136/138：2 条「奇偶」无叙事；角色故事、描述、神之眼/神之心、关联语音、生日邮件已入库。",
    "- 任务有 50 条 OBC 缺正文；其中不少是邀约/活动系列页。",
    "- 1,051 条任务里仍混有系列/总览页与子任务页，尚未做最终“一篇一幕”审计。",
    "",
    "### P1：高信息密度文本未做",
    "",
    "- 武器 252 条，0 入库。",
    "- 圣遗物 63 套，0 入库。",
    "- 活动 275 条，0 入库。",
    "- 成就 1,626 条，0 入库。",
    "- 角色语音、材料/食物/道具描述、地理志、官方公告、漫画、NPC 对话都未做。",
    "",
    "### 质量缺口",
    "",
    f"- 散落文本版本 unknown：{unknown_lore}/706；按约定不再猜。",
    f"- 待补任务：{pending}/1,101。",
    "- 书籍：500 只有第一卷全文；1158 版本 unknown。",
    "- 同文重复组：" + "、".join(
        f"{r['n']} 条（{r['docs']}）" for r in dupes[:6]
    ) + (" 等。" if len(dupes) > 6 else "。"),
    "- 知识层全空：entities / relations / claims / events / timeline_entries 都是 0。",
    "",
    "## 建议顺序",
    "",
    "1. **武器/圣遗物**：252 + 63，单条短、信息密度高，适合批量。",
    "2. **活动/成就**：275 + 1,626，主要补版本、事件、世界观碎片。",
    "3. **50 条待补任务 + 同文重复组**：邀约/活动模板，补完再宣布任务库完整。",
    "4. **物品/地理/公告/漫画/NPC**：量大，放后面。",
    "5. **知识层**：等文本覆盖稳定后再做实体、关系、时间线。",
    "",
]
OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"wrote {OUT}")

