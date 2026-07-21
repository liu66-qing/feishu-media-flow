# Platform Preference Profiler 技术设计文档

## 1. 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                    platform-preference-profiler              │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  样本加载器   │───▶│  LLM 分析器   │───▶│  画像生成器   │  │
│  │ (load_samples)│    │(analyze_platform)│ │ (write_json) │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                    │                    │          │
│         ▼                    ▼                    ▼          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │ .data/samples/│    │  prompts/    │    │ .data/profiles/│  │
│  │ {platform}/   │    │analyze_samples│    │ {platform}_  │  │
│  │ sample_xxx.json│   │   .md        │    │ profile.json │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │    下游消费模块       │
                    ├─────────────────────┤
                    │ • content-generate-* │
                    │ • critic             │
                    │ • image-compose      │
                    └─────────────────────┘
```

## 2. 核心组件

### 2.1 样本加载器 (`load_samples`)

**职责**：从文件系统加载指定平台的样本数据

**输入**：
- `samples_dir`: 样本根目录（Path）
- `platform`: 平台标识（str）

**输出**：
- `list[dict]`: 样本列表

**逻辑**：
```python
def load_samples(samples_dir: Path, platform: str) -> list[dict]:
    platform_dir = samples_dir / platform
    if not platform_dir.exists():
        return []
    
    samples = []
    for sample_file in sorted(platform_dir.glob("*.json")):
        try:
            sample = json.loads(sample_file.read_text(encoding="utf-8"))
            samples.append(sample)
        except Exception as e:
            print(f"Warning: failed to load {sample_file}: {e}")
    
    return samples
```

**设计要点**：
- 按文件名排序保证确定性
- 异常样本跳过而非中断
- 返回空列表而非抛异常（优雅降级）

### 2.2 置信度计算器 (`calculate_confidence`)

**职责**：基于样本数量和指标一致性计算画像置信度

**算法**：
```
基础置信度 = f(样本数量)
  - count < 3:  0.3 + (count/3) * 0.2   → 0.3-0.5
  - 3 ≤ count ≤ 5: 0.5 + ((count-3)/2) * 0.2 → 0.5-0.7
  - count > 5: 0.7 + min((count-5)/10, 0.2) → 0.7-0.9

一致性调整 = max(0, 0.1 - CV * 0.05)
  - CV = 变异系数 = 标准差 / 均值
  - CV 越小 → 一致性越高 → 置信度越高

最终置信度 = min(0.95, 基础置信度 + 一致性调整)
```

**设计要点**：
- 样本数量是主要因子（3 个样本达到 0.5 置信度）
- 指标一致性是次要因子（最多贡献 0.1）
- 上限 0.95 保留不确定性空间

### 2.3 LLM 分析器 (`analyze_platform`)

**职责**：调用 LLM 分析样本并生成 V2 Schema 画像

**输入**：
- `client`: OpenAI 客户端
- `model`: 模型名称
- `platform`: 平台标识
- `samples`: 样本列表

**输出**：
- `dict`: V2 Schema 画像

**Prompt 结构**：
```
[analyze_samples.md 系统 prompt]

请分析以下{N}条{platform}平台的高表现内容样本，生成该平台的内容偏好画像（V2 Schema）：

[样本 JSON]
```

**重试机制**：
- 最多 2 次尝试
- 第 2 次附加提示："只返回 JSON 对象，不要 Markdown 代码块"
- 失败抛出 `ProfilerError`

**设计要点**：
- 使用 `response_format={"type": "json_object"}` 强制 JSON 输出
- 系统 prompt 和用户 prompt 合并为单个 user 消息（兼容不同 API 格式）
- 内容使用 list 格式 `[{"type": "text", "text": ...}]`（兼容多模态 API）

### 2.4 画像过期检查 (`is_profile_expired`)

**职责**：检查画像文件是否存在且未过期

**逻辑**：
```python
def is_profile_expired(profile_path: Path) -> bool:
    if not profile_path.exists():
        return True
    
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    gen_at = profile.get("gen_at", "")
    if not gen_at:
        return True
    
    gen_time = datetime.fromisoformat(gen_at)
    age_days = (datetime.now(_CST) - gen_time).days
    return age_days >= PROFILE_EXPIRY_DAYS  # 7 天
```

**设计要点**：
- 文件不存在 → 过期
- 缺少 `gen_at` 字段 → 过期
- 超过 7 天 → 过期
- 解析异常 → 过期（安全优先）

### 2.5 主流程 (`run`)

**职责**：编排完整的画像生成流程

**流程图**：
```
开始
  │
  ▼
读取 input.json
  │
  ▼
遍历 platforms 列表
  │
  ├─▶ 检查画像是否过期
  │     │
  │     ├─ 未过期 → 跳过（除非 --force）
  │     │
  │     └─ 已过期 → 继续分析
  │           │
  │           ▼
  │       加载样本
  │           │
  │           ▼
  │       调用 LLM 分析
  │           │
  │           ▼
  │       写入画像文件
  │
  ▼
生成索引文件
  │
  ▼
