"""
image-compose v2 AI 背景图测试脚本
=================================
使用 image_mode="ai_bg" 调用 DashScope API 生成 AI 背景图，
验证 8 种场景的智能模板匹配 + AI 生图 + HTML 叠加完整流程。

运行方式：
    cd image-compose
    python test/run_v2_ai_test.py

输出位置：
    test/results/v2_ai_test/
    ├── case_01_学习/
    │   ├── input.json
    │   ├── logs.txt
    │   ├── image-compose.json
    │   └── output/
    │       ├── ai_bg.png          AI 生成的背景图
    │       └── xhs-cover-08.png   最终封面（AI背景+模板文字叠加）
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


# 复用 v2 测试的 8 组数据
TEST_CASES = [
    {
        "name": "case_01_学习",
        "content_id": "CNT-V2AI-001",
        "job_id": "JOB-V2AI-001",
        "title": "考研复习时间规划",
        "subtitle": "每天多学2小时的秘密",
        "visual_context": {
            "scene_hint": "",
            "keywords": ["考研复习", "时间管理", "番茄工作法", "黄金时间段"],
            "topic_summary": "大学生考研复习时间规划指南"
        },
        "expected_template": "xhs-cover-08",
    },
    {
        "name": "case_02_校园",
        "content_id": "CNT-V2AI-002",
        "job_id": "JOB-V2AI-002",
        "title": "社团招新季来了",
        "subtitle": "3个方法让转化率翻倍",
        "visual_context": {
            "scene_hint": "",
            "keywords": ["社团招新", "校园活动", "摆摊转化", "新生季"],
            "topic_summary": "大学社团招新活动策划与转化提升"
        },
        "expected_template": "xhs-cover-04",
    },
    {
        "name": "case_03_美食",
        "content_id": "CNT-V2AI-003",
        "job_id": "JOB-V2AI-003",
        "title": "食堂隐藏菜单大揭秘",
        "subtitle": "这5道菜绝了",
        "visual_context": {
            "scene_hint": "",
            "keywords": ["食堂美食", "隐藏菜单", "学生党必吃", "性价比"],
            "topic_summary": "大学食堂隐藏美食推荐"
        },
        "expected_template": "xhs-cover-03",
    },
    {
        "name": "case_04_生活",
        "content_id": "CNT-V2AI-004",
        "job_id": "JOB-V2AI-004",
        "title": "宿舍改造计划",
        "subtitle": "500元打造ins风小窝",
        "visual_context": {
            "scene_hint": "",
            "keywords": ["宿舍改造", "ins风", "收纳神器", "平价好物"],
            "topic_summary": "大学宿舍低成本改造分享"
        },
        "expected_template": "xhs-cover-06",
    },
    {
        "name": "case_05_穿搭",
        "content_id": "CNT-V2AI-005",
        "job_id": "JOB-V2AI-005",
        "title": "早秋穿搭公式",
        "subtitle": "学生党平价搭配",
        "visual_context": {
            "scene_hint": "",
            "keywords": ["早秋穿搭", "学生党", "平价", "简约风"],
            "topic_summary": "大学生秋季平价穿搭推荐"
        },
        "expected_template": "xhs-cover-07",
    },
    {
        "name": "case_06_活动",
        "content_id": "CNT-V2AI-006",
        "job_id": "JOB-V2AI-006",
        "title": "校园歌手大赛",
        "subtitle": "报名倒计时3天",
        "visual_context": {
            "scene_hint": "",
            "keywords": ["歌手大赛", "校园活动", "报名", "才艺展示"],
            "topic_summary": "校园歌手大赛活动宣传"
        },
        "expected_template": "xhs-cover-04",
    },
    {
        "name": "case_07_通知",
        "content_id": "CNT-V2AI-007",
        "job_id": "JOB-V2AI-007",
        "title": "奖学金申请指南",
        "subtitle": "截止日期本周五",
        "visual_context": {
            "scene_hint": "",
            "keywords": ["奖学金", "申请流程", "截止日期", "材料准备"],
            "topic_summary": "大学奖学金申请流程与注意事项"
        },
        "expected_template": "xhs-cover-02",
    },
    {
        "name": "case_08_情绪",
        "content_id": "CNT-V2AI-008",
        "job_id": "JOB-V2AI-008",
        "title": "焦虑时读这篇",
        "subtitle": "5个心理学小技巧",
        "visual_context": {
            "scene_hint": "",
            "keywords": ["焦虑缓解", "心理学", "情绪管理", "自我疗愈"],
            "topic_summary": "大学生焦虑情绪缓解方法"
        },
        "expected_template": "xhs-cover-03",
    },
]


def build_input(case: dict) -> dict:
    """构建 AI 背景图模式的 input.json"""
    return {
        "content_id": case["content_id"],
        "job_id": case["job_id"],
        "template_name": "",  # 留空，智能匹配自动选择
        "image_mode": "ai_bg",  # AI 背景图模式
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
    """运行单个 AI 背景图测试用例"""
    case_dir = results_dir / case["name"]

    if case_dir.exists():
        shutil.rmtree(case_dir)
    case_dir.mkdir(parents=True, exist_ok=True)

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
        error_json = case_dir / "error.json"
        if error_json.exists():
            try:
                with open(error_json, "r", encoding="utf-8") as f:
                    error_data = json.load(f)
            except Exception:
                pass

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    output_images = []
    output_dir = case_dir / "output"
    if output_dir.exists():
        for f in sorted(output_dir.glob("*.png")):
            size_kb = round(f.stat().st_size / 1024, 1)
            output_images.append({"name": f.name, "size_kb": size_kb})

    template_used = result_data.get("data", {}).get("template_used") if result_data else None
    expected = case["expected_template"]
    match = template_used == expected
    image_mode = result_data.get("data", {}).get("image_mode_used") if result_data else None
    ai_prompt = result_data.get("data", {}).get("ai_prompt_used") if result_data else None
    fallback = result_data.get("data", {}).get("ai_fallback_reason") if result_data else None

    return {
        "case_name": case["name"],
        "title": case["title"],
        "subtitle": case["subtitle"],
        "visual_context": case["visual_context"],
        "success": success,
        "duration_seconds": round(duration, 1),
        "output_images": output_images,
        "template_used": template_used,
        "expected_template": expected,
        "template_match": match,
        "image_mode_used": image_mode,
        "ai_prompt_used": ai_prompt,
        "ai_fallback_reason": fallback,
        "error": error_data,
    }


def main():
    results_dir = Path(__file__).parent / "results" / "v2_ai_test"
    results_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("image-compose v2 AI background test - 8 scene templates")
    print("step1_analyze -> smart match -> DashScope AI -> HTML overlay")
    print(f"Output: {results_dir}")
    print("NOTE: Each case calls DashScope API (~30-120s), total ~5-15min")
    print("=" * 70)

    all_results = []

    for i, case in enumerate(TEST_CASES, 1):
        print(f"\n[{i}/8] {case['name']}: {case['title']} - {case['subtitle']}")
        print(f"    keywords: {case['visual_context']['keywords']}")

        result = run_single_case(case, results_dir)
        all_results.append(result)

        if result["success"]:
            mode = result.get("image_mode_used", "?")
            tpl = result.get("template_used", "?")
            expected = result.get("expected_template", "?")
            match_str = "[OK]" if result["template_match"] else "[X]"
            imgs = ", ".join(f"{img['name']}({img['size_kb']}KB)" for img in result.get("output_images", []))
            dur = result["duration_seconds"]
            print(f"    {match_str} mode={mode}, template={tpl} (expected: {expected})")
            print(f"    time: {dur}s | images: {imgs}")
            if result.get("ai_prompt_used"):
                prompt = result["ai_prompt_used"]
                print(f"    prompt: {prompt[:120]}...")
            if result.get("ai_fallback_reason"):
                print(f"    fallback: {result['ai_fallback_reason']}")
        else:
            print(f"    [FAIL]")
            err = result.get("error")
            if err:
                print(f"    error: {json.dumps(err, ensure_ascii=False)[:300]}")

        # 保存单组结果
        result_file = results_dir / f"result_{case['name']}.json"
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    passed = sum(1 for r in all_results if r["success"])
    matched = sum(1 for r in all_results if r.get("template_match"))
    ai_ok = sum(1 for r in all_results if r.get("image_mode_used") == "ai_bg")
    failed = len(all_results) - passed

    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_cases": len(all_results),
        "passed": passed,
        "failed": failed,
        "template_matched": matched,
        "ai_bg_success": ai_ok,
        "ai_bg_fallback": len(all_results) - ai_ok,
        "results": all_results,
    }

    summary_file = results_dir / "test_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print(f"Summary: {passed}/{len(all_results)} passed")
    print(f"  Template match: {matched}/{len(all_results)}")
    print(f"  AI bg success:  {ai_ok}/{len(all_results)}")
    if failed > 0:
        print(f"  [FAIL] {failed} cases failed")
    print(f"Summary file: {summary_file}")
    print("=" * 70)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
