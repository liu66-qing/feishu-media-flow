# platform-preference-profiler 测试日志

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 测试概览

| 项目 | 说明 |
|------|------|
| 模块 | platform-preference-profiler |
| 测试目录 | test-repository/platform-preference-profiler/ |
| 测试用例数 | 3 组（多平台画像生成） |
| 运行方式 | `python main.py --job-dir test/fixtures/<case>` |

## 测试用例

| 用例 | 场景 | 预期输出 |
|------|------|----------|
| case_001 | 小红书画像生成 | V2 Schema 五维度画像 |
| case_002 | 抖音画像生成 | V2 Schema 五维度画像 |
| case_003 | 微信公众号画像生成 | V2 Schema 五维度画像 |

## 产物说明

- `fixtures/` — 测试输入（input.json 含平台历史数据）
- `results/` — 测试输出（platform_preference_profiler.json + logs.txt）

## 验证要点

- [ ] 输出符合 V2 Schema（topic/lang/vis/struct/forbid 五维度）
- [ ] expires_at 为 7 天后时间戳
- [ ] 各维度数据非空且结构正确
- [ ] 不同平台画像有明显差异化

---

> Created by: 尹羿璇 | 2026-07-21
