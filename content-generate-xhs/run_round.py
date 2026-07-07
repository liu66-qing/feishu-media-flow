import argparse
import json
import logging
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path


def detect_target_dir(results_root: Path):
    results_root.mkdir(parents=True, exist_ok=True)
    v_dirs = []
    for d in results_root.iterdir():
        if d.is_dir() and re.match(r"v\d+_test$", d.name):
            n = int(d.name[1:].split("_")[0])
            v_dirs.append((n, d))
    if not v_dirs:
        v_max, r_max = 0, 0
    else:
        v_max, v_max_dir = max(v_dirs, key=lambda x: x[0])
        r_dirs = []
        for d in v_max_dir.iterdir():
            if d.is_dir() and re.match(r"round\d+$", d.name):
                m = int(d.name[5:])
                r_dirs.append((m, d))
        r_max = max((m for m, _ in r_dirs), default=0)
    if r_max < 3:
        v_target = v_max if v_max > 0 else 1
        r_target = r_max + 1
    else:
        v_target = v_max + 1
        r_target = 1
    v_dir = results_root / f"v{v_target}_test"
    round_dir = v_dir / f"round{r_target}"
    if round_dir.exists() and any(round_dir.iterdir()):
        raise RuntimeError(f"目标目录已存在且非空: {round_dir}")
    round_dir.mkdir(parents=True, exist_ok=True)
    return v_dir, round_dir, v_target, r_target


def setup_round_logging(round_dir: Path):
    log_file = round_dir / "run.log"
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    for h in list(logger.handlers):
        logger.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


def reset_job_logging(job_dir: Path):
    logger = logging.getLogger()
    for h in list(logger.handlers):
        logger.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass
    log_file = job_dir / "logs.txt"
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)


def restore_round_logging(round_dir: Path):
    logger = logging.getLogger()
    for h in list(logger.handlers):
        logger.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass
    log_file = round_dir / "run.log"
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)


def copy_inputs(input_dir: Path, round_dir: Path):
    if not input_dir.exists():
        raise FileNotFoundError(f"输入目录不存在: {input_dir}")
    pattern = re.compile(r"^input_(\d+)\.json$")
    files = []
    for f in sorted(input_dir.iterdir()):
        m = pattern.match(f.name)
        if m and f.is_file():
            files.append((int(m.group(1)), f))
    files.sort(key=lambda x: x[0])
    if len(files) < 5:
        raise RuntimeError(f"输入文件不足5个，仅找到 {len(files)} 个: {[f.name for _, f in files]}")
    test_dirs = []
    for idx, (num, src) in enumerate(files[:5], start=1):
        test_dir = round_dir / f"test_{idx:02d}"
        test_dir.mkdir(parents=True, exist_ok=True)
        dst = test_dir / "input.json"
        shutil.copy2(src, dst)
        test_dirs.append((test_dir, num, src.name))
    return test_dirs


def run_single(test_dir: Path, skill_dir: Path, retries: int, logger: logging.Logger):
    sys.path.insert(0, str(skill_dir))
    from main import generate_xhs_content, write_output, write_error, load_input, SKILL_NAME, setup_logging
    sys.path.pop(0)

    reset_job_logging(test_dir)
    logging.info(f"开始处理: {test_dir.name}")
    try:
        input_data = load_input(test_dir)
    except Exception as e:
        logging.error(f"读取 input.json 失败: {e}")
        write_error(test_dir, f"读取输入失败: {e}")
        return False, None, str(e)

    required_fields = ["content_id", "job_id", "topic"]
    missing = [f for f in required_fields if f not in input_data]
    if missing:
        msg = f"缺少必填字段: {', '.join(missing)}"
        logging.error(msg)
        write_error(test_dir, msg)
        return False, None, msg

    last_err = None
    for attempt in range(retries + 1):
        try:
            result = generate_xhs_content(input_data, skill_dir)
            write_output(test_dir, SKILL_NAME, result)
            logging.info(f"处理成功: {test_dir.name}")
            return True, result, None
        except Exception as e:
            last_err = e
            logging.warning(f"处理失败 (尝试 {attempt+1}/{retries+1}): {e}")
            if attempt < retries:
                time.sleep(2)
    write_error(test_dir, str(last_err))
    logging.error(f"处理最终失败: {test_dir.name}: {last_err}")
    return False, None, str(last_err)


