你负责第 4 步：自我审查并修正文案。

检查 step3_body 草稿：
- 是否年轻、真诚、不油腻，像真人经验分享。
- 是否出现“建议”“一定”“绝对”。
- 是否有营销腔、夸大承诺、虚构事实、平台不友好表达。
- 正文是否 500-800 个中文字符。
- hashtags 是否 5-8 个且以 # 开头。
- cover_text 是否 10-12 个中文字符。
- title_options 是否 exactly 3 个，selected_title 是否来自 title_options。

如有问题，直接修正。最终只输出 JSON object。

JSON 结构：
{
  "final": {
    "title_options": ["标题1", "标题2", "标题3"],
    "selected_title": "最终标题",
    "body": "修正后的500-800字正文",
    "hashtags": ["#标签1", "#标签2", "#标签3", "#标签4", "#标签5"],
    "cover_text": "10到12字封面文案",
    "risk_notes": ["审查发现或已规避的风险；没有则为空数组"]
  },
  "review_score": {
    "hook_strength": 0,
    "authenticity": 0,
    "risk_control": 0
  }
}
