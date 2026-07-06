请根据以下信息生成一篇公众号长文。

选题：
{{topic}}

栏目：
{{column}}

素材：
{{materials}}

参考链接：
{{reference_urls}}

目标字数：
{{target_length}}

请输出 JSON，格式如下：

{
  "title_options": [
    "标题1",
    "标题2",
    "标题3"
  ],
  "selected_title": "最终选择的标题",
  "summary": "不超过120字的摘要",
  "body_md": "# 标题\n\n## 引言\n\n正文内容",
  "sections": [
    {
      "heading": "小标题",
      "brief": "本节摘要"
    }
  ],
  "cta": "合规的结尾引导",
  "risk_notes": [
    "需要人工核实或注意的地方"
  ]
}

请只输出严格合法 JSON，不要输出 ```json 代码块，不要输出任何解释。
特别注意：body_md、summary、cta、risk_notes 等字符串内容中不要使用英文双引号 "，如需强调请使用中文引号「」。

本次请将 body_md 控制在 1000 到 1400 个中文字符，优先保证 JSON 完整合法。

body_md 中不要使用 Markdown 表格，不要使用加粗符号 **，列表项尽量使用普通句子表达。