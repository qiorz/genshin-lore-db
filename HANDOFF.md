# 交接文档 · 原神世界观数据库

> 更新时间：2026-11-05  
> 项目根目录：`D:\harn\2\genshin-lore-db`  
> 一句话状态：**正文层已收齐（书籍、任务、散落文本、角色、武器、圣遗物、活动、观景点、物品、官方公告、NPC 对话），共 7,734 篇、453,939 段，可从 Markdown 全量重建；成就只做 CSV。P0 自动质检、P1 筛选可用性、P2 知识层三批种子均已落地：400 实体 / 434 个名字（含 34 个别名）/ 106 关系 / 233 说法 / 61 条时间线 / 764 条实体出处，全部可点回原文段落，**400 个全部复核完毕**。原 Web UI 搜索结果零改动。剩下漫画、PV、七圣召唤牌面文本，以及按队列复核剩余 340 张扩量卡片。**

---

## 0. 变更记录

主要改动在 2026-11-04：第 0 步把正文收进 `corpus/`，第 1 步收任务尾巴，第 2 步武器与圣遗物，
第 3 步活动与成就，第 4 步地理，第 5 步材料/食物/动物/道具，第 6 步官方公告与 NPC 对话；
2026-11-05 补了 Web UI 启停脚本、校对了 `quest.obc.5299`，并落地 P0 自动质检、
P1 筛选可用性、P2 知识层四批种子。下面按倒序排列。

### 第 19 步 · 400 张全部复核完成（2026-11-05）

从 30 张核到 400 张，共四轮。人工判断的部分不多，**大量时间花在修生成端**——
因为同一类错误会重复出现在几十张卡上，逐张改不如改规则。

| 问题 | 表现 | 修法 |
|---|---|---|
| 锚点是页面小标题 | 沃雅妮莎的「在演出准备室中的自言自语」 | `looks_like_heading()`：无标点无引号的短句不算证据；角色页找不到就退回全库 |
| 锚点来自版本补丁 | 深渊咏者取自「2.6 更新说明·新增副掉落物」 | 公告文档不进实体证据池；**事件/节庆例外**（它们的出处本就是版本公告） |
| 锚点是攻略文本 | 圣火竞技场的「获取方式：…箱子上」 | 噪声词加「获取方式/宝箱/合成台/刷新时间」 |
| 主锚点排序不当 | 提瓦特首条是杂志标题；原初首条是「原初一滴」 | 原词括注 > 无括注 > 更长词前缀；再看标题是否在讲它、句子长短 |
| 一词两义 | 「龙王」= 北斗的江湖称号 / 元素龙王 | 拆为元素龙王，旧实体剪枝 |
| 泛称被当人名 | 「主持人」「浮游水蕈兽·元素生命」进了 NPC | 加入说话人黑名单，按台词量补两个真 NPC |

还有两个**幂等判定**的坑（都被这次复核暴露）：

1. `build_stage4.py` 用「上一次 seed 的 id」当白名单，导致上一版删掉的实体
   永久判为「库里已有」——碧水原因此丢失。改成「库里 id − 前三批 seed 的 id」。
2. `enrich_evidence.py` 只在「补足」有变化时写盘，纯重排不落盘，改了半天没生效。

最终：**400 / 400 reviewed**，`entity_evidence` 758 条，关系 106，claims 233。

### 第 18 步 · claims 从 10 补到 233（2026-11-05）

claims 是「谁在什么立场下说了什么」。原来看起来难做，是因为库里 `sections.speaker`
是空的——导入时按标题切段，把「说话人 → 若干段话」的结构拍平了。
但**原始 Markdown 里的署名还在**，直接从那儿读就行。

| 项 | 结果 |
|---|---|
| `scripts/mine_claims.py` | 读 `corpus/characters/**/*.md` 的 `## 角色关联语音` 段，按空行切块；独立成行、无标点、≤8 字的行 = 说话人；其后段落 = 他的话 |
| 主语判定 | `【关于X·主题】` → 主语 X、谓词=主题；其余段落 → 主语=本页角色、谓词=评价 |
| 过滤 | 普通段落必须**提到主语**且带评价词，否则是闲话；同主语同说话人同开头去重 |
| 结果 | claims 10 → **233**，覆盖实体 10 → **65**；全部解析到 `section_id` |
| 置信度 | 这批评分统一为 `likely`——它是**某个角色的说法**，不是旁白定论；`perspective` 记说话人 |

典型一条：主语「芙宁娜」、谓词「评价」、视角「钟离」——
「与『自我』签订下拯救国家的契约，并严守五百年，最终骗过了天理…」。

顺带修了展示：说法在卡片上截到 110 字（全文在原文里），状态改中文（open→待定），
否则一条长语音就把整张卡撑爆。

### 第 17 步 · 关系边与别名（2026-11-05）

400 张卡里只有 22 个实体有边、34 个别名——卡铺开了，图还是空的。这一步补这两块。

| 项 | 结果 |
|---|---|
| `scripts/mine_relations.py` | 人物→组织 60 条、地点→国家 9 条、组织→国家 2 条，共 **63 条**新边；关系总数 43 → **106**，有边的实体 22 → **81** |
| 判据 | 同一句里两个实体不重叠共现 + 跨度 ≤16 字 + 中间只有连接词或明确职务词；地点/国家只认相邻句式（`X位于Y`、`Y境内的X`、`Y的X`），不靠距离猜 |
| 人工复核 | 81 条人物候选里剔掉 26 条，逐条写明理由（「千岩军要抓捕辛焱」不是辛焱属千岩军；「拉拢她加入花羽会」是尚未加入） |
| `scripts/mine_aliases.py` | 严格规则（「别名」正名相邻）只挖出 11 条，说明多数别称不写成引号形式；改为**人工词表 + 语料校验**（每个别称在库里出现 ≥2 次且与正名同篇共现） |
| `scripts/apply_aliases.py` | 复核后写入对应 seed 的 `aliases`；只收有辨识度的称号，**「女仆」「堂主」「宫司」这类职务词一律不收**——搜出来命中一大片，反而降低检索质量 |
| 别名 | 34 → **59** 条，有别名的实体 26 → **48**。搜「岩王爷」直接落到钟离 |

三个踩过的坑：

1. **国家名是地点名的子串**：`蒙德 ⊂ 蒙德城`，最初「前往蒙德城」被当成「蒙德城位于蒙德」的证据。
   现在共现检测会排除重叠区间。
2. **一句里并列多个国家**：「地处蒙德璃月的交通要道」分不清归属，整句弃用。
3. **否定句**：「挪德卡莱不属于蒙德」「并不隶属于枫丹司法体系」——出现否定词直接跳过。

关系 id 用 7000 段（人工 2000 段、事件参与 5000 段之外），种子写在 `seed-stage6.yaml`。

### 第 16 步 · 「176 篇提及，只有 1 条原文？」（2026-11-05）

用户点开「记忆」发现：复核队列说它被 176 篇任务提及，卡片上「关联原文」只有 1 条。
两个数字都没错，但页面只显示了后者，等于让人无法对账——这是**显示缺陷**，不是数据缺失。

| 问题 | 处理 |
|---|---|
| 页面上只有锚点数，没有提及数 | 详情页新增「全库提及 N 篇（任务 M 篇 / 共 K 段）」+「检索这些原文 →」链接；说明文字写清「这里只列锚定出处」 |
| 一张卡只存 1 条锚点 | 第五批的高频实体改成最多 3 条（不同文档各一句），主锚点排第一；`entity_evidence` 用 `is_primary` 区分 |
| 第三批仍是 1 条 | 新增 `scripts/enrich_evidence.py`，给指定种子的非人物实体补到 3 条；实体集合、id、描述都不动 |
| 锚点选得不准 | 「记忆力」「记忆感」这类构词被当成「记忆」：加后缀黑名单；原文写作「记忆」的句子加权最高 |

结果：`entity_evidence` 403 → **764**，145 个实体有 2–3 条锚点。
「记忆」现在显示 3 条真正把它当专名的原话（「记忆」被滋养，所以有「生命」/ 提瓦特的地脉中流淌着「记忆」…）。

> 教训：图谱类界面里，「我们收录了几条」和「原文出现了几次」是两个概念。
> 只显示前者，用户会以为后者是数据缺失；只显示后者，又会让人以为每条都建了卡。两个都得给。

### 第 15 步 · 第五批：实体收尾到 400（2026-11-05）

用户要求「把实体扩充完毕」，按第 13 步定的上限 400 收尾。

