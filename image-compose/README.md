# image-compose

小红书专线技能包 — 封面/卡片图片合成模块。

根据 HTML 模板和变量自动生成小红书封面图与内容卡片（1080×1350 PNG），支持 AI 生成氛围感背景图。

**技术方案**：HTML + Playwright（Chromium 截图），AI 图像生成（Qwen-Image-2.0-Pro，可选）
**输出尺寸**：1080 × 1350 px（小红书推荐 4:5 竖版图）
**输出格式**：PNG

---

## 快速开始

### 1. 安装依赖

```bash
cd image-compose
pip install -r requirements.txt
```

安装 Playwright 浏览器（首次运行必需）：

```bash
playwright install chromium
```

### 2. 配置环境变量（仅 AI 模式需要）

在项目根目录 `.env` 文件中配置阿里云百炼 API：

```env
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://your-workspace.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-image-2.0-pro-2026-06-22
```

代码会自动将 `/compatible-mode/v1` 转换为原生 API 路径进行调用。

### 3. 准备输入数据

在任意目录创建 `input.json` 文件，模板模式示例：

```json
{
  "content_id": "CNT-20260705-001",
  "job_id": "JOB-20260705-001",
  "template_name": "xhs-cover-01",
  "variables": {
    "title": "招新别只会摆摊",
    "subtitle": "3个方法翻倍转化率",
    "bg_color": "#FF6B6B",
    "accent_color": "#FFFFFF"
  },
  "output_size": {
    "width": 1080,
    "height": 1350
  }
}
```

AI 背景模式示例：

```json
{
  "content_id": "CNT-20260707-001",
  "job_id": "JOB-20260707-001",
  "image_mode": "ai_bg",
  "variables": {
    "title": "校园秋日限定｜银杏大道拍照攻略",
    "subtitle": "最佳拍摄时间：下午3-5点",
    "ai_prompt": "秋天银杏大道，金色落叶铺满道路，阳光透过树叶洒下光斑，温暖治愈氛围，竖版构图，高清摄影风格"
  },
  "output_size": {
    "width": 1080,
    "height": 1350
  }
}
```

AI 模式会自动调用 Qwen-Image-2.0-Pro 生成氛围感背景图，再叠加 xhs-cover-03 模板的文字排版。如 AI 生成失败会自动降级到模板模式，不中断流程。

### 4. 运行合成

```bash
python main.py --job-dir /path/to/your/job/directory
```

**参数说明**：
- `--job-dir`：必填，指定包含 `input.json` 的目录路径

合成成功后，输出文件位于 `{job_dir}/` 下：
- 图片：`output/{template_name}.png`
- 元数据：`image-compose.json`
- 日志：`logs.txt`

### 5. 批量测试

```bash
python test/run_tests.py
```

测试结果输出到 `test/results/`，`test/fixtures/` 保持纯净（只读）。

---

## 两种生成模式

通过 `image_mode` 字段切换：

| 模式 | 字段值 | 说明 | 优点 | 缺点 |
|------|--------|------|------|------|
| 模板模式（默认） | `"template"` | HTML 模板 + Playwright 截图 | 快速（~2s）、零成本、稳定 | 视觉效果相对简洁 |
| AI 背景模式 | `"ai_bg"` | 调用 Qwen-Image-2.0-Pro 生成氛围感竖版背景图，再用 xhs-cover-03 叠字 | 视觉效果更好、氛围感强 | 需配置 API Key，约1-2分钟 |

**自动降级机制**：AI 模式下如果生成失败（网络问题、API 配额不足、配置缺失等），自动降级到 template 模式继续生成图片，不会中断流程。降级原因记录在输出元数据的 `ai_fallback_reason` 字段。

| 降级场景 | `ai_fallback_reason` 值 | 处理方式 |
|----------|--------------------------|----------|
| 未配置 API Key | `"missing_api_key"` | 直接降级 |
| API 请求超时（>120秒） | HTTP 错误信息 | 重试1次后降级 |
| API 返回错误（配额/权限/模型不可用） | HTTP 错误信息 | 重试1次后降级 |
| 图片下载失败或为空 | 错误信息 | 重试1次后降级 |
| API 返回格式异常 | 错误信息 | 重试1次后降级 |

