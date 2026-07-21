# hot-topic-collector 开发者指南

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 1. 模块间数据交互

### 下游输出
```
hot-topic-collector → hot-topic-collector.json → hot-rewrite / app
```
采集的选题送入 hot-rewrite 改写，或由 app 直接调度。

## 2. 内部工作流
```
input.json (keywords + platforms)
  → collect_topics() — 微博/抖音/小红书 API 采集
  → dedupe_topics() — 去重
  → call_llm_filter() — LLM 智能筛选（失败降级到本地筛选）
  → hot-topic-collector.json
```

## 3. 测试指南
```bash
python main.py --job-dir test/fixtures/job1
```
测试产物：`hot-topic-collector.json`、`logs.txt`、`error.json`

## 4. 调试技巧
- `fetch_errors` 记录各平台采集错误，网络问题时可检查代理设置
- `raw_count` 为 0 且使用了种子选题时，说明所有 API 均失败
- `llm_enabled=false` 时查看 `llm_error` 了解降级原因
- `REQUEST_TIMEOUT` 默认 10 秒，网络慢时可调整
