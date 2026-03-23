"""Unified EvoLink API client with built-in retry logic."""

from __future__ import annotations

import asyncio
import json
import logging

import httpx

logger = logging.getLogger("app.evolink_api")

_DEFAULT_TIMEOUT = 120.0
_DEFAULT_MAX_RETRIES = 3
_RETRY_BACKOFF_BASE = 2.0  # seconds: 2, 4, 8 ...


def _mask_key(api_key: str) -> str:
    return f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"


def _extract_text(data: dict) -> str:
    """Extract text from a Gemini-style response."""
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"Unexpected EvoLink response format: {data}") from exc


async def call_evolink_gemini_api(
    *,
    api_base_url: str,
    api_key: str,
    model_name: str,
    prompt: str,
    temperature: float = 0.3,
    video_url: str | None = None,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    timeout: float = _DEFAULT_TIMEOUT,
) -> str:
    """
    Call EvoLink API (Gemini protocol) with automatic retry.

    Supports both text-only and video+text calls.
    Returns the extracted text content.

    Raises:
        httpx.HTTPStatusError: after all retries exhausted
        ValueError: if response format is unexpected
    """
    url = f"{api_base_url.rstrip('/')}/v1beta/models/{model_name}:generateContent"

    # Build parts: optional video + text
    parts: list[dict] = []
    if video_url:
        parts.append({"fileData": {"mimeType": "video/mp4", "fileUri": video_url}})
    parts.append({"text": prompt})

    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"temperature": temperature},
    }

    masked_key = _mask_key(api_key)
    logger.info(
        "EvoLink API request: model=%s, api_key=%s, video=%s",
        model_name, masked_key, bool(video_url),
    )
    logger.info("EvoLink API prompt: %s", prompt[:400])

    last_exc: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    url,
                    json=payload,
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if not resp.is_success:
                    logger.error(
                        "EvoLink API error (attempt %d/%d): status=%d, body=%s",
                        attempt, max_retries, resp.status_code, resp.text[:500],
                    )
                resp.raise_for_status()
                data = resp.json()

            logger.info("EvoLink API raw response: %s", json.dumps(data, ensure_ascii=False)[:1000])
            text = _extract_text(data)
            logger.info("EvoLink API extracted text: %s", text[:500])
            return text

        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                wait = _RETRY_BACKOFF_BASE ** attempt
                logger.warning(
                    "EvoLink API attempt %d/%d failed: %s — retrying in %.1fs",
                    attempt, max_retries, exc, wait,
                )
                await asyncio.sleep(wait)
            else:
                logger.error(
                    "EvoLink API attempt %d/%d failed (giving up): %s",
                    attempt, max_retries, exc,
                )

    raise last_exc  # type: ignore[misc]
