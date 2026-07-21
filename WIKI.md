# Feishu Media Flow — 项目维基

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 项目概述

多平台自媒体内容自动化工作流系统，覆盖从热点采集、内容生成、审核润色、风险检测到图片渲染、发布打包的全链路。支持小红书、抖音、微信公众号三个平台，通过 V2 Schema 平台偏好画像实现差异化内容输出。

---

## 模块清单

| 模块 | 功能 | 文档 |
|------|------|------|
| **app** | 主控服务（飞书交互 + 调度 + Agent 循环） | [README](app/README.md) · [技术设计](app/TECHNICAL_DESIGN.md) · [开发者指南](app/DEVELOPER_GUIDE.md) |
| **platform-preference-profiler** | 平台偏好画像生成（V2 Schema 五维度） | [README](platform-preference-profiler/README.md) · [技术设计](platform-preference-profiler/TECHNICAL_DESIGN.md) · [开发者指南](platform-preference-profiler/DEVELOPER_GUIDE.md) |
| **hot-topic-collector** | 多平台热点采集 + LLM 筛选 | [README](hot-topic-collector/README.md) · [技术设计](hot-topic-collector/TECHNICAL_DESIGN.md) · [开发者指南](hot-topic-collector/DEVELOPER_GUIDE.md) |
| **hot-rewrite** | 热点内容改写 + Simhash 相似度校验 | [README](hot-rewrite/README.md) · [技术设计](hot-rewrite/TECHNICAL_DESIGN.md) · [开发者指南](hot-rewrite/DEVELOPER_GUIDE.md) |
| **content-generate-xhs** | 小红书内容生成（4-Step LLM Pipeline） | [README](content-generate-xhs/README.md) · [技术设计](content-generate-xhs/TECHNICAL_DESIGN.md) · [开发者指南](content-generate-xhs/DEVELOPER_GUIDE.md) |
| **content-generate-douyin** | 抖音内容生成（4-Step LLM Pipeline） | [README](content-generate-douyin/README.md) · [技术设计](content-generate-douyin/TECHNICAL_DESIGN.md) · [开发者指南](content-generate-douyin/DEVELOPER_GUIDE.md) |
| **content-generate-wechat** | 微信公众号内容生成（LLM + WebFetch） | [README](content-generate-wechat/README.md) · [技术设计](content-generate-wechat/TECHNICAL_DESIGN.md) · [开发者指南](content-generate-wechat/DEVELOPER_GUIDE.md) |
| **content-review-polish** | 内容审核润色（四维评分 + 双模式） | [README](content-review-polish/README.md) · [技术设计](content-review-polish/TECHNICAL_DESIGN.md) · [开发者指南](content-review-polish/DEVELOPER_GUIDE.md) |
| **risk-check** | 风险检测（本地规则 + LLM 语义审查） | [README](risk-check/README.md) · [技术设计](risk-check/TECHNICAL_DESIGN.md) · [开发者指南](risk-check/DEVELOPER_GUIDE.md) |
| **image-compose** | 图片渲染（HTML模板 + Playwright + AI背景） | [README](image-compose/README.md) · [技术设计](image-compose/TECHNICAL_DESIGN.md) · [开发者指南](image-compose/DEVELOPER_GUIDE.md) |
| **video-generate** | 抖音图文卡片包生成（调用 image-compose） | [README](video-generate/README.md) · [技术设计](video-generate/TECHNICAL_DESIGN.md) · [开发者指南](video-generate/DEVELOPER_GUIDE.md) |
| **xhs-publish-package** | 小红书发布打包（文本 + 图片 + 清单） | [README](xhs-publish-package/README.md) · [技术设计](xhs-publish-package/TECHNICAL_DESIGN.md) · [开发者指南](xhs-publish-package/DEVELOPER_GUIDE.md) |

---

## 工作流全景

