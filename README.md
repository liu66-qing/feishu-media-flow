# Feishu Media Flow

面向大学生社团与校园新媒体的飞书原生内容工作流。系统从飞书接收选题，按平台生成文案和媒体，经过人工审批后交付或发布到小红书、抖音图文和微信公众号。

> 进度基线：2026-07-22，以 `b6c8fc3` 为上游基线完成任务书闭环改造；自动化验收为 44 项通过。任何改变模块状态、入口或平台边界的合并，都必须同步更新本文档。

## 先看这里

当前唯一主链是：

```text
飞书消息 / 卡片动作 / 外部 tick
              |
              v
       app/api/feishu.py
              |
              v
         AgentLoop
              |
      +-------+--------+
      |       |        |
   内容生成  Critic   媒体生成
      |       |        |
      +-------+--------+
              |
         人工发布审批
              |
      发布或平台化人工交付
```

- 新功能应接入 `app/services/agent_loop.py`，不要继续接入旧 `WorkflowService`。
- `app/services/workflow.py` 和 `app/services/scheduler.py` 仅保留迁移参考，不接收新的飞书入口流量。
- 所有 Skill 遵守 `python main.py --job-dir <dir>`、读取 `input.json`、输出 `{skill}.json` 或 `error.json` 的约定。
- `video-generate/` 只是历史兼容名称，当前生成抖音图文卡片，不生成 MP4。

## 状态图例

| 标记 | 含义 |
| --- | --- |
| ✅ 主链已接入 | 已被 AgentLoop 调用，并有对应主链测试 |
| 🟡 部分完成 | 有可运行代码，但存在数据、接线、外部依赖或测试缺口 |
| ⚠️ 明确边界 | 名称或接口存在，但不能按更完整的能力理解 |
| ⬜ 未开始 | 仓库中没有对应实现，需要新增模块 |
| 🧊 遗留参考 | 不再是当前运行入口 |

## 应用层组成与进度

| 组成部分 | 状态 | 当前实现 | 当前缺口 | 开发入口 |
| --- | --- | --- | --- | --- |
| FastAPI 与飞书入口 | ✅ | `/health`、`/feishu/webhook`、URL verification、token/签名校验、`event_id` 幂等、命令与卡片分流 | 真实飞书权限和公网回调需部署配置 | `app/main.py`、`app/api/feishu.py`、`app/api/agent.py` |
| AgentLoop 状态机 | ✅ | 生成、Critic、媒体生成、发布审批、排期、发布、失败通知和进程恢复 | 周报采集不在60秒恢复循环内，必须由外部任务调用 `/agent/tick` | `app/services/agent_loop.py` |
| 选题 Planner | ✅ | 根据月度排期缺口生成选题并发审批卡片 | 只使用固定账号定位和近期选题，未读取热点样本与平台偏好 | `app/services/planner.py`、`app/prompts/planner_system.md` |
| 内容 Critic | ✅ | 按平台适配度、价值密度、人味、结构和发布成熟度评分并触发修改 | 规则为静态 Prompt；抖音评审描述仍偏视频口播，与当前图文交付不完全一致 | `app/services/critic.py`、`app/prompts/critic_*.md` |
| 飞书多维表 | 🟡 | 通用 CRUD；支持内容、素材、账号、发布日志、系统配置5张表的 ID | 主链主要使用内容表和账号表；素材表、发布日志表尚未形成完整写入链路 | `app/services/bitable.py`、`app/config.py` |
| SkillRunner | ✅ | 为 Skill 创建任务目录、写 `input.json`、传递 LLM 环境变量、读取横线或下划线输出名 | 非图片 Skill 共用120秒超时，长任务需要单独评估 | `app/services/skill_runner.py`、`app/models.py::SkillJob` |
| 小红书交付 | 🟡 | 文案生成、Critic、封面、发布包和自动发布调用已串联 | 真实发布依赖未纳入仓库的 `vendor/social-auto-upload` 和有效账号登录 | `AgentLoop._handle_passed()`、`_handle_packaging()`、`app/services/publisher.py` |
| 抖音图文交付 | ✅ | 生成1张封面和4-7张有序卡片，发送飞书供手动上传 | 不生成 MP4；AgentLoop 明确禁止进入自动 Publisher | `app/services/media_delivery.py::compose_douyin_cards()` |
| 公众号交付 | 🟡 | 生成长文、900x500封面和正文配图；有权限时写草稿，无权限时飞书人工交付 | 真实草稿能力取决于公众号永久素材、正文图片和草稿箱权限 | `app/services/media_delivery.py::compose_wechat_package()`、`app/services/wechat.py` |
| 发布适配器 | 🟡 | 包装 `social-auto-upload`；发布成功后保存帖子 ID、URL、发布时间并建立发布日志 | 当前主链只自动发布小红书；真实帖子标识仍取决于外部上传工具返回值 | `app/services/publisher.py`、`AgentLoop._handle_scheduled()` |
| 旧 WorkflowService | 🧊 | 保留旧生成、risk-check、图片合成和排期代码 | 不再接收飞书入口；不要在这里开发新链路 | `app/services/workflow.py` |
| 旧 scheduler | 🧊 | 保留旧到期发布辅助函数 | 当前恢复与发布归 AgentLoop 所有 | `app/services/scheduler.py` |

