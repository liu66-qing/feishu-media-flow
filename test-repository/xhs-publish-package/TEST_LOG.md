# xhs-publish-package 测试日志

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 测试概览

| 项目 | 说明 |
|------|------|
| 模块 | xhs-publish-package |
| 测试目录 | test-repository/xhs-publish-package/ |
| 单元测试 | 5 组 + 端到端测试 3 组 |
| 运行方式 | `python test/run_tests.py`（单元）/ `python main.py --job-dir e2e_test/test_XX`（端到端） |

## 单元测试用例

| 用例 | 场景 | 预期输出 |
|------|------|----------|
| test_01 | 正常场景（2图） | 全部文件正确生成 |
| test_02 | 空 assets | 无 assets 目录 |
| test_03 | 多图（4图） | 全部图片复制 |
| test_04 | 无 scheduled_at | checklist 显示"未设置" |
| test_05 | 图片缺失 | .missing 占位文件 |

## 端到端测试用例

| 用例 | 场景 | 来源 |
|------|------|------|
| e2e_test/test_01 | 社团招新（单图） | content-generate-xhs round3 |
| e2e_test/test_02 | 创业主题（3图） | content-generate-xhs round3 |
| e2e_test/test_03 | 图片缺失容错 | 模拟上游缺失 |

## 产物说明

- `test/fixtures/` — 单元测试输入
- `test/results/` — 单元测试输出
- `e2e_test/` — 端到端测试（含真实上游数据）
- `test/quality_review.md` — 质量评审报告
- `e2e_test/e2e_test_report.md` — 端到端测试报告

## 验证要点

- [ ] title.txt / body.txt / hashtags.txt 内容正确
- [ ] checklist.md 无 `{variable}` 残留
- [ ] assets/ 图片完整复制，缺失有 .missing 占位
- [ ] manifest.json 含 package_created_at
- [ ] 多次运行目录删除重建正常

---

> Created by: 尹羿璇 | 2026-07-21
