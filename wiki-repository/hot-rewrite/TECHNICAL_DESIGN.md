# hot-rewrite 技术设计文档

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 1. 架构概览

```
┌────────────────────────────────────────────────────────┐
│                    hot-rewrite                          │
├────────────────────────────────────────────────────────┤
│  input.json (source_text + source_url + ...)            │
│    ↓                                                    │
│  call_rewrite_llm() — LLM 分析原文 + 改写             │
│    ↓                                                    │
│  similarity() — Simhash 计算相似度                     │
│    ↓                                                    │
│  score > 0.3? ──是──→ build_retry_hint() → 重试(≤2次) │
│    ↓ 否                                                 │
│  hot_rewrite.json                                       │
└────────────────────────────────────────────────────────┘
```

## 2. 核心数据结构

### 2.1 输入

| 字段 | 类型 | 必填 | 说明 |
|------|------|:---:|------|
| source_text | string | 是 | 原始热帖正文 |
| source_url | string | 否 | 原文来源链接 |
| target_platform | string | 否 | 目标平台（默认 xhs） |
| target_column | string | 否 | 目标栏目 |
| rewrite_angle | string | 否 | 改写角度提示 |

### 2.2 输出

| 字段 | 说明 |
|------|------|
| original_analysis | 原文分析 `{hook, structure, viral_points, target_audience}` |
| rewritten_content | 改写结果 `{title, body, hashtags}` |
| similarity_score | 归一化相似度分数（< 0.3 为通过） |
| source_attribution | 来源归属 `{url, note}` |
| risk_notes | 风险提示 |

## 3. 关键函数

### `similarity(a, b) -> (normalized, raw)`
Simhash 相似度计算：
- 中文分词：多尺寸滑窗（9-14字）
- 原始分数：`1 - distance/64`
- 归一化：`max(0, (raw - 0.5) * 2)`，消除同主题短文本的基线偏高

### `call_rewrite_llm(input_data, retry_hint) -> dict`
LLM 改写调用：
- 使用 JSON mode 强制结构化输出
- 重试时追加上次相似度分数，要求更大程度改变表达

### `build_retry_hint(attempt, last_score) -> str`
构建重试提示：告知上次相似度，要求从完全不同的角度改写。

## 4. 设计决策

1. **Simhash 而非编辑距离**：Simhash 对语义相近但表达不同的文本更敏感
2. **归一化基线 0.5**：中文同主题短文本 Simhash 原始分偏高，0.5 附近为随机基线
3. **最多 2 次重试**：平衡质量和 API 成本
4. **角度驱动改写**：通过 `rewrite_angle` 引导 LLM 从不同视角改写
