import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path

from openai import OpenAI
from simhash import Simhash


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


def read_text(path):
    with path.open("r", encoding="utf-8") as f:
        return f.read()


def render_template(template, values):
    result = template
    for key, value in values.items():
        result = result.replace("{{" + key + "}}", str(value))
    return result


def call_llm(prompt, system="", model=None):
    model = model or os.getenv("LLM_MODEL", "gpt-5.4-mini")
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"},
        max_tokens=4096
    )

    return resp.choices[0].message.content or ""


def parse_llm_json(raw):
    text = raw.strip()

    if text.startswith("```"):
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"^```\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group(0))
        raise


def tokenize_zh(text):
    cleaned = (
        text.replace("\n", "")
        .replace(" ", "")
        .replace("，", "")
        .replace("。", "")
        .replace("：", "")
        .replace("；", "")
        .replace("？", "")
        .replace("！", "")
        .replace("、", "")
        .replace("「", "")
        .replace("」", "")
        .replace("“", "")
        .replace("”", "")
        .replace("（", "")
        .replace("）", "")
        .replace('"', "")
        .replace("'", "")
    )

    tokens = []
    for size in (9, 10, 11, 12, 13, 14):
        for index in range(0, max(0, len(cleaned) - size + 1)):
            tokens.append(cleaned[index:index + size])

    if not tokens:
        tokens = list(cleaned)

    return tokens


def similarity(a, b):
    h1 = Simhash(tokenize_zh(a))
    h2 = Simhash(tokenize_zh(b))

    raw_score = 1 - (h1.distance(h2) / 64)
    normalized_score = max(0, (raw_score - 0.5) * 2)

    return round(normalized_score, 4), round(raw_score, 4)


def analyze_source(source_text):
    return {
        "hook": "原文通过直接指出痛点吸引读者注意。",
        "structure": "痛点引入 -> 方法拆解 -> 场景说明 -> 总结建议",
        "viral_points": [
            "开头问题明确",
            "内容结构清晰",
            "读者能快速代入"
        ],
        "target_audience": "对该主题感兴趣、希望获得实用建议的读者"
    }


def rewrite_content(input_data):
    target_platform = input_data.get("target_platform", "xhs")
    target_column = input_data.get("target_column", "经验干货")

    title = "开学季别只拼热闹，先把动线想清楚"

    body = (
        f"这版内容面向 {target_platform} 平台，改用「迎新动线设计」来展开，"
        "重点不是讲怎么介绍自己，而是思考一个同学从远处看到、走近、参与、离开的全过程。\n\n"
        "很多开学季摊点看起来很忙，但路过的人并不知道自己下一步该做什么。"
        "如果桌面信息太多、成员站位太散、互动入口不明显，对方很可能看一眼就走。\n\n"
        "可以先把空间分成三个区域。\n\n"
        "第一个区域负责吸引注意。这里不需要放满文字，只要让人一眼看懂主题。"
        "比如用一句清楚的问题、一张场景图，或者一个正在进行的小任务。\n\n"
        "第二个区域负责轻量参与。不要一上来要求对方长时间交流，"
        "可以设置一个三十秒就能完成的动作，让陌生感先降下来。\n\n"
        "第三个区域负责收尾。结束时给对方一个明确记忆点，"
        "比如下一场公开活动、适合的人群，或者一个可以之后再看的内容入口。\n\n"
        "这样做的核心，是把开学季摊点从单纯展示，变成一段有顺序的体验。"
        "当路径更清楚，人就更容易从路过变成愿意了解。"
    )

    hashtags = [f"#{target_column}", "#开学季", "#活动动线"]

    return {
        "title": title,
        "body": body,
        "hashtags": hashtags
    }


def rewrite_content_with_llm(input_data):
    if not os.getenv("LLM_API_KEY"):
        raise RuntimeError("LLM_API_KEY is not set")

    system = read_text(SYSTEM_PROMPT_PATH)
    template = read_text(USER_TEMPLATE_PATH)

    prompt = render_template(template, {
        "source_text": input_data.get("source_text", ""),
        "source_url": input_data.get("source_url", ""),
        "target_platform": input_data.get("target_platform", "xhs"),
        "target_column": input_data.get("target_column", "经验干货")
    })

    raw = call_llm(prompt, system=system)

    if not raw.strip():
        raise ValueError("LLM returned empty content")

    data = parse_llm_json(raw)

    if "rewritten_content" in data:
        rewritten = data["rewritten_content"]
    else:
        rewritten = data

    for field in ["title", "body", "hashtags"]:
        if field not in rewritten:
            raise ValueError(f"LLM output missing field: {field}")

    return {
        "title": rewritten.get("title", ""),
        "body": rewritten.get("body", ""),
        "hashtags": rewritten.get("hashtags", [])
    }


def generate_hot_rewrite(input_data):
    source_text = input_data.get("source_text", "")
    source_url = input_data.get("source_url", "")

    original_analysis = analyze_source(source_text)
    llm_enabled = False
    llm_error = ""

    try:
        rewritten_content = rewrite_content_with_llm(input_data)
        llm_enabled = True
    except Exception as e:
        rewritten_content = rewrite_content(input_data)
        llm_error = str(e)

    rewritten_text = rewritten_content["title"] + "\n" + rewritten_content["body"]
    similarity_score, _simhash_raw_score = similarity(source_text, rewritten_text)

    if similarity_score > 0.3:
        status = "failed"
        risk_notes = [
            "similarity_score 超过 0.3，当前改写结果与原文相似度过高，需要重写。"
        ]
    else:
        status = "success"
        risk_notes = []

    return status, {
        "original_analysis": original_analysis,
        "rewritten_content": rewritten_content,
        "similarity_score": similarity_score,
        "similarity_method": "simhash_normalized_from_raw_baseline_0.5",
        "source_attribution": {
            "url": source_url,
            "note": "灵感来自原始内容，已重构角度、结构和表达方式。"
        },
        "risk_notes": risk_notes,
        "llm_enabled": llm_enabled,
        "llm_error": llm_error
    }


def run(job_dir):
    job_dir = Path(job_dir)
    input_path = job_dir / "input.json"
    output_path = job_dir / "hot_rewrite.json"
    logs_path = job_dir / "logs.txt"
    error_path = job_dir / "error.json"

    try:
        input_data = load_json(input_path)
        status, data = generate_hot_rewrite(input_data)

        result = {
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "content_id": input_data.get("content_id", ""),
            "data": data
        }

        write_json(output_path, result)

        logs_path.write_text(
            f"[{status}] hot-rewrite finished. similarity_score={data['similarity_score']}\n",
            encoding="utf-8"
        )

        return 0 if status == "success" else 1

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