| 来源 | 做法 | 结果 |
|---|---|---|
| NPC 人物 | 靠 `sections.speaker` 统计台词量：≥50 段且库里没有的，按台词量取前 66 个。台词多说明剧情分量足，比词表靠谱 | 66 个（婕德、泽维尔、卡特皮拉、兰罗摩、凯瑟琳、萍姥姥、哲平…） |
| 概念 | 候选表 + 库内证据，**剔除泛用词**（契约/仪式/血亲/祭司/誓约/圣遗物/神谕/梦境/花海/终末）——这些在几乎任何一句话里都能命中，收进来只是稀释 | +34 → 43 |
| 生物 | 同上（深渊法师、遗迹猎者、兽境猎犬、蕈兽、无相之雷、雷音权现…） | +23 → 29 |
| 神明 | 芙卡洛斯、厄歌莉娅、奥赛尔、跋掣、花神、赤王、盐神、尘之魔神 | +8 → 14 |
| 组织 | 愚人众执行官、八重堂、万民堂、不卜庐、神里家、九条家、幕府、执律庭 | +8 → 35 |
| 事件/节庆 | 海灯节、风花节、逐月节、光华容彩祭、三界路飨祭、眼狩令、锁国令、坎瑞亚灾变… | +18 → 18 |
| **合计** | | **400**（character 191 / location 62 / concept 43 / organization 35 / creature 29 / event 18 / deity 14 / nation 8） |

`entity_evidence` 253 → **403**，全部解析到 `section_id`；`entity_names` 434（400 本名 + 34 别名）。

**两个新工具**（这一批踩坑的产物）：

- `load_knowledge.py --prune`：剪掉「库里存在但任何种子都没有」的实体。
  上一批改候选表后，被删的 7 个泛用概念仍留在库里，`--prune` 一次清掉。
- `scripts/prune_cards.py`：用 YAML 解析 front matter，删掉过期卡与同 id 多目录的重复副本。
  起因：`枫丹科学院` 从地点改组织后，旧目录那份卡没被删，页面能搜到两张。

> 教训：用 `python -c` 跑含 `\s`/`\S` 的正则时，反斜杠会被 shell 吃掉，
> 于是「重复 0 张」的假阴性差点放过一张重复卡。现在这类检查一律写成脚本文件、用 YAML 解析。

原搜索仍 **22,229 字节**；`audit_corpus.py --strict` ERROR 0 / WARN 63；`integrity_check` ok。

### 第 14 步 · 复核队列与状态机制（2026-11-05）

220 张 draft 平铺着看不完，所以先解决「先看哪些」和「看完记在哪」两个问题。

| 动作 | 结果 |
|---|---|
| `scripts/review_queue.py` | 按「出现在多少篇**任务**正文里」再按「多少篇文档」排序——被越多任务引用的实体，类型或名字写错的代价越大；同时做三项机械校验（引文是否真在那一篇、引文是否含名、人物类型是否与角色页一致） |
| `knowledge/review-state.yaml` | 复核结论单独存一份，**不写进脚本生成的 seed**（重新生成会覆盖）。`load_knowledge.py` / `export_entity_cards.py` 读它覆盖状态，改动一条命令即生效 |
| 报告 | `exports/review/entity-review-queue.md`（前 N 条带原话）+ `.csv`（全部 190 条） |
| 首轮结果 | 按队列核了前 30 张，标记 reviewed；剩余 190 张按同一口径继续 |

### 核这 30 张发现的三类问题（都已修）

1. **分类错**：`枫丹科学院` 原按地点生成——它是机构，改为 `organization`。
   生成脚本当时把同名候选按「首次出现的分类」保留，地点在前就被当成了地点。
2. **描述暗示归属**：第三批写成「证据出自{region}地区文档的人物条目」。
   话虽属实，但枫丹的证据恰好出自一篇纳塔文档，读起来像在说「枫丹属于纳塔」。
   已改为纯分类标签「国度条目（第三批扩量…）」，地区信息保留在证据链接里（67 条一并修正）。
3. **引文不像人话**：`▌空月归乡 · 哥伦比娅…` 这类版式标题、`…会说：` 这类引出下文的提示句被当成了证据。
   已加过滤：`▌`/`【` 开头、以冒号结尾、含「过场动画」「时说的话」。

### 生成脚本可重跑了

`build_stage4.py` 原先用「库里已有同名实体」判重，导致**重跑时全部跳过**，
连分类写错也改不了（一度把 `seed-stage4.yaml` 覆盖成 0 条，靠 `git checkout 9b8786e` 恢复）。
现在改为读上一次的 `seed-stage4.yaml` 拿 id 白名单：本批自己的 id 不算「已存在」，重跑结果稳定。

> 教训：生成脚本必须能对**自己的产物**幂等，否则「重新生成」等于「清空」。

### 第 13 步 · P2 第四批：实体扩到 250（2026-11-05）

用户先要一个「最终做多少」的数字，定 400；再要求「先扩这么多」，即里程碑 250。
这一批换了做法：**第三批是挖候选，这批是收权威名单**。

| 动作 | 结果 |
|---|---|
| `scripts/build_stage4.py` | 角色不再靠词表猜——`doc_type='character'` 的 136 篇角色页就是权威名单，一篇一人；同名去重、跳过「旅行者·元素」变体（同属 `entity.traveler`）、跳过库里已有名字（温迪/钟离/纳西妲/雷电影已是 deity） |
| 地点/组织 | 候选表只给名字，**收不收由库里有没有真实句子决定**；落空的进 skipped，不硬塞。47 个地点 + 15 个组织全部命中（`枫丹科学院` 同时出现在两类里，按首次出现的 location 保留） |
| 描述口径 | 角色用 `manifests/character-index.csv` 的**游戏内标注**（地区 · 元素 · 武器 · 星级），其余用中性分类标签「地点条目 / 组织条目」，不写剧情结论 |
| 引文切分修正 | 直接按 `。` 切句会把「…。」——某人 切成两半，证据以 `」` 开头。改为**跟踪「」『』括号深度**再切，并过滤「过场动画」「【纯标题】」这类旁白/标题行 |
| 结果 | 100 → **250**：character 37→125、location 16→63、organization 11→26，concept/nation/creature/deity 不变；`entity_evidence` 103→**253**，全部解析到 section_id |
| 幂等 | 全部固定主键，重跑 `load_knowledge.py --apply` 行数不变；卡片 250 张由 `export_entity_cards.py` 重新导出 |
| **原搜索零改动** | `/` 与 `/search` 代码本轮未动；`/?q=巴巴托斯` 仍是 **22,229 字节**，与上一轮基线逐字节相同 |
| 质量门 | 250 份卡片 YAML 解析 0 失败、entity_id 无重复；`audit_corpus.py --strict` ERROR 0 / WARN 63；`integrity_check` ok |

需要 `pypinyin` 生成中文名 → `entity_id`（`entity.ban-ni-te`）。没装时会退回文档号兜底，
因此它只是**生成脚本**的依赖，不影响灌库与 Web UI 运行。

### 第 12 步 · P2 第三批：实体扩量到 100（2026-11-05）

用户要求「实体多扩一些，先到 100」。扩量不等于乱收：新实体全部由 `corpus/` 真实段落驱动，
描述只写中性分类标签，不写剧情结论。

| 动作 | 结果 |
|---|---|
| `scripts/mine_entities.py` | 从词表 × 真实段落反查候选，按文档类型打分（任务/书籍/角色 3 分，公告 −3 分），噪声词扣分、名字出现在段首加分；输出 `knowledge/entity-candidates.csv` 供人过目。单字「空」会误命中「空虚」，已剔除；别名只收同段共现（皇女/博士/丑角/仆人/战争之国 5 个） |
| `knowledge/seed-stage3.yaml` | 70 个新实体（`status: draft`），每个都有 `doc_id` + 原话，干跑 **147/147 证据命中** |
| 种子改为多批 | `load_knowledge.py` / `export_entity_cards.py` 改成 glob `knowledge/seed*.yaml`，以后加批次不用改脚本 |
| **新表 `entity_evidence`**（迁移 `005`） | 之前实体出处只活在 YAML 和生成的 Markdown 里，没进库，详情页「关联原文」对 70 张新卡全显示 0。现在逐句入库 **103 条**（100 个实体，section_id 全部解析成功），详情页带原话可点回原文；与 `claims` 分开——`claims` 是带视角的断言，这里只回答「原文提到过它」 |
| Web UI | `/entities` 去掉 50/60 条上限（300 个实体也不会截断）、加类型下拉、统计行改为实时查询、新卡标「待复核」；`/api/entities` 同步 |
| **原搜索零改动** | 同库对照：`git show HEAD:webui/app.py` 跑在 8766，3 组 `/api/search`（钟离/天空之琴/纳西妲）与新版输出**完全一致**；`/?q=巴巴托斯` 整页 22,229 字节**逐字节相同**（`cmp` 无差异） |
| 质量门 | 100 份卡片 YAML 解析 0 失败、entity_id 无重复；`audit_corpus.py --strict` ERROR 0 / WARN 63（仍是已知的「洞天 vs 角色彩蛋」频道冗余，非串内容）；`integrity_check` ok |

