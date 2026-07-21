# xhs-publish-package 技术设计文档

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 1. 架构概览

```
┌──────────────────────────────────────────────────────────────┐
│                    xhs-publish-package                        │
├──────────────────────────────────────────────────────────────┤
│  input.json (title + body + hashtags + assets)                │
│    ↓                                                          │
│  validate_input() — 校验必填字段                              │
│    ↓                                                          │
│  create_publish_directory() — 创建 publish_package/ 目录      │
│    ↓                                                          │
│  generate_text_files() — 输出 title/body/hashtags.txt         │
│    ↓                                                          │
│  generate_checklist() — 生成 checklist.md 审核清单            │
│    ↓                                                          │
│  generate_manifest() — 生成 manifest.json 元数据              │
│    ↓                                                          │
│  copy_assets() — 复制图片到 assets/（缺失创建 .missing）      │
│    ↓                                                          │
│  xhs_publish_package.json (成功) / error.json (失败)          │
└──────────────────────────────────────────────────────────────┘
```

## 2. 核心数据结构

### 2.1 输入

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| content_id | string | ✅ | 内容唯一标识 |
| job_id | string | ✅ | 任务唯一标识 |
| title | string | ✅ | 小红书标题 |
| body | string | ✅ | 正文内容 |
| hashtags | list[str] | ✅ | 话题标签数组 |
| assets | list[dict] | — | 资源数组 `[{type: "image", path: "..."}]` |
| cover_text | string | — | 封面文字 |
| scheduled_at | string | — | 计划发布时间（ISO 8601） |

### 2.2 输出目录结构

```
publish_package/
├── title.txt          ← 纯标题文本
├── body.txt           ← 纯正文文本
├── hashtags.txt       ← 每行一个标签
├── checklist.md       ← 人工审核清单
├── manifest.json      ← 完整元数据 + package_created_at
└── assets/            ← 图片资源（复制自上游）
    ├── cover.png
    └── card_01.png
```

### 2.3 状态输出

| 文件 | 字段 | 说明 |
|------|------|------|
| xhs_publish_package.json | publish_package_path | 发布包目录路径 |
| | files_count | 总文件数（5 + 图片数） |
| error.json | error | 错误信息 |

## 3. 关键函数

### `validate_input(input_data) -> None`
校验 5 个必填字段（content_id, job_id, title, body, hashtags），缺失时抛出 ValueError。

### `create_publish_directory(job_dir) -> Path`
若 `publish_package/` 已存在则删除重建，确保输出干净。同时创建 `assets/` 子目录。

### `generate_text_files(publish_dir, input_data)`
将 title / body / hashtags 分别写入独立 `.txt` 文件，hashtags 每行一个。

### `generate_checklist(publish_dir, input_data)`
生成 Markdown 格式的发布清单，包含完整内容预览和 6 项人工检查项（图片、标题、正文、标签、顺序、时间）。

### `copy_assets(job_dir, publish_dir, input_data) -> int`
遍历 assets 数组，复制存在的图片到 `assets/`，不存在的创建 `.missing` 占位文件。返回成功复制数量。非 `type: "image"` 的资源跳过。

## 4. 容错机制

| 场景 | 处理方式 |
|------|----------|
| 图片文件不存在 | 创建 `{filename}.missing` 占位文件，继续执行 |
| assets 为空 | 不创建 assets 目录，正常输出其他文件 |
| scheduled_at 为空 | checklist 显示"未设置" |
| 非图片资源 | 跳过并输出 WARNING 日志 |
| publish_package 已存在 | 删除重建，保证干净输出 |

## 5. 设计决策

1. **零外部依赖**：纯标准库实现（argparse/json/logging/shutil/pathlib/datetime），部署简单
2. **删除重建策略**：每次运行清空 publish_package/，避免旧文件残留
3. **缺失不中断**：图片缺失只创建占位文件，不阻断打包流程，运营可先发布文字部分
4. **日志追加模式**：logs.txt 使用 append 模式，多次运行保留历史
5. **相对路径支持**：assets path 支持 `./` 前缀，方便上游直接拼接

---

> Created by: 尹羿璇 | 2026-07-21
