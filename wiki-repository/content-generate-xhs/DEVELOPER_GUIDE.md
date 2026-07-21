# content-generate-xhs 开发者指南

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 1. 模块间数据交互

### 1.1 上游输入

```
app/skill_runner → job_dir/input.json → content-generate-xhs
```

`skill_runner` 创建 job 目录，写入 `input.json`（含 content_id、job_id、topic、materials、brand），通过子进程调用 `main.py --job-dir`。

### 1.2 下游输出

```
content-generate-xhs → content-generate-xhs.json → 下游消费
```

输出 JSON 被以下模块消费：
- **image-compose**：读取 `step1_analyze` 字段生成封面图
- **risk-check**：对 `body` 和 `hashtags` 进行风险检测
- **content-review-polish**：对正文进行润色评审

### 1.3 数据依赖

| 依赖 | 路径 | 说明 |
|------|------|------|
| 平台约束 | `app/prompts/platform_constraints.json` | XHS 静态约束规则 |
| 偏好画像 | `.data/profiles/xhs_profile.json` | V2 Schema 动态画像（可选，7天过期） |

## 2. 内部工作流

```
input.json
  → read_json() + require_fields()     # 读取 & 校验
  → build_client()                      # 创建 OpenAI 客户端
  → step1_analyze (LLM)                # 选题分析：拆解为三个角度
  → step2_titles (LLM)                 # 标题生成：3 候选 + 选定 1
  → step3_body (LLM)                   # 正文撰写：body + hashtags + cover_text
  → step4_review (LLM)                 # 审查修复：评分 + 修复 + 最终 JSON
  → normalize_final()                   # 字段提取 & 回退
  → validate_output()                   # 硬指标校验
  → content-generate-xhs.json           # 写入结果
```

每个 step 通过 `call_step()` 调用 LLM，共享 `context` dict 传递上下文。JSON 解析失败自动重试 1 次。

## 3. 测试指南

### 3.1 离线 Mock 测试（无需 API Key）

```bash
cd content-generate-xhs
python test_mock.py
```

验证：输入读取、字段校验、Prompt 加载、输出写入、格式验证。

### 3.2 真实 API 测试

```bash
# 确保 .env 已配置 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL
python main.py --job-dir test/fixtures/input_01.json 的父目录
```

### 3.3 批量版本测试

```bash
python run_round.py              # 自动推断版本/轮次，跑 5 个选题
python run_round.py --no-report  # 跳过报告生成
```

测试产物在 `test/results/vN_test/roundN/` 下，每轮含 5 个用例的输出 JSON 和质量报告。

### 3.4 测试产物说明

| 文件 | 说明 |
|------|------|
| `content-generate-xhs.json` | LLM 生成的最终输出 |
| `error.json` | 失败时的错误信息 |
| `logs.txt` | 运行日志 |
| `quality_report.md` | 质量报告（技术指标 + 人工评分区） |
| `vN_test_report.md` | 版本级综合报告（含跨版本对比） |

## 4. 调试技巧

### 4.1 查看 Pipeline 日志

输出 JSON 中的 `pipeline_log` 包含每步的 `duration_ms` 和 `tokens`，可定位慢步骤。

### 4.2 单步调试 Prompt

在 `call_step()` 中设置断点，查看 `messages` 列表即可看到发送给 LLM 的完整 prompt。

### 4.3 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| `missing environment variable(s)` | .env 未加载 | 确保通过 `app` 调度或手动 `load_dotenv()` |
| JSON 解析失败 | LLM 返回非 JSON | 已自动重试；若持续失败检查模型是否支持 JSON mode |
| `body must be 300-1200 characters` | 正文过长/过短 | 调整 step3 prompt 或检查 step4 修复逻辑 |
| 画像未生效 | 画像过期或路径错误 | 检查 `.data/profiles/xhs_profile.json` 的 `gen_at` 是否在 7 天内 |
