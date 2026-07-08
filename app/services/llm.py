"""Shared LLM calling utility. All agent modules use this."""

import json
import logging
import os

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=os.getenv("LLM_API_KEY", ""),
            base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
        )
    return _client


async def call_llm(
    system: str,
    user: str,
    *,
    model: str | None = None,
    response_json: bool = False,
    max_retries: int = 1,
) -> str:
    """Call LLM with system + user message. Returns raw text or JSON string."""
    client = _get_client()
    model = model or os.getenv("LLM_MODEL", "qwen-plus")

    kwargs: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if response_json:
        kwargs["response_format"] = {"type": "json_object"}

    for attempt in range(max_retries + 1):
        try:
            resp = await client.chat.completions.create(**kwargs)
            content = resp.choices[0].message.content or ""
            if response_json:
                json.loads(content)  # validate
            return content
        except json.JSONDecodeError:
            if attempt < max_retries:
                logger.warning("LLM returned invalid JSON, retrying (attempt %d)", attempt + 1)
                continue
            logger.error("LLM JSON parse failed after retries")
            return content
        except Exception as e:
            if attempt < max_retries:
                logger.warning("LLM call failed: %s, retrying", e)
                continue
            raise

    return ""
