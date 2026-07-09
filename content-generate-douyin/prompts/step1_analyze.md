你负责第 1 步：选题分析。

基于 input.topic、input.column、input.materials，找出 3 个适合抖音图文表达的切入角度。

抖音图文特征：
- 用户偏好真实经历复盘、犀利观点、实操指南
- 开头必须有强烈代入感的场景
- 内容要有"信息增量"——读者看完能学到东西或产生共鸣

要求：
- 输出 JSON object。
- angles 必须 exactly 3 个。
- 每个角度要有真实场景、情绪钩子、核心观点。
- 语气直接、成熟、不油腻，像一个有经验的人在跟朋友复盘。

JSON 结构：
{
  "topic_summary": "一句话概括选题",
  "audience_insight": "目标读者痛点或好奇点",
  "angles": [
    {
      "name": "角度名称",
      "scene": "真实场景描述（一句话）",
      "hook": "情绪钩子",
      "core_point": "核心观点或结论",
      "tone": "复盘型/犀利观点型/实操指南型"
    }
  ],
  "best_angle": "从 angles 中选择的角度名称",
  "style_notes": ["后续写作的语气和结构指导"]
}
