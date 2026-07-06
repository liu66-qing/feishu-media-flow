# hot-rewrite

## 功能说明

hot-rewrite 用于对热帖进行爆点分析，并从新的角度改写成原创内容。

当前版本支持：

- 读取原文、来源链接、目标平台、目标栏目和改写角度
- 分析原文 hook、structure、viral_points、target_audience
- 生成 rewritten_content
- 标注 source_attribution
- 使用 Simhash 计算相似度
- 输出 similarity_score、simhash_raw_score 和 similarity_method
- 当 similarity_score > 0.3 时返回 failed

## 输入

输入文件固定为：

```text
{job_dir}/input.json
示例：
{
  "content_id": "CNT-HOT-001",
  "job_id": "JOB-HOT-001",
  "source_url": "https://example.com/source-post-001",
  "source_text": "原始热帖正文",
  "target_platform": "xhs",
  "target_column": "经验干货",
  "rewrite_angle": "从大学生社团负责人的视角"
}

## 输出
输出文件固定为：
{job_dir}/hot_rewrite.json

输出字段包括：
original_analysis：原文爆点分析
rewritten_content：改写结果
similarity_score：归一化后相似度分数，用于判断是否通过
simhash_raw_score：Simhash 原始分数
similarity_method：相似度计算方式说明
source_attribution：来源标注
risk_notes：风险提示

## 相似度规则
任务要求改写结果相似度低于 30%。
当前版本使用 Simhash 计算文本相似度，并保留两个分数：
simhash_raw_score = 1 - distance / 64
similarity_score = max(0, (simhash_raw_score - 0.5) * 2)

原因：
Simhash 原始分数对中文同主题短文本偏高，0.5 附近常代表随机基线，不一定代表高度相似。因此当前版本保留原始分数，同时使用归一化后的 similarity_score 作为验收判断。

判断规则：
similarity_score < 0.3：success
similarity_score >= 0.3：failed

## 运行方式
在项目根目录 D:\Agent 下运行：
python skills/media-workflow/scripts/hot-rewrite/main.py --job-dir skills/media-workflow/scripts/hot-rewrite/test/fixtures/case_001

## 当前测试结果
case_001 已通过：
similarity_score < 0.3
source_attribution 非空
rewritten_content 与原文角度不同
original_analysis 中 viral_points 数量 ≥ 3

## 当前不足
当前版本仍为模板生成版，存在以下不足：
original_analysis 为规则模板，不是真正 LLM 分析
rewritten_content 为固定模板改写，不是真正根据原文灵活生成
目前只完成 1 条测试样例，任务书要求 5 篇真实爆款
尚未串联 risk-check
“不是同义替换”仍需要人工判断

## 后续优化
下一版建议：
接入 LLM 完成原文分析和改写
对 similarity_score > 0.3 的结果自动重写，最多重写 2 次
准备 5 篇真实热帖测试
将 rewritten_content 串联 risk-check
在 quality_review.md 中记录人工判断结果