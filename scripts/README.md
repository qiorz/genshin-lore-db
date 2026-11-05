# scripts

## 当前可用

| 脚本 | 作用 | 依赖 |
|---|---|---|
| `check_env.ps1` | 检查 Python/SQLite/FTS5/包/目录 | PowerShell 5.1+ |
| `Search-Corpus.ps1` | 在 `corpus/` 中做 Markdown 全文搜索 | PowerShell 5.1+ |
| `fetch_obc.py` | 抓观测枢 entry_page / search / channel_tree | Python 3.11+ |
| `render_obc.py` | entry_page → Markdown 草稿（任务/书籍/角色/散落文本/武器/圣遗物/活动/地理/物品/NPC 对话） | Python 3.11+ |
| `load_markdown.py` | Markdown → SQLite（documents/sections/FTS） | Python 3.11+ |
| `search.py` | SQLite FTS5 命令行检索 | Python 3.11+ |
| `validate_frontmatter.py` | front matter schema 校验 | Python 3.11+ |
| `build_obc_index.py` | 从频道列表生成书籍/散落文本/任务索引 | Python 3.11+ |
| `resolve_versions_bwiki.py` | 用 BWiki SMW 批量补书籍版本/地区 | Python 3.11+ |
| `resolve_scattered_versions.py` | 从散落文本“相关任务”推导版本 | Python 3.11+ |
| `render_obc_batch.py` | 批量渲染散落文本/任务 | Python 3.11+ |
| `build_character_index.py` | 从角色频道生成 `character-index.csv` | Python 3.11+ |
| `render_characters.py` | 角色页 → `corpus/characters/`（只留叙事文本） | Python 3.11+ |
| `fill_quests_from_bwiki.py` | 用 BWiki 子任务页补 OBC 缺正文的任务 | Python 3.11+ |
| `mark_empty_quests.py` | 给仍无对话的任务加待补标记 | Python 3.11+ |
| `clean_filled_quest_notes.py` | 清理已补全任务的“无对话”旧标记 | Python 3.11+ |
| `sync_index_versions.py` | 索引版本同步到 front matter/DB | Python 3.11+ |
| `report_db.py` | 生成简洁数据库统计 | Python 3.11+ |
| `move_books_to_corpus.py` | 书籍按地区移入 `corpus/books/` | Python 3.11+ |
| `render_equipment.py` | 武器/圣遗物批量渲染 | Python 3.11+ |
| `fetch_bwiki_equipment.py` | BWiki 装备故事与版本对照 | Python 3.11+ |
| `render_events.py` | 活动页 + 成就索引 | Python 3.11+ |
| `render_geography.py` | 观景点 / 区域 | Python 3.11+ |
| `render_items.py` | 材料/食物/动物/道具 | Python 3.11+ |
| `fetch_announcements.py` | 抓米游社官方帖与游戏内公告 API | Python 3.11+ |
| `render_notices.py` | 官方公告 → `corpus/notices/` | Python 3.11+ |
| `render_npcs.py` | NPC 对话/逸闻/彩蛋 → `corpus/voices/` | Python 3.11+ |
| `repair_quest_5299_epilogue.py` | 用 OBC 原始快照重填 5299 的「尾声」，修复 BWiki 短名错配 | Python 3.11+ |
| `corpus_rules.py` | 共享规则：结构性元数据行识别、台词归一化（导入器与体检脚本共用） | Python 3.11+ |
| `audit_corpus.py` | **全库体检**：串内容/重复、字段覆盖、corpus↔DB 对账、FTS 完整性 | Python 3.11+ |
| `enrich_release_versions.py` | 按官方版本更新说明的上线日期区间，给有 `release_date` 无 `version` 的公告推导版本（`official`/`inferred`） | Python 3.11+ |
| `normalize_version_labels.py` | 把「月之X」/多版本列表/版本区间归一化为 `X.Y`，玩法标签移出 version 字段 | Python 3.11+ |
| `build_stage5.py` | 第五批收尾：NPC 人物按 `sections.speaker` 台词量取（≥50 段），其余类别走候选表 + 库内证据；剔除泛用词；产出 `seed-stage5.yaml` | Python 3.11+ |
| `mine_relations.py` | 从正文挖人物→组织、地点/组织→国家三类关系：同句不重叠共现 + 跨度 ≤16 字 + 连接词/职务词；地点类只认相邻句式；人工复核剔除项写在同一文件里并注明理由 | Python 3.11+ |
| `mine_aliases.py` | 别名候选：严格引号相邻规则 + 人工词表（每个别称须在语料出现 ≥2 次且与正名同篇）；输出候选 CSV | Python 3.11+ |
| `apply_aliases.py` | 把复核通过的别名写回实体所在 seed 的 `aliases`；只收有辨识度的称号，职务词不收 | Python 3.11+ |
| `enrich_evidence.py` | 给指定种子里证据不足的**非人物**实体补锚点到 3 条（不同文档各一句），不动实体集合与描述；`--apply` 才写 | Python 3.11+ |
| `prune_cards.py` | 清理 `knowledge/entities/` 下的过期卡与同 id 多目录的重复副本（YAML 解析 front matter，不靠正则）；`--apply` 才删 | Python 3.11+ |
| `review_queue.py` | 给 `status=draft` 的实体排复核优先级（先按任务提及篇数，再按文档篇数），做三项机械校验，输出 `exports/review/` 下 md + csv；`--mark/--unmark` 写复核记录 | Python 3.11+ |
| `knowledge_state.py` | 复核状态的唯一读取入口：`reviewed_ids()`。复核结论存 `knowledge/review-state.yaml`，不写进会被重新生成的 seed | Python 3.11+ |
| `build_stage4.py` | 第四批扩量：角色直接以 136 篇角色页为权威名单，地点/组织用候选表 + 库内证据校验；中文名经 `pypinyin` 生成 `entity_id`，未安装时退回文档号；产出 `entity-candidates-stage4.csv` 与 `seed-stage4.yaml` | Python 3.11+ |
| `mine_entities.py` | 从词表 × 真实段落反查候选实体，按文档类型打分并扣噪声词，产出 `knowledge/entity-candidates.csv`；只给候选，收录与否由人定 | Python 3.11+ |
| `load_knowledge.py` | 把 `knowledge/seed*.yaml`（全部批次）灌进知识层（实体/别名/出处/说法/关系/事件/时间线）；证据只用 `doc_id + 短引用` 现场解析 section_id，抗重导；固定主键幂等；`--prune` 剪掉已不在任何种子中的实体 | Python 3.11+ |
| `export_entity_cards.py` | 把知识层种子导出为 `knowledge/` 下 400 份实体卡 + 说法/事件/时间线 Markdown（生成物，不要手改） | Python 3.11+ |

