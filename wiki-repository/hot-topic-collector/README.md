# hot-topic-collector — 热点采集 Skill

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 功能简介

从微博、抖音、小红书等平台采集热门话题，结合关键词过滤和 LLM 智能筛选，输出与校园社团运营相关的高质量选题建议。

## 核心特性

- **多平台采集**：微博（Ajax API）、抖音/小红书（VVHAN API）
- **LLM 智能筛选**：根据关键词相关性、热度排序，输出选题建议
- **本地降级**：LLM 不可用时使用关键词匹配本地筛选
- **种子选题兜底**：所有 API 失败时使用内置的 10 条种子选题
- **去重 + 归一化**：自动去重，热度分数归一化到 1-100

## 目录结构

```
hot-topic-collector/
├── main.py                  ← 核心执行入口（383行）
├── SKILL.md                 ← Skill 定义
├── requirements.txt         ← Python 依赖
├── prompts/
│   └── filter_topics.md     ← LLM 筛选 prompt
└── test/fixtures/job1/      ← 测试数据
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
| requests | HTTP 请求（微博/VVHAN API） |
