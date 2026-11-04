# corpus/artifacts · 圣遗物故事

观测枢圣遗物套词条 **63** 套，每套一篇，五个部位各一节。只收**部位描述**与**故事**，不含套装数值、推荐搭配。

```text
corpus/artifacts/
├─ 血红之证.md      每套一篇，平铺
├─ 祭火之人.md
├─ …
├─ README.md
└─ index.csv
```

文件名 = 套装名，`## 生之花 · 感谢你的奉献` 这种标题带上部位名。

`index.csv` 字段：

```text
doc_id,title,subtype,version,version_source,version_confidence,path
```

## 内容来源

| 字段 | 来源 | 说明 |
|---|---|---|
| 部位名 | OBC `artifact_list_v2` 的 `name.value` | 如「感谢你的奉献」 |
| 描述 | 同上 `desc` | 一两句的外观描述 |
| 故事 | 同上 `story` | 完整故事 |
| 版本 | **BWiki** `|实装版本=` | OBC 圣遗物频道没有版本字段 |

- 63/63 版本已标，`version_source: bwiki`；
- 部位归属优先用模块名（`生之花` 等），模块名为空时回退到 `name.key`（如「生之花：」）。
  不这样就漏掉 `烬城勇者绘卷` 的全部 5 个部位。

## 只有 1 个部位的套装

有 4 套在 OBC 与 BWiki 上都只收录了 `理之冠`，其余 4 个部位是空占位（`<p></p>`）：

```text
祭火之人 · 祭水之人 · 祭雷之人 · 祭冰之人
```

这几套的文档里 `- 部件：1/5`，`notes` 也标了「OBC 仅收录 1 个部位」。
不是解析失败，是来源页本身为空。

## 与 BWiki 对照

`manifests/equipment-bwiki-compare.csv` 同时记录圣遗物的对照：

- OBC 每套把 5 个部位的故事拼起来算字数；
- BWiki 取 `|生之花故事=`…`|理之冠故事=` 五段；
- 圣遗物整体 ratio 偏高（1.2–3.0）多为 BWiki 只写了 1–2 个部位，不是 OBC 多收。

## 重新导入

```powershell
.\tools\python\python.exe scripts\load_markdown.py --dir corpus\artifacts --bulk
```

> 圣遗物是叙事文本，入库**用 jieba 分词**（不加 `--no-segment`）。
