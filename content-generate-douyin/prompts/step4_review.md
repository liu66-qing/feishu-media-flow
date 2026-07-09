你负责第 4 步：自我审查并修正文案。

检查 step3_body 草稿：
- 是否有真实场景代入感（不是空泛说教）。
- 是否有小红书味（emoji堆砌、符号装饰、"姐妹们"等），如有则删除。
- 是否有营销腔、虚构事实、夸大承诺。
- 正文是否 600-1500 个中文字符（少于600字必须扩写）。
- 结尾是否有编号建议（没有则补充）。
- hashtags 是否 3-6 个且以 # 开头。
- cover_lines 是否 2-4 行、每行 3-7 字。
- title_options 是否 exactly 3 个，selected_title 是否来自 title_options。

如有问题，直接修正。最终只输出 JSON object。

JSON 结构：
{
  "final": {
    "title_options": ["标题1", "标题2", "标题3"],
    "selected_title": "最终标题",
    "body": "修正后的600-1500字正文",
    "cover_lines": ["封面第一行", "封面第二行", "封面第三行"],
    "hashtags": ["#标签1", "#标签2", "#标签3"],
    "risk_notes": ["审查发现或已规避的风险；没有则为空数组"]
  },
  "review_score": {
    "authenticity": 0,
    "hook_strength": 0,
    "actionability": 0
  }
}