def evaluate_hard_metrics(data: dict):
    issues = []
    title_options = data.get("title_options", [])
    body = data.get("body", "")
    hashtags = data.get("hashtags", [])
    cover_text = data.get("cover_text", "")
    selected = data.get("selected_title", "")
    risk_notes = data.get("risk_notes", None)

    metrics = {}
    metrics["title_count_ok"] = len(title_options) == 3
    metrics["title_count"] = len(title_options)
    if not metrics["title_count_ok"]:
        issues.append(f"标题数量{len(title_options)}（应为3）")

    title_lens = [len(t) for t in title_options]
    metrics["title_lens"] = title_lens
    bad_titles = [(t, l) for t, l in zip(title_options, title_lens) if not (12 <= l <= 25)]
    metrics["title_len_ok"] = len(bad_titles) == 0
    if bad_titles:
        issues.append(f"标题长度不合规: {[(t, l) for t, l in bad_titles]}")

    body_len = len(body)
    metrics["body_len"] = body_len
    metrics["body_len_ok"] = 400 <= body_len <= 900
    if not metrics["body_len_ok"]:
        issues.append(f"正文{body_len}字（建议500-800）")

    tag_count = len(hashtags)
    metrics["tag_count"] = tag_count
    metrics["tag_count_ok"] = 5 <= tag_count <= 8
    if not metrics["tag_count_ok"]:
        issues.append(f"标签数量{tag_count}（应为5-8）")

    tag_hash_ok = all(isinstance(t, str) and t.startswith("#") for t in hashtags)
    metrics["tag_hash_ok"] = tag_hash_ok
    if not tag_hash_ok:
        issues.append("存在不以 # 开头的标签")

    cover_len = len(cover_text)
    metrics["cover_len"] = cover_len
    metrics["cover_len_ok"] = 10 <= cover_len <= 12
    if not metrics["cover_len_ok"]:
        issues.append(f"封面文案{cover_len}字（要求10-12）")

    metrics["selected_ok"] = selected in title_options
    if not metrics["selected_ok"]:
        issues.append("selected_title 不在 title_options 中")

    metrics["risk_notes_ok"] = isinstance(risk_notes, list)
    if not metrics["risk_notes_ok"]:
        issues.append("risk_notes 不是数组")

    risk_words = ["最", "第一", "保证", "100%", "绝对", "必须"]
    risk_hits = []
    for w in risk_words:
        positions = [m.start() for m in re.finditer(re.escape(w), body)]
        for pos in positions:
            start = max(0, pos - 8)
            end = min(len(body), pos + len(w) + 8)
            ctx = body[start:end].replace("\n", " ")
            risk_hits.append((w, ctx))
    metrics["risk_hits"] = risk_hits

    para_count = len([p for p in body.split("\n") if p.strip()])
    metrics["para_count"] = para_count

    return metrics, issues


