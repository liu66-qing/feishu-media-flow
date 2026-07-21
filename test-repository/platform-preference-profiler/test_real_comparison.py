"""
真实 API 偏好注入前后对比测试
==============================
用同一个选题，分别调用 XHS / 抖音 / 微信公众号内容生成模块，
对比「无画像」和「有画像」时的真实输出差异。

用法:
    cd 项目根目录
    python platform-preference-profiler/test/test_real_comparison.py
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
TEST_RESULTS_DIR = PROJECT_ROOT / "platform-preference-profiler" / "test" / "results" / "real_comparison"

# 统一测试选题
TEST_TOPIC = "大学生如何高效利用碎片化时间"

# 各模块的输入数据
XHS_INPUT = {
    "content_id": "CNT-COMPARE-XHS",
    "job_id": "JOB-COMPARE-XHS",
    "topic": TEST_TOPIC,
    "column": "校园成长",
    "materials": [
        "课间10分钟可以用来回顾上节课笔记要点",
        "排队打饭时刷单词APP效率很高",
        "通勤路上听播客比刷短视频更有价值",
        "午休前15分钟做冥想能提升下午专注力",
        "睡前10分钟写日记复盘一天收获"
    ],
    "brand": {
        "tone": "真诚、实用、有共鸣",
        "audience": "大学生、考研党"
    }
}

DOUYIN_INPUT = {
    "content_id": "CNT-COMPARE-DY",
    "job_id": "JOB-COMPARE-DY",
    "topic": TEST_TOPIC,
    "duration_target": 60,
    "style": "口播 + 图文卡片"
}

WECHAT_INPUT = {
    "content_id": "CNT-COMPARE-WX",
    "job_id": "JOB-COMPARE-WX",
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

PLATFORMS = [
    {"name": "xhs", "module": "content-generate-xhs", "input": XHS_INPUT, "profile": "xhs_profile.json"},
    {"name": "douyin", "module": "content-generate-douyin", "input": DOUYIN_INPUT, "profile": "douyin_profile.json"},
    {"name": "wechat", "module": "content-generate-wechat", "input": WECHAT_INPUT, "profile": "wechat_profile.json"},
]


def load_dotenv_manual():
    """手动加载 .env 文件到 os.environ"""
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        print(f"[WARN] .env 文件不存在: {env_file}")
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())
    print("[INFO] 已加载 .env 环境变量")


def setup_env():
    """设置环境变量，使用文本模型"""
    load_dotenv_manual()
    os.environ["LLM_MODEL"] = os.getenv("LLM_TEXT_MODEL", "qwen-plus")
    print(f"[INFO] 使用文本模型: {os.environ['LLM_MODEL']}")
    print(f"[INFO] API Base URL: {os.environ.get('LLM_BASE_URL', 'NOT SET')}")


def hide_profiles():
    """隐藏所有画像文件（重命名为 .bak）"""
    for p in PLATFORMS:
        src = PROFILES_DIR / p["profile"]
        dst = PROFILES_DIR / (p["profile"] + ".bak")
        if src.exists() and not dst.exists():
            src.rename(dst)
            print(f"[INFO] 隐藏画像: {src.name} -> {dst.name}")


def restore_profiles():
    """恢复所有画像文件"""
    for p in PLATFORMS:
        src = PROFILES_DIR / (p["profile"] + ".bak")
        dst = PROFILES_DIR / p["profile"]
        if src.exists() and not dst.exists():
            src.rename(dst)
            print(f"[INFO] 恢复画像: {src.name} -> {dst.name}")


def run_module(platform_info: dict, job_dir: Path) -> dict:
    """运行一个内容生成模块，返回结果"""
    module_dir = PROJECT_ROOT / platform_info["module"]
    script = module_dir / "main.py"

    # 写入 input.json
    job_dir.mkdir(parents=True, exist_ok=True)
    input_path = job_dir / "input.json"
    input_path.write_text(json.dumps(platform_info["input"], ensure_ascii=False, indent=2), encoding="utf-8")

    # 运行模块
    cmd = [sys.executable, str(script), "--job-dir", str(job_dir)]
    print(f"  命令: {' '.join(cmd)}")

    start = time.time()
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env={**os.environ},
        timeout=300,
    )
    elapsed = time.time() - start

    ret = {
        "platform": platform_info["name"],
        "elapsed_seconds": round(elapsed, 1),
        "return_code": result.returncode,
        "stdout": result.stdout[-500:] if result.stdout else "",
        "stderr": result.stderr[-500:] if result.stderr else "",
        "output": None,
        "error": None,
    }

    # 读取输出
    output_file = job_dir / f"{platform_info['module']}.json"
    error_file = job_dir / "error.json"

    if output_file.exists():
        ret["output"] = json.loads(output_file.read_text(encoding="utf-8"))
    if error_file.exists():
        ret["error"] = json.loads(error_file.read_text(encoding="utf-8"))

    return ret


def extract_comparable_fields(output: dict, platform: str) -> dict:
    """提取可对比的字段"""
    if not output:
        return {}

    data = output.get("data", output)  # wechat wraps in "data"

    if platform == "xhs":
        return {
            "selected_title": data.get("selected_title", ""),
            "title_options": data.get("title_options", []),
            "body": data.get("body", ""),
            "body_length": len(data.get("body", "")),
            "hashtags": data.get("hashtags", []),
            "cover_text": data.get("cover_text", ""),
        }
    elif platform == "douyin":
        return {
            "selected_title": data.get("selected_title", ""),
            "title_options": data.get("title_options", []),
            "body": data.get("body", ""),
            "body_length": len(data.get("body", "")),
            "hashtags": data.get("hashtags", []),
            "cover_lines": data.get("cover_lines", []),
            "cards_count": len(data.get("cards", [])),
        }
    elif platform == "wechat":
        return {
            "selected_title": data.get("selected_title", data.get("title_options", [""])[0] if data.get("title_options") else ""),
            "title_options": data.get("title_options", []),
            "body_md": data.get("body_md", ""),
            "body_length": len(data.get("body_md", "")),
            "sections": [s.get("heading", "") for s in data.get("sections", [])],
            "summary": data.get("summary", ""),
        }
    return {}


def generate_diff_report(platform: str, without: dict, with_: dict) -> dict:
    """生成单个平台的对比报告"""
    fields_without = extract_comparable_fields(without.get("output"), platform) if without.get("output") else {}
    fields_with = extract_comparable_fields(with_.get("output"), platform) if with_.get("output") else {}

    diff = {
        "platform": platform,
        "without_profile": {
            "success": without.get("return_code") == 0,
            "elapsed": without.get("elapsed_seconds"),
            "fields": fields_without,
        },
        "with_profile": {
            "success": with_.get("return_code") == 0,
            "elapsed": with_.get("elapsed_seconds"),
            "fields": fields_with,
        },
        "changes": {},
    }

    if fields_without and fields_with:
        # 标题对比
        t1 = fields_without.get("selected_title", "")
        t2 = fields_with.get("selected_title", "")
        diff["changes"]["title_changed"] = t1 != t2
        diff["changes"]["title_without"] = t1
        diff["changes"]["title_with"] = t2

        # 正文长度对比
        len1 = fields_without.get("body_length", 0)
        len2 = fields_with.get("body_length", 0)
        diff["changes"]["body_length_diff"] = len2 - len1
        diff["changes"]["body_length_without"] = len1
        diff["changes"]["body_length_with"] = len2

        # Hashtags 对比
        tags1 = fields_without.get("hashtags", [])
        tags2 = fields_with.get("hashtags", [])
        diff["changes"]["hashtags_without"] = tags1
        diff["changes"]["hashtags_with"] = tags2
        diff["changes"]["hashtags_changed"] = tags1 != tags2

        # 正文内容对比（前100字）
        body1 = fields_without.get("body", fields_without.get("body_md", ""))
        body2 = fields_with.get("body", fields_with.get("body_md", ""))
        diff["changes"]["body_preview_without"] = body1[:200] + "..." if len(body1) > 200 else body1
        diff["changes"]["body_preview_with"] = body2[:200] + "..." if len(body2) > 200 else body2

    return diff


def main():
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    print("=" * 70)
    print("真实 API 偏好注入前后对比测试")
    print(f"测试时间: {datetime.now().isoformat()}")
    print(f"测试选题: {TEST_TOPIC}")
    print("=" * 70)

    setup_env()
    TEST_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    all_results = {"timestamp": datetime.now().isoformat(), "topic": TEST_TOPIC, "platforms": {}}

    # ===== 第一轮：无画像 =====
    print("\n" + "=" * 70)
    print("第一轮：无画像（隐藏 profile 文件）")
    print("=" * 70)
    hide_profiles()

    round1_results = {}
    for p in PLATFORMS:
        print(f"\n--- 运行 {p['name']} (无画像) ---")
        job_dir = TEST_RESULTS_DIR / "round1_no_profile" / p["name"]
        try:
            result = run_module(p, job_dir)
            round1_results[p["name"]] = result
            status = "SUCCESS" if result["return_code"] == 0 else "FAILED"
            print(f"  结果: {status} ({result['elapsed_seconds']}s)")
            if result.get("error"):
                print(f"  错误: {result['error'].get('error', 'unknown')}")
        except Exception as e:
            round1_results[p["name"]] = {"error": str(e), "return_code": -1}
            print(f"  异常: {e}")

    # ===== 第二轮：有画像 =====
    print("\n" + "=" * 70)
    print("第二轮：有画像（恢复 profile 文件）")
    print("=" * 70)
    restore_profiles()

    round2_results = {}
    for p in PLATFORMS:
        print(f"\n--- 运行 {p['name']} (有画像) ---")
        job_dir = TEST_RESULTS_DIR / "round2_with_profile" / p["name"]
        try:
            result = run_module(p, job_dir)
            round2_results[p["name"]] = result
            status = "SUCCESS" if result["return_code"] == 0 else "FAILED"
            print(f"  结果: {status} ({result['elapsed_seconds']}s)")
            if result.get("error"):
                print(f"  错误: {result['error'].get('error', 'unknown')}")
        except Exception as e:
            round2_results[p["name"]] = {"error": str(e), "return_code": -1}
            print(f"  异常: {e}")

    # ===== 生成对比报告 =====
    print("\n" + "=" * 70)
    print("生成对比报告")
    print("=" * 70)

    diff_reports = []
    for p in PLATFORMS:
        name = p["name"]
        r1 = round1_results.get(name, {})
        r2 = round2_results.get(name, {})
        diff = generate_diff_report(name, r1, r2)
        diff_reports.append(diff)
        print(f"\n[{name}]")
        changes = diff.get("changes", {})
        if changes:
            print(f"  标题变化: {changes.get('title_changed', 'N/A')}")
            print(f"  无画像标题: {changes.get('title_without', 'N/A')}")
            print(f"  有画像标题: {changes.get('title_with', 'N/A')}")
            print(f"  正文长度差: {changes.get('body_length_diff', 'N/A')} 字")
            print(f"  Hashtags 变化: {changes.get('hashtags_changed', 'N/A')}")

    # 保存完整结果
    all_results["round1_no_profile"] = round1_results
    all_results["round2_with_profile"] = round2_results
    all_results["diff_reports"] = diff_reports

    report_path = TEST_RESULTS_DIR / "comparison_report.json"
    report_path.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完整报告已保存: {report_path}")

    # 保存可读的 Markdown 报告
    md_path = TEST_RESULTS_DIR / "REAL_COMPARISON_REPORT.md"
    write_markdown_report(md_path, all_results, diff_reports)
    print(f"Markdown 报告已保存: {md_path}")

    print("\n测试完成！")


def write_markdown_report(path: Path, results: dict, diffs: list):
    """生成 Markdown 格式的对比报告"""
    lines = []
    lines.append("# 真实 API 偏好注入前后对比报告")
    lines.append("")
    lines.append(f"**测试时间**: {results['timestamp']}")
    lines.append(f"**测试选题**: {results['topic']}")
    lines.append(f"**文本模型**: {os.environ.get('LLM_MODEL', 'unknown')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for diff in diffs:
        platform = diff["platform"]
        platform_names = {"xhs": "小红书", "douyin": "抖音", "wechat": "微信公众号"}
        lines.append(f"## {platform_names.get(platform, platform)} ({platform})")
        lines.append("")

        w = diff["without_profile"]
        wi = diff["with_profile"]

        lines.append(f"| 指标 | 无画像 | 有画像 |")
        lines.append(f"|------|--------|--------|")
        lines.append(f"| 是否成功 | {'✅' if w['success'] else '❌'} | {'✅' if wi['success'] else '❌'} |")
        lines.append(f"| 耗时 | {w['elapsed']}s | {wi['elapsed']}s |")
        lines.append("")

        changes = diff.get("changes", {})
        if changes:
            lines.append("### 关键差异")
            lines.append("")
            lines.append(f"- **标题对比**:")
            lines.append(f"  - 无画像: {changes.get('title_without', 'N/A')}")
            lines.append(f"  - 有画像: {changes.get('title_with', 'N/A')}")
            lines.append("")
            lines.append(f"- **正文长度**: {changes.get('body_length_without', 0)} → {changes.get('body_length_with', 0)} 字 (差值: {changes.get('body_length_diff', 0)})")
            lines.append("")

            lines.append(f"- **Hashtags 对比**:")
            lines.append(f"  - 无画像: {', '.join(changes.get('hashtags_without', []))}")
            lines.append(f"  - 有画像: {', '.join(changes.get('hashtags_with', []))}")
            lines.append("")

            lines.append("### 正文开头对比")
            lines.append("")
            lines.append("**无画像版本：**")
            lines.append("")
            lines.append("> " + (changes.get("body_preview_without", "N/A").replace("\n", "\n> ")))
            lines.append("")
            lines.append("**有画像版本：**")
            lines.append("")
            lines.append("> " + (changes.get("body_preview_with", "N/A").replace("\n", "\n> ")))
            lines.append("")

        # 完整输出
        lines.append("### 完整输出")
        lines.append("")
        lines.append("<details>")
        lines.append("<summary>无画像完整输出</summary>")
        lines.append("")
        r1_data = results.get("round1_no_profile", {}).get(platform, {})
        if r1_data.get("output"):
            lines.append("```json")
            lines.append(json.dumps(r1_data["output"], ensure_ascii=False, indent=2)[:3000])
            lines.append("```")
        elif r1_data.get("error"):
            lines.append(f"**错误**: {r1_data['error']}")
        lines.append("")
        lines.append("</details>")
        lines.append("")
        lines.append("<details>")
        lines.append("<summary>有画像完整输出</summary>")
        lines.append("")
        r2_data = results.get("round2_with_profile", {}).get(platform, {})
        if r2_data.get("output"):
            lines.append("```json")
            lines.append(json.dumps(r2_data["output"], ensure_ascii=False, indent=2)[:3000])
            lines.append("```")
        elif r2_data.get("error"):
            lines.append(f"**错误**: {r2_data['error']}")
        lines.append("")
        lines.append("</details>")
        lines.append("")
        lines.append("---")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