## Skill 组成与进度

| Skill | 状态 | 当前能力与边界 | 独立运行入口 | 主链接入点 |
| --- | --- | --- | --- | --- |
| `content-generate-xhs` | ✅ | 四阶段 LLM 生成：角度、标题、正文、审查；读取素材并输出标题、正文、标签和封面文案 | `content-generate-xhs/main.py` | `AgentLoop._generate_draft()` |
| `content-generate-douyin` | ✅ | 生成抖音图文文案、封面大字和4-7张卡片数据；不生成视频字段 | `content-generate-douyin/main.py` | `AgentLoop._generate_draft()` |
| `content-generate-wechat` | ✅ | LLM 长文、摘要、章节和配图计划；支持 WebFetch/WebSearch，失败时模板降级 | `content-generate-wechat/main.py` | `AgentLoop._generate_draft()` |
| `image-compose` | ✅ | HTML叠字、校园编辑海报和手绘视觉、AI背景、Playwright截图；AI失败可降级模板 | `image-compose/main.py`、`image-compose/test/run_tests.py` | `AgentLoop._compose_image()`、`MediaDeliveryService` |
| `xhs-publish-package` | ✅ | 整理标题、正文、标签、清单、manifest和图片资源 | `xhs-publish-package/main.py` | `AgentLoop._handle_packaging()` |
| `video-generate` | ⚠️ | 历史兼容名；把抖音卡片数据渲染为PNG卡片包 | `video-generate/main.py` | `MediaDeliveryService.compose_douyin_cards()` |
| `hot-topic-collector` | 🟡 | 微博、抖音、小红书热榜采集，LLM筛选和本地关键词兜底 | `python hot-topic-collector/main.py --job-dir hot-topic-collector/test/fixtures/job1` | `AgentLoop._collect_weekly_topics()`，仅由 `/agent/tick` 触发 |
| `hot-rewrite` | 🟡 | LLM热点改写、Simhash相似度和最多2次重试 | `hot-rewrite/main.py` | 未接入 AgentLoop |
| `platform-sample-collector` | ✅ | 三平台统一样本结构、可追溯性过滤、成功/缓存/降级标识，并写入持续样本库 | `platform-sample-collector/main.py` | `AgentLoop.refresh_platform_preferences()` |
| `platform-preference-profiler` | ✅ | 按真实样本生成带样本ID、数量、置信度和版本的三平台独立画像 | `platform-preference-profiler/main.py` | `AgentLoop.refresh_platform_preferences()` |
| `platform-metrics-collector` | ✅ | 标准化1h/6h/24h/72h曝光、阅读/播放、互动与涨粉快照；无来源时明确降级 | `platform-metrics-collector/main.py` | `AgentLoop.collect_due_metrics()` |
| `risk-check` | 🟡 | 规则词库风险检查，仓库有20条Skill级fixture结果 | `risk-check/main.py` | 仅旧 `WorkflowService` 调用；当前 AgentLoop 不调用 |
| `content-review-polish` | 🟡 | 规则模板润色和质量评分 | `content-review-polish/main.py` | 未接入 AgentLoop；主链目前使用 Critic 修改 |

## 当前平台交付边界

| 平台 | 内容 | 媒体 | 最终交付 |
| --- | --- | --- | --- |
| 小红书 | 平台化图文文案 | 1080x1350封面，可扩展卡片 | 审批后调用 `social-auto-upload`；外部依赖或账号不可用时不能视为真实发布成功 |
| 抖音 | 图文正文、标签、封面与卡片文案 | 1张封面 + 4-7张正文/总结卡 | 飞书顺序交付后手动上传；当前不是 MP4 视频链路 |
| 公众号 | Markdown长文、摘要、章节 | 900x500封面 + 2张正文配图 | 有接口权限时写草稿，否则飞书标注素材和插图位置 |

## 当前优先任务与成员入口

### P0：自动素材采集可用化

负责人建议：郝乐瑾。

已完成：热点参数真实传入 Skill；周报卡片保留素材ID、来源链接、热度、相关度、建议角度和数据状态；采纳后完整素材进入内容记录；配置素材表时同步持久化。验收测试覆盖采集参数、持久化、卡片字段和采纳透传。

外部边界：抖音和小红书热点仍依赖公开数据源；接口不可用时明确标记降级，不能把缓存描述成实时热点。`/agent/tick` 仍需 cron/systemd 定期触发。

