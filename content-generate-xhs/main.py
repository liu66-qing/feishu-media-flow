import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).parent.parent / ".env")


SKILL_NAME = "content-generate-xhs"


def get_llm_client():
    return OpenAI(
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    )


def call_llm(prompt: str, system: str = "", model: str = None) -> str:
    client = get_llm_client()
    model = model or os.getenv("LLM_MODEL", "gpt-5.4-mini")
    
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"}
    )
    return resp.choices[0].message.content


def load_prompt(filepath: Path) -> str:
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def setup_logging(job_dir: Path):
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
    input_path = job_dir / "input.json"
    with open(input_path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_output(job_dir: Path, skill_name: str, data: dict):
    output_path = job_dir / f"{skill_name}.json"
    result = {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "content_id": data.get("content_id", ""),
        "data": data
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


def write_error(job_dir: Path, error_msg: str):
    error_path = job_dir / "error.json"
    error_data = {
        "status": "error",
        "timestamp": datetime.now().isoformat(),
        "error": error_msg
    }
    with open(error_path, "w", encoding="utf-8") as f:
        json.dump(error_data, f, ensure_ascii=False, indent=2)


def generate_xhs_content(input_data: dict, skill_dir: Path) -> dict:
    system_prompt = load_prompt(skill_dir / "prompts" / "system.md")
    user_template = load_prompt(skill_dir / "prompts" / "user_template.md")
    
    topic = input_data.get("topic", "")
    column = input_data.get("column", "")
    materials = input_data.get("materials", [])
    brand = input_data.get("brand", {})
    
    user_prompt = user_template.format(
        topic=topic,
        column=column,
        materials="\n".join(f"- {m}" for m in materials),
        tone=brand.get("tone", ""),
        audience=brand.get("audience", "")
    )
    
    def _fix_double_escaped_newlines(s: str) -> str:
        literal_backslash_n = "\\n"
        if literal_backslash_n in s:
            actual_newline_count = s.count("\n")
            literal_n_count = s.count(literal_backslash_n)
            if literal_n_count > actual_newline_count:
                s = s.replace(literal_backslash_n, "\n")
        return s

    def _parse_llm_response(text: str) -> dict:
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.startswith("```")]
            text = "\n".join(lines).strip()
        parsed = json.loads(text)
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict) and ("title_options" in item or "body" in item):
                    parsed = item
                    break
            if isinstance(parsed, list):
                parsed = parsed[0] if parsed else {}
        if not isinstance(parsed, dict):
            raise ValueError(f"LLM 返回格式错误，期望 JSON 对象，实际为: {type(parsed)}")
        if "body" in parsed and isinstance(parsed["body"], str):
            parsed["body"] = _fix_double_escaped_newlines(parsed["body"])
        return parsed

    logging.info("Calling LLM to generate content...")
    max_retries = 2
    for attempt in range(max_retries + 1):
        response = call_llm(user_prompt, system_prompt)
        try:
            result = _parse_llm_response(response)
            break
        except (json.JSONDecodeError, ValueError, IndexError) as e:
            if attempt < max_retries:
                logging.warning(f"LLM response parse failed (attempt {attempt+1}): {e}, retrying...")
                continue
            logging.error(f"LLM response parse failed after {max_retries+1} attempts: {e}")
            logging.error(f"Raw response: {response[:2000]}")
            raise ValueError(f"LLM 返回格式错误: {e}")
    
    result["content_id"] = input_data.get("content_id", "")
    return result


def main():
    parser = argparse.ArgumentParser(description="Skill: content-generate-xhs")
    parser.add_argument("--job-dir", required=True, help="Job directory path")
    args = parser.parse_args()

    job_dir = Path(args.job_dir)
    skill_dir = Path(__file__).parent
    
    setup_logging(job_dir)
    logging.info(f"Starting skill, job_dir: {job_dir}")

    try:
        input_data = load_input(job_dir)
        
        required_fields = ["content_id", "job_id", "topic"]
        missing_fields = [f for f in required_fields if f not in input_data]
        if missing_fields:
            raise ValueError(f"缺少必填字段: {', '.join(missing_fields)}")
        
        result = generate_xhs_content(input_data, skill_dir)
        write_output(job_dir, SKILL_NAME, result)
        logging.info("Skill completed successfully")
        sys.exit(0)
    except Exception as e:
        logging.error(f"Skill failed: {e}", exc_info=True)
        write_error(job_dir, str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()