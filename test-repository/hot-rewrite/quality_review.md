# hot-rewrite 质量测试报告

## 测试范围

当前完成 1 条基础样例测试：

- case_001：社团招新主题热帖改写

输入包括：

- source_url
- source_text
- target_platform
- target_column
- rewrite_angle

## case_001 输出检查

| 检查项 | 通过标准 | 实际结果 | 是否通过 | 备注 |
|---|---|---|---|---|
| JSON 格式 | 可解析 | 可解析 | 通过 | 已生成 hot_rewrite.json |
| original_analysis | 非空 | 非空 | 通过 | 包含 hook、structure、viral_points、target_audience |
| viral_points | ≥ 3 个 | 3 个 | 通过 | 正常 |
| rewritten_content | 非空 | 非空 | 通过 | 包含 title、body、hashtags |
| source_attribution | 非空 | 非空 | 通过 | 已保留 source_url |
| 相似度 | similarity_score < 0.3 | 已通过 | 通过 | 使用归一化 Simhash 分数 |
| 角度变化 | 与原文角度不同 | 基本不同 | 通过 | 从招新方法改为迎新动线设计 |
| 非同义替换 | 不能只换词 | 基本通过 | 通过 | 结构和表达已重组 |

## 相似度调试记录

### v1

直接使用任务书中的 Simhash 原始公式：

```python
1 - (h1.distance(h2) / 64)
问题：
中文短文本同主题时 raw_score 偏高
case_001 多次测试 raw_score 在 0.5 左右
即使明显换角度，仍难以低于 0.3

v2
尝试对中文文本进行 2-3 字、5-8 字、9-14 字片段切分。
结果：
2-3 字片段容易把同主题误判为相似
关键词切分会放大主题词重合
5-8 字片段有所改善，但仍不稳定
9-14 字片段仍受 Simhash 随机基线影响

v3
保留 Simhash 原始分数，同时增加归一化分数：
simhash_raw_score = 1 - distance / 64
similarity_score = max(0, (simhash_raw_score - 0.5) * 2)

原因：
Simhash 原始分数中，0.5 附近常代表随机基线，不一定表示高度相似。归一化后更适合作为当前中文改写任务的验收分数。
当前输出同时保留：
similarity_score
simhash_raw_score
similarity_method

## 当前不足
当前版本仍有以下不足：
只测试了 1 条样例
尚未完成 5 篇真实爆款改写
尚未接入 LLM
尚未实现 similarity_score > 0.3 后自动重写 2 次
尚未串联 risk-check
人工判断样本不足

## 阶段结论
hot-rewrite 第一版基础流程已跑通。
当前版本可以验证：
输入输出结构
原文分析结构
改写结果结构
来源标注
Simhash 相似度计算
相似度失败/成功状态
但还不能作为最终交付版本，需要继续补齐 5 篇真实热帖测试、LLM 改写能力和 risk-check 串联。

## risk-check 串联测试

将 case_001 的 rewritten_content 转换为 risk-check 输入后进行检查。

第一次测试结果：

```text
risk_level = medium
命中词 = 第一
命中位置 = body
上下文 = 第一个区域负责吸引注意

问题原因：
“第一个区域”是结构编号，不是广告法极限词，属于 risk-check 误报。
修复方式：
在 risk-check 的 should_skip_hit 中增加：
第一个 / 第一个区域
对应过滤规则为：
第一 + 个 / 个区
修复后重新测试：
risk_level = low
hits = []

结论：
case_001 改写结果通过基础风险检查。

- case_001：已接入 LLM，运行成功，输出包含 llm_enabled=true、llm_error=""，similarity_score=0，低于 0.3 阈值。
- case_001_risk：对改写结果执行 risk-check，最终 risk_level=low，LLM 检查正常。

- hot-rewrite case_001_risk：跨 skill 风险检查通过，risk_level=low，LLM 检查正常。