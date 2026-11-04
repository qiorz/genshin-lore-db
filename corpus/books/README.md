# corpus/books · 游戏内书籍

当前收录 92 本观测枢书籍条目，按地区分目录：

```text
corpus/books/
├─ 蒙德/
├─ 璃月/
├─ 稻妻/
├─ 须弥/
├─ 枫丹/
├─ 纳塔/
├─ 挪德卡莱/
├─ 至冬/
├─ 渊下宫/
├─ 提瓦特/
├─ 未知/
└─ index.csv
```

`index.csv` 字段：

```text
doc_id,title,region,version,version_source,version_confidence,path
```

说明：

- 92 本来自观测枢书籍频道 93 条中的唯一书；`503 林间风·故事拔萃节选` 是 `501 林间风` 的重复卷，跳过。
- `白之公主与六侏儒`（500）只有第一卷全文，其余卷为简介，待 BWiki 补。
- `残破的笔记`（1158）版本未知。
- 书籍正文只保留文字，不提取封面/地图图片。
- 这些文件已进入正式 `corpus/`，重新导入用：

```powershell
.\tools\python\python.exe scripts\load_markdown.py --dir corpus\books
```
