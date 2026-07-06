# content-generate-wechat

## 功能说明

content-generate-wechat 用于根据选题、栏目、素材和参考链接生成公众号长文。

当前版本为模板生成版，主要用于验证：

- 输入输出结构
- JSON 格式
- Markdown 正文结构
- 与 risk-check 的串联流程

后续可接入 LLM，生成更完整、更自然的公众号文章。

## 输入

输入文件固定为：

```text
{job_dir}/input.json
示例：
{
  "content_id": "CNT-WECHAT-001",
  "job_id": "JOB-WECHAT-001",
  "topic": "Rust 语言在 2026 年的生态现状",
  "column": "技术观察",
  "materials": [
    "参考 rust-lang.org 官方博客",
    "GitHub trending 上 Rust 项目数据"
  ],
  "reference_urls": [
    "https://blog.rust-lang.org/",
    "https://github.com/trending/rust"
  ],
  "target_length": 1500
}

## 输出
输出文件固定为：
{job_dir}/content_generate_wechat.json
输出字段包括：
title_options：标题备选
selected_title：选中的标题
summary：摘要，目标不超过 120 字
body_md：Markdown 正文
sections：文章结构
cta：合规结尾引导
risk_notes：风险或核实提醒

运行日志输出到：
{job_dir}/logs.txt

如果运行失败，错误信息输出到：
{job_dir}/error.json

## 运行方式
在项目根目录 D:\Agent 下运行：
python skills/media-workflow/scripts/content-generate-wechat/main.py --job-dir skills/media-workflow/scripts/content-generate-wechat/test/fixtures/case_001

## 内容要求
公众号正文应满足：
Markdown 格式清晰
至少包含 3 个二级标题
摘要不超过 120 字
对不确定数据、趋势或年份信息标注「[需核实]」
避免绝对化、夸大化表达
CTA 不出现加微信、扫码领取、私信领等违规引流词
正文应有基本观点，不只是素材堆砌

## risk-check 串联
生成结果需要经过 risk-check。
串联测试路径：
test/fixtures/case_001_risk/
运行：
python skills/media-workflow/scripts/risk-check/main.py --job-dir skills/media-workflow/scripts/content-generate-wechat/test/fixtures/case_001_risk

当前结果：
risk_level = low
说明当前样例通过基础风险检查。

## 当前状态
当前版本已完成：
读取 input.json
输出 content_generate_wechat.json
生成 title_options、summary、body_md、sections、cta、risk_notes
完成 case_001 生成测试
完成 case_001_risk 串联 risk-check 测试

当前不足：
正文长度偏短，未达到 1200-1800 字
模板生成内容深度有限
尚未接入 LLM
尚未完成 3 个选题 × 3 次测试
尚未完成人工可读性反馈

## 后续优化
接入 LLM 生成正文
控制 body_md 在 1200-1800 字
增强观点密度和可读性
自动将生成内容送入 risk-check
扩展 3 个选题，每个选题跑 3 次
补充非技术读者反馈

当前版本已接入 LLM，并支持 WebFetch / WebSearch 工具调用；当 LLM 失败时会回退到模板生成。
当前版本已接入 LLM，并支持 WebFetch / WebSearch 工具调用；生成结果已通过 risk-check 串联测试。