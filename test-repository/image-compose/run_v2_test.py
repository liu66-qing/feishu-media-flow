"""
image-compose v2 测试脚本
========================
模拟 step1_analyze 数据经过 image-compose 技能包，展示 8 种 HTML 模板效果。
每个测试用例包含不同的 visual_context（模拟从 workflow.py 传来的 step1_analyze 数据），
验证智能模板匹配和场景化渲染。

运行方式：
    cd image-compose
    python test/run_v2_test.py

输出位置：
    test/results/v2_test/
    ├── case_01_学习/
    │   ├── input.json
    │   ├── logs.txt
    │   ├── image-compose.json
    │   └── output/
    │       └── xhs-cover-08.png
    ├── case_02_校园/
    │   └── ...
    └── test_summary.json
"""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

# 将 image-compose 根目录加入 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))
from main import run_job


# ---------------------------------------------------------------------------
# 8 组测试数据：模拟不同场景的 step1_analyze 输出 + visual_context
# ---------------------------------------------------------------------------
TEST_CASES = [
    {
        "name": "case_01_学习",
        "content_id": "CNT-V2-001",
        "job_id": "JOB-V2-001",
        "title": "考研复习时间规划",
        "subtitle": "每天多学2小时的秘密",
        "visual_context": {
            "scene_hint": "",
            "keywords": ["考研复习", "时间管理", "番茄工作法", "黄金时间段"],
            "topic_summary": "大学生考研复习时间规划指南"
        },
        "expected_template": "xhs-cover-08",  # 学习 → 全幅柔焦+中心白卡
    },
    {
        "name": "case_02_校园",
        "content_id": "CNT-V2-002",
        "job_id": "JOB-V2-002",
        "title": "社团招新季来了",
        "subtitle": "3个方法让转化率翻倍",
        "visual_context": {
            "scene_hint": "",
            "keywords": ["社团招新", "校园活动", "摆摊转化", "新生季"],
            "topic_summary": "大学社团招新活动策划与转化提升"
        },
        "expected_template": "xhs-cover-04",  # 社团招新 → 活动 → 大字报+emoji
    },
    {
        "name": "case_03_美食",
        "content_id": "CNT-V2-003",
        "job_id": "JOB-V2-003",
        "title": "食堂隐藏菜单大揭秘",
        "subtitle": "这5道菜绝了",
        "visual_context": {
            "scene_hint": "",
            "keywords": ["食堂美食", "隐藏菜单", "学生党必吃", "性价比"],
            "topic_summary": "大学食堂隐藏美食推荐"
        },
        "expected_template": "xhs-cover-03",  # 美食 → 底部文字
    },
    {
        "name": "case_04_生活",
        "content_id": "CNT-V2-004",
        "job_id": "JOB-V2-004",
        "title": "宿舍改造计划",
        "subtitle": "500元打造ins风小窝",
        "visual_context": {
            "scene_hint": "",
            "keywords": ["宿舍改造", "ins风", "收纳神器", "平价好物"],
            "topic_summary": "大学宿舍低成本改造分享"
        },
        "expected_template": "xhs-cover-06",  # 生活 → 顶部文字
    },
    {
        "name": "case_05_穿搭",
        "content_id": "CNT-V2-005",
        "job_id": "JOB-V2-005",
        "title": "早秋穿搭公式",
        "subtitle": "学生党平价搭配",
        "visual_context": {
            "scene_hint": "",
            "keywords": ["早秋穿搭", "学生党", "平价", "简约风"],
            "topic_summary": "大学生秋季平价穿搭推荐"
        },
        "expected_template": "xhs-cover-07",  # 穿搭 → 左对齐杂志风
    },
    {
        "name": "case_06_活动",
        "content_id": "CNT-V2-006",
        "job_id": "JOB-V2-006",
        "title": "校园歌手大赛",
        "subtitle": "报名倒计时3天",
        "visual_context": {
            "scene_hint": "",
            "keywords": ["歌手大赛", "校园活动", "报名", "才艺展示"],
            "topic_summary": "校园歌手大赛活动宣传"
        },
        "expected_template": "xhs-cover-04",  # 活动 → 大字报+emoji
    },
    {
        "name": "case_07_通知",
        "content_id": "CNT-V2-007",
        "job_id": "JOB-V2-007",
        "title": "奖学金申请指南",
        "subtitle": "截止日期本周五",
        "visual_context": {
            "scene_hint": "",
            "keywords": ["奖学金", "申请流程", "截止日期", "材料准备"],
            "topic_summary": "大学奖学金申请流程与注意事项"
        },
        "expected_template": "xhs-cover-02",  # 通知 → 卡片式
    },
    {
        "name": "case_08_情绪",
        "content_id": "CNT-V2-008",
        "job_id": "JOB-V2-008",
        "title": "焦虑时读这篇",
        "subtitle": "5个心理学小技巧",
        "visual_context": {
            "scene_hint": "",
            "keywords": ["焦虑缓解", "心理学", "情绪管理", "自我疗愈"],
            "topic_summary": "大学生焦虑情绪缓解方法"
        },
        "expected_template": "xhs-cover-03",  # 情绪 → 底部文字（氛围感）
    },
]


