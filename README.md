# Feishu Media Flow

社团自媒体工作流 MVP 后端。目标是把飞书 Bot、多维表格、内容 Skill、图片卡片、公众号草稿和排期调度串起来，覆盖小红书、抖音图文和公众号。

## 已实现

- FastAPI 服务：`GET /health`、`POST /feishu/webhook`
- 飞书 URL verification challenge
- 飞书事件 token 校验、可选 webhook 签名校验
- `event_id` 幂等去重
- Bot 命令解析：`/新建 平台 选题`、`/状态`、`/排期`
- AgentLoop 统一编排 `/新建`、审批动作、状态推进与平台发布
- 完整图文审批卡片：图片、标题、全文、标签与单内容审批动作
- 飞书多维表 CRUD 客户端与 5 张表配置校验
- Skill 子进程调用器，遵守 `input.json` / `{skill}.json` 约定
- 缺少 Skill 时的 dry-run 降级，便于先跑通后端
- 公众号 Markdown 转 HTML、草稿 API 客户端
- 抖音生成 1 张封面加 4–7 张有序图文卡片，只发送到飞书供手动上传，不生成 MP4
- 公众号自动生成 900×500 封面和正文配图；接口可用时写入草稿，否则在飞书标注插图位置
- AI 生图统一限制为中国大学校园和 18–24 岁中国大学生，失败自动降级为编辑海报模板
- AgentLoop 后台恢复：扫描可自动推进及已到期内容并继续执行
- 单元测试覆盖核心逻辑

旧 `WorkflowService` 和 scheduler 仅保留作迁移参考，不再接收飞书入口流量；旧卡片动作会返回明确的停用提示，不会交叉进入新状态机。第一阶段黑盒架构说明见 [`docs/architecture-stage-1.md`](docs/architecture-stage-1.md)。

## 运行

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
playwright install chromium
pytest
uvicorn app.main:app --reload
```

## 飞书命令

```text
/新建 小红书 社团招新如何提高转化率
/新建 抖音 社团招新现场如何提高转化率
/新建 公众号 社团活动复盘怎么写
/状态
```

## 需要手动配置

这些涉及外部平台账号、权限或真实表结构，代码已预留入口，但必须由项目管理员配置：

- 飞书自建应用：`FEISHU_APP_ID`、`FEISHU_APP_SECRET`
- 飞书事件订阅：`FEISHU_VERIFICATION_TOKEN`，如启用签名再填 `FEISHU_WEBHOOK_SECRET`
- 飞书 Bot 权限：接收消息、发送消息、卡片回调
- 飞书多维表格：创建内容库、素材库、账号库、发布日志、系统配置 5 张表，并填写 `.env` 里的表 ID
- 飞书回调公网地址：本地开发可用内网穿透，把 `/feishu/webhook` 配到事件订阅
- OpenClaw Skill：放到 `SKILL_ROOT`，每个 Skill 需有 `main.py`
- 公众号：配置 `WECHAT_APP_ID`、`WECHAT_APP_SECRET`，并确保账号具备永久素材、正文图片上传和草稿箱接口权限；权限不足时系统自动改为飞书手动插图交付
- 图片渲染：部署后执行 `playwright install chromium`；需要 AI 背景图时配置 `LLM_API_KEY`，不配置则使用模板图

## 环境变量

复制 `.env.example` 为 `.env` 后填写。不要把 `.env` 提交到仓库。

## 测试

```bash
pytest
```

当前测试不依赖真实飞书或微信账号，会用 dry-run 和 fake store 验证可执行行为。
