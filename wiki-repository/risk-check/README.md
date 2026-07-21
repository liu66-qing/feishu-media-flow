# risk-check — 风险检测 Skill

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 功能简介

对生成的内容进行多层级风险检测：本地禁用词扫描 + LLM 语义审查，输出风险等级和修改建议。

## 核心特性

- **双引擎检测**：本地规则扫描 + LLM 语义审查
- **四级风险分类**：absolute_claims / platform_risk / sensitive_domains / political
- **三级风险等级**：high / medium / low
- **智能跳过**：上下文感知的误报过滤（如"第一次"中的"第一"不报）
- **修改建议**：针对每个命中词给出具体替换建议

## 目录结构

```
risk-check/
├── main.py                  ← 核心执行入口（288行）
├── SKILL.md                 ← Skill 定义
├── requirements.txt         ← Python 依赖
├── rules/
│   └── forbidden_words.json ← 禁用词规则库
├── prompts/
│   ├── system.md            ← LLM 审查系统 prompt
│   ├── user_template.md     ← LLM 审查用户 prompt
│   └── history/             ← Prompt 版本历史
└── test/
    ├── fixtures/            ← 测试输入（20组）
    └── results/             ← 测试输出
```

## 快速入门

```bash
pip install -r requirements.txt
python main.py --job-dir <含 input.json 的目录>
```

## 依赖说明

| 依赖 | 说明 |
|------|------|
| openai >= 1.0.0 | LLM API 调用（语义审查） |
