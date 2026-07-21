# content-generate-douyin — 抖音图文内容生成 Skill

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 功能简介

根据选题和素材，通过 4 步 LLM Pipeline 生成抖音图文笔记内容（标题、正文、话题标签、封面大字、4-7 张有序图文卡片）。是社团自媒体工作流中抖音专线的核心内容生成模块。

## 核心特性

- **4-Step LLM Pipeline**：分析 → 标题 → 正文卡片 → 审查，逐步控制质量
- **JSON Mode + 自动重试**：强制结构化输出，解析失败自动重试
- **抖音专属卡片**：生成 4-7 张有序图文卡片，最后一张为总结卡
- **平台偏好画像**：支持 V2 Schema 动态画像注入，7 天过期自动降级
- **硬指标校验**：标题数、正文字数、标签格式、卡片数量等自动验证

## 目录结构

```
content-generate-douyin/
├── main.py              ← 核心执行入口
├── SKILL.md             ← Skill 定义与规范
├── requirements.txt     ← Python 依赖
├── prompts/
│   ├── step1_analyze.md ← 选题分析 prompt
│   ├── step2_titles.md  ← 标题+封面大字 prompt
│   ├── step3_body.md    ← 正文+卡片 prompt
│   ├── step4_review.md  ← 审查修复 prompt
│   ├── system.md        ← 系统 prompt
│   ├── user_template.md ← 用户 prompt 模板
│   └── history/         ← Prompt 版本历史
└── test/
    ├── fixtures/        ← 测试输入
    └── results/         ← 测试输出
```

## 快速入门

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量（.env）
# LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

# 3. 运行
python main.py --job-dir <含 input.json 的目录>
```

## 依赖说明

| 依赖 | 说明 |
|------|------|
| openai >= 1.0.0 | LLM API 调用 |
| Python >= 3.10 | 类型注解支持 |
