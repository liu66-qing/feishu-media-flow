# risk-check 测试日志

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 测试概览

| 项目 | 说明 |
|------|------|
| 模块 | risk-check |
| 测试目录 | test-repository/risk-check/ |
| 测试用例数 | 20 组（覆盖各类风险场景） |
| 运行方式 | `python main.py --job-dir test/fixtures/<case>` |

## 测试用例分类

| 类别 | 用例数 | 场景 |
|------|--------|------|
| 正常内容 | 3 | 无风险内容，预期 low |
| 绝对化表达 | 4 | "最好""第一""唯一"等 |
| 引流词 | 3 | 微信/加V/私聊等 |
| 敏感行业 | 4 | 医疗/金融/教育等 |
| 政治敏感 | 3 | 政策/领导人等 |
| 混合风险 | 3 | 多类风险叠加 |

## 产物说明

- `fixtures/` — 测试输入（input.json 含 title + body + hashtags）
- `results/` — 测试输出（risk_check.json + logs.txt）
- `quality_review.md` — 质量评审报告

## 验证要点

- [ ] 风险等级判定正确（high/medium/low）
- [ ] hits 中每条含 word/type/location/context
- [ ] should_skip_hit 误报过滤生效（"第一次"不报警）
- [ ] LLM 审查关注点合理（llm_concerns 非空时）
- [ ] suggestions 给出可操作的替换建议

---

> Created by: 尹羿璇 | 2026-07-21
