# 知识层第一批种子 · 灌库报告

> 2026-11-05T19:20:02+08:00 · 模式：写入 · 来源 `knowledge/seed.yaml`

| 项 | 值 |
|---|---|
| 实体 | 30 |
| 别名（不含规范名） | 29 |
| claims | 10 |
| 证据引用 | 43 |
| 证据解析成功 | 43 |
| 校验错误 | 0 |

claims 置信度：confirmed 5、likely 2、disputed 2、speculative 1

## 证据样例（点得回原文）

- `quest.obc.508097` 第 227 段 / section 956560：温迪即风神巴巴托斯（confirmed / accepted）
- `quest.obc.1250` 第 641 段 / section 895430：钟离是岩王帝君摩拉克斯以凡人身份使用的名字（confirmed / accepted）
- `quest.obc.5299` 第 819 段 / section 905041：纳西妲即须弥的草神小吉祥草王（confirmed / accepted）
- `quest.obc.509511` 第 732 段 / section 898604：达达利亚的愚人众执行官代号是「公子」（confirmed / accepted）
- `quest.obc.399` 第 203 段 / section 873279：特瓦林就是被称为风魔龙的龙（confirmed / accepted）

证据只用 `doc_id + 短引用` 定位，重导 corpus 后重跑本脚本即可重新对齐；
不硬编码 section_id。原文层（documents / sections）不受影响。
