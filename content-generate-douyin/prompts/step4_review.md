你负责第 4 步：自我审查并修正文案。

检查 step3_body 草稿：
- 是否有真实场景代入感（不是空泛说教）。
- 是否有小红书味（emoji堆砌、符号装饰、"姐妹们"等），如有则删除。
- 是否有营销腔、虚构事实、夸大承诺。
- 逐项核对正文里的数字、百分比、人物引语、亲历口吻和结果描述是否能在 input 与 materials 中找到依据。找不到依据时必须删除；场景只能写成明确的演示情境，不能冒充团队真实经历。
- 检查受众是否是准大一而不是社团运营者；检查AI焦虑是否在前半段转成具体学习或项目路径。
- 若材料含TYUT创新学社，结尾只引导进入招新群，不写虚假的名额稀缺和倒计时。
- 正文是否 600-1500 个中文字符（少于600字必须扩写）。
- 结尾是否有编号建议（没有则补充）。
- hashtags 是否 3-6 个且以 # 开头。
- cover_lines 是否 2-4 行、每行 3-7 字。
- title_options 是否 exactly 3 个，selected_title 是否来自 title_options。
- cards 是否为 4-7 张、每张只表达一个信息点，最后一张是否为 summary。
- cards 中是否出现真人出镜、风景素材、实拍视频、绿幕、外部图库等要求；如有，改为纯图文编辑海报表达。
- 每张卡是否包含 kind、section_label、title、body、highlight。

如有问题，直接修正。最终只输出 JSON object。

JSON 结构：
{
  "final": {
    "title_options": ["标题1", "标题2", "标题3"],
    "selected_title": "最终标题",
    "body": "修正后的600-1500字正文",
    "cover_lines": ["封面第一行", "封面第二行", "封面第三行"],
    "cards": [
      {
        "kind": "detail",
        "section_label": "方法一",
        "title": "卡片标题",
        "body": "卡片正文",
        "highlight": "重点结论"
      },
      {
        "kind": "summary",
        "section_label": "快速回顾",
        "title": "总结标题",
        "body": "01 第一条\n02 第二条\n03 第三条",
        "highlight": "收束建议"
      }
    ],
    "hashtags": ["#标签1", "#标签2", "#标签3"],
    "risk_notes": ["审查发现或已规避的风险；没有则为空数组"]
  },
  "review_score": {
    "authenticity": 0,
    "hook_strength": 0,
    "actionability": 0
  }
}
