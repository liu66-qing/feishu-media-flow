import argparse
import json
import os
from datetime import datetime
from pathlib import Path
import re
import html
import urllib.parse
import urllib.request

from openai import OpenAI

SKILL_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = SKILL_DIR / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "system.md"
USER_TEMPLATE_PATH = PROMPTS_DIR / "user_template.md"

def clean_html(raw_html):
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", raw_html)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?s)<.*?>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def web_fetch(url, prompt="", max_chars=8000):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; media-workflow/1.0)"
        }
    )

    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read()

    try:
        page = raw.decode("utf-8")
    except UnicodeDecodeError:
        page = raw.decode("utf-8", errors="ignore")

    text = clean_html(page)

    if len(text) > max_chars:
        text = text[:max_chars] + "...[truncated]"

    return {
        "url": url,
        "prompt": prompt,
        "content": text
    }


def web_search(query, max_results=5):
    search_url = "https://duckduckgo.com/html/?" + urllib.parse.urlencode({
        "q": query
    })

    req = urllib.request.Request(
        search_url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; media-workflow/1.0)"
        }
    )

    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read()

    page = raw.decode("utf-8", errors="ignore")

    results = []
    pattern = re.compile(
        r'<a rel="nofollow" class="result__a" href="(.*?)">(.*?)</a>',
        re.S
    )

    for href, title_html in pattern.findall(page):
        title = clean_html(title_html)

        parsed_href = html.unescape(href)
        parsed = urllib.parse.urlparse(parsed_href)
        params = urllib.parse.parse_qs(parsed.query)

        if "uddg" in params:
            url = params["uddg"][0]
        else:
            url = parsed_href

        results.append({
            "title": title,
            "url": url
        })

        if len(results) >= max_results:
            break

    return {
        "query": query,
        "results": results
    }

def run_tool_call(tool_call):
    name = tool_call.function.name
    args = json.loads(tool_call.function.arguments or "{}")

    if name == "WebFetch":
        return web_fetch(
            url=args.get("url", ""),
            prompt=args.get("prompt", "")
        )

    if name == "WebSearch":
        return web_search(
            query=args.get("query", "")
        )

    return {
        "error": f"Unsupported tool: {name}"
    }

def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def call_llm(prompt, system="", model=None):
    model = model or os.getenv("LLM_MODEL", "gpt-5.4-mini")
    client = OpenAI(
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
    )

    tools = [
        {
            "type": "function",
            "function": {
                "name": "WebFetch",
                "description": "Fetch text content from a web page URL.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "prompt": {"type": "string"}
                    },
                    "required": ["url"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "WebSearch",
                "description": "Search the web and return result titles and URLs.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"}
                    },
                    "required": ["query"]
                }
            }
        }
    ]

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt}
    ]

    for _ in range(3):
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            max_tokens=8192
        )

        message = resp.choices[0].message
        tool_calls = message.tool_calls or []
        content = message.content or ""

        if tool_calls:
            messages.append({
                "role": "assistant",
                "content": content,
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "type": tool_call.type,
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments
                        }
                    }
                    for tool_call in tool_calls
                ]
            })

            for tool_call in tool_calls:
                try:
                    tool_result = run_tool_call(tool_call)
                except Exception as e:
                    tool_result = {
                        "error": str(e),
                        "tool": tool_call.function.name
                    }

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result, ensure_ascii=False)
                })

            continue

        if content.strip():
            return content

    final_resp = client.chat.completions.create(
        model=model,
        messages=messages + [
            {
                "role": "user",
                "content": "请基于以上工具结果生成最终严格合法 JSON，不要输出解释文字。"
            }
        ],
        tools=tools,
        tool_choice="none",
        max_tokens=8192
    )

    return final_resp.choices[0].message.content or ""


def read_text(path):
    with path.open("r", encoding="utf-8") as f:
        return f.read()


def render_template(template, values):
    result = template
    for key, value in values.items():
        result = result.replace("{{" + key + "}}", str(value))
    return result


def parse_llm_json(raw):
    text = raw.strip()

    if text.startswith("```json"):
        text = text.removeprefix("```json").removesuffix("```").strip()
    elif text.startswith("```"):
        text = text.removeprefix("```").removesuffix("```").strip()

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]

    return json.loads(text)

def build_title_options(topic):
    return [
        f"{topic}：一篇给普通读者的观察",
        f"重新理解{topic}",
        f"关于{topic}，这几个变化值得关注"
    ]


def build_sections(topic, materials):
    material_text = "；".join(materials) if materials else "暂无补充素材"

    return [
        {
            "heading": "引言：为什么现在讨论这个话题",
            "brief": f"说明为什么现在需要讨论「{topic}」。"
        },
        {
            "heading": "背景现状：先把信息放回语境里",
            "brief": f"结合已有素材梳理主题背景：{material_text}。"
        },
        {
            "heading": "关键观察：读者真正需要带走什么",
            "brief": "总结读者最需要关注的变化、机会或问题。"
        },
        {
            "heading": "写作建议：让文章更像公众号，而不是资料整理",
            "brief": "给出面向普通读者的理解方式和下一步建议。"
        }
    ]


