# content-review-polish — 内容润色评审 Skill

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 功能简介

审查并润色小红书文案，是内容质量兜底模块。对原文标题、正文、排版进行评分，识别问题并输出润色后的内容。支持 LLM 润色，LLM 失败时降级到规则模板润色。

## 核心特性

- **四维评分**：hook（钩子）、naturalness（自然度）、depth（深度）、layout（排版）
- **问题识别**：标题钩子弱、营销腔、内容深度不足、排版不清晰
- **多级润色**：支持 light / medium / heavy 三种润色强度
- **弹性降级**：LLM 失败自动回退到规则模板润色

## 目录结构

```
content-review-polish/
├── main.py              ← 核心执行入口（333行）
├── SKILL.md             ← Skill 定义
├── requirements.txt     ← Python 依赖
├── prompts/
│   ├── system.md        ← LLM 系统 prompt
│   ├── user_template.md ← LLM 用户 prompt 模板
│   └── history/         ← Prompt 版本历史
└── test/
    ├── fixtures/        ← 测试输入
    └── results/         ← 测试输出
```

## 快速入门

```bash
pip install -r requirements.txt
python main.py --job-dir <含 input.json 的目录>
```

## 依赖说明

| 依赖 | 说明 |
|------|------|
| openai >= 1.0.0 | LLM API 调用 |
