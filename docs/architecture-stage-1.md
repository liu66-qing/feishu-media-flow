# 第一阶段：飞书指令到小红书自动上传的黑盒链路

## 0. 开始前的链路收敛结论

当前运行链路已经统一为：

`飞书 webhook -> AgentLoop -> 内容/图片/发布包黑盒 -> 飞书最终审批卡片 -> AgentLoop -> Publisher -> 小红书`

入口与所有权边界如下：

| 能力 | 当前唯一所有者 | 说明 |
|---|---|---|
| `/新建`、`/状态`、`/排期` | AgentLoop | 飞书入口不再实例化 WorkflowService |
| 选题审批、发布审批、拒绝、重试 | AgentLoop | 飞书 API 只解析事件并转交动作 |
| 自动状态推进和中断恢复 | AgentLoop | 应用后台每 60 秒恢复可自动推进的记录 |
| 到期发布 | AgentLoop | 旧 scheduler 不再挂到应用启动入口 |
| WorkflowService | 旧链路参考/迁移代码 | 保留已有实现，但不接收新的运行流量 |
| 旧卡片动作 | 明确拒绝 | `approve_all` 等动作返回 `deprecated_action`，不会跨回旧链路 |

这意味着一条内容不会再出现“由 WorkflowService 创建，却由 AgentLoop 审批”的混合所有权。

## 1. 这阶段只看什么

本阶段把每个业务能力视为黑盒，不讨论它内部用了哪个 Prompt、模板、Python 函数或浏览器选择器，只关注四件事：

1. 谁触发它。
2. 它接收什么。
3. 它产出什么。
4. 失败后由谁接住。

## 2. 黑盒节点

| 编号 | 黑盒节点 | 输入 | 输出 | 与其他节点的协作责任 |
|---|---|---|---|---|
| B1 | 飞书用户界面 | `/新建 小红书 <选题>` | 飞书消息事件 | 给链路一个明确的平台和选题 |
| B2 | 飞书事件网关 | webhook 请求 | 已验证、已去重的命令或卡片动作 | 校验来源，避免同一事件被执行两次 |
| B3 | AgentLoop 编排中心 | 命令、卡片动作、当前状态 | 下一状态与待执行任务 | 是整条链路唯一的流程所有者 |
| B4 | 状态存储 | 内容 ID、状态、各节点产物 | 可恢复的内容记录 | 让异步任务、审批回调和后台恢复看到同一事实 |
| B5 | 内容生产黑盒 | 平台、选题、素材 | 标题、正文、标签、封面文案 | 只交付结构化文案，不决定是否发布 |
| B6 | 视觉生产黑盒 | 标题、封面文案、视觉参数 | 封面/正文图片路径 | 只生产媒体文件，不持有审批权 |
| B7 | 发布包黑盒 | 文案与图片 | 可上传的标准发布包 | 固化标题、正文、标签和图片顺序 |
| B8 | 飞书最终审批卡片 | 完整发布包摘要与飞书图片 key | `approve_publish` 或 `reject_publish` | 把人放在唯一的发布闸门上 |
| B9 | 发布调度黑盒 | 已批准的内容 | 到期发布任务 | 当前策略是批准后立即到期，同时保留状态恢复能力 |
| B10 | 平台发布适配器 | 账号、标题、正文、标签、图片路径 | 成功或失败结果 | 把统一发布载荷翻译成小红书上传动作 |
| B11 | 小红书 | 已登录账号与上传动作 | 已发布笔记或平台错误 | 最终外部系统 |
| B12 | 通知与恢复 | 发布结果、卡住的状态 | 飞书成功/失败通知、重试入口 | 失败可见，进程重启后可继续推进 |

## 3. 正常协作时序

1. 用户在飞书发送 `/新建 小红书 社团招新怎么提高转化`。
2. B2 校验 webhook、读取 `event_id` 并完成幂等判断，然后把命令交给 B3。
3. B3 安排异步生产，飞书请求立即收到 `accepted`，不等待整条生产链；后台任务开始时先在 B4 建立唯一 `content_id`，状态记为 `generating`。
4. B5 返回结构化文案。B3 将文案写入 B4，并驱动内容质量检查；需要修改时仍留在内容生产黑盒内部循环。
5. 内容通过后，B3 把标题与封面文案交给 B6。B6 返回实际图片文件。
6. B3 将文案和图片交给 B7。B7 产出发布包及有序的图片路径。
7. B3 上传预览图片到飞书，B8 向原始会话发送一张完整审批卡片。卡片包含图片、标题、全文、标签、内容 ID，以及批准/拒绝按钮。
8. 用户点击“批准并自动发布”。B2 再次完成事件校验和去重，将 `{action, content_id, operator}` 交给 B3。
9. B3 只允许 `awaiting_publish_approval` 状态接受该动作，校验后推进到 `publish_approved`，记录审批人和审批时间。
10. B9 将内容转为立即到期的 `scheduled` 任务。B3 随后推进到 `publishing`。
11. B10 读取账号和发布包，调用小红书上传能力。成功后 B4 记为 `published`；失败则记为 `failed`。
12. B12 将结果发回飞书。失败卡片可触发重试或人工接管；服务重启时，后台恢复循环会继续处理尚未到达人为闸门或终态的记录。

