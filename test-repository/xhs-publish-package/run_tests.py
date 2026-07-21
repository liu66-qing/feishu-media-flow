"""
批量测试脚本
执行所有测试用例并记录结果
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime


def run_test(test_dir: Path, main_py: Path) -> dict:
    """执行单个测试"""
    result = {
        "test_dir": str(test_dir),
        "test_name": test_dir.name,
        "timestamp": datetime.now().isoformat(),
        "success": False,
        "output_files": [],
        "error": None,
        "logs": None
    }

    try:
        # 运行 main.py
        cmd = [sys.executable, str(main_py), "--job-dir", str(test_dir)]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')

        result["logs"] = proc.stdout + proc.stderr

        # 检查输出
        publish_dir = test_dir / "publish_package"
        result_json = test_dir / "xhs_publish_package.json"
        error_json = test_dir / "error.json"

        if result_json.exists():
            result["success"] = True
            with open(result_json, "r", encoding="utf-8") as f:
                result["output_files"].append("xhs_publish_package.json")
                result["result_data"] = json.load(f)

        if error_json.exists():
            result["success"] = False
            with open(error_json, "r", encoding="utf-8") as f:
                result["error"] = json.load(f)

        # 检查 publish_package 目录
        if publish_dir.exists():
            files = list(publish_dir.glob("**/*"))
            result["publish_package_files"] = [f.name for f in files if f.is_file()]

            # 检查 assets 目录
            assets_dir = publish_dir / "assets"
            if assets_dir.exists():
                assets_files = list(assets_dir.glob("*"))
                result["assets_files"] = [f.name for f in assets_files if f.is_file()]
            else:
                result["assets_files"] = []

        # 检查 logs.txt
        logs_file = test_dir / "logs.txt"
        if logs_file.exists():
            with open(logs_file, "r", encoding="utf-8") as f:
                result["logs_content"] = f.read()

    except Exception as e:
        result["error"] = str(e)

    return result


def main():
    """执行所有测试"""
    test_base = Path(__file__).parent / "fixtures"
    main_py = Path(__file__).parent.parent / "main.py"
    results_dir = Path(__file__).parent / "results"

    results_dir.mkdir(parents=True, exist_ok=True)

    # 清理旧的测试输出
    for test_dir in test_base.glob("test_*"):
        publish_dir = test_dir / "publish_package"
        if publish_dir.exists():
            import shutil
            shutil.rmtree(publish_dir)

        for f in test_dir.glob("*.json"):
            if f.name != "input.json":
                f.unlink()

        logs_file = test_dir / "logs.txt"
        if logs_file.exists():
            logs_file.unlink()

    # 执行所有测试
    test_dirs = sorted(test_base.glob("test_*"))
    all_results = []

    print("=" * 60)
    print("开始执行测试")
    print("=" * 60)

    for test_dir in test_dirs:
        print(f"\n>>> 执行测试: {test_dir.name}")
        result = run_test(test_dir, main_py)
        all_results.append(result)

        # 打印结果
        if result["success"]:
            print(f"    ✅ 测试通过")
            print(f"    输出文件: {result.get('publish_package_files', [])}")
            print(f"    资源文件: {result.get('assets_files', [])}")
        else:
            print(f"    ❌ 测试失败")
            print(f"    错误: {result.get('error', 'Unknown')}")

        # 保存单个测试结果
        result_file = results_dir / f"test_result_{test_dir.name}.json"
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    # 保存汇总结果
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_tests": len(all_results),
        "passed": sum(1 for r in all_results if r["success"]),
        "failed": sum(1 for r in all_results if not r["success"]),
        "results": all_results
    }

    summary_file = results_dir / "test_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # 打印汇总
    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)
    print(f"总测试数: {summary['total_tests']}")
    print(f"通过: {summary['passed']}")
    print(f"失败: {summary['failed']}")
    print(f"结果文件: {summary_file}")

    return summary


if __name__ == "__main__":
    main()