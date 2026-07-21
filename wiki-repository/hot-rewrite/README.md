# hot-rewrite

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

热帖改写技能包（LLM版）。

读取原文，调用 LLM 从新角度改写为原创内容，使用 Simhash 计算相似度并自动重试，确保改写结果与原文相似度低于 30%。

**技术方案**：OpenAI 兼容 API（LLM 改写） + Simhash（相似度校验）
**输入格式**：JSON（`input.json`）
**输出格式**：JSON（`hot_rewrite.json`）

---

## 快速开始

### 1. 安装依赖

```bash
cd hot-rewrite
pip install -r requirements.txt
```

### 2. 配置环境变量

在项目根目录 `.env` 中配置：

```env
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-5.4-mini
```

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `LLM_API_KEY` | 是 | — | LLM API 密钥 |
| `LLM_BASE_URL` | 否 | `https://api.openai.com/v1` | API 地址 |
| `LLM_MODEL` | 否 | `gpt-5.4-mini` | 模型名称 |

### 3. 准备输入数据

在任意目录创建 `input.json`：

```json
{
  "content_id": "CNT-HOT-001",
  "job_id": "JOB-HOT-001",
  "source_url": "https://example.com/source-post-001",
  "source_text": "原始热帖正文...",
  "target_platform": "xhs",
  "target_column": "经验干货",
  "rewrite_angle": "从大学生社团负责人的视角"
}
```

### 4. 运行改写

```bash
python hot-rewrite/main.py --job-dir hot-rewrite/test/fixtures/case_001
```

**参数说明**：
- `--job-dir`：必填，指定包含 `input.json` 的目录路径

运行成功后，输出文件位于 `{job_dir}/` 下：
- 改写结果：`hot_rewrite.json`
- 运行日志：`logs.txt`

---

## 工作流程

```
读取 input.json
    ↓
调用 LLM 分析原文爆点 + 改写内容
    ↓
Simhash 计算相似度
    ↓
similarity_score > 0.3？ ──是──→ 追加重试提示，重新调用 LLM（最多 2 次）
    │                                    ↓
    │                              再次计算相似度
    ↓ 否
输出 hot_rewrite.json
```

---

## 输入字段详解

### 必填字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `source_text` | string | 原始热帖正文 |

### 可选字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `content_id` | string | `""` | 内容 ID，用于输出元数据 |
| `job_id` | string | `""` | 任务 ID |
| `source_url` | string | `""` | 原文来源链接 |
| `target_platform` | string | `"xhs"` | 目标平台 |
| `target_column` | string | `"经验干货"` | 目标栏目 |
| `rewrite_angle` | string | `""` | 改写角度提示 |

---

## 输出格式

### 成功输出（`{job_dir}/hot_rewrite.json`）

```json
{
  "status": "success",
  "timestamp": "2026-07-14T12:00:00",
  "content_id": "CNT-HOT-001",
  "data": {
    "original_analysis": {
      "hook": "原文开头或标题的核心吸引点",
      "structure": "原文段落结构和逻辑脉络",
      "viral_points": ["爆点1", "爆点2", "爆点3"],
      "target_audience": "目标读者群体"
    },
    "rewritten_content": {
      "title": "改写后的标题",
      "body": "改写后的正文",
      "hashtags": ["#标签1", "#标签2", "#标签3"]
    },
    "similarity_score": 0.15,
    "similarity_method": "simhash_normalized_from_raw_baseline_0.5",
    "source_attribution": {
      "url": "https://example.com/source-post-001",
      "note": "灵感来自原始内容，已重构角度、结构和表达方式。"
    },
    "risk_notes": [],
    "llm_enabled": true,
    "llm_error": ""
  }
}
```

### 失败输出（`{job_dir}/error.json`）

```json
{
  "status": "failed",
  "timestamp": "2026-07-14T12:00:00",
  "error": "LLM_API_KEY is not set"
}
```

### 相似度超标失败（`hot_rewrite.json` 中 `status = "failed"`）

```json
{
  "status": "failed",
  "data": {
    "similarity_score": 0.45,
    "risk_notes": [
      "similarity_score=0.45，经过 2 次重试后仍超过 0.3，改写结果与原文相似度过高，建议人工介入。"
    ]
  }
}
```

---

## 相似度规则

使用 Simhash 计算改写结果与原文的文本相似度：

| 分数 | 计算方式 |
|------|----------|
| `simhash_raw_score` | `1 - distance / 64` |
| `similarity_score` | `max(0, (simhash_raw_score - 0.5) * 2)` |

