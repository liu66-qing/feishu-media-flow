# content-review-polish 开发者指南

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 1. 模块间数据交互

### 上游输入
```
content-generate-xhs/douyin → 生成内容 → content-review-polish
```
接收上游生成的文案（title/body/hashtags/cover_text）进行审查润色。

### 下游输出
```
content-review-polish → content_review_polish.json → risk-check
```
润色后的内容送入 risk-check 进行风险检测。

## 2. 内部工作流
```
input.json (original + polish_level)
  → polish_content_with_llm()
      → call_llm(JSON mode) → 评分+润色+修改摘要
  → 失败降级 → polish_content()
      → score_original() → find_issues()
      → polish_title() → polish_body() → polish_cover_text()
  → content_review_polish.json
```

## 3. 测试指南
```bash
python main.py --job-dir test/fixtures/case_001
```
测试产物：`content_review_polish.json`、`logs.txt`、`error.json`

## 4. 调试技巧
- `quality_score.overall` 低于 3 时检查 `issues` 列表定位具体问题
- `llm_enabled=false` 时表示 LLM 降级，查看 `llm_error` 了解原因
- medium/heavy 润色会自动拆段，观察 `polished.body` 的换行变化
