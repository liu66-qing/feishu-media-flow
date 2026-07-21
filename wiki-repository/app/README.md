# App — FastAPI 后端核心

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 功能简介

`app/` 是 Feishu Media Flow 项目的 FastAPI 后端核心，负责接收飞书 Bot 事件、解析用户命令、调度技能模块执行、管理内容生命周期（选题 → 草稿 → 审核 → 发布），以及提供飞书多维表格和公众号集成的 API 层。

## 核心特性

- **飞书事件处理**：URL 校验、token 校验、消息幂等去重
- **Bot 命令解析**：支持 `/新建 平台 选题`、`/状态` 等指令
- **审批卡片**：构建飞书交互式卡片，处理用户审批回调
- **多维表格 CRUD**：5 张预设表的读写操作
- **技能模块调度**：通过子进程调用各 OpenClaw Skill
- **公众号集成**：Markdown 转 HTML、草稿创建与发布
- **排期调度**：定时将 approved 状态内容推进到发布流程

## 目录结构

```
app/
├── __init__.py
├── main.py                  # FastAPI 应用入口
├── config.py                # 配置加载（环境变量）
├── models.py                # 领域模型（TopicBrief, PlatformDraft 等）
── api/
│   ├── __init__.py
│   ├── agent.py             # Bot 事件与命令 API
│   ├── feishu.py            # 飞书集成 API
│   └── health.py            # 健康检查
├── services/
│   ├── __init__.py
│   ├── agent_loop.py        # Agent 主循环
│   ├── bitable.py           # 飞书多维表格操作
│   ├── cards.py             # 审批卡片构建
│   ├── commands.py          # 命令解析
│   ├── critic.py            # 内容评审服务
│   ├── feishu_security.py   # 飞书安全校验
│   ├── idempotency.py       # 幂等去重
│   ├── llm.py               # LLM 调用封装
│   ├── notifier.py          # 消息通知
│   ├── planner.py           # 内容规划
│   ├── publisher.py         # 发布服务
│   ├── scheduler.py         # 排期调度
│   ├── skill_runner.py      # 技能模块子进程调度
│   ├── wechat.py            # 微信公众号集成
│   ── workflow.py          # 工作流编排
── prompts/
    ├── critic_system.md     # 评审系统 prompt
    ├── critic_user_template.md
    ├── planner_system.md    # 规划系统 prompt
    └── platform_constraints.json  # 平台静态约束
```

## 快速入门

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量（复制 .env.example 为 .env）
cp .env.example .env
# 编辑 .env 填入 FEISHU_APP_ID、FEISHU_APP_SECRET 等

# 3. 启动服务
uvicorn app.main:app --reload

# 4. 访问健康检查
curl http://localhost:8000/health
```

## 依赖说明

| 依赖 | 用途 |
|------|------|
| fastapi | Web 框架 |
| uvicorn | ASGI 服务器 |
| pydantic | 数据验证与模型 |
| openai | LLM API 调用 |
| python-dotenv | 环境变量加载 |
| httpx | HTTP 客户端（飞书 API） |

---

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21
