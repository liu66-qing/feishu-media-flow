# Platform Preference Profiler 开发者指南

本文档面向开发者，详细解读模块的运行流程、测试方法和集成方式。

## 目录

1. [模块定位](#1-模块定位)
2. [运行流程详解](#2-运行流程详解)
3. [测试指南](#3-测试指南)
4. [集成到工作流](#4-集成到工作流)
5. [调试技巧](#5-调试技巧)
6. [常见问题](#6-常见问题)

---

## 1. 模块定位

### 1.1 在系统中的角色

```
┌─────────────────────────────────────────────────────────────┐
│                      内容生产流水线                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │ hot-topic-   │───▶│ content-     │───▶│ image-       │  │
│  │ collector    │    │ generate-*   │    │ compose      │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                            │                      │          │
│                            ▼                      ▼          │
│                     ┌──────────────┐    ┌──────────────┐  │
│                     │ risk-check   │    │ xhs-publish  │  │
│                     └──────────────┘    └──────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         platform-preference-profiler (本模块)         │  │
│  │                                                      │  │
│  │  输入：.data/samples/{platform}/*.json               │  │
│  │  输出：.data/profiles/{platform}_profile.json        │  │
│  │                                                      │  │
│  │  消费者：content-generate-*, critic, image-compose   │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 核心职责

1. **样本分析**：读取真实平台样本，提取偏好特征
2. **画像生成**：调用 LLM 生成结构化画像（V2 Schema）
3. **置信度评估**：基于样本质量和数量计算可信度
4. **弹性降级**：画像缺失时回退到静态规则

### 1.3 设计原则

- **数据驱动**：基于真实样本，非人工规则
- **动态更新**：7 天有效期，定期刷新
- **优雅降级**：画像缺失不影响主流程
- **平台隔离**：各平台画像独立，互不干扰

---

## 2. 运行流程详解

### 2.1 启动流程

```bash
python platform-preference-profiler/main.py --job-dir <job_directory> [--force] [--incremental]
```

**参数说明**：
- `--job-dir`：必填，包含 `input.json` 的目录
- `--force`：可选，强制重新分析所有平台
- `--incremental`：可选，增量模式（仅分析新样本）

### 2.2 执行步骤

#### Step 1: 加载配置

```python
job = read_json(job_dir / "input.json")
# job = {
#     "content_id": "PROF-001",
#     "job_id": "JOB-001",
#     "platforms": ["xhs", "douyin", "wechat"],
#     "samples_dir": ".data/samples",
#     "output_dir": ".data/profiles"
# }
```

#### Step 2: 初始化 LLM 客户端

```python
client, model = build_client()
# 自动检测并替换图像模型为文本模型
# 如果 LLM_MODEL 包含 "image"，则使用 "qwen-plus"
```

#### Step 3: 遍历平台分析

```python
for platform in platforms:
    # 3.1 检查画像是否过期
    if not force and not is_profile_expired(profile_path):
        print(f"  Profile exists and is fresh, skipping")
        continue
    
    # 3.2 加载样本
    samples = load_samples(samples_dir, platform)
    if not samples:
        print(f"  Warning: no samples found for {platform}")
        continue
    
    # 3.3 调用 LLM 分析
    profile = analyze_platform(client, model, platform, samples)
    
    # 3.4 写入画像文件
    write_json(profile_path, profile)
```

#### Step 4: 生成索引文件

```python
index = {
    "cid": job.get("content_id", "PROF-unknown"),
    "jid": job.get("job_id", "JOB-unknown"),
    "sample_root": str(samples_dir.relative_to(project_root)),
    "profile_root": str(output_dir.relative_to(project_root)),
    "gen_at": now_iso(),
    "profiles": [
        {
            "pf": "xhs",
            "path": ".data/profiles/xhs_profile.json",
            "s_cnt": 4,
            "conf": 0.65,
            "v": "1.0"
        },
        # ... 其他平台
    ]
}
write_json(job_dir / OUTPUT_NAME, index)
```

### 2.3 LLM 分析流程

```python
def analyze_platform(client, model, platform, samples):
    # 1. 读取系统 prompt
    system_prompt = read_prompt("analyze_samples.md")
    
    # 2. 构建用户消息（合并系统 prompt）
    samples_text = json.dumps(samples, ensure_ascii=False, indent=2)
    user_message = f"{system_prompt}\n\n请分析以下{len(samples)}条{platform}平台..."
    
    # 3. 调用 LLM（最多 2 次尝试）
    for attempt in range(2):
        messages = [
            {"role": "user", "content": [{"type": "text", "text": user_message}]},
        ]
        
        if attempt == 1:
            messages.append({
                "role": "user",
                "content": "上一轮没有得到可解析的 JSON..."
            })
        
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=4096,
        )
        
        # 4. 解析响应
        raw = response.choices[0].message.content or ""
        try:
            profile = parse_json_object(raw)
            # 添加元数据
            profile["pf"] = platform
            profile["gen_at"] = now_iso()
            profile["v"] = "1.0"
            profile["s_cnt"] = len(samples)
            profile["s_ids"] = [s.get("sample_id") for s in samples]
            profile["conf"] = calculate_confidence(samples)
            return profile
        except Exception as e:
            if attempt == 1:
                raise ProfilerError(f"Failed to parse LLM response: {e}")
```

### 2.4 置信度计算

```python
def calculate_confidence(samples):
    count = len(samples)
    
    # 基础置信度（基于样本数量）
    if count < 3:
        base_conf = 0.3 + (count / 3) * 0.2  # 0.3-0.5
    elif count <= 5:
        base_conf = 0.5 + ((count - 3) / 2) * 0.2  # 0.5-0.7
    else:
        base_conf = 0.7 + min((count - 5) / 10, 0.2)  # 0.7-0.9
    
    # 一致性调整（基于指标变异系数）
    metrics_list = [s.get("metrics", {}) for s in samples if s.get("metrics")]
    if metrics_list:
        likes = [m.get("likes", 0) for m in metrics_list]
        if likes and max(likes) > 0:
            mean = sum(likes) / len(likes)
            variance = sum((x - mean)**2 for x in likes) / len(likes)
            cv = (variance ** 0.5) / mean if mean > 0 else 0
            consistency_bonus = max(0, 0.1 - cv * 0.05)
            base_conf = min(0.95, base_conf + consistency_bonus)
    
    return round(base_conf, 2)
```

**示例计算**：
- 4 个样本，likes=[36000, 8308, 5382, 1457]
- 基础置信度：0.5 + ((4-3)/2) * 0.2 = 0.6
- 均值：12786.75，标准差：14823，CV：1.16
- 一致性调整：max(0, 0.1 - 1.16 * 0.05) = 0.042
- 最终置信度：min(0.95, 0.6 + 0.042) = **0.64** ≈ 0.65

---

## 3. 测试指南

### 3.1 测试目录结构

```
platform-preference-profiler/
── test/
    └── fixtures/
        └── job1/
            ├── input.json              # 测试输入
            ├── platform-preference-profiler.json  # 预期输出（参考）
            └── error.json              # 错误日志（运行时生成）
```

### 3.2 运行测试

#### 基础测试

```bash
# 进入项目根目录
cd "y:\TYUT\creating learning club\feishu-media-flow-main"

# 运行 profiler（使用测试 fixture）
python platform-preference-profiler/main.py --job-dir platform-preference-profiler/test/fixtures/job1 --force
```

**预期输出**：
```
Analyzing platform: xhs
  Loaded 4 samples
  Profile saved to Y:\...\ .data\profiles\xhs_profile.json
Analyzing platform: douyin
  Loaded 3 samples
  Profile saved to Y:\...\ .data\profiles\douyin_profile.json
Analyzing platform: wechat
  Loaded 3 samples
  Profile saved to Y:\...\ .data\profiles\wechat_profile.json

Index file saved to Y:\...\platform-preference-profiler\test\fixtures\job1\platform-preference-profiler.json
Analyzed 3 platforms
```

#### 单平台测试

修改 `input.json`：
```json
{
  "content_id": "PROF-001",
  "job_id": "JOB-001",
  "platforms": ["xhs"],
  "samples_dir": ".data/samples",
  "output_dir": ".data/profiles"
}
```

然后运行：
```bash
python platform-preference-profiler/main.py --job-dir platform-preference-profiler/test/fixtures/job1 --force
```

### 3.3 验证输出

#### 检查画像文件

```bash
# 查看 XHS 画像
cat .data/profiles/xhs_profile.json | python -m json.tool

# 验证必填字段
python -c "
import json
profile = json.load(open('.data/profiles/xhs_profile.json'))
required = ['pf', 'gen_at', 'v', 'conf', 's_cnt', 's_ids', 'topic', 'lang', 'vis', 'struct', 'forbid']
missing = [f for f in required if f not in profile]
if missing:
    print(f'Missing fields: {missing}')
else:
    print('All required fields present')
"
```

#### 检查索引文件

```bash
cat platform-preference-profiler/test/fixtures/job1/platform-preference-profiler.json | python -m json.tool
```

**预期结构**：
```json
{
  "cid": "PROF-001",
  "jid": "JOB-001",
  "sample_root": ".data\\samples",
  "profile_root": ".data\\profiles",
  "gen_at": "2026-07-21T...",
  "profiles": [
    {
      "pf": "xhs",
      "path": ".data\\profiles\\xhs_profile.json",
      "s_cnt": 4,
      "conf": 0.65,
      "v": "1.0"
    },
    ...
  ]
}
```

### 3.4 自动化测试脚本

创建 `test/run_tests.py`：

```python
"""Automated tests for platform-preference-profiler."""

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROFILER_DIR = PROJECT_ROOT / "platform-preference-profiler"
TEST_FIXTURE = PROFILER_DIR / "test" / "fixtures" / "job1"


def run_profiler(force: bool = True) -> int:
    """Run the profiler and return exit code."""
    cmd = [
        sys.executable,
        str(PROFILER_DIR / "main.py"),
        "--job-dir", str(TEST_FIXTURE),
    ]
    if force:
        cmd.append("--force")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    return result.returncode


def validate_profile(platform: str) -> bool:
    """Validate a generated profile file."""
    profile_path = PROJECT_ROOT / ".data" / "profiles" / f"{platform}_profile.json"
    
    if not profile_path.exists():
        print(f"❌ Profile not found: {profile_path}")
        return False
    
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    
    required_fields = [
        "pf", "gen_at", "v", "conf", "s_cnt", "s_ids",
        "topic", "lang", "vis", "struct", "forbid"
    ]
    
    missing = [f for f in required_fields if f not in profile]
    if missing:
        print(f"❌ {platform} profile missing fields: {missing}")
        return False
    
    # Validate types
    if not isinstance(profile["conf"], (int, float)):
        print(f"❌ {platform} conf must be numeric")
        return False
    
    if not 0 <= profile["conf"] <= 1:
        print(f"❌ {platform} conf must be between 0 and 1")
        return False
    
    if not isinstance(profile["struct"], list):
        print(f"❌ {platform} struct must be array")
        return False
    
    print(f"✅ {platform} profile valid (conf={profile['conf']}, samples={profile['s_cnt']})")
    return True


def main():
    print("=" * 60)
    print("Platform Preference Profiler - Test Suite")
    print("=" * 60)
    
    # Step 1: Run profiler
    print("\n[1/3] Running profiler...")
    exit_code = run_profiler(force=True)
    if exit_code != 0:
        print("❌ Profiler failed")
        sys.exit(1)
    
    # Step 2: Validate profiles
    print("\n[2/3] Validating profiles...")
    platforms = ["xhs", "douyin", "wechat"]
    all_valid = True
    for platform in platforms:
        if not validate_profile(platform):
            all_valid = False
    
    if not all_valid:
        print("\n❌ Some profiles are invalid")
        sys.exit(1)
    
    # Step 3: Validate index file
    print("\n[3/3] Validating index file...")
    index_path = TEST_FIXTURE / "platform-preference-profiler.json"
    if not index_path.exists():
        print(f"❌ Index file not found: {index_path}")
        sys.exit(1)
    
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if len(index.get("profiles", [])) != len(platforms):
        print(f"❌ Index should have {len(platforms)} profiles, got {len(index.get('profiles', []))}")
        sys.exit(1)
    
    print(f"✅ Index file valid ({len(index['profiles'])} platforms)")
    
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
```

运行测试：
```bash
python platform-preference-profiler/test/run_tests.py
```

### 3.5 测试样本数据

当前测试样本位于 `.data/samples/`：

| 平台 | 样本数 | 来源 |
|------|--------|------|
| XHS | 4 | 真实小红书笔记 |
| Douyin | 3 | 真实抖音视频 |
| WeChat | 3 | 1 真实 + 2 占位符 |

**添加新样本**：
1. 在 `.data/samples/{platform}/` 创建 JSON 文件
2. 遵循样本格式（见 README）
3. 重新运行 profiler

---

## 4. 集成到工作流

### 4.1 在 Agent Loop 中调用

```python
# app/services/skill_runner.py
class SkillRunner:
    def run_profiler(self, platforms: list[str]) -> dict:
        """Run platform preference profiler."""
        job_dir = self._create_job_dir("profiler")
        
        input_data = {
            "content_id": f"PROF-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "job_id": f"JOB-{uuid.uuid4().hex[:8]}",
            "platforms": platforms,
            "samples_dir": ".data/samples",
            "output_dir": ".data/profiles"
        }
        
        write_json(job_dir / "input.json", input_data)
        
        # Run profiler
        result = subprocess.run(
            [sys.executable, "platform-preference-profiler/main.py",
             "--job-dir", str(job_dir), "--force"],
            capture_output=True, text=True
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Profiler failed: {result.stderr}")
        
        return read_json(job_dir / "platform-preference-profiler.json")
```

### 4.2 定时刷新画像

使用 cron 或调度系统定期运行：

```bash
# 每周日凌晨 2 点刷新画像
0 2 * * 0 cd /path/to/project && python platform-preference-profiler/main.py --job-dir scheduler/jobs/profiler --force >> logs/profiler.log 2>&1
```

### 4.3 下游模块集成

#### content-generate-xhs

```python
# 自动加载画像（已在 main.py 中实现）
from main import load_platform_profile, build_system_prompt

SYSTEM_PROMPT = build_system_prompt()
# 画像自动注入到 SYSTEM_PROMPT
```

#### critic

```python
# 评审时参考画像
from app.services.critic import load_platform_profile

async def evaluate_with_profile(self, draft, context):
    profile = load_platform_profile(draft.platform.value)
    if profile:
        # 使用画像中的偏好进行评审
        context["platform_preferences"] = profile
    
    return await self.evaluate(draft, context)
```

#### image-compose

```python
# 获取视觉风格提示
from image-compose.main import get_visual_style_hints

hints = get_visual_style_hints("xhs")
# hints = {
#     "color_palette": ["暖棕", "淡黄", ...],
#     "composition": {...},
#     "mood": "...",
#     "decoration": "..."
# }

# 用于 AI 生图 prompt
prompt = f"{base_prompt}, {hints['mood']}, colors: {', '.join(hints['color_palette'])}"
```

---

## 5. 调试技巧

### 5.1 启用详细日志

```bash
export PYTHONDEBUG=1
python platform-preference-profiler/main.py --job-dir test/fixtures/job1 --force
```

### 5.2 查看 LLM 原始响应

修改 `main.py` 临时添加调试输出：

```python
def analyze_platform(...):
    # ... 调用 LLM ...
    raw = response.choices[0].message.content or ""
    print(f"DEBUG: Raw LLM response:\n{raw[:1000]}")  # 临时调试
    # ...
```

### 5.3 单步调试

```bash
# 使用 Python 调试器
python -m pdb platform-preference-profiler/main.py --job-dir test/fixtures/job1 --force
```

### 5.4 检查环境变量

```bash
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('LLM_API_KEY:', 'SET' if os.getenv('LLM_API_KEY') else 'NOT SET')
print('LLM_BASE_URL:', os.getenv('LLM_BASE_URL', 'NOT SET'))
print('LLM_MODEL:', os.getenv('LLM_MODEL', 'NOT SET'))
print('LLM_TEXT_MODEL:', os.getenv('LLM_TEXT_MODEL', 'NOT SET'))
"
```

### 5.5 验证样本格式

```python
import json
from pathlib import Path

samples_dir = Path(".data/samples/xhs")
for sample_file in sorted(samples_dir.glob("*.json")):
    sample = json.loads(sample_file.read_text(encoding="utf-8"))
    required = ["sample_id", "platform", "title", "body", "metrics"]
    missing = [f for f in required if f not in sample]
    if missing:
        print(f" {sample_file.name}: missing {missing}")
    else:
        print(f"✅ {sample_file.name}: {sample['title'][:30]}...")
```

---

## 6. 常见问题

### Q1: 画像生成失败，报错 "missing environment variable(s)"

**原因**：`.env` 文件未加载或配置错误

**解决**：
```bash
# 检查.env 文件是否存在
ls -la .env

# 检查内容
cat .env | grep LLM

# 手动加载测试
python -c "from dotenv import load_dotenv; load_dotenv(); import os; print(os.getenv('LLM_API_KEY'))"
```

### Q2: LLM 返回非 JSON 格式

**原因**：Prompt 不够严格或模型不兼容

**解决**：
1. 检查 `prompts/analyze_samples.md` 是否包含 JSON 格式要求
2. 尝试更换模型（设置 `LLM_TEXT_MODEL`）
3. 查看原始响应（添加调试输出）

### Q3: 画像置信度过低（<0.5）

**原因**：样本数量不足或指标差异过大

**解决**：
1. 增加样本数量（至少 3 个）
2. 选择同类型高表现样本（指标相近）
3. 检查样本质量（标题、正文、指标是否完整）

### Q4: 下游模块未加载画像

**原因**：画像文件路径错误或已过期

**解决**：
```bash
# 检查画像文件是否存在
ls -la .data/profiles/

# 检查画像生成时间
cat .data/profiles/xhs_profile.json | grep gen_at

# 强制刷新
python platform-preference-profiler/main.py --job-dir test/fixtures/job1 --force
```

### Q5: 如何添加新平台？

**步骤**：
1. 创建样本目录：`.data/samples/{new_platform}/`
2. 添加样本文件（遵循样本格式）
3. 修改 `input.json` 的 `platforms` 字段
4. 运行 profiler 生成画像
5. 在下游模块添加对应的画像加载逻辑

### Q6: 画像过期后会自动重新生成吗？

**回答**：不会自动重新生成，需要手动运行或使用调度系统。

**建议**：
- 使用 cron 定时任务（每周一次）
- 或在 agent loop 中检测画像过期并触发刷新

---

## 附录

### A. 样本格式模板

```json
{
  "sample_id": "XHS-001",
  "platform": "xhs",
  "collected_at": "2026-07-21T10:00:00+08:00",
  "source_url": "https://www.xiaohongshu.com/discovery/item/...",
  "title": "样本标题",
  "body": "样本正文内容...",
  "hashtags": ["#标签 1", "#标签 2"],
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

### B. V2 Schema 完整字段

```json
{
  "pf": "xhs",
  "gen_at": "2026-07-21T18:01:13.128291+08:00",
  "v": "1.0",
  "conf": 0.65,
  "s_cnt": 4,
  "s_ids": ["XHS-001", "XHS-002", "XHS-003", "XHS-004"],
  "acc_type": "个人经验型女性向内容创作者",
  "biz_scene": "高转化潜力的生活决策辅助场景",
  "topic": {
    "pref": ["高考择校指导", "平价实用好物分享"],
    "pref_weight": [0.48, 0.32],
    "bad": ["纯品牌硬广", "抽象哲理说教"],
    "tags": ["#无广告纯分享", "#便宜小破烂"],
    "angle": "第一人称真实体验切入",
    "title_tpl": ["对于 [人群]+[事件] 的 [价值导向] 建议"],
    "post_rule": "高频发布（周更 2-3 篇）",
    "search_keywords": ["高考选大学 女生"],
    "title_len": "12-22 字",
    "ctas": ["一定要多找学姐学长问"]
  },
  "lang": {
    "tone": "亲切闺蜜式口吻",
    "para": "短段落为主（平均 2-3 行/段）",
    "word_len": "320-980",
    "interact": "设问引导",
    "emoji": "每 3-5 段插入 1 个精准 emoji",
    "tag_limit": "8-12 个垂直标签",
    "text_forbid": ["绝对/必须/唯一"],
    "carrier": "图文为主（95%）",
    "link_rule": "禁止站外导流链接",
    "pronoun": "高频使用'你'",
    "split_symbol": "空行分隔"
  },
  "vis": {
    "ratio": "4:5 竖版为主",
    "cover": "文字主导型封面",
    "color": ["暖棕", "淡黄"],
    "text_color": "深灰（#333）",
    "char": "人物出镜率<10%",
    "blank": "中高留白（≥40%）",
    "img_num": "1-11 张",
    "img_style": "生活化实拍＞精修图",
    "vis_forbid": ["过度美颜滤镜"],
    "video_audio": "暂未见视频样本",
    "img_layout": "单图封面 + 内页多图轮播",
    "font_style": "无衬线字体"
  },
  "struct": [
    ["开篇身份锚定", "20-60 字", "明确受众 + 场景 + 价值承诺"],
    ["核心判断声明", "30-80 字", "给出不可妥协原则"]
  ],
  "forbid": ["医疗功效宣称", "教育结果保证"],
  "forbid_level": [
    "高风险：涉及教育/健康结果承诺",
    "中风险：平台对比贬损"
  ],
  "allow_substitute": ["烂脸→肤感不适"]
}
```

### C. 相关文档

- [README.md](./README.md) - 快速入门
- [TECHNICAL_DESIGN.md](./TECHNICAL_DESIGN.md) - 技术设计
- [prompts/analyze_samples.md](./prompts/analyze_samples.md) - LLM Prompt
- [SKILL.md](./SKILL.md) - Skill 定义

---

**文档版本**：1.0  
**最后更新**：2026-07-21  
**维护者**：尹羿璇
