# hot-topic-collector 测试日志

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 测试概览

| 项目 | 说明 |
|------|------|
| 模块 | hot-topic-collector |
| 测试目录 | test-repository/hot-topic-collector/ |
| 测试用例数 | 1 组（job1 多平台采集） |
| 运行方式 | `python main.py --job-dir test/fixtures/job1` |

## 测试用例

| 用例 | 场景 | 预期输出 |
|------|------|----------|
| job1 | 多平台热点采集 + LLM 筛选 | 筛选后的热点列表（含来源平台、热度、改写标题） |

## 产物说明

- `fixtures/` — 测试输入（input.json + hot-topic-collector.json 配置）
- `results/` — 测试输出（hot_topic_collector.json + logs.txt）

## 验证要点

- [ ] 采集覆盖微博/抖音/小红书三个平台
- [ ] LLM 筛选后保留与校园相关的热点
- [ ] 每条热点含 source_platform、title、reason 字段
- [ ] API 不可用时种子兜底机制正常触发
- [ ] 输出按热度排序

---

> Created by: 尹羿璇 | 2026-07-21
