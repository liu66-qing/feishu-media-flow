"""
全模块偏好注入前后对比测试（真实 API 调用）
============================================
覆盖 4 个模块：content-generate-xhs / content-generate-douyin /
              content-generate-wechat / image-compose
每个模块跑 2 轮：无画像 → 有画像，所有产物输出到同一文件夹。

用法:
    cd 项目根目录
    python platform-preference-profiler/test/test_full_comparison.py
"""

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROFILES_DIR = PROJECT_ROOT / ".data" / "profiles"

# 统一产物输出目录
OUTPUT_DIR = PROJECT_ROOT / "platform-preference-profiler" / "test" / "results" / "full_comparison"

# 统一测试选题
TEST_TOPIC = "大学生如何高效利用碎片化时间"

# ===== 各模块输入 =====
XHS_INPUT = {
    "content_id": "CNT-CMP-XHS",
    "job_id": "JOB-CMP-XHS",
    "topic": TEST_TOPIC,
    "column": "校园成长",
    "materials": [
        "课间10分钟可以用来回顾上节课笔记要点",
        "排队打饭时刷单词APP效率很高",
        "通勤路上听播客比刷短视频更有价值",
        "午休前15分钟做冥想能提升下午专注力",
        "睡前10分钟写日记复盘一天收获"
    ],
    "brand": {"tone": "真诚、实用、有共鸣", "audience": "大学生、考研党"}
}

DOUYIN_INPUT = {
    "content_id": "CNT-CMP-DY",
    "job_id": "JOB-CMP-DY",
    "topic": TEST_TOPIC,
    "duration_target": 60,
    "style": "口播 + 图文卡片"
}

WECHAT_INPUT = {
    "content_id": "CNT-CMP-WX",
    "job_id": "JOB-CMP-WX",
    "topic": TEST_TOPIC,
    "column": "成长方法论",
    "materials": [
        "认知科学关于注意力残留的研究",
        "Cal Newport 的深度工作理论",
        "时间块管理法的实践经验"
    ],
    "reference_urls": [],
    "target_length": 1200
}

IMAGE_INPUT = {
    "content_id": "CNT-CMP-IMG",
    "job_id": "JOB-CMP-IMG",
    "template_name": "xhs-cover-03",
    "variables": {
        "title": "碎片时间管理",
        "subtitle": "大学生必看",
        "ai_prompt": "中国大学校园清晨，阳光透过梧桐树叶洒在石板路上，几位大学生背着书包走向教学楼，画面清新明亮，充满青春活力"
    },
    "image_mode": "ai_bg",
    "output_size": {"width": 1080, "height": 1350}
}

PLATFORMS = [
    {"name": "xhs",       "module": "content-generate-xhs",     "input": XHS_INPUT,     "profile": "xhs_profile.json",     "output_file": "content-generate-xhs.json"},
    {"name": "douyin",    "module": "content-generate-douyin",  "input": DOUYIN_INPUT,  "profile": "douyin_profile.json",  "output_file": "content-generate-douyin.json"},
    {"name": "wechat",    "module": "content-generate-wechat",  "input": WECHAT_INPUT,  "profile": "wechat_profile.json",  "output_file": "content-generate-wechat.json"},
    {"name": "image",     "module": "image-compose",            "input": IMAGE_INPUT,   "profile": "xhs_profile.json",     "output_file": "image-compose.json"},
]


def load_dotenv_manual():
    """手动加载 .env"""
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        print(f"[WARN] .env not found: {env_file}")
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())
    print("[INFO] .env loaded")


def setup_env():
    load_dotenv_manual()
    # 文本模块用 qwen-plus
    os.environ["LLM_MODEL"] = os.getenv("LLM_TEXT_MODEL", "qwen-plus")
    print(f"[INFO] LLM_MODEL = {os.environ['LLM_MODEL']}")
    print(f"[INFO] LLM_BASE_URL = {os.environ.get('LLM_BASE_URL', 'NOT SET')}")