---

## 模板清单

### xhs-cover-01 — 简约文字型封面

**设计风格**：纯色背景 + 居中大标题 + 副标题，极简风格
**适用场景**：干货分享、经验总结、要点提炼

```json
{
  "template_name": "xhs-cover-01",
  "variables": {
    "title": "招新别只会摆摊",
    "subtitle": "3个方法翻倍转化率",
    "bg_color": "#FF6B6B",
    "accent_color": "#FFFFFF"
  }
}
```

### xhs-cover-02 — 卡片型封面

**设计风格**：白色圆角卡片浮于彩色背景上，营造层次感
**适用场景**：清单类、对比类、步骤类内容

```json
{
  "template_name": "xhs-cover-02",
  "variables": {
    "title": "大学四年最后悔没做的5件事",
    "subtitle": "大一看到就好了",
    "bg_color": "#4ECDC4",
    "accent_color": "#FFFFFF"
  }
}
```

### xhs-cover-03 — 图文混排型封面

**设计风格**：支持自定义背景图片，底部渐变遮罩 + 白色文字
**适用场景**：风景类、活动回顾、场景展示（AI 模式自动使用此模板）

```json
{
  "template_name": "xhs-cover-03",
  "variables": {
    "title": "校园秋日限定｜银杏大道拍照攻略",
    "subtitle": "最佳拍摄时间：下午3-5点",
    "bg_image": "path/to/your/background.jpg"
  }
}
```

> `bg_image` 可选，支持本地路径、HTTP URL 或 base64 data URI；未提供时用 `bg_color` 纯色背景。

### xhs-card-01 — 通用内容卡片

**设计风格**：米色背景 + 引号装饰 + 标签，温暖质感
**适用场景**：金句分享、笔记摘要、要点总结

```json
{
  "template_name": "xhs-card-01",
  "variables": {
    "title": "考研还是就业？我用这张表想清楚了",
    "subtitle": "适合大三纠结的同学",
    "bg_color": "#6C5CE7",
    "accent_color": "#FFFFFF"
  }
}
```

---

## 输入字段详解

### 必填字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `variables.title` | string | 主标题，支持自动换行和字号缩放 |

> 注意：`template_name` 在 template 模式下必填，但在 `ai_bg` 模式下会自动使用 `xhs-cover-03`，可省略。

### 可选字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `content_id` | string | `""` | 内容 ID，用于输出元数据 |
| `job_id` | string | `""` | 任务 ID，用于输出元数据 |
| `template_name` | string | `""` | 模板名（ai_bg 模式自动覆盖为 xhs-cover-03） |
| `image_mode` | string | `"template"` | 生成模式：`"template"` 或 `"ai_bg"` |
| `variables.subtitle` | string | `""` | 副标题 |
| `variables.bg_color` | string | `"#FFFFFF"` | 背景颜色（十六进制） |
| `variables.accent_color` | string | `"#000000"` | 文字强调色（十六进制） |
| `variables.bg_image` | string | `""` | 自定义背景图片（仅 xhs-cover-03） |
| `variables.ai_prompt` | string | `""` | AI 背景自定义 prompt，不传则自动拼接 |
| `output_size.width` | int | `1080` | 输出宽度（像素） |
| `output_size.height` | int | `1350` | 输出高度（像素） |

### 自动 Prompt 拼接规则

不传 `ai_prompt` 时，自动生成：

```
小红书封面背景图，{title}，氛围感摄影风格，无文字，无水印，高质量，竖构图[，主题：{subtitle}]
```

只有 `subtitle` 非空时才追加"，主题：{subtitle}"。建议传入自定义 `ai_prompt` 获得更精确的背景效果。

---

## 输出格式

### 成功输出（`{job_dir}/image-compose.json`）

```json
{
  "status": "success",
  "timestamp": "2026-07-07T20:30:00+08:00",
  "data": {
    "image_path": "/path/to/output/xhs-cover-03.png",
    "width": 1080,
    "height": 1350,
    "template_used": "xhs-cover-03",
    "image_mode_used": "ai_bg",
    "ai_fallback_reason": null,
    "ai_prompt_used": "小红书封面背景图，掌控情绪的人才能掌控人生..."
  }
}
```