结束
```

**关键参数**：
- `--force`: 强制重新分析所有平台（忽略过期检查）
- `--incremental`: 增量模式（仅分析新样本，未来实现）

## 3. V2 Schema 详解

### 3.1 与 V0 的对比

| 特性 | V0 | V2 |
|------|-----|-----|
| 键名 | 长命名（`preference_weight`） | 压缩命名（`pref_weight`） |
| 嵌套 | 多层嵌套 | 扁平化 |
| 内容结构 | 字符串描述 | 二维数组（阶段/字数/说明） |
| 流量字段 | 无 | `post_rule`, `search_keywords` |
| 风控字段 | 简单列表 | 分级（`forbid_level`）+ 替换词（`allow_substitute`） |

### 3.2 字段分类

#### 元数据字段
```json
{
  "pf": "xhs",                    // 平台标识
  "gen_at": "2026-07-21T...",     // 生成时间
  "v": "1.0",                     // Schema 版本
  "conf": 0.65,                   // 置信度
  "s_cnt": 4,                     // 样本数量
  "s_ids": ["XHS-001", ...]       // 样本 ID 列表
}
```

#### 账号定位字段
```json
{
  "acc_type": "个人经验型女性向内容创作者...",
  "biz_scene": "高转化潜力的生活决策辅助场景..."
}
```

#### 选题偏好 (`topic`)
```json
{
  "pref": ["高考择校指导", ...],      // 偏好主题
  "pref_weight": [0.48, ...],         // 偏好权重
  "bad": ["纯品牌硬广", ...],         // 厌恶主题
  "tags": ["#无广告纯分享", ...],     // 高频标签
  "angle": "第一人称真实体验切入...",  // 切入角度
  "title_tpl": ["对于[人群]+[事件]..."], // 标题模板
  "post_rule": "高频发布（周更 2-3 篇）...", // 发布规则
  "search_keywords": ["高考选大学 女生", ...], // 搜索关键词
  "title_len": "12-22 字",            // 标题长度
  "ctas": ["一定要多找学姐学长问", ...] // CTA 话术
}
```

#### 语言风格 (`lang`)
```json
{
  "tone": "亲切闺蜜式口吻...",        // 语调
  "para": "短段落为主...",            // 段落特征
  "word_len": "320-980",             // 字数范围
  "interact": "设问引导...",          // 互动方式
  "emoji": "每 3-5 段插入 1 个...",    // emoji 使用
  "tag_limit": "8-12 个垂直标签...",   // 标签限制
  "text_forbid": ["绝对/必须/唯一", ...], // 禁用词
  "carrier": "图文为主（95%）...",     // 内容载体
  "link_rule": "禁止站外导流链接...",   // 链接规则
  "pronoun": "高频使用'你'...",        // 人称代词
  "split_symbol": "空行分隔..."        // 分隔符
}
```

#### 视觉风格 (`vis`)
```json
{
  "ratio": "4:5 竖版为主（占比 90%）",  // 画面比例
  "cover": "文字主导型封面...",         // 封面风格
  "color": ["暖棕", "淡黄", ...],       // 色彩偏好
  "text_color": "深灰（#333）...",      // 文字颜色
  "char": "人物出镜率<10%...",          // 人物出现
  "blank": "中高留白（≥40%）...",       // 留白程度
  "img_num": "1-11 张...",             // 图片数量
  "img_style": "生活化实拍＞精修图...",  // 图片风格
  "vis_forbid": ["过度美颜滤镜", ...],   // 视觉禁用
  "video_audio": "暂未见视频样本...",    // 视频/音频
  "img_layout": "单图封面 + 内页多图...", // 图片布局
  "font_style": "无衬线字体..."         // 字体风格
}
```

#### 内容结构 (`struct`)
```json
[
  ["开篇身份锚定", "20-60 字", "明确受众 + 场景 + 价值承诺"],
  ["核心判断声明", "30-80 字", "给出不可妥协原则"],
  ["结构化风险拆解", "180-500 字", "分点罗列可验证维度"],
  ["真实细节佐证", "60-150 字", "具象感官描写增强可信度"],
  ["情绪价值升华", "80-200 字", "将日常体验升维至成长隐喻"],
  ["轻量 CTA 收尾", "20-50 字", "自然植入行动建议"]
]
```

#### 风控字段
```json
{
  "forbid": [
    "医疗功效宣称",
    "教育结果保证",
    "性别对立表述"
  ],
  "forbid_level": [
    "高风险：涉及教育/健康结果承诺",
    "中风险：平台对比贬损",
    "低风险：过度修饰词"
  ],
  "allow_substitute": [
    "烂脸→肤感不适",
    "胃不舒服→肠胃敏感"
  ]
}
```

## 4. 弹性降级机制

### 4.1 降级策略

```
内容生成请求
      │
      ▼
  加载画像文件
      │
      ├─ 存在且未过期 ──▶ 使用画像（动态规则）
      │
      ─ 不存在或已过期 ──▶ 使用 platform_constraints.json（静态规则）
