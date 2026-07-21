# content-generate-xhs 技术设计文档

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 1. 架构概览

```
┌────────────────────────────────────────────────────────┐
│              content-generate-xhs                       │
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
│  normalize_final() — 提取/回退字段                      │
│    ↓                                                    │
│  validate_output() — 硬指标校验                         │
│    ↓                                                    │
│  content-generate-xhs.json                              │
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
| brand | object | 否 | 品牌信息 `{tone, audience}` |

### 2.2 输出 (`content-generate-xhs.json`)

| 字段 | 类型 | 说明 |
|------|------|------|
| content_id | string | 继承自输入 |
| job_id | string | 继承自输入 |
| title_options | list[str] (1-5) | 候选标题 |
| selected_title | string | 最终选定标题 |
| body | string (300-1200字) | 正文 |
| hashtags | list[str] (3-10) | 话题标签，以 `#` 开头 |
| cover_text | string (4-20字) | 封面文案 |
| risk_notes | list[str] | 风险提示 |
| pipeline_log | object | 各步骤耗时/token 统计 |
| step1_analyze | object | 选题分析结果（供下游封面生成使用） |

### 2.3 平台约束 (`platform_constraints.json`)

从 `app/prompts/platform_constraints.json` 读取 XHS 平台的静态约束：
- `title_max_length`: 20
- `body_min_length`: 400, `body_max_length`: 900
- `cover_text_max_length`: 15
- `max_tags`: 10
- `forbidden_words`: 禁用词列表
- `style_guide`: 风格指南
- `content_structure`: 内容结构要求

### 2.4 平台偏好画像 (V2 Schema)

从 `.data/profiles/xhs_profile.json` 读取动态画像，7 天过期：
- `topic`: 选题偏好
- `lang`: 语言风格
- `vis`: 视觉风格
- `struct`: 内容结构
- `forbid`: 额外禁用词
- `conf`: 置信度
- `s_cnt`: 样本数

画像不存在或过期时，自动降级到静态 `platform_constraints.json`。

## 3. 关键函数说明

### `build_system_prompt() -> str`
构建系统提示词，合并平台约束 + 动态偏好画像。画像存在时注入 V2 Schema 五维度信息。

### `call_step(client, model, step_name, prompt, job, context) -> (dict, dict)`
单步 LLM 调用：
- 使用 `response_format={"type": "json_object"}` 强制 JSON 输出
- 解析失败时追加一条重试提示，最多 2 次尝试
- 返回解析后的 dict 和 `{duration_ms, tokens, attempts, status}` 日志

### `parse_json_object(raw: str) -> dict`
LLM 原始输出 → 可解析 JSON：
1. 剥离 ` ```json ``` ` 代码块
2. 定位首个 `{` 到末尾 `}` 的子串
3. `json.loads()` 解析

### `normalize_final(job, context) -> dict`
从 step4_review 提取最终结果，字段缺失时逐级回退到前序步骤。

### `validate_output(result) -> None`
硬指标校验，不满足则抛出 `PipelineError`：
- 标题 1-5 个
- 正文 300-1200 字
- 标签 3-10 个，均以 `#` 开头
- 封面文案 4-20 字

## 4. 4-Step Pipeline 设计

| Step | Prompt 文件 | 职责 |
|------|------------|------|
| step1_analyze | `step1_analyze.md` | 选题拆解为三个角度 |
| step2_titles | `step2_titles.md` | 生成 3 个候选标题 + 选定 1 个 |
| step3_body | `step3_body.md` | 撰写正文、标签、封面文案 |
| step4_review | `step4_review.md` | 审查评分、修复问题、输出最终 JSON |

每步共享同一个 `context` dict，后续步骤可引用前序结果。所有步骤使用同一 `SYSTEM_PROMPT`。

## 5. 环境变量

| 变量 | 说明 | 必填 |
|------|------|:---:|
| LLM_API_KEY | LLM API 密钥 | 是 |
| LLM_BASE_URL | API 基础 URL | 是 |
| LLM_MODEL | 模型名称 | 是 |

## 6. 错误处理

- 输入文件缺失 → `PipelineError`
- 必填字段缺失 → `PipelineError`
- 环境变量缺失 → `PipelineError`
- LLM 返回不可解析 JSON → 重试 1 次，仍失败则 `PipelineError`
- 输出校验不通过 → `PipelineError`
- 所有异常 → 写入 `error.json`，退出码 1

## 7. 设计决策

1. **多步 Pipeline vs 单次调用**：拆分为 4 步可逐步控制质量，step4 作为"审查者"修复前序问题
2. **JSON Mode + 重试**：`response_format=json_object` 确保结构化输出，解析失败追加提示重试
3. **平台约束外置**：从 `app/prompts/platform_constraints.json` 读取，避免硬编码
4. **偏好画像弹性降级**：画像过期自动回退到静态约束，保证可用性
5. **step1_analyze 透传**：输出中保留 step1 结果供 image-compose 模块使用