def build_input(case: dict) -> dict:
    """构建 image-compose 的 input.json，包含 visual_context 模拟 step1_analyze 数据"""
    return {
        "content_id": case["content_id"],
        "job_id": case["job_id"],
        "template_name": "",  # 留空，让智能匹配自动选择
        "image_mode": "template",  # 模板模式（不调用 DashScope API）
        "variables": {
            "title": case["title"],
            "subtitle": case["subtitle"],
            "visual_context": case["visual_context"],
        },
        "output_size": {
            "width": 1080,
            "height": 1350,
        },
    }


def run_single_case(case: dict, results_dir: Path) -> dict:
    """运行单个测试用例"""
    case_dir = results_dir / case["name"]

    # 清理旧结果
    if case_dir.exists():
        shutil.rmtree(case_dir)
    case_dir.mkdir(parents=True, exist_ok=True)

    # 写入 input.json
    input_data = build_input(case)
    with open(case_dir / "input.json", "w", encoding="utf-8") as f:
        json.dump(input_data, f, ensure_ascii=False, indent=2)

    start_time = datetime.now()
    result_data = None
    error_data = None

    try:
        result_data = run_job(case_dir)
        success = True
    except Exception as e:
        error_data = {"message": str(e)}
        success = False
        # 读取 error.json
        error_json = case_dir / "error.json"
        if error_json.exists():
            try:
                with open(error_json, "r", encoding="utf-8") as f:
                    error_data = json.load(f)
            except Exception:
                pass

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    # 收集输出图片信息
    output_images = []
    output_dir = case_dir / "output"
    if output_dir.exists():
        for f in sorted(output_dir.glob("*.png")):
            size_kb = round(f.stat().st_size / 1024, 1)
            output_images.append({"name": f.name, "size_kb": size_kb})

    template_used = result_data.get("data", {}).get("template_used") if result_data else None
    expected = case["expected_template"]
    match = template_used == expected

    return {
        "case_name": case["name"],
        "scene": case["name"].split("_")[1],  # 提取场景名
        "title": case["title"],
        "subtitle": case["subtitle"],
        "visual_context": case["visual_context"],
        "success": success,
        "duration_seconds": round(duration, 1),
        "output_images": output_images,
        "template_used": template_used,
        "expected_template": expected,
        "template_match": match,
        "image_mode_used": result_data.get("data", {}).get("image_mode_used") if result_data else None,
        "error": error_data,
    }


def main():
    results_dir = Path(__file__).parent / "results" / "v2_test"
    results_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("image-compose v2 test - 8 scene template demo")
    print("simulating step1_analyze -> smart template match -> HTML render")
    print(f"Output: {results_dir}")
    print("=" * 70)

    all_results = []

    for case in TEST_CASES:
        print(f"\n>>> [{case['name']}] {case['title']} - {case['subtitle']}")
        print(f"    visual_context: {case['visual_context']['keywords']}")

        result = run_single_case(case, results_dir)
        all_results.append(result)

        if result["success"]:
            tpl = result.get("template_used", "?")
            expected = result.get("expected_template", "?")
            match_str = "[OK]" if result["template_match"] else "[X]"
            imgs = ", ".join(f"{i['name']}({i['size_kb']}KB)" for i in result.get("output_images", []))
            print(f"    {match_str} template: {tpl} (expected: {expected})")
            print(f"    time: {result['duration_seconds']}s | images: {imgs}")
        else:
            print(f"    [FAIL] error")
            err = result.get("error")
            if err:
                print(f"    error: {json.dumps(err, ensure_ascii=False)[:300]}")

        # 保存单组结果
        result_file = results_dir / f"result_{case['name']}.json"
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    # 汇总报告
    passed = sum(1 for r in all_results if r["success"])
    matched = sum(1 for r in all_results if r.get("template_match"))
    failed = len(all_results) - passed

    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_cases": len(all_results),
        "passed": passed,
        "failed": failed,
        "template_matched": matched,
        "template_mismatched": len(all_results) - matched,
        "results": all_results,
    }

    summary_file = results_dir / "test_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print(f"Summary: {passed}/{len(all_results)} passed, {matched}/{len(all_results)} template matched")
    if failed > 0:
        print(f"  [FAIL] {failed} cases failed")
    print(f"Summary file: {summary_file}")
    print("=" * 70)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