```

### 4.2 实现方式

各内容生成模块在启动时自动尝试加载画像：

```python
# content-generate-xhs/main.py
def load_platform_profile() -> dict | None:
    """Load platform preference profile (V2 Schema). Returns None if not found or expired."""
    if not _PROFILE_FILE.exists():
        return None
    try:
        profile = json.loads(_PROFILE_FILE.read_text(encoding="utf-8"))
        # Check expiry (7 days)
        gen_at = profile.get("gen_at", "")
        if gen_at:
            gen_time = datetime.fromisoformat(gen_at)
            if gen_time.tzinfo is None:
                gen_time = gen_time.replace(tzinfo=timezone.utc)
            age_days = (datetime.now(timezone.utc) - gen_time).days
            if age_days >= 7:
                return None
        return profile
    except Exception:
        return None


def build_system_prompt() -> str:
    """Build system prompt with platform constraints and optional preference profile."""
    base_prompt = "你是小红书内容共创编辑..."  # 静态规则
    
    # Inject platform preference profile if available
    profile = load_platform_profile()
    if profile:
        base_prompt += "\n\n## 平台偏好画像（动态）\n"
        base_prompt += f"- 置信度：{profile.get('conf', 0)}\n"
        # ... 注入各维度偏好
    
    return base_prompt
```

### 4.3 降级场景

| 场景 | 行为 |
|------|------|
| 画像文件不存在 | 使用静态规则 |
| 画像文件过期（>7 天） | 使用静态规则 |
| 画像文件损坏 | 使用静态规则 |
| 画像置信度过低（<0.3） | 使用静态规则（未来实现） |

## 5. 性能考量

### 5.1 耗时分析

| 阶段 | 耗时 | 说明 |
|------|------|------|
| 样本加载 | <100ms | 本地文件读取 |
| LLM 分析 | 10-30s | 取决于样本数量和模型 |
| 画像写入 | <50ms | 本地文件写入 |
| **总计** | **10-30s/平台** | 3 平台约 30-90s |

### 5.2 优化策略

1. **缓存机制**：7 天内不重复分析
2. **并行分析**：未来可实现多平台并行（当前串行）
3. **增量更新**：`--incremental` 模式（未来实现）

### 5.3 Token 消耗

| 平台 | 样本数 | 预估 Token | 说明 |
|------|--------|-----------|------|
| XHS | 4 | ~8000 | 样本平均 2000 token |
| Douyin | 3 | ~6000 | 样本平均 2000 token |
| WeChat | 3 | ~9000 | 样本平均 3000 token |
| **总计** | **10** | **~23000** | 约$0.05-0.10 |

## 6. 安全考量

### 6.1 API 密钥管理

- 通过环境变量加载（`LLM_API_KEY`）
- 使用 `python-dotenv` 从 `.env` 文件读取
- 不在代码中硬编码密钥

### 6.2 样本数据隐私

- 样本存储在本地 `.data/samples/` 目录
- 不上传到外部服务（除 LLM API）
- 敏感信息应在采集时脱敏

### 6.3 输出验证

- LLM 输出必须为合法 JSON
- 解析失败时重试 1 次
- 仍失败则抛出异常（不写入错误画像）

## 7. 扩展性设计

### 7.1 新增平台

1. 在 `.data/samples/` 创建新平台目录
2. 在 `input.json` 的 `platforms` 数组添加平台标识
3. 运行 profiler 生成画像
4. 在下游模块添加对应的画像加载逻辑

### 7.2 新增维度

1. 修改 `prompts/analyze_samples.md` 添加分析维度
2. 更新 V2 Schema 定义
3. 下游模块适配新字段

### 7.3 自定义模型

通过环境变量覆盖默认模型：

```bash
# 使用专用文本模型
export LLM_TEXT_MODEL="qwen-plus"

# 或使用其他兼容 API
export LLM_BASE_URL="https://api.openai.com/v1"
export LLM_MODEL="gpt-4o"
```

## 8. 故障排查

### 8.1 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 画像生成失败 | API 密钥错误 | 检查 `.env` 配置 |
| 画像为空 | 样本目录不存在 | 创建 `.data/samples/{platform}/` |
| 画像过期快 | 系统时间错误 | 检查服务器时区（应为 UTC+8） |
| LLM 返回非 JSON | Prompt 不够严格 | 更新 `analyze_samples.md` |

### 8.2 日志位置

- 标准输出：控制台打印分析进度
- 错误日志：`<job_dir>/error.json`
- 索引文件：`<job_dir>/platform-preference-profiler.json`

### 8.3 调试技巧

```bash
# 启用详细日志
export PYTHONDEBUG=1

# 单平台测试
python main.py --job-dir test/fixtures/job1 --force
# 修改 input.json 的 platforms 为 ["xhs"]

# 查看画像内容
cat .data/profiles/xhs_profile.json | python -m json.tool
```

## 9. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0 | 2026-07-21 | 初始版本，支持 XHS/Douyin/WeChat |

## 10. 参考资料

- [V2 Schema 定义](./平台偏好画像 Schema 迭代对比文档.md)
- [LLM Prompt 设计](./prompts/analyze_samples.md)
- [下游模块集成](../content-generate-xhs/main.py)
