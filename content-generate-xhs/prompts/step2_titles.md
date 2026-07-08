你负责第 2 步：标题生成。

基于第 1 步的 best_angle 和 angles，生成 3 个小红书标题候选，并选择一个最适合正文展开的标题。

要求：
- 输出 JSON object。
- title_options 必须 exactly 3 个。
- selected_title 必须来自 title_options。
- 标题口语、具体、像真人会发的笔记。
- 避免夸张承诺、焦虑制造、营销腔。
- 不要使用“建议”“一定”“绝对”。
- 每个标题不超过 28 个中文字符。

JSON 结构：
{
  "title_options": ["标题1", "标题2", "标题3"],
  "selected_title": "从 title_options 中选择的标题",
  "title_rationale": "为什么选它"
}