```powershell
# Windows PowerShell（当前环境需要 Bypass 执行策略）
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_env.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Search-Corpus.ps1 钟离

# 观测枢试点
.\tools\python\python.exe scripts\fetch_obc.py --entry-page-id 399 --force
.\tools\python\python.exe scripts\render_obc.py --entry raw\official_site\obc\entries\399.json `
    --type quest --doc-id quest.obc.399 --region 蒙德 `
    --out exports\obc-batch\quest-399.md
.\tools\python\python.exe scripts\render_obc.py --entry raw\official_site\obc\entries\507704.json `
    --type lore --doc-id lore.obc.507704 --region 挪德卡莱 `
    --out exports\obc-batch\lore-507704.md
.\tools\python\python.exe scripts\validate_frontmatter.py exports\obc-batch\quest-399.md
.\tools\python\python.exe scripts\load_markdown.py exports\obc-batch\quest-399.md
.\tools\python\python.exe scripts\search.py 钟离

# 索引与版本
.\tools\python\python.exe scripts\build_obc_index.py
.\tools\python\python.exe scripts\resolve_versions_bwiki.py --category 书籍 --property 书籍名

# 批量散落文本/任务（先 fetch，再 resolve/ render / load）
.\tools\python\python.exe scripts\fetch_obc.py --channel-id 68 251 43 --force
.\tools\python\python.exe scripts\resolve_scattered_versions.py
.\tools\python\python.exe scripts\render_obc_batch.py --doc-type lore
.\tools\python\python.exe scripts\render_obc_batch.py --doc-type quest
.\tools\python\python.exe scripts\validate_frontmatter.py --dir exports\obc-batch --quiet
.\tools\python\python.exe scripts\load_markdown.py --dir exports\obc-batch
```

