# Platform Preference Profiler

Analyze high-performing content samples from different platforms (Xiaohongshu, Douyin, WeChat) and generate platform preference profiles using V2 Schema.

## When to Use

- Generate or update platform preference profiles based on real content samples
- Analyze what content styles perform well on each platform
- Create data-driven guidance for content generation across platforms

## Input

Place `input.json` in the job directory with the following structure:

```json
{
  "content_id": "PROF-xxx",
  "job_id": "JOB-xxx",
  "platforms": ["xhs", "douyin", "wechat"],
  "samples_dir": ".data/samples",
  "output_dir": ".data/profiles"
}
```

## Sample Data Format

Each platform should have sample files in `.data/samples/{platform}/sample_xxx.json`:

```json
{
  "sample_id": "XHS-001",
  "platform": "xhs",
  "collected_at": "2026-07-21T10:00:00+08:00",
  "source_url": "https://www.xiaohongshu.com/discovery/item/...",
  "title": "Sample Title",
  "body": "Sample content body...",
  "hashtags": ["#tag1", "#tag2"],
  "cover_description": "Cover image description",
  "metrics": {
    "likes": 1000,
    "comments": 100,
    "collects": 500,
    "shares": 50
  },
  "content_type": "经验分享",
  "image_count": 5
}
```

## Output

Generates `platform-preference-profiler.json` in the job directory with profile index, and individual profile files in `.data/profiles/{platform}_profile.json`.

## V2 Profile Schema

Each platform profile contains:

- `pf`: Platform identifier (xhs/douyin/wechat)
- `gen_at`: Generation timestamp
- `v`: Schema version
- `conf`: Confidence score (0-1)
- `s_cnt`: Sample count
- `s_ids`: Sample IDs used
- `topic`: Topic preferences
- `lang`: Language style preferences
- `vis`: Visual style preferences
- `struct`: Content structure preferences
- `forbid`: Forbidden content list
- `forbid_level`: Restriction level

## Usage

```bash
python main.py --job-dir <job_directory>
python main.py --job-dir <job_directory> --force
python main.py --job-dir <job_directory> --incremental
```

## Environment Variables

- `LLM_API_KEY`: OpenAI-compatible API key
- `LLM_BASE_URL`: API base URL
- `LLM_MODEL`: Model name to use

## Profile Expiry

Profiles expire after 7 days. Use `--force` to regenerate regardless of age.
