# content-generate-douyin 质量测试报告

## 测试范围

当前完成 1 条基础样例测试：

- case_001：3个方法让社团招新效率更高
- case_001_risk：将生成脚本转换为 risk-check 输入后进行串联测试

## case_001 输出检查

| 检查项 | 通过标准 | 实际结果 | 是否通过 | 备注 |
|---|---|---|---|---|
| JSON 格式 | 可解析 | 可解析 | 通过 | 已生成 content_generate_douyin.json |
| 总时长 | duration_target ±5 秒 | 75 秒 | 通过 | 目标 75 秒 |
| 场景数 | 8-15 个 | 10 个 | 通过 | 正常 |
| 单场景时长 | 每个 ≤ 8 秒 | 全部 ≤ 8 秒 | 通过 | v2 已修复 |
| 首场景 hook | 明显钩子 | 有 | 通过 | 以问题开场 |
| subtitle 精简 | 短于 voiceover | 基本满足 | 通过 | 屏幕字更短 |
| asset_hint | 每场景都有 | 每场景都有 | 通过 | 正常 |
| caption | 非空 | 非空 | 通过 | 正常 |
| cover_text | 非空 | 非空 | 通过 | 正常 |

## 时长修复记录

第一次生成中，scene 10 的 duration 为 9 秒，超过任务书要求的：

```text
每场景 ≤ 8 秒

修复方式：
将 scene 1 从 6 秒调整为 7 秒
增加时长分配逻辑
保证每个场景时长控制在 5-8 秒

修复后：
duration = 75
scenes = 10
max scene duration = 8

risk-check 串联测试

第一次串联测试中，risk-check 将“最重要的信息”中的“最”误判为 absolute_claims。

问题原因：
“最重要的信息”在该语境中是内容结构表达，不是广告宣传中的极限承诺。

修复方式：
在 risk-check 的 should_skip_hit 中增加“最重要”的过滤。

修复后重新测试：
risk_level = low
hits = []
结论：case_001 通过基础风险检查。

Prompt 迭代记录

v1
建立基础短视频脚本结构：
title
duration
hook
scenes
caption
hashtags
cover_text

问题：
最后一个场景 duration 为 9 秒，超过限制

v2

修复场景时长：
每个 scene duration 控制在 5-8 秒
总时长保持在 duration_target ±5 秒
结果：
duration = 75
scenes = 10
每个 scene duration ≤ 8

v3

完成 risk-check 串联：
首次命中“最重要”的误报
已在 risk-check 中增加中性表达过滤
修复后 risk_level = low

当前不足

当前版本仍有以下不足：
只测试 1 个选题
尚未接入 LLM
尚未进行真实朗读录音测试
尚未完成“3/5 场景以上自然通顺”的人工评估
生成内容模板化较强

阶段结论

content-generate-douyin 第一版基础流程已跑通。
当前版本可以验证：
输入输出结构
分镜 JSON 结构
总时长控制
单场景时长控制
asset_hint 完整性
risk-check 串联
后续需要补充更多选题、朗读测试和 LLM 生成能力。

## LLM 接入记录

content-generate-douyin 已接入 LLM。

测试结果：

```text
content-generate-douyin:
llm_enabled = true
llm_error = ""

risk-check 串联:
risk_level = low
llm_enabled = true
llm_error = ""

追加修复：content-generate-douyin 串联测试中，“第一，目标是否清楚”被误判为 absolute_claims。已将“第一，” “第一、” “第一：”等结构编号表达加入过滤规则。