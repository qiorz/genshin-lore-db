# corpus/characters · 角色叙事文本

当前收录 **136** 个角色，按地区分目录：

```text
corpus/characters/
├─ 蒙德/
├─ 璃月/
├─ 稻妻/
├─ 须弥/
├─ 枫丹/
├─ 纳塔/
├─ 挪德卡莱/
├─ 至冬/
├─ 未知/
└─ index.csv
```

内容只保留游戏内叙事模块：

- 更多描述
- 角色详细
- 角色故事 1–5
- 神之眼 / 神之心
- 角色关联语音
- 生日邮件

**不包含**属性、命之座、配队、攻略、数值和图片。

说明：

- OBC 角色频道共 138 条；136 条有叙事内容；
- `奇偶·男性`、`奇偶·女性` 没有叙事模块，未入库；
- 版本来自 BWiki `实装版本`，136/136 有版本；
- `index.csv` 字段：`doc_id,title,region,version,element,weapon,star,path`。

重新导入：

```powershell
.\tools\python\python.exe scripts\load_markdown.py --dir corpus\characters --bulk --no-segment
```
