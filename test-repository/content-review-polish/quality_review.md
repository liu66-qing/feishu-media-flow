# content-review-polish 质量测试报告

## 测试范围

当前完成 1 条基础 badcase 测试：

- case_001：社团招新文案，存在标题弱、营销腔、内容深度不足问题
- case_001_risk：将 polished 内容转换为 risk-check 输入后进行串联测试

## case_001 输出检查

| 检查项 | 通过标准 | 实际结果 | 是否通过 | 备注 |
|---|---|---|---|---|
| JSON 格式 | 可解析 | 可解析 | 通过 | 已生成 content_review_polish.json |
| quality_score | 包含 5 个评分项 | 已包含 | 通过 | hook、naturalness、depth、layout、overall |
| badcase 评分 | overall < 3 | 2.5 | 通过 | 原文质量较差 |
| issues | 非空 | 3 条 | 通过 | 能识别主要问题 |
| polished | 与 original 不同 | 明显不同 | 通过 | 标题和正文均有修改 |
| changes_summary | 非空 | 非空 | 通过 | 正常 |
| risk-check | risk_level = low | low | 通过 | 润色后无命中 |

## 原文问题

原文：

```text

分享一下社团招新
社团招新真的很重要，大家一定要赶紧准备。这个方法绝对有用，可以保证效果变好。

识别问题：
标题钩子偏弱
正文存在营销腔和绝对化表达
内容信息量偏少

润色结果

润色后标题：
社团招新前，先把这三件事想清楚

润色后正文：
社团招新真的很重要，可以提前做一些准备。

这些方法能帮助你把现场流程理得更清楚。

可以先从三个问题开始：这次想吸引什么样的新生？现场谁负责介绍？活动结束后怎么继续沟通？

如果信息还不够完整，建议补充具体场景、真实例子或执行步骤。

迭代记录

v1
建立基础评分和润色流程。
问题：
机械替换导致表达不自然
出现“要可以先”“可以有机会效果变好”等问题

v2
改为短语级替换和场景化补充。
结果：
标题更自然
正文去掉绝对化表达
补充了三个具体问题

v3
完成 risk-check 串联测试。

结果：
risk_level = low
hits = []

当前不足

当前版本仍有以下不足：
只测试 1 条 badcase
尚未接入 LLM
评分逻辑较简单
尚未测试 light / heavy 模式
保留主旨仍需要人工判断

阶段结论

content-review-polish 第一版基础流程已跑通。

当前版本可以验证：
输入输出结构
质量评分
问题识别
润色输出
changes_summary
risk-check 串联
后续需要补充更多 badcase、LLM 润色能力和人工质量判断。

- case_001：已接入 LLM，运行成功，输出包含 llm_enabled=true、llm_error=""。
- 对生成结果执行 risk-check，最终风险等级为 low。

- case_001_risk：对润色后的内容执行 risk-check，最终 risk_level=low，llm_enabled=true，llm_error=""。

- content-review-polish case_001_risk：跨 skill 风险检查通过，risk_level=low，LLM 检查正常。