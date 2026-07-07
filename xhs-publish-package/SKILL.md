# xhs-publish-package

将已生成的小红书内容打包成发布目录结构，方便人工审核和发布。

## 功能概述

本 Skill 接收小红书内容生成结果，将其打包成标准化的发布包目录结构，包含：
- 纯文本文件（标题、正文、话题标签）
- 发布检查清单（checklist.md）
- 资源文件清单（manifest.json）
- 图片资源（如有）

## 输入格式

输入文件：`{job_dir}/input.json`

```json
{
  "content_id": "CNT-20260706-001",
  "job_id": "JOB-20260706-001",
  "title": "招新别只会摆摊",
  "body": "开学季社团招新到了...",
  "hashtags": ["#社团招新", "#大学生活", "#校园运营"],
  "cover_text": "招新转化翻倍",
  "assets": [
    {"type": "image", "path": "cover.png"},
    {"type": "image", "path": "card_01.png"}
  ],
  "scheduled_at": "2026-07-06T20:30:00+08:00"
}
```

**必填字段**：
- `content_id`: 内容唯一标识
- `job_id`: 任务唯一标识
- `title`: 小红书标题
- `body`: 正文内容
- `hashtags`: 话题标签数组

**可选字段**：
- `cover_text`: 封面文字
- `assets`: 资源数组（支持图片）
- `scheduled_at`: 计划发布时间

## 输出格式

输出目录：`{job_dir}/publish_package/`

```
publish_package/
├── title.txt          # 标题文本
├── body.txt           # 正文文本
├── hashtags.txt       # 话题标签（每行一个）
├── checklist.md       # 发布检查清单
├── manifest.json      # 完整元数据
└── assets/            # 图片资源目录
    ├── cover.png
    └── card_01.png
```

**特殊处理**：
- 图片不存在时，创建 `{filename}.missing` 占位文件
- `assets` 为空数组时，不创建 assets 目录

## 运行方式

```bash
python main.py --job-dir {job_dir}
```

**参数**：
- `--job-dir`: 工作目录路径（必须包含 input.json）

**输出文件**：
- 成功：`{job_dir}/xhs_publish_package.json`
- 失败：`{job_dir}/error.json`
- 日志：`{job_dir}/logs.txt`

## 依赖

无外部依赖，纯 Python 标准库实现。

## 测试方法

执行 5 组测试用例：

```bash
# 测试 1: 正常场景（2张图片）
python main.py --job-dir test/fixtures/test_01

# 测试 2: 空 assets 数组
python main.py --job-dir test/fixtures/test_02

# 测试 3: 多图片场景（4张图片）
python main.py --job-dir test/fixtures/test_03

# 测试 4: 无 scheduled_at 字段
python main.py --job-dir test/fixtures/test_04

# 测试 5: 图片缺失场景
python main.py --job-dir test/fixtures/test_05
```

验证输出文件完整性和正确性。

## 错误处理

- 输入文件不存在 → 返回错误
- JSON 格式错误 → 返回错误
- 必填字段缺失 → 返回错误
- 图片文件缺失 → 创建 .missing 占位文件，不中断流程