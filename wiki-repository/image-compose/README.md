# image-compose

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

小红书封面/卡片图片合成技能包。

根据 HTML 模板和变量自动生成小红书封面图与内容卡片（1080×1350 PNG），支持 AI 生成氛围感背景图 + 智能场景匹配。

**技术方案**：HTML + Playwright（Chromium 截图），AI 图像生成（DashScope wanx2.1-t2i-turbo，可选）
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
IMAGE_MODEL=wanx2.1-t2i-turbo
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

AI 模式会自动调用 DashScope wanx2.1-t2i-turbo 生成氛围感背景图，智能匹配最佳模板叠加文字排版。如 AI 生成失败会自动降级到模板模式，不中断流程。

**智能场景匹配**：AI 模式下无需指定模板，系统根据标题/关键词自动推断场景（学习/校园/美食/生活/穿搭/活动/通知/情绪），匹配最佳模板和配色方案。

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
| AI 背景模式 | `"ai_bg"` | 调用 wanx2.1-t2i-turbo 生成氛围感背景图，智能匹配模板叠字 | 视觉效果更好、氛围感强、自动场景匹配 | 需配置 API Key，约1-2分钟 |

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

**设计风格**：纯色/背景图 + 居中大标题 + 副标题，极简风格，文字带阴影增强可读性
**适用场景**：干货分享、经验总结、要点提炼
**支持 bg_image**：是

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

**设计风格**：半透明毛玻璃卡片浮于背景上，backdrop-filter 模糊效果，营造层次感
**适用场景**：清单类、对比类、步骤类内容、通知
**支持 bg_image**：是

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

### xhs-cover-03 — 底部文字型封面

**设计风格**：支持背景图，底部半透明渐变遮罩 + 白色文字描边，AI 背景图充分展示
**适用场景**：美食、情绪、氛围感内容（AI 美食/情绪场景自动使用此模板）
**支持 bg_image**：是

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

### xhs-cover-04 — 大字报型封面

**设计风格**：半透明标题块 + 毛玻璃效果，活泼醒目，视觉冲击力强
**适用场景**：社团活动、招新、比赛、倒计时
**支持 bg_image**：是

### xhs-cover-05 — 顶部色块型封面

**设计风格**：顶部半透明色块 + 毛玻璃效果 + 居中大标题
**适用场景**：穿搭、时尚、好物推荐
**支持 bg_image**：是

### xhs-cover-06 — 顶部文字型封面

**设计风格**：顶部半透明遮罩 + 增强文字阴影，背景图完整展示
**适用场景**：校园、生活、日常 vlog（AI 校园/生活场景自动使用此模板）
**支持 bg_image**：是

### xhs-cover-07 — 左对齐杂志风封面

**设计风格**：左侧半透明遮罩 + 文字左对齐，右侧展示背景图
**适用场景**：穿搭、时尚杂志风
**支持 bg_image**：是

### xhs-cover-08 — 中心毛玻璃卡片封面

**设计风格**：全幅柔焦背景 + 中心毛玻璃卡片，backdrop-filter 模糊透出背景
**适用场景**：学习、自习、笔记（AI 学习场景自动使用此模板）
**支持 bg_image**：是

### xhs-cover-09 — 高级大字报封面

**设计风格**：漫画风格大字报，超大粗体文字 + 黑色描边 + 3D 阴影，速度线/爆炸星burst/闪电装饰，HOT 标签，强视觉冲击力
**适用场景**：社团活动、招新、比赛、服务推广、倒计时（AI 活动场景自动使用此模板）
**支持 bg_image**：是

```json
{
  "template_name": "xhs-cover-09",
  "variables": {
    "title": "做视频！",
    "subtitle": "什么都可以！",
    "bg_color": "#FF6B6B",
    "accent_color": "#FFD700"
  }
}
```

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

> 注意：`template_name` 在 template 模式下必填，但在 `ai_bg` 模式下会自动根据场景智能匹配，可省略。

### 可选字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `content_id` | string | `""` | 内容 ID，用于输出元数据 |
| `job_id` | string | `""` | 任务 ID，用于输出元数据 |
| `template_name` | string | `""` | 模板名（ai_bg 模式下自动智能匹配，可省略） |
| `image_mode` | string | `"template"` | 生成模式：`"template"` 或 `"ai_bg"` |
| `variables.subtitle` | string | `""` | 副标题 |
| `variables.bg_color` | string | `"#FFFFFF"` | 背景颜色（十六进制） |
| `variables.accent_color` | string | `"#000000"` | 文字强调色（十六进制） |
| `variables.bg_image` | string | `""` | 自定义背景图片（所有模板均支持） |
| `variables.ai_prompt` | string | `""` | AI 背景自定义 prompt，不传则自动拼接 |
| `output_size.width` | int | `1080` | 输出宽度（像素） |
| `output_size.height` | int | `1350` | 输出高度（像素） |

### 智能场景匹配（AI 模式）

AI 模式下，系统根据标题和关键词自动推断场景，匹配最佳模板和配色：