已知遗留：70 张扩量卡片是半自动产物，`status=draft`，别名与出处可信但描述需人工抽样复核。


### 第 11 步 · P2 第二批：关系 / 时间线 / 正式卡片（2026-11-05）

第一批 30 实体 + 10 说法经用户校对通过（`seed.yaml` 的 `status: reviewed`）。
本批按既定方向往下铺，仍遵守「卡片是额外增加，原搜索零改动」。

| 动作 | 结果 |
|---|---|
| `knowledge/seed-stage2.yaml` | 26 条人工关系边 + 8 个提瓦特纪年事件 + 53 个现实版本上线（从公告自动生成，不手写）；每条证据仍是 `doc_id + 短引用`，干跑 **77/77 命中** |
| `scripts/load_knowledge.py` | 扩展为读两个 seed；写入 `entity_relations=43`（含 17 条事件参与）、`events=8`、`event_sources=8`、`timeline_entries=61`；全部固定主键、幂等复跑行数不变 |
| 两条时间线分开 | `era=release`（53 条官方公告上线日期，`certainty=exact`）与 `era=teyvat`（8 条，只有相对先后，约数不写成绝对年份）**严格不互相换算** |
| `scripts/export_entity_cards.py` | 把种子导出成 50 份便于人读的 Markdown：30 实体 / 10 说法 / 8 事件 / 2 时间线，按 `knowledge/README.md` 的模板分类落盘。**生成物，不要手改** |
| Web UI | 新增 `/entity/<id>` 详情页（关系出边/入边、说法置信度、相关时间线、关联原文）与 `/timeline`（两区块）、`/api/entity`、`/api/timeline`；导航加「时间线」 |
| **原搜索零改动** | 用 `git show HEAD:webui/app.py` 在 8766 端口跑旧版逐字对比：3 组 `/api/search` 输出完全一致，`<section class="results">` 13,693 字符完全一致；`git diff` 涉及 `result-card` 的行 0 行 |

关系置信度同样不统一：NPC 语音、角色叙述、编校判断分别标 `likely`，
「教令院推行虚空」用 `operated_by` 而非 `created_by`（原文未直述发明者）——
按「先有证据，再写结论」不把推测写成定论。
`audit_corpus.py --strict` 仍 ERROR 0，`integrity_check` ok，正文层 7,734 / 453,939 未变。

### 第 10 步 · P2 第一批知识层种子（2026-11-05）

用户约束：**卡片是额外增加，原文搜索结果样式必须原样保留**（有时要找的就是原文某一句话）。

| 动作 | 结果 |
|---|---|
| 复用已有表 | `entities / entity_names / claims / entity_relations / events / timeline_entries` 等 11 张表早在 `schema.sql` 里、此前全为 0；本轮不建表，只按规范填数据 |
| `knowledge/seed.yaml` | 30 个核心实体（神明 / 人物 / 组织 / 国家 / 概念）+ 29 个别名 + 10 条 claims；每条证据都是库里真实存在的台词或旁白 |
| `scripts/load_knowledge.py` | 灌库脚本。证据**不硬编码 section_id**（全量重导后会变），只写 `doc_id + 短引用`，灌库时现场解析；查不到就报错，不静默跳过。干跑 43/43 证据命中 |
| 独立入口 | 新增 `/entities` 与 `/api/entities`；导航加「实体卡片」；搜索页底部加**默认折叠**的「相关实体」提示区 |
| **原搜索零改动** | 与 P1 版逐字对比：`/api/search` 两组查询输出完全一致，`<section class="results">` 区块 13,693 字符完全一致；只多了导航链接与底部折叠区 |

数据：`entities=30 / entity_names=59 / claims=10`，10 条 claims 全部挂上真实 `section_id`。
置信度故意不统一：`confirmed`（温迪即巴巴托斯）、`likely`（角色视角的解释）、
`speculative`（雷电影与雷电将军人偶须区分，编校判断）、`disputed`（芙宁娜是水神，剧情后被推翻）。
这是「矛盾是数据，不是错误」的示范，也避免把角色的一句话包装成定论。

**刻意没做（当轮）**：没自动生成全量知识图谱，没动 `entity_relations` / `timeline_entries`，
没把种子拆成正式实体 Markdown。等这批卡片人工校对、确认方向后再铺 —— 已于第 11 步完成。
报告 `exports/obc-evaluation/knowledge-seed-report.md`。

### 第 9 步 · P1 让筛选真的可用（2026-11-05）

| 动作 | 结果 |
|---|---|
| 版本推导 | `enrich_release_versions.py`：用 1.1→7.2 共 53 篇官方版本更新说明的上线日期构成时间线，给 2 篇活动公告推出 6.7 / 7.1，标 `official` / `inferred`，`notes` 留依据；**不新增枚举值**，避免改 DB 的 CHECK 约束 |
| 版本归一化 | `normalize_version_labels.py`：70 篇非标准值 → 52「月之X」映射 6.0–6.7、15 多版本书籍取最早版本、1 个区间取起始、2「常驻」玩法标签移出 version；**原值全部写进 notes** |
| 重导 | 72 篇（2 + 70），front matter 全通过；DB 里非 `X.Y` 的版本值现为 **0** |
| Web UI | 新增字段覆盖率面板与 `/api/coverage`；版本输入改下拉 + 前缀精确匹配；按地区/版本筛选时提示排除多少未标注文档；剧透筛选下线（全库仅 10 篇分级）；空值显示「未标注」 |
| 回归 | `audit_corpus.py --strict` 仍 ERROR 0；`/`、`/about`、`/api/coverage`、各筛选组合全 200 |

**为什么覆盖率没涨**：地区空 3,041 篇全是物品 / 武器 / 圣遗物 / 活动 / 公告——
这些类型本来就没有地区字段；版本空值同理，是上游无数据。
剧情类（任务 / 书籍 / 角色 / 散落文本 / 观景点 / NPC 对话）地区 **100% 已标注**。
所以 P1 的重点是**把筛选边界讲清楚**，不是把数字填满。
版本覆盖率 25.4%（1,965/7,734）没变，但值已全部可用：按 `6.0` 筛选不会再漏掉「月之一」的文档。

清单：`manifests/metadata-enrichment.csv`、`manifests/version-normalization.csv`。

### 第 8 步 · P0 自动质检（2026-11-05）

| 动作 | 结果 |
|---|---|
| 新增 `scripts/audit_corpus.py` | 5 类只读检查：front matter / corpus↔DB 对账 / 跨文档重复与**连续雷同块** / 字段覆盖 / 短正文；输出 5 份 CSV + 摘要 |
| 新增 `scripts/corpus_rules.py` | 结构性元数据行识别 + 台词归一化，导入器与体检共用同一套规则 |
| 改 `load_markdown.py` + 全量重导 | `- 类型：` 等元数据行不再写进 sections/FTS；先备份 DB，按原分词模式分两组重导 |
| 回归验证 | 取 Git 历史里**修复前**的 5299，脚本自动标 `high`：与 533 共享 55 句、30 句连续雷同、须弥/蒙德跨地区 |
| 首份体检 | 7,734 篇、ERROR 0；5,068 组跨文档重复台词、455 对疑似、63 对跨地区连续雷同；短正文 3,090 篇（其中任务 75） |

**重导结果**：文档 7,734 篇与正文 13,306,758 字符不变，段落 458,726 → **453,939**
（少了 4,787 个元数据段），FTS 行数与 sections 一致，`integrity_check` 与 FTS
`integrity-check` 均通过，各类型分词模式保持不变。

**体检发现（待人工判定）**：63 个高风险里绝大多数是「洞天」与「角色彩蛋」两个频道
重复收录同一段角色洞天对话，属真实冗余；公告补偿/版权模板句在 50 篇里重复是已知取舍。
完整报告 `exports/obc-evaluation/audit/audit-summary.md`。
**以后每次入库后跑**：`.\tools\python\python.exe .\scripts\audit_corpus.py --strict`。

