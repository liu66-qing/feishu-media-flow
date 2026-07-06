# content-generate-douyin

## 功能说明

content-generate-douyin 用于根据选题生成 60-90 秒抖音短视频分镜脚本。

当前版本支持：

- 读取 topic、duration_target、style
- 输出 title、duration、hook、scenes、caption、hashtags、cover_text
- 自动生成 8-15 个场景
- 每个场景包含 voiceover、subtitle、visual、asset_hint
- 控制每个场景 duration 不超过 8 秒
- 控制总时长接近 duration_target
- 支持与 risk-check 串联测试

## 输入

输入文件固定为：

```text
{job_dir}/input.json

示例：
{
  "content_id": "CNT-DOUYIN-001",
  "job_id": "JOB-DOUYIN-001",
  "topic": "3个方法让社团招新效率更高",
  "duration_target": 75,
  "style": "口播 + 图文卡片"
}

输出

输出文件固定为：
{job_dir}/content_generate_douyin.json
输出字段包括：
title：视频标题
duration：总时长
style：视频风格
hook：开场钩子
scenes：分镜数组
caption：发布文案
hashtags：标签
cover_text：封面文字

每个 scene 包含：
index
duration
voiceover
subtitle
visual
asset_hint

运行方式

在项目根目录 D:\Agent 下运行：
python skills/media-workflow/scripts/content-generate-douyin/main.py --job-dir skills/media-workflow/scripts/content-generate-douyin/test/fixtures/case_001

验收规则

当前版本按任务书检查以下规则：
总时长 = duration_target ±5 秒
场景数 8-15 个
每个场景 duration ≤ 8 秒
第一幕有明显 hook
subtitle 比 voiceover 更精简
每个场景都有 asset_hint
输出内容通过 risk-check

当前测试结果

case_001 已完成测试：
duration = 75
scenes = 10
每个 scene duration ≤ 8
每个 scene 均包含 asset_hint
第一幕包含 hook
risk-check 串联结果为 low

当前不足

当前版本仍为模板生成版，存在以下不足：
未接入 LLM
内容结构较固定
尚未完成多人朗读测试
尚未测试 3/5 场景以上自然通顺
尚未扩展多个不同选题

后续优化

下一版建议：
接入 LLM，提升脚本自然度
根据不同 topic 动态生成场景
增加朗读测试记录
扩展至少 5 组 fixtures
自动串联 risk-check