## 4. 节点间的数据契约

| 交接 | 最小契约 |
|---|---|
| B2 -> B3 | `platform`、`topic`、`chat_id`；`event_id` 在网关层完成幂等后不进入业务契约 |
| B3 -> B5 | `content_id`、`platform`、`topic`、`materials` |
| B5 -> B6 | `selected_title`、`body`、`hashtags`、`cover_text` |
| B6 -> B7 | `cover_path`/`image_path`、`card_paths` |
| B7 -> B8 | `title`、`body`、`hashtags`、`asset_paths`、`content_id` |
| B8 -> B3 | `action=approve_publish|reject_publish`、`content_id`、`operator_open_id` |
| B3 -> B10 | `platform`、`account`、`title`、`body`、`tags`、`image_paths` |
| B10 -> B12 | `success`、`platform`、`message`、标准输出/错误摘要 |

协作规则只有一条核心原则：上游交结构化产物，下游只通过契约读取；状态只能由 AgentLoop 推进。

## 5. 人工闸门、终态与恢复

人为等待状态只有两个：

- `awaiting_topic_approval`：自动选题场景使用；手工 `/新建` 已表达选题意图，因此直接进入内容生产。
- `awaiting_publish_approval`：完整文案和图片已准备好，等待最终发布授权。

主要终态：

- `published`：小红书上传成功。
- `rejected`：人工拒绝，不再自动推进。
- `failed`：节点执行失败，可通过重试卡片恢复。
- `cancelled`：人工接管，自动链路停止。

后台恢复只推进“本应自动继续”的状态，不会越过人工审批状态。

## 6. 真实运行的外部前提

代码闭环不等于外部平台已经可发布。真实运行前还需要：

- 飞书应用事件订阅、消息与卡片权限配置正确。
- 内容多维表至少存在代码使用的字段：`content_id`、`topic`、`platform`、`status`、`version`、`revision_count`、`materials`、`chat_id`、`created_at`、`source`、`content_payload`、`critic_feedback`、`image_result`、`package_result`、`reviewed_by`、`reviewed_at`、`scheduled_at`。自动选题还需要 `target_platforms`、`key_points`。
- `vendor/social-auto-upload` 已安装其运行依赖。
- 小红书账号 cookie 有效；优先读取账号表中 `platform=xhs,status=active` 的 `account_name`，没有时使用 `SOCIAL_AUTO_UPLOAD_DEFAULT_ACCOUNT`，默认值为 `default`。
- 生成图片在发布进程所在机器上仍可访问。

本次测试使用假的 Publisher，没有对真实小红书账号执行上传。

## 7. 黑盒节点与代码落点

第一阶段仍然把业务能力当作黑盒，但图上必须同时给出黑盒的代码入口。阅读时按“业务责任 -> 编排方法 -> 执行实现”三层理解：

