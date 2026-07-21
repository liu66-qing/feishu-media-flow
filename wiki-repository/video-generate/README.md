# video-generate — 抖音图文卡片包生成 Skill

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 功能简介

将上游生成的内容数据渲染为有序的抖音图文卡片包（1 张封面 + 4–7 张正文卡片 + 1 张总结卡），输出 PNG 图片供手动上传发布。

> 目录保留历史名称 `video-generate`，实际不生成视频/音频，仅生成静态图片卡片。

## 核心特性

- **有序卡片包**：封面 + 正文卡片 + 总结卡，自动排序编号
- **视觉系统联动**：调用 image-compose 模块渲染，共享 10 套模板 + AI 背景
- **主题智能匹配**：根据选题内容自动选择校园手绘 / 编辑海报模板集
- **弹性兜底**：cards 为空时自动生成 4 张默认校园内容卡片
- **成本可控**：默认仅封面使用 AI 背景，正文卡用纯模板（`ai_all_cards` 可全开）

## 目录结构

```
video-generate/
├── main.py              ← 核心执行入口（290行）
├── SKILL.md             ← Skill 定义
├── requirements.txt     ← Python 依赖
└── test/
    └── fixtures/
        └── job1/        ← 测试输入
```

## 快速入门

```bash
pip install -r requirements.txt
python main.py --job-dir <含 input.json 的目录>
```

## 依赖说明

| 依赖 | 说明 |
|------|------|
| image-compose 模块 | 卡片渲染引擎（通过 importlib 动态加载） |

---

> Created by: 尹羿璇 | 2026-07-21
