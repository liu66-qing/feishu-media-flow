# content-generate-douyin 测试日志

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 测试概览

| 项目 | 说明 |
|------|------|
| 模块 | content-generate-douyin |
| 测试目录 | test-repository/content-generate-douyin/ |
| 测试用例数 | 2 组（case_001 正常 + case_001_risk 风险） |
| 运行方式 | `python main.py --job-dir test/fixtures/case_001` |

## 测试用例

| 用例 | 场景 | 输入 | 预期输出 |
|------|------|------|----------|
| case_001 | 正常抖音内容生成 | topic + history + platform_profile | 3标题 + 正文 + 标签 + cards + cover_lines |
| case_001_risk | 含敏感内容的风险场景 | 含风险关键词的 topic | 正常生成（风险由 risk-check 检测） |

## 产物说明

- `fixtures/` — 测试输入（input.json + history + platform_profile）
- `results/` — 测试输出（content_generate_douyin.json + logs.txt）
- `quality_review.md` — 质量评审报告

## 验证要点

- [ ] cards 数组 4-7 张，每张含 kind/title/body/highlight
- [ ] 最后一张卡片 kind = "summary"
- [ ] cover_lines 非空且每行 ≤ 15 字
- [ ] hashtags 数量 3-8 个
- [ ] body 口语化、短句为主

---

> Created by: 尹羿璇 | 2026-07-21