| 场景 | 关键词示例 | 自动匹配模板 | 配色方案 |
|------|-----------|-------------|----------|
| 学习 | 学习、考试、考研、笔记、自习 | xhs-cover-08（中心毛玻璃卡片） | 米色 + 棕色 |
| 校园 | 校园、宿舍、开学、毕业、银杏 | xhs-cover-06（顶部文字） | 浅绿 + 深绿 |
| 美食 | 吃、食堂、美食、咖啡、探店 | xhs-cover-03（底部文字） | 暖橙 + 棕 |
| 生活 | 生活、日常、vlog、改造、收纳 | xhs-cover-06（顶部文字） | 浅蓝 + 蓝灰 |
| 穿搭 | 穿搭、衣服、搭配、购物 | xhs-cover-07（左对齐杂志风） | 粉紫 + 玫瑰 |
| 活动 | 社团、活动、招新、比赛、倒计时 | xhs-cover-04（大字报） | 粉红 + 红 |
| 通知 | 通知、报名、招募、面试、讲座 | xhs-cover-02（卡片式） | 靛蓝 + 紫 |
| 情绪 | 情绪、情感、心理、治愈 | xhs-cover-03（底部文字） | 浅紫 + 紫 |

### AI Prompt 自动构建规则

不传 `ai_prompt` 时，系统根据场景自动构建专业 prompt：
- 根据标题推断场景风格（学习/美食/校园等）
- 生成完整场景构图，画面饱满丰富（不留白）
- 文字可读性由 HTML 模板的半透明遮罩/毛玻璃效果保证
- 要求博主实拍感、8K 高清、低对比度不抢文字视线
- 不含"小红书"字样，不要求生成文字

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
| xhs-cover-04 | 72px | 36px |
| xhs-cover-05 | 68px | 36px |
| xhs-cover-06 | 68px | 36px |
| xhs-cover-07 | 68px | 36px |
| xhs-cover-08 | 64px | 32px |
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

所有模板均支持。在 `variables` 中添加 `bg_image` 字段，值为本地图片路径或 URL：

```json
"bg_image": "./assets/background.jpg"
```

本地路径会自动转为 base64 data URI 内嵌到 HTML 中（避免 Playwright headless 模式下 file:// 协议限制）。

### Q5: 如何修改模板样式？

编辑 `templates/{template_name}/template.html` 中的 CSS 样式即可，修改后下次运行自动生效。

### Q6: 如何使用 AI 生成背景图？

1. 在 input.json 中设置 `"image_mode": "ai_bg"`
2. 可选在 `variables.ai_prompt` 中传入自定义 prompt，不传则根据标题自动构建
3. 确保项目根目录 `.env` 已配置 `LLM_API_KEY`
4. AI 模式会自动推断场景、匹配最佳模板和配色
5. AI 失败会自动降级到模板模式，无需担心流程中断

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
2. 根据标题/关键词推断场景（学习/美食/校园等）
3. 智能匹配最佳模板和配色方案
4. 构建场景适配的专业 prompt（完整场景构图，不留白）
5. POST 请求到 DashScope `/api/v1/services/aigc/text2image/image-synthesis`
6. 异步任务 polling，从响应中提取 image URL（OSS 临时链接）
7. 下载图片保存到 `{job_dir}/output/ai_bg.png`
8. 转为 base64 data URI 传入匹配到的模板
9. 失败自动重试 1 次，仍失败则降级到模板模式

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
├── templates/               # HTML 模板（8套封面 + 1套卡片）
│   ├── xhs-cover-01/template.html   # 简约文字型
│   ├── xhs-cover-02/template.html   # 卡片型（毛玻璃）
│   ├── xhs-cover-03/template.html   # 底部文字型
│   ├── xhs-cover-04/template.html   # 大字报型
│   ├── xhs-cover-05/template.html   # 顶部色块型
│   ├── xhs-cover-06/template.html   # 顶部文字型
│   ├── xhs-cover-07/template.html   # 左对齐杂志风
│   ├── xhs-cover-08/template.html   # 中心毛玻璃卡片
│   └── xhs-card-01/template.html    # 通用内容卡片
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
- [ ] AI 背景图为完整场景构图，无纯色块留白
- [ ] 模板遮罩半透明/毛玻璃，背景图充分展示

---

## 更新日志

### v1.3 (2026-07-14)

- 模板全面优化：所有模板改为半透明遮罩/毛玻璃效果，AI 背景图充分展示
- 新增 4 套模板：xhs-cover-04（大字报）、xhs-cover-05（顶部色块）、xhs-cover-06（顶部文字）、xhs-cover-07（杂志风）、xhs-cover-08（中心毛玻璃卡片）
- 所有模板新增 bg_image 背景图支持
- AI prompt 策略优化：从"要求留白"改为"完整场景构图"，文字可读性由模板遮罩保证
- 智能场景匹配：根据标题自动推断场景（8种），匹配最佳模板和配色
- AI 模型更新为 wanx2.1-t2i-turbo
- 文字阴影/描边增强，保证在半透明背景上的可读性

### v1.2 (2026-07-10)

- 新增场景风格关键词库（学习/校园/美食/生活/穿搭/活动/通知/情绪）
- AI prompt 根据场景自动适配风格描述
- 新增 cover_prompt_guide.md prompt 构建指南

### v1.1 (2026-07-07)

- 新增 AI 背景图生成功能（`image_mode=ai_bg`）
- 调用 DashScope wanx2.1-t2i-turbo 模型生成氛围感竖版背景
- AI 失败自动降级到模板模式，不中断流程
- 支持自定义 `ai_prompt`，未传则根据场景自动构建
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
