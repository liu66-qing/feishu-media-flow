import argparse
import json
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path


def setup_logging(job_dir: Path):
    """配置日志输出到 {job_dir}/logs.txt"""
    log_file = job_dir / "logs.txt"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout)
        ]
    )


def load_input(job_dir: Path) -> dict:
    """读取输入文件"""
    input_path = job_dir / "input.json"
    if not input_path.exists():
        raise FileNotFoundError(f"输入文件不存在: {input_path}")

    try:
        with open(input_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 格式错误: {e}")


def validate_input(input_data: dict) -> None:
    """验证输入数据的必填字段"""
    required_fields = ["content_id", "job_id", "title", "body", "hashtags"]
    missing_fields = []

    for field in required_fields:
        if field not in input_data:
            missing_fields.append(field)

    if missing_fields:
        raise ValueError(f"缺少必填字段: {', '.join(missing_fields)}")


def write_output(job_dir: Path, skill_name: str, data: dict):
    """写入成功输出"""
    output_path = job_dir / f"{skill_name}.json"
    result = {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "data": data
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


def write_error(job_dir: Path, error_msg: str):
    """写入错误输出"""
    error_path = job_dir / "error.json"
    error_data = {
        "status": "error",
        "timestamp": datetime.now().isoformat(),
        "error": error_msg
    }
    with open(error_path, "w", encoding="utf-8") as f:
        json.dump(error_data, f, ensure_ascii=False, indent=2)


def create_publish_directory(job_dir: Path) -> Path:
    """创建发布包目录结构"""
    publish_dir = job_dir / "publish_package"
    assets_dir = publish_dir / "assets"

    # 如果目录已存在，删除重建
    if publish_dir.exists():
        logging.info(f"目录已存在，删除重建: {publish_dir}")
        shutil.rmtree(publish_dir)

    publish_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)
    logging.info(f"创建发布包目录: {publish_dir}")

    return publish_dir


def generate_text_files(publish_dir: Path, input_data: dict):
    """生成纯文本文件"""
    # title.txt
    title_path = publish_dir / "title.txt"
    with open(title_path, "w", encoding="utf-8") as f:
        f.write(input_data["title"])
    logging.info(f"生成 title.txt: {title_path}")

    # body.txt
    body_path = publish_dir / "body.txt"
    with open(body_path, "w", encoding="utf-8") as f:
        f.write(input_data["body"])
    logging.info(f"生成 body.txt: {body_path}")

    # hashtags.txt
    hashtags_path = publish_dir / "hashtags.txt"
    with open(hashtags_path, "w", encoding="utf-8") as f:
        for tag in input_data["hashtags"]:
            f.write(f"{tag}\n")
    logging.info(f"生成 hashtags.txt: {hashtags_path}")


def generate_checklist(publish_dir: Path, input_data: dict):
    """
    生成 checklist.md 文件
    用于人工审核和发布的检查清单，包含标题、正文、话题标签和检查项
    """
    content_id = input_data.get("content_id", "")
    # 处理 scheduled_at 字段，默认为 "未设置"
    scheduled_at = input_data.get("scheduled_at", "未设置")
    if not scheduled_at:
        scheduled_at = "未设置"

    title = input_data.get("title", "")
    body = input_data.get("body", "")
    hashtags = input_data.get("hashtags", [])
    # 将话题标签列表转换为空格分隔的字符串
    hashtags_str = " ".join(hashtags) if hashtags else ""

    checklist_content = f"""# 小红书发布清单 — {content_id}

建议发布时间：{scheduled_at}

## 标题（复制）
{title}

## 正文（复制）
{body}

## 话题标签（复制）
{hashtags_str}

## 检查项
- [ ] 图片已下载
- [ ] 标题无错别字
- [ ] 正文通顺
- [ ] 话题标签正确
- [ ] 图片顺序正确
- [ ] 发布时间确认
"""

    checklist_path = publish_dir / "checklist.md"
    with open(checklist_path, "w", encoding="utf-8") as f:
        f.write(checklist_content)
    logging.info(f"生成 checklist.md: {checklist_path}")


def generate_manifest(publish_dir: Path, input_data: dict):
    """生成 manifest.json 文件"""
    manifest_data = input_data.copy()
    manifest_data["package_created_at"] = datetime.now().isoformat()

    manifest_path = publish_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, ensure_ascii=False, indent=2)
    logging.info(f"生成 manifest.json: {manifest_path}")


