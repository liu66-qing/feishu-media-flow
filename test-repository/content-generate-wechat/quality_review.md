# content-generate-wechat 质量测试报告

## 测试范围

当前完成第一条基础样例测试：

- case_001：Rust 语言在 2026 年的生态现状
- case_001_risk：将生成结果转为 risk-check 输入后进行串联测试

## case_001 生成结果检查

| 检查项 | 通过标准 | 实际结果 | 是否通过 | 备注 |
|---|---|---|---|---|
| JSON 格式 | 可正常解析 | 可解析 | 通过 | 已生成 content_generate_wechat.json |
| title_options | 至少 3 个标题 | 3 个 | 通过 | 正常 |
| selected_title | 非空 | 非空 | 通过 | 正常 |
| summary | ≤ 120 字 | ≤ 120 字 | 通过 | 正常 |
| body_md | Markdown 正文 | 已生成 | 通过 | 有标题和二级标题 |
| 小标题 | ≥ 3 个 `##` | 超过 3 个 | 通过 | 正常 |
| sections | 结构化数组 | 已生成 | 通过 | 正常 |
| cta | 非违规引流 | 未出现引流词 | 通过 | 正常 |
| risk_notes | 有风险提醒 | 已生成 | 通过 | 正常 |

## risk-check 串联结果

第一次串联测试中，risk-check 将「读者最需要知道的是」里的「最」误判为 absolute_claims，返回 medium。

修复方式：

- 在 risk-check 中加入「最需要」等中性表达过滤

修复后重新测试：

```text
risk_level = low
hits = []
结论：case_001 通过 risk-check。

## 当前不足
当前版本为模板生成版，存在以下不足：
内容更接近文章骨架，不是完整公众号长文
观点深度不足
尚未接入 LLM
尚未完成 3 个选题 × 3 次测试
尚未完成非技术读者可读性反馈

## Prompt 迭代记录
v1
建立基础输出结构：
title_options
selected_title
summary
body_md
sections
cta
risk_notes
问题：
正文偏短
内容深度不足

v2
计划加强结构和长度控制：
body_md 控制在 1200-1800 字
至少 3 个二级标题
数据和趋势标注「[需核实]」
CTA 避免违规引流

v3
计划提升文章深度和可读性：
不只罗列素材
每节有明确观点
参考资料自然融入正文
输出后必须通过 risk-check

## 阶段结论
content-generate-wechat 第一版基础结构通过。
当前可作为开发骨架继续迭代，但还不能作为最终公众号长文生成版本交付。后续需要接入 LLM，并补齐 3 个选题 × 3 次测试和人工反馈。当前版本已将 body_md 扩展为接近 1200 字的公众号长文结构，较 v1 明显改善。但由于仍是模板生成，文章深度和表达自然度仍需要 LLM 或人工继续优化。

## LLM 接入记录

已接入 LLM 生成公众号长文。

实现方式：

- 使用 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL 读取模型配置
- 从 prompts/system.md 和 prompts/user_template.md 读取 prompt
- 支持 WebFetch / WebSearch 工具调用
- 工具结果回传给模型后生成最终 JSON
- 如果 LLM 失败，则回退到模板生成版

调试记录：

- 初次接入时模型返回 tool_calls，content 为空
- 后续增加 WebFetch / WebSearch 本地工具执行
- 发现长文 JSON 容易因输出过长截断
- 已通过限制 body_md 长度和提高 max_tokens 解决

当前结果：

```text
llm_enabled = true
llm_error = ""

## LLM 接入与联网工具测试

content-generate-wechat 已接入 LLM，并支持 WebFetch / WebSearch 工具调用。

测试过程：

- 初次 LLM 返回 tool_calls，content 为空
- 增加本地 WebFetch / WebSearch 函数
- 增加 tool_calls 处理逻辑：模型请求工具 → 本地执行工具 → 工具结果回传模型 → 生成最终 JSON
- 发现长文 JSON 容易因输出过长或英文双引号导致解析失败
- 通过限制 body_md 长度、提高 max_tokens、约束 JSON 格式后修复

当前测试结果：

```text
content-generate-wechat:
llm_enabled = true
llm_error = ""

risk-check 串联:
risk_level = low
llm_enabled = true
llm_error = ""