import argparse
import json
import os
from datetime import datetime
from pathlib import Path

from openai import OpenAI

SKILL_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = SKILL_DIR / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "system.md"
USER_TEMPLATE_PATH = PROMPTS_DIR / "user_template.md"

client = OpenAI(
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
)


def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def call_llm(prompt, system="", model=None):
    model = model or os.getenv("LLM_MODEL", "gpt-5.4-mini")

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=4096
        )
        content = resp.choices[0].message.content or ""
        if content.strip():
            return content
    except Exception:
        pass

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ],
        max_tokens=4096
    )
    return resp.choices[0].message.content or ""


def read_text(path):
    with path.open("r", encoding="utf-8") as f:
        return f.read()


def render_template(template, values):
    result = template
    for key, value in values.items():
        result = result.replace("{{" + key + "}}", str(value))
    return result


def parse_llm_json(raw):
    text = raw.strip()

    if text.startswith("```json"):
        text = text.removeprefix("```json").removesuffix("```").strip()
    elif text.startswith("```"):
        text = text.removeprefix("```").removesuffix("```").strip()

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]

    return json.loads(text)


def build_scenes(topic, duration_target):
    scenes = [
        {
            "index": 1,
            "duration": 7,
            "voiceover": f"你是不是也遇到过这个问题：{topic}，听起来简单，真正做起来却很乱？",
            "subtitle": "听起来简单，做起来很乱？",
            "visual": "开场对比画面：一边是忙乱现场，一边是清晰准备清单",
            "asset_hint": "准备忙乱现场图、清单图或对比卡片"
        },
        {
            "index": 2,
            "duration": 7,
            "voiceover": "很多人一上来就想做大动作，但其实先把流程拆清楚更重要。",
            "subtitle": "先别急，先拆流程",
            "visual": "画面出现流程拆解卡片",
            "asset_hint": "流程图、便签纸、白板画面"
        },
        {
            "index": 3,
            "duration": 8,
            "voiceover": "第一步，先确定目标。你到底想让对方知道什么、记住什么、下一步做什么？",
            "subtitle": "第一步：确定目标",
            "visual": "三个问题依次弹出：知道什么、记住什么、做什么",
            "asset_hint": "三问题文字卡片"
        },
        {
            "index": 4,
            "duration": 7,
            "voiceover": "如果目标不清楚，后面的文案、画面和动作都会跟着跑偏。",
            "subtitle": "目标不清楚，后面都会偏",
            "visual": "箭头偏离路线的动画或示意图",
            "asset_hint": "路线箭头、偏航示意"
        },
        {
            "index": 5,
            "duration": 8,
            "voiceover": "第二步，把信息分层。最重要的信息放前面，补充说明放后面。",
            "subtitle": "第二步：信息分层",
            "visual": "信息分成主标题、重点、补充说明三层",
            "asset_hint": "分层信息卡片"
        },
        {
            "index": 6,
            "duration": 7,
            "voiceover": "不要一口气塞太多内容。短视频里，观众每一秒都在判断要不要继续看。",
            "subtitle": "别一口气塞太多",
            "visual": "密密麻麻文字与清爽卡片对比",
            "asset_hint": "文字拥挤画面、简洁卡片"
        },
        {
            "index": 7,
            "duration": 8,
            "voiceover": "第三步，设计一个能马上执行的小动作，比如收藏、评论、试一试。",
            "subtitle": "第三步：给一个小动作",
            "visual": "收藏、评论、行动按钮依次出现",
            "asset_hint": "收藏图标、评论气泡、行动按钮"
        },
        {
            "index": 8,
            "duration": 7,
            "voiceover": "这个动作越具体，观众越容易真的跟着做。",
            "subtitle": "动作越具体，越容易执行",
            "visual": "抽象建议变成具体待办清单",
            "asset_hint": "待办清单、勾选动画"
        },
        {
            "index": 9,
            "duration": 8,
            "voiceover": "总结一下：先定目标，再分层信息，最后给出一个小动作。",
            "subtitle": "目标、分层、动作",
            "visual": "三步总结卡片",
            "asset_hint": "三步总结图"
        },
        {
            "index": 10,
            "duration": 6,
            "voiceover": "下次再做类似内容，可以直接按这个顺序检查一遍。",
            "subtitle": "下次直接按这个顺序检查",
            "visual": "结尾清单定格",
            "asset_hint": "结尾清单卡片"
        }
    ]

    total = sum(scene["duration"] for scene in scenes)
    diff = duration_target - total

    if diff != 0:
        for scene in reversed(scenes):
            if diff > 0 and scene["duration"] < 8:
                scene["duration"] += 1
                diff -= 1
            elif diff < 0 and scene["duration"] > 5:
                scene["duration"] -= 1
                diff += 1

            if diff == 0:
                break

    return scenes

def generate_douyin_script_with_llm(input_data):
    if not os.getenv("LLM_API_KEY"):
        raise RuntimeError("LLM_API_KEY is not set")

    system = read_text(SYSTEM_PROMPT_PATH)
    template = read_text(USER_TEMPLATE_PATH)

    prompt = render_template(template, {
        "topic": input_data.get("topic", ""),
        "duration_target": input_data.get("duration_target", 75),
        "style": input_data.get("style", "口播 + 图文卡片")
    })

    raw = call_llm(prompt, system=system)

    if not raw.strip():
        raise ValueError("LLM returned empty content")

    data = parse_llm_json(raw)

    required_fields = [
        "title",
        "duration",
        "style",
        "hook",
        "scenes",
        "caption",
        "hashtags",
        "cover_text"
    ]

    for field in required_fields:
        if field not in data:
            raise ValueError(f"LLM output missing field: {field}")

    data["llm_enabled"] = True
    data["llm_error"] = ""

    return data

def generate_douyin_script(input_data):
    topic = input_data.get("topic", "")
    duration_target = int(input_data.get("duration_target", 75))
    style = input_data.get("style", "口播 + 图文卡片")

    scenes = build_scenes(topic, duration_target)
    duration = sum(scene["duration"] for scene in scenes)

    return {
        "title": topic,
        "duration": duration,
        "style": style,
        "hook": scenes[0]["voiceover"],
        "scenes": scenes,
        "caption": f"{topic}，可以先从目标、信息分层和行动设计三个角度检查。",
        "hashtags": ["#短视频脚本", "#内容运营", "#实用方法"],
        "cover_text": "3步讲清楚"
    }


def run(job_dir):
    job_dir = Path(job_dir)
    input_path = job_dir / "input.json"
    output_path = job_dir / "content_generate_douyin.json"
    logs_path = job_dir / "logs.txt"
    error_path = job_dir / "error.json"

    try:
        input_data = load_json(input_path)
        try:
            data = generate_douyin_script_with_llm(input_data)
        except Exception as llm_error:
            data = generate_douyin_script(input_data)
            data["llm_enabled"] = False
            data["llm_error"] = str(llm_error)

        result = {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "content_id": input_data.get("content_id", ""),
            "data": data
        }

        write_json(output_path, result)

        logs_path.write_text(
            f"[success] content-generate-douyin finished. duration={data['duration']}\n",
            encoding="utf-8"
        )

        return 0

    except Exception as e:
        error = {
            "status": "failed",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }
        write_json(error_path, error)
        return 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-dir", required=True, help="Path to job directory containing input.json")
    args = parser.parse_args()

    exit_code = run(args.job_dir)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()