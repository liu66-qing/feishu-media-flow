# hot-topic-collector 质量验证记录

## 测试时间

2026-07-20

## 测试对象

```text
hot-topic-collector/test/fixtures/job1
```

## 测试命令

```powershell
python hot-topic-collector/main.py --job-dir hot-topic-collector/test/fixtures/job1
```

## 测试结果

- 运行状态：success
- raw_count：58
- filtered_count：8
- llm_enabled：false
- llm_error：LLM_API_KEY is not set
- degraded_platforms：
  - douyin
  - xhs
- cache_used：true

## 验证结论

本轮测试验证了任务书中最关键的问题修复：

- 即使 LLM 不可用，也不会因为缺少 openai 包或 API Key 导致整个采集器不可运行。
- 即使抖音和小红书公开接口连接失败，微博已获得的实时素材仍然保留。
- 当实时热点与校园社团方向关联不足时，会使用明确标记为 `fallback` 的选题补足结果。
- 本次有效选题数达到 8 条，满足“每次有效运行提供 8 至 10 条相关选题”的最低要求。

## 注意事项

本次输出中包含 fallback 选题，说明它是降级结果，不是实时采集内容。

后续如果要提高真实素材比例，需要继续增加抖音、小红书和公众号的稳定公开数据源，减少 fallback 占比。
