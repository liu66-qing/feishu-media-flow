# Platform Preference Profiler

基于真实平台样本，自动生成多平台内容偏好画像（V2 Schema），为内容生成模块提供数据驱动的风格适配指导。

## 功能概述

本模块分析小红书、抖音、微信公众号三个平台的高表现内容样本，提取平台偏好特征，生成结构化的画像文件。画像包含选题、语言、视觉、结构、禁用词五大维度，供下游内容生成模块（content-generate-*）和评审模块（critic）使用。

## 核心特性

- **V2 Schema 画像**：压缩键名、多维增强、弹性降级
- **置信度评估**：基于样本数量和指标一致性自动计算
- **7天有效期**：画像自动过期，支持强制刷新
- **弹性降级**：画像缺失时回退到静态规则（platform_constraints.json）

## 目录结构

```
platform-preference-profiler/
── main.py                    # 核心逻辑
├── SKILL.md                   # Skill 定义文件
├── requirements.txt           # Python 依赖
├── prompts/
│   └── analyze_samples.md     # LLM 分析样本的 prompt
└── test/
    └── fixtures/
        ── job1/
            ├── input.json     # 测试输入
            └── platform-preference-profiler.json  # 测试输出
```

## 快速开始

### 1. 准备样本数据

在 `.data/samples/{platform}/` 目录下放置样本文件：

```
.data/samples/
├── xhs/
│   ├── sample_001.json
│   ├── sample_002.json
│   └── ...
├── douyin/
│   └── ...
└── wechat/
    └── ...
```

样本格式见 [样本格式说明](#样本格式)。

### 2. 运行 Profiler

```bash
# 基础运行（仅分析过期或不存在的画像）
python platform-preference-profiler/main.py --job-dir <job_directory>

# 强制重新分析所有平台
python platform-preference-profiler/main.py --job-dir <job_directory> --force

# 增量模式（仅分析新样本）
python platform-preference-profiler/main.py --job-dir <job_directory> --incremental
```

### 3. 查看输出

输出文件：
- `.data/profiles/{platform}_profile.json` - 各平台画像
- `<job_dir>/platform-preference-profiler.json` - 索引文件

## 样本格式

每个样本文件包含以下字段：

```json
{
  "sample_id": "XHS-001",
  "platform": "xhs",
  "collected_at": "2026-07-21T10:00:00+08:00",
  "source_url": "https://www.xiaohongshu.com/discovery/item/...",
  "title": "样本标题",
  "body": "样本正文内容...",
  "hashtags": ["#标签1", "#标签2"],
  "cover_description": "封面图描述",
  "metrics": {
    "likes": 1000,
    "comments": 100,
    "collects": 500,
    "shares": 50
  },
  "content_type": "经验分享",
  "image_count": 5
}
```

**字段说明**：
- `sample_id`：样本唯一标识
- `platform`：平台标识（xhs/douyin/wechat）
- `collected_at`：采集时间（ISO 8601 格式）
- `source_url`：原始链接
- `title`：内容标题
- `body`：内容正文
- `hashtags`：标签列表
- `cover_description`：封面图描述（用于视觉分析）
- `metrics`：互动数据（点赞、评论、收藏、转发）
- `content_type`：内容类型
- `image_count`：图片数量（视频为 0）

## V2 画像 Schema

生成的画像文件包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `pf` | string | 平台标识 |
| `gen_at` | string | 生成时间 |
| `v` | string | Schema 版本 |
| `conf` | float | 置信度（0-1） |
| `s_cnt` | int | 样本数量 |
| `s_ids` | array | 样本 ID 列表 |
| `acc_type` | string | 账号类型 |
| `biz_scene` | string | 业务场景 |
| `topic` | object | 选题偏好 |
| `lang` | object | 语言风格 |
| `vis` | object | 视觉风格 |
| `struct` | array | 内容结构 |
| `forbid` | array | 禁用内容 |
| `forbid_level` | array | 风险等级 |
| `allow_substitute` | array | 允许替换词 |

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `LLM_API_KEY` | 是 | OpenAI 兼容 API 密钥 |
| `LLM_BASE_URL` | 是 | API 基础 URL |
| `LLM_MODEL` | 否 | 模型名称（默认使用文本模型） |
| `LLM_TEXT_MODEL` | 否 | 文本分析专用模型（覆盖 LLM_MODEL） |

## 与其他模块的集成

### content-generate-* 模块

自动加载画像并注入到 SYSTEM_PROMPT：

```python
# 在 content-generate-xhs/main.py 中
from main import load_platform_profile

profile = load_platform_profile()
if profile:
    # 画像已自动注入到 SYSTEM_PROMPT
    pass
```

### critic 模块

评审时参考画像进行平台适配度评分：

```python
from app.services.critic import load_platform_profile

profile = load_platform_profile("xhs")
if profile:
    # 使用画像中的偏好进行评审
    pass
```

### image-compose 模块

获取视觉风格提示用于 AI 生图：

```python
from image-compose.main import get_visual_style_hints

hints = get_visual_style_hints("xhs")
# hints = {
#     "color_palette": [...],
#     "composition": {...},
#     "mood": "...",
#     "decoration": "..."
# }
```

## 测试

```bash
# 运行测试
python platform-preference-profiler/main.py --job-dir platform-preference-profiler/test/fixtures/job1 --force
```

测试 fixture 位于 `test/fixtures/job1/`，包含：
- `input.json`：测试输入配置
- `platform-preference-profiler.json`：预期输出（参考）

## 常见问题

### Q: 画像生成失败怎么办？

检查以下几点：
1. 环境变量是否正确配置
2. 样本文件是否存在且格式正确
3. LLM API 是否可访问

### Q: 如何更新画像？

```bash
# 强制刷新所有平台
python platform-preference-profiler/main.py --job-dir <job_dir> --force

# 仅刷新特定平台（修改 input.json 中的 platforms 字段）
```

### Q: 画像过期了怎么办？

画像默认 7 天过期，过期后自动重新生成。如需立即刷新，使用 `--force` 参数。

## 许可证

本项目遵循 MIT 许可证。
