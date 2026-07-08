# content-generate-xhs

Generate Xiaohongshu-ready copy from a structured job directory through a four-step OpenAI-compatible LLM pipeline.

## Input

Run with `--job-dir`. The directory must contain `input.json`:

```json
{
  "content_id": "content-id",
  "job_id": "job-id",
  "topic": "选题",
  "column": "栏目",
  "materials": [],
  "brand": {
    "tone": "年轻真诚",
    "audience": "目标读者"
  }
}
```

## Environment

Set an OpenAI-compatible chat completions endpoint:

```powershell
$env:LLM_API_KEY="..."
$env:LLM_BASE_URL="https://api.openai.com/v1"
$env:LLM_MODEL="gpt-4o-mini"
```

## Usage

```powershell
python main.py --job-dir E:\path\to\job
```

The command writes `content_generate_xhs.json` into the job directory. On failure it writes `error.json` and exits non-zero.

## Pipeline

1. `prompts/step1_analyze.md`: analyze the topic into three angles.
2. `prompts/step2_titles.md`: generate three title options and select one.
3. `prompts/step3_body.md`: draft 500-800 Chinese characters, hashtags, and cover text.
4. `prompts/step4_review.md`: review, score, and repair the draft, then emit final JSON.

Every step reads its prompt from disk, requests `response_format={"type":"json_object"}`, and retries once if JSON parsing fails. The final output includes `pipeline_log` with duration and token usage for every step.
