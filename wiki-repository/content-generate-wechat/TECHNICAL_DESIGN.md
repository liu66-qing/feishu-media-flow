# content-generate-wechat 技术设计文档

> Created by: 尹羿璇 | 2026-07-21
> Last modified by: 尹羿璇 | 2026-07-21

## 1. 架构概览

```
┌────────────────────────────────────────────────────────┐
│              content-generate-wechat                    │
├────────────────────────────────────────────────────────┤
│  input.json                                             │
│    ↓                                                    │
│  load_json()                                            │
│    ↓                                                    │
│  ┌──────────────────────────────────────────────┐      │
│  │ generate_wechat_content_with_llm()           │      │
│  │  → call_llm() with WebFetch/WebSearch tools  │      │
│  │  → parse_llm_json() → normalize_image_plan() │      │
│  └──────────────────┬───────────────────────────┘      │
│                     ↓ 失败时降级                        │
│  ┌──────────────────────────────────────────────┐      │
│  │ generate_wechat_content() — 模板生成          │      │
│  │  → build_title_options()                     │      │
│  │  → build_sections() → build_body_md()        │      │
│  │  → build_image_plan()                        │      │
│  └──────────────────────────────────────────────┘      │
│    ↓                                                    │
│  content-generate-wechat.json                           │
└────────────────────────────────────────────────────────┘
```

## 2. 核心数据结构

### 2.1 输入 (`input.json`)

| 字段 | 类型 | 必填 | 说明 |
|------|------|:---:|------|
| content_id | string | 否 | 内容 ID |
| job_id | string | 否 | 任务 ID |
| topic | string | 是 | 选题主题 |
| column | string | 否 | 栏目名称（默认"内容观察"） |
| materials | list[str] | 否 | 参考素材 |
| reference_urls | list[str] | 否 | 参考链接 |
| target_length | int | 否 | 目标字数（默认 1500） |

### 2.2 输出 (`content-generate-wechat.json`)

| 字段 | 类型 | 说明 |
|------|------|------|
| status | string | "success" |
| timestamp | string | ISO 时间戳 |
| content_id | string | 继承自输入 |
| data.title_options | list[str] | 3 个候选标题 |
| data.selected_title | string | 选定标题 |
| data.summary | string | 摘要（≤120字） |
| data.body_md | string | Markdown 正文 |
| data.sections | list[dict] | 文章分节结构 |
| data.image_plan | list[dict] | 配图计划（1 cover + 2 inline） |
| data.cta | string | 结尾引导 |
| data.risk_notes | list[str] | 风险提示 |
| data.llm_enabled | bool | 是否使用 LLM |
| data.llm_error | string | LLM 错误信息 |

### 2.3 配图计划 (`image_plan[]`)

| 字段 | 说明 |
|------|------|
| role | "cover"（封面）或 "inline"（文内配图） |
| title | 配图标题 |
| prompt | AI 生图 prompt |
| target_heading | 对应的文章章节 |
| alt_text | 替代文字 |

## 3. 关键函数说明

### `call_llm(prompt, system, model) -> str`
支持 tool calling 的 LLM 调用：
- 注册 WebFetch 和 WebSearch 两个工具
- LLM 可自主决定是否调用工具获取外部信息
- 最多 3 轮工具调用循环，最后生成最终回答

### `web_fetch(url, prompt, max_chars) -> dict`
抓取网页内容：清理 HTML 标签，提取纯文本，截断到 max_chars。

### `web_search(query, max_results) -> dict`
通过 DuckDuckGo 搜索，返回标题和 URL 列表。

### `normalize_image_plan(value, topic, sections) -> list[dict]`
配图计划归一化：确保恰好 1 张 cover + 2 张 inline，缺失时用默认值填充。

### `generate_wechat_content(input_data) -> dict`
模板降级方案：纯规则生成标题、分节、正文。当 LLM 不可用时使用。

## 4. 设计决策

1. **LLM + 工具调用**：公众号文章需要更丰富的信息，LLM 可主动搜索/抓取补充素材
2. **弹性降级**：LLM 失败时回退到模板生成，保证流程不中断
3. **配图计划**：自动生成 3 张配图建议（1封面+2文内），供 image-compose 使用
4. **Markdown 正文**：公众号场景适合长文，使用 Markdown 格式便于后续转 HTML
