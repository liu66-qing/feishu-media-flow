# content-generate-douyin

## 功能

根据选题生成抖音图文内容，不生成短视频分镜、配音或时长数据。

生成流程分为选题分析、标题与封面、正文与卡片、质量审查四步。最终结果包含：

- 3 个标题候选和 1 个最终标题。
- 2–4 行封面大字。
- 适合手动发布抖音图文的正文和标签。
- 4–7 张有序正文卡片，最后一张固定为总结卡。

卡片只描述编辑海报式图文内容，不要求真人出镜、自然风景、实拍视频、绿幕、手机截图或外部图库。

## 输入

`{job_dir}/input.json`：

```json
{
  "content_id": "CNT-xxx",
  "job_id": "JOB-xxx",
  "platform": "douyin",
  "topic": "社团招新现场如何提高转化",
  "column": "校园运营",
  "materials": []
}
```

## 输出

结果写入 `{job_dir}/content-generate-douyin.json`，主要字段为：

- `selected_title`
- `body`
- `hashtags`
- `cover_lines`
- `cover_text`
- `cards`
- `risk_notes`

每张 `cards` 数据包含 `kind`、`section_label`、`title`、`body`、`highlight`。此结果交给兼容名为 `video-generate` 的卡片包生成器渲染为 PNG，最终由用户手动上传抖音。
