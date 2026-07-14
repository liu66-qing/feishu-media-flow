# hot-rewrite（LLM版）

## 功能说明

hot-rewrite 用于对热帖进行爆点分析，并从新的角度用 LLM 改写成原创内容。

当前版本（LLM版）支持：

- 读取原文、来源链接、目标平台、目标栏目和改写角度
- 调用 LLM 分析原文爆点结构（hook、structure、viral_points、target_audience）
- 调用 LLM 从新角度改写内容（保留核心信息，换叙事风格，不编造事实）
- 使用 Simhash 计算与原文的相似度
- 相似度 > 0.3 时自动要求 LLM 重写（最多 2 次重试）
- 标注 source_attribution
- 输出 similarity_score 和 similarity_method

## 环境变量

- `LLM_API_KEY`：LLM API 密钥（必填）
- `LLM_BASE_URL`：LLM API 地址（默认 `https://api.openai.com/v1`）
- `LLM_MODEL`：模型名称（默认 `gpt-5.4-mini`）

## 输入

输入文件固定为：

```text
{job_dir}/input.json
```

示例：

```json
{
  "content_id": "CNT-HOT-001",
  "job_id": "JOB-HOT-001",
  "source_url": "https://example.com/source-post-001",
  "source_text": "原始热帖正文",
  "target_platform": "xhs",
  "target_column": "经验干货",
  "rewrite_angle": "从大学生社团负责人的视角"
}
```

## 输出

输出文件固定为：

```text
{job_dir}/hot_rewrite.json
```

输出字段包括：

- `original_analysis`：原文爆点分析（LLM 生成）
- `rewritten_content`：改写结果（LLM 生成）
- `similarity_score`：归一化后相似度分数，用于判断是否通过
- `similarity_method`：相似度计算方式说明
- `source_attribution`：来源标注
- `risk_notes`：风险提示
- `llm_enabled`：是否启用 LLM（当前版本固定为 true）
- `llm_error`：LLM 错误信息（无错误时为空）

## 相似度规则

任务要求改写结果相似度低于 30%。

当前版本使用 Simhash 计算文本相似度，并保留两个分数：

- `simhash_raw_score = 1 - distance / 64`
- `similarity_score = max(0, (simhash_raw_score - 0.5) * 2)`

原因：Simhash 原始分数对中文同主题短文本偏高，0.5 附近常代表随机基线，不一定代表高度相似。因此当前版本保留原始分数，同时使用归一化后的 similarity_score 作为验收判断。

判断规则：

- `similarity_score < 0.3`：success
- `similarity_score >= 0.3`：自动重试，最多 2 次；重试后仍超标则 failed

## 自动重试机制

当改写结果相似度超过 0.3 时，系统会自动重试：

1. 第 1 次重试：在 prompt 中追加重试提示，告知上次相似度分数
2. 第 2 次重试（最后一次）：再次追加更强的改写要求
3. 超过 2 次仍未通过：标记为 `failed`，建议人工介入

## 运行方式

在项目根目录下运行：

```bash
python hot-rewrite/main.py --job-dir hot-rewrite/test/fixtures/case_001
```

## 后续优化

- 准备 5 篇真实热帖测试
- 将 rewritten_content 串联 risk-check
- 在 quality_review.md 中记录人工判断结果
