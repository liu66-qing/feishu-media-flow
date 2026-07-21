# Feishu Media Flow — 项目维基文档仓库

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 项目概述

多平台自媒体内容自动化工作流系统，覆盖从热点采集、内容生成、审核润色、风险检测到图片渲染、发布打包的全链路。支持小红书、抖音、微信公众号三个平台，通过 V2 Schema 平台偏好画像实现差异化内容输出。

---

## 模块文档索引

每个模块包含 3 份标准文档：

| 文档 | 说明 |
|------|------|
| README.md | 功能简介、核心特性、目录结构、快速入门 |
| TECHNICAL_DESIGN.md | 架构设计、数据结构、关键函数、设计决策 |
| DEVELOPER_GUIDE.md | 模块间交互、内部工作流、测试指南、调试技巧 |

---

### 主控服务

| 模块 | 功能 | 文档 |
|------|------|------|
| **app** | 飞书交互 + 调度 + Agent 循环 | [README](app/README.md) · [技术设计](app/TECHNICAL_DESIGN.md) · [开发者指南](app/DEVELOPER_GUIDE.md) |
| **platform-preference-profiler** | 平台偏好画像（V2 Schema 五维度） | [README](platform-preference-profiler/README.md) · [技术设计](platform-preference-profiler/TECHNICAL_DESIGN.md) · [开发者指南](platform-preference-profiler/DEVELOPER_GUIDE.md) |

### 热点采集与改写

| 模块 | 功能 | 文档 |
|------|------|------|
| **hot-topic-collector** | 多平台热点采集 + LLM 筛选 | [README](hot-topic-collector/README.md) · [技术设计](hot-topic-collector/TECHNICAL_DESIGN.md) · [开发者指南](hot-topic-collector/DEVELOPER_GUIDE.md) |
| **hot-rewrite** | 热点内容改写 + Simhash 相似度校验 | [README](hot-rewrite/README.md) · [技术设计](hot-rewrite/TECHNICAL_DESIGN.md) · [开发者指南](hot-rewrite/DEVELOPER_GUIDE.md) |

### 内容生成（三平台）

| 模块 | 功能 | 文档 |
|------|------|------|
| **content-generate-xhs** | 小红书 4-Step LLM Pipeline | [README](content-generate-xhs/README.md) · [技术设计](content-generate-xhs/TECHNICAL_DESIGN.md) · [开发者指南](content-generate-xhs/DEVELOPER_GUIDE.md) |
| **content-generate-douyin** | 抖音 4-Step LLM Pipeline | [README](content-generate-douyin/README.md) · [技术设计](content-generate-douyin/TECHNICAL_DESIGN.md) · [开发者指南](content-generate-douyin/DEVELOPER_GUIDE.md) |
| **content-generate-wechat** | 微信公众号 LLM + WebFetch | [README](content-generate-wechat/README.md) · [技术设计](content-generate-wechat/TECHNICAL_DESIGN.md) · [开发者指南](content-generate-wechat/DEVELOPER_GUIDE.md) |

### 审核与风控

| 模块 | 功能 | 文档 |
|------|------|------|
| **content-review-polish** | 四维评分 + 双模式润色 | [README](content-review-polish/README.md) · [技术设计](content-review-polish/TECHNICAL_DESIGN.md) · [开发者指南](content-review-polish/DEVELOPER_GUIDE.md) |
| **risk-check** | 本地规则 + LLM 语义审查 | [README](risk-check/README.md) · [技术设计](risk-check/TECHNICAL_DESIGN.md) · [开发者指南](risk-check/DEVELOPER_GUIDE.md) |

### 图片渲染与发布

| 模块 | 功能 | 文档 |
|------|------|------|
| **image-compose** | HTML 模板 + Playwright + AI 背景 | [README](image-compose/README.md) · [技术设计](image-compose/TECHNICAL_DESIGN.md) · [开发者指南](image-compose/DEVELOPER_GUIDE.md) |
| **video-generate** | 抖音图文卡片包（调用 image-compose） | [README](video-generate/README.md) · [技术设计](video-generate/TECHNICAL_DESIGN.md) · [开发者指南](video-generate/DEVELOPER_GUIDE.md) |
| **xhs-publish-package** | 小红书发布打包 | [README](xhs-publish-package/README.md) · [技术设计](xhs-publish-package/TECHNICAL_DESIGN.md) · [开发者指南](xhs-publish-package/DEVELOPER_GUIDE.md) |

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

## 测试日志索引

| 模块 | 测试日志 |
|------|----------|
| content-generate-xhs | [TEST_LOG](content-generate-xhs/TEST_LOG.md) |
| content-generate-douyin | [TEST_LOG](content-generate-douyin/TEST_LOG.md) |
| content-generate-wechat | [TEST_LOG](content-generate-wechat/TEST_LOG.md) |
| content-review-polish | [TEST_LOG](content-review-polish/TEST_LOG.md) |
| hot-rewrite | [TEST_LOG](hot-rewrite/TEST_LOG.md) |
| hot-topic-collector | [TEST_LOG](hot-topic-collector/TEST_LOG.md) |
| image-compose | [TEST_LOG](image-compose/TEST_LOG.md) |
| platform-preference-profiler | [TEST_LOG](platform-preference-profiler/TEST_LOG.md) |
| risk-check | [TEST_LOG](risk-check/TEST_LOG.md) |
| video-generate | [TEST_LOG](video-generate/TEST_LOG.md) |
| xhs-publish-package | [TEST_LOG](xhs-publish-package/TEST_LOG.md) |

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
- 每个模块包含 3 份标准文档 + 测试日志
- 目录结构：`{module-name}/README.md` · `TECHNICAL_DESIGN.md` · `DEVELOPER_GUIDE.md` · `TEST_LOG.md`

---

> Created by: 尹羿璇 | 2026-07-21
