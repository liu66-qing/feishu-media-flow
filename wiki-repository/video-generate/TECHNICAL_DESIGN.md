# video-generate 技术设计文档

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 1. 架构概览

```
┌──────────────────────────────────────────────────────────────┐
│                       video-generate                          │
├──────────────────────────────────────────────────────────────┤
│  input.json (content_id + job_id + topic + cards + ...)       │
│    ↓                                                          │
│  normalize_cards() — 标准化卡片数据（兜底生成）               │
│    ↓                                                          │
│  load_image_compose_module() — 动态加载 image-compose         │
│    ↓                                                          │
│  select_card_template_set() — 主题匹配模板集                  │
│    ↓                                                          │
│  render_card_set() — 逐卡渲染（封面 + N张正文 + 总结）        │
│    ↓                                                          │
│  video-generate.json (card_paths + manifest)                  │
└──────────────────────────────────────────────────────────────┘
         ↓ 调用
┌──────────────────────────────────────────────────────────────┐
│                     image-compose 模块                        │
│  run_job() → HTML模板 + Playwright截图 / DashScope AI背景     │
└──────────────────────────────────────────────────────────────┘
```

## 2. 核心数据结构

### 2.1 输入

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| content_id | string | ✅ | 内容 ID |
| job_id | string | ✅ | 任务 ID |
| topic | string | ✅ | 选题 |
| selected_title | string | — | 选定标题 |
| cover_lines | list[str] | — | 封面文案行 |
| cards | list[dict] | — | 正文卡片数据（≤7张） |
| body | string | — | 发布文案 |
| hashtags | list[str] | — | 话题标签 |
| image_mode | string | — | `template` / `ai_bg`，默认 template |
| visual_style | string | — | `auto` / `comic` / `editorial` |
| ai_all_cards | bool | — | 是否所有卡片都用 AI 背景，默认 false |
| output_size | dict | — | `{width, height}`，默认 1080×1350 |

### 2.2 卡片数据结构（cards 数组项）

| 字段 | 类型 | 说明 |
|------|------|------|
| kind | string | `detail` / `summary`（最后一张强制 summary） |
| section_label | string | 分区标签，≤20 字 |
| title | string | 卡片标题，≤32 字 |
| body | string | 卡片正文，≤180 字 |
| highlight | string | 高亮金句，≤80 字 |

### 2.3 输出（video-generate.json）

| 字段 | 说明 |
|------|------|
| status | `"success"` |
| publish_mode | 固定 `"manual_upload"` |
| cover_path | 首张封面绝对路径 |
| card_paths | 全部图片有序路径列表 |
| total_cards | 图片总数 |
| visual_style | 整组视觉系统 |
| caption | 发布文案 |
| hashtags | 话题标签 |
| cards | 清单 `[{index, role, image_path, template, visual_style, illustration_variant, label}]` |

## 3. 关键函数

### `normalize_cards(payload) -> list[dict]`
从 `payload.cards` 或 `payload.generation.cards` 提取卡片数据，截断至 7 张，字段标准化。若为空则生成 4 张默认校园内容卡片。最后一张强制设为 `summary`。

### `load_image_compose_module() -> module`
通过 `importlib.util.spec_from_file_location` 动态加载 `image-compose/main.py`，避免包依赖。

### `render_card_set(payload, job_dir) -> (images, manifest)`
核心渲染流程：
1. 标准化卡片 → 选择模板集 → 确定颜色/品牌变量
2. 构建封面 render_spec（page 01）
3. 逐张构建正文/总结卡 render_spec（page 02~N）
4. 依次调用 `image_compose.run_job()` 渲染每张卡片
5. 复制输出图片到 `output/card_XX.png`

### `select_card_template_set(selection_text, preferred_style)`
委托给 image-compose 的模板选择逻辑，根据主题文本和视觉风格偏好匹配模板集（cover + card + summary 三模板）。

## 4. 渲染流程细节

```
封面 (card_01.png)
  → template: cover 模板
  → image_mode: 用户指定（默认 template）
  → AI prompt: subtitle 或 title

正文卡 (card_02.png ~ card_N-1.png)
  → template: card 模板
  → image_mode: ai_all_cards=true 时用户指定，否则 template
  → AI prompt: card.title + card.body

总结卡 (card_N.png)
  → template: summary 模板
  → image_mode: 同正文卡逻辑
```

每张卡片的渲染目录为 `render/XX/input.json`，渲染后复制到 `output/card_XX.png`。

## 5. 设计决策

1. **动态加载 image-compose**：通过 importlib 而非 subprocess，可直接调用函数获取渲染结果，避免 JSON 序列化开销
2. **历史名称保留**：目录名 `video-generate` 不改为 `douyin-card-generate`，避免已部署工作流失效
3. **默认仅封面 AI**：正文卡用纯模板渲染，大幅减少 DashScope API 调用次数和耗时
4. **卡片上限 7 张**：抖音图文限制，超出自动截断
5. **兜底卡片**：上游未传 cards 时不报错，自动生成可用的默认内容

---

> Created by: 尹羿璇 | 2026-07-21
