# content-generate-douyin 开发者指南

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 1. 模块间数据交互

### 1.1 上游输入
```
app/skill_runner → job_dir/input.json → content-generate-douyin
```

### 1.2 下游输出
```
content-generate-douyin → content-generate-douyin.json → 下游消费
```
- **video-generate**：读取 cards 和 cover_lines 渲染为 PNG 卡片包
- **risk-check**：对 body 和 hashtags 进行风险检测

### 1.3 数据依赖
| 依赖 | 路径 | 说明 |
|------|------|------|
| 偏好画像 | `.data/profiles/douyin_profile.json` | V2 Schema 动态画像（可选，7天过期） |

## 2. 内部工作流
```
input.json
  → read_json() + require_fields()
  → build_client()
  → step1_analyze (LLM) → 选题分析
  → step2_titles (LLM)  → 标题 + 封面大字
  → step3_body (LLM)    → 正文 + 卡片
  → step4_review (LLM)  → 审查修复
  → normalize_final() + normalize_cards()
  → validate_output()
  → content-generate-douyin.json
```

## 3. 测试指南

### 3.1 运行测试
```bash
python main.py --job-dir test/fixtures/case_001
```

### 3.2 测试产物
| 文件 | 说明 |
|------|------|
| `content-generate-douyin.json` | 最终输出（含 cards） |
| `error.json` | 失败时的错误信息 |
| `logs.txt` | 运行日志 |

## 4. 调试技巧
- 输出 JSON 中 `pipeline_log` 含每步耗时和 token 消耗
- 卡片结构不规范时检查 `normalize_cards()` 的归一化逻辑
- 画像未生效检查 `.data/profiles/douyin_profile.json` 的 `gen_at` 是否在 7 天内
