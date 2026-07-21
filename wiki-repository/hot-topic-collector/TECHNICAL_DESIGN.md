# hot-topic-collector 技术设计文档

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 1. 架构概览

```
┌────────────────────────────────────────────────────────┐
│                hot-topic-collector                      │
├────────────────────────────────────────────────────────┤
│  input.json (keywords + platforms + max_topics)         │
│    ↓                                                    │
│  collect_topics(platforms)                              │
│    ├─ fetch_weibo_hot() — 微博 Ajax API                │
│    ├─ fetch_vvhan_hot("douyin") — 抖音 VVHAN API       │
│    ├─ fetch_vvhan_hot("xhs") — 小红书 VVHAN API        │
│    └─ 全部失败 → seed_topics() — 内置种子选题          │
│    ↓                                                    │
│  dedupe_topics() — 去重                                 │
│    ↓                                                    │
│  ┌──────────────────────────────────────────────┐      │
│  │ call_llm_filter() — LLM 智能筛选            │      │
│  └──────────────────┬───────────────────────────┘      │
│                     ↓ 失败时降级                        │
│  filter_topics_locally() — 关键词匹配筛选              │
│    ↓                                                    │
│  hot-topic-collector.json                               │
└────────────────────────────────────────────────────────┘
```

## 2. 核心数据结构

### 2.1 输入

| 字段 | 类型 | 说明 |
|------|------|------|
| keywords | list[str] | 过滤关键词（默认 ["大学生","社团","运营","校园","新媒体"]） |
| platforms | list[str] | 采集平台（默认 ["weibo","douyin","xhs"]） |
| max_topics | int | 最大输出数量（默认 10） |

### 2.2 输出

| 字段 | 说明 |
|------|------|
| collected_at | 采集时间 (UTC) |
| topics | 筛选后的选题列表 |
| raw_count | 原始采集数量 |
| filtered_count | 筛选后数量 |
| llm_enabled | 是否使用 LLM |
| fetch_errors | 采集错误列表 |

### 2.3 选题结构 (`topics[]`)

| 字段 | 说明 |
|------|------|
| title | 选题标题 |
| source | 来源平台 |
| source_url | 来源链接 |
| heat_score | 热度（1-100） |
| relevance_score | 关键词相关度（0-1） |
| angle_suggestion | 角度建议 |
| suggested_platform | 建议发布平台 |

## 3. 关键函数

### `normalize_heat(value) -> int`
热度归一化：将各平台不同的热度格式（数字/字符串/阅读量）统一映射到 1-100。

### `keyword_relevance(title, keywords) -> float`
关键词相关度评分：精确匹配 +0.22/词，相关术语 +0.08/词，上限 1.0。

### `suggest_platform(title) -> str`
根据标题关键词建议平台：图文类→xhs，视频类→douyin，其他→原平台。

### `build_angle(title, keywords) -> str`
根据选题内容生成角度建议（招新/活动/新媒体等不同模板）。

## 4. 设计决策

1. **多源采集 + 种子兜底**：API 失败不中断，内置种子选题保证可用性
2. **LLM 筛选 + 本地降级**：LLM 理解力强，但关键词匹配也能提供基础筛选
3. **热度归一化**：不同平台热度量纲不同，统一映射到 1-100 便于排序