**归一化原因**：Simhash 原始分数对中文同主题短文本偏高，0.5 附近常代表随机基线，因此使用归一化后的 `similarity_score` 作为验收标准。

| similarity_score | 结果 |
|------------------|------|
| `< 0.3` | success |
| `>= 0.3` | 自动重试，最多 2 次；仍超标则 failed |

---

## 自动重试机制

当改写结果相似度超过 0.3 时，系统自动重试：

1. **第 1 次重试**：在 prompt 中追加重试提示，告知上次相似度分数，要求从完全不同的角度改写
2. **第 2 次重试**（最后一次）：再次追加更强的改写要求
3. **超过 2 次仍未通过**：标记为 `failed`，建议人工介入

---

## 改写 Prompt 核心原则

LLM 改写遵循以下原则（定义在 `prompts/system.md`）：

1. **保留原文核心信息**：不丢失关键事实、数据和观点
2. **换表达角度/叙事风格**：从不同视角切入（如第一人称→第三人称分析、案例叙述→方法论拆解）
3. **不编造事实**：所有信息来源于原文
4. **不复制连续表达**：不直接复制原文连续超过 10 个字
5. **避免违规内容**：不含绝对化承诺、夸大效果、站外引流

---

## 测试

### 测试用例

`test/fixtures/` 中包含测试输入：

| 测试组 | 说明 |
|--------|------|
| case_001 | 社团招新主题热帖改写 |
| case_001_risk | 风险检测对照用例 |

### 运行测试

```bash
# 单组测试
python hot-rewrite/main.py --job-dir hot-rewrite/test/fixtures/case_001

# 验证相似度
python -c "
import json
from hot_rewrite.main import similarity

with open('hot-rewrite/test/fixtures/case_001/input.json') as f:
    source = json.load(f)['source_text']
with open('hot-rewrite/test/fixtures/case_001/hot_rewrite.json') as f:
    result = json.load(f)

rewritten = result['data']['rewritten_content']
text = rewritten['title'] + '\n' + rewritten['body']
score, raw = similarity(source, text)
print(f'similarity_score={score}, raw_score={raw}')
"
```

### 测试检查项

- [ ] `status` 为 `"success"`
- [ ] `similarity_score < 0.3`
- [ ] `original_analysis` 包含 `hook`、`structure`、`viral_points`（≥3 条）、`target_audience`
- [ ] `rewritten_content` 包含 `title`、`body`、`hashtags`
- [ ] 改写内容角度不同于原文，但保留核心信息
- [ ] 无编造原文不存在的事实

---

## 常见问题

### Q1: 报错 `RuntimeError: LLM_API_KEY is not set`

确保环境变量已配置。在项目根目录 `.env` 中设置 `LLM_API_KEY`，或在终端直接 `set LLM_API_KEY=sk-xxx`。

### Q2: 相似度一直超标怎么办？

- 检查 LLM 模型是否正确支持中文输出
- 尝试在 `rewrite_angle` 中提供更具体的改写角度
- 可调整 `MAX_REWRITE_RETRIES` 常量（`main.py` 第 17 行）增加重试次数

### Q3: LLM 返回空内容

检查 `LLM_BASE_URL` 和 `LLM_MODEL` 是否正确，确认 API 配额充足。

---

## 目录结构

```
hot-rewrite/
├── README.md                # 本文件（使用说明）
├── SKILL.md                 # 技能说明文档（面向工作流集成）
├── main.py                  # 主入口
├── requirements.txt         # Python 依赖
├── prompts/
│   ├── system.md            # LLM 系统 prompt
│   └── user_template.md     # LLM 用户 prompt 模板
└── test/
    └── fixtures/            # 测试输入
        ├── case_001/
        └── case_001_risk/
```

---

## 更新日志

### v2.0 (2026-07-14)

- 从模板生成版升级为 LLM 改写版
- 删除硬编码的 `analyze_source()` 和 `rewrite_content()` 函数
- 原文分析和改写均由 LLM 完成，灵活适配不同主题
- 新增自动重试机制：similarity_score > 0.3 时最多重试 2 次
- 更新 prompt：明确保留核心信息、换角度、不编造事实等原则
- SKILL.md 新增环境变量和重试机制说明

### v1.0 (2026-07-06)

- 实现模板生成版改写
- Simhash 相似度校验
- 基础输入输出 JSON 格式

---

## 联系方式

- 负责人：尹羿璇
- 项目：社团自媒体工作流系统
