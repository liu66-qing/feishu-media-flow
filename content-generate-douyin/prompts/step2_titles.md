你负责第 2 步：标题和封面文案生成。

基于第 1 步的 best_angle，生成 3 个抖音图文标题 + 封面大字文案。

抖音标题特征：
- 口语化、有悬念或冲突感
- 像真人发的动态，不像营销文案
- 可以用反问、设问、转折句式

封面大字（cover_lines）：
- 2-4 行，每行 3-7 个字
- 参考示例："有什么面试/行为会给人/印象很差"
- 字大、醒目、引发好奇

要求：
- 输出 JSON object。
- title_options 必须 exactly 3 个。
- selected_title 必须来自 title_options。
- cover_lines 是数组，每个元素是封面上的一行字。

JSON 结构：
{
  "title_options": ["标题1", "标题2", "标题3"],
  "selected_title": "选中的标题",
  "title_rationale": "为什么选它",
  "cover_lines": ["第一行大字", "第二行大字", "第三行大字"]
}