### 第 7 步 · 启停脚本与 5299 校对（2026-11-05）

| 动作 | 结果 |
|---|---|
| Web UI 启停 | `start.ps1` 改后台常驻（幂等/自检/PID），新增 `stop.ps1` 与两个 `.cmd` 双击入口；`app.py` 加 `--log-file`；提交 `4fa66ee` |
| **校对 5299** | **第三章 第二幕「千朵玫瑰带来的黎明」的 `## 尾声` 整段是蒙德序章第三幕内容，已用 OBC 原始快照重填** |
| 根因 | `render_quest` 不认 `collapse_panel` 剧情 → 误判 OBC 无正文 → BWiki 补全时短名「尾声」错配到「尾声的尾声」 |
| 防再犯 | `fill_quests_from_bwiki.py` 短名（≤3 字）必须精确匹配、加 `MANUAL_REVIEW` 保护；删除错配缓存 |
| 排查 | 177 篇补全文档全扫，23 组「节标题 ≠ 来源页」，除 5299 外无整篇串入；详见 `exports/obc-evaluation/quest-5299-proofread.md` |

修复后文档 1,201 段 / 38,495 字符；全库 7,734 篇 / 453,939 段 / 13,306,758 字符，`integrity_check` ok。

### 第 6 步 · 官方公告与 NPC 对话

| 动作 | 结果 |
|---|---|
| 抓取 | NPC 三频道 2,525 个 entry 全部落盘（断点续跑补最后 883 条，3 并发） |
| 公告原始 | 米游社官方账号 53 篇 `getPostFull` + 游戏内公告 API 当前窗口 29 条 |
| 渲染器 | `render_obc.py` 新增 `render_npc`；新建 `scripts/render_npcs.py`、`scripts/render_notices.py` |
| 公告归档 | `corpus/notices/` 55 篇：53 篇版本更新说明（1.1→7.2 连续）+ 2 篇活动公告 |
| NPC 归档 | `corpus/voices/` 2,401 篇：NPC 对话 2,275 / 角色逸闻 62 / 角色彩蛋 64 |
| 跳过清单 | `manifests/notice-skip.csv` 27 条、`manifests/npc-skip.csv` 124 条 |
| 入库 | 文档 5,278 → 7,734，段落 358,452 → 458,736，正文约 1,330 万字符 |

**公告**：米游社 53 篇覆盖 1.1 到 7.2 无断档，版本/上线日期都来自帖子里，不猜；
6.x 用「月之一…月之八」映射 6.0…6.7。正文按 `verbatim` 保留，只去图片与表格，
补偿/更新时间等运营段落仍在文中——**定位是版本时间线佐证，不作叙事正文统计**，取舍写在每篇 `notes`。
游戏内公告 29 条里 27 条跳过：运营类、与米游社重复、纯图片无正文。

**NPC 对话**：只收 `interactive_dialogue` 对话图、`秘闻馆情报`、`好感套装对话`、
`赠礼对话`、`逸闻纪事·X` 的名称/简介；商品列表、奖励、挑战规则、地图、生日邮件一律不收。
洞天/赠礼对话节点里混有「语音汉语/英语/日语/韩语：[当前音频暂无文件名]」占位行，
渲染时按行剔除。地区来自频道列表 `ext.filter`，「诺德卡莱」统一为「挪德卡莱」；
频道没有版本字段，`version` 全部不写。124 条无可提取对话，逐条进 `npc-skip.csv`。

**顺手修了 Web UI**：`TYPE_LABELS` / `TYPE_ORDER` 原先只写死 4 类，
现在覆盖全部 12 种 `doc_type`，新增的 `notice` / `voice` 在筛选下拉里能正常显示。

### 第 5 步 · 材料 / 食物 / 动物 / 道具（P3）

| 动作 | 结果 |
|---|---|
| 抓取 | 四个频道共 2,622 条 entry（食物 325、材料 2,058、动物 227、道具 12） |
| 渲染器 | `render_obc.py` 新增 `render_item`；`scripts/render_items.py` 批量 + 索引 |
| 归档 | `corpus/items/<子类型>/` 2,622 篇，`index.csv` 2,622 行 |
| 入库 | 文档 2,656 → 5,278，段落 344,303 → 358,452 |

**只收描述**：`material_base_info.attr["描述"]` 与 `good_desc` 的「背景故事」；
用途、分布、使用效果、配方、获取方式、分布面板全部丢弃。
食物页的三个品质变体（奇怪/正常/美味）各成一节；12 组同名材料用 ` (obc-<content_id>)` 消歧。
**版本全部 unknown**：OBC 物品频道没有版本字段，BWiki 材料页也没有统一 `实装版本`，按约定不猜。

**修掉一个统计 bug**：`render_items.py` 原来用 `body[6:]` 判断「有无正文」，
但单小节物品的 `## 描述` 恰好落在索引 5，导致 1,028 条材料被误判为空、只归档 833 条。
改为「除固定的 `## 物品信息` 外是否还有别的小节」后，2,622 条全部通过。
`render_events.py` 有同样写法（活动因固定 3–4 行信息碰巧没触发），已一并改成稳妥判断。

### 第 4 步 · 地理与观景点（P3）

| 动作 | 结果 |
|---|---|
| 观景点 | 264 篇 → `corpus/geography/观景点/<地区>/`，10 个地区 |
| 区域 | 71 个区域**无正文**，做成 `manifests/regions.csv`（790 行） |
| 入库 | 文档 2,392 → 2,656，段落 343,464 → 344,303 |

区域页模块里只有地图、系列任务、怪物/素材/机关列表，没有一句散文，因此没有硬塞进正文层。

### 第 3 步 · 活动与成就（P2）

| 动作 | 结果 |
|---|---|
| 抓取 | 活动 275 + 成就 1,626，共 1,901 个 entry（2 并发，总量仍 1 请求/秒） |
| 活动归档 | **47 篇**有叙事内容 → `corpus/events/游戏活动/`，版本来自频道 ext，47/47 |
| 活动跳过 | 228 条写成 `manifests/event-skip.csv`，全是公告/纪行/赛季页 |
| 成就索引 | **1,558 条** → `manifests/achievements.csv`（名称/描述/成就集/版本/隐藏/每日委托） |
| 入库 | 文档 2,345 → 2,392，段落 339,809 → 343,464 |

**为什么活动只有 47 篇**：活动页的剧情本体是 `event` 任务，早就收在 `corpus/quests/event/`（288 条）；
活动页本身只有简介、规则、奖励。47 篇是确实带活动简介或彩蛋对话的那部分。

**成就不进正文层**：1,558 条只做 CSV。理由：单条只有一句描述，做成 1,558 个 Markdown 会稀释正文层，
但它是很好的版本/事件索引。

### 第 2 步 · 武器与圣遗物（P1）

| 动作 | 结果 |
|---|---|
| 抓取 | OBC 武器 252 + 圣遗物 63，entry_page 全部落 `raw/`（此前只抓了频道列表） |
| 渲染器 | `render_obc.py` 新增 `render_weapon` / `render_artifact` |
| 归档 | `corpus/weapons/<武器类型>/` 252 篇，`corpus/artifacts/` 63 篇 |
| BWiki 对照 | 315 条全部找到同名页，版本 315/315 补齐；244 条故事与 OBC **完全一致** |
| BWiki 补缺 | `星锋剑` OBC 故事原文为「暂无」，用 BWiki 补全并挂第二条 source |
| 入库 | 文档 2,030 → 2,345，段落 329,859 → 339,809 |

**只收叙事**：武器取「装备描述（`<hr>` 之后）+ 相关故事」，圣遗物取五个部位的「描述 + 故事」；
精炼数值、属性、套装效果、推荐角色全部丢弃。

两个上游毛病记在 `corpus/artifacts/README.md`：
- 4 套「祭X之人」在 OBC 与 BWiki 都只有 `理之冠`，其余部位是空占位；
- 部分圣遗物页面模块名为空，部位名在 `name.key` 里，渲染器已做回退。

### 第 1 步 · 收任务尾巴

