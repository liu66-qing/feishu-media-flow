# image-compose - 小红书/抖音卡片图片合成

## 功能定位

根据主题自动选择视觉系统并合成小红书、抖音封面图和内容卡片，默认输出 1080x1350 像素的 PNG 图片。支持两种生成模式：
- **template 模式**（默认）：使用 HTML+Playwright 模板合成，速度快、零成本
- **ai_bg 模式**：调用 Qwen-Image-2.0 AI 模型生成氛围感背景图，再通过 HTML+Playwright 叠上标题文字，视觉效果更佳

## 技术方案

**HTML + Playwright**：使用 HTML/CSS 实现模板排版，通过 Playwright 截图生成高质量图片。

**AI 背景图生成（可选）**：通过阿里云百炼 DashScope 原生 API（多模态生成接口）调用 Qwen-Image-2.0-Pro 模型生成竖版背景图，再通过 HTML+Playwright 叠上标题文字，视觉效果更佳。AI 调用失败时自动降级到 template 模式，保证流程不中断。

优点：
- CSS 排版灵活，支持复杂布局
- 文字自动换行、居中效果自然
- AI 背景模式视觉效果接近真实小红书博主封面
- 容错降级，零成本保底可用

## 模板清单

| 模板名 | 用途 | 尺寸 | 设计风格 |
|--------|------|------|---------|
| `xhs-cover-01` | 封面 | 1080x1350 | 简约文字型：纯色背景 + 居中大标题 + 副标题 |
| `xhs-cover-02` | 封面 | 1080x1350 | 卡片型：白色卡片浮于彩色背景上，文字在卡片内 |
| `xhs-cover-03` | 封面 | 1080x1350 | 旧版图文混排型：支持背景图 + 半透明遮罩 + 文字 |
| `xhs-card-01` | 内容卡片 | 1080x1350 | 通用内容卡片：适合展示正文要点、金句 |
| `campus-poster-cover/card/summary` | 封面/正文/总结 | 1080x1350 | 校园编辑海报：适合招新、报名、通知、活动、清单和流程 |
| `campus-comic-cover/card/summary` | 封面/正文/总结 | 1080x1350 | 极简校园手绘：白底、粗黑线、亮蓝强调，适合问答、对比、科普、复盘和观点 |

未指定 `template_name` 时，系统根据主题选择完整模板组，同一组卡片不会混用两套视觉系统。

## 输入格式

### template 模式（默认）

```json
{
  "content_id": "CNT-20260705-001",
  "job_id": "JOB-20260705-001",
  "image_mode": "template",
  "template_name": "",
  "variables": {
    "title": "招新别只会摆摊",
    "subtitle": "3个方法翻倍转化率",
    "visual_style": "auto",
    "template_role": "cover"
  },
  "output_size": {
    "width": 1080,
    "height": 1350
  }
}
```

### ai_bg 模式（AI 生成背景图）

```json
{
  "content_id": "CNT-20260705-001",
  "job_id": "JOB-20260705-001",
  "image_mode": "ai_bg",
  "template_name": "",
  "variables": {
    "title": "掌控情绪的人才能掌控人生",
    "subtitle": "5个心理学技巧",
    "visual_style": "comic",
    "template_role": "cover",
    "ai_prompt": "大学生在校园 AI 展台交流和提问，极简手绘海报，无文字"
  },
  "output_size": {
    "width": 1080,
    "height": 1350
  }
}
```

**注意**：`ai_bg` 模式保留主题选中的模板。AI 生成的插画或背景保存到 `{job_dir}/output/ai_bg.png`；调用失败时继续使用所选模板的内置视觉，不会中断出图。

### 顶层字段说明

| 字段 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `template_name` | 否 | `""` | 留空时按主题自动选择；传具体模板名时固定使用该模板 |
| `image_mode` | 否 | `"template"` | 生成模式：`"template"`（模板合成）或 `"ai_bg"`（AI生成背景+叠字） |
| `content_id` | 否 | "" | 内容 ID |
| `job_id` | 否 | "" | 任务 ID |
| `variables` | 是 | - | 变量字典 |
| `output_size` | 否 | 1080x1350 | 输出尺寸 |

### variables 字段说明

| 字段 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `title` | 是 | - | 主标题，支持自动换行（最多2行）和字号缩放 |
| `subtitle` | 否 | "" | 副标题 |
| `bg_color` | 否 | "#FFFFFF" | 背景颜色（十六进制），template 模式使用 |
| `accent_color` | 否 | "#000000" | 文字强调色 |
| `bg_image` | 否 | "" | 自定义背景图片路径（仅 xhs-cover-03 使用，ai_bg 模式自动设置） |
| `ai_prompt` | 否 | "" | AI 生成背景图的自定义 prompt；不传则自动根据 title/subtitle 拼接 |
| `visual_style` | 否 | `"auto"` | `auto`、`comic` 或 `editorial`；显式值可覆盖主题判断 |
| `template_role` | 否 | `"cover"` | `cover`、`card` 或 `summary` |
| `illustration_variant` | 否 | 自动判断 | 漫画正文构图：`idea`、`explain`、`compare`、`dialogue`、`group` |

## AI 自动降级策略

当 `image_mode` 为 `"ai_bg"` 但以下情况发生时，自动降级到 template 模式：

