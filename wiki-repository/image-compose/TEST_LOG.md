# image-compose 测试日志

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 测试概览

| 项目 | 说明 |
|------|------|
| 模块 | image-compose |
| 测试目录 | test-repository/image-compose/ |
| 测试用例数 | 10+ 组（覆盖 9 套封面模板 + 1 套卡片模板） |
| 运行方式 | `python main.py --job-dir test/fixtures/<case>` |

## 测试用例

| 用例 | 场景 | 预期输出 |
|------|------|----------|
| cover-01 ~ cover-09 | 9 套封面模板渲染 | PNG 封面图 |
| card-01 | 正文卡片模板渲染 | PNG 卡片图 |
| ai-bg 系列 | DashScope AI 背景生成 | AI 背景封面图 |
| v2 系列 | V2 版本模板变量测试 | 渲染结果对比 |

## 产物说明

- `fixtures/` — 测试输入（input.json + 模板变量）
- `expected/` — 预期输出基准
- `results/` — 实际测试输出
- `run_tests.py` — 批量测试脚本
- `run_v2_test.py` — V2 模板专用测试
- `run_v2_ai_test.py` — AI 背景模式测试
- `quality_review.md` — 质量评审报告

## 验证要点

- [ ] 模板变量正确替换（title/subtitle/body 等）
- [ ] 输出尺寸符合 output_size 设定（默认 1080×1350）
- [ ] AI 背景模式正常调用 DashScope API
- [ ] 模板降级：AI 失败时回退到纯色背景
- [ ] Playwright 截图无渲染异常

---

> Created by: 尹羿璇 | 2026-07-21