| 动作 | 结果 |
|---|---|
| 修复散落文本空白页 | `render_obc.py` 支持「根节点缺失」的对话图，12 篇从 0 字恢复到 113–4300 字 |
| 重分类 | 19 条邀约 → `hangout`，4 条间章 → `interlude`，目录不再空 |
| 系列页标注 | 15 篇标题含「系列/合集/总览」的页 + 3 篇海灯节，加 `tags: [系列任务]`，共 18 篇 |
| 同名同文合并 | 好东西，坏品味 5→1、通知【明蕴镇】 2→1，来源并入主文档，删除冗余 5 篇 |
| 重复组判定 | 剩余 10 组逐组写判定，见 `manifests/duplicates.csv` |
| BWiki 补空壳 | 32 条探测完毕：BWiki 无可用正文，**0 条补全**，见 `exports/obc-evaluation/bwiki-stub-probe.md` |
| 修工具 | `fill_quests_from_bwiki.py` 删除「匹配不到就取第一条」的回退（4190 事故根因） |

**数量变化**：文档 2,035 → 2,030（合并 5 篇），段落 330,417 → 329,859，正文字符 7,322,802 → 7,303,488。
减少的部分全部来自重复合并，没有丢内容；散落文本反而新增了 12 篇被修复的正文。

**未做**：32 条空壳仍然补不了（上游没正文）；「一篇一幕」审计只做到系列页标注，没有拆分多幕文件。

### 第 0 步 · 把正文收进 corpus

这次只做一件事：**让 `corpus/` 成为真正完整、可重建的权威正文层**。之前 706 条散落文本和 50 条任务只存在于 `exports/` 和 SQLite 里，一旦重装库就会丢。

#### 做了什么

| 动作 | 结果 |
|---|---|
| 备份数据库 | `db/backup/genshin_lore-20261104-121411.sqlite3`（244 MB，校验 2,035 篇 / 330,417 段 / integrity ok） |
| 初始化 Git | 基线提交 `cb9647f`，仓库 36.95 MiB；`db/`、`tools/`、`logs/` 不进版本库 |
| 迁移散落文本 | 706 条 → `corpus/scattered/<地区>/`，新建 `index.csv`（706 行） |
| 迁移有正文任务 | 19 条 → `corpus/quests/<subtype>/`（原先误留在 exports 的「待补」，其实有正文） |
| 隔离空壳任务 | 31 条 → `corpus/quests/_pending/` |
| 更新任务索引 | `corpus/quests/index.csv`：1,051 → 1,069 行 |
| 重导入 | 只重导这 756 篇，未做全量重建 |

### 验证结果

重导入后与迁移前**逐篇一致**：

```text
文档：2,035（不变）
段落：330,417（不变）
正文字符：7,322,802（不变）
每篇 section 数：diff 无差异
normalized_path 指向 exports 的文档：0
PRAGMA integrity_check：ok
```

### 顺手修了两篇坏数据

这两篇是历史 BWiki 补全/合并脚本留下的，不是迁移造成，但重导入会如实反映，所以必须修：

1. **`quest.obc.500835 云云椒椒`**：文件正文被覆盖成「赤望所居，锦落云程」的内容（front matter 还挂着 500835 的来源）。已用 `raw/` 原始快照重新渲染恢复，6,495 字，332 段。
2. **`quest.obc.4190 邀约事件·久岐忍 第一幕`**：OBC 页面本身 0 剧情模块；BWiki 补全时匹配到错误页面，把凝光/云堇/加尔恰等其他邀约的整篇文本塞了进来，**里面没有一句久岐忍**。已回退为 OBC-only 空壳，移入 `_pending/`，等正确页面重补。

### 新增的 Git 约定

- `.gitattributes` 把 `raw/**` 标为 `binary`：`raw/**/meta/*.json` 记录了响应体 `sha256`，若 Git 做 CRLF→LF 转换，重新检出后哈希就对不上，破坏「原始快照不可变」。
- `corpus/**` 仍是 `text eol=lf`，换行符统一不影响正文语义。

---

## 1. 现在到哪一步

| 模块 | 数量 | 状态 |
|---|---:|---|
| 书籍 | 92 | 已归档 `corpus/books/` |
| 散落文本 | 705 | 已归档 `corpus/scattered/<地区>/` |
| 任务（有正文） | 1,065 | 已归档 `corpus/quests/<subtype>/` |
| 任务（空壳） | 32 | 隔离在 `corpus/quests/_pending/` |
| 角色 | 136 | 已归档 `corpus/characters/` |
| 武器 | 252 | 已归档 `corpus/weapons/<类型>/`，版本 252/252 |
| 圣遗物 | 63 | 已归档 `corpus/artifacts/`，版本 63/63 |
| 活动 | 275 | 47 篇有叙事，已归档 `corpus/events/`；228 条见 `event-skip.csv` |
| 观景点 | 264 | 已归档 `corpus/geography/观景点/<地区>/` |
| 区域 | 71 | 无正文，做成 `manifests/regions.csv`（790 行） |
| 材料 | 2,058 | 已归档 `corpus/items/材料/` |
| 食物 | 325 | 已归档 `corpus/items/食物/`（含三品质变体） |
| 动物 | 227 | 已归档 `corpus/items/动物/` |
| 道具 | 12 | 已归档 `corpus/items/道具/` |
| 成就 | 1,626 | 1,558 条入 `manifests/achievements.csv`（不进正文层） |
| 官方公告 | 82 | 55 篇已归档 `corpus/notices/`；27 条见 `notice-skip.csv` |
| NPC 对话/逸闻/彩蛋 | 2,525 | 2,401 篇已归档 `corpus/voices/`；124 条见 `npc-skip.csv` |
| 知识层 | — | 400 实体（全部 reviewed）/ 459 个名字 / 106 关系 / 233 说法 / 8 纪年事件 / 61 条时间线 / 758 条实体出处；`knowledge/` 下 400 份正式卡片 |

当前数据库：

```text
文档：7,734
段落：453,939
正文字符：13,306,758
来源：9
数据库大小：约 345 MB
```

按类型：

```text
物品：2,622（材料 2,058 / 食物 325 / 动物 227 / 道具 12）
NPC 对话：2,401（NPC 对话 2,275 / 角色彩蛋 64 / 角色逸闻 62）
任务：1,097（1,065 有正文 + 32 空壳，均在库里）
散落文本：705
观景点：264
武器：252
角色：136
书籍：92
圣遗物：63
官方公告：55（版本更新说明 53 / 活动公告 2）
活动：47
（成就 1,558 条只在 CSV，不计入文档数）
```

任务子类型：

```text
world 642 · event 288 · story 92 · archon 46 · hangout 19 · interlude 4 · other 6
（其中 32 条空壳分布在 world 20 / story 12，含 12 条邀约）
```

版本覆盖：

| 类型 | 已标版本 | 未知 |
|---|---:|---:|
| 任务 | 1,097/1,097 | 0 |
| 角色 | 136/136 | 0 |
| 书籍 | 91/92 | 1（1158） |
| 散落文本 | 226/705 | 479 |
| 武器 | 252/252 | 0（全部来自 BWiki） |
| 圣遗物 | 63/63 | 0（全部来自 BWiki） |
| 官方公告 | 53/55 | 2（活动公告无版本字段） |
| NPC 对话/物品/观景点 | — | 频道无版本字段，一律不写、不猜 |

---

## 2. 最快入口

### Web UI（推荐日常使用）

```text
http://127.0.0.1:8765/
```

启停（也可以直接双击 `webui/start-webui.cmd` / `webui/stop-webui.cmd`）：

```powershell
cd D:\harn\2\genshin-lore-db
.\webui\start.ps1        # 后台启动，先探 /health，重复执行安全
.\webui\stop.ps1         # 按端口精确停止，校验身份、不误杀其他 Python
```

换端口用 `-Port 8766`（启停都要带）；日志在 `logs/webui-<port>.log`，
PID 文件 `logs/webui-<port>.pid`，均不进 Git。若终端报「禁止运行脚本」，
先执行 `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force`。
细节见 [`webui/README.md`](webui/README.md)。

健康检查：

```text
http://127.0.0.1:8765/health
```

特点：只读、搜索、类型/地区/版本/剧透筛选、文档页、来源、原始 Markdown。

### 命令行检索

```powershell
cd D:\harn\2\genshin-lore-db

.\tools\python\python.exe .\scripts\search.py 白之公主
.\tools\python\python.exe .\scripts\search.py 钟离 --type character
.\tools\python\python.exe .\scripts\search.py 层岩巨渊 --region 璃月 --spoiler 1
```

### SQLite

```powershell
.\tools\sqlite\sqlite3.exe -readonly .\db\genshin_lore.sqlite3
```

详细访问方式见 [`docs/06-访问与检索.md`](docs/06-访问与检索.md)。

---

## 3. 数据资产位置

