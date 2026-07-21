# hot-rewrite 开发者指南

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 1. 模块间数据交互

### 上游输入
```
hot-topic-collector → 热点选题 → hot-rewrite
```
接收热点原文进行改写。

### 下游输出
```
hot-rewrite → hot_rewrite.json → content-generate-xhs/douyin
```
改写后的内容送入对应平台的内容生成模块进一步加工。

## 2. 内部工作流
```
input.json (source_text + rewrite_angle)
  → call_rewrite_llm() — LLM 分析+改写
  → similarity(source, rewritten) — Simhash 校验
  → score > 0.3? → build_retry_hint() → 重试(≤2次)
  → hot_rewrite.json
```

## 3. 测试指南
```bash
python main.py --job-dir test/fixtures/case_001
python main.py --job-dir test/fixtures/case_001_risk  # 串联 risk-check
```
测试产物：`hot_rewrite.json`、`logs.txt`、`error.json`

## 4. 调试技巧
- `similarity_score` 接近 0.3 边界时可调整 `MAX_REWRITE_RETRIES` 增加重试次数
- `tokenize_zh()` 使用 9-14 字滑窗分词，可调整尺寸范围
- 改写角度不够差异化时，在 `rewrite_angle` 中提供更具体的指引
