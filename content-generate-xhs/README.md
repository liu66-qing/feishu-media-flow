# content-generate-xhs — 小红书图文文案生成 Skill

基于选题和素材，自动生成符合小红书平台风格的图文笔记文案（标题、正文、话题标签、封面文案）。是社团自媒体工作流中小红书专线的核心模块。

当前版本：**v3**（段落节奏优化版）

---

## 目录结构

```
content-generate-xhs/
├── README.md                  ← 本文件
├── SKILL.md                   ← Skill 定义与规范说明（输入输出、字段定义、工作流程）
├── main.py                    ← 核心执行入口（LLM 调用、JSON 解析、结果写入）
├── run_round.py               ← 自动化批量测试脚本（跑5个选题一轮 + 自动生成质量报告）
├── requirements.txt           ← Python 依赖（openai、python-dotenv）
├── test_mock.py               ← Mock 测试脚本（不调 LLM，验证核心流程逻辑）
│
├── prompts/
│   ├── system.md              ← 系统提示词（v3，定义写作规则、段落节奏、风格约束、自检清单）
│   ├── user_template.md       ← 用户提示词模板（动态填充 topic/materials/brand 等字段）
│   └── history/
│       ├── v1.md              ← v1 版本 Prompt 历史记录（基线版本）
│       ├── v2.md              ← v2 版本 Prompt 历史记录（第一人称/禁止符号编号/cover字数/risk_notes）
│       └── v3.md              ← v3 版本 Prompt 历史记录（段落节奏专项优化）
│
└── test/
    ├── fixtures/              ← 测试输入用例（5个固定选题）
    │   ├── input_01.json      ← 选题：大学社团招新
    │   ├── input_02.json      ← 选题：校园恋爱
    │   ├── input_03.json      ← 选题：大学生创业
    │   ├── input_04.json      ← 选题：大学生社交
    │   └── input_05.json      ← 选题：大学生学习和就业
    │
    ├── expected/
    │   └── output.json        ← 期望输出格式参考（非自动校验用，作示例）
    │
    ├── quality_review.md      ← 早期人工质量评审记录（v1 阶段）
    │
    └── results/               ← 各版本测试结果
        ├── v1_test/
        │   ├── round1/        ← v1 第一轮测试结果（5篇 + 质量报告）
        │   ├── round2/        ← v1 第二轮测试结果
        │   ├── round3/        ← v1 第三轮测试结果
        │   └── v1_test_report.md  ← v1 综合测试报告
        ├── v2_test/
        │   ├── round1~3/      ← v2 三轮测试结果
        │   └── v2_test_report.md  ← v2 综合测试报告
        └── v3_test/
            ├── round1~3/      ← v3 三轮测试结果（每轮5篇 output + quality_report.md）
            └── v3_test_report.md  ← v3 综合测试报告（含 v1/v2/v3 对比）
```

---

## 核心文件说明

### 执行入口

