# platform-metrics-collector

采集并标准化公众号、抖音和小红书已发布内容在 1h、6h、24h、72h 的表现快照。

统一入口：

```bash
python platform-metrics-collector/main.py --job-dir <job-dir>
```

`input.json` 必须包含 `content_id`、`platform` 和 `checkpoint`。指标可以通过 `metrics` 人工导入，或配置 `metrics_endpoint` 从自有合规接口读取。没有真实数据时输出 `data_status=unavailable`，不得用零值冒充真实表现。

输出 `platform-metrics-collector.json`，快照统一包含曝光、阅读/播放、点赞、评论、收藏、转发和涨粉，并保留 `metrics_source`、`data_status` 和实验变量。