| 节点 | 业务责任 | 编排入口 | 功能实现位置 | 关键产物/状态 |
|---|---|---|---|---|
| B1 飞书用户 | 发命令、做最终审批 | 外部系统 | 飞书客户端 | `/新建`、卡片按钮动作 |
| B2 飞书事件网关 | 安全校验、幂等、命令与动作分流 | `app/api/feishu.py::feishu_webhook` | `app/services/feishu_security.py`、`idempotency.py`、`commands.py` | 合法命令或卡片动作 |
| B3 AgentLoop 编排中心 | 创建任务、判断当前状态、选择下一个处理器 | `AgentLoop.create_content_from_topic`、`handle_card_action`、`run_until_checkpoint` | `app/services/agent_loop.py` | 唯一 `content_id` 和状态跃迁 |
| B4 状态存储 | 保存当前事实，使异步任务和回调会合 | AgentLoop 内所有 `create_record/update_record/list_records` 调用 | `app/services/bitable.py::BitableClient`、飞书多维表 | `status`、`content_payload`、`image_result`、`package_result` |
| B5 内容生产 | 生成标题、正文、标签和封面文案，并完成质量修订 | `AgentLoop._handle_generating`、`_handle_critiquing`、`_revise_draft` | `SkillRunner.run("content-generate-xhs")`、`content-generate-xhs/main.py`、`app/services/critic.py` | `content_payload`，状态到 `passed` |
| B6 视觉生产 | 把文案转换成可发布图片 | `AgentLoop._handle_passed`、`_handle_composing_image`、`_compose_image` | `SkillRunner.run("image-compose")`、`image-compose/main.py` | `image_result`，状态到 `packaging` |
| B7 发布包 | 固化文案、标签和图片顺序 | `AgentLoop._handle_packaging` | `SkillRunner.run("xhs-publish-package")`、`xhs-publish-package/main.py` | `package_result.asset_paths`，状态到 `awaiting_publish_approval` |
| B8 最终审批卡片 | 将完整内容交给人做唯一一次发布授权 | `AgentLoop._send_publish_approval_card` | `app/services/cards.py::build_publish_review_card`、`notifier.py::upload_image/send_card` | `approve_publish` 或 `reject_publish` |
| B9 审批与调度 | 校验审批前状态，记录审批人，生成立即到期任务 | `AgentLoop.approve_publish`、`_approve_checkpoint`、`_handle_publish_approved` | `app/services/agent_loop.py` | `publish_approved -> scheduled` |
| B10 平台发布 | 把标准载荷翻译成小红书上传命令 | `AgentLoop._handle_scheduled` | `app/services/publisher.py::Publisher.publish/_publish_xhs_note`、`vendor/social-auto-upload/sau_cli.py` | `publishing -> published/failed` |
| B11 小红书 | 接收真实图文上传 | Publisher 外部边界 | 小红书创作平台 | 笔记或平台错误 |
| B12 恢复与通知 | 恢复中断状态、通知成功/失败、提供重试 | `AgentLoop.advance_due_items`、`_notify_publish_failure` | `app/main.py::_agent_recovery_loop`、`notifier.py` | 飞书通知、`retry_publish` |

### 状态与处理器对照

| 当前状态 | 谁可以推进 | AgentLoop 处理器 | 下一个状态 |
|---|---|---|---|
| `generating` | 自动 | `_handle_generating` | `critiquing` |
| `critiquing` | 自动 | `_handle_critiquing` | `revising` / `passed` / `rejected` |
| `revising` | 自动修订调用内部完成 | `_revise_draft` | `critiquing` |
| `passed` | 自动 | `_handle_passed` | 小红书进入 `composing_image` |
| `composing_image` | 自动 | `_handle_composing_image` / `_compose_image` | `packaging` |
| `packaging` | 自动 | `_handle_packaging` | `awaiting_publish_approval` |
| `awaiting_publish_approval` | 只能由人 | `approve_publish` / `reject_item` | `publish_approved` / `rejected` |
| `publish_approved` | 自动 | `_handle_publish_approved` | `scheduled` |
| `scheduled` 且已到期 | 自动 | `_handle_scheduled` | `publishing` |
| `publishing` | Publisher 结果 | `_handle_scheduled` 后半段 | `published` / `failed` |
| `failed` | 只能由重试或人工接管 | `handle_card_action` | `scheduled` / `cancelled` |

`run_until_checkpoint` 负责连续调用自动处理器；遇到 `awaiting_publish_approval`、未来才到期的 `scheduled` 或任何终态就停止。`advance_due_items` 是进程重启后的恢复入口，使用同一套规则，不另造第二条链。

### 推荐的代码阅读路径

1. 从 `app/api/feishu.py::feishu_webhook` 看请求如何进入系统。
2. 跟进 `AgentLoop.create_content_from_topic` 和 `run_until_checkpoint`，理解编排骨架。
3. 对照上面的状态表逐个阅读 `_handle_*` 方法，不要先钻进 Skill。
4. 再拆 `SkillRunner -> content-generate-xhs -> image-compose -> xhs-publish-package`。
5. 回到 `_send_publish_approval_card` 和 `handle_card_action` 看人工闸门。
6. 最后读 `_handle_scheduled -> Publisher -> social-auto-upload`，理解真实发布边界。
7. 用 `tests/test_agent_loop.py` 对照完整成功路径和非法审批状态。

## 8. 具象架构图提示词

将下面提示词直接交给 GPT，让它输出 Mermaid：