### 失败输出（`{job_dir}/error.json`）

```json
{
  "status": "error",
  "timestamp": "2026-07-07T20:30:00+08:00",
  "error": "模板不存在: invalid-template"
}
```

---

## 文字适配策略

标题文字自动适配，不会截断或加省略号：

1. **优先自动换行**：超过单行宽度时自动换行，最多显示 2 行
2. **字号缩放兜底**：2 行仍显示不下时，逐步缩小字号直到适配

| 模板 | 初始字号 | 最小字号 |
|------|----------|----------|
| xhs-cover-01 | 72px | 32px |
| xhs-cover-02 | 64px | 36px |
| xhs-cover-03 | 68px | 36px |
| xhs-card-01 | 56px | 30px |

| 标题长度 | 预期效果 |
|----------|----------|
| 8字以内 | 单行显示，初始字号 |
| 10-15字 | 自动换行2行，初始字号 |
| 15-25字 | 换行2行，字号略缩小 |
| 25-40字 | 换行2行，字号明显缩小 |
| 40字以上 | 换行2行，字号缩到最小 |

---

## 测试

### 测试用例

`test/fixtures/` 中共 7 组测试输入（只读）：

| 测试组 | 模板 | 场景 |
|--------|------|------|
| test_01 | xhs-cover-01 | 8字短标题 |
| test_02 | xhs-cover-02 | 15字中标题 |
| test_03 | xhs-cover-03 | 18字中标题（纯色背景） |
| test_04 | xhs-card-01 | 20字长标题 |
| test_05 | xhs-cover-01 | 50+字超长标题（压力测试） |
| test_06 | ai_bg → xhs-cover-03 | AI 模式，自动生成 prompt |
| test_07 | ai_bg → xhs-cover-03 | AI 模式，自定义 ai_prompt |

### 运行测试

```bash
# 批量测试（推荐）
python test/run_tests.py

# 单组手动测试（将 input.json 放到任意目录后运行）
python main.py --job-dir /path/to/job_dir
```

### 测试目录结构

```
test/
├── fixtures/              # 测试输入（只读，纯净）
│   └── test_XX/input.json
├── results/               # 测试输出（自动生成）
│   ├── test_XX/           # 单组测试的任务目录
│   │   ├── input.json
│   │   ├── logs.txt
│   │   ├── image-compose.json
│   │   └── output/*.png
│   ├── test_result_test_XX.json
│   └── test_summary.json  # 汇总报告
├── expected/              # 【可选】人工参考样例截图（代码不读取，仅供肉眼比对）
├── run_tests.py           # 批量测试脚本
└── quality_review.md      # 质量自评
```

### 测试检查项

- [ ] 输出 PNG 文件存在且大小 > 0 字节
- [ ] 图片尺寸为 1080×1350 像素
- [ ] 中文字体正常显示（无方块/乱码）
- [ ] 标题文字完整显示（无截断）
- [ ] 颜色搭配舒适，不刺眼
- [ ] 留白合理，文字区不超过画面 60%

---

## 常见问题

### Q1: 报错 `ModuleNotFoundError: No module named 'playwright'`

```bash
pip install playwright
playwright install chromium
```

### Q2: 中文字体显示为方块

- **Windows**：系统自带微软雅黑，一般不会出现
- **Linux**：安装中文字体 `sudo apt-get install fonts-wqy-zenhei`
- **macOS**：系统自带苹方字体，一般不会出现

### Q3: 标题太长被截断

标题超过模板最大显示区域且字号已缩到最小时会截断。建议缩短标题到 20 字以内，或修改模板 HTML 中的最小字号限制。

### Q4: 如何使用自定义背景图片？

仅 `xhs-cover-03` 支持。在 `variables` 中添加 `bg_image` 字段，值为本地图片路径或 URL：

```json
"bg_image": "./assets/background.jpg"
```

本地路径会自动转为 base64 data URI 内嵌到 HTML 中（避免 Playwright headless 模式下 file:// 协议限制）。

