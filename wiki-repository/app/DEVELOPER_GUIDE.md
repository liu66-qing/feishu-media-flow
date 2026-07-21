# App 开发者指南

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 1. 模块间数据交互

### 1.1 上游输入

```
飞书 Bot 消息 → /webhook/event → agent_loop → commands → workflow
```

用户在飞书中发送 `/新建 xhs 社团招新攻略`，经 webhook 进入 agent_loop。

### 1.2 下游输出

```
workflow → skill_runner → 各技能模块（子进程）→ 结果回写多维表格
```

skill_runner 为每个技能创建 job 目录，写入 input.json，调用子进程，读取输出 JSON。

### 1.3 数据流全景

```
选题(proposed) → 审批(approved) →  dispatched
  → content-generate-{platform} → 草稿(generating)
  → critic → 评审(critiquing) → [revise 循环] → passed
  → image-compose → 封面(composing_image)
  → xhs-publish-package → 打包(packaging)
  → 发布审批 → scheduled → publishing → published
```

## 2. 内部工作流程

### 2.1 命令处理链路

```python
# app/services/agent_loop.py
async def handle_message(event):
    # 1. 幂等校验
    if idempotency.is_duplicate(event.message_id):
        return
    # 2. 命令解析
    cmd = commands.parse(event.message.text)
    # 3. 触发工作流
    await workflow.dispatch(cmd)
```

### 2.2 技能调度流程

```python
# app/services/skill_runner.py
def run_skill(skill_name: str, input_data: dict) -> dict:
    job_dir = create_temp_job_dir(skill_name)
    write_json(job_dir / "input.json", input_data)
    result = subprocess.run(
        [sys.executable, f"{skill_name}/main.py", "--job-dir", str(job_dir)],
        capture_output=True, text=True, timeout=300
    )
    return read_json(job_dir / f"{skill_name}.json")
```

### 2.3 评审循环

```python
# app/services/workflow.py
async def run_critic_loop(draft: PlatformDraft):
    for _ in range(MAX_REVISIONS):
        feedback = await critic.evaluate(draft)
        if feedback.decision == "pass":
            draft.status = DraftStatus.PASSED
            break
        draft = await revise(draft, feedback)
```

## 3. 测试指南

### 3.1 运行测试

```bash
# 项目根目录
cd "y:\TYUT\creating learning club\feishu-media-flow-main"

# 运行全部单元测试
pytest tests/ -v

# 运行指定测试
pytest tests/test_commands.py -v
pytest tests/test_idempotency.py -v
pytest tests/test_feishu_api.py -v
```

### 3.2 测试文件说明

| 文件 | 测试内容 |
|------|---------|
| `test_commands.py` | 命令解析逻辑 |
| `test_idempotency.py` | 幂等去重 |
| `test_feishu_api.py` | 飞书 API 调用 |
| `test_scheduler.py` | 排期调度 |
| `test_skill_runner.py` | 技能调度 |
| `test_wechat.py` | 公众号集成 |
| `test_agent_loop.py` | Agent 主循环 |
| `test_agent_media_delivery.py` | 媒体交付 |
| `test_campus_media.py` | 校园媒体 |

### 3.3 测试产物

pytest 运行后生成 `.pytest_cache/` 目录，包含测试缓存。测试本身不产生额外产物文件。

## 4. 调试技巧

### 4.1 启用调试日志

```bash
# 设置日志级别
$env:LOG_LEVEL="DEBUG"
uvicorn app.main:app --reload --log-level debug
```

### 4.2 本地测试 webhook

使用 ngrok 或类似工具将本地服务暴露到公网：

```bash
ngrok http 8000
# 将 ngrok URL 配置到飞书应用的事件订阅地址
```

### 4.3 跳过飞书校验（开发模式）

在 `config.py` 中设置 `FEISHU_VERIFY_TOKEN` 为空可跳过 token 校验。

## 5. 常见问题

### Q1: 飞书事件回调返回 403

检查 `FEISHU_VERIFICATION_TOKEN` 是否与飞书开放平台配置一致。

### Q2: 技能模块执行超时

检查 `skill_runner.py` 中的 timeout 设置（默认 300s），LLM 调用可能较慢。

### Q3: 多维表格写入失败

检查飞书应用的表格权限是否已授予，以及表 ID 配置是否正确。

### Q4: LLM 调用失败

确认 `.env` 中 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL` 配置正确。文本模块需额外配置 `LLM_TEXT_MODEL=qwen-plus`。

---

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21