```text
corpus/
├─ books/           92 本书（按地区）
├─ quests/          1,065 条有正文任务（archon 46 / story 92 / world 622 / event 288 / hangout 7 / interlude 4 / other 6）
│  └─ _pending/     32 条 OBC 无剧情对话的空壳页
├─ scattered/       705 条散落文本（按地区）
├─ weapons/         252 把武器（按类型：单手剑/双手剑/弓/法器/长柄武器）
├─ artifacts/       63 套圣遗物（平铺，每套一篇）
├─ events/          47 篇有叙事内容的活动
├─ geography/       264 篇观景点（按地区）
├─ items/           2,622 条材料/食物/动物/道具
├─ voices/          2,401 篇 NPC 对话/逸闻/彩蛋（按子类型 + 地区）
├─ notices/         55 篇官方公告（按子类型）
└─ characters/      136 个角色（按地区）

exports/
├─ obc-batch/       只剩 lore-manifest.csv / quest-manifest.csv 两份批次台账
└─ obc-evaluation/  统计、审计、抽样对照、补全报告

raw/
├─ official_site/obc/     OBC entry JSON、频道列表、meta（本轮 +2,525 条 NPC）
├─ official_site/announcements/ 游戏内公告 API 当前窗口（29 条）
├─ miyoushe/posts/        米游社官方版本更新说明（53 篇）
└─ bwiki/                 BWiki 版本查询、装备对照、任务补全缓存

db/
├─ genshin_lore.sqlite3
└─ backup/          数据库快照（不进 Git）

manifests/
├─ obc-index.csv        书籍/散落/任务 1,900 条
├─ character-index.csv  角色 138 条（136 已入库）
├─ coverage.csv         覆盖矩阵
├─ versions.csv         人工确认的版本
├─ notice-skip.csv      未归档公告（27 条）
└─ npc-skip.csv         未归档 NPC（124 条，均为无对话）
```

索引：

- [`corpus/books/index.csv`](corpus/books/index.csv)
- [`corpus/quests/index.csv`](corpus/quests/index.csv)
- [`corpus/scattered/index.csv`](corpus/scattered/index.csv)
- [`corpus/characters/index.csv`](corpus/characters/index.csv)
- [`corpus/voices/index.csv`](corpus/voices/index.csv)
- [`corpus/notices/index.csv`](corpus/notices/index.csv)
- [`manifests/obc-index.csv`](manifests/obc-index.csv)
- [`manifests/character-index.csv`](manifests/character-index.csv)

---

## 4. 已完成的关键工作

### 4.1 书籍

- OBC 93 条，92 本唯一书；
- `503 林间风·故事拔萃节选` 是 `501` 的重复卷，跳过；
- `500 白之公主与六侏儒` 只有第一卷全文，已标待补；
- `1158 残破的笔记` 版本 unknown；
- 已按地区归档到 `corpus/books/`。

### 4.2 散落文本

- 705 条归档 `corpus/scattered/`，10 个地区目录；
- 只保留交互文本，跳过地图截图/坐标；
- 226 条从相关任务/成就/活动推导出版本；
- 479 条版本 unknown，按约定不猜；
- 4 组同名条目（共 9 个文件）用 ` (obc-<content_id>)` 后缀消歧；
- 12 篇原本正文为空的页面已修复（见 §5.4）；
- 1 组同文重复（通知【明蕴镇】）已合并。

### 4.3 任务

- 1,097 个 OBC entry，全部在库；
- 1,065 条有正文，归档 `corpus/quests/`；
- 32 条无正文，隔离在 `_pending/`；
- 183 条用了 BWiki 源补全；
- 修复了 OBC `interactive_dialogue` 的 graph-only 格式，恢复了 381 条任务的对话；
- 任务版本 1,097/1,097 已补齐；
- 迁移时把 19 条「其实有正文、但被误标待补」的任务从 exports 收进 corpus；
- 第 1 步把 19 条邀约归入 `hangout/`、4 条间章归入 `interlude/`；
- 5 篇同名同文的任务/散落文本已合并，OBC 条目 id 保留在 `source` 里。

### 4.4 角色

- OBC 138 条，136 条入库；
- 2 条 `奇偶·男性/女性` 没有叙事模块，跳过；
- 只收：更多描述、角色详细、角色故事 1–5、神之眼/神之心、角色关联语音、生日邮件；
- 不含属性、命之座、配队、攻略、数值、图片；
- 版本来自 BWiki，136/136。

### 4.5 基础设施

- FTS5 改为 **trigram**，不依赖 jieba；
- 3 字以上中文直接 `MATCH`，2 字词回退 `LIKE`；
- 新增 `sections.parent_id` 索引，修复重载大任务时的级联删除性能；
- Web UI：`http.server + sqlite3 + markdown`，只读，无 Flask/FastAPI 依赖；
- 抽样对照、覆盖审计、补全报告都在 `exports/obc-evaluation/`；
- **Git 已初始化**，基线 `cb9647f`，`raw/` 按 binary 处理。

### 4.6 武器与圣遗物

- 武器 252 把（单手剑 59 / 双手剑 45 / 弓 50 / 法器 55 / 长柄武器 43），归档 `corpus/weapons/<类型>/`；
- 圣遗物 63 套，归档 `corpus/artifacts/`，每套五节（生之花/死之羽/时之沙/空之杯/理之冠）；
- 只收叙事：武器取「`<hr>` 之后的装备描述 + 相关故事」，圣遗物取「部位描述 + 部位故事」；
- **版本全部来自 BWiki**（OBC 这两个频道没有版本字段），252/252、63/63；
- BWiki 同名页 315/315 全部命中，244/315 的故事与 OBC 逐字一致；
- `星锋剑` OBC 原文「暂无」，已用 BWiki 补全；
- 4 套「祭X之人」在两边都只有 `理之冠`，文档标 `部件：1/5`；
- 部分圣遗物模块名为空，部位名在 `name.key` 里，渲染器已回退处理。

### 4.7 活动与成就

- 活动频道 275 条，只有 **47 条**有叙事内容，归档 `corpus/events/游戏活动/`；
- 只收三样：活动概述（非 `〓` 公告格式）、活动简介（「简介/背景」字段）、剧情/彩蛋对话；
- 228 条跳过，逐条原因写进 `manifests/event-skip.csv`：游戏活动 168、纪行 53、其他 5、活动祈愿 1、未知 1；
- 活动版本来自频道 ext 的 `版本/`（含「月之X」写法），47/47 有值；
- **成就 1,558 条只做 CSV**（`manifests/achievements.csv`），字段：名称/描述/成就集/版本/隐藏/每日委托；
- 成就页有两种形态：94 个成就集页（表格一次多行）+ 1,532 个单条页（`material_base_info` 里的成就描述）；
- 14 条成就的隐藏/每日标记为空：只在成就集表格里出现，频道无同名条目可回查。

### 4.8 地理与观景点

- 观景点 264 条归档 `corpus/geography/观景点/<地区>/`，10 个地区目录；
- 只收 `collapse_panel` 里的描述文字，图片块、地图、考据推荐全部丢弃；
- 描述很短（中位 50 字），是景点铭牌式文字，不是长篇设定；
- **区域 71 条没有正文**：模块只有地图、任务/怪物/素材/机关列表，没有一句散文；
- 区域信息做成 `manifests/regions.csv`：790 行，字段 `region,section,key,items,source_page_id`；
- 观景点频道没有版本字段，`version` 留空。

### 4.9 材料 / 食物 / 动物 / 道具

- 四个频道共 **2,622** 条，全部有描述，`manifests/item-skip.csv` 为空；
- 材料 2,058、食物 325、动物 227、道具 12，分别归档 `corpus/items/<子类型>/`；
- 只收 `material_base_info.attr["描述"]` 与 `good_desc` 里的「背景故事」；
- 丢弃：`用途`、`主要分布`、`使用效果`、`配方`、`获取方式`、`相关信息` 表格、`<名称>分布` 折叠面板、攻略；
- 食物页常带三个品质变体（奇怪/正常/美味），按原顺序各成一节；
- 12 组同名材料用 ` (obc-<content_id>)` 后缀消歧（如 `「镇物」`、`铁钥匙`、`藏宝图`）；
- **2,622 条版本全部 `unknown`**：OBC 物品频道只有食物类型/星级/获取方式/动物类型，没有版本字段，BWiki 材料页也没有统一 `实装版本`。按约定不猜。

### 4.10 官方公告

- 米游社原神官方账号 53 篇版本更新说明，**1.1 → 7.2 连续无断档**；版本与上线日期都来自帖子本身。
- 6.x 标题写作「月之一…月之八」，按 `manifests/version-labels.csv` 映射 6.0…6.7；
  「月之八」标题缺「版本」二字，渲染器也照常解析。
