# content-generate-wechat 开发者指南

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 1. 模块间数据交互

### 1.1 上游输入
```
app/skill_runner → job_dir/input.json → content-generate-wechat
```

### 1.2 下游输出
```
content-generate-wechat → content-generate-wechat.json → 下游消费
```
- **risk-check**：对 body_md 进行风险检测
- **image-compose**：根据 image_plan 生成封面和文内配图

### 1.3 数据依赖
| 依赖 | 路径 | 说明 |
|------|------|------|
| 偏好画像 | `.data/profiles/wechat_profile.json` | V2 Schema（可选，7天过期） |

## 2. 内部工作流
```
input.json
  → load_json()
  → generate_wechat_content_with_llm()
      → read_text(system.md) + 注入偏好画像
      → render_template(user_template.md, {topic, column, materials, ...})
      → call_llm(prompt, system) — 含 WebFetch/WebSearch 工具调用
      → parse_llm_json(raw) — 解析 LLM JSON
      → normalize_image_plan() — 配图计划归一化
  → 失败时降级 → generate_wechat_content() — 模板生成
  → content-generate-wechat.json
```

## 3. 测试指南

### 3.1 运行测试
```bash
# 单组测试
python main.py --job-dir test/fixtures/case_001

# 串联 risk-check
python main.py --job-dir test/fixtures/case_001_risk
# 然后运行 risk-check 对输出进行检测
```

### 3.2 测试产物
| 文件 | 说明 |
|------|------|
| `content-generate-wechat.json` | 最终输出（含 body_md、image_plan） |
| `logs.txt` | 运行日志 |
| `error.json` | 失败时的错误信息 |

## 4. 调试技巧
- `llm_enabled` 字段标识是否成功使用了 LLM
- `llm_error` 字段记录降级原因
- WebFetch/WebSearch 调用失败不影响整体流程，LLM 会基于已有素材生成
- 检查 `image_plan` 是否包含 1 张 cover + 2 张 inline