def build_image_plan(topic, sections):
    headings = [
        str(item.get("heading", "")).strip()
        for item in sections
        if isinstance(item, dict) and str(item.get("heading", "")).strip()
    ]
    first_heading = headings[1] if len(headings) > 1 else "背景现状"
    second_heading = headings[2] if len(headings) > 2 else "关键变化"
    return [
        {
            "role": "cover",
            "title": topic,
            "prompt": f"{topic}，中国大学校园主题编辑海报，主题视觉明确、明亮、有冲击力",
            "target_heading": "公众号封面",
            "alt_text": f"{topic}文章封面",
        },
        {
            "role": "inline",
            "title": first_heading,
            "prompt": f"{topic}的{first_heading}，中国大学校园和大学生场景，适合公众号横版配图",
            "target_heading": first_heading,
            "alt_text": f"{topic}：{first_heading}",
        },
        {
            "role": "inline",
            "title": second_heading,
            "prompt": f"{topic}的{second_heading}，中国大学校园和大学生场景，亮眼的信息海报构图",
            "target_heading": second_heading,
            "alt_text": f"{topic}：{second_heading}",
        },
    ]


def normalize_image_plan(value, topic, sections):
    raw_items = value if isinstance(value, list) else []
    normalized = []
    cover_seen = False
    inline_count = 0
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        role = "cover" if str(raw.get("role", "")).lower() == "cover" else "inline"
        if role == "cover":
            if cover_seen:
                continue
            cover_seen = True
        else:
            inline_count += 1
            if inline_count > 2:
                continue
        normalized.append({
            "role": role,
            "title": str(raw.get("title") or raw.get("target_heading") or topic).strip()[:42],
            "prompt": str(raw.get("prompt") or topic).strip(),
            "target_heading": str(raw.get("target_heading") or "关键变化").strip(),
            "alt_text": str(raw.get("alt_text") or raw.get("title") or topic).strip(),
        })

    fallback = build_image_plan(topic, sections)
    if not cover_seen:
        normalized.insert(0, fallback[0])
    existing_targets = {item["target_heading"] for item in normalized if item["role"] == "inline"}
    for item in fallback[1:]:
        if sum(plan["role"] == "inline" for plan in normalized) >= 2:
            break
        if item["target_heading"] not in existing_targets:
            normalized.append(item)
    return normalized


def build_body_md(topic, column, materials, reference_urls, target_length):
    materials_md = "\n".join(f"- {item}" for item in materials) if materials else "- [需核实] 暂无明确素材"
    urls_md = "\n".join(f"- {url}" for url in reference_urls) if reference_urls else "- [需核实] 暂无参考链接"

    return f"""# {topic}

## 引言：为什么现在讨论这个话题

在「{column}」这个栏目里，我们关注的不只是一个话题本身，更关注它背后的变化、原因和可能影响。围绕「{topic}」，读者最需要知道的是：哪些信息已经比较明确，哪些判断还需要继续核实，哪些变化可能和自己有关。

一篇好的公众号文章，不应该只是把资料重新排列一遍。它需要先帮读者降低理解门槛，再把复杂信息拆成几个可以判断的问题。对于「{topic}」这样的选题，尤其需要避免两种写法：一种是把未经确认的信息写得过于确定，另一种是堆砌概念但没有观点。

因此，本文会先整理已有素材，再从背景、变化和建议三个角度展开。涉及数据、趋势或年份判断的部分，如果当前素材不足，需要保留「[需核实]」标注。

## 背景现状：先把信息放回语境里

目前可参考的素材包括：

{materials_md}

这些素材可以帮助我们搭建基本判断，但它们并不等于完整结论。比如，官方博客通常更适合确认版本变化、社区计划和正式公告；趋势榜单更适合观察短期热度；开发者讨论则能反映真实使用体验，但也容易受到样本范围影响。

所以在写作时，需要把不同来源放在不同位置使用。确定性强的信息，可以作为背景事实；带有个人体验或社区情绪的信息，更适合作为观察线索；如果涉及具体数字、排名变化或行业判断，则应该补充来源，或者明确标注「[需核实]」。

这样处理的好处是，文章不会显得空泛，也不会把暂时无法确认的内容包装成确定结论。

## 关键观察：读者真正需要带走什么

讨论「{topic}」时，可以先抓住三个观察角度。

第一，变化是否真的发生了。很多话题看起来热闹，但可能只是短期讨论增加，并不代表生态、用户或行业结构已经发生明显变化。因此，文章中如果要写“变化”，最好说明变化来自哪里，是官方动作、社区反馈，还是项目数量、工具链体验等可观察信号。

第二，这些变化影响谁。公众号读者不一定都是专业从业者，所以文章需要把影响说清楚。比如，它可能影响学习者的技术选择，也可能影响团队的工具评估，还可能影响内容创作者对技术趋势的判断。不同读者关心的问题不同，文章要尽量把结论落到具体场景。

第三，哪些判断还不能说得太满。如果素材只来自少量讨论，就不适合写成确定趋势。如果缺少权威来源，就应该保留空间。使用「[需核实]」不是削弱文章，而是让文章更可信。

## 写作建议：让文章更像公众号，而不是资料整理

如果要把「{topic}」写成一篇可读的公众号文章，可以采用“问题—背景—观察—建议”的结构。

开头先提出一个读者能理解的问题，例如“这个变化为什么值得关注”。中间部分再解释背景，不要一开始就堆概念。进入主体后，每个小节只解决一个核心问题，并尽量用短段落表达。结尾部分则回到读者行动：他们可以继续关注什么、需要补充哪些资料、如何避免误判。

这种结构的优势是阅读负担较低。读者即使不了解全部背景，也能顺着文章看到重点。对于技术类或趋势类选题来说，这比单纯罗列素材更适合公众号场景。

## 对读者的建议

如果你正在关注「{topic}」，可以先从三个问题开始：

1. 这个话题和我有什么关系？
2. 目前有哪些信息是确定的？
3. 哪些结论还需要更多资料支持？

当这三个问题都能回答清楚时，文章的判断会更稳。如果暂时回答不清楚，也不必强行下结论，可以把它写成阶段性观察。

## 参考资料

{urls_md}

## 结语

总体来看，「{topic}」值得继续观察。本文先基于现有材料做出初步整理，后续如果有新的信息或更可靠来源，可以继续补充更新。

对公众号内容来说，可靠比热闹更重要。尤其是涉及趋势、生态、数据和年份变化的文章，更需要把事实、判断和建议分开写。这样既能保持内容的可读性，也能减少夸大表达带来的风险。
"""

