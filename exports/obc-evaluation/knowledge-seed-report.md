# 知识层种子 · 灌库报告

> 2026-11-11T09:24:28+08:00 · 模式：写入 · 来源：`knowledge/seed.yaml`、`knowledge/seed-stage10.yaml`、`knowledge/seed-stage2.yaml`、`knowledge/seed-stage3.yaml`、`knowledge/seed-stage4.yaml`、`knowledge/seed-stage5.yaml`、`knowledge/seed-stage6.yaml`、`knowledge/seed-stage7.yaml`、`knowledge/seed-stage8.yaml`、`knowledge/seed-stage9.yaml`

| 项 | 值 |
|---|---|
| 实体 | 400（reviewed 400） |
| 种子批次 | 10 |
| 别名（不含规范名） | 74 |
| claims | 364 |
| 关系边 | 198 条人工 + 17 条事件参与 |
| 提瓦特纪年事件 | 8（era=teyvat，只有相对顺序） |
| 现实版本上线 | 53（era=release，官方公告日期） |
| 证据引用 | 1328 |
| 证据解析成功 | 1328 |
| 校验错误 | 0 |

claims 置信度：likely 280、speculative 77、confirmed 5、disputed 2  
关系置信度：likely 119、confirmed 79

## 两条时间线互不换算

- `era=release`：现实世界版本上线日期，取自米游社官方版本更新说明，certainty=exact；
- `era=teyvat`：提瓦特纪年，只有相对先后，sort_key 为负数不代表年份，
  原文里的「约两千六百年前」「五百年前」保留为约数文字，不写成 absolute_year。

## 证据样例（点得回原文）

- `quest.obc.508097` 第 227 段 / section 956560：温迪即风神巴巴托斯
- `quest.obc.1250` 第 641 段 / section 895430：钟离是岩王帝君摩拉克斯以凡人身份使用的名字
- `quest.obc.5299` 第 819 段 / section 905041：纳西妲即须弥的草神小吉祥草王
- `quest.obc.4691` 第 917 段 / section 1102222：entity.venti —deity_of→
- `voice.obc.1258` 第 21 段 / section 1247765：entity.zhongli —deity_of→

证据只用 `doc_id + 短引用` 定位，重导 corpus 后重跑本脚本即可重新对齐；
不硬编码 section_id。原文层（documents / sections）不受影响。
