# video-generate 开发者指南

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 1. 模块间数据交互

### 上游输入
```
content-generate-douyin → 生成内容（cards + cover_lines + body + hashtags）→ video-generate
```

### 下游输出
```
video-generate → video-generate.json + output/card_XX.png → app（发送到飞书 → 手动上传抖音）
```

### 模块依赖
```
video-generate ──importlib──→ image-compose（动态加载，共享渲染引擎）
```

## 2. 内部工作流
```
input.json
  → read_json() — 读取输入
  → normalize_cards() — 标准化卡片（兜底4张默认卡）
  → load_image_compose_module() — 动态加载渲染模块
  → select_card_template_set() — 主题匹配模板集
  → render_card_set()
      → 构建封面 spec → image_compose.run_job() → card_01.png
      → 构建正文 spec × N → image_compose.run_job() → card_02~N-1.png
      → 构建总结 spec → image_compose.run_job() → card_N.png
  → video-generate.json（含 card_paths + manifest）
```

## 3. 测试指南
```bash
python main.py --job-dir video-generate/test/fixtures/job1
```
测试产物：
- `output/card_XX.png` — 渲染后的卡片图片
- `render/XX/input.json` — 每张卡的渲染输入
- `video-generate.json` — 成功输出
- `error.json` — 失败输出
- `logs.txt` — 运行日志

## 4. 调试技巧
- 查看 `render/XX/input.json` 了解每张卡片传给 image-compose 的完整变量
- `manifest` 中 `visual_style` 和 `illustration_variant` 可确认模板选择是否符合预期
- 封面 AI 背景失败时检查 `error.json` 中的 DashScope API 错误信息
- 修改兜底卡片内容：编辑 `normalize_cards()` 中的默认 cards 列表
- `ai_all_cards=true` 会为每张正文卡调用 AI，调试时建议关闭以加速
- image-compose 模块路径硬编码为 `PROJECT_ROOT / "image-compose" / "main.py"`，确保目录结构不变

## 5. 扩展开发

### 新增卡片类型
在 `normalize_cards()` 中新增 `kind` 值，并在 `render_card_set()` 中为其选择合适的模板。

### 调整卡片数量限制
修改 `normalize_cards()` 中 `[:7]` 的截断值，注意抖音平台图文上限。

### 自定义默认卡片
编辑 `normalize_cards()` 中 cards 为空时的兜底数据，适配不同内容主题。

---

> Created by: 尹羿璇 | 2026-07-21