def generate_report(round_dir: Path, results: list, v_num: int, r_num: int, model: str, input_dir: Path):
    report_path = round_dir / "quality_report.md"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    themes = {}
    for r in results:
        try:
            with open(r["test_dir"] / "input.json", "r", encoding="utf-8") as f:
                inp = json.load(f)
            themes[r["idx"]] = inp.get("topic", r["test_dir"].name)
        except Exception:
            themes[r["idx"]] = r["test_dir"].name

    lines = []
    lines.append(f"# content-generate-xhs v{v_num} round{r_num} 测试质量报告")
    lines.append("")
    lines.append("## 测试基本信息")
    lines.append("")
    lines.append("| 项目 | 内容 |")
    lines.append("|------|------|")
    lines.append(f"| 技能名称 | content-generate-xhs（小红书图文文案生成） |")
    lines.append(f"| Prompt 版本 | v{v_num} |")
    lines.append(f"| 测试轮次 | round{r_num} |")
    lines.append(f"| 测试日期 | {now} |")
    lines.append(f"| LLM 模型 | {model or '（未检测到）'} |")
    lines.append(f"| 输入目录 | `{input_dir}` |")
    lines.append(f"| 测试样本数 | 5 个选题 × 1 次 = 5 条输出 |")
    lines.append(f"| 成功数量 | {sum(1 for r in results if r['success'])} / 5 |")
    lines.append("")

    lines.append("## 一、技术指标验证")
    lines.append("")
    lines.append("| 测试项 | 通过标准 | test_01<br>社团招新 | test_02<br>校园恋爱 | test_03<br>大学生创业 | test_04<br>大学生社交 | test_05<br>学习就业 |")
    lines.append("|--------|---------|:---:|:---:|:---:|:---:|:---:|")

    def cell(ok):
        return "✅" if ok else "⚠️"

    row_exit = ["退出码 0", "无 error.json"]
    row_json = ["JSON 格式", "json.loads 不报错"]
    row_status = ["status=success", "字段校验"]
    row_cid = ["content_id 一致", "与输入匹配"]
    row_tc = ["title_options 数量", "= 3 个"]
    row_tl = ["标题长度", "12-25 字"]
    row_sl = ["selected_title 有效", "在列表中"]
    row_bl = ["正文长度", "500-800 字"]
    row_hc = ["hashtags 数量", "5-8 个"]
    row_hh = ["标签格式", "以 # 开头"]
    row_cl = ["cover_text 长度", "10-12 字"]
    row_rn = ["risk_notes 类型", "数组"]

    for r in results:
        pass_check = {
            "exit": r["success"],
            "json": True,
            "status": True,
            "cid": True,
            "tc": True,
            "tl": True,
            "sl": True,
            "bl": True,
            "hc": True,
            "hh": True,
            "cl": True,
            "rn": True,
        }
        m = r.get("metrics")
        if m:
            pass_check["tc"] = m.get("title_count_ok", False)
            pass_check["tl"] = m.get("title_len_ok", False)
            pass_check["sl"] = m.get("selected_ok", False)
            pass_check["bl"] = m.get("body_len_ok", False)
            pass_check["hc"] = m.get("tag_count_ok", False)
            pass_check["hh"] = m.get("tag_hash_ok", False)
            pass_check["cl"] = m.get("cover_len_ok", False)
            pass_check["rn"] = m.get("risk_notes_ok", False)
        else:
            for k in pass_check:
                pass_check[k] = False
        r["_checks"] = pass_check

    for label, key in [
        ("退出码", "exit"), ("JSON 合法", "json"), ("status=success", "status"),
        ("content_id 一致", "cid"), ("标题数量=3", "tc"), ("标题长度12-25", "tl"),
        ("selected_title 有效", "sl"), ("正文长度", "bl"),
        ("标签数量5-8", "hc"), ("标签以 # 开头", "hh"),
        ("cover_text 10-12字", "cl"), ("risk_notes 数组", "rn"),
    ]:
        row = f"| {label} | 见左 |"
        for r in results:
            if not r["success"] and key != "exit":
                row += " — |"
            else:
                row += f" {cell(r['_checks'][key])} |"
        lines.append(row)

    lines.append("")
    lines.append("### 字段统计详情")
    lines.append("")
    lines.append("| 测试 | 主题 | 状态 | 标题数 | 标题长度 | 正文字数 | 标签数 | 封面字数 | 段落数 |")
    lines.append("|------|------|:---:|:---:|---------|:---:|:---:|:---:|:---:|")
    for r in results:
        theme = themes.get(r["idx"], r["test_dir"].name)
        short_theme = theme[:10] + ("…" if len(theme) > 10 else "")
        if not r["success"]:
            lines.append(f"| test_{r['idx']:02d} | {short_theme} | ❌失败 | — | — | — | — | — | — |")
            continue
        m = r["metrics"]
        lines.append(
            f"| test_{r['idx']:02d} | {short_theme} | ✅ | "
            f"{m['title_count']} | {m['title_lens']} | {m['body_len']} | "
            f"{m['tag_count']} | {m['cover_len']} | {m['para_count']} |"
        )
    lines.append("")

    lines.append("### 问题汇总")
    lines.append("")
    total_issues = 0
    for r in results:
        if not r["success"]:
            lines.append(f"- **test_{r['idx']:02d}** ❌ 运行失败: {r.get('error','')}")
            total_issues += 1
            continue
        if r["issues"]:
            total_issues += len(r["issues"])
            lines.append(f"- **test_{r['idx']:02d}** {themes.get(r['idx'],'')}:")
            for iss in r["issues"]:
                lines.append(f"  - ⚠️ {iss}")
    if total_issues == 0:
        lines.append("- ✅ 所有硬指标均通过，无格式问题。")
    lines.append("")

    lines.append("### 风险词初筛（绝对化词汇）")
    lines.append("")
    has_risk = False
    for r in results:
        if not r["success"] or not r.get("metrics"):
            continue
        hits = r["metrics"].get("risk_hits", [])
        if hits:
            has_risk = True
            lines.append(f"- **test_{r['idx']:02d}**:")
            for w, ctx in hits:
                lines.append(f"  - 「{w}」…{ctx}…")
    if not has_risk:
        lines.append("- ✅ 未发现明显绝对化词汇。")
    lines.append("")
    lines.append("> 注：此处为正则初筛，语义上合理的「第一排」「最近」等可能被误命中，需人工复核。")
    lines.append("")

    lines.append("## 二、肉眼质量评分【待人工填写】")
    lines.append("")
    lines.append("评分标准：1-5 分，每项 ≥3 分通过。")
    lines.append("")
    lines.append("| 测试 | 主题 | 内容深度 | 语言自然度 | 钩子强度 | 排版 | 整体 | 总分 |")
    lines.append("|------|------|:---:|:---:|:---:|:---:|:---:|:---:|")
    for r in results:
        theme = themes.get(r["idx"], "")
        short_theme = theme[:12] + ("…" if len(theme) > 12 else "")
        lines.append(f"| test_{r['idx']:02d} | {short_theme} |  |  |  |  |  |  |")
    lines.append("")
    lines.append("### 逐篇点评【待人工填写】")
    lines.append("")
    for r in results:
        theme = themes.get(r["idx"], "")
        lines.append(f"#### test_{r['idx']:02d} — {theme}")
        lines.append("")
        lines.append("**选中标题**：（待填）")
        lines.append("")
        lines.append("- 亮点：")
        lines.append("- 不足：")
        lines.append("")

    lines.append("## 三、综合结论【待人工填写】")
    lines.append("")
    lines.append("- 硬指标通过率：____")
    lines.append("- 肉眼均分：____")
    lines.append("- 本轮结论：____（通过 / 需迭代）")
    lines.append("- 下轮优化方向：")
    lines.append("  1. ")
    lines.append("  2. ")
    lines.append("")

    lines.append("## 附录：本轮产出文件清单")
    lines.append("")
    lines.append(f"```")
    lines.append(f"v{v_num}_test/round{r_num}/")
    lines.append(f"├── run.log")
    lines.append(f"├── quality_report.md")
    for i in range(1, 6):
        suffix = "/"
        lines.append(f"├── test_{i:02d}/")
        lines.append(f"│   ├── input.json")
        td = round_dir / f"test_{i:02d}"
        has_out = (td / "content-generate-xhs.json").exists()
        has_err = (td / "error.json").exists()
        if has_out:
            lines.append(f"│   ├── content-generate-xhs.json")
        if has_err:
            lines.append(f"│   ├── error.json")
        lines.append(f"│   └── logs.txt")
    lines.append(f"```")
    lines.append("")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="content-generate-xhs: run a full round of 5 tests")
    parser.add_argument("--input-dir", default=None, help="输入目录（默认 {skill-dir}/test/fixtures）")
    parser.add_argument("--no-report", action="store_true", help="不生成 quality_report.md")
    parser.add_argument("--retries", type=int, default=2, help="单个用例失败重试次数（默认2）")
    parser.add_argument("--skill-dir", default=None, help="skill 根目录（默认脚本所在目录）")
    parser.add_argument("--results-root", default=None, help="结果根目录（默认 {skill-dir}/test/results）")
    args = parser.parse_args()

    skill_dir = Path(args.skill_dir).resolve() if args.skill_dir else Path(__file__).parent.resolve()
    input_dir = Path(args.input_dir).resolve() if args.input_dir else skill_dir / "test" / "fixtures"
    results_root = Path(args.results_root).resolve() if args.results_root else skill_dir / "test" / "results"

    print(f"Skill 目录: {skill_dir}")
    print(f"输入目录  : {input_dir}")
    print(f"结果根目录: {results_root}")

    try:
        v_dir, round_dir, v_num, r_num = detect_target_dir(results_root)
    except Exception as e:
        print(f"❌ 目录检测失败: {e}")
        sys.exit(2)

    print(f"目标目录  : {round_dir}")
    print(f"版本/轮次 : v{v_num} / round{r_num}")

    logger = setup_round_logging(round_dir)
    logger.info(f"========== v{v_num}_test/round{r_num} 开始 ==========")
    logger.info(f"输入目录: {input_dir}")

    try:
        test_dirs = copy_inputs(input_dir, round_dir)
    except Exception as e:
        logger.error(f"准备输入失败: {e}")
        sys.exit(2)

    logger.info(f"已准备 {len(test_dirs)} 个测试目录")

    run_results = []
    for i, (test_dir, src_num, src_name) in enumerate(test_dirs, start=1):
        theme_short = src_name
        try:
            with open(test_dir / "input.json", "r", encoding="utf-8") as f:
                inp = json.load(f)
            theme_short = inp.get("topic", src_name)
        except Exception:
            pass
        logger.info(f"[{i}/5] 运行 {test_dir.name} <- {src_name} ({theme_short[:20]})")
        print(f"\n>>> [{i}/5] {test_dir.name}  主题: {theme_short[:30]}")
        success, data, error = run_single(test_dir, skill_dir, args.retries, logger)
        restore_round_logging(round_dir)

        record = {
            "idx": i,
            "test_dir": test_dir,
            "src_name": src_name,
            "theme": theme_short,
            "success": success,
            "error": error,
            "data": data,
            "issues": [],
            "metrics": None,
        }
        if success and data:
            metrics, issues = evaluate_hard_metrics(data)
            record["metrics"] = metrics
            record["issues"] = issues
        run_results.append(record)

    logger.info("========== 全部用例执行完毕 ==========")
    print(f"\n{'='*60}")
    print(f"  v{v_num}_test / round{r_num}  运行完成")
    print(f"{'='*60}")
    for r in run_results:
        if r["success"]:
            m = r["metrics"]
            extra = f"{m['body_len']}字 / {m['tag_count']}标签"
            flag = "✅" if not r["issues"] else "⚠️"
            print(f"  test_{r['idx']:02d}  {r['theme'][:18]:<20} {flag}  {extra}")
            if r["issues"]:
                for iss in r["issues"]:
                    print(f"            - {iss}")
        else:
            print(f"  test_{r['idx']:02d}  {r['theme'][:18]:<20} ❌  {r['error'][:50]}")
    ok_count = sum(1 for r in run_results if r["success"])
    print(f"\n  成功: {ok_count}/5")
    logger.info(f"成功: {ok_count}/5")

    if not args.no_report:
        model = __import__("os").getenv("LLM_MODEL", "gpt-5.4-mini")
        generate_report(round_dir, run_results, v_num, r_num, model, input_dir)
        print(f"  报告已生成: {round_dir / 'quality_report.md'}")
        logger.info(f"报告已生成: {round_dir / 'quality_report.md'}")
    else:
        print("  （已跳过质量报告生成）")
        logger.info("已跳过质量报告生成 (--no-report)")

    sys.exit(0 if ok_count == 5 else 1)


if __name__ == "__main__":
    main()