- 游戏内公告 API 只保留当前窗口 29 条：2 条带叙事的活动公告归档，27 条跳过
  （运营类 / 与米游社重复 / 纯图片无正文），逐条见 `manifests/notice-skip.csv`。
- 全文 `verbatim`，只删图片与表格，把 `〓小标题〓` 转成 `###`；
  补偿内容等运营段落保留，定位是**版本时间线佐证**，不作叙事正文统计。
- 55 篇中 53 篇有 `version`（`official` / `confirmed`），2 篇活动公告无版本字段，不猜。

### 4.11 NPC 对话 / 角色逸闻 / 角色彩蛋

- 三频道 2,525 条 entry 全部落盘，2,401 条有可归档对话，124 条只有商品/地图/空占位模块。
- 按子类型 + 地区归档：NPC 对话 2,275、角色彩蛋 64、角色逸闻 62；地区来自频道 `ext.filter`。
- 只收对话图、`秘闻馆情报`、`好感套装对话`、`赠礼对话`、`逸闻纪事·X` 名称/简介；
  商品/奖励/规则/地图/生日邮件一律不收；语音占位行已剔除。
- 正文约 231 万字符，是本库里仅次于任务的世界观细节来源（地名、传闻、日常生活、角色关系）。
- 3 组同名条目加 ` (obc-<content_id>)`；同页重复模块名加 `· 其二/其三`。
- 频道无版本字段，2,401 篇均不写 `version`。

---

## 5. 已知缺口与质量问题

### 5.1 明确未做

| 模块 | OBC 条目 | 状态 |
|---|---:|---|
| 武器 | 252 | done（252 篇，BWiki 版本全补齐） |
| 圣遗物 | 63 | done（63 套，4 套仅 1 部位） |
| 活动 | 275 | partial（47 篇有叙事，228 条系统页） |
| 观景点 | 264 | done（264 篇） |
| 区域 | 71 | done（结构化索引，无正文） |
| 成就 | 1,626 | done（1,558 条 CSV，不进正文层） |
| 材料/食物/道具 | 2,622 | done（2,622 篇，版本全部 unknown） |
| 官方公告 | 82 | done（55 篇归档，版本更新说明 1.1→7.2 连续） |
| NPC 对话 | 2,525 | done（2,401 篇归档，124 条无对话） |
| 漫画 | 未统计 | 未做 |
| PV / 过场动画文本 | 未统计 | 未做 |
| 七圣召唤牌面文本 | 未统计 | 未做（角色彩蛋里的七圣召唤**对话**已收） |
| 知识层 | — | done（400 实体全部复核 / 106 关系 / 233 说法 / 61 时间线，见第 10–19 步） |

> 剩下的是跨媒介内容（漫画、PV、七圣召唤牌面文本）与知识层打磨：
> 实体已到 400 个且全部复核完毕，claims 233 条，
> 关系 106 条覆盖 81 个实体，claims 233 条覆盖 65 个实体（全部来自角色语音，其余实体还没有说法）。
> 官方公告与 NPC 对话已接入；游戏内公告 API 只给当前窗口 29 条，
> 历史的版本说明靠米游社官方帖补齐，没有把运营公告硬塞进正文层。

### 5.2 任务尾巴

- 32 条空壳任务在 `_pending/`，主要是邀约/活动系列页；**BWiki 也补不了**（见 §5.4）；
- 邀约/间章归类已完成：`hangout/` 7 篇有正文（另 12 条空壳 subtype 已改 hangout），`interlude/` 4 篇；
- 18 篇系列页已加 `tags: [系列任务]`（标题含「系列/合集/总览」的 15 篇 + 海灯节 3 篇）；
- **多幕文件未拆分**：`雾海纪行系列任务`（4 幕）、`清籁逐雷记系列任务`（4 幕）等仍是「一篇多幕」。
  规范第 84 行允许「一个系列一篇，超长再拆」，所以先保留，没有强行切成合成的 doc_id；
- 同文重复已处理，剩 10 组逐组判定见 `manifests/duplicates.csv`：
  - 已合并 2 组（`好东西，坏品味` 5→1、`通知【明蕴镇】` 2→1）；
  - 保留 8 组：旅行者形态 4 组、危影重重 1 组、海灯节 1 组、空壳页 2 组，原因写在 CSV 里。

### 5.3 版本与书籍

- `1158 残破的笔记` unknown；
- `500 白之公主与六侏儒` 只有第一卷；
- 479 条散落文本版本 unknown。

### 5.4 内容质量

- **`quest.obc.5299` 串内容已修复（2026-11-05）**：第三章 第二幕「千朵玫瑰带来的黎明」的
  `## 尾声` 曾被 BWiki 短名错配填成序章 第三幕「巨龙与自由之歌」的蒙德尾声。
  已用观测枢原始快照的 `collapse_panel` 剧情对话重填（95 行 / 3,418 字），
  并修了补全脚本匹配规则。完整证据见 `exports/obc-evaluation/quest-5299-proofread.md`。
  **遗留**：`render_quest` 至今只认 `interactive_dialogue`，OBC 把剧情放在 `collapse_panel` 的任务
  仍会被误判为空；另有 11 组零碎错配节待人工核对。
- **散落文本空白页已修复**：`render_obc.py` 之前只从 `root_id` 起步，遇到「根节点不在 contents 里」的页面会输出空正文。现在改为从无父节点的孤岛起步、按节点 key 时间戳排序。12 篇恢复，最长 4,300 字。
- **`quest.obc.4190`**：BWiki 补全匹配到错误页面，已回退为空壳；原脚本「匹配不到就取第一条」的回退已删除。
- **`quest.obc.500835`**：曾被覆盖，已从 `raw/` 重渲染修复。
- **32 条空壳**：OBC 无正文，BWiki 同名页面的「任务剧情」也全部为空（3 个挂 `{{待补充}}`）。探测报告见 `exports/obc-evaluation/bwiki-stub-probe.md`。

### 5.5 审计数字

完整审计见：

- [`exports/obc-evaluation/coverage-audit.md`](exports/obc-evaluation/coverage-audit.md)
- [`exports/obc-evaluation/crosscheck.md`](exports/obc-evaluation/crosscheck.md)
- [`exports/obc-evaluation/bwiki-quest-fill.txt`](exports/obc-evaluation/bwiki-quest-fill.txt)
- [`exports/obc-evaluation/quest-5299-proofread.md`](exports/obc-evaluation/quest-5299-proofread.md)（5299 串内容校对与 177 篇补全文档排查）

覆盖矩阵已更新到 `manifests/coverage.csv`：

- `books = done`
- `characters = done`
- `scattered_text = done`（正文已归档，479 条版本 unknown）
- `hangouts = partial`（19 条已入库并归类，12 条无正文）
- `interludes = done`（4 条已归类）
- `main_story / story_quests / world_quests / event_quests = partial`
- `official_notices = done`、`npc_dialogue = done`、`character_voices = done`（NPC/逸闻/彩蛋对话）
- `entities / relations / claims / timeline = partial`（两批种子，待扩量）
- 其余 `planned`（漫画、PV、七圣召唤牌面）

---

## 6. 关键设计决策

1. **OBC 做主源，BWiki 做校验/兜底**；不是官方逐字文本，front matter 标 `canon_status: community`、`transcription: near-verbatim`。
2. **Markdown 是正文权威副本，SQLite 是索引层**；不要手工改 DB 正文，改 Markdown 后重导入。
   > 但反过来也成立：如果 Markdown 被脚本写坏，DB 里的旧版可能是唯一好副本。**重导入前先备份 DB**，并用 `char_count` 对账。
3. **版本必须溯源**：
   - `obc-filter`：任务频道版本；
   - `bwiki`：书籍/角色实装版本；
   - `derived-related-quest`：散落文本从相关任务/成就/活动推导；
   - 找不到就 `unknown`，不猜。
4. **不收攻略/配队/数值/图片**；角色只收叙事模块。
5. **同文异址允许共存**：哈希索引非唯一，重复通过 `v_duplicate_hashes` 查看。
6. **Web UI 只读**，只监听 `127.0.0.1`，不公网暴露。
7. **FTS5 trigram**：3 字以上中文可搜，2 字回退 `LIKE`。
8. **空壳与正文分目录**：`corpus/quests/` 只放有正文的，`_pending/` 放 OBC 0 剧情的页面，避免「任务数」虚高。
9. **`raw/` 在 Git 里按 binary 处理**：meta 存了响应体 `sha256`，不能做换行符转换。
10. **公告是完整官方文件，不做段落裁剪**：只去图片/表格，补偿与更新时间等运营文字保留，
    但明确标注「时间线佐证，不作叙事正文统计」，避免和「不收奖励/数值」的原则冲突时无从判断。
