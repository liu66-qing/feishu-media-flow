# image-compose 技术设计文档

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 1. 架构概览

```
┌────────────────────────────────────────────────────────┐
│                    image-compose                        │
├────────────────────────────────────────────────────────┤
│  input.json (template_name/variables/image_mode)        │
│    ↓                                                    │
│  infer_scene_from_text() — 场景推断                    │
│    ↓                                                    │
│  select_template() — 智能模板+配色匹配                 │
│    ↓                                                    │
│  image_mode == "ai_bg"?                                │
│    ├─ 是 → load_env_config() → generate_ai_background() │
│    │       ↓ 失败降级                                   │
│    └─ 否 → 直接模板渲染                                │
│    ↓                                                    │
│  render_html() → capture_screenshot() (Playwright)     │
│    ↓                                                    │
│  output/*.png + image-compose.json                      │
└────────────────────────────────────────────────────────┘
```

## 2. 核心数据结构

### 2.1 输入

| 字段 | 类型 | 说明 |
|------|------|------|
| template_name | string | 模板名（ai_bg 模式可省略） |
| image_mode | string | "template" 或 "ai_bg" |
| variables | object | 模板变量 `{title, subtitle, bg_color, bg_image, ai_prompt, ...}` |
| output_size | object | `{width: 1080, height: 1350}` |

### 2.2 输出

| 字段 | 说明 |
|------|------|
| image_path | 输出图片路径 |
| template_used | 使用的模板名 |
| visual_style_used | 视觉风格（editorial/comic） |
| image_mode_used | 实际使用的模式 |
| ai_fallback_reason | AI 降级原因（null 表示未降级） |
| ai_prompt_used | 实际使用的 AI prompt |

## 3. 关键函数

### `infer_scene_from_text(text) -> str`
场景推断：得分制统计关键词命中，返回最高分场景（学习/校园/美食/生活/穿搭/活动/通知/情绪）。

### `select_template(scene, template_name, text, visual_style, role) -> dict`
智能模板匹配：根据场景+视觉风格+角色自动选择最佳模板和配色。

### `build_ai_prompt(title, subtitle, ai_prompt, blank_area, visual_style, illustration_variant) -> str`
AI prompt 构建：根据场景+风格+构图类型生成专业 DashScope prompt，含身份约束和禁止项。

### `generate_ai_background(title, subtitle, ai_prompt, output_dir, env_config) -> tuple`
DashScope 文生图调用：异步提交 → polling → 下载图片，失败重试 1 次。

### `capture_screenshot(html_content, output_path, width, height)`
Playwright 截图：headless Chromium，viewport 1080x1350，等待 networkidle 后截图。

## 4. 视觉系统

### 4.1 两套卡片模板集
- **editorial**（编辑海报风）：campus-poster-cover/card/summary，暖白+朱红
- **comic**（知识漫画风）：campus-comic-cover/card/summary，白底+亮蓝

### 4.2 场景→模板映射
8 种场景各映射到最佳 xhs-cover 模板和配色方案。

## 5. 设计决策

1. **HTML+Playwright 而非 Canvas**：HTML 模板更易维护和调整样式
2. **AI 降级不中断**：AI 失败自动回退模板模式，保证流程可用
3. **场景智能匹配**：根据标题关键词自动选择模板+配色，减少手动配置
4. **base64 data URI**：解决 Playwright headless 模式下 file:// 协议无法加载本地图片的问题
5. **平台偏好画像注入**：AI prompt 可参考 vis 维度的色彩和构图偏好
