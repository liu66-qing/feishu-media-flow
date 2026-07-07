"""
Mock 测试脚本 - 不依赖外部 LLM，验证核心流程逻辑
"""
import json
import sys
from datetime import datetime
from pathlib import Path

# 模拟 LLM 返回内容
MOCK_RESPONSE = {
    "title_options": [
        "招新别只会摆摊！3个方法翻倍转化",
        "社团招新做对这一件事，报名爆棚",
        "亲测有效｜社团招新转化率提升3倍"
    ],
    "selected_title": "招新别只会摆摊！3个方法翻倍转化",
    "body": "开学季到了，又到了社团招新的关键时期。\n\n说实话，去年我们社团的招新情况真的惨不忍睹——在食堂门口摆了三天摊，发了500多份传单，结果报名的不到20个人。\n\n最大的问题是：路过的人根本不知道我们在做什么，很多人只是礼貌性地接过传单就走了，转手就扔进了垃圾桶。\n\n后来我们痛定思痛，花了一个暑假研究怎么改进招新策略，试了这几个方法之后，效果提升非常明显。\n\n第一个是做试玩体验区。\n\n比如我们是摄影社团，就在摊位旁边搭了一个小摄影棚，让路过的同学可以免费拍一张照片。这样大家不用问就知道我们社团在做什么了，而且体验感很强。去年用这个方法的转化率提升了3倍，很多同学拍完照之后就直接扫码报名了。\n\n第二个是准备精美的宣传手册。\n\n不是那种传统的黑白传单，而是有质感的彩色小册子，里面放了我们社团活动的照片和成员的真实故事。很多同学拿到手之后会停下来翻一翻，觉得这个社团挺有意思的，至少不会看一眼就扔掉。\n\n第三个是设置互动游戏环节。\n\n参与就可以拿到小礼品，比如社团定制的钥匙扣、贴纸之类的小东西。这样大家会主动过来了解，而不是被动接收信息。互动过程中我们的成员会自然地介绍社团的情况，气氛也不会那么尴尬。\n\n总结一下，招新其实不难，关键是要让同学主动来了解你，而不是被动接收信息。\n\n你们社团有什么招新妙招？欢迎在评论区分享！",
    "hashtags": ["#社团招新", "#大学生活", "#社团运营", "#校园干货", "#招新技巧", "#大学生社团"],
    "cover_text": "招新转化率翻倍秘籍分享",
    "risk_notes": []
}


def test_flow():
    job_dir = Path("./test/fixtures")
    results_dir = Path("./test/results")
    results_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("Content-Generate-XHS Mock Test")
    print("=" * 60)
    
    # 1. 测试输入读取
    print("\n[1/5] 测试输入读取...")
    input_path = job_dir / "input_01.json"
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            input_data = json.load(f)
        print(f"  ✅ 成功读取输入: {input_data['content_id']}")
        print(f"  📌 选题: {input_data['topic']}")
        print(f"  📝 素材数量: {len(input_data.get('materials', []))}")
    except Exception as e:
        print(f"  ❌ 读取失败: {e}")
        return False
    
    # 2. 测试必填字段校验
    print("\n[2/5] 测试必填字段校验...")
    required_fields = ["content_id", "job_id", "topic"]
    missing = [f for f in required_fields if f not in input_data]
    if missing:
        print(f"  ❌ 缺少字段: {missing}")
        return False
    print(f"  ✅ 所有必填字段存在")
    
    # 3. 模拟 Prompt 构建
    print("\n[3/5] 测试 Prompt 构建...")
    skill_dir = Path(__file__).parent
    system_prompt_path = skill_dir / "prompts" / "system.md"
    user_template_path = skill_dir / "prompts" / "user_template.md"
    
    if not system_prompt_path.exists():
        print(f"  ❌ system.md 不存在")
        return False
    if not user_template_path.exists():
        print(f"  ❌ user_template.md 不存在")
        return False
    
    with open(system_prompt_path, "r", encoding="utf-8") as f:
        system_content = f.read()
    with open(user_template_path, "r", encoding="utf-8") as f:
        user_template = f.read()
    
    print(f"  ✅ system.md 已加载 ({len(system_content)} 字符)")
    print(f"  ✅ user_template.md 已加载 ({len(user_template)} 字符)")
    
    # 4. 模拟输出写入
    print("\n[4/5] 测试输出写入...")
    result = {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "content_id": input_data["content_id"],
        "data": MOCK_RESPONSE
    }
    result["data"]["content_id"] = input_data["content_id"]
    
    output_path = results_dir / "content-generate-xhs.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"  ✅ 输出已写入: {output_path}")
    
    # 5. 输出内容验证
    print("\n[5/5] 输出内容验证...")
    data = result["data"]
    
    # 验证标题数量
    title_count = len(data["title_options"])
    assert title_count == 3, f"标题数量错误: {title_count}"
    print(f"  ✅ 标题数量: {title_count}")
    
    # 验证标题字数
    for title in data["title_options"]:
        assert 12 <= len(title) <= 25, f"标题字数错误: {title} ({len(title)}字)"
    print(f"  ✅ 标题字数: 12-25字")
    
    # 验证正文字数
    body_len = len(data["body"])
    assert 500 <= body_len <= 800, f"正文字数错误: {body_len}字"
    print(f"  ✅ 正文字数: {body_len}字")
    
    # 验证标签数量
    tag_count = len(data["hashtags"])
    assert 5 <= tag_count <= 8, f"标签数量错误: {tag_count}"
    print(f"  ✅ 标签数量: {tag_count}")
    
    # 验证封面文案
    cover_len = len(data["cover_text"])
    assert 10 <= cover_len <= 12, f"封面文案字数错误: {cover_len}字"
    print(f"  ✅ 封面文案: {cover_len}字")
    
    # 验证 selected_title
    assert data["selected_title"] in data["title_options"], "selected_title 不在 title_options 中"
    print(f"  ✅ selected_title 有效")
    
    # 验证风险记录
    assert isinstance(data["risk_notes"], list), "risk_notes 必须是数组"
    print(f"  ✅ risk_notes 格式正确")
    
    print("\n" + "=" * 60)
    print("✅ 所有测试通过！")
    print("=" * 60)
    
    # 输出内容预览
    print("\n📄 生成内容预览:")
    print(f"   标题选项:")
    for i, t in enumerate(data["title_options"], 1):
        print(f"     {i}. {t}")
    print(f"\n   选中标题: {data['selected_title']}")
    print(f"\n   封面文案: {data['cover_text']}")
    print(f"\n   话题标签: {' '.join(data['hashtags'])}")
    print(f"\n   正文预览: {data['body'][:100]}...")
    
    return True


if __name__ == "__main__":
    success = test_flow()
    sys.exit(0 if success else 1)