### Q5: 如何修改模板样式？

编辑 `templates/{template_name}/template.html` 中的 CSS 样式即可，修改后下次运行自动生效。

### Q6: 如何使用 AI 生成背景图？

1. 在 input.json 中设置 `"image_mode": "ai_bg"`
2. 可选在 `variables.ai_prompt` 中传入自定义 prompt，不传则自动拼接
3. 确保项目根目录 `.env` 已配置 `LLM_API_KEY`
4. AI 失败会自动降级到模板模式，无需担心流程中断

---

## 技术细节

### Playwright 截图流程

1. 启动 headless Chromium 浏览器
2. 创建页面，viewport 设为 1080×1350
3. 通过 `page.set_content()` 加载渲染后的 HTML（背景图以 base64 data URI 内嵌）
4. 等待 `networkidle` 状态
5. 截图保存为 PNG
6. 关闭浏览器

### AI 背景图生成流程

1. 从项目根目录 `.env` 加载 API 配置
2. 构建 prompt（自定义或自动拼接）
3. POST 请求到 DashScope 多模态生成接口 `/api/v1/services/aigc/multimodal-generation/generation`
4. 从响应的 `output.choices[0].message.content` 数组提取 image URL（OSS 临时链接）
5. 下载图片保存到 `{job_dir}/output/ai_bg.png`
6. 转为 base64 data URI 传入 xhs-cover-03 模板
7. 失败自动重试 1 次，仍失败则降级

### 代码调用方式

除命令行外，也可在 Python 代码中直接调用：

```python
from pathlib import Path
from main import run_job

result = run_job(Path("/path/to/job_dir"))
print(result["data"]["image_path"])
```

`run_job()` 返回结果字典，失败抛异常，不会调用 `sys.exit()`。

---

## 目录结构

```
image-compose/
├── README.md                # 本文件（使用说明）
├── SKILL.md                 # 技能说明文档（面向工作流集成）
├── main.py                  # 主入口（含 run_job() 函数）
├── requirements.txt         # Python 依赖
├── templates/               # HTML 模板
│   ├── xhs-cover-01/template.html
│   ├── xhs-cover-02/template.html
│   ├── xhs-cover-03/template.html
│   └── xhs-card-01/template.html
└── test/
    ├── fixtures/            # 测试输入（只读）
    ├── results/             # 测试输出（自动生成）
    ├── expected/            # 参考样例
    ├── run_tests.py         # 批量测试脚本
    └── quality_review.md
```

---

## 美观标准

- [ ] 文字对齐统一（全部居中）
- [ ] 颜色搭配不刺眼（避免高饱和撞色）
- [ ] 留白充足（文字区 < 60% 画面）
- [ ] 字体层级分明（标题 900 vs 副标题 400）
- [ ] 装饰元素克制（不喧宾夺主）
- [ ] 不像 PPT / Word 艺术字
- [ ] 中文字体正常显示（无方块/乱码）
- [ ] AI 背景图为竖构图氛围感摄影风格，无乱码文字

---

## 更新日志

### v1.1 (2026-07-07)

- 新增 AI 背景图生成功能（`image_mode=ai_bg`）
- 调用 Qwen-Image-2.0-Pro 模型生成氛围感竖版背景
- AI 失败自动降级到模板模式，不中断流程
- 支持自定义 `ai_prompt`，未传则自动拼接
- 背景图使用 base64 data URI 内嵌，解决 Playwright file:// 加载问题
- 输出元数据增加 `image_mode_used` / `ai_fallback_reason` / `ai_prompt_used` 字段
- 新增批量测试脚本 `test/run_tests.py`，结果输出到 `test/results/`，fixtures 保持纯净
- 重构核心逻辑为 `run_job()` 函数，支持代码直接调用

### v1.0 (2026-07-06)

- 实现 4 套小红书模板（xhs-cover-01/02/03, xhs-card-01）
- 支持自动换行 + 字号缩放
- 支持自定义背景图片（xhs-cover-03）
- 提供 5 组测试数据

---

## 联系方式

- 负责人：尹羿璇
- 项目：社团自媒体工作流系统