11. **同一段文本只在一个正文层出现**：生日邮件已在 `corpus/characters/`，角色彩蛋页里的生日模块不再重复收录。

---

## 7. 常用命令

### 检索

```powershell
.\tools\python\python.exe .\scripts\search.py 芙宁娜
.\tools\python\python.exe .\scripts\search.py 葬火之战 --type book --limit 5
.\tools\python\python.exe .\scripts\search.py 钟离 --type character --json
```

### 校验

```powershell
.\tools\python\python.exe .\scripts\validate_frontmatter.py --dir .\corpus\characters --quiet
.\tools\python\python.exe .\scripts\validate_frontmatter.py --dir .\corpus\quests --quiet
.\tools\python\python.exe .\scripts\validate_frontmatter.py --dir .\corpus\scattered --quiet
.\tools\python\python.exe .\scripts\validate_frontmatter.py --dir .\corpus\books --quiet
```

### 重新导入（注意分词模式不同）

```powershell
# 不分词：任务 / 角色 / NPC 对话
.\tools\python\python.exe .\scripts\load_markdown.py --dir .\corpus\quests --dir .\corpus\characters --dir .\corpus\voices --bulk --no-segment

# 要分词（不要加 --no-segment）：其余目录
.\tools\python\python.exe .\scripts\load_markdown.py --dir .\corpus\books --dir .\corpus\scattered --dir .\corpus\weapons --dir .\corpus\artifacts --dir .\corpus\events --dir .\corpus\geography --dir .\corpus\items --dir .\corpus\notices --bulk
```

上面两条合起来就是全量重导（约 1.5 分钟）。**重导前先备份 DB**；
`- 类型：` 等结构性元数据行由 `scripts/corpus_rules.py` 识别并排除出 sections/FTS，
改规则时 `load_markdown.py` 与 `audit_corpus.py` 共用该文件，不要只改一边。

重导后必跑体检：

```powershell
.\tools\python\python.exe .\scripts\audit_corpus.py --strict
```

### 统计与审计

```powershell
.\tools\python\python.exe .\scripts\report_db.py
.\tools\python\python.exe .\scripts\audit_coverage.py
```

### 数据库检查

```powershell
.\tools\sqlite\sqlite3.exe -readonly .\db\genshin_lore.sqlite3 "PRAGMA integrity_check;"
.\tools\sqlite\sqlite3.exe -readonly .\db\genshin_lore.sqlite3 "SELECT COUNT(*) FROM sections;"
```

### 备份

```powershell
.\tools\sqlite\sqlite3.exe .\db\genshin_lore.sqlite3 ".backup .\db\backup\genshin_lore-$(Get-Date -Format yyyyMMdd-HHmmss).sqlite3"
```

### Web UI

```powershell
.\webui\start.ps1
# 或
.\tools\python\python.exe .\webui\app.py --host 127.0.0.1 --port 8765
```

---

## 8. 下一步计划

### P0：收任务尾巴（基本完成）

已完成：subtype 归类、系列页标注、同文重复判定与合并、空白散落文本修复、BWiki 补全探测。

剩下的两件：

- **32 条空壳**：OBC 与 BWiki 都没有正文，只能从游戏数据包（`TalkConfig` / `QuestExcelConfigData`）取，属新数据源接入；
- **多幕文件拆分**：`雾海纪行`、`清籁逐雷记` 等 11 个系列页是一篇多幕。规范允许「一个系列一篇」，若要严格「一篇一幕」，得设计合成 doc_id 的规则（如 `quest.obc.2942.act1`），会影响 `source.page_id` 的一一对应，需要先定规范再动手。

### P1：武器 + 圣遗物（已完成）

- 252 把武器 + 63 套圣遗物已归档入库，版本由 BWiki 补齐；
- 对照结果：244/315 与 BWiki 故事完全一致，仅 `星锋剑` 需用 BWiki 补；
- 详细说明见 `corpus/weapons/README.md`、`corpus/artifacts/README.md`。

### P2：活动 + 成就（已完成）

- 活动 275 条中 47 条有叙事，已归档 `corpus/events/`；其余 228 条是公告/纪行/赛季页，清单在 `manifests/event-skip.csv`；
- 成就 1,558 条已抽成 `manifests/achievements.csv`，不进正文层；
- 活动剧情本体本来就在 `corpus/quests/event/`（288 条），不需要重复收。

### P3：其他文本（部分完成）

已完成：

- **材料/食物/动物/道具** 2,622 条，归档 `corpus/items/`；
- **观景点** 264 条，归档 `corpus/geography/`；**区域** 71 个做成 `manifests/regions.csv`。

已完成（第 6 步）：

- **官方公告** 55 篇 → `corpus/notices/`（53 篇版本更新说明覆盖 1.1→7.2 无断档）；
- **NPC 对话 / 逸闻 / 彩蛋** 2,401 篇 → `corpus/voices/`。

未做：

- 漫画、PV / 过场文本；
- 七圣召唤牌面文本（角色彩蛋里的七圣召唤对话已顺带收录）。

### P4：知识层（两批种子已完成）

- `entities` 400（全部 reviewed）/ `entity_names` 459 / `entity_relations` 106 / `claims` 233 / `entity_evidence` 758；
- `events` 8 / `event_sources` 8 / `timeline_entries` 61（53 现实版本 + 8 提瓦特纪年）；
- 权威源是 `knowledge/seed*.yaml`（四批），`knowledge/**/*.md` 是导出的阅读视图，
  SQLite 是查询层；改结论改 seed 后重跑 `load_knowledge.py --apply` 与 `export_entity_cards.py --apply`。

下一步建议：知识层已收口，剩下的是跨媒介内容（漫画/PV/七圣召唤牌面）与 claims 的视角补充；
给争议说法补「不同来源」对照，再考虑 `document_links` / `document_aliases` 两张仍为 0 的表；
**不要自动生成全量图谱**。

---

## 9. 交接注意事项

- **Git 已初始化**，基线 `cb9647f`。`db/*.sqlite3`、`tools/`、`logs/*.log` 不进版本库；`raw/` 在库里但按 `binary` 处理。
- 数据库约 244 MB，`raw/` 约 136 MB，`tools/` 约 94 MB；仓库当前 36.95 MiB。
- **重导入前先 `.backup` 一份 DB**：Markdown 可能被历史脚本写坏，DB 反而留着好副本（见 §5.4）。
- 不要手工改 SQLite 正文；改 Markdown 后重新 `load_markdown.py`。
  - 例外：合并重复文档需要删除 DB 行，必须 `PRAGMA foreign_keys = ON` 才能级联清掉 sections / sources / tags。用 `sqlite3` CLI 时要显式加这一句，默认是关的。
- 删改文档后记得同步 `corpus/*/index.csv`，否则索引会指向不存在的文件。
- 批量导入大文档时，确保 `idx_sections_parent` 存在；否则级联删除会很慢。
- FTS 触发器存在时逐条导入会慢；大批量可先 drop triggers，导入后 rebuild（当前 schema 已有 trigram 迁移）。
- 32 条空壳任务和 480 条 unknown 版本不是「漏跑」，是来源本身没有稳定字段/正文，已明确标记。
- 游戏文本版权归原权利方；本库仅本地个人研究使用，Web UI 不要公网部署。

---

## 10. 相关文档

- [README](README.md)
- [总体设计](docs/00-总体设计.md)
- [数据源与合规](docs/01-数据源与合规.md)
- [数据规范](docs/02-数据规范.md)
- [实施路线图](docs/03-实施路线图.md)
- [观测枢评估](docs/05-观测枢评估.md)
- [访问与检索](docs/06-访问与检索.md)
- [覆盖审计](exports/obc-evaluation/coverage-audit.md)
- [抽样对照](exports/obc-evaluation/crosscheck.md)
- [数据库统计](exports/obc-evaluation/summary.txt)
- [Web UI 说明](webui/README.md)
- [散落文本说明](corpus/scattered/README.md)
- [待补任务说明](corpus/quests/_pending/README.md)
- [活动说明](corpus/events/README.md)
- [成就索引](manifests/achievements.csv)
- [重复组判定](manifests/duplicates.csv)
- [BWiki 空壳探测](exports/obc-evaluation/bwiki-stub-probe.md)