```text
你是一名资深软件架构师和代码导读作者。请基于下面给出的真实代码映射，为“飞书 /新建 小红书 -> 完整图文审批卡片 -> 自动上传小红书”生成 3 张 Mermaid 图。目标不是做抽象概念图，而是让第一次接触仓库的人能同时看懂：业务如何流动、AgentLoop 如何编排、每项功能去哪个文件和方法找。

通用绘图规则：
- 所有代码位置使用“仓库相对路径::类.方法”或“仓库相对路径::函数”，不要使用易漂移的行号。
- 每个主要节点固定显示 3 行：业务名称、代码入口、主要输入/输出或状态。
- 实线箭头表示本次请求内的调用，虚线箭头表示异步任务、后台恢复或失败重试。
- 在写多维表的位置标注“状态持久化”，在外部系统边界标注“外部 I/O”。
- 用一种统一颜色表示 AgentLoop 控制节点；Skill 执行节点使用另一种颜色；飞书、小红书和多维表使用中性色。
- 不展开 Prompt 内容、HTML 模板细节和 social-auto-upload 的浏览器选择器。
- 中文标签，布局清晰，代码文字使用等宽样式，不要使用 emoji。

图一：运行时组件与代码落点图，使用 flowchart LR。

分 6 个 subgraph：
1. 飞书交互；
2. 接入与安全；
3. 编排与状态；
4. 内容生产；
5. 媒体与发布包；
6. 平台发布。

必须包含以下真实节点：

A. 飞书用户
- 输入：/新建 小红书 <选题>
- 输出：消息事件、approve_publish/reject_publish

B. 飞书 Webhook
- app/api/feishu.py::feishu_webhook
- app/api/feishu.py::_handle_message
- app/api/feishu.py::_handle_card_action
- 输入：飞书 webhook；输出：命令或卡片动作

C. 安全与幂等
- app/services/feishu_security.py::verify_webhook_signature/verify_event_token
- app/services/idempotency.py::IdempotencyStore.seen_or_record
- app/services/commands.py::parse_command

D. AgentLoop 编排中心
- app/services/agent_loop.py::AgentLoop.create_content_from_topic
- app/services/agent_loop.py::AgentLoop.run_until_checkpoint
- app/services/agent_loop.py::AgentLoop.advance_item
- app/services/agent_loop.py::AgentLoop.handle_card_action
- 标注“唯一流程与状态所有者”

E. 飞书多维表状态存储
- app/services/bitable.py::BitableClient
- 关键字段：content_id、status、content_payload、image_result、package_result、reviewed_by、scheduled_at

F. 内容生成 Skill
- app/services/agent_loop.py::AgentLoop._handle_generating/_generate_draft
- app/services/skill_runner.py::SkillRunner.run
- content-generate-xhs/main.py
- 输出：selected_title、body、hashtags、cover_text

G. Critic 质量闭环
- app/services/agent_loop.py::AgentLoop._handle_critiquing/_revise_draft
- app/services/critic.py::Critic.evaluate
- 输出：pass/revise/reject

H. 图片合成
- app/services/agent_loop.py::AgentLoop._handle_passed/_handle_composing_image/_compose_image
- image-compose/main.py
- 输出：image_result、cover_path/card_paths

I. 小红书发布包
- app/services/agent_loop.py::AgentLoop._handle_packaging
- xhs-publish-package/main.py
- 输出：package_result.asset_paths

J. 完整图文审批卡片
- app/services/agent_loop.py::AgentLoop._send_publish_approval_card
- app/services/cards.py::build_publish_review_card
- app/services/notifier.py::FeishuNotifier.upload_image/send_card
- 输出：approve_publish 或 reject_publish

K. 审批与立即调度
- app/services/agent_loop.py::AgentLoop.approve_publish/_approve_checkpoint/_handle_publish_approved
- 状态：awaiting_publish_approval -> publish_approved -> scheduled

L. Publisher 适配器
- app/services/agent_loop.py::AgentLoop._handle_scheduled
- app/services/publisher.py::Publisher.publish/_publish_xhs_note
- 输入：account/title/body/tags/image_paths

M. social-auto-upload
- vendor/social-auto-upload/sau_cli.py
- 外部 I/O：登录 cookie、浏览器上传

N. 小红书创作平台
- 输出：发布成功或平台错误

O. 后台恢复与失败通知
- app/main.py::_agent_recovery_loop
- app/services/agent_loop.py::AgentLoop.advance_due_items/_notify_publish_failure
- app/services/notifier.py

主链必须明确连接为：
A -> B -> C -> D -> E；
D -> F -> G -> H -> I -> J -> A；
A 点击批准 -> B -> D -> K -> L -> M -> N；
N -> D -> E -> O -> A。

必须额外画出：
- D 与 E 之间每个阶段的读写关系；
- O 到 D 的虚线“每 60 秒恢复自动状态”；
- G 到 F 的虚线“revise 后重新质检”；
- 发布失败从 L/N 回到 failed，再由 retry_publish 回到 scheduled；
- 一个与主链完全断开的灰色 Legacy 区：app/services/workflow.py::WorkflowService、app/services/scheduler.py，标注“不接收运行流量；旧卡片动作返回 deprecated_action”。

图二：AgentLoop 状态机与处理器图，使用 stateDiagram-v2。

必须逐一标注状态对应的代码处理器：
- generating -- _handle_generating --> critiquing
- critiquing -- _handle_critiquing: revise --> revising
- revising -- _revise_draft --> critiquing
- critiquing -- _handle_critiquing: pass --> passed
- critiquing -- _handle_critiquing: reject --> rejected
- passed -- _handle_passed[XHS] --> composing_image
- composing_image -- _handle_composing_image/_compose_image --> packaging
- packaging -- _handle_packaging --> awaiting_publish_approval
- awaiting_publish_approval -- approve_publish/_approve_checkpoint --> publish_approved
- awaiting_publish_approval -- reject_item --> rejected
- publish_approved -- _handle_publish_approved --> scheduled
- scheduled -- _handle_scheduled[到期] --> publishing
- publishing -- Publisher成功 --> published
- publishing -- Publisher失败 --> failed
- failed -- retry_publish --> scheduled
- failed -- manual_takeover --> cancelled

给 generating、critiquing、passed、composing_image、packaging、publish_approved、到期 scheduled 加注释“run_until_checkpoint 可自动推进”；给 awaiting_publish_approval 加醒目标注“人工闸门，恢复循环不得越过”；给 published/rejected/cancelled 加注释“终态”。

图三：一次真实 /新建 请求的 sequenceDiagram。

参与者按顺序为：
User、Feishu、Webhook、AgentLoop、Bitable、SkillRunner、XhsGenerator、Critic、ImageCompose、PublishPackage、ReviewCard、Publisher、SAU、XHS。

必须表现下面的同步/异步边界和真实方法：
1. User -> Feishu：/新建 小红书 <选题>。
2. Feishu -> Webhook：事件请求；Webhook 内完成安全校验与 event_id 幂等。
3. Webhook -> AgentLoop：通过 asyncio.create_task 启动 create_content_from_topic；Webhook -> Feishu：立即返回 accepted。
4. AgentLoop -> Bitable：创建 content_id，status=generating。
5. AgentLoop -> SkillRunner -> XhsGenerator：生成结构化文案；回写 content_payload，status=critiquing。
6. AgentLoop -> Critic：evaluate；使用 alt 表示 pass、revise、reject，其中 revise 回写 critic_feedback 后重新 evaluate。
7. pass 后调用 image-compose；回写 image_result，status=packaging。
8. 调用 xhs-publish-package；回写 package_result，status=awaiting_publish_approval。
9. 上传图片并构建完整 ReviewCard；Feishu -> User 显示图片、标题、正文、标签。
10. User 点击批准；Webhook -> AgentLoop.handle_card_action -> approve_publish；先校验当前状态，只允许 awaiting_publish_approval。
11. 回写 reviewed_by/reviewed_at 和 publish_approved；自动推进 scheduled_at=now -> publishing。
12. AgentLoop -> Publisher -> SAU -> XHS：上传图文。
13. 使用 alt 表示成功回写 published 并通知，失败回写 failed 并发送重试卡片。
14. 使用 opt 表示进程中断后 app/main.py::_agent_recovery_loop 调用 advance_due_items 恢复自动状态，但在 awaiting_publish_approval 停止。

三张图之后，再输出一个简短“代码索引”表，列为：业务能力、首读文件、关键符号、建议下一跳。不要输出泛化的架构原则，不要虚构仓库中不存在的组件。
```

## 9. 第二阶段拆箱顺序

第二阶段按数据流顺序拆，不按文件大小拆：

1. 飞书 webhook 的安全校验、幂等与命令解析。
2. AgentLoop 的状态表、合法跃迁和 `run_until_checkpoint`。
3. 内容生成与 Critic 自动修订循环。
4. SkillRunner 的子进程协议和输出兼容。
5. 图片合成、发布包与完整飞书卡片的字段映射。
6. 发布审批、账号选择、Publisher 与 social-auto-upload。
7. 后台恢复、失败重试和测试替身如何验证整条链路。

第二阶段应始终拿本阶段的数据契约做对照：实现可以替换，节点间契约和状态所有权不能漂移。
