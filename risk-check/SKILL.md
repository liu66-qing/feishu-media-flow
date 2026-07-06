# risk-check

## 功能说明

risk-check 用于检查内容中的基础合规风险，是内容工作流的全局质检关卡。

当前版本支持：

- 广告法极限词检查，例如：最、第一、唯一、保证、100%
- 平台引流词检查，例如：加微信、私信领、扫码领取
- 敏感行业词检查，例如：医疗诊断、投资收益、考试包过
- 命中词位置、上下文和修改建议输出
- 基础误报过滤，例如：“第一次”“最后”不作为极限词风险处理

后续可接入 LLM，用于判断软性风险，例如夸大承诺、疑似软广、隐性引流等。

## 输入

输入文件固定为：

```text
{job_dir}/input.json
示例：
{
  "content_id": "CNT-20260705-001",
  "job_id": "JOB-20260705-001",
  "platform": "xhs",
  "title": "招新别只会摆摊",
  "body": "开学季社团招新，用这个方法保证转化率第一",
  "hashtags": ["#社团招新"]
}

## 输出
输出文件固定为：
{job_dir}/risk_check.json

运行日志输出到：
{job_dir}/logs.txt

如果运行失败，错误信息输出到：
{job_dir}/error.json

## 风险等级规则
low
满足任一情况：
没有命中风险词
仅命中 1-2 个平台引流词

medium
满足任一情况：
命中广告法极限词
命中 3 个及以上平台引流词
后续 LLM 判断存在 1-2 条软性风险

high
满足任一情况：
命中敏感行业词
命中政治敏感词
后续 LLM 判断存在 3 条及以上软性风险

## 词库位置
词库文件：
rules/forbidden_words.json

当前分类：
absolute_claims：广告法极限词
platform_risk：平台引流词
sensitive_domains：敏感行业词
political：政治敏感词

## 运行方式
在项目根目录 D:\Agent 下运行：
python skills/media-workflow/scripts/risk-check/main.py --job-dir skills/media-workflow/scripts/risk-check/test/fixtures/case_001
运行成功后，检查对应 case 目录下的：
risk_check.json
logs.txt

## 测试说明
测试数据位于：
test/fixtures/
本轮测试共 20 条：
case_001 到 case_010：正常内容，预期 low
case_011 到 case_020：风险内容，预期 medium、high 或命中 platform_risk
测试报告位于：
test/quality_review.md

## 当前测试结论
本轮 20 条测试全部通过。
正常内容 10 条，误报 0 条
风险内容 10 条，漏报 0 条
假阳性率：0%
假阴性率：0%

case_007 和 case_008 曾在 v1 中出现误报：
“第一次”被误判为命中“第一”
“最后”被误判为命中“最”
v2 已增加上下文过滤规则，修复以上问题。

## 后续优化
下一版可以加入 LLM 审查：
判断标题或正文是否存在夸大承诺
判断是否存在疑似软广
判断是否存在隐性引流
给出更自然的改写建议

LLM 输出应继续保持 JSON 格式，并写入：
{
  "llm_concerns": [],
  "suggestions": []
}