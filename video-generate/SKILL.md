# video-generate（兼容名）

## 功能说明

此目录保留历史名称，避免已经部署的工作流失效。当前功能是生成抖音图文卡片包，不生成 MP4、不生成语音，也不调用 MoneyPrinterTurbo。

输出使用与小红书一致的可复用视觉系统：1 张封面加 4–7 张正文卡片，最后一张为总结卡。默认尺寸为 1080×1350 PNG。

系统会按主题整组选型：问答、对比、科普、复盘、观点等内容使用白底黑线的校园手绘模板；通知、招新、报名、活动、清单和流程使用校园编辑海报模板。同一组图片始终保持同一视觉系统。

## 输入

输入文件固定为 `{job_dir}/input.json`，主要字段：

- `content_id`：内容 ID。
- `job_id`：任务 ID。
- `topic`：选题。
- `selected_title`、`cover_lines`：封面文案。
- `cards`：按顺序排列的正文卡片数据。
- `body`、`hashtags`：抖音发布文案和标签。
- `image_mode`：`template` 或 `ai_bg`。AI 只用于封面背景，并强制大学校园和大学生场景约束。
- `visual_style`：可选 `auto`、`comic`、`editorial`，默认 `auto`；显式值覆盖主题判断。
- `ai_all_cards`：默认 `false`，设为 `true` 时才为每张正文卡调用 AI；默认只在封面使用 AI，控制耗时与成本。

## 输出

结果写入 `{job_dir}/video-generate.json`：

- `publish_mode`：固定为 `manual_upload`。
- `cover_path`：首张封面路径。
- `card_paths`：全部图片的有序路径。
- `visual_style`：整组实际使用的视觉系统。
- `cards`：包含页码、用途、模板、视觉系统和情景构图变体的清单。
- `caption`、`hashtags`：手动上传抖音时使用的文案。

图片写入 `{job_dir}/output/card_01.png`、`card_02.png` 等文件。系统只把卡片发到飞书，由用户手动上传抖音。

## 运行方式

```bash
python video-generate/main.py --job-dir video-generate/test/fixtures/card-video
```