## 计划中的脚本

按依赖顺序：

| 脚本 | 作用 | 输入 | 输出 |
|---|---|---|---|
| `fetch_bwiki.py` | 抓 BWiki 页面（对照/兜底） | 页面名/ID 清单 | `raw/bwiki/*` + `meta.json` |
| `fetch_miyoushe.py` | 抓米游社帖子 | `post_id` 清单 | `raw/miyoushe/*` |
| `parse_bwiki.py` | 解析任务/书籍/武器/圣遗物 | wikitext | 结构化 JSON |
| `coverage.py` | 按观测枢频道树统计覆盖 | db + channel_tree | CSV/Markdown |
| `init_db.py` | 建库/迁移 | schema | `db/*.sqlite3` |

`render_obc.py` 目前是试点版：任务对话图去重展开、书籍分卷、角色故事过滤；还不是完整解析器。

## 编码约定

- Python 3.11+（`fetch_obc.py` 用 `tomllib`；当前便携版 3.13），UTF-8，LF；
- 所有脚本支持 `--dry-run`（不写文件/库）；
- 抓取脚本支持 `--limit`、`--resume`；
- 原始快照只增不改；同名文件加 `-<revid>` 或时间戳；
- 数据库写入记录 `ingest_runs`（`load_markdown.py` 已记录；抓取脚本扩量前补上）；
- 日志写 `logs/`，不要只输出到终端；
- 不在代码里写 Cookie/Token；需要时读环境变量；
- 默认 1 请求/秒，失败指数退避；
- 解析失败要保留原始快照和错误信息，不静默跳过；
- 不要用 `print` 输出大段原文，日志只记录路径和摘要。

## 建议的模块划分

```text
scripts/
├─ common/
│  ├─ config.py          # 读 config/sources.toml
│  ├─ http.py            # 限速、重试、缓存、UA
│  ├─ paths.py           # 项目路径
│  └─ log.py
├─ fetch_bwiki.py
├─ fetch_miyoushe.py
├─ parse_bwiki.py
├─ normalize.py
├─ init_db.py
├─ load_corpus.py
├─ search.py
├─ validate.py
└─ coverage.py
```

第一版不要过度抽象；先把一个页面的路径跑通，再抽公共模块。

## 测试

至少覆盖：

- 模板清洗：`{{颜色}}`、`{{黑幕}}`、`[[链接|显示]]`、`{{任务描述}}`；
- 对话解析：`*角色：台词`；
- 选项保留：`> 选项：`；
- front matter 校验；
- 重复哈希不重复入库；
- FTS 中文查询。

用小样本做单元测试，不要连真实站点跑测试。

## 入库后必跑体检

```powershell
.\tools\python\python.exe .\scripts\audit_corpus.py --strict
```

知识层改动后（改了 `knowledge/seed*.yaml`）：

```powershell
.\tools\python\python.exe .\scripts\load_knowledge.py            # 先干跑，证据必须 100% 命中
.\tools\python\python.exe .\scripts\load_knowledge.py --apply
.\tools\python\python.exe .\scripts\export_entity_cards.py --apply
```

只读，输出到 `exports/obc-evaluation/audit/`：

| 文件 | 内容 |
|---|---|
| `audit-summary.md` | 总览、字段覆盖率、Top 15 需复核重复块 |
| `findings.csv` | 全部 ERROR / WARN |
| `suspect-pairs.csv` | 文档对共享台词数、**最长连续雷同块**、风险等级 |
| `duplicate-lines.csv` | 同一句出现在多篇文档的台词 |
| `empty-docs.csv` | 正文少于 100 字的文档 |
| `field-gaps.csv` | 缺失版本/地区/日期的文档 |

- `--strict`：出现 ERROR 时退出码 1，可接 CI；WARN 只是复核线索。
- 高风险 = 跨地区 + 连续 ≥8 句雷同。**不等于错误**：同角色洞天对话在不同频道重复收录、
  系列任务共用台词都会命中，需要人工判定。
- 回归测试：把有问题的历史文档放进临时目录，用
  `--corpus <dir> --no-db --out-dir <dir>` 验证能否抓出该文档对。
- `load_markdown.py` 与体检脚本共用 `corpus_rules.py`；改元数据行规则时两边一起改。

