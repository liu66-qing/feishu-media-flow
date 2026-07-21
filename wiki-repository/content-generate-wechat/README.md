# content-generate-wechat — 公众号文章生成 Skill

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 功能简介

根据选题、栏目、素材和参考链接生成公众号长文。支持 LLM 生成（含 WebFetch/WebSearch 工具调用），LLM 失败时自动降级到模板生成。

## 核心特性

- **LLM + 工具调用**：支持 WebFetch 抓取网页、WebSearch 搜索补充素材
- **弹性降级**：LLM 失败自动回退到模板生成，保证可用性
- **平台偏好画像**：V2 Schema 动态画像注入 system prompt
- **完整输出结构**：标题候选、正文 Markdown、分节结构、配图计划、CTA、风险提示

## 目录结构

```
content-generate-wechat/
├── main.py              ← 核心执行入口（618行）
├── SKILL.md             ← Skill 定义
├── requirements.txt     ← Python 依赖
├── prompts/
│   ├── system.md        ← 系统 prompt
│   ├── user_template.md ← 用户 prompt 模板
│   └── history/         ← Prompt 版本历史
└── test/
    ├── fixtures/        ← 测试输入
    └── results/         ← 测试输出
```

## 快速入门

```bash
pip install -r requirements.txt
# 配置 .env: LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
python main.py --job-dir <含 input.json 的目录>
```

## 依赖说明

| 依赖 | 说明 |
|------|------|
| openai >= 1.0.0 | LLM API 调用（含 tool calling） |
