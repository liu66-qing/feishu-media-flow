# content-review-polish 技术设计文档

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 1. 架构概览

```
┌────────────────────────────────────────────────────────┐
│              content-review-polish                      │
├────────────────────────────────────────────────────────┤
│  input.json (含 original + polish_level)                │
│    ↓                                                    │
│  ┌──────────────────────────────────────────────┐      │
│  │ polish_content_with_llm()                    │      │
│  │  → call_llm(JSON mode) → parse_llm_json()   │      │
│  └──────────────────┬───────────────────────────┘      │
│                     ↓ 失败时降级                        │
│  ┌──────────────────────────────────────────────┐      │
│  │ polish_content() — 规则模板润色              │      │
│  │  → score_original() → find_issues()          │      │
│  │  → polish_title() → polish_body()            │      │
│  │  → polish_cover_text()                       │      │
│  └──────────────────────────────────────────────┘      │
│    ↓                                                    │
│  content_review_polish.json                             │
└────────────────────────────────────────────────────────┘
```

## 2. 核心数据结构

### 2.1 输入

| 字段 | 类型 | 说明 |
|------|------|------|
| content_id | string | 内容 ID |
| original | object | 原文 `{title, body, hashtags, cover_text}` |
| polish_level | string | "light" / "medium" / "heavy" |

### 2.2 输出

| 字段 | 类型 | 说明 |
|------|------|------|
| quality_score | object | `{hook, naturalness, depth, layout, overall}` |
| issues | list[str] | 识别出的问题列表 |
| polished | object | `{title, body, hashtags, cover_text}` |
| changes_summary | string | 修改摘要 |
| llm_enabled | bool | 是否使用 LLM |

## 3. 关键函数

### `score_original(original) -> dict`
四维评分（每项 1-5 分）：
- **hook**：检测弱钩子词（"分享一下"等）和标题长度
- **naturalness**：检测营销词（"绝对""保证"等）
- **depth**：检测正文长度
- **layout**：检测段落换行

### `polish_body(body, polish_level) -> str`
- 替换绝对化表达为客观说法
- medium/heavy 级别自动增加段落换行
- 正文过短时自动补充提示

## 4. 设计决策

1. **LLM + 规则双模式**：LLM 润色更自然，规则润色更稳定
2. **四维评分**：覆盖标题吸引力、语言自然度、信息深度、排版质量
3. **渐进润色**：light 仅替换问题词，medium/heavy 增加段落拆分
