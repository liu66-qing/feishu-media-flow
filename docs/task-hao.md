# 郝乐瑾 任务书

## 项目背景

飞书媒体Agent项目（feishu-media-flow），当前已跑通：/新建 → LLM生成文案 → 审批卡片 → 封面合成 → 排期。你负责补齐两个核心缺失模块：**视频自动生成** 和 **热点自动采集**。

仓库地址：https://github.com/liu66-qing/feishu-media-flow

---

## 任务1：`video-generate` Skill

### 做什么

新建 `video-generate/` 目录，实现一个 Skill，对接 MoneyPrinterTurbo（https://github.com/harry0703/MoneyPrinterTurbo ）的 HTTP API，实现"给一个选题 → 输出一个完整短视频"。

MoneyPrinterTurbo 会由刘俊清在服务器上部署（地址 `http://localhost:8080`），你的 Skill 作为调用方。

### 输入输出约定

输入 `input.json`：
```json
{
  "content_id": "CNT-xxx",
  "job_id": "JOB-xxx",
  "platform": "douyin",
  "topic": "大学生如何高效备考",
  "voice_name": "zh-CN-YunxiNeural",
  "video_source": "pexels",
  "duration": 60
}
```

输出 `video-generate.json`：
```json
{
  "content_id": "CNT-xxx",
  "job_id": "JOB-xxx",
  "video_path": "output/video.mp4",
  "cover_path": "output/cover.jpg",
  "duration": 63,
  "script": "生成的完整脚本文案",
  "subtitle_path": "output/subtitles.srt"
}
```

### 约束条件

1. 必须遵循项目统一 Skill 接口：`python main.py --job-dir <dir>`，读 input.json，写 video-generate.json 或 error.json
2. MoneyPrinterTurbo API 地址从环境变量 `VIDEO_API_URL` 读取（默认 `http://localhost:8080`）
3. 视频生成是异步的（提交任务 → 轮询状态），你的 Skill 需要轮询等待完成（超时 10 分钟报错）
4. 生成完毕后把视频文件和封面图拷贝到 `{job_dir}/output/` 目录下
5. 失败时写 error.json，格式：`{"status": "error", "generated_at": "ISO时间", "error": "错误信息"}`
6. requirements.txt 只加 `requests`
7. 不要引入新的 LLM 调用 — MoneyPrinterTurbo 内部自己调 LLM 生成脚本

### 目标效果

在服务器上执行 `python main.py --job-dir test_job/` 后，test_job/output/ 下有一个 60 秒左右的 mp4 视频 + 封面 jpg + 字幕 srt。

### 目录结构

```
video-generate/
├── main.py
├── SKILL.md
├── requirements.txt
└── test/
    └── fixtures/
        └── job1/
            └── input.json
```

---

## 任务2：`hot-topic-collector` Skill

### 做什么

新建 `hot-topic-collector/` 目录，实现一个 Skill，定时采集各平台热点，用 LLM 筛选出与"大学生社团运营"相关的选题。

### 输入输出约定

输入 `input.json`：
```json
{
  "content_id": "HOTCOL-xxx",
  "job_id": "JOB-xxx",
  "keywords": ["大学生", "社团", "运营", "校园", "新媒体"],
  "platforms": ["weibo", "douyin", "xhs"],
  "max_topics": 10
}
```

输出 `hot-topic-collector.json`：
```json
{
  "collected_at": "2026-07-14T09:00:00Z",
  "topics": [
    {
      "title": "热点标题",
      "source": "weibo",
      "source_url": "https://...",
      "heat_score": 85,
      "relevance_score": 0.8,
      "angle_suggestion": "可以从XX角度切入做小红书图文",
      "suggested_platform": "xhs"
    }
  ],
  "raw_count": 50,
  "filtered_count": 8
}
```

### 约束条件

1. 遵循 Skill 接口规范（同上）
2. 热点数据源使用公开可访问的接口，不要用需要登录的API：
   - 微博热搜：`https://weibo.com/ajax/side/hotSearch`
   - 或聚合平台如 tophub.today 的公开接口
   - 抖音/小红书热点可用第三方聚合
3. LLM 筛选调用通过环境变量 `LLM_API_KEY`/`LLM_BASE_URL`/`LLM_MODEL` 配置（项目已有的 qwen-plus）
4. 筛选 prompt 要明确：输入=热点列表+社团关键词，输出=匹配度评分+切入角度建议
5. 网络请求超时设 10 秒，某个平台抓取失败不影响其他平台
6. requirements.txt：`requests`, `openai`

### 目标效果

运行后输出 8-10 条与社团运营相关的热点，每条有明确的内容切入角度和建议发布平台。

### 目录结构

```
hot-topic-collector/
├── main.py
├── SKILL.md
├── prompts/
│   └── filter_topics.md
├── requirements.txt
└── test/
    └── fixtures/
        └── job1/
            └── input.json
```

---

## 通用要求

1. 所有代码推送到 https://github.com/liu66-qing/feishu-media-flow 的 main 分支
2. 每个 Skill 必须能独立运行测试：`python main.py --job-dir test/fixtures/job1`
3. SKILL.md 写清楚：功能描述、输入输出格式、依赖、当前状态
4. 不要修改 `app/` 目录下的代码（那部分由刘俊清负责集成）
5. 代码风格参考 `content-generate-xhs/main.py`（类型注解、错误处理、write_json 工具函数）
