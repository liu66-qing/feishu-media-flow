# image-compose 开发者指南

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 1. 模块间数据交互

### 上游输入
- **content-generate-xhs**：读取 cover_text、step1_analyze 生成封面
- **content-generate-wechat**：读取 image_plan 生成配图
- **video-generate**：调用 run_job() 渲染卡片

### 下游输出
```
image-compose → output/*.png → xhs-publish-package / video-generate
```

## 2. 内部工作流
```
input.json
  → infer_scene_from_text() → select_template()
  → [ai_bg?] → generate_ai_background() (DashScope)
  → load_template() → render_html()
  → capture_screenshot() (Playwright)
  → output/*.png + image-compose.json
```

## 3. 代码调用方式
```python
from main import run_job
from pathlib import Path
result = run_job(Path("/path/to/job_dir"))  # 返回 dict，失败抛异常
```

## 4. 测试指南
```bash
python test/run_tests.py           # 批量测试（7组）
python main.py --job-dir test/fixtures/test_06  # 单组 AI 模式
```
测试产物：`output/*.png`、`image-compose.json`、`logs.txt`

## 5. 调试技巧
- AI 模式慢（1-2分钟），模板模式快（~2秒）
- `ai_fallback_reason` 非 null 表示 AI 降级
- 中文字体方块问题：Linux 需安装 `fonts-wqy-zenhei`
- 标题截断：超过 40 字会缩到最小字号仍可能截断
- `logs.txt` 同时输出到 stdout 和文件