| 降级原因 | ai_fallback_reason 值 |
|----------|----------------------|
| 缺少 LLM_API_KEY 环境变量 | `"missing_api_key"` |
| API 调用超时（120秒） | 错误信息字符串 |
| API 返回错误（4xx/5xx） | 错误信息字符串 |
| 图片下载失败或为空 | 错误信息字符串 |
| 重试 1 次后仍失败 | 错误信息字符串 |

降级后会在输出 JSON 的 `ai_fallback_reason` 字段记录原因，调用方总能拿到一张可用图片。

## 自动 Prompt 拼接规则

无论是否传入自定义 `ai_prompt`，系统都会追加硬性约束：角色只能是 18–24 岁中国大学生，场景只能是中国大学校园，禁止职场人士、儿童、游客、纯自然风景、网红棚拍、文字、水印和品牌标识。漫画模板会额外约束白底、粗黑线、亮蓝强调和对应的情景构图。

## 环境配置

AI 背景模式需要在项目根目录 `.env` 文件中配置：

```env
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://your-workspace.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-image-2.0-pro-2026-06-22
```

代码会自动将 `/compatible-mode/v1` 转换为原生 API 路径 `/api/v1/services/aigc/multimodal-generation/generation` 进行调用。当前项目已配置好阿里云百炼 workspace 端点，可直接使用。

## 输出格式

成功时输出到 `{job_dir}/image-compose.json`：

```json
{
  "status": "success",
  "timestamp": "2026-07-05T20:30:00+08:00",
  "data": {
    "image_path": "{job_dir}/output/xhs-cover-03.png",
    "width": 1080,
    "height": 1350,
    "template_used": "xhs-cover-03",
    "visual_style_used": "comic",
    "illustration_variant": "dialogue",
    "image_mode_used": "ai_bg",
    "ai_fallback_reason": null,
    "ai_prompt_used": "小红书封面背景图，掌控情绪..."
  }
}
```

降级时输出示例：
```json
{
  "status": "success",
  "timestamp": "2026-07-05T20:30:00+08:00",
  "data": {
    "image_path": "{job_dir}/output/xhs-cover-01.png",
    "width": 1080,
    "height": 1350,
    "template_used": "xhs-cover-01",
    "image_mode_used": "template",
    "ai_fallback_reason": "missing_env_config",
    "ai_prompt_used": null
  }
}
```

失败时输出到 `{job_dir}/error.json`：

```json
{
  "status": "error",
  "timestamp": "2026-07-05T20:30:00+08:00",
  "error": "模板不存在: invalid-template"
}
```

## 输出字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `image_path` | string | 生成图片的绝对路径 |
| `width` | int | 图片宽度（像素） |
| `height` | int | 图片高度（像素） |
| `template_used` | string | 实际使用的模板名 |
| `visual_style_used` | string | 实际使用的视觉系统：`comic`、`editorial` 或 `legacy_scene` |
| `illustration_variant` | string | 实际使用的漫画构图变体 |
| `image_mode_used` | string | 实际使用的模式：`"template"` 或 `"ai_bg"` |
| `ai_fallback_reason` | string/null | AI 降级原因，成功时为 null |
| `ai_prompt_used` | string/null | 实际发送给 AI 的 prompt，template 模式为 null |

## 文字适配策略

1. **优先自动换行**：标题超过单行宽度时自动换行，最多 2 行
2. **字号缩放兜底**：如果 2 行仍显示不下，自动缩小字号直到适配
3. **禁止截断**：文字不会被截断或加省略号

## 美观标准（强制）

- 文字对齐一致（居中/左对齐统一）
- 颜色搭配不刺眼
- 留白合理（文字区不超过画面 60%）
- 字体层级分明（标题 > 副标题）
- 参考真实小红书爆款封面风格，不能像 Word 艺术字
- AI 图片必须符合中国大学校园与大学生身份约束，无乱码文字、水印或品牌标识

## 运行方式

```bash
cd image-compose
python main.py --job-dir ./path/to/job_dir
```

## 依赖

```
playwright>=1.40.0
python-dotenv>=1.0.0
```

首次运行前需安装 Playwright 浏览器：

```bash
playwright install chromium
```

## 测试

### 批量测试（推荐）

一键运行全部测试用例，结果输出到 `test/results/` 目录（保持 `test/fixtures/` 纯净）：

```bash
cd image-compose
python test/run_tests.py
```

测试脚本会：
1. 将 `test/fixtures/test_XX/input.json` 复制到 `test/results/test_XX/`
2. 在 results 目录下执行合成，fixtures 目录不产生输出文件
3. 打印每组测试的耗时、模式、输出文件大小
4. 生成 `test/results/test_summary.json` 汇总报告

### 目录约定

```
test/
├── fixtures/           # 测试输入数据（只读，纯净）
│   ├── test_01/input.json
│   ├── test_02/input.json
│   └── ...
├── results/            # 测试输出（运行脚本自动生成）
│   ├── test_01/output/*.png
│   ├── test_summary.json
│   └── ...
├── expected/           # 期望参考样例
└── run_tests.py        # 批量测试脚本
```

### 测试要求

- 至少 5 组不同输入全部通过
- 输出 PNG > 0 字节
- 尺寸像素正确（1080x1350）
- 10字/20字/30字标题不截断
- 中文字体无方块/乱码
- 4 套模板都能独立调用
- 错模板名返回 error.json
- AI 模式下背景图成功生成或正确降级
- API Key 不出现在日志中（脱敏处理）
