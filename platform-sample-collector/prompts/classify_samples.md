请对下面的平台内容样本做质量筛选和偏好标注。

关键词：
{{keywords}}

样本：
{{samples}}

要求：

1. 只保留与大学生、校园、社团、招新、新媒体、活动运营相关的内容。
2. 不要保留重复、低质量、无来源、明显无关的样本。
3. 保留原始 platform、source_url、published_at、data_status。
4. data_status 不能被篡改，不能把 cache、fixture、fallback 写成 live。
5. 只输出严格 JSON，不要输出解释文字。

输出格式：

{
  "samples": [
    {
      "platform": "xhs",
      "title": "标题",
      "summary": "摘要",
      "cover": "封面地址",
      "hashtags": ["#标签"],
      "published_at": "发布时间",
      "source": "来源",
      "source_url": "https://...",
      "metrics": {
        "likes": 0,
        "comments": 0,
        "shares": 0,
        "favorites": 0,
        "views": 0
      },
      "quality_status": "valid",
      "quality_score": 0.8,
      "data_status": "live",
      "collected_at": "2026-07-20T00:00:00Z"
    }
  ]
}
