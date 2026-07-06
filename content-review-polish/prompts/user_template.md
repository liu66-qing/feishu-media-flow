请审查并润色以下小红书文案。

原始标题：
{{title}}

原始正文：
{{body}}

原始标签：
{{hashtags}}

原始封面文字：
{{cover_text}}

润色强度：
{{polish_level}}

请输出 JSON，格式如下：

{
  "quality_score": {
    "hook": 3,
    "naturalness": 4,
    "depth": 3,
    "layout": 4,
    "overall": 3.5
  },
  "issues": [
    "问题说明"
  ],
  "polished": {
    "title": "润色后的标题",
    "body": "润色后的正文",
    "hashtags": [
      "#标签"
    ],
    "cover_text": "封面文字"
  },
  "changes_summary": "修改说明"
}

请只输出严格合法 JSON，不要输出 Markdown，不要输出解释文字。