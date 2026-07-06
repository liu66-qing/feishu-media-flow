# risk-check 质量测试报告

## 测试范围

本次测试共 20 条内容：

- 正常内容 10 条：case_001 到 case_010
- 风险内容 10 条：case_011 到 case_020

测试目标：

- 正常内容应返回 low
- 广告法极限词应返回 medium
- 敏感行业词应返回 high
- 平台引流词应记录 hits，并按命中数量判断风险等级

## 测试结果

| 用例 | 内容类型 | 预期结果 | 实际结果 | 是否通过 | 备注 |
|---|---|---|---|---|---|
| case_001 | 正常内容 | low | low | 通过 | 无命中 |
| case_002 | 正常内容 | low | low | 通过 | 无命中 |
| case_003 | 正常内容 | low | low | 通过 | 无命中 |
| case_004 | 正常内容 | low | low | 通过 | 无命中 |
| case_005 | 正常内容 | low | low | 通过 | 无命中 |
| case_006 | 正常内容 | low | low | 通过 | 无命中 |
| case_007 | 正常内容 | low | low | 通过 | v1 曾误报“第一次”，v2 已修复 |
| case_008 | 正常内容 | low | low | 通过 | v1 曾误报“最后”，v2 已修复 |
| case_009 | 正常内容 | low | low | 通过 | 无命中 |
| case_010 | 正常内容 | low | low | 通过 | 无命中 |
| case_011 | 绝对化表达 | medium | medium | 通过 | 命中“最” |
| case_012 | 绝对化表达 | medium | medium | 通过 | 命中“保证” |
| case_013 | 绝对化表达 | medium | medium | 通过 | 命中“第一” |
| case_014 | 平台引流词 | low | low | 通过 | 命中“私信领”，按规则仍为 low |
| case_015 | 敏感行业词 | high | high | 通过 | 命中“医疗诊断” |
| case_016 | 敏感行业词 | high | high | 通过 | 命中“投资收益” |
| case_017 | 敏感行业词 | high | high | 通过 | 命中“考试包过” |
| case_018 | 绝对化表达 | medium | medium | 通过 | 命中“顶级” |
| case_019 | 绝对化表达 | medium | medium | 通过 | 命中“100%” |
| case_020 | 平台引流词 | low | low | 通过 | 命中平台引流词，按当前规则为 low |

## 指标统计

### 假阳性率

正常内容共 10 条，误报 0 条。

假阳性率：

```text
0 / 10 = 0%

### douyin 串联测试误报

在 content-generate-douyin 的 case_001_risk 串联测试中，risk-check 将“最重要的信息”误判为命中 absolute_claims 中的“最”。

问题原因：

“最重要的信息”在该语境中是内容结构表达，不是广告宣传中的极限承诺。

修复方式：

在 should_skip_hit 中增加对“最重要”的过滤。

修复后结果：

```text
risk_level = low
hits = []

## LLM 接入记录

已根据任务书统一规范接入 LLM：

- API Key 从 LLM_API_KEY 读取
- Base URL 从 LLM_BASE_URL 读取
- Model 从 LLM_MODEL 读取
- Prompt 从 prompts/system.md 和 prompts/user_template.md 读取
- LLM 输出解析为 JSON 后写入 llm_concerns 和 suggestions


## LLM 接入测试记录

已按任务书统一规范接入 LLM：

- API Key 从 LLM_API_KEY 读取
- Base URL 从 LLM_BASE_URL 读取
- Model 从 LLM_MODEL 读取
- Prompt 从 prompts/system.md 和 prompts/user_template.md 读取
- LLM 输出写入 llm_concerns 和 suggestions

测试配置：

```text
LLM_BASE_URL = <your_base_url>
LLM_MODEL = <your_base_model>