# video-generate 测试日志

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 测试概览

| 项目 | 说明 |
|------|------|
| 模块 | video-generate |
| 测试目录 | test-repository/video-generate/ |
| 测试用例数 | 1 组（卡片包生成） |
| 运行方式 | `python main.py --job-dir test/fixtures/job1` |

## 测试用例

| 用例 | 场景 | 预期输出 |
|------|------|----------|
| job1 | 抖音图文卡片包生成 | 封面 + 正文卡 + 总结卡 PNG |

## 产物说明

- `fixtures/` — 测试输入（input.json + error.json）
- `output/` — 渲染后的卡片图片（card_XX.png）
- `render/` — 每张卡的渲染输入（XX/input.json）

## 验证要点

- [ ] 卡片总数 = 1封面 + N正文 + 1总结
- [ ] card_paths 有序且文件存在
- [ ] 最后一张卡片 role = "summary"
- [ ] visual_style 整组一致
- [ ] image-compose 模块动态加载成功

---

> Created by: 尹羿璇 | 2026-07-21
