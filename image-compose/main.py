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
    title = variables.get("title", "")
    subtitle = variables.get("subtitle", "")
    bg_color = variables.get("bg_color", "#FFFFFF")
    accent_color = variables.get("accent_color", "#000000")
    bg_image = variables.get("bg_image", "")

    width = output_size.get("width", 1080)
    height = output_size.get("height", 1350)

    html = template_html
    html = html.replace("{{title}}", title)
    html = html.replace("{{subtitle}}", subtitle)
    html = html.replace("{{bg_color}}", bg_color)
    html = html.replace("{{accent_color}}", accent_color)
    html = html.replace("{{bg_image}}", bg_image)
    html = html.replace("{{width}}", str(width))
    html = html.replace("{{height}}", str(height))

    return html


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
    model = os.getenv("IMAGE_MODEL", "wanx2.1-t2i-turbo")

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
    "学习": "ins简约学习风，柔和书桌场景，笔记本、钢笔、咖啡元素，低饱和奶fufu色调",
    "校园": "清新校园风，梧桐道光影，柔和阳光，青春明亮，浅景深背景虚化",
    "美食": "美食特写背景，暖黄灯光，食物自然虚化，有食欲，浅景深",
    "生活": "治愈日常风，柔和自然光，干净明亮，生活化场景自然虚化",
    "穿搭": "简约穿搭背景，柔和光线，衣物元素边角虚化，干净ins风",
    "活动": "明亮活泼风，浅彩色小元素点缀，画面干净不杂乱，青春有活力",
    "通知": "柔和渐变背景，极简几何小装饰，干净正式",
    "情绪": "治愈氛围感，柔和夕阳光影，低饱和色调，大光圈背景虚化",
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


def select_template(scene: str, template_name: str = "") -> dict:
    """
    根据场景自动选择最佳模板和配色。
    若已指定 template_name 则不覆盖，仅补充配色。
    返回 dict: {template, bg_color, accent_color, blank_area}
    """
    config = SCENE_TEMPLATE_MAP.get(scene, SCENE_TEMPLATE_MAP["学习"])
    if template_name:
        config["template"] = template_name
    return config


def build_ai_prompt(title: str, subtitle: str, ai_prompt: str, blank_area: str = "中心") -> str:
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
    if ai_prompt:
        return ai_prompt

    # 从 title + subtitle 推断场景风格
    combined_text = f"{title} {subtitle}"
    scene = infer_scene_from_text(combined_text)

    style_prompt = SCENE_STYLE_MAP.get(scene, SCENE_STYLE_MAP["学习"])
    prompt = (
        f"3:4竖版封面背景图，{style_prompt}，"
        f"搭配{title}元素，"
        f"柔和漫反射自然光，完整场景构图，画面饱满丰富，"
        f"无任何文字、字母、数字、水印、logo，绝对不要生成任何文字，"
        f"高清8K细节真实，像博主随手拍的照片，低对比度不抢文字视线，"
        f"不要清晰人物正脸"
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

    # ---------- 智能模板匹配（两种模式共用） ----------
    # 根据 visual_context 或标题推断场景，自动选择最佳模板和配色
    if not template_name:
        visual_context = variables.get("visual_context", {})
        if visual_context:
            keywords = visual_context.get("keywords", [])
            topic_summary = visual_context.get("topic_summary", "")
            combined_text = f"{topic_summary} {' '.join(keywords)} {title}"
            scene = infer_scene_from_text(combined_text)
            logging.info(f"Visual context from step1_analyze: scene={scene}, keywords={keywords}")
        else:
            combined_text = f"{title} {subtitle}"
            scene = infer_scene_from_text(combined_text)

        template_config = select_template(scene, template_name)
        template_name = template_config["template"]

        # 自动设置配色（如果用户未自定义）
        if not variables.get("bg_color") or variables.get("bg_color") == "#FF6B6B":
            variables["bg_color"] = template_config["bg_color"]
        if not variables.get("accent_color") or variables.get("accent_color") == "#FFFFFF":
            variables["accent_color"] = template_config["accent_color"]

        logging.info(f"Smart template match: scene={scene}, template={template_name}, blank_area={template_config['blank_area']}")

    # ---------- AI 背景模式分支 ----------
    if image_mode == "ai_bg":
        env_config = load_env_config()
        if not env_config["api_key"]:
            ai_fallback_reason = "missing_api_key"
            logging.warning("Missing LLM_API_KEY, falling back to template mode")
            image_mode_used = "template"
        else:
            try:
                # 获取留白区域用于 prompt 构图
                visual_context = variables.get("visual_context", {})
                if visual_context:
                    keywords = visual_context.get("keywords", [])
                    topic_summary = visual_context.get("topic_summary", "")
                    combined_text = f"{topic_summary} {' '.join(keywords)} {title}"
                else:
                    combined_text = f"{title} {subtitle}"
                scene = infer_scene_from_text(combined_text)
                template_config = select_template(scene)
                blank_area = template_config["blank_area"]

                # 生成与模板构图匹配的 AI prompt
                ai_prompt = build_ai_prompt(title, subtitle, ai_prompt, blank_area)

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
