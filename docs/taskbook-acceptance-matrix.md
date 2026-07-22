# 任务书验收矩阵

本文件以 `docs/assignments/` 中三份任务书为当前验收口径。`docs/task-yin.md` 与 `docs/task-hao.md` 保留为早期阶段记录；与当前任务书冲突时，以 `docs/assignments/` 为准。

## 郝乐瑾：自动素材采集与平台样本库

| 任务书要求 | 实现位置 | 自动验证 | 当前边界 |
| --- | --- | --- | --- |
| 每次提供8至10条相关选题 | `hot-topic-collector/`、`AgentLoop._collect_weekly_topics` | `tests/test_taskbook_acceptance.py` 验证参数真实传入 | 数量取决于公开源；不足时明确降级 |
| 三平台结构统一样本 | `platform-sample-collector/` | fixture 实测 11 条有效样本：公众号3、抖音5、小红书3 | 真实运行需配置公开 feed 或提供合规导出 |
| 标题、摘要、封面、标签、时间、来源、互动 | `platform-sample-collector/main.py::normalize_sample` | 验收测试拒绝无来源样本 | 缺失字段保留为空，不伪造 |
| 实时/缓存/失败可区分 | 两个 collector 的 `data_status`、`degraded_platforms`、`fetch_errors` | 验收测试验证状态透传 | 第三方接口失败不会冒充实时 |
| 无效、重复、无关内容清理 | `clean_samples`、热点去重与相关性筛选 | fixture 和单测 | 语义质量仍需结合管理员审核 |
| 采纳后完整信息进入生成 | `build_material_review_card`、`handle_card_action` | 测试验证来源、热度、角度、链接完整透传 | 飞书字段需按 README 建表 |

## 尹羿璇：平台偏好分析与生成风格适配

| 任务书要求 | 实现位置 | 自动验证 | 当前边界 |
| --- | --- | --- | --- |
| 三个平台独立画像 | `platform-preference-profiler/` | 样本数量门槛与画像注入测试 | 画像质量取决于真实高表现样本 |
| 每条偏好可追溯到样本 | 画像字段 `s_ids`、`s_cnt`、`conf`、`gen_at` | profiler fixture 与索引输出 | LLM总结必须保留样本ID |
| 偏好进入文案生成 | `SkillJob.preference_profile/profile_version`、三个生成 Skill | 注入式 Prompt 测试 | 无合格画像时使用静态规则并标记 `static` |
| 偏好进入内容评审 | `Critic.evaluate` | 测试与代码契约 | 动态偏好只作为样本依据补充，不覆盖安全规则 |
| 偏好进入画面 | `image-compose` | 对比度单测与实际1080×1350渲染 | AI背景需要服务器模型配置 |
| 画面保持可读 | `image-compose::_contrast_ratio` | 白字/近白背景案例已修复并实测 | 模板美术水平与AI背景需分别评价 |
| 避免编造事实 | 三平台审查 Prompt、`hot-rewrite` 输入校验 | 空原文拒绝测试 | 最终发布仍保留人工审批闸门 |

## 刘俊清：主流程集成与流量反馈闭环

| 任务书要求 | 实现位置 | 自动验证 | 当前边界 |
| --- | --- | --- | --- |
| 素材、偏好、生成接成一条链 | `AgentLoop` | 既有主链测试 + 任务书验收测试 | 外部 cron 负责触发 `/agent/tick` |
| 发布内容可追踪 | `PublishResult`、`_handle_scheduled`、发布日志表 | CLI元数据解析测试 | 上传工具必须返回帖子ID或链接 |
| 1h/6h/24h/72h快照 | `platform-metrics-collector/`、`collect_due_metrics` | 时间点顺序与去重测试 | 需平台合规接口或创作者中心导出 |
| 曝光、阅读/播放和互动指标 | `METRIC_FIELDS` | 全字段标准化测试 | 不同平台无对应指标时保留0，但由来源状态解释 |
| 单变量实验记录 | 快照 `experiment` 字段 | fixture 包含封面变量案例 | 对照组需实际发布安排 |
| 每周流量复盘 | `app/services/analytics.py` | 测试排除 fallback 数据并输出待验证假设 | 小样本不会输出确定规律 |
| README与真实进度一致 | `README.md`、本矩阵、`.env.example` | `pytest` 与服务器复验 | 每次合并需同步维护 |

## 当前自动化与效果证据

- 完整回归与任务书验收：`44 passed`。
- 平台样本 fixture：`raw_count=11`、`valid_count=11`，公众号3、抖音5、小红书3。
- 指标 fixture：成功生成6小时快照，并保留 `metrics_source=creator-center-export` 与实验变量。
- 图片效果：1080×1350模板图实际渲染成功；低对比度输入被自动纠正。
- 服务器模型与真实外部源：推送后在 `/opt/feishu-media-flow` 运行统一验收脚本，结果另存入 `evaluation_runs/` 作为PPT证据。
