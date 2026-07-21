# platform-sample-collector

## 功能说明

platform-sample-collector 用于采集公众号、抖音、小红书三个平台的高表现内容样本，并整理成结构统一的平台样本库。

该 skill 的重点不是生成内容，而是为后续平台偏好分析提供真实、可追溯、可清洗的素材样本。

## 输入

输入文件固定为：

```text
{job_dir}/input.json
```

示例：

```json
{
  "content_id": "SAMPLE-001",
  "job_id": "JOB-SAMPLE-001",
  "platforms": ["wechat", "douyin", "xhs"],
  "keywords": ["大学生", "社团", "校园", "招新", "新媒体"],
  "max_samples": 30,
  "source_feeds": {
    "wechat": ["https://example.com/wechat-feed.json"],
    "douyin": [],
    "xhs": []
  },
  "samples": []
}
```

## 输出

输出文件固定为：

```text
{job_dir}/platform-sample-collector.json
```

输出字段包括：

- `status`
- `collected_at`
- `platforms`
- `samples`
- `raw_count`
- `valid_count`
- `by_platform`
- `fetch_errors`
- `degraded_platforms`
- `cache_used`
- `notes`

每条 sample 包含：

- `platform`
- `title`
- `summary`
- `cover`
- `hashtags`
- `published_at`
- `source`
- `source_url`
- `metrics`
- `quality_status`
- `quality_score`
- `data_status`
- `collected_at`

## 数据状态

必须明确区分素材来源状态：

- `live`：本次实时采集
- `cache`：历史缓存
- `fixture`：测试样本
- `fallback`：降级兜底
- `unknown`：来源状态未明确

不允许把 `cache`、`fixture` 或 `fallback` 冒充为 `live`。

## 清洗规则

当前版本会过滤：

- 空标题
- 重复来源链接或重复标题
- 与校园、社团、招新、新媒体、活动运营相关性过低的内容
- 结构信息不足导致 `quality_score < 0.35` 的内容

## 运行方式

在 `feishu-media-flow` 根目录运行：

```bash
python platform-sample-collector/main.py --job-dir platform-sample-collector/test/fixtures/job1
```

## 当前状态

当前版本已完成独立运行接口、公开 JSON/RSS feed 解析、输入样本归一化、历史缓存读取、去重清洗、质量评分和平台降级说明。

真实平台账号或私有采集接口需要后续由项目管理员配置到 `source_feeds` 或缓存文件中。
