# App 技术设计文档

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 1. 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI Application                    │
─────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │ /webhook │  │  /agent  │  │ /health  │             │
│  │ (飞书事件) │  │ (Bot命令) │  │ (健康检查) │             │
│  └────┬─────┘  └────┬─────┘  └──────────┘             │
│       │              │                                   │
│       ▼              ▼                                   │
│  ┌──────────────────────────┐                           │
│  │    services/ 业务逻辑层    │                           │
│  ├──────────────────────────┤                           │
│  │ agent_loop  → 主循环      │                           │
│  │ commands    → 命令解析    │                           │
│  │ skill_runner→ 技能调度    │                           │
│  │ workflow    → 流程编排    │                           │
│  │ critic      → 内容评审    │                           │
│  │ bitable     → 多维表格    │                           │
│  │ cards       → 审批卡片    │                           │
│  │ publisher   → 发布服务    │                           │
│  │ scheduler   → 排期调度    │                           │
│  │ wechat      → 公众号集成  │                           │
│  │ notifier    → 消息通知    │                           │
│  │ idempotency → 幂等去重    │                           │
│  │ llm         → LLM调用    │                           │
│  └──────────────────────────┘                           │
│       │                                                  │
│       ▼                                                  │
│  ┌──────────────────────────┐                           │
│  │   models.py 领域模型层    │                           │
│  │ TopicBrief / PlatformDraft│                           │
│  │ SkillJob / SkillResult   │                           │
│  └──────────────────────────┘                           │
└─────────────────────────────────────────────────────────
       │
       ▼ 子进程调用
┌─────────────────────────────────────────────────────────┐
│              OpenClaw Skill 技能模块                      │
│  hot-topic-collector → content-generate-* → risk-check  │
│  → image-compose → xhs-publish-package → video-generate │
└─────────────────────────────────────────────────────────┘
```

## 2. 核心数据结构

### 2.1 领域模型（models.py）

| 模型 | 用途 | 关键状态 |
|------|------|---------|
| `TopicBrief` | 选题（一个选题可产出多平台草稿） | proposed → approved → dispatched |
| `PlatformDraft` | 平台草稿（选题的子实体） | generating → critiquing → revising → passed → composing_image → packaging → scheduled → published |
| `CriticScore` | 评审五维评分 | hook / information_density / naturalness / platform_fit / actionability |
| `CriticFeedback` | 评审反馈 | decision: pass / revise / reject |
| `SkillJob` | 技能任务输入 | content_id, job_id, platform, topic, materials |
| `SkillResult` | 技能任务输出 | status, timestamp, content_id, data |
| `Platform` | 平台枚举 | xhs / wechat / douyin |

### 2.2 草稿状态机

```
generating → critiquing → revising → (循环直到 passed)
  passed → composing_image → packaging → awaiting_publish_approval
  → publish_approved → scheduled → publishing → published
```

异常路径：任何阶段 → failed / rejected / cancelled

## 3. 关键模块说明

### 3.1 agent_loop.py — Agent 主循环

接收飞书消息事件，解析命令，驱动工作流执行。核心流程：
1. 接收 webhook 事件
2. 幂等校验（idempotency.py）
3. 命令解析（commands.py）
4. 触发工作流（workflow.py）
5. 返回响应

### 3.2 skill_runner.py — 技能模块调度

通过 `subprocess` 调用各技能模块的 `main.py --job-dir`，实现模块解耦。
- 创建临时 job 目录，写入 input.json
- 调用子进程，捕获 stdout/stderr
- 解析输出 JSON，写入多维表格

### 3.3 workflow.py — 工作流编排

编排从选题到发布的完整流程，按状态机推进 PlatformDraft。

### 3.4 critic.py — 内容评审

调用 LLM 对草稿进行五维评分，输出结构化评审意见。支持平台偏好画像注入。

### 3.5 bitable.py — 多维表格

封装飞书多维表格 API，管理 5 张预设表：选题表、草稿表、发布表等。

## 4. API 接口

| 端点 | 方法 | 说明 |
|------|------|------|
| `/webhook/event` | POST | 飞书事件回调 |
| `/webhook/card` | POST | 飞书卡片交互回调 |
| `/health` | GET | 健康检查 |

## 5. 配置项

所有配置通过 `.env` 文件加载：

| 变量 | 必填 | 说明 |
|------|------|------|
| `FEISHU_APP_ID` | 是 | 飞书应用 ID |
| `FEISHU_APP_SECRET` | 是 | 飞书应用密钥 |
| `FEISHU_VERIFICATION_TOKEN` | 是 | 事件订阅校验 token |
| `FEISHU_WEBHOOK_SECRET` | 否 | 事件加密密钥 |
| `WECHAT_APP_ID` | 否 | 公众号 AppID |
| `WECHAT_APP_SECRET` | 否 | 公众号 AppSecret |
| `LLM_API_KEY` | 是 | LLM API 密钥 |
| `LLM_BASE_URL` | 是 | LLM API 地址 |
| `LLM_MODEL` | 是 | 图像生成模型 |
| `LLM_TEXT_MODEL` | 否 | 文本分析模型（默认 qwen-plus） |
| `SKILL_ROOT` | 否 | 技能模块根目录 |

## 6. 设计决策

- **子进程隔离**：技能模块通过 subprocess 调用而非 import，实现模块独立部署和故障隔离
- **幂等设计**：基于消息 ID 的去重机制，防止飞书重试导致重复执行
- **状态机驱动**：草稿生命周期用枚举状态管理，确保流程可追溯
- **弹性降级**：LLM 不可用时部分模块有规则模板兜底

---

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21
