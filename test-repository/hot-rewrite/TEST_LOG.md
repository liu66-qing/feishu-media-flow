# hot-rewrite 测试日志

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 测试概览

| 项目 | 说明 |
|------|------|
| 模块 | hot-rewrite |
| 测试目录 | test-repository/hot-rewrite/ |
| 测试用例数 | 2 组（正常改写 + 低相似度重试） |
| 运行方式 | `python main.py --job-dir test/fixtures/<case>` |

## 测试用例

| 用例 | 场景 | 预期输出 |
|------|------|----------|
| case_001 | 正常热点改写 | 改写后内容 + Simhash 相似度 ≤ 0.3 |
| case_002 | 改写相似度过高 | 自动重试（≤2次）直到相似度达标 |

## 产物说明

- `fixtures/` — 测试输入（input.json 含原始热点内容）
- `results/` — 测试输出（hot_rewrite.json + logs.txt）
- `quality_review.md` — 质量评审报告

## 验证要点

- [ ] 改写后 Simhash 相似度 ≤ 0.3 阈值
- [ ] 保留核心信息但表达方式完全不同
- [ ] 自动重试机制正常（retry_count 字段记录）
- [ ] 改写后内容通顺、无乱码

---

> Created by: 尹羿璇 | 2026-07-21
