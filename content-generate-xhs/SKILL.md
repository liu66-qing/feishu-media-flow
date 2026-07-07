---
name: "content-generate-xhs"
description: "基于选题和素材生成小红书笔记文案，包括标题、正文、话题标签和封面文案"
---

# content-generate-xhs - 小红书图文文案生成

## 概述

本 Skill 是社团自媒体工作流系统中小红书专线的核心模块，负责根据选题和素材自动生成符合小红书平台风格的图文笔记文案。

## 功能定位

- 基于输入的选题和素材，生成高质量的小红书笔记文案
- 输出包含标题候选、正文、话题标签和封面文案
- 语言风格年轻、真诚、有干货，符合小红书平台调性

## 职责边界

- ✅ 标题生成 (3个候选)
- ✅ 正文生成 (500-800字)
- ✅ 话题标签 (5-8个)
- ✅ 封面文案
- ❌ 不做风险审查（交给 risk-check）
- ❌ 不做图片生成（交给 image-compose）

## 工作流程

1. 读取 `{job_dir}/input.json` 获取输入数据
2. 加载 `prompts/system.md` 系统提示词
3. 加载 `prompts/user_template.md` 用户提示词模板
4. 填充用户提示词模板，构建完整提示词
5. 调用 LLM 生成内容
6. 解析 LLM 返回的 JSON 结果
7. 写入 `{job_dir}/content-generate-xhs.json`
8. 记录日志到 `{job_dir}/logs.txt`

## 输入规范

**文件**: `{job_dir}/input.json`

```json
{
  "content_id": "CNT-20260705-001",
  "job_id": "JOB-20260705-001",
  "topic": "开学季社团招新如何提高报名转化率",
  "column": "经验干货",
  "materials": [
    "社团招新最大痛点是路过的人不了解社团在做什么",
    "去年我们尝试了做一个试玩体验区，转化率提升 3 倍"
  ],
  "brand": {
    "tone": "年轻、真诚、不油腻",
    "audience": "大学生"
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| content_id | string | 是 | 内容唯一标识 |
| job_id | string | 是 | 任务唯一标识 |
| topic | string | 是 | 选题主题 |
| column | string | 否 | 栏目分类，如"经验干货" |
| materials | array | 否 | 参考素材列表 |
| brand | object | 否 | 品牌调性配置 |
| brand.tone | string | 否 | 语气风格 |
| brand.audience | string | 否 | 目标受众 |

## 输出规范

**文件**: `{job_dir}/content-generate-xhs.json`

```json
{
  "status": "success",
  "timestamp": "2026-07-05T20:30:00+08:00",
  "content_id": "CNT-20260705-001",
  "data": {
    "title_options": [
      "招新别只会摆摊！3个方法翻倍转化",
      "社团招新做对这一件事，报名爆棚",
      "亲测有效｜社团招新转化率提升3倍"
    ],
    "selected_title": "招新别只会摆摊！3个方法翻倍转化",
    "body": "开学季到了...(500-800字)",
    "hashtags": ["#社团招新", "#大学生活", "#社团运营", "#校园干货", "#招新技巧"],
    "cover_text": "招新转化翻倍",
    "risk_notes": []
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| status | string | "success" 或 "error" |
| timestamp | string | ISO 8601 格式时间戳 |
| content_id | string | 内容唯一标识 |
| data.title_options | array | 3个标题候选，每个12-25字 |
| data.selected_title | string | 默认选中的标题 |
| data.body | string | 正文内容，500-800字 |
| data.hashtags | array | 5-8个话题标签 |
| data.cover_text | string | 封面文案，10-12字 |
| data.risk_notes | array | 风险提示（通常为空） |

## 错误处理

| 错误场景 | 处理方式 | 输出 |
|---------|---------|------|
| 缺少必填字段 | 抛出 ValueError | error.json |
| 输入文件不存在 | 捕获 FileNotFoundError | error.json |
| LLM 返回非 JSON | 捕获 JSONDecodeError | error.json |
| LLM API 调用失败 | 捕获 APIError | error.json |
| 其他未知错误 | 捕获 Exception | error.json |

## 边界情况

- **空素材数组**: 正常处理，基于选题生成内容
- **超长素材**: 自动截断，只取前10条
- **空栏目**: 使用默认值"经验干货"
- **网络超时**: 自动重试1次

## 运行方式

```bash
cd skills/media-workflow/scripts/content-generate-xhs
python main.py --job-dir ./test/fixtures
```

## 测试标准

| 测试项 | 通过标准 |
|--------|---------|
| title_options | 包含3个标题，每个12-25字 |
| body | 500-800字，段落短，语言自然 |
| hashtags | 5-8个，每个以#开头 |
| cover_text | 10-12字，简洁有力 |
| JSON 格式 | 输出可被 json.loads 解析 |
| 5组测试 | 全部输入通过 |

## 质量标准

- 文案语言自然，像人写的
- 开头有钩子，能抓住注意力
- 内容有干货，不空泛
- 段落节奏舒服，适合手机阅读
- 没有营销号口吻和绝对化表达

## 目录结构

```
content-generate-xhs/
├── SKILL.md
├── main.py
├── requirements.txt
├── prompts/
│   ├── system.md
│   ├── user_template.md
│   └── history/
│       └── v1.md
└── test/
    ├── fixtures/
    │   ├── input_01.json
    │   ├── input_02.json
    │   ├── input_03.json
    │   ├── input_04.json
    │   └── input_05.json
    ├── expected/
    │   └── output.json
    ├── results/
    └── quality_review.md
```

## 环境配置

需要设置以下环境变量：

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| LLM_API_KEY | LLM API Key | - |
| LLM_BASE_URL | LLM API 地址 | https://api.openai.com/v1 |
| LLM_MODEL | LLM 模型名称 | gpt-5.4-mini |