def hide_profiles():
    for p in PLATFORMS:
        src = PROFILES_DIR / p["profile"]
        dst = PROFILES_DIR / (p["profile"] + ".bak")
        if src.exists() and not dst.exists():
            src.rename(dst)
    print("[INFO] Profiles hidden")


def restore_profiles():
    for p in PLATFORMS:
        src = PROFILES_DIR / (p["profile"] + ".bak")
        dst = PROFILES_DIR / p["profile"]
        if src.exists() and not dst.exists():
            src.rename(dst)
    print("[INFO] Profiles restored")


def run_module(platform_info: dict, job_dir: Path) -> dict:
    """运行模块，返回结果"""
    module_dir = PROJECT_ROOT / platform_info["module"]
    script = module_dir / "main.py"

    job_dir.mkdir(parents=True, exist_ok=True)
    input_path = job_dir / "input.json"
    input_path.write_text(json.dumps(platform_info["input"], ensure_ascii=False, indent=2), encoding="utf-8")

    cmd = [sys.executable, str(script), "--job-dir", str(job_dir)]
    print(f"  CMD: {' '.join(cmd[-3:])}")

    start = time.time()
    result = subprocess.run(
        cmd, capture_output=True, text=True,
        cwd=str(PROJECT_ROOT), env={**os.environ}, timeout=300,
    )
    elapsed = time.time() - start

    ret = {
        "platform": platform_info["name"],
        "module": platform_info["module"],
        "elapsed_seconds": round(elapsed, 1),
        "return_code": result.returncode,
        "stdout_tail": result.stdout[-300:] if result.stdout else "",
        "stderr_tail": result.stderr[-300:] if result.stderr else "",
        "output_file": None,
        "error_file": None,
        "output_data": None,
        "error_data": None,
    }

    # 收集输出
    output_file = job_dir / platform_info["output_file"]
    error_file = job_dir / "error.json"
    if output_file.exists():
        ret["output_file"] = str(output_file)
        ret["output_data"] = json.loads(output_file.read_text(encoding="utf-8"))
    if error_file.exists():
        ret["error_file"] = str(error_file)
        ret["error_data"] = json.loads(error_file.read_text(encoding="utf-8"))

    # 收集图片产物（image-compose）
    output_dir = job_dir / "output"
    if output_dir.exists():
        pngs = list(output_dir.glob("*.png"))
        ret["generated_images"] = [str(p) for p in pngs]
        ai_bg = job_dir / "ai_bg.png"
        if ai_bg.exists():
            ret["generated_images"].append(str(ai_bg))

    return ret


def clean_output_dir():
    """清理输出目录"""
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def extract_summary(result: dict, platform: str) -> dict:
    """提取可对比摘要"""
    data = result.get("output_data")
    if not data:
        err = result.get("error_data")
        return {"success": False, "error": err.get("error", "unknown") if err else "no output"}

    inner = data.get("data", data)

    if platform == "xhs":
        return {
            "success": True,
            "title": inner.get("selected_title", ""),
            "body_length": len(inner.get("body", "")),
            "hashtags": inner.get("hashtags", []),
            "cover_text": inner.get("cover_text", ""),
            "token_usage": sum(
                v.get("tokens", {}).get("total_tokens", 0)
                for v in inner.get("pipeline_log", {}).values()
            ),
        }
    elif platform == "douyin":
        return {
            "success": True,
            "title": inner.get("selected_title", ""),
            "body_length": len(inner.get("body", "")),
            "hashtags": inner.get("hashtags", []),
            "cards_count": len(inner.get("cards", [])),
            "token_usage": sum(
                v.get("tokens", {}).get("total_tokens", 0)
                for v in inner.get("pipeline_log", {}).values()
            ),
        }
    elif platform == "wechat":
        return {
            "success": True,
            "title": inner.get("selected_title", ""),
            "body_length": len(inner.get("body_md", "")),
            "sections": [s.get("heading", "") for s in inner.get("sections", [])],
            "llm_enabled": inner.get("llm_enabled", None),
        }
    elif platform == "image":
        return {
            "success": True,
            "template": inner.get("template_used", ""),
            "image_mode": inner.get("image_mode_used", ""),
            "image_path": inner.get("image_path", ""),
            "ai_prompt_used": inner.get("ai_prompt_used", ""),
            "generated_images": result.get("generated_images", []),
        }
    return {"success": True, "raw_keys": list(inner.keys())}


