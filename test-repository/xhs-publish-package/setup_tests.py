"""
测试数据生成脚本
用于创建测试输入数据和测试图片
"""

import json
import base64
import zlib
import struct
from pathlib import Path


def create_png(width: int, height: int, color: tuple) -> bytes:
    """创建简单的 PNG 图片字节数据"""
    r, g, b = color

    def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
        chunk_len = struct.pack('>I', len(data))
        chunk_crc = struct.pack('>I', zlib.crc32(chunk_type + data) & 0xffffffff)
        return chunk_len + chunk_type + data + chunk_crc

    # PNG signature
    signature = b'\x89PNG\r\n\x1a\n'

    # IHDR chunk
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr = png_chunk(b'IHDR', ihdr_data)

    # IDAT chunk (image data)
    raw_data = b''
    for y in range(height):
        raw_data += b'\x00'  # filter byte
        for x in range(width):
            raw_data += bytes([r, g, b])

    compressed = zlib.compress(raw_data, 9)
    idat = png_chunk(b'IDAT', compressed)

    # IEND chunk
    iend = png_chunk(b'IEND', b'')

    return signature + ihdr + idat + iend


def create_test_image(path: Path, color: tuple, text: str = ""):
    """创建简单的测试图片"""
    png_data = create_png(200, 200, color)
    with open(path, 'wb') as f:
        f.write(png_data)
    print(f"创建图片: {path}")


