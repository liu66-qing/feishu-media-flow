# content-generate-wechat 测试日志

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 测试概览

| 项目 | 说明 |
|------|------|
| 模块 | content-generate-wechat |
| 测试目录 | test-repository/content-generate-wechat/ |
| 测试用例数 | 2 组（case_001 正常 + case_001_risk 风险） |
| 运行方式 | `python main.py --job-dir test/fixtures/case_001` |

## 测试用例

| 用例 | 场景 | 输入 | 预期输出 |
|------|------|------|----------|
| case_001 | 正常公众号内容生成 | topic + history + platform_profile | 标题 + 正文 + 摘要 |
| case_001_risk | 含敏感内容的风险场景 | 含风险关键词的 topic | 正常生成（风险由 risk-check 检测） |

## 产物说明

- `fixtures/` — 测试输入（input.json + history + platform_profile）
- `results/` — 测试输出（content_generate_wechat.json + logs.txt）
- `quality_review.md` — 质量评审报告

## 验证要点

- [ ] title 简洁有力（≤ 30 字）
- [ ] body 结构完整（引言 + 正文分段 + 结尾引导）
- [ ] WebFetch/WebSearch 工具调用成功（有联网数据引用）
- [ ] 弹性降级：API Key 缺失时回退到模板生成
- [ ] digest 摘要 ≤ 120 字

---

> Created by: 尹羿璇 | 2026-07-21
