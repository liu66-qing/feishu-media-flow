# Feishu Media Flow

社团自媒体工作流 MVP 后端。目标是把飞书 Bot、多维表格、OpenClaw Skill、审批卡片、公众号草稿和排期调度串起来，先保证小红书 + 公众号链路可运行、可测试、可继续接入真实平台。

## 已实现

- FastAPI 服务：`GET /health`、`POST /feishu/webhook`
- 飞书 URL verification challenge
- 飞书事件 token 校验、可选 webhook 签名校验
- `event_id` 幂等去重
- Bot 命令解析：`/新建 平台 选题`、`/状态`
- 审批卡片 JSON 构建、批量通过按钮回调处理
- 飞书多维表 CRUD 客户端与 5 张表配置校验
- Skill 子进程调用器，遵守 `input.json` / `{skill}.json` 约定
- 缺少 Skill 时的 dry-run 降级，便于先跑通后端
- 公众号 Markdown 转 HTML、草稿 API 客户端
- 简易 scheduler tick：扫描 scheduled 内容并触发到 approved
- 单元测试覆盖核心逻辑

## 运行

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pytest
uvicorn app.main:app --reload
```

## 飞书命令

```text
/新建 小红书 社团招新如何提高转化率
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
- 公众号：认证服务号/订阅号权限，配置 `WECHAT_APP_ID`、`WECHAT_APP_SECRET`，并准备封面 `thumb_media_id`

## 环境变量

复制 `.env.example` 为 `.env` 后填写。不要把 `.env` 提交到仓库。

## 测试

```bash
pytest
```

当前测试不依赖真实飞书或微信账号，会用 dry-run 和 fake store 验证可执行行为。