def main():
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    print("=" * 70)
    print("全模块偏好注入前后对比测试（真实 API）")
    print(f"时间: {datetime.now().isoformat()}")
    print(f"选题: {TEST_TOPIC}")
    print(f"模块: {', '.join(p['name'] for p in PLATFORMS)}")
    print("=" * 70)

    setup_env()
    clean_output_dir()

    all_results = {
        "timestamp": datetime.now().isoformat(),
        "topic": TEST_TOPIC,
        "model": os.environ.get("LLM_MODEL", "unknown"),
        "rounds": {},
    }

    # ===== 第一轮：无画像 =====
    print("\n" + "=" * 70)
    print("ROUND 1: 无画像")
    print("=" * 70)
    hide_profiles()

    round1 = {}
    for p in PLATFORMS:
        print(f"\n--- {p['name']} (无画像) ---")
        job_dir = OUTPUT_DIR / "round1_no_profile" / p["name"]
        try:
            r = run_module(p, job_dir)
            round1[p["name"]] = r
            status = "OK" if r["return_code"] == 0 and r["output_data"] else "FAIL"
            print(f"  => {status} ({r['elapsed_seconds']}s)")
            if r.get("error_data"):
                print(f"  => Error: {r['error_data'].get('error', '')}")
        except Exception as e:
            round1[p["name"]] = {"error": str(e), "return_code": -1, "elapsed_seconds": 0}
            print(f"  => EXCEPTION: {e}")

    # ===== 第二轮：有画像 =====
    print("\n" + "=" * 70)
    print("ROUND 2: 有画像")
    print("=" * 70)
    restore_profiles()

    round2 = {}
    for p in PLATFORMS:
        print(f"\n--- {p['name']} (有画像) ---")
        job_dir = OUTPUT_DIR / "round2_with_profile" / p["name"]
        try:
            r = run_module(p, job_dir)
            round2[p["name"]] = r
            status = "OK" if r["return_code"] == 0 and r["output_data"] else "FAIL"
            print(f"  => {status} ({r['elapsed_seconds']}s)")
            if r.get("error_data"):
                print(f"  => Error: {r['error_data'].get('error', '')}")
        except Exception as e:
            round2[p["name"]] = {"error": str(e), "return_code": -1, "elapsed_seconds": 0}
            print(f"  => EXCEPTION: {e}")

    # ===== 生成摘要对比 =====
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    comparison = {}
    for p in PLATFORMS:
        name = p["name"]
        s1 = extract_summary(round1.get(name, {}), name)
        s2 = extract_summary(round2.get(name, {}), name)
        comparison[name] = {"without_profile": s1, "with_profile": s2}

        print(f"\n[{name}]")
        print(f"  无画像: {json.dumps(s1, ensure_ascii=False)[:200]}")
        print(f"  有画像: {json.dumps(s2, ensure_ascii=False)[:200]}")

    all_results["rounds"] = {
        "round1_no_profile": {k: {kk: vv for kk, vv in v.items() if kk != "output_data"} for k, v in round1.items()},
        "round2_with_profile": {k: {kk: vv for kk, vv in v.items() if kk != "output_data"} for k, v in round2.items()},
    }
    all_results["comparison_summary"] = comparison

    # 保存总索引
    index_path = OUTPUT_DIR / "test_index.json"
    index_path.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n总索引: {index_path}")

    # 列出所有产物
    print("\n所有产物文件:")
    for f in sorted(OUTPUT_DIR.rglob("*")):
        if f.is_file():
            rel = f.relative_to(OUTPUT_DIR)
            size = f.stat().st_size
            print(f"  {rel}  ({size:,} bytes)")

    print("\nDone!")


if __name__ == "__main__":
    main()
