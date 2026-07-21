# content-generate-xhs 测试日志

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 测试概览

| 项目 | 说明 |
|------|------|
| 模块 | content-generate-xhs |
| 测试目录 | test-repository/content-generate-xhs/ |
| 测试用例数 | 2 组（case_001 正常 + case_001_risk 风险） |
| 运行方式 | `python main.py --job-dir test/fixtures/case_001` |

## 测试用例

| 用例 | 场景 | 输入 | 预期输出 |
|------|------|------|----------|
| case_001 | 正常小红书内容生成 | topic + history + platform_profile | 3标题 + 正文 + 标签 + 封面文案 |
| case_001_risk | 含敏感内容的风险场景 | 含风险关键词的 topic | 正常生成（风险由 risk-check 检测） |

## 产物说明

- `fixtures/` — 测试输入（input.json + history + platform_profile）
- `results/` — 测试输出（content_generate_xhs.json + logs.txt）
- `quality_review.md` — 质量评审报告

## 验证要点

- [ ] JSON mode 输出格式正确（titles 数组长度 = 3）
- [ ] body 含 emoji、分段符合小红书风格
- [ ] hashtags 数量在 5-10 个范围
- [ ] cover_text 不超过 12 字
- [ ] 画像注入生效（有画像 vs 无画像输出差异明显）

---

> Created by: 尹羿璇 | 2026-07-21
