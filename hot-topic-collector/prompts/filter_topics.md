请从下面的热点列表中，筛选出最适合"大学生社团运营 / 校园新媒体 / 社团活动策划"方向二次创作的选题。

关键词：
{{keywords}}

最多输出 {{max_topics}} 条。

热点列表：
{{topics}}

筛选要求：

1. 优先选择能和大学生、社团、校园活动、招新、新媒体运营、内容策划、学生组织管理产生明确关联的热点。
2. 不要为了凑数选择完全无关的娱乐八卦。
3. 每条都要给出 0 到 1 的 relevance_score。
4. angle_suggestion 要具体说明可以从什么内容角度切入。
5. suggested_platform 只能是 xhs、douyin、weibo 之一。
6. 只输出 JSON，不要输出解释文字。

输出格式：

{
  "topics": [
    {
      "title": "热点标题",
      "source": "weibo",
      "source_url": "https://...",
      "heat_score": 85,
      "relevance_score": 0.8,
      "angle_suggestion": "可以从XX角度切入做小红书图文",
      "suggested_platform": "xhs"
    }
  ]
}