验收：每次运行有明确的成功/降级状态；成功平台有可追溯素材；筛选出8-10条有效选题；采纳后完整素材进入内容生成。

### P1：平台偏好驱动的画面与语言

负责人建议：尹羿璇。

已完成：三平台样本库与画像 Skill 已建立；AgentLoop 每日检查样本，并在每个平台至少3条可追溯样本时刷新画像。画像随 SkillJob 进入三平台文案、Critic 与图片合成，并在内容记录中保留版本。图片合成增加平台配色读取和 WCAG 对比度保护。

验收：同一选题在三平台生成明显不同的画面和语言；每条动态规则可追溯到样本；生成结果记录画像版本。

### P2：流量数据与投送机制分析

负责人建议：刘俊清。

已完成：发布结果保存帖子ID、URL和发布时间；发布日志表记录发布事件与指标快照；AgentLoop 按1h、6h、24h、72h采集指标；每周生成严格区分观测、规律和待验证假设的复盘文件。

外部边界：真实指标必须来自配置的合规接口或创作者中心导出。未配置时记录 `data_status=unavailable`，不会用零值冒充真实表现。

验收：每次发布有可追踪ID；四个时间点有数据快照；周报能区分事实、统计规律和待验证假设。

## 本地运行

```bash
python -m venv .venv
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m playwright install chromium
pytest
uvicorn app.main:app --reload
```

Ubuntu：

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m playwright install chromium
pytest
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

常用接口：

```text
GET  /health
POST /feishu/webhook
POST /agent/tick
POST /agent/advance/{item_id}
POST /agent/test/weekly-material
```

飞书命令：

```text
/新建 小红书 社团招新如何提高转化率
/新建 抖音 社团招新现场如何提高转化率
/新建 公众号 社团活动复盘怎么写
/状态
/排期
```

## 环境与外部依赖

仓库当前没有 `.env.example`，请依据 `app/config.py` 在根目录创建 `.env`。不要提交真实密钥。

核心配置：

```text
APP_ENV
APP_BASE_URL
DATA_DIR
AGENT_RECOVERY_ENABLED

FEISHU_APP_ID
FEISHU_APP_SECRET
FEISHU_VERIFICATION_TOKEN
FEISHU_ENCRYPT_KEY
FEISHU_ADMIN_OPEN_IDS
FEISHU_DEFAULT_CHAT_ID
FEISHU_BITABLE_APP_TOKEN
FEISHU_TABLE_CONTENT
FEISHU_TABLE_MATERIALS
FEISHU_TABLE_ACCOUNTS
FEISHU_TABLE_PUBLISH_LOGS
FEISHU_TABLE_CONFIG

LLM_API_KEY
LLM_BASE_URL
LLM_MODEL
DASHSCOPE_API_KEY

WECHAT_APP_ID
WECHAT_APP_SECRET
SKILL_ROOT
SOCIAL_AUTO_UPLOAD_DEFAULT_ACCOUNT
```

外部依赖边界：

- 飞书：需要应用权限、事件订阅、公网回调和5张多维表。
- 小红书自动发布：需要在被 `.gitignore` 排除的 `vendor/social-auto-upload/` 安装工具并完成账号登录。
- 公众号草稿：需要永久素材、正文图片上传和草稿箱权限。
- AI背景：`image-compose` 当前读取 `LLM_API_KEY` 并调用 DashScope 文生图接口，缺失或调用失败时降级模板；Runner虽会传递 `DASHSCOPE_API_KEY`，但该模块目前未读取它。
- 周报素材：需要外部 cron 或 systemd timer 定期调用 `POST /agent/tick`。

## 测试基线

2026-07-22 对任务书闭环版本执行：

```text
44 passed
```

这些单元测试覆盖 AgentLoop、小红书主链、抖音/公众号媒体交付、飞书事件、幂等、SkillRunner、校园视觉和公众号转换。它们不覆盖真实飞书、公众号、小红书账号，也不覆盖热点数据源的有效性。

改动前后至少运行：

```bash
pytest
```

涉及 Skill 时，还必须按对应 `SKILL.md` 运行独立 fixture；真实接口结果不得只用 mock 代替。

## 协作维护规则

1. 开始任务前先确认本页状态和“开发入口”，不要从遗留模块接线。
2. 新增 Skill 时同时提交 `main.py`、`SKILL.md`、`requirements.txt` 和最小 fixture。
3. 改变输入输出字段时，同时修改调用方、模型、fixture和README状态表。
4. 改变“主链已接入 / 独立可运行 / 未完成”状态时，PR必须更新本文档的进度基线。
5. 不得把 mock、模板降级或兼容名称描述成真实平台能力。
6. 不得提交 `.env`、账号Cookie、密钥或平台导出的隐私数据。
