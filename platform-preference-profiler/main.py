"""Platform preference profiler - analyzes platform samples and generates V2 preference profiles."""

import argparse
import json
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


# Load .env from project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


SKILL_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = SKILL_DIR / "prompts"
OUTPUT_NAME = "platform-preference-profiler.json"

# UTC+8 timezone
_CST = timezone(timedelta(hours=8))

# Profile expiry threshold (days)
PROFILE_EXPIRY_DAYS = 7


class ProfilerError(Exception):
    pass


def now_iso() -> str:
    return datetime.now(_CST).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ProfilerError(f"missing input file: {path}")
    with path.open("r", encoding="utf-8-sig") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ProfilerError("input.json must be a JSON object")
    return data


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    if not path.exists():
        raise ProfilerError(f"missing prompt file: {path}")
    return path.read_text(encoding="utf-8")


def parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```json"):
        text = text.removeprefix("```json").removesuffix("```").strip()
    elif text.startswith("```"):
        text = text.removeprefix("```").removesuffix("```").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("LLM response must be a JSON object")
    return data


def build_client() -> tuple[OpenAI, str]:
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL")
    model = os.getenv("LLM_MODEL")
    
    # Use text model for analysis (override if image model is set)
    text_model = os.getenv("LLM_TEXT_MODEL")
    if text_model:
        model = text_model
    elif model and "image" in model.lower():
        # Default to qwen-plus if current model is an image model
        model = "qwen-plus"
    
    missing = [
        name
        for name, value in {
            "LLM_API_KEY": api_key,
            "LLM_BASE_URL": base_url,
        }.items()
        if not value
    ]
    if missing:
        raise ProfilerError(f"missing environment variable(s): {', '.join(missing)}")
    return OpenAI(api_key=api_key, base_url=base_url), str(model) if model else "qwen-plus"


def load_samples(samples_dir: Path, platform: str) -> list[dict[str, Any]]:
    """Load all sample files for a given platform."""
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


def calculate_confidence(samples: list[dict[str, Any]]) -> float:
    """Calculate confidence score based on sample count and metrics consistency."""
    if not samples:
        return 0.0
    
    count = len(samples)
    
    # Base confidence from sample count
    if count < 3:
        base_conf = 0.3 + (count / 3) * 0.2  # 0.3-0.5
    elif count <= 5:
        base_conf = 0.5 + ((count - 3) / 2) * 0.2  # 0.5-0.7
    else:
        base_conf = 0.7 + min((count - 5) / 10, 0.2)  # 0.7-0.9
    
    # Adjust based on metrics consistency
    metrics_list = [s.get("metrics", {}) for s in samples if s.get("metrics")]
    if metrics_list:
        likes = [m.get("likes", 0) for m in metrics_list]
        if likes and max(likes) > 0:
            variance = sum((x - sum(likes)/len(likes))**2 for x in likes) / len(likes)
            cv = (variance ** 0.5) / (sum(likes)/len(likes)) if sum(likes)/len(likes) > 0 else 0
            # Lower CV = more consistent = higher confidence
            consistency_bonus = max(0, 0.1 - cv * 0.05)
            base_conf = min(0.95, base_conf + consistency_bonus)
    
    return round(base_conf, 2)


def analyze_platform(
    client: OpenAI,
    model: str,
    platform: str,
    samples: list[dict[str, Any]],
) -> dict[str, Any]:
    """Analyze samples for a single platform and return V2 profile."""
    system_prompt = read_prompt("analyze_samples.md")
    
    # Build user message with all samples
    samples_text = json.dumps(samples, ensure_ascii=False, indent=2)
    user_message = f"{system_prompt}\n\n请分析以下{len(samples)}条{platform}平台的高表现内容样本，生成该平台的内容偏好画像（V2 Schema）：\n\n{samples_text}"
    
    started = time.perf_counter()
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    
    for attempt in range(2):
        # Some APIs require content to be a list of content parts
        messages = [
            {"role": "user", "content": [{"type": "text", "text": user_message}]},
        ]
        
        if attempt == 1:
            messages.append(
                {
                    "role": "user",
                    "content": "上一轮没有得到可解析的JSON。请只返回一个JSON对象，不要Markdown代码块，不要解释文字。",
                }
            )
        
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=4096,
        )
        
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens or 0,
                "completion_tokens": response.usage.completion_tokens or 0,
                "total_tokens": response.usage.total_tokens or 0,
            }
        
        raw = response.choices[0].message.content or ""
        
        try:
            profile = parse_json_object(raw)
            # Add metadata
            profile["pf"] = platform
            profile["gen_at"] = now_iso()
            profile["v"] = "1.0"
            profile["s_cnt"] = len(samples)
            profile["s_ids"] = [s.get("sample_id", f"{platform.upper()}-{i+1}") for i, s in enumerate(samples)]
            profile["conf"] = calculate_confidence(samples)
            
            return profile
        except Exception as e:
            if attempt == 1:
                raise ProfilerError(f"Failed to parse LLM response for {platform}: {e}; raw={raw[:500]}")
    
    raise ProfilerError(f"Failed to analyze {platform} after retries")