```
┌─────────────────────┐
│ hot-topic-collector  │ ← 多平台热点采集
└─────────┬───────────┘
          ↓
┌─────────────────────┐
│    hot-rewrite       │ ← 热点改写 + 相似度校验
└─────────┬───────────┘
          ↓
┌─────────────────────────────────────────────────────┐
│           platform-preference-profiler               │ ← 平台画像
└─────────┬───────────────────┬───────────────────────┘
          ↓                   ↓                       ↓
┌─────────────────┐ ┌──────────────────┐ ┌─────────────────────┐
│ content-gen-xhs │ │ content-gen-dy   │ │ content-gen-wechat  │
└───────┬─────────┘ └───────┬──────────┘ └──────────┬──────────┘
        ↓                   ↓                       ↓
┌─────────────────────────────────────────────────────────────┐
│                  content-review-polish                       │ ← 审核润色
└─────────────────────────┬───────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                       risk-check                             │ ← 风险检测
└─────────────────────────┬───────────────────────────────────┘
                          ↓
          ┌───────────────┴───────────────┐
          ↓                               ↓
┌─────────────────┐            ┌─────────────────────┐
│  image-compose   │            │ xhs-publish-package │
│  (图片渲染)       │            │ (发布打包)           │
└───────┬──────────┘            └─────────────────────┘
        ↓
┌─────────────────┐
│ video-generate   │ ← 抖音卡片包
└─────────────────┘
```

---

## 测试仓库

所有模块的测试用例统一迁移至 `test-repository/`，每个模块含 `TEST_LOG.md` 测试日志。

| 模块 | 测试目录 | 测试日志 |
|------|----------|----------|
| content-generate-xhs | [test-repository/content-generate-xhs](test-repository/content-generate-xhs/) | [TEST_LOG](test-repository/content-generate-xhs/TEST_LOG.md) |
| content-generate-douyin | [test-repository/content-generate-douyin](test-repository/content-generate-douyin/) | [TEST_LOG](test-repository/content-generate-douyin/TEST_LOG.md) |
| content-generate-wechat | [test-repository/content-generate-wechat](test-repository/content-generate-wechat/) | [TEST_LOG](test-repository/content-generate-wechat/TEST_LOG.md) |
| content-review-polish | [test-repository/content-review-polish](test-repository/content-review-polish/) | [TEST_LOG](test-repository/content-review-polish/TEST_LOG.md) |
| hot-rewrite | [test-repository/hot-rewrite](test-repository/hot-rewrite/) | [TEST_LOG](test-repository/hot-rewrite/TEST_LOG.md) |
| hot-topic-collector | [test-repository/hot-topic-collector](test-repository/hot-topic-collector/) | [TEST_LOG](test-repository/hot-topic-collector/TEST_LOG.md) |
| image-compose | [test-repository/image-compose](test-repository/image-compose/) | [TEST_LOG](test-repository/image-compose/TEST_LOG.md) |
| platform-preference-profiler | [test-repository/platform-preference-profiler](test-repository/platform-preference-profiler/) | [TEST_LOG](test-repository/platform-preference-profiler/TEST_LOG.md) |
| risk-check | [test-repository/risk-check](test-repository/risk-check/) | [TEST_LOG](test-repository/risk-check/TEST_LOG.md) |
| video-generate | [test-repository/video-generate](test-repository/video-generate/) | [TEST_LOG](test-repository/video-generate/TEST_LOG.md) |
| xhs-publish-package | [test-repository/xhs-publish-package](test-repository/xhs-publish-package/) | [TEST_LOG](test-repository/xhs-publish-package/TEST_LOG.md) |

> 根目录 `tests/` 为系统级集成测试，保留原位不做迁移。

---

## 技术栈

| 组件 | 技术 |
|------|------|
| LLM | OpenAI API（GPT-4o-mini） + DashScope（文生图） |
| 图片渲染 | Playwright + HTML/CSS 模板 |
| 相似度 | Simhash（hot-rewrite） |
| 平台交互 | 飞书开放平台 API（消息卡片 + 多维表格） |
| 运行环境 | Python 3.10+ / FastAPI |

---

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env  # 填写 OPENAI_API_KEY、FEISHU_APP_ID 等

# 启动服务
python -m app.main
```

---

## 文档规范

- 每份文档头部/尾部包含署名：`Created by: 尹羿璇 | 2026-07-21`
- 每个模块包含 3 份文档：README.md（功能简介）、TECHNICAL_DESIGN.md（技术设计）、DEVELOPER_GUIDE.md（开发者指南）
- 测试目录统一存放于 `test-repository/{module-name}/`

---

> Created by: 尹羿璇 | 2026-07-21
