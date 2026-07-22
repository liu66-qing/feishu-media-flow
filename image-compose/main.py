"""
image-compose 技能包 - 主入口
=============================

功能：根据 HTML 模板和变量合成小红书封面/卡片图片（1080x1350 PNG），
      可选 AI 生成氛围感背景图（Qwen-Image-2.0-Pro via DashScope）。

两种运行方式：
  1) 命令行：python main.py --job-dir <目录>
     输出到 <目录>/output/*.png、<目录>/logs.txt、<目录>/image-compose.json
  2) 代码调用：from main import run_job; run_job(Path("<目录>"))
     返回结果字典，不调用 sys.exit()，适合被测试脚本/工作流直接 import 使用。

依赖：playwright、python-dotenv（标准库以外）
环境变量：从项目根目录 .env 读取 LLM_API_KEY、LLM_BASE_URL、LLM_MODEL（仅 AI 模式需要）
"""

import argparse
import base64
import html
import json
import logging
import mimetypes
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright


# ---------------------------------------------------------------------------
# 平台偏好画像加载（V2 Schema）
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PROFILE_DIR = _PROJECT_ROOT / ".data" / "profiles"


def load_platform_profile(platform: str) -> dict | None:
    """Load platform preference profile (V2 Schema). Returns None if not found or expired."""
    profile_file = _PROFILE_DIR / f"{platform}_profile.json"
    if not profile_file.exists():
        return None
    try:
        profile = json.loads(profile_file.read_text(encoding="utf-8"))
        # Check expiry (7 days)
        gen_at = profile.get("gen_at", "")
        if gen_at:
            gen_time = datetime.fromisoformat(gen_at)
            if gen_time.tzinfo is None:
                from datetime import timezone as _tz
                gen_time = gen_time.replace(tzinfo=_tz.utc)
            age_days = (datetime.now(_tz.utc) - gen_time).days
            if age_days >= 7:
                return None
        return profile
    except Exception:
        return None


def get_visual_style_hints(platform: str, injected_profile: dict | None = None) -> dict:
    """Get visual style hints from platform preference profile for AI image generation."""
    profile = injected_profile or load_platform_profile(platform)
    if not profile:
        return {}
    
    vis = profile.get("vis", {})
    return {
        "color_palette": vis.get("color_palette", []),
        "composition": vis.get("composition", {}),
        "mood": vis.get("mood", ""),
        "decoration": vis.get("decoration", ""),
    }


def _relative_luminance(color: str) -> float:
    """Return WCAG relative luminance for a six-digit hex color."""
    value = str(color or "").strip().lstrip("#")
    if len(value) != 6:
        return 0.5
    try:
        channels = [int(value[index:index + 2], 16) / 255 for index in (0, 2, 4)]
    except ValueError:
        return 0.5
    linear = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast_ratio(first: str, second: str) -> float:
    high, low = sorted((_relative_luminance(first), _relative_luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


# ---------------------------------------------------------------------------
# 基础工具函数
# ---------------------------------------------------------------------------

def setup_logging(job_dir: Path):
    """配置日志：同时写入 {job_dir}/logs.txt 和标准输出 stdout。"""
    log_file = job_dir / "logs.txt"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout)
        ]
    )