def is_profile_expired(profile_path: Path) -> bool:
    """Check if a profile file exists and is not expired."""
    if not profile_path.exists():
        return True
    
    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        gen_at = profile.get("gen_at", "")
        if not gen_at:
            return True
        
        gen_time = datetime.fromisoformat(gen_at)
        if gen_time.tzinfo is None:
            gen_time = gen_time.replace(tzinfo=_CST)
        
        age_days = (datetime.now(_CST) - gen_time).days
        return age_days >= PROFILE_EXPIRY_DAYS
    except Exception:
        return True


def load_profile(platform: str, profiles_dir: Path) -> dict[str, Any] | None:
    """Load a platform preference profile. Returns None if not found or expired."""
    profile_path = profiles_dir / f"{platform}_profile.json"
    
    if not profile_path.exists():
        return None
    
    if is_profile_expired(profile_path):
        return None
    
    try:
        return json.loads(profile_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def run(job_dir: Path, force: bool = False, incremental: bool = False) -> int:
    error_path = job_dir / "error.json"
    try:
        job = read_json(job_dir / "input.json")
        
        # Project root is 3 levels up from job_dir (job_dir -> fixtures -> test -> platform-preference-profiler -> project_root)
        project_root = job_dir.parent.parent.parent.parent
        
        platforms = job.get("platforms", ["xhs", "douyin", "wechat"])
        samples_dir = Path(job.get("samples_dir", ".data/samples")).resolve()
        output_dir = Path(job.get("output_dir", ".data/profiles")).resolve()
        
        client, model = build_client()
        
        profiles_summary = []
        pipeline_log = {}
        
        for platform in platforms:
            print(f"Analyzing platform: {platform}")
            
            profile_path = output_dir / f"{platform}_profile.json"
            
            # Check if we need to regenerate
            if not force and not incremental and not is_profile_expired(profile_path):
                print(f"  Profile exists and is fresh, skipping")
                profile = json.loads(profile_path.read_text(encoding="utf-8"))
            else:
                # Load samples
                samples = load_samples(samples_dir, platform)
                if not samples:
                    print(f"  Warning: no samples found for {platform}")
                    continue
                
                print(f"  Loaded {len(samples)} samples")
                
                # Analyze
                started = time.perf_counter()
                profile = analyze_platform(client, model, platform, samples)
                duration_ms = int((time.perf_counter() - started) * 1000)
                
                # Write profile
                write_json(profile_path, profile)
                print(f"  Profile saved to {profile_path}")
                
                pipeline_log[platform] = {
                    "duration_ms": duration_ms,
                    "sample_count": len(samples),
                    "status": "ok",
                }
            
            profiles_summary.append({
                "pf": platform,
                "path": str(profile_path.relative_to(project_root)) if profile_path.exists() else str(profile_path),
                "s_cnt": profile.get("s_cnt", 0),
                "conf": profile.get("conf", 0),
                "v": profile.get("v", "1.0"),
            })
        
        # Write index file
        index = {
            "cid": job.get("content_id", "PROF-unknown"),
            "jid": job.get("job_id", "JOB-unknown"),
            "sample_root": str(samples_dir.relative_to(project_root)) if samples_dir.exists() else str(samples_dir),
            "profile_root": str(output_dir.relative_to(project_root)) if output_dir.exists() else str(output_dir),
            "gen_at": now_iso(),
            "profiles": profiles_summary,
        }
        
        write_json(job_dir / OUTPUT_NAME, index)
        print(f"\nIndex file saved to {job_dir / OUTPUT_NAME}")
        print(f"Analyzed {len(profiles_summary)} platforms")
        
        return 0
        
    except Exception as exc:
        write_json(
            error_path,
            {
                "status": "error",
                "generated_at": now_iso(),
                "error": str(exc),
            },
        )
        print(f"Error: {exc}")
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze platform samples and generate preference profiles (V2 Schema).")
    parser.add_argument("--job-dir", required=True, help="Directory containing input.json")
    parser.add_argument("--force", action="store_true", help="Force full re-analysis of all platforms")
    parser.add_argument("--incremental", action="store_true", help="Only analyze new samples and merge")
    args = parser.parse_args()
    
    raise SystemExit(run(Path(args.job_dir).resolve(), force=args.force, incremental=args.incremental))


if __name__ == "__main__":
    main()
