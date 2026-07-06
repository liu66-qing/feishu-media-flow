请根据以下原文进行爆款改写。

原文链接：
{{source_url}}

原文内容：
{{source_text}}

目标平台：
{{target_platform}}

目标栏目：
{{target_column}}

改写角度：
{{rewrite_angle}}

请输出 JSON，格式如下：

{
  "original_analysis": {
    "hook": "原文开头或标题的吸引点",
    "structure": "原文结构",
    "viral_points": [
      "爆点1",
      "爆点2",
      "爆点3"
    ],
    "target_audience": "目标读者"
  },
  "rewritten_content": {
    "title": "改写后的标题",
    "body": "改写后的正文",
    "hashtags": [
      "#标签"
    ]
  },
  "similarity_score": 0.22,
  "source_attribution": {
    "url": "原始链接",
    "note": "来源说明"
  },
  "risk_notes": []
}

请基于下面原文做爆款改写，但必须明显降低相似度。

原文：
{{source_text}}

来源链接：
{{source_url}}

目标平台：
{{target_platform}}

目标栏目：
{{target_column}}

只输出 JSON，格式如下：

{
  "rewritten_content": {
    "title": "改写后的标题",
    "body": "改写后的正文",
    "hashtags": ["#标签1", "#标签2", "#标签3"]
  }
}