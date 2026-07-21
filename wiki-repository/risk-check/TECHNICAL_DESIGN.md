# risk-check 技术设计文档

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 1. 架构概览

```
┌────────────────────────────────────────────────────────┐
│                     risk-check                          │
├────────────────────────────────────────────────────────┤
│  input.json (title + body + hashtags + platform)        │
│    ↓                                                    │
│  scan_forbidden_words() — 本地规则扫描                 │
│    ↓                                                    │
│  run_llm_review() — LLM 语义审查                      │
│    ↓                                                    │
│  judge_risk_level() — 综合判定风险等级                  │
│    ↓                                                    │
│  build_suggestions() — 生成修改建议                     │
│    ↓                                                    │
│  risk_check.json                                        │
└────────────────────────────────────────────────────────┘
```

## 2. 核心数据结构

### 2.1 输入

| 字段 | 类型 | 说明 |
|------|------|------|
| title | string | 标题 |
| body | string | 正文 |
| hashtags | list[str] | 话题标签 |
| platform | string | 目标平台 |
| content_id | string | 内容 ID |

### 2.2 输出

| 字段 | 说明 |
|------|------|
| risk_level | "high" / "medium" / "low" |
| hits | 本地扫描命中列表 `[{word, type, location, context}]` |
| llm_concerns | LLM 审查关注点列表 |
| suggestions | 综合修改建议 |
| llm_enabled | 是否使用 LLM |

## 3. 风险等级判定规则

| 条件 | 等级 |
|------|------|
| 命中 sensitive_domains 或 political | **high** |
| LLM 关注点 ≥ 3 条 | **high** |
| 命中 absolute_claims | **medium** |
| LLM 关注点 ≥ 1 条 | **medium** |
| platform_risk 命中 > 2 次 | **medium** |
| 以上均不满足 | **low** |

## 4. 关键函数

### `scan_forbidden_words(input_data, rules) -> list[hit]`
遍历 `forbidden_words.json` 中的四类规则词，在 title/body/hashtags 中扫描。使用 `should_skip_hit()` 做上下文感知的误报过滤。

### `should_skip_hit(text, word, index) -> bool`
智能跳过：如"第一"后面跟"次/步/轮/章"等安全词时不报警。

### `run_llm_review(input_data) -> dict`
LLM 语义审查：检测本地规则无法覆盖的隐含风险（如夸大承诺、敏感暗示）。

## 5. 设计决策

1. **双引擎互补**：本地规则快速精确，LLM 语义审查覆盖隐含风险
2. **误报过滤**：上下文感知避免"第一次""最好"等正常用语被误报
3. **LLM 可选**：API Key 未配置时仅用本地规则，不影响基本功能
