# hot-topic-collector

## 功能说明

hot-topic-collector 用于采集公开热点，并筛选出适合"大学生社团运营 / 校园新媒体"方向创作的选题。

当前版本支持：

- 按 `platforms` 采集微博、抖音、小红书热点
- 微博使用 `https://weibo.com/ajax/side/hotSearch`
- 抖音、小红书优先使用公开聚合热点接口
- 单个平台抓取失败不影响其他平台
- 网络请求超时 10 秒
- 使用 LLM 根据关键词筛选热点并生成内容切入角度
- LLM 不可用时使用本地关键词评分兜底

## 输入

输入文件固定为：

```text
{job_dir}/input.json
```

示例：

```json
{
  "content_id": "HOTCOL-xxx",
  "job_id": "JOB-xxx",
  "keywords": ["大学生", "社团", "运营", "校园", "新媒体"],
  "platforms": ["weibo", "douyin", "xhs"],
  "max_topics": 10
}
```

## 输出

输出文件固定为：

```text
{job_dir}/hot-topic-collector.json
```

输出字段包括：

- `collected_at`：采集时间，UTC ISO 格式
- `topics`：筛选后的热点选题
- `raw_count`：原始热点数量
- `filtered_count`：筛选后热点数量
- `llm_enabled`：是否成功使用 LLM
- `llm_error`：LLM 错误信息，成功时为空
- `fetch_errors`：各平台采集失败信息

每条 topic 包含：

- `title`
- `source`
- `source_url`
- `heat_score`
- `relevance_score`
- `angle_suggestion`
- `suggested_platform`

失败时写入：

```text
{job_dir}/error.json
```

格式：

```json
{
  "status": "error",
  "generated_at": "ISO时间",
  "error": "错误信息"
}
```

## 依赖

```text
requests
openai
```

## 环境变量

LLM 筛选通过以下环境变量配置：

```text
LLM_API_KEY
LLM_BASE_URL
LLM_MODEL
```

## 运行方式

在项目根目录运行：

```bash
python hot-topic-collector/main.py --job-dir hot-topic-collector/test/fixtures/job1
```

## 当前状态

当前版本已完成 Skill 独立运行接口、公开热点采集、LLM 筛选、本地兜底和测试 fixture。