def generate_wechat_content_with_llm(input_data):
    if not os.getenv("LLM_API_KEY"):
        raise RuntimeError("LLM_API_KEY is not set")

    system = read_text(SYSTEM_PROMPT_PATH)
    template = read_text(USER_TEMPLATE_PATH)

    prompt = render_template(template, {
        "topic": input_data.get("topic", ""),
        "column": input_data.get("column", ""),
        "materials": json.dumps(input_data.get("materials", []), ensure_ascii=False),
        "reference_urls": json.dumps(input_data.get("reference_urls", []), ensure_ascii=False),
        "target_length": input_data.get("target_length", 1500)
    })

    raw = call_llm(prompt, system=system)

    if not raw.strip():
        raise ValueError("LLM returned empty content")

    try:
        data = parse_llm_json(raw)
    except Exception as e:
        preview = raw[:1000]
        raise ValueError(f"Failed to parse LLM JSON: {e}; raw_preview={preview}")

    required_fields = [
        "title_options",
        "selected_title",
        "summary",
        "body_md",
        "sections",
        "cta",
        "risk_notes"
    ]

    for field in required_fields:
        if field not in data:
            raise ValueError(f"LLM output missing field: {field}")

    data["image_plan"] = normalize_image_plan(
        data.get("image_plan"),
        input_data.get("topic", ""),
        data.get("sections", []),
    )
    data["llm_enabled"] = True
    data["llm_error"] = ""

    return data

def generate_wechat_content(input_data):
    topic = input_data.get("topic", "")
    column = input_data.get("column", "内容观察")
    materials = input_data.get("materials", [])
    reference_urls = input_data.get("reference_urls", [])
    target_length = input_data.get("target_length", 1500)

    title_options = build_title_options(topic)
    selected_title = title_options[0]
    sections = build_sections(topic, materials)
    body_md = build_body_md(topic, column, materials, reference_urls, target_length)

    return {
        "title_options": title_options,
        "selected_title": selected_title,
        "summary": f"本文围绕{topic}，从背景、关键变化和读者建议三个角度进行整理，并标注需核实信息。",
        "body_md": body_md,
        "sections": sections,
        "image_plan": build_image_plan(topic, sections),
        "cta": "关注我们，持续获取更多内容观察。",
        "risk_notes": [
            "涉及具体数据、排名或趋势判断时，需要补充可靠来源。",
            "当前版本为模板生成，正式发布前建议人工润色。"
        ]
    }


def run(job_dir):
    job_dir = Path(job_dir)
    input_path = job_dir / "input.json"
    output_path = job_dir / "content-generate-wechat.json"
    logs_path = job_dir / "logs.txt"
    error_path = job_dir / "error.json"

    try:
        input_data = load_json(input_path)
        try:
            data = generate_wechat_content_with_llm(input_data)
        except Exception as llm_error:
            data = generate_wechat_content(input_data)
            data["llm_enabled"] = False
            data["llm_error"] = str(llm_error)

        result = {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "content_id": input_data.get("content_id", ""),
            "data": data
        }

        write_json(output_path, result)

        logs_path.write_text(
            "[success] content-generate-wechat finished.\n",
            encoding="utf-8"
        )

        return 0

    except Exception as e:
        error = {
            "status": "failed",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }
        write_json(error_path, error)
        return 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-dir", required=True, help="Path to job directory containing input.json")
    args = parser.parse_args()

    exit_code = run(args.job_dir)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
