请根据以下信息生成抖音短视频分镜脚本。

选题：
{{topic}}

目标时长：
{{duration_target}}

风格：
{{style}}

请输出 JSON，格式如下：

{
  "title": "视频标题",
  "duration": 75,
  "style": "口播 + 图文卡片",
  "hook": "开场钩子",
  "scenes": [
    {
      "index": 1,
      "duration": 6,
      "voiceover": "口播内容",
      "subtitle": "屏幕字幕",
      "visual": "画面描述",
      "asset_hint": "素材建议"
    }
  ],
  "caption": "发布文案",
  "hashtags": [
    "#标签"
  ],
  "cover_text": "封面文字"
}

请只输出严格合法 JSON，不要输出 Markdown，不要输出解释文字。

注意：voiceover、subtitle、visual、asset_hint 中不要使用英文双引号 "，如需引用请使用中文引号「」。