def load_input(job_dir: Path) -> dict:
    """读取 {job_dir}/input.json 并返回解析后的字典。"""
    input_path = job_dir / "input.json"
    with open(input_path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_output(job_dir: Path, skill_name: str, data: dict):
    """写入成功结果到 {job_dir}/{skill_name}.json。"""
    output_path = job_dir / f"{skill_name}.json"
    result = {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "data": data
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


def write_error(job_dir: Path, error_msg: str):
    """写入错误结果到 {job_dir}/error.json。"""
    error_path = job_dir / "error.json"
    error_data = {
        "status": "error",
        "timestamp": datetime.now().isoformat(),
        "error": error_msg
    }
    with open(error_path, "w", encoding="utf-8") as f:
        json.dump(error_data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 模板加载与 HTML 渲染
# ---------------------------------------------------------------------------

def load_template(template_name: str) -> str:
    """
    加载 HTML 模板文件。
    模板位于 templates/{template_name}/template.html，文件中包含 {{title}}、{{subtitle}}、
    {{bg_color}}、{{accent_color}}、{{bg_image}}、{{width}}、{{height}} 等占位符。
    """
    template_dir = Path(__file__).parent / "templates" / template_name
    template_file = template_dir / "template.html"

    if not template_file.exists():
        raise ValueError(f"模板不存在: {template_name}")

    with open(template_file, "r", encoding="utf-8") as f:
        return f.read()


def render_html(template_html: str, variables: dict, output_size: dict) -> str:
    """
    将 variables 字典中的值替换到模板 HTML 的占位符中，返回可直接用于截图的完整 HTML 字符串。

    支持的变量（全部有默认值）：
        title       主标题
        subtitle    副标题
        bg_color    背景色（十六进制）
        accent_color  文字强调色
        bg_image    背景图（URL 或 base64 data URI；为空则不使用背景图）
    output_size 决定 {{width}}/{{height}}，默认 1080x1350。
    """
    width = output_size.get("width", 1080)
    height = output_size.get("height", 1350)
    defaults = {
        "title": "",
        "subtitle": "",
        "body": "",
        "highlight": "",
        "section_label": "核心内容",
        "brand_name": "校园新媒体",
        "series_name": "本期精选",
        "page_label": "01 / 01",
        "page_number": "01",
        "metric_label": "",
        "metric_value": "",
        "visual_style": "auto",
        "illustration_variant": "idea",
        "footer": "校园内容工作流",
        "bg_color": "#F7F4EE",
        "accent_color": "#C94F32",
        "bg_image": "",
        "width": width,
        "height": height,
    }
    values = {**defaults, **variables, "width": width, "height": height}
    raw_keys = {"bg_image", "bg_color", "accent_color", "width", "height"}

    rendered = template_html
    for key, value in values.items():
        string_value = str(value or "")
        if key not in raw_keys:
            string_value = html.escape(string_value, quote=True)
        rendered = rendered.replace(f"{{{{{key}}}}}", string_value)
    return rendered


# ---------------------------------------------------------------------------
# Playwright 截图
# ---------------------------------------------------------------------------

def capture_screenshot(html_content: str, output_path: Path, width: int, height: int):
    """
    启动 headless Chromium，加载渲染后的 HTML，等待网络空闲后截图保存为 PNG。
    Playwright 不通过 file:// 协议加载本地文件，因此背景图必须以 base64 data URI 形式
    内嵌在 HTML 中（参考 image_to_data_uri 函数）。
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": width, "height": height})

        page.set_content(html_content)
        page.wait_for_load_state("networkidle")
        page.screenshot(path=str(output_path), full_page=False)

        browser.close()


# ---------------------------------------------------------------------------
# AI 背景图生成（DashScope / Qwen-Image-2.0-Pro）
# ---------------------------------------------------------------------------

def load_env_config() -> dict:
    """
    从项目根目录 .env 读取 AI 调用所需配置。

    环境变量：
        LLM_API_KEY   百炼 API Key（必填，否则 AI 模式会自动降级）
        LLM_BASE_URL  百炼 workspace 的 base URL，支持 compatible-mode/v1 结尾，
                     会自动转换为原生 API 路径 .../api/v1/services/aigc/multimodal-generation/generation
        LLM_MODEL     模型名，默认 qwen-image-2.0-pro-2026-06-22
    """
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "")
    model = os.getenv("LLM_MODEL", "wanx2.1-t2i-turbo")

    if base_url:
        if "/compatible-mode/" in base_url:
            api_base = base_url.replace("/compatible-mode/v1", "/api/v1")
        elif base_url.rstrip("/").endswith("/v1"):
            api_base = base_url.rstrip("/")
        else:
            api_base = base_url.rstrip("/") + "/api/v1"
    else:
        api_base = "https://dashscope.aliyuncs.com/api/v1"

    endpoint = api_base.rstrip("/") + "/services/aigc/text2image/image-synthesis"

    return {
        "api_key": api_key,
        "endpoint": endpoint,
        "model": model
    }


def mask_api_key(key: str) -> str:
    """对 API Key 做脱敏：保留前 4 位和后 4 位，中间用 *** 代替，避免泄露到日志。"""
    if len(key) <= 8:
        return "***"
    return key[:4] + "***" + key[-4:]


# ---------------------------------------------------------------------------
# 场景风格关键词库（对应 cover_prompt_guide.md 分类）
# ---------------------------------------------------------------------------

SCENE_STYLE_MAP = {
    "学习": "中国大学图书馆或自习室，18至24岁大学生学习小组，书本与笔记本电脑，专注而有朝气",
    "校园": "中国大学校园教学楼与林荫路，18至24岁大学生结伴交流，青春明亮",
    "美食": "中国大学食堂或校园咖啡空间，18至24岁大学生用餐交流，干净有活力",
    "生活": "中国大学宿舍公共区或校园生活空间，18至24岁大学生日常协作，真实自然",
    "穿搭": "中国大学校园步道，18至24岁大学生清爽日常穿搭，青春编辑感",
    "活动": "中国大学社团活动现场，18至24岁大学生共同布展或排练，热烈有秩序",
    "通知": "中国大学校园公告与活动空间，年轻学生查看信息，现代编辑海报感",
    "情绪": "中国大学校园傍晚学习生活场景，18至24岁大学生安静思考，克制温暖",
}

SCENE_KEYWORDS = {
    "学习": ["学习", "考试", "考证", "考研", "笔记", "书本", "图书馆", "自习", "复习", "规划"],
    "校园": ["校园", "宿舍", "开学", "毕业", "梧桐", "银杏"],
    "美食": ["吃", "食堂", "美食", "饭", "咖啡", "蛋糕", "奶茶", "甜点", "探店", "减脂", "健康餐", "菜单", "食谱"],
    "生活": ["生活", "日常", "vlog", "周末", "放松", "改造", "收纳", "好物"],
    "穿搭": ["穿搭", "衣服", "搭配", "包包", "购物", "公式", "秋季", "冬季", "春季", "夏季"],
    "活动": ["社团", "活动", "聚会", "迎新", "晚会", "比赛", "大赛", "歌手", "报名", "招新", "倒计时"],
    "通知": ["通知", "报名", "招募", "面试", "会议", "讲座", "奖学金", "申请", "截止", "指南", "流程"],
    "情绪": ["心情", "感悟", "随笔", "深夜", "情绪", "晚安", "治愈", "温柔", "焦虑", "心理", "压力", "疗愈"],
    "情感": ["恋爱", "脱单", "追女生", "追男生", "备胎", "舔狗", "倒追", "相亲", "婚姻", "感情", "分手", "复合", "撩", "约会", "表白"],
}


def infer_scene_from_text(text: str) -> str:
    """
    根据文本内容推断场景分类。
    采用「得分制」：统计每个场景命中的关键词数量，返回得分最高的场景。
    无匹配时返回 '学习'（默认兖底）。
    """
    if not text:
        return "学习"
    text_lower = text.lower()

    scores = {}
    for scene, keywords in SCENE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[scene] = score

    if not scores:
        return "学习"

    # 返回得分最高的场景；同分时按 SCENE_KEYWORDS 定义顺序优先
    return max(scores, key=lambda s: scores[s])


# ---------------------------------------------------------------------------
# 场景 → 模板 + 配色 智能匹配（对应 cover_prompt_guide.md 构图分类）
# ---------------------------------------------------------------------------

SCENE_TEMPLATE_MAP = {
    "学习": {
        "template": "xhs-cover-08",   # 全幅柔焦 + 中心白卡
        "bg_color": "#F5F0EB",
        "accent_color": "#8B7355",
        "blank_area": "全幅柔焦留白",
    },
    "校园": {
        "template": "xhs-cover-06",   # 顶部文字（上半留白背景）
        "bg_color": "#E8F4E8",
        "accent_color": "#4A7C59",
        "blank_area": "上半部分",
    },
    "美食": {
        "template": "xhs-cover-03",   # 底部文字（下半留白背景）
        "bg_color": "#FFF5E6",
        "accent_color": "#D4A574",
        "blank_area": "下半部分",
    },
    "生活": {
        "template": "xhs-cover-06",   # 顶部文字（上半留白背景）
        "bg_color": "#E8F0F5",
        "accent_color": "#5B8BA0",
        "blank_area": "上半部分",
    },
    "穿搭": {
        "template": "xhs-cover-07",   # 左对齐杂志风（侧边留白）
        "bg_color": "#F5F0F0",
        "accent_color": "#A0788C",
        "blank_area": "侧边",
    },
    "活动": {
        "template": "xhs-cover-04",   # 大字报+emoji（活泼）
        "bg_color": "#FFE4E1",
        "accent_color": "#FF6B6B",
        "blank_area": "中心",
    },
    "通知": {
        "template": "xhs-cover-02",   # 卡片式（正式）
        "bg_color": "#E8EAF6",
        "accent_color": "#5C6BC0",
        "blank_area": "中心",
    },
    "情绪": {
        "template": "xhs-cover-03",   # 底部文字（氛围感背景）
        "bg_color": "#F0E6F6",
        "accent_color": "#9575CD",
        "blank_area": "上半部分",
    },
}


CARD_TEMPLATE_SETS = {
    "editorial": {
        "cover": "campus-poster-cover",
        "card": "campus-poster-card",
        "summary": "campus-poster-summary",
        "bg_color": "#F7F4EE",
        "accent_color": "#C94F32",
        "blank_area": "中心和上半部分",
    },
    "comic": {
        "cover": "campus-comic-cover",
        "card": "campus-comic-card",
        "summary": "campus-comic-summary",
        "bg_color": "#FCFCFA",
        "accent_color": "#1688F8",
        "blank_area": "下半部分插画区",
    },
}

COMIC_STYLE_KEYWORDS = [
    "为什么", "怎么", "如何", "到底", "是不是", "值不值", "区别", "对比", "真相", "误区",
    "纠结", "焦虑", "困惑", "避坑", "踩坑", "复盘", "经历", "故事", "观点", "科普",
    "看懂", "入门", "原理", "趋势", "ai", "agent", "机器人", "内行", "聊聊",
]

EDITORIAL_STYLE_KEYWORDS = [
    "通知", "公告", "招新", "招募", "报名", "截止", "倒计时", "活动", "比赛", "晚会",
    "讲座", "会议", "奖学金", "申请", "流程", "步骤", "清单", "日程", "指南", "发布",
]


def infer_visual_style(text: str, preferred: str = "auto") -> str:
    """Select a reusable visual system from topic semantics."""
    normalized_preference = str(preferred or "auto").strip().lower()
    aliases = {
        "handdrawn": "comic", "hand-drawn": "comic", "漫画": "comic", "手绘": "comic",
        "poster": "editorial", "海报": "editorial", "编辑": "editorial",
    }
    normalized_preference = aliases.get(normalized_preference, normalized_preference)
    if normalized_preference in CARD_TEMPLATE_SETS:
        return normalized_preference
    if normalized_preference == "legacy_scene":
        return "legacy_scene"

    content = str(text or "").lower()
    comic_score = sum(1 for keyword in COMIC_STYLE_KEYWORDS if keyword in content)
    editorial_score = sum(1 for keyword in EDITORIAL_STYLE_KEYWORDS if keyword in content)
    comic_score += content.count("?") + content.count("？")
    if any(token in content for token in ("a/b", "vs", "优缺点", "一边", "另一边")):
        comic_score += 2
    return "comic" if comic_score > editorial_score else "editorial"


def infer_illustration_variant(text: str, role: str = "card") -> str:
    """Choose a comic scene composition without coupling it to the topic taxonomy."""
    if role == "summary":
        return "group"
    content = str(text or "").lower()
    if any(keyword in content for keyword in ("对比", "区别", "两种", "各自", "vs", "a/b", "优缺点")):
        return "compare"
    if any(keyword in content for keyword in ("对话", "沟通", "交流", "提问", "答疑", "采访", "讨论")):
        return "dialogue"
    if any(keyword in content for keyword in ("三类", "三种", "大家", "团队", "同学们", "群体", "一起")):
        return "group"
    if any(keyword in content for keyword in ("方法", "步骤", "清单", "怎么做", "如何", "先", "再")):
        return "explain"
    return "idea"


def select_card_template_set(text: str, preferred: str = "auto") -> dict:
    visual_style = infer_visual_style(text, preferred)
    if visual_style == "legacy_scene":
        visual_style = "editorial"
    config = dict(CARD_TEMPLATE_SETS[visual_style])
    config["visual_style"] = visual_style
    return config


def select_template(
    scene: str,
    template_name: str = "",
    text: str = "",
    visual_style: str = "auto",
    role: str = "cover",
) -> dict:
    """
    根据场景自动选择最佳模板和配色。
    若已指定 template_name 则不覆盖，仅补充配色。
    返回 dict: {template, bg_color, accent_color, blank_area}
    """
    selected_style = infer_visual_style(text, visual_style)
    if selected_style == "legacy_scene":
        config = dict(SCENE_TEMPLATE_MAP.get(scene, SCENE_TEMPLATE_MAP["学习"]))
        config["visual_style"] = "legacy_scene"
    else:
        template_set = select_card_template_set(text, selected_style)
        config = {
            "template": template_set.get(role, template_set["cover"]),
            "bg_color": template_set["bg_color"],
            "accent_color": template_set["accent_color"],
            "blank_area": template_set["blank_area"],
            "visual_style": template_set["visual_style"],
        }
    if template_name:
        config["template"] = template_name
        if template_name.startswith("campus-comic-"):
            config.update({"visual_style": "comic", "bg_color": "#FCFCFA", "accent_color": "#1688F8", "blank_area": "下半部分插画区"})
        elif template_name.startswith("campus-poster-"):
            config.update({"visual_style": "editorial", "bg_color": "#F7F4EE", "accent_color": "#C94F32", "blank_area": "中心和上半部分"})
        elif template_name.startswith("xhs-"):
            legacy_config = dict(SCENE_TEMPLATE_MAP.get(scene, SCENE_TEMPLATE_MAP["学习"]))
            legacy_config.update({"template": template_name, "visual_style": "legacy_scene"})
            config = legacy_config
        elif template_name.startswith("wechat-"):
            config.update({"visual_style": "editorial", "bg_color": "#F7F4EE", "accent_color": "#C94F32", "blank_area": "中心和上半部分"})
    return config


def build_ai_prompt(
    title: str,
    subtitle: str,
    ai_prompt: str,
    blank_area: str = "中心",
    visual_style: str = "editorial",
    illustration_variant: str = "idea",
) -> str:
    """
    构建发给 AI 的图片生成 prompt：
      - 若用户在 input.json 的 variables.ai_prompt 中传入了自定义 prompt，直接使用；
      - 否则根据 title/subtitle 自动推断场景风格，组装适配 DashScope wanx 的专业 prompt。
      - 生成完整场景图，不要求留白（文字遮挡由 HTML 模板半透明遮罩处理）。

    Prompt 策略（参考 cover_prompt_guide.md）：
      - 不含"小红书"字样，避免触发平台敏感词
      - 不要求生成文字（AI 生图模型画文字会乱码）
      - 生成完整场景，不要纯色块留白
      - 要求博主实拍感、8K 高清
    """
    marker = "硬性身份与场景约束"
    if ai_prompt and marker in ai_prompt:
        return ai_prompt

    combined_text = f"{title} {subtitle}"
    scene = infer_scene_from_text(combined_text)
    style_prompt = SCENE_STYLE_MAP.get(scene, SCENE_STYLE_MAP["学习"])
    creative_direction = ai_prompt.strip() if ai_prompt else f"主题语义：{title}；补充语义：{subtitle}"
    if visual_style == "comic":
        return (
            f"竖版极简手绘AI知识漫画插画，{creative_direction}。"
            f"场景语义：{style_prompt}；构图类型：{illustration_variant}。"
            f"深海军蓝、青蓝与白色的TYUT创新学社品牌配色，粗黑或深蓝马克笔线条，圆头抽象大学生人物，"
            f"人物表情克制幽默，动作清楚，像知识科普漫画而不是儿童绘本。"
            f"只表达一个视觉隐喻：AI浪潮、旧路线与项目路线分岔、空白简历逐步点亮、工具使用者与问题解决者对照中的一种；"
            f"主体集中在{blank_area}，其余区域干净，方便后续由HTML模板排中文标题、Logo与二维码。"
            f"{marker}：角色只能表达18至24岁的中国大学生、社团成员或校园志愿者；"
            f"通过书包、笔记本电脑、展台、图书馆桌椅、社团物料等体现中国大学校园语境。"
            f"禁止社会职场人士、商务会议、儿童、中学生、游客、纯自然风景、旅游地标、商业棚拍和写实网红人物。"
            f"无任何文字、字母、数字、水印、logo、校徽、二维码或品牌标识；不要生成伪文字。"
            f"画面平整清晰、留白充足、黑线边缘干净，适合作为知识图文卡片插画。"
        )
    prompt = (
        f"竖版校园主题编辑海报背景，{creative_direction}。"
        f"场景设计：{style_prompt}。"
        f"画面要有一个亮眼且明确的主题视觉焦点，使用朱红、暖白、黑色与少量钴蓝形成现代校园海报配色，"
        f"构图简洁有层次，在{blank_area}保留干净的文字排版空间，主体不得遮挡该区域。"
        f"{marker}：人物只能是18至24岁的中国大学生，身份呈现为学生、社团成员或校园志愿者；"
        f"地点只能在中国大学校园、教学楼、图书馆、自习室、宿舍公共区、食堂或社团活动空间。"
        f"禁止社会职场人士、商务会议、儿童、中学生、游客、城市街拍、纯自然风景、旅游地标、豪宅和商业影棚。"
        f"禁止人物大头特写与网红摆拍，优先中景或远景、自然互动、真实校园细节。"
        f"无任何文字、字母、数字、水印、logo、校徽或品牌标识；不要生成伪文字。"
        f"高质量海报摄影或精致编辑插画质感，明亮、青春、有冲击力，但背景细节不能干扰后续标题。"
    )
    return prompt


def download_image(url: str, save_path: Path):
    """将 AI 返回的 OSS 临时 URL 下载保存到本地 save_path。"""
    urllib.request.urlretrieve(url, str(save_path))
    if not save_path.exists() or save_path.stat().st_size == 0:
        raise Exception("下载图片失败，文件为空")


def image_to_data_uri(image_path: str) -> str:
    """
    将本地图片文件读取为 base64 data URI（如 data:image/png;base64,iVBOR...）。
    用于将 AI 生成的背景图或用户自定义本地背景图直接内嵌到 HTML 中，
    避免 Playwright headless 模式下 file:// 协议无法加载本地文件的安全限制。
    """
    path = Path(image_path)
    if not path.exists():
        return image_path
    mime_type, _ = mimetypes.guess_type(str(path))
    if not mime_type:
        mime_type = "image/png"
    with open(path, "rb") as f:
        img_data = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime_type};base64,{img_data}"


def generate_ai_background(title: str, subtitle: str, ai_prompt: str,
                           output_dir: Path, env_config: dict) -> tuple:
    """
    调用 DashScope 文生图接口生成 AI 背景图。

    流程：
      1. 用 build_ai_prompt() 构建 prompt
      2. 调用 wanx2.1-t2i-turbo 文生图
      3. 从 response 中抽取 image URL
      4. 下载图片保存到 {output_dir}/ai_bg.png
      5. 失败自动重试 1 次（共 2 次尝试），仍失败则抛异常交由上层降级

    返回：(本地保存路径字符串，实际使用的 prompt)
    """
    prompt = build_ai_prompt(title, subtitle, ai_prompt)
    save_path = output_dir / "ai_bg.png"

    endpoint = env_config["endpoint"]
    model = env_config["model"]
    api_key = env_config["api_key"]

    request_body = {
        "model": model,
        "input": {
            "prompt": prompt
        },
        "parameters": {
            "size": "768*1024",
            "n": 1
        }
    }
    logging.info(
        f"Calling DashScope text2image, model={model}, "
        f"prompt={prompt[:80]}..., api_key={mask_api_key(api_key)}"
    )

    last_error = None
    for attempt in range(2):
        try:
            data = json.dumps(request_body).encode("utf-8")
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "X-DashScope-Async": "enable"
            }
            req = urllib.request.Request(endpoint, data=data, headers=headers, method="POST")

            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            # Async task: poll for result
            task_id = result.get("output", {}).get("task_id")
            if not task_id:
                raise Exception(f"No task_id in response: {json.dumps(result, ensure_ascii=False)[:300]}")

            logging.info(f"AI image task submitted: {task_id}, polling...")
            import time
            task_url = env_config["endpoint"].replace("/services/aigc/text2image/image-synthesis", f"/tasks/{task_id}")
            poll_headers = {"Authorization": f"Bearer {api_key}"}

            for _ in range(60):
                time.sleep(2)
                poll_req = urllib.request.Request(task_url, headers=poll_headers, method="GET")
                with urllib.request.urlopen(poll_req, timeout=15) as poll_resp:
                    task_result = json.loads(poll_resp.read().decode("utf-8"))

                task_status = task_result.get("output", {}).get("task_status", "")
                if task_status == "SUCCEEDED":
                    results_list = task_result.get("output", {}).get("results", [])
                    if results_list:
                        image_url = results_list[0].get("url")
                        break
                elif task_status == "FAILED":
                    raise Exception(f"Task failed: {json.dumps(task_result, ensure_ascii=False)[:300]}")
            else:
                raise Exception("AI image generation timed out (120s)")

            if not image_url:
                raise Exception(
                    f"API 返回中未找到 image URL: {json.dumps(result, ensure_ascii=False)[:300]}"
                )

            logging.info(f"AI image generated, downloading from {image_url[:80]}...")
            download_image(image_url, save_path)

            logging.info(f"AI background saved to: {save_path}")
            return (str(save_path.resolve()), prompt)

        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8")
            except Exception:
                pass
            last_error = f"HTTP {e.code}: {err_body[:200]}"
            logging.warning(f"AI generation attempt {attempt + 1} failed: {last_error}")
        except Exception as e:
            last_error = str(e)[:200]
            logging.warning(f"AI generation attempt {attempt + 1} failed: {last_error}")

    raise Exception(f"AI 背景图生成失败: {last_error}")


# ---------------------------------------------------------------------------
# 核心任务入口（供 CLI 和测试脚本共用）
# ---------------------------------------------------------------------------

def run_job(job_dir: Path) -> dict:
    """
    执行单次图片合成任务。这是技能包的核心函数，CLI 入口 main() 和批量测试脚本
    run_tests.py 都通过调用它来完成工作。

    参数：
        job_dir  任务目录，必须包含 input.json；输出文件（output/、logs.txt、
                 image-compose.json/error.json）都会写到这个目录下。

    返回：
        成功时返回形如 {"status": "success", "timestamp": "...", "data": {...}} 的字典；
        失败时抛出异常（CLI 入口 main() 会捕获并写 error.json）。

    处理流程：
        1. 读取 input.json，解析 template_name、variables、image_mode 等字段
        2. 如果 variables.bg_image 是本地文件路径，转为 base64 data URI
        3. 如果 image_mode == "ai_bg"：
             a. 加载 .env 中的 API Key
             b. Key 缺失 → 降级为 template 模式（fallback_reason=missing_api_key）
             c. Key 存在 → 调用 generate_ai_background()，失败则重试 1 次，
                仍失败则降级为 template 模式
             d. AI 成功 → 强制使用 xhs-cover-03 模板，将 AI 背景图作为 bg_image
        4. 加载模板、渲染 HTML、Playwright 截图
        5. 写 image-compose.json 并返回结果
    """
    setup_logging(job_dir)
    logging.info(f"Starting image-compose, job_dir: {job_dir}")

    input_data = load_input(job_dir)
    content_id = input_data.get("content_id", "")
    template_name = input_data.get("template_name", "")
    variables = input_data.get("variables", {})
    output_size = input_data.get("output_size", {"width": 1080, "height": 1350})
    image_mode = input_data.get("image_mode", "template")
    platform = str(input_data.get("platform") or "xhs")
    profile = input_data.get("preference_profile") or {}
    visual_hints = get_visual_style_hints(platform, profile)

    title = variables.get("title", "")
    subtitle = variables.get("subtitle", "")
    ai_prompt = variables.get("ai_prompt", "")
    bg_image_input = variables.get("bg_image", "")

    # 用户自定义本地背景图 → 转为 base64 data URI（避免 file:// 协议限制）
    if bg_image_input and not bg_image_input.startswith(("http://", "https://", "data:")):
        bg_path = Path(bg_image_input)
        if bg_path.exists():
            variables["bg_image"] = image_to_data_uri(str(bg_path.resolve()))

    width = output_size.get("width", 1080)
    height = output_size.get("height", 1350)

    ai_fallback_reason = None
    ai_prompt_used = None
    image_mode_used = image_mode

    output_dir = job_dir / "output"
    output_dir.mkdir(exist_ok=True)

    # ---------- 主题驱动的视觉系统与模板匹配 ----------
    visual_context = variables.get("visual_context", {})
    if visual_context:
        keywords = visual_context.get("keywords", [])
        if not isinstance(keywords, list):
            keywords = []
        topic_summary = visual_context.get("topic_summary", "")
        combined_text = f"{topic_summary} {' '.join(str(item) for item in keywords)} {title} {subtitle}"
    else:
        keywords = []
        combined_text = f"{title} {subtitle}"
    scene = infer_scene_from_text(combined_text)
    preferred_visual_style = str(variables.get("visual_style") or "auto")
    profile_style = str((profile.get("vis") or {}).get("visual_style") or "")
    if preferred_visual_style == "auto" and profile_style in CARD_TEMPLATE_SETS:
        preferred_visual_style = profile_style
    template_role = str(variables.get("template_role") or "cover")
    template_config = select_template(
        scene,
        template_name,
        text=combined_text,
        visual_style=preferred_visual_style,
        role=template_role,
    )
    visual_style_used = template_config.get("visual_style", "editorial")
    illustration_variant = str(
        variables.get("illustration_variant")
        or infer_illustration_variant(combined_text, template_role)
    )
    variables["visual_style"] = visual_style_used
    variables["illustration_variant"] = illustration_variant

    if not template_name:
        template_name = template_config["template"]

        # 自动设置配色（如果用户未自定义）
        if not variables.get("bg_color") or variables.get("bg_color") == "#FF6B6B":
            variables["bg_color"] = template_config["bg_color"]
        if not variables.get("accent_color") or variables.get("accent_color") == "#FFFFFF":
            variables["accent_color"] = template_config["accent_color"]

    palette = visual_hints.get("color_palette") or []
    if palette and not variables.get("bg_color"):
        variables["bg_color"] = str(palette[0])
    if len(palette) > 1 and not variables.get("accent_color"):
        variables["accent_color"] = str(palette[1])
    variables.setdefault("bg_color", template_config["bg_color"])
    variables.setdefault("accent_color", template_config["accent_color"])
    if _contrast_ratio(variables["bg_color"], variables["accent_color"]) < 4.5:
        variables["accent_color"] = "#1F2937" if _relative_luminance(variables["bg_color"]) > 0.45 else "#FFFFFF"
        logging.warning("Adjusted accent color to meet readable contrast")

    logging.info(
        "Smart template match: scene=%s, visual_style=%s, role=%s, variant=%s, template=%s",
        scene,
        visual_style_used,
        template_role,
        illustration_variant,
        template_name,
    )

    # ---------- AI 背景模式分支 ----------
    if image_mode == "ai_bg":
        env_config = load_env_config()
        if not env_config["api_key"]:
            ai_fallback_reason = "missing_api_key"
            logging.warning("Missing LLM_API_KEY, falling back to template mode")
            image_mode_used = "template"
        else:
            try:
                blank_area = template_config["blank_area"]

                # 生成与模板构图匹配的 AI prompt
                ai_prompt = build_ai_prompt(
                    title,
                    subtitle,
                    ai_prompt,
                    blank_area,
                    visual_style_used,
                    illustration_variant,
                )

                ai_bg_path_str, ai_prompt_used = generate_ai_background(
                    title, subtitle, ai_prompt, output_dir, env_config
                )
                bg_data_uri = image_to_data_uri(ai_bg_path_str)
                variables["bg_image"] = bg_data_uri
                image_mode_used = "ai_bg"

                logging.info(f"AI background generated: scene={scene}, blank_area={blank_area}")
            except Exception as e:
                ai_fallback_reason = str(e)[:200]
                logging.error(f"AI background generation failed, falling back to template: {e}")
                image_mode_used = "template"

    logging.info(
        f"Template: {template_name}, Content ID: {content_id}, Image Mode: {image_mode_used}"
    )

    # ---------- 模板渲染 + 截图 ----------
    template_html = load_template(template_name)
    rendered_html = render_html(template_html, variables, output_size)

    output_filename = f"{template_name}.png"
    output_path = output_dir / output_filename

    logging.info(f"Capturing screenshot to {output_path}")
    capture_screenshot(rendered_html, output_path, width, height)

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise Exception("截图生成失败，输出文件为空")

    result_data = {
        "image_path": str(output_path),
        "width": width,
        "height": height,
        "template_used": template_name,
        "visual_style_used": visual_style_used,
        "illustration_variant": illustration_variant,
        "image_mode_used": image_mode_used,
        "ai_fallback_reason": ai_fallback_reason,
        "ai_prompt_used": ai_prompt_used
    }

    result = {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "data": result_data
    }

    if content_id:
        write_output(job_dir, "image-compose", result_data)
    else:
        output_json = job_dir / "image-compose.json"
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    logging.info(f"Image compose completed successfully: {output_path}")
    return result


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main():
    """
    命令行入口：解析 --job-dir 参数，调用 run_job() 完成合成。
    成功时进程退出码为 0，失败时写 error.json 并以退出码 1 退出。
    """
    parser = argparse.ArgumentParser(description="Skill: image-compose")
    parser.add_argument("--job-dir", required=True, help="Job directory path")
    args = parser.parse_args()

    job_dir = Path(args.job_dir)

    try:
        run_job(job_dir)
        sys.exit(0)
    except Exception as e:
        logging.error(f"Image compose failed: {e}", exc_info=True)
        write_error(job_dir, str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
