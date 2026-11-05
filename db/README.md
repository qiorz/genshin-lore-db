# db · 本地数据库

这个目录存放 SQLite 数据库文件，默认：

```text
db/genshin_lore.sqlite3
```

当前状态：**全量文本库，含 9 个来源、7,734 篇文档、453,939 个段落**（物品 2,622、NPC 对话/逸闻/彩蛋 2,401、任务 1,097、散落文本 705、观景点 264、武器 252、角色 136、书籍 92、圣遗物 63、官方公告 55、活动 47；成就 1,558 条只在 CSV）。数据库文件约 345 MB，`integrity_check` 与 FTS5 `integrity-check` 均通过，中文检索、版本来源字段可用。

## 规则

- 数据库是**本地生成物**，不提交到版本库；
- 正式正文的权威副本在 `corpus/`：92 本书在 `corpus/books/`，1,065 条任务在 `corpus/quests/`，32 条空壳任务在 `corpus/quests/_pending/`，705 条散落文本在 `corpus/scattered/`，136 个角色在 `corpus/characters/`，252 把武器在 `corpus/weapons/`，63 套圣遗物在 `corpus/artifacts/`，47 篇活动在 `corpus/events/`，264 篇观景点在 `corpus/geography/`，2,622 条材料/食物/动物/道具在 `corpus/items/`，2,401 篇 NPC 对话/逸闻/彩蛋在 `corpus/voices/`，55 篇官方公告在 `corpus/notices/`；数据库只是索引层，可随时从 `corpus/` 全量重建；
- 重新导入时注意分词模式：`quests` / `characters` / `voices` 用 `--no-segment`，`books` / `scattered` / `items` / `notices` **不加**该参数（走 jieba 分词）；
- 不要手工改数据库里的正文；改 Markdown，再重新导入；
- 改表结构用 `schema/migrations/`，不要直接改现库；
- 升级/重建前备份。

## 建库

```powershell
python scripts/init_db.py
```

或手动：

```python
import sqlite3
from pathlib import Path

con = sqlite3.connect("db/genshin_lore.sqlite3")
con.execute("PRAGMA foreign_keys = ON")
con.executescript(Path("schema/schema.sql").read_text(encoding="utf-8"))
con.executescript(Path("schema/fts.sql").read_text(encoding="utf-8"))
con.commit()
```

## 备份

```powershell
Copy-Item db/genshin_lore.sqlite3 "db/backup/genshin_lore-$(Get-Date -Format yyyyMMdd-HHmmss).sqlite3"
```

## 导出

- 阅读版：`exports/`
- 结构化：`sqlite3 db/genshin_lore.sqlite3 ".mode csv" ".output exports/documents.csv" "SELECT ..."`
- 备份：直接复制 `.sqlite3` 文件（先确保没有写入）。

## 注意

- `PRAGMA foreign_keys = ON` 是每个连接都要设置的；
- WAL 模式会生成 `-wal` / `-shm` 文件，复制前先关闭连接；
- 不要把数据库文件放进 `raw/` 或 `corpus/`。





