# xhs-publish-package — 小红书内容发布打包 Skill

&gt; 小红书内容生产流水线的最后一环：将上游生成的文案和图片打包成运营可直接使用的发布包。

---

## 目录

- [功能概述](#功能概述)
- [在流水线中的位置](#在流水线中的位置)
- [快速开始](#快速开始)
- [输入格式详解](#输入格式详解)
- [输出结构详解](#输出结构详解)
- [命令行参数](#命令行参数)
- [与上游 Skill 对接](#与上游-skill-对接)
- [错误处理与容错](#错误处理与容错)
- [目录结构](#目录结构)
- [测试验证](#测试验证)
- [常见问题](#常见问题)

---

## 功能概述

`xhs-publish-package` 是小红书内容生产流水线的**打包发布环节**。它接收上游 Skill（文案生成 + 图片合成）输出的结构化数据，将文案、话题标签、图片等素材打包成标准化目录，方便人工审核后一键发布。

### 核心能力

| 能力 | 说明 |
|------|------|
| 文本拆分 | 将标题、正文、标签分别输出为独立 `.txt` 文件，方便直接复制粘贴 |
| 检查清单 | 自动生成 `checklist.md`，包含完整内容和人工审核检查项 |
| 元数据记录 | 生成 `manifest.json` 记录内容 ID、时间、图片清单等完整元数据 |
| 图片整理 | 将图片资源统一复制到 `assets/` 目录，保持原始文件名 |
| 缺失容错 | 图片缺失时创建 `.missing` 占位文件，不中断整体流程 |
| 完整日志 | 输出 `logs.txt` 记录每一步操作，便于排查问题 |

---

## 在流水线中的位置

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│ content-generate-xhs│     │    image-compose    │     │ xhs-publish-package │
│   (文案生成 Skill)   │────▶│   (图片合成 Skill)   │────▶│   (本 Skill: 打包)   │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
                                                               │
                                                               ▼
                                                    ┌─────────────────────┐
                                                    │  publish_package/   │
                                                    │  (运营审核发布包)    │
                                                    └─────────────────────┘
```

**工作流串联方式**：
1. `content-generate-xhs` 生成标题、正文、话题标签
2. `image-compose` 基于封面文案生成配图（封面 + 卡片）
3. 将文案和图片路径整合为 `input.json`
4. 运行 `xhs-publish-package` 生成标准化发布包
5. 运营人员打开 `checklist.md` 审核内容，复制文本、上传图片发布

---

## 快速开始

### 1. 准备工作目录

在任意位置创建 Job 目录，结构如下：

```
my_job/
├── input.json      # 输入数据（必需）
└── output/         # 图片存放目录（由上游 image-compose 生成）
    ├── cover.png
    └── card_01.png
```

### 2. 编写 input.json

```json
{
  "content_id": "CNT-20260707-001",
  "job_id": "JOB-20260707-001",
  "title": "招新没人来？学长掏心窝子给4条建议",
  "body": "去年九月社团招新，我负责的摊位摆了整整一下午...",
  "hashtags": ["#大学社团招新", "#社团招新攻略", "#大学生干货"],
  "cover_text": "招新转化翻倍",
  "assets": [
    {"type": "image", "path": "./output/cover.png"}
  ],
  "scheduled_at": "2026-07-07T20:30:00+08:00"
}
```

### 3. 运行 Skill

```bash
python main.py --job-dir path/to/my_job
```

### 4. 获取结果

运行成功后，在 `my_job/publish_package/` 目录下获得完整发布包：

```
my_job/publish_package/
├── title.txt       # ← 复制这个到小红书标题栏
├── body.txt        # ← 复制这个到小红书正文
├── hashtags.txt    # ← 复制这些标签
├── checklist.md    # ← 打开这个审核内容
├── manifest.json   # 元数据（归档用）
└── assets/
    └── cover.png   # ← 上传这些图片
```

---

## 输入格式详解

**输入文件**：`{job_dir}/input.json`

### 必填字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `content_id` | string | 内容唯一标识，建议格式 `CNT-YYYYMMDD-NNN` |
| `job_id` | string | 任务唯一标识，建议格式 `JOB-YYYYMMDD-NNN` |
| `title` | string | 小红书标题（最多 20 字，含 emoji） |
| `body` | string | 正文内容，支持空行分段，最长约 1000 字 |
| `hashtags` | string[] | 话题标签数组，每个标签以 `#` 开头 |

### 可选字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `cover_text` | string | `""` | 封面大标题文字（供 image-compose 使用） |
| `assets` | array | `[]` | 资源数组，目前仅支持图片类型 |
| `scheduled_at` | string | `"未设置"` | 计划发布时间，ISO 8601 格式，空字符串显示"未设置" |

### assets 数组项格式

```json
{
  "type": "image",
  "path": "./output/cover.png"
}
```

- `type`: 目前固定为 `"image"`
- `path`: 图片相对路径（相对于 `{job_dir}`），支持 `./` 前缀

### 最小输入示例（无图片）

```json
{
  "content_id": "CNT-TEST-001",
  "job_id": "JOB-TEST-001",
  "title": "测试标题",
  "body": "测试正文内容",
  "hashtags": ["#测试"]
}
```

---

## 输出结构详解

**输出目录**：`{job_dir}/publish_package/`

每次运行会**删除已有的 `publish_package/` 目录并重新创建**，确保输出干净。

### 文件清单

| 文件 | 用途 | 使用者 |
|------|------|--------|
| `title.txt` | 纯标题文本，无任何格式 | 复制到小红书标题栏 |
| `body.txt` | 纯正文文本，保留原始换行 | 复制到小红书正文区 |
| `hashtags.txt` | 每行一个话题标签 | 复制追加到正文末尾 |
| `checklist.md` | 人工审核清单 | 运营审核时打开 |
| `manifest.json` | 完整元数据 | 归档/系统对接 |
| `assets/` | 图片资源目录 | 上传到小红书 |

### checklist.md 模板结构

```markdown
# 小红书发布清单 — {content_id}

建议发布时间：{scheduled_at}

## 标题（复制）
{title}

## 正文（复制）
{body}

## 话题标签（复制）
{hashtags 空格分隔}

## 检查项
- [ ] 图片已下载
- [ ] 标题无错别字
- [ ] 正文通顺
- [ ] 话题标签正确
- [ ] 图片顺序正确
- [ ] 发布时间确认
```

### manifest.json 字段说明

在输入数据基础上自动追加：

| 追加字段 | 类型 | 说明 |
|----------|------|------|
| `package_created_at` | string | 打包时间，ISO 8601 格式 |

### Job 目录根级输出文件

运行结束后，在 `{job_dir}/` 根目录生成状态文件：

| 文件 | 说明 |
|------|------|
| `xhs_publish_package.json` | 成功状态，包含输出路径和文件数量 |
| `error.json` | 失败状态，包含错误信息 |
| `logs.txt` | 详细运行日志（追加写入） |

**成功输出示例**：
```json
{
  "status": "success",
  "timestamp": "2026-07-07T20:59:06.703216",
  "data": {
    "publish_package_path": "e2e_test/test_01/publish_package",
    "files_count": 6
  }
}
```

**失败输出示例**：
```json
{
  "status": "error",
  "timestamp": "2026-07-07T20:59:00.123456",
  "error": "缺少必填字段: title"
}
```

---

## 命令行参数

```bash
python main.py --job-dir &lt;JOB_DIR&gt;
```

| 参数 | 必需 | 说明 |
|------|------|------|
| `--job-dir` | ✅ | Job 目录路径，必须包含 `input.json` |

### 退出码

| 退出码 | 含义 |
|--------|------|
| `0` | 成功（含图片缺失但流程完成的情况） |
| `1` | 失败（输入文件问题、JSON 错误、字段缺失等） |

---

## 与上游 Skill 对接

### 对接 content-generate-xhs

`content-generate-xhs` 输出结构如下：

```json
{
  "status": "success",
  "data": {
    "selected_title": "招新没人来？学长掏心窝子给4条建议",
    "body": "正文内容...",
    "hashtags": ["#大学社团招新", "#社团招新攻略"],
    "cover_text": "招新转化翻倍",
    "selected_title_index": 0,
    "all_titles": ["标题1", "标题2", "标题3"]
  }
}
```

**字段映射**：

| content-generate-xhs 输出 | xhs-publish-package 输入 |
|---------------------------|--------------------------|
| `data.selected_title` | `title` |
| `data.body` | `body` |
| `data.hashtags` | `hashtags` |
| `data.cover_text` | `cover_text` |
| （自行生成） | `content_id`, `job_id` |

### 对接 image-compose

`image-compose` 在 `{job_dir}/output/` 下生成图片，如：
- `output/xhs-cover-01.png`（封面图）
- `output/xhs-card-01.png`（内容卡片）

在 `input.json` 的 `assets` 中引用这些相对路径即可：

```json
{
  "assets": [
    {"type": "image", "path": "./output/xhs-cover-01.png"},
    {"type": "image", "path": "./output/xhs-card-01.png"}
  ]
}
```

### 完整串联示例（Python 脚本）

```python
import json
from pathlib import Path
import subprocess

job_dir = Path("jobs/my_post")
job_dir.mkdir(exist_ok=True)

# 1. 假设 content_result 是 content-generate-xhs 的输出
# 2. 假设 image-compose 已在 job_dir/output/ 下生成了图片

input_data = {
    "content_id": "CNT-20260707-001",
    "job_id": "JOB-20260707-001",
    "title": content_result["data"]["selected_title"],
    "body": content_result["data"]["body"],
    "hashtags": content_result["data"]["hashtags"],
    "cover_text": content_result["data"]["cover_text"],
    "assets": [
        {"type": "image", "path": "./output/cover.png"}
    ],
    "scheduled_at": "2026-07-07T20:30:00+08:00"
}

# 写入 input.json
(job_dir / "input.json").write_text(
    json.dumps(input_data, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

# 运行 xhs-publish-package
result = subprocess.run(
    ["python", "main.py", "--job-dir", str(job_dir)],
    capture_output=True, text=True
)

if result.returncode == 0:
    print("打包成功！打开 publish_package/checklist.md 进行审核")
```

---

## 错误处理与容错

| 场景 | 处理方式 | 退出码 |
|------|----------|--------|
| `input.json` 文件不存在 | 返回错误，写入 `error.json` | 1 |
| `input.json` JSON 格式错误 | 返回错误，写入 `error.json` | 1 |
| 必填字段（title/body/hashtags 等）缺失 | 返回错误，写入 `error.json` | 1 |
| 图片文件不存在 | 创建 `{filename}.missing` 占位文件，**继续执行** | 0 |
| assets 数组为空 | 不创建 `assets/` 目录，正常输出其他文件 | 0 |
| `scheduled_at` 为空字符串 | checklist 中显示"未设置" | 0 |

### 图片缺失占位文件内容示例

```
原始路径: ./output/not_exists.png
文件缺失，请检查上游图片生成是否完成
```

### 日志级别

| 级别 | 使用场景 |
|------|----------|
| `INFO` | 正常流程节点（加载文件、生成文件、复制图片等） |
| `WARNING` | 非致命问题（图片缺失、跳过非图片资源等） |
| `ERROR` | 致命错误（文件不存在、JSON 解析失败等） |

---

## 目录结构

```
xhs-publish-package/
├── main.py                  # 主程序入口
├── SKILL.md                 # Skill 定义文件（给 AI 读的）
├── README.md                # 本文件（给人读的）
├── requirements.txt         # 依赖声明（无外部依赖）
├── history/
│   └── v1.md                # v1 版本开发记录
├── 使用说明.md               # 中文使用指南
├── test/                    # 单元测试
│   ├── setup_tests.py       # 测试数据初始化
│   ├── run_tests.py         # 测试执行脚本
│   ├── fixtures/            # 5 组测试用例
│   │   ├── test_01/         # 正常场景（2图）
│   │   ├── test_02/         # 空 assets
│   │   ├── test_03/         # 多图（4图）
│   │   ├── test_04/         # 无 scheduled_at
│   │   └── test_05/         # 图片缺失
│   ├── results/             # 测试结果（JSON）
│   └── quality_review.md    # 质量评审报告
└── e2e_test/                # 端到端集成测试（使用真实上游数据）
    ├── test_01/             # 社团招新（单图）
    ├── test_02/             # 创业主题（多图）
    ├── test_03/             # 图片缺失场景
    └── e2e_test_report.md   # 端到端测试报告
```

---

## 测试验证

### 运行单元测试

```bash
cd xhs-publish-package
python test/run_tests.py
```

5 组固定测试用例覆盖：正常场景、空 assets、多图片、无排期、图片缺失。

### 运行端到端测试

端到端测试使用上游 `content-generate-xhs` 和 `image-compose` 的真实输出数据，位于 `e2e_test/` 目录：

```bash
# Test 01: 社团招新（单图，来自 content-generate-xhs round3/test_01）
python main.py --job-dir e2e_test/test_01

# Test 02: 创业主题（3图，无排期，来自 round3/test_03）
python main.py --job-dir e2e_test/test_02

# Test 03: 图片缺失容错测试
python main.py --job-dir e2e_test/test_03
```

详细测试报告见 [e2e_test_report.md](file:///y:/TYUT/Skills/xhs-publish-package/e2e_test/e2e_test_report.md)。

### 手动验证检查清单

运行成功后，请手动确认以下内容：

- [ ] `title.txt` 内容正确，无多余换行
- [ ] `body.txt` 空行分段正确，无文字丢失
- [ ] `hashtags.txt` 每个标签独占一行
- [ ] `checklist.md` 内容完整，无 `{variable}` 残留
- [ ] `assets/` 目录下图片可正常打开
- [ ] 若有缺失图片，`.missing` 文件存在且内容有提示
- [ ] `manifest.json` 包含 `package_created_at` 字段
- [ ] `logs.txt` 无 ERROR 级别日志

---

## 常见问题

### Q: 图片路径应该怎么写？

A: `assets[].path` 是相对于 `{job_dir}` 的相对路径。推荐写法：
- `./output/cover.png`（推荐，显式表示相对路径）
- `output/cover.png`（也支持）

不推荐使用绝对路径，如果上游返回绝对路径，请自行转换为相对路径。

### Q: 支持图片重命名吗？

A: 不做重命名，保持原始文件名复制到 `assets/`。如需重命名，请在准备 `input.json` 时自行处理。

### Q: 可以在同一个 job_dir 多次运行吗？

A: 可以。每次运行会先删除已有的 `publish_package/` 目录再重新创建，不会叠加旧文件。日志 `logs.txt` 是追加写入的，多次运行会保留历史记录。

### Q: 支持视频资源吗？

A: 当前版本仅处理 `type: "image"` 的资源，视频类型会被跳过并输出 WARNING 日志。如需视频支持请提需求。

### Q: 支持自定义 checklist 模板吗？

A: 当前版本 checklist 模板内置在代码中。如需自定义，可直接修改 `main.py` 中 `generate_checklist()` 函数的模板字符串。

### Q: body.txt 的换行能保留小红书的段落格式吗？

A: 是的。`body.txt` 原样写入 `body` 字段内容，空行分段完全保留。复制粘贴到小红书编辑器时，段落格式与原文一致。

### Q: 没有任何图片，能正常运行吗？

A: 可以。`assets` 为空数组或不提供该字段时，不创建 `assets/` 目录，其他文件正常生成。发布时直接发纯文字笔记即可。

---

## 依赖要求

- Python 3.8+
- 无第三方依赖（仅使用标准库：`argparse`, `json`, `logging`, `shutil`, `pathlib`, `datetime`）

---

## 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-07-07 | 初始版本，包含文本拆分、checklist 生成、图片复制、缺失容错功能 |

---

## License

内部 Skill，仅限 TYUT 小红书专线项目使用。