def create_test_data():
    """创建所有测试数据"""
    base_path = Path(__file__).parent / "fixtures"

    # Test 01: 正常场景（2张图片）
    test01_dir = base_path / "test_01"
    test01_dir.mkdir(parents=True, exist_ok=True)

    # 创建测试图片
    create_test_image(test01_dir / "cover.png", (255, 100, 100), "Cover")
    create_test_image(test01_dir / "card_01.png", (100, 255, 100), "Card 01")

    input_01 = {
        "content_id": "CNT-20260706-001",
        "job_id": "JOB-20260706-001",
        "title": "招新别只会摆摊",
        "body": "开学季社团招新到了，别只会摆摊发传单！\n\n今天分享3个高转化招新技巧：\n1️⃣ 互动体验区 - 让新生亲身参与\n2️⃣ 社群预热 - 建立归属感\n3️⃣ 现场演示 - 用结果说话\n\n这些方法让你的招新效率翻倍！",
        "hashtags": ["#社团招新", "#大学生活", "#校园运营"],
        "cover_text": "招新转化翻倍",
        "assets": [
            {"type": "image", "path": "cover.png"},
            {"type": "image", "path": "card_01.png"}
        ],
        "scheduled_at": "2026-07-06T20:30:00+08:00"
    }

    with open(test01_dir / "input.json", "w", encoding="utf-8") as f:
        json.dump(input_01, f, ensure_ascii=False, indent=2)
    print(f"创建测试数据: {test01_dir / 'input.json'}")

    # Test 02: 空 assets 数组
    test02_dir = base_path / "test_02"
    test02_dir.mkdir(parents=True, exist_ok=True)

    input_02 = {
        "content_id": "CNT-20260706-002",
        "job_id": "JOB-20260706-002",
        "title": "校园生活必备清单",
        "body": "新学期开始了，这些物品你准备好了吗？\n\n✅ 学习用品\n✅ 生活用品\n✅ 电子产品\n\n关注我，获取更多校园攻略！",
        "hashtags": ["#校园生活", "#新生指南", "#必备清单"],
        "cover_text": "开学必备",
        "assets": [],
        "scheduled_at": "2026-07-06T18:00:00+08:00"
    }

    with open(test02_dir / "input.json", "w", encoding="utf-8") as f:
        json.dump(input_02, f, ensure_ascii=False, indent=2)
    print(f"创建测试数据: {test02_dir / 'input.json'}")

    # Test 03: 多图片场景（4张图片）
    test03_dir = base_path / "test_03"
    test03_dir.mkdir(parents=True, exist_ok=True)

    # 创建测试图片
    create_test_image(test03_dir / "cover.png", (255, 150, 100), "Cover")
    create_test_image(test03_dir / "card_01.png", (100, 150, 255), "Card 01")
    create_test_image(test03_dir / "card_02.png", (150, 255, 100), "Card 02")
    create_test_image(test03_dir / "card_03.png", (255, 100, 200), "Card 03")

    input_03 = {
        "content_id": "CNT-20260706-003",
        "job_id": "JOB-20260706-003",
        "title": "社团活动策划全攻略",
        "body": "想办一场成功的社团活动？这份攻略请收好！\n\n📋 前期准备\n🎯 活动执行\n📊 效果复盘\n\n详细内容见图~",
        "hashtags": ["#社团活动", "#策划攻略", "#校园活动", "#大学生活"],
        "cover_text": "活动策划全攻略",
        "assets": [
            {"type": "image", "path": "cover.png"},
            {"type": "image", "path": "card_01.png"},
            {"type": "image", "path": "card_02.png"},
            {"type": "image", "path": "card_03.png"}
        ],
        "scheduled_at": "2026-07-07T10:00:00+08:00"
    }

    with open(test03_dir / "input.json", "w", encoding="utf-8") as f:
        json.dump(input_03, f, ensure_ascii=False, indent=2)
    print(f"创建测试数据: {test03_dir / 'input.json'}")

    # Test 04: 无 scheduled_at 字段
    test04_dir = base_path / "test_04"
    test04_dir.mkdir(parents=True, exist_ok=True)

    # 创建测试图片
    create_test_image(test04_dir / "cover.png", (200, 100, 150), "Cover")
    create_test_image(test04_dir / "detail.png", (100, 200, 150), "Detail")

    input_04 = {
        "content_id": "CNT-20260706-004",
        "job_id": "JOB-20260706-004",
        "title": "宿舍收纳小技巧",
        "body": "宿舍空间小？这几招让你收纳无忧！\n\n🏠 垂直空间利用\n📦 收纳盒分类\n👔 挂式收纳\n\n赶紧学起来！",
        "hashtags": ["#宿舍收纳", "#生活技巧", "#大学生活"],
        "cover_text": "宿舍收纳技巧",
        "assets": [
            {"type": "image", "path": "cover.png"},
            {"type": "image", "path": "detail.png"}
        ]
    }

    with open(test04_dir / "input.json", "w", encoding="utf-8") as f:
        json.dump(input_04, f, ensure_ascii=False, indent=2)
    print(f"创建测试数据: {test04_dir / 'input.json'}")

    # Test 05: 图片缺失场景
    test05_dir = base_path / "test_05"
    test05_dir.mkdir(parents=True, exist_ok=True)

    # 只创建一张存在的图片
    create_test_image(test05_dir / "cover.png", (150, 100, 200), "Cover")
    # 不创建 missing_image.png

    input_05 = {
        "content_id": "CNT-20260706-005",
        "job_id": "JOB-20260706-005",
        "title": "图书馆自习指南",
        "body": "如何在图书馆高效自习？\n\n📚 选择合适位置\n⏰ 规划学习时间\n🎧 准备降噪耳机\n\n祝大家学习顺利！",
        "hashtags": ["#图书馆", "#自习指南", "#学习技巧"],
        "cover_text": "图书馆自习指南",
        "assets": [
            {"type": "image", "path": "cover.png"},
            {"type": "image", "path": "missing_image.png"}
        ],
        "scheduled_at": "2026-07-07T14:00:00+08:00"
    }

    with open(test05_dir / "input.json", "w", encoding="utf-8") as f:
        json.dump(input_05, f, ensure_ascii=False, indent=2)
    print(f"创建测试数据: {test05_dir / 'input.json'}")

    print("\n✅ 所有测试数据创建完成！")


if __name__ == "__main__":
    create_test_data()