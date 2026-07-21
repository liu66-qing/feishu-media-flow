# content-review-polish 测试日志

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 测试概览

| 项目 | 说明 |
|------|------|
| 模块 | content-review-polish |
| 测试目录 | test-repository/content-review-polish/ |
| 测试用例数 | 2 组（正常内容 + 低质量内容润色） |
| 运行方式 | `python main.py --job-dir test/fixtures/<case>` |

## 测试用例

| 用例 | 场景 | 预期输出 |
|------|------|----------|
| case_001 | 正常内容审核润色 | 四维评分 + 润色后内容 |
| case_002 | 低质量内容润色 | 评分偏低 + 大幅润色修改 |

## 产物说明

- `fixtures/` — 测试输入（input.json 含 title + body）
- `results/` — 测试输出（content_review_polish.json + logs.txt）
- `quality_review.md` — 质量评审报告

## 验证要点

- [ ] 四维评分（hook/naturalness/depth/layout）各 1-10 分
- [ ] polished_body 比原始 body 质量提升
- [ ] LLM 模式与规则模式均能正常工作
- [ ] suggestions 给出具体可操作的修改建议

---

> Created by: 尹羿璇 | 2026-07-21
