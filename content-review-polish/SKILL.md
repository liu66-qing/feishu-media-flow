# content-review-polish

## 功能说明

content-review-polish 用于审查并润色小红书文案，是内容质量兜底 Skill。

当前版本支持：

- 对原文标题、正文、排版进行基础评分
- 输出 hook、naturalness、depth、layout、overall 分数
- 识别标题钩子弱、营销腔、内容深度不足等问题
- 根据 polish_level 进行轻量或中等润色
- 输出 polished title、body、hashtags、cover_text
- 输出 changes_summary
- 支持与 risk-check 串联测试

## 输入

输入文件固定为：

```text
{job_dir}/input.json

示例：
{
  "content_id": "CNT-POLISH-001",
  "job_id": "JOB-POLISH-001",
  "original": {
    "title": "分享一下社团招新",
    "body": "社团招新真的很重要，大家一定要赶紧准备。这个方法绝对有用，可以保证效果变好。",
    "hashtags": ["#社团招新", "#大学生活"],
    "cover_text": ""
  },
  "polish_level": "medium"
}

输出

输出文件固定为：
{job_dir}/content_review_polish.json

输出字段包括：
quality_score
issues
polished
changes_summary

运行方式

在项目根目录 D:\Agent 下运行：
python skills/media-workflow/scripts/content-review-polish/main.py --job-dir skills/media-workflow/scripts/content-review-polish/test/fixtures/case_001

当前测试结果

case_001 已完成测试：
原文 overall = 2.5
识别出标题钩子弱、营销腔、内容深度不足
polished 与 original 有明显差异
润色后通过 risk-check，risk_level = low

当前不足

当前版本仍为规则模板版，存在以下不足：
尚未接入 LLM
评分规则较简单
只测试 1 条 badcase
尚未覆盖 light / heavy 多种润色强度
保留主旨仍需要人工判断

后续优化

下一版建议：
接入 LLM 进行更自然的润色
准备 5 条明显差的原稿进行评分测试
测试 light、medium、heavy 三种模式
串联 risk-check
在 quality_review.md 中补充人工判断记录