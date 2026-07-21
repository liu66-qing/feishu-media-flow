"""
偏好注入前后对比测试
===================

测试内容生成模块在有无平台偏好画像时的输出差异。
"""

import json
import sys
from pathlib import Path
from datetime import datetime


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TEST_DIR = PROJECT_ROOT / "platform-preference-profiler" / "test" / "results" / "test_run_001"


def load_profile(platform: str) -> dict | None:
    """加载平台画像"""
    profile_path = PROJECT_ROOT / ".data" / "profiles" / f"{platform}_profile.json"
    if not profile_path.exists():
        return None
    return json.loads(profile_path.read_text(encoding="utf-8"))


def get_static_constraints(platform: str) -> dict:
    """获取静态平台约束"""
    constraints_file = PROJECT_ROOT / "app" / "prompts" / "platform_constraints.json"
    if not constraints_file.exists():
        return {}
    constraints = json.loads(constraints_file.read_text(encoding="utf-8"))
    return constraints.get(platform, {})


def build_prompt_without_profile(platform: str) -> str:
    """构建无画像的 prompt（仅静态规则）"""
    constraints = get_static_constraints(platform)
    
    platform_names = {"xhs": "小红书", "douyin": "抖音", "wechat": "公众号"}
    name = platform_names.get(platform, platform)
    
    prompt = f"你是{name}内容创作者。\n\n"
    prompt += "## 平台约束\n"
    prompt += f"- 标题：最多{constraints.get('title_max_length', 20)}字\n"
    prompt += f"- 正文：{constraints.get('body_min_length', 400)}-{constraints.get('body_max_length', 900)}字\n"
    prompt += f"- 标签：最多{constraints.get('max_tags', 10)}个\n"
    prompt += f"- 禁用词：{'、'.join(constraints.get('forbidden_words', []))}\n\n"
    prompt += "## 风格要求\n"
    prompt += f"{constraints.get('style_guide', '无')}\n\n"
    prompt += "## 内容结构\n"
    prompt += f"{constraints.get('content_structure', '无')}"
    
    return prompt


def build_prompt_with_profile(platform: str) -> str:
    """构建有画像的 prompt（静态规则 + 动态画像）"""
    base_prompt = build_prompt_without_profile(platform)
    profile = load_profile(platform)
    
    if not profile:
        return base_prompt
    
    base_prompt += "\n\n## 平台偏好画像（动态）\n"
    base_prompt += f"- 置信度：{profile.get('conf', 0)}\n"
    base_prompt += f"- 样本数：{profile.get('s_cnt', 0)}\n"
    
    topic = profile.get("topic", {})
    if topic:
        base_prompt += f"- 选题偏好：{json.dumps(topic.get('pref', []), ensure_ascii=False)}\n"
        base_prompt += f"- 切入角度：{topic.get('angle', '')}\n"
        base_prompt += f"- 标题模板：{json.dumps(topic.get('title_tpl', []), ensure_ascii=False)}\n"
    
    lang = profile.get("lang", {})
    if lang:
        base_prompt += f"- 语言风格：{lang.get('tone', '')}\n"
        base_prompt += f"- 段落特征：{lang.get('para', '')}\n"
        base_prompt += f"- 字数范围：{lang.get('word_len', '')}\n"
        base_prompt += f"- emoji 使用：{lang.get('emoji', '')}\n"
    
    vis = profile.get("vis", {})
    if vis:
        base_prompt += f"- 视觉风格：{vis.get('img_style', '')}\n"
        base_prompt += f"- 色彩偏好：{json.dumps(vis.get('color', []), ensure_ascii=False)}\n"
        base_prompt += f"- 封面风格：{vis.get('cover', '')}\n"
    
    struct = profile.get("struct", [])
    if struct:
        base_prompt += f"- 内容结构：{len(struct)}个阶段\n"
        for i, stage in enumerate(struct[:3], 1):  # 只显示前 3 个阶段
            base_prompt += f"  {i}. {stage[0]} ({stage[1]})\n"
    
    forbid = profile.get("forbid", [])
    if forbid:
        base_prompt += f"- 额外禁用：{'、'.join(forbid)}\n"
    
    return base_prompt


def compare_prompts(platform: str) -> dict:
    """对比有无画像的 prompt 差异"""
    prompt_without = build_prompt_without_profile(platform)
    prompt_with = build_prompt_with_profile(platform)
    
    profile = load_profile(platform)
    
    return {
        "platform": platform,
        "profile_loaded": profile is not None,
        "profile_confidence": profile.get("conf", 0) if profile else 0,
        "profile_samples": profile.get("s_cnt", 0) if profile else 0,
        "prompt_without_profile": prompt_without,
        "prompt_with_profile": prompt_with,
        "prompt_length_without": len(prompt_without),
        "prompt_length_with": len(prompt_with),
        "length_increase": len(prompt_with) - len(prompt_without),
        "increase_percentage": round((len(prompt_with) - len(prompt_without)) / len(prompt_without) * 100, 1) if len(prompt_without) > 0 else 0
    }


def generate_comparison_report() -> dict:
    """生成完整对比报告"""
    platforms = ["xhs", "douyin", "wechat"]
    comparisons = []
    
    for platform in platforms:
        comparison = compare_prompts(platform)
        comparisons.append(comparison)
    
    report = {
        "test_id": "test_run_001",
        "generated_at": datetime.now().isoformat(),
        "test_type": "preference_injection_comparison",
        "platforms": comparisons,
        "summary": {
            "total_platforms": len(platforms),
            "profiles_loaded": sum(1 for c in comparisons if c["profile_loaded"]),
            "avg_confidence": round(sum(c["profile_confidence"] for c in comparisons) / len(comparisons), 2),
            "avg_prompt_increase_pct": round(sum(c["increase_percentage"] for c in comparisons) / len(comparisons), 1)
        }
    }
    
    return report


def main():
    # Fix Windows console encoding
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    
    print("=" * 70)
    print("偏好注入前后对比测试")
    print("=" * 70)
    
    # 生成对比报告
    report = generate_comparison_report()
    
    # 保存报告
    report_path = TEST_DIR / "preference_comparison_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ 对比报告已保存：{report_path}")
    
    # 打印摘要
    print("\n" + "=" * 70)
    print("测试摘要")
    print("=" * 70)
    print(f"测试平台数：{report['summary']['total_platforms']}")
    print(f"成功加载画像：{report['summary']['profiles_loaded']}/{report['summary']['total_platforms']}")
    print(f"平均置信度：{report['summary']['avg_confidence']}")
    print(f"Prompt 平均增长：{report['summary']['avg_prompt_increase_pct']}%")
    
    # 打印各平台详情
    print("\n" + "=" * 70)
    print("各平台详情")
    print("=" * 70)
    
    for comp in report["platforms"]:
        print(f"\n【{comp['platform'].upper()}】")
        print(f"  画像加载：{'✅ 是' if comp['profile_loaded'] else '❌ 否'}")
        if comp["profile_loaded"]:
            print(f"  置信度：{comp['profile_confidence']}")
            print(f"  样本数：{comp['profile_samples']}")
        print(f"  Prompt 长度（无画像）：{comp['prompt_length_without']} 字符")
        print(f"  Prompt 长度（有画像）：{comp['prompt_length_with']} 字符")
        print(f"  增长：+{comp['length_increase']} 字符 (+{comp['increase_percentage']}%)")
    
    print("\n" + "=" * 70)
    print("✅ 测试完成")
    print("=" * 70)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
