"""
image-compose 批量测试脚本
==========================

用途：一键运行 test/fixtures/ 下所有测试用例，将结果输出到 test/results/，
      保持 fixtures 目录纯净（只读测试数据，不产生任何输出文件）。

运行方式：
    cd image-compose
    python test/run_tests.py

输出位置：
    test/results/
    ├── test_01/                       单组测试的任务目录（由脚本从 fixtures 复制 input.json 后生成）
    │   ├── input.json                 复制过来的输入文件
    │   ├── logs.txt                   运行日志
    │   ├── image-compose.json         合成结果元数据
    │   └── output/
    │       └── xhs-cover-01.png       合成图片（AI 模式下还会有 ai_bg.png）
    ├── test_result_test_01.json       单组测试的结构化结果（含耗时、文件大小等）
    ├── test_result_test_02.json
    ├── ...
    └── test_summary.json              所有测试的汇总报告（通过数/失败数）

设计要点：
  - 不使用 subprocess 启动子进程，而是直接 import main.run_job() 调用，
    避免沙盒环境中子进程被限制访问 Playwright 模块的问题。
  - 运行前自动清理 results 中同名旧目录，保证每次运行结果干净。
  - fixtures 目录中的 test_XX 子目录只包含 input.json，永远不会被写入。
"""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

# 将 image-compose 根目录加入 sys.path，以便直接 import main 模块
sys.path.insert(0, str(Path(__file__).parent.parent))
from main import run_job


def run_single_test(test_name: str, fixtures_dir: Path, results_dir: Path) -> dict:
    """
    执行单组测试：将 fixtures/test_name/input.json 复制到 results/test_name/，
    然后调用 run_job() 完成图片合成，收集结果信息返回。

    参数：
        test_name     测试用例目录名（如 "test_01"）
        fixtures_dir  测试输入数据根目录（test/fixtures）
        results_dir   测试输出根目录（test/results）

    返回：
        包含以下字段的字典：
          test_name          测试名
          success            是否成功
          duration_seconds   耗时（秒）
          output_images      输出 PNG 列表 [{"name": ..., "size_kb": ...}, ...]
          image_mode_used    实际使用的模式（template/ai_bg）
          template_used      实际使用的模板
          ai_prompt_used     AI 模式下实际发送的 prompt
          ai_fallback_reason AI 降级原因（未降级则为 None）
          error              失败时的错误信息
    """
    fixture_dir = fixtures_dir / test_name
    result_dir = results_dir / test_name
    input_src = fixture_dir / "input.json"

    if not input_src.exists():
        return {
            "test_name": test_name,
            "success": False,
            "error": f"input.json not found in {fixture_dir}"
        }

    # 如果 results 下已有旧的测试结果目录，先删除以保证干净
    if result_dir.exists():
        shutil.rmtree(result_dir)
    result_dir.mkdir(parents=True, exist_ok=True)

    # 将 input.json 从 fixtures 复制到 results 的任务目录中
    shutil.copy2(input_src, result_dir / "input.json")

    start_time = datetime.now()
    error_data = None
    result_data = None

    try:
        # 直接调用 run_job()，避免子进程方式的依赖和沙盒问题
        result_data = run_job(result_dir)
        success = True
    except Exception as e:
        error_data = {"message": str(e)}
        success = False
        # run_job 失败时会写 error.json，尝试读取更详细的错误
        error_json = result_dir / "error.json"
        if error_json.exists():
            try:
                with open(error_json, "r", encoding="utf-8") as f:
                    error_data = json.load(f)
            except Exception:
                pass

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    # 收集输出图片信息（文件名 + 大小）
    output_images = []
    output_dir = result_dir / "output"
    if output_dir.exists():
        for f in sorted(output_dir.glob("*.png")):
            size_kb = round(f.stat().st_size / 1024, 1)
            output_images.append({"name": f.name, "size_kb": size_kb})

    return {
        "test_name": test_name,
        "success": success,
        "duration_seconds": round(duration, 1),
        "output_images": output_images,
        "image_mode_used": result_data.get("data", {}).get("image_mode_used") if result_data else None,
        "template_used": result_data.get("data", {}).get("template_used") if result_data else None,
        "ai_prompt_used": result_data.get("data", {}).get("ai_prompt_used") if result_data else None,
        "ai_fallback_reason": result_data.get("data", {}).get("ai_fallback_reason") if result_data else None,
        "error": error_data
    }


def main():
    """
    批量测试入口：
      1. 扫描 fixtures 目录下所有 test_* 子目录
      2. 依次执行每组测试
      3. 实时打印进度和结果到控制台
      4. 每组结果写入 test/results/test_result_test_XX.json
      5. 汇总写入 test/results/test_summary.json
      6. 返回进程退出码：全部通过返回 0，有失败返回 1
    """
    base_dir = Path(__file__).parent
    fixtures_dir = base_dir / "fixtures"
    results_dir = base_dir / "results"

    results_dir.mkdir(parents=True, exist_ok=True)

    # 自动发现 fixtures 下所有 test_ 开头的目录作为测试用例
    test_names = sorted([d.name for d in fixtures_dir.iterdir() if d.is_dir() and d.name.startswith("test_")])

    print("=" * 60)
    print(f"image-compose 批量测试 ({len(test_names)} 组)")
    print(f"Fixtures: {fixtures_dir}")
    print(f"Results:  {results_dir}")
    print("=" * 60)

    all_results = []

    for test_name in test_names:
        print(f"\n>>> 运行 {test_name} ...", end=" ", flush=True)
        result = run_single_test(test_name, fixtures_dir, results_dir)
        all_results.append(result)

        if result["success"]:
            mode = result.get("image_mode_used", "?")
            tpl = result.get("template_used", "?")
            imgs = ", ".join(f"{i['name']}({i['size_kb']}KB)" for i in result.get("output_images", []))
            dur = result.get("duration_seconds", "?")
            print(f"✅ 通过 ({dur}s)")
            print(f"    mode={mode}, template={tpl}")
            print(f"    images: {imgs}")
            if result.get("ai_fallback_reason"):
                print(f"    fallback: {result['ai_fallback_reason']}")
        else:
            print(f"❌ 失败")
            err = result.get("error")
            if err:
                print(f"    error: {json.dumps(err, ensure_ascii=False)[:300]}")

        # 保存单组测试结果 JSON
        result_file = results_dir / f"test_result_{test_name}.json"
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    passed = sum(1 for r in all_results if r["success"])
    failed = len(all_results) - passed

    # 生成汇总报告
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_tests": len(all_results),
        "passed": passed,
        "failed": failed,
        "results": all_results
    }

    summary_file = results_dir / "test_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(f"测试汇总: {passed}/{len(all_results)} 通过", end="")
    if failed > 0:
        print(f", {failed} 失败")
    else:
        print(" (全部通过)")
    print(f"汇总报告: {summary_file}")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
