# 尹羿璇 任务书

## 项目背景

飞书媒体Agent项目（feishu-media-flow），当前已跑通：/新建 → LLM生成文案 → 审批卡片 → 封面合成 → 排期。你负责的模块集中在**视觉效果提升**和**飞书卡片交互完善**。

仓库地址：https://github.com/liu66-qing/feishu-media-flow

---

## 任务1：优化封面图生成效果

### 做什么

当前封面用纯 HTML 模板截图，效果简陋。你需要研究真正好看的小红书封面是怎么用 AI 生图 prompt 做出来的，然后改进我们的 prompt 策略。

### 参考仓库

https://github.com/Xiangyu-CAS/xiaohongshu-ops-skill

去看这个仓库里：
- 生成封面图的 prompt 是怎么写的
- 用了什么模型、什么参数
- prompt 中控制风格/排版/色调的关键词是什么
- 有没有 negative prompt

把你的发现整理成 `image-compose/prompts/cover_prompt_guide.md`，内容包括：
- 好用的 prompt 模板（中英文都要）
- 风格关键词库（按场景分类：学习类、生活类、美食类、穿搭类...）
- 排版关键词（文字位置、留白、构图）

### 然后改代码

修改 `app/services/workflow.py` 中 `_compose_image_for_content` 方法：

1. 从生成结果（step1_analyze 的 scene/hook）提取视觉关键词
2. 用 `cover_prompt_guide.md` 中的模板组装高质量 prompt
3. 传 `image_mode="ai_bg"` 给 compose_job

### 约束条件

1. prompt 必须适配 DashScope wanx 模型（阿里通义万相）
2. 不要在 prompt 中要求生成文字（AI 生图模型画文字会乱码）— 文字由 Pillow/HTML 叠加
3. 生成的是**背景底图**，不是完整封面
4. 改进前后要有对比（同一个选题，改进前 vs 改进后的截图放到 `image-compose/docs/` 下）

### 目标效果

生成的封面背景图看起来像真实小红书博主会用的底图，而不是纯色方块。

---

## 任务2：素材周报卡片 + 采纳入队

### 做什么

实现每周一自动给管理员群发一张"本周热点素材"卡片，管理员点"采纳"后自动进入选题生成队列。

### 具体改动

1. **`app/services/agent_loop.py`** 的 `tick()` 方法中，加入周一触发逻辑：
   - 判断今天是否周一 且 今天还没发过素材卡片
   - 调用 `hot-topic-collector` Skill 获取热点（郝的 Skill，接口见她的任务书）
   - 用热点结果构建素材卡片发到群里

2. **`app/services/cards.py`** 新增 `build_material_review_card(topics)` 函数：
   - 展示 5-10 条热点：标题 + 来源 + 建议角度 + 建议平台
   - 每条有"采纳"/"忽略"按钮
   - 按钮 value 格式：`{"action": "adopt_topic", "topic_title": "...", "platform": "xhs", "angle": "..."}`

3. **`app/api/feishu.py`** 的 `_handle_card_action` 中，处理 `adopt_topic` 动作：
   - 把采纳的热点自动调用 `workflow.create_content_from_topic()` 进入生成流程

### 约束条件

1. 周一判断用服务器本地时间（UTC+8）
2. 防重复：用一个标记文件 `.data/weekly_material_sent_{date}.flag` 防止同一天重复发
3. 如果 `hot-topic-collector` Skill 还没就绪，先用 mock 数据测试卡片效果
4. 卡片样式参考已有的 `build_review_card` 和 `build_schedule_card`

### 目标效果

每周一早上群里收到一张热点卡片，点"采纳"后自动开始生成对应平台内容。

---

## 任务3：完善 `hot-rewrite` Skill

### 做什么

当前 `hot-rewrite/` 是模板生成版（SKILL.md 里明确写了"模板生成版"），改为真正用 LLM 改写。

### 具体要求

1. 读取原文 → 调用 LLM 从新角度改写 → 输出改写后内容
2. 改写后用 simhash 计算与原文相似度（当前已有 simhash 逻辑，保留）
3. 相似度 > 0.3 则自动要求 LLM 重写（最多 2 次重试）
4. 改写 prompt 要求：
   - 保留原文核心信息
   - 换一个表达角度/叙事风格
   - 不要编造原文没有的事实
   - 输出格式保持不变

### 约束条件

1. LLM 调用通过环境变量 `LLM_API_KEY`/`LLM_BASE_URL`/`LLM_MODEL`
2. 不改变现有输入输出 JSON 格式
3. SKILL.md 更新状态为"LLM版"
4. 保留 simhash 查重逻辑

### 目标效果

输入一篇热点文章，输出一篇角度不同但信息等价的改写文章，simhash 相似度 < 0.3。

---

## 任务4：视频预览卡片

### 做什么

在 `app/services/cards.py` 新增 `build_video_review_card()` 函数，用于视频生成完成后发到群里审批。

### 卡片内容

- 标题："🎬 视频生成完成：{topic}"
- 封面图预览（飞书卡片支持 img 组件，用封面图 URL）
- 脚本文案预览（折叠面板，展开看完整脚本）
- 视频时长
- "下载视频"按钮（链接到服务器静态文件 URL）
- "通过发布" / "打回重新生成" 按钮

### 函数签名

```python
def build_video_review_card(
    content_id: str,
    topic: str,
    script: str,
    cover_url: str,
    video_url: str,
    duration: int,
) -> dict:
```

### 约束条件

1. 飞书卡片不支持内嵌视频播放，只能用图片+链接
2. 按钮 value 格式与现有审批卡片一致：`{"action": "approve_publish", "content_id": "..."}`
3. 卡片 JSON 结构参考已有的 `build_review_card`
4. 封面图 URL 格式：`http://139.196.183.227:8000/static/jobs/{job_id}/output/cover.jpg`（静态文件服务由刘俊清配置）

### 目标效果

群里收到一张视频审批卡片，能看到封面、读到脚本、点链接下载视频、一键审批。

---

## 通用要求

1. 所有代码推送到 https://github.com/liu66-qing/feishu-media-flow 的 main 分支
2. 改动涉及 `app/` 目录时注意不要与郝的代码冲突（她只动 Skill 目录）
3. 代码风格参考现有文件（类型注解、async/await、错误处理）
4. 每个改动附带简要测试说明（怎么验证它work了）
