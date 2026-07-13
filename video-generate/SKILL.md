# video-generate

## 功能说明

video-generate 用于根据选题自动生成完整短视频，调用 MoneyPrinterTurbo HTTP API 实现"选题 → 短视频"的端到端生成。

当前版本支持：
- 读取 topic、voice_name、video_source、duration
- 调用 MoneyPrinterTurbo API 提交视频生成任务
- 异步轮询任务状态（超时 10 分钟）
- 下载生成的视频、封面和字幕文件到 output/ 目录
- 输出 video-generate.json 结果文件

## 输入

输入文件固定为：
```text
{job_dir}/input.json
```

示例：
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

字段说明：
- content_id: 内容 ID
- job_id: 任务 ID
- platform: 目标平台（douyin/xhs）
- topic: 选题内容
- voice_name: 语音名称（Azure TTS 语音名）
- video_source: 视频素材来源（pexels/pixabay）
- duration: 目标时长（秒）

## 输出

输出文件固定为：
```text
{job_dir}/video-generate.json
```

输出字段包括：
- content_id: 内容 ID
- job_id: 任务 ID
- video_path: 生成视频路径
- cover_path: 封面图片路径
- duration: 实际时长
- script: 生成的完整脚本文案
- subtitle_path: 字幕文件路径

同时在 `{job_dir}/output/` 目录下生成：
- video.mp4: 生成的视频文件
- cover.jpg: 封面图片
- subtitles.srt: 字幕文件

## 运行方式

在项目根目录下运行：
```bash
python video-generate/main.py --job-dir video-generate/test/fixtures/job1
```

## 环境变量

- VIDEO_API_URL: MoneyPrinterTurbo API 地址，默认 `http://localhost:8080`

## 依赖

- requests

## 当前状态

已完成基础框架实现，需在服务器上配合 MoneyPrinterTurbo 服务进行测试验证。