# risk-check 开发者指南

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 1. 模块间数据交互

### 上游输入
```
content-generate-* / content-review-polish → 生成内容 → risk-check
```

### 下游输出
```
risk-check → risk_check.json → app (决定是否通过审核)
```

## 2. 内部工作流
```
input.json (title + body + hashtags)
  → scan_forbidden_words() — 本地规则扫描
  → run_llm_review() — LLM 语义审查（可选）
  → judge_risk_level() — 综合判定
  → build_suggestions() — 生成建议
  → risk_check.json
```

## 3. 测试指南
```bash
python main.py --job-dir test/fixtures/case_001
```
20 组测试覆盖：正常内容、绝对化表达、引流词、敏感行业、政治敏感等。
测试产物：`risk_check.json`、`logs.txt`、`error.json`

## 4. 调试技巧
- `hits` 中每条含 `context` 字段可定位命中上下文
- `should_skip_hit()` 控制误报过滤，新增安全词在此函数
- 新增禁用词编辑 `rules/forbidden_words.json`
- `llm_enabled=false` 时仅本地规则生效，查看 `llm_error` 了解原因