def copy_assets(job_dir: Path, publish_dir: Path, input_data: dict) -> int:
    """
    复制图片资源到 assets 目录
    - 如果图片文件存在，复制到 assets 目录
    - 如果图片文件不存在，创建 .missing 占位文件
    - 返回成功复制的图片数量
    """
    assets = input_data.get("assets", [])
    assets_dir = publish_dir / "assets"
    copied_count = 0
    total_assets = len(assets)

    if not assets:
        logging.info("assets 数组为空，不复制任何资源")
        return copied_count

    # 遍历所有资源，处理图片复制和缺失文件
    for idx, asset in enumerate(assets, 1):
        if asset.get("type") != "image":
            logging.warning(f"跳过非图片资源: {asset}")
            continue

        asset_path = asset.get("path", "")
        if not asset_path:
            logging.warning("资源路径为空，跳过")
            continue

        # 解析相对路径，支持 "./" 前缀
        source_path = job_dir / asset_path.lstrip("./")

        if not source_path.exists():
            filename = source_path.name
            missing_path = assets_dir / f"{filename}.missing"
            with open(missing_path, "w", encoding="utf-8") as f:
                f.write(f"原始路径: {asset_path}\n文件缺失，请检查上游图片生成是否完成\n")
            logging.warning(f"[{idx}/{total_assets}] 图片文件不存在: {source_path}，创建占位文件: {missing_path}")
            continue

        # 复制文件到 assets 目录
        dest_path = assets_dir / source_path.name
        shutil.copy2(source_path, dest_path)
        logging.info(f"[{idx}/{total_assets}] 复制图片: {source_path} -> {dest_path}")
        copied_count += 1

    return copied_count


def core_logic(job_dir: Path, input_data: dict) -> dict:
    """
    核心业务逻辑：打包小红书内容到发布目录
    处理流程：
    1. 创建发布包目录结构
    2. 生成纯文本文件（title.txt, body.txt, hashtags.txt）
    3. 生成发布检查清单（checklist.md）
    4. 生成元数据文件（manifest.json）
    5. 复制图片资源到 assets 目录
    6. 统计生成的文件数量
    """
    # 1. 创建发布包目录
    publish_dir = create_publish_directory(job_dir)

    # 2. 生成纯文本文件
    generate_text_files(publish_dir, input_data)

    # 3. 生成 checklist.md
    generate_checklist(publish_dir, input_data)

    # 4. 生成 manifest.json
    generate_manifest(publish_dir, input_data)

    # 5. 复制图片资源
    assets_copied = copy_assets(job_dir, publish_dir, input_data)

    # 6. 统计文件数量（5个核心文件 + 成功复制的图片数量）
    # 核心5文件: title.txt, body.txt, hashtags.txt, checklist.md, manifest.json
    files_count = 5 + assets_copied

    return {
        "publish_package_path": str(publish_dir),
        "files_count": files_count
    }


def main():
    parser = argparse.ArgumentParser(description="Skill: xhs-publish-package")
    parser.add_argument("--job-dir", required=True, help="Job directory path")
    args = parser.parse_args()

    job_dir = Path(args.job_dir)

    # 确保日志目录存在
    job_dir.mkdir(parents=True, exist_ok=True)

    setup_logging(job_dir)
    logging.info(f"Starting skill, job_dir: {job_dir}")

    try:
        # 加载并验证输入
        input_data = load_input(job_dir)
        logging.info("成功加载 input.json")

        validate_input(input_data)
        logging.info("输入数据验证通过")

        # 执行核心逻辑
        result = core_logic(job_dir, input_data)

        # 写入成功输出
        write_output(job_dir, "xhs_publish_package", result)
        logging.info("Skill completed successfully")

        sys.exit(0)
    except FileNotFoundError as e:
        logging.error(f"文件未找到: {e}")
        write_error(job_dir, str(e))
        sys.exit(1)
    except ValueError as e:
        logging.error(f"输入数据错误: {e}")
        write_error(job_dir, str(e))
        sys.exit(1)
    except Exception as e:
        logging.error(f"Skill failed: {e}", exc_info=True)
        write_error(job_dir, str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()