**[main.py](file:///y:/TYUT/Skills/content-generate-xhs/main.py)**

Skill 的主程序，负责：
1. 读取 `{job_dir}/input.json`，校验必填字段（`content_id`、`job_id`、`topic`）
2. 加载 [prompts/system.md](file:///y:/TYUT/Skills/content-generate-xhs/prompts/system.md) 和 [prompts/user_template.md](file:///y:/TYUT/Skills/content-generate-xhs/prompts/user_template.md)
3. 用素材和品牌信息填充模板，调用 LLM（通过环境变量 `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` 配置）
4. 解析 LLM 返回的 JSON（含自动重试2次、代码块剥离、双重转义换行符修复）
5. 将结果写入 `{job_dir}/content-generate-xhs.json`，错误则写入 `error.json`
6. 日志记录到 `{job_dir}/logs.txt`

运行方式：
```bash
python main.py --job-dir <job目录路径>
```

### 测试工具

**[run_round.py](file:///y:/TYUT/Skills/content-generate-xhs/run_round.py)**

自动化批量测试脚本，功能包括：
- **自动版本管理**：扫描 `test/results/` 目录，自动推断下一个版本号和轮次（v1→v2→v3，每版本3轮）
- **批量执行**：复制 `test/fixtures/` 下的5个 input 文件到独立 test_nn 目录，逐个调用 `main.py` 执行
- **硬指标校验**：自动检测标题数量/长度、正文字数、标签数量/格式、封面字数、绝对化风险词等
- **自动报告**：运行结束后生成 `quality_report.md` 模板，含技术指标表格、段落数统计、待人工评分区域

运行方式：
```bash
python run_round.py                      # 自动推断版本/轮次
python run_round.py --no-report          # 跳过报告生成
python run_round.py --retries 1          # 自定义失败重试次数
```

**[test_mock.py](file:///y:/TYUT/Skills/content-generate-xhs/test_mock.py)**

离线 Mock 测试脚本，不调用 LLM，使用内置的 MOCK_RESPONSE 验证：输入读取、字段校验、Prompt 文件加载、输出写入、格式验证等核心流程。用于在无网络/无 API Key 环境下快速验证代码逻辑。

运行方式：
```bash
python test_mock.py
```

### Prompt 文件

**[prompts/system.md](file:///y:/TYUT/Skills/content-generate-xhs/prompts/system.md)**（v3 当前版本）

系统提示词，约 2000+ 字，定义了小红书文案生成的全部规则，核心章节包括：
1. 角色定义（学姐/学长视角，第一人称分享）
2. 输出格式（JSON 结构字段说明）
3. 内容要求（开头钩子、干货结构、真诚表达、互动结尾）
4. 风格红线（禁 emoji/符号编号、禁营销腔、禁绝对化用词）
5. 标签规则（5-8个，精准适配）
6. **段落节奏**（v3 新增，强制 22-32 段，每段 1-2 句，含正反示范和三段式拆法）
7. 封面文案（10-12字，含正反示例）
8. Few-shot 示例（校园恋爱话题完整示范）
9. 10项自检清单

**[prompts/user_template.md](file:///y:/TYUT/Skills/content-generate-xhs/prompts/user_template.md)**

用户侧模板，使用 `{topic}`、`{column}`、`{materials}`、`{tone}`、`{audience}` 等占位符，运行时动态填充。v3 版本增加了段落约束提醒。

**[prompts/history/](file:///y:/TYUT/Skills/content-generate-xhs/prompts/history)**

历次 Prompt 迭代历史存档：
- [v1.md](file:///y:/TYUT/Skills/content-generate-xhs/prompts/history/v1.md)：基线版本，基础框架
- [v2.md](file:///y:/TYUT/Skills/content-generate-xhs/prompts/history/v2.md)：修复 emoji/编号问题、强化第一人称、增加 risk_notes、cover 字数约束
- [v3.md](file:///y:/TYUT/Skills/content-generate-xhs/prompts/history/v3.md)：段落节奏专项优化，解决长段落问题

### 测试数据

**[test/fixtures/](file:///y:/TYUT/Skills/content-generate-xhs/test/fixtures)**

5个固定测试选题，覆盖校园内容主要场景：

| 文件 | 选题 | 栏目 | 素材数 |
|------|------|------|:---:|
| [input_01.json](file:///y:/TYUT/Skills/content-generate-xhs/test/fixtures/input_01.json) | 大学社团招新实用攻略 | 校园干货 | 5条 |
| [input_02.json](file:///y:/TYUT/Skills/content-generate-xhs/test/fixtures/input_02.json) | 校园恋爱/情感 | 情感 | 多条 |
| [input_03.json](file:///y:/TYUT/Skills/content-generate-xhs/test/fixtures/input_03.json) | 大学生创业 | 经验干货 | 多条 |
| [input_04.json](file:///y:/TYUT/Skills/content-generate-xhs/test/fixtures/input_04.json) | 大学生社交/社恐 | 校园生活 | 多条 |
| [input_05.json](file:///y:/TYUT/Skills/content-generate-xhs/test/fixtures/input_05.json) | 大学生学习和就业 | 规划 | 多条 |

**[test/results/](file:///y:/TYUT/Skills/content-generate-xhs/test/results)**

各版本测试产出，每个版本目录下包含3轮测试子目录。每轮目录结构：
```
roundN/
├── run.log                    ← 本轮运行日志（时间戳、每个用例的成功/失败、统计汇总）
├── quality_report.md          ← 质量报告（自动生成技术指标 + 人工填写肉眼评分和点评）
└── test_01~test_05/
    ├── input.json             ← 该测试用例的输入（从 fixtures 复制）
    ├── content-generate-xhs.json  ← LLM 生成的输出结果（成功时）
    ├── error.json             ← 错误信息（失败时）
    └── logs.txt               ← 该用例的运行日志
```

版本级别的综合报告（如 [v3_test_report.md](file:///y:/TYUT/Skills/content-generate-xhs/test/results/v3_test/v3_test_report.md)）包含三轮数据汇总、跨版本对比（v1/v2/v3 指标变化）、标杆篇目推荐、问题根因分析和下版改进建议。

### 配置与文档

**[SKILL.md](file:///y:/TYUT/Skills/content-generate-xhs/SKILL.md)**

Skill 的标准定义文件，包含：
- Skill 元信息（name、description，YAML frontmatter）
- 功能定位与职责边界
- 完整的输入/输出 JSON 字段定义（含字段类型、必填性、取值范围）
- 工作流程8步骤
- 错误处理表与边界情况说明
- 质量标准与测试通过标准
- 环境变量配置说明

**[requirements.txt](file:///y:/TYUT/Skills/content-generate-xhs/requirements.txt)**

Python 依赖：
- `openai>=1.0.0`：用于调用 LLM API
- `python-dotenv>=1.0.0`：从 `.env` 文件加载环境变量

---

## 环境配置

需要设置以下环境变量（可通过 `.env` 文件配置）：

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `LLM_API_KEY` | LLM API Key | —（必填） |
| `LLM_BASE_URL` | LLM API 地址 | `https://api.openai.com/v1` |
| `LLM_MODEL` | 使用的模型名称 | `qwen3.6-plus`（实际配置） |

---

## 版本迭代摘要

| 版本 | 核心改进 | 段落合规率 | 肉眼均分 | 标杆篇目 |
|------|---------|:---:|:---:|:---:|
| v1 | 初版基线 | ~27% | 19.5/25 | 0篇 |
| v2 | 第一人称+禁符号编号+cover字数+risk_notes | ~27% | 20.4/25 | 1篇（23分） |
| **v3** | **段落节奏专项优化（22-32段、每段1-2句）** | **80%** | **21.7/25** | **5篇（含1篇满分25分）** |

v3 质量评级：**A-（优秀）**，已达到生产可用水平。详细对比见 [v3 综合测试报告](file:///y:/TYUT/Skills/content-generate-xhs/test/results/v3_test/v3_test_report.md)。

---

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量（或创建 .env 文件）
set LLM_API_KEY=your_api_key_here

# 3. 运行一轮完整测试（5个选题）
python run_round.py

# 4. 或离线验证流程（无需API Key）
python test_mock.py

# 5. 或对单个选题运行
python main.py --job-dir ./test/fixtures
```
