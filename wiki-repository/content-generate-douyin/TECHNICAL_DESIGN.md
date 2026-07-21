# content-generate-douyin 技术设计文档

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 1. 架构概览

```
┌────────────────────────────────────────────────────────┐
│              content-generate-douyin                    │
├────────────────────────────────────────────────────────┤
│  input.json                                             │
│    ↓                                                    │
│  require_fields() — 校验 content_id/job_id/topic       │
│    ↓                                                    │
│  build_client() — OpenAI 兼容客户端                     │
│    ↓                                                    │
│  ┌──────────────────────────────────────────────┐      │
│  │ 4-Step LLM Pipeline (JSON mode + retry)      │      │
│  │  step1_analyze → step2_titles →              │      │
│  │  step3_body → step4_review                   │      │
│  └──────────────────────────────────────────────┘      │
│    ↓                                                    │
│  normalize_final() — 提取/回退字段 + 卡片归一化        │
│    ↓                                                    │
│  validate_output() — 硬指标校验                         │
│    ↓                                                    │
│  content-generate-douyin.json                           │
└────────────────────────────────────────────────────────┘
```

## 2. 核心数据结构

### 2.1 输入 (`input.json`)

| 字段 | 类型 | 必填 | 说明 |
|------|------|:---:|------|
| content_id | string | 是 | 内容唯一标识 |
| job_id | string | 是 | 任务唯一标识 |
| topic | string | 是 | 选题主题 |
| column | string | 否 | 栏目名称 |
| materials | list[str] | 否 | 参考素材列表 |

### 2.2 输出 (`content-generate-douyin.json`)

| 字段 | 类型 | 说明 |
|------|------|------|
| content_id | string | 继承自输入 |
| job_id | string | 继承自输入 |
| title_options | list[str] (1-5) | 候选标题 |
| selected_title | string | 最终选定标题 |
| body | string (400-2000字) | 正文 |
| hashtags | list[str] (2-8) | 话题标签，以 `#` 开头 |
| cover_lines | list[str] (1-5) | 封面大字（每行 3-7 字） |
| cover_text | string | 封面文字（cover_lines 拼接） |
| cards | list[dict] (4-7) | 有序图文卡片 |
| risk_notes | list[str] | 风险提示 |
| pipeline_log | object | 各步骤耗时/token 统计 |

### 2.3 卡片结构 (`cards[]`)

| 字段 | 类型 | 说明 |
|------|------|------|
| kind | "detail" / "summary" | 卡片类型，最后一张固定为 summary |
| section_label | string (≤20字) | 段落标签 |
| title | string (≤32字) | 卡片标题 |
| body | string (≤180字) | 卡片正文 |
| highlight | string (≤80字) | 高亮金句 |

### 2.4 平台偏好画像 (V2 Schema)

从 `.data/profiles/douyin_profile.json` 读取，7 天过期，注入 system prompt：
- topic / lang / vis / struct / forbid 五维度
- 画像不存在或过期时自动降级到静态约束

## 3. 关键函数说明

### `build_system_prompt() -> str`
构建抖音专属系统提示词：成熟真实风格、禁止小红书风格、含卡片约束。画像存在时注入动态偏好。

### `normalize_cards(value) -> list[dict]`
将 LLM 输出的原始卡片数据归一化：
- 最多保留 7 张
- 校验 kind 只能是 detail/summary
- 截断超长字段
- 最后一张强制设为 summary

### `normalize_final(job, context) -> dict`
从 step4_review 提取最终结果，字段缺失时逐级回退。cover_text 由 cover_lines 拼接生成。

### `validate_output(result) -> None`
硬指标校验：
- 标题 1-5 个，正文 400-2000 字
- 标签 2-8 个，均以 `#` 开头
- 封面大字 1-5 行
- 卡片 4-7 张，每张含 title 和 body
- 最后一张必须是 summary

## 4. 4-Step Pipeline

| Step | Prompt 文件 | 职责 |
|------|------------|------|
| step1_analyze | `step1_analyze.md` | 选题拆解 |
| step2_titles | `step2_titles.md` | 标题候选 + 封面大字 |
| step3_body | `step3_body.md` | 正文 + 卡片内容生成 |
| step4_review | `step4_review.md` | 审查评分 + 修复 |

与 XHS 模块共享相同的 Pipeline 架构，但输出结构不同（抖音多了 cards 和 cover_lines）。

## 5. 设计决策

1. **卡片式输出**：抖音图文以卡片形式呈现，每张卡片独立成章，最后一张总结
2. **封面大字**：抖音封面需要 2-4 行大字，每行 3-7 字，与 XHS 的 cover_text 不同
3. **风格隔离**：明确禁止小红书风格（emoji 堆砌、符号装饰），保持抖音成熟真实调性
4. **卡片归一化**：LLM 输出可能不规范，`normalize_cards()` 做兜底处理
