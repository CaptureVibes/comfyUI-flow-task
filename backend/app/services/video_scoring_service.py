"""AI video scoring service using EvoLink API."""
from __future__ import annotations

import asyncio
import logging
import re

import httpx

from app.models.system_setting import SystemSetting
from app.models.video_task_config import VideoTaskConfig

logger = logging.getLogger("app.video_scoring")


async def score_video_with_ai(
    *,
    video_url: str,
    config: VideoTaskConfig,
    system_settings: SystemSetting,
) -> tuple[float, float, float, str, str] | tuple[None, None, str]:
    """
    Perform two-round AI scoring on a video using EvoLink API.

    Args:
        video_url: CDN URL of the video to score
        config: VideoTaskConfig with round1/round2 settings
        system_settings: SystemSetting with evolink_api_key and evolink_api_base_url

    Returns:
        Tuple of (final_score, round1_score, round2_score, round1_reason, round2_reason) on success
        Tuple of (None, None, error_message) on failure
        Scores are 0-100 integers
    """
    api_key = system_settings.evolink_api_key
    api_base_url = system_settings.evolink_api_base_url

    if not api_key:
        logger.warning("EvoLink API key not configured, skipping AI scoring")
        return (None, None, "EvoLink API key 未配置")

    # Check if at least one round has a prompt
    has_round1 = config.round1_enabled and config.round1_prompt.strip()
    has_round2 = config.round2_enabled and config.round2_prompt.strip()

    if not has_round1 and not has_round2:
        error_msg = "AI 评分提示词为空，请在任务配置中设置第一轮或第二轮的评分提示词"
        logger.warning("No scoring prompts configured: %s", error_msg)
        return (None, None, error_msg)

    logger.info("=" * 80)
    logger.info("AI Video Scoring Started")
    logger.info("  Video URL: %s", video_url[:100])
    logger.info("  Round 1 - Enabled: %s, HasPrompt: %s, Threshold: %.1f, Weight: %.2f",
                config.round1_enabled, bool(config.round1_prompt), config.round1_threshold, config.round1_weight)
    logger.info("  Round 2 - Enabled: %s, HasPrompt: %s, Threshold: %.1f, Weight: %.2f",
                config.round2_enabled, bool(config.round2_prompt), config.round2_threshold, config.round2_weight)
    logger.info("=" * 80)

    # Round 1: Initial scoring
    round1_score = None
    round1_reason = ""
    if config.round1_enabled:
        if not config.round1_prompt:
            logger.warning("Round 1 is enabled but prompt is empty, skipping round 1")
        else:
            logger.info("Starting Round 1 scoring...")
            round1_result = await _score_single_round(
                video_url=video_url,
                scoring_prompt=config.round1_prompt,
                model=config.round1_model,
                api_key=api_key,
                api_base_url=api_base_url,
                round_num=1,
            )
            # Check if result is an error tuple
            if round1_result is None or (isinstance(round1_result, tuple) and round1_result[0] is None):
                error_msg = round1_result[1] if isinstance(round1_result, tuple) else "第一轮 AI 评分失败：未知错误"
                logger.error("Round 1 scoring failed completely: %s", error_msg)
                return (None, None, error_msg)

            round1_score, round1_reason = round1_result
            logger.info("Round 1 completed with score: %.1f", round1_score)

            # Check if round1 score meets threshold
            if round1_score < config.round1_threshold:
                logger.warning("Round 1 score %.1f below threshold %.1f, skipping round 2", round1_score, config.round1_threshold)
                # Still calculate final score (round2 will be 0)
                final_score = round1_score * config.round1_weight
                logger.info("Final score (round 1 only): %.1f = %.1f × %.2f + 0 × %.2f", final_score, round1_score, config.round1_weight, config.round2_weight)
                return (final_score, round1_score, 0.0, round1_reason, "")

            logger.info("Round 1 score %.1f passed threshold %.1f, proceeding to round 2", round1_score, config.round1_threshold)
    else:
        logger.info("Round 1 is disabled, skipping")

    # Round 2: Detailed scoring
    round2_score = 0.0
    round2_reason = ""
    if config.round2_enabled:
        if not config.round2_prompt:
            logger.warning("Round 2 is enabled but prompt is empty, skipping round 2")
        else:
            logger.info("Starting Round 2 scoring...")
            round2_result = await _score_single_round(
                video_url=video_url,
                scoring_prompt=config.round2_prompt,
                model=config.round2_model,
                api_key=api_key,
                api_base_url=api_base_url,
                round_num=2,
            )
            # Check if result is an error tuple
            if round2_result is None or (isinstance(round2_result, tuple) and round2_result[0] is None):
                error_msg = round2_result[1] if isinstance(round2_result, tuple) else "第二轮 AI 评分失败：未知错误"
                logger.warning("Round 2 scoring failed: %s, using round 1 score only", error_msg)
                round2_score = 0.0
                round2_reason = f"获取失败：{error_msg}"
            else:
                round2_score, round2_reason = round2_result
                logger.info("Round 2 completed with score: %.1f", round2_score)
    else:
        logger.info("Round 2 is disabled, skipping")

    # Calculate final weighted score
    if round1_score is not None:
        final_score = round1_score * config.round1_weight + round2_score * config.round2_weight

        logger.info("=" * 80)
        logger.info("AI Scoring Completed")
        logger.info("  Round 1 Score: %.1f", round1_score)
        logger.info("  Round 2 Score: %.1f", round2_score)
        logger.info("  Final Score: %.1f = %.1f × %.2f + %.1f × %.2f", final_score, round1_score, config.round1_weight, round2_score, config.round2_weight)
        logger.info("=" * 80)
        return (final_score, round1_score, round2_score, round1_reason, round2_reason)

    # This shouldn't happen given the earlier checks, but handle it
    return (None, None, "AI 评分配置错误：没有启用任何评分轮次")


async def _score_single_round(
    *,
    video_url: str,
    scoring_prompt: str,
    model: str,
    api_key: str,
    api_base_url: str,
    round_num: int,
    max_retries: int = 3,
) -> tuple[float, str] | tuple[None, str]:
    """
    Perform a single round of AI scoring with retry logic.

    Args:
        video_url: CDN URL of the video
        scoring_prompt: The scoring criteria prompt
        model: Model name (e.g., gemini-2.0-flash)
        api_key: EvoLink API key
        api_base_url: EvoLink API base URL
        round_num: Round number (1 or 2) for logging
        max_retries: Maximum number of retry attempts

    Returns:
        Tuple of (Score as float, reason as str) on success
        Tuple of (None, error_message) if all retries failed
    """
    url = f"{api_base_url.rstrip('/')}/v1beta/models/{model}:generateContent"
    
    # Enforce JSON output format
    json_instructions = (
        "\n\n请必须以JSON格式输出你的评分和理由，必须包含两个字段：\n"
        "- \"score\": 数字（0到100之间），表示视频的最终得分\n"
        "- \"reason\": 字符串，详细解释你给出这个打分的理由\n"
        "示例输出：\n"
        "{\n"
        "  \"score\": 85,\n"
        "  \"reason\": \"视频内容清晰明了，且形式新颖有趣...\"\n"
        "}"
    )
    final_prompt = scoring_prompt + json_instructions

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"fileData": {"mimeType": "video/mp4", "fileUri": video_url}},
                    {"text": final_prompt},
                ],
            }
        ]
    }

    masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
    logger.info("=" * 80)
    logger.info("Round %d AI scoring started", round_num)
    logger.info("  Model: %s", model)
    logger.info("  API Key: %s", masked_key)
    logger.info("  Video URL: %s", video_url[:100])
    logger.info("  Scoring Prompt: %s", scoring_prompt[:200])
    logger.info("=" * 80)

    for attempt in range(max_retries):
        try:
            logger.info("Round %d - Attempt %d/%d: Sending HTTP request to %s", round_num, attempt + 1, max_retries, url)
            async with httpx.AsyncClient(timeout=120.0) as client:
                logger.info("Round %d - Attempt %d/%d: HTTP client created, posting request...", round_num, attempt + 1, max_retries)
                resp = await client.post(
                    url,
                    json=payload,
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                logger.info("Round %d - Attempt %d/%d: HTTP response received - status %d", round_num, attempt + 1, max_retries, resp.status_code)
                if not resp.is_success:
                    logger.error("Round %d attempt %d: HTTP %d - %s", round_num, attempt + 1, resp.status_code, resp.text[:200])
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        continue
                resp.raise_for_status()
                data = resp.json()

            # Extract score from response
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            logger.info("Round %d raw AI response: %s", round_num, text[:200])

            # Parse numeric score and reason from response
            score, reason = _extract_score_and_reason(text)
            if score is not None:
                logger.info("Round %d scoring succeeded: score=%.1f", round_num, score)
                return score, reason
            else:
                logger.warning("Round %d attempt %d: could not parse score from response: %s", round_num, attempt + 1, text[:200])
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue

        except httpx.HTTPStatusError as exc:
            logger.error("Round %d attempt %d: HTTP error - %s", round_num, attempt + 1, exc)
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
        except (KeyError, IndexError, TypeError) as exc:
            logger.error("Round %d attempt %d: Invalid response format - %s", round_num, attempt + 1, exc)
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
        except Exception as exc:
            logger.error("Round %d attempt %d: Unexpected error - %s", round_num, attempt + 1, exc)
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue

    logger.error("Round %d scoring failed after %d attempts", round_num, max_retries)
    # Return error message tuple
    return (None, f"第{round_num}轮 AI 评分失败：API 调用重试 {max_retries} 次后仍失败（可能是网络超时或 API 服务不可用）")


def _extract_score_and_reason(text: str) -> tuple[float | None, str]:
    """
    Extract a numeric score and reason from AI JSON response text.
    Fallback to older regex extraction if JSON parsing fails.
    """
    import json
    text = text.strip()
    
    # Strip markdown code blocks if present
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        data = json.loads(text)
        score = float(data.get("score"))
        reason = str(data.get("reason", "未提供理由"))
        if 0 <= score <= 100:
            return score, reason
    except Exception as e:
        logger.warning("Failed to parse AI response as JSON: %s. Raw text: %s", e, text[:100])

    # Fallback legacy extraction
    reason = text
    text_lower = text.lower()

    # Try direct number first
    match = re.search(r"\b(\d{1,3})\b", text_lower)
    if match:
        score = float(match.group(1))
        if 0 <= score <= 100:
            return score, reason

    # Try fraction format (e.g., "7.5/10")
    match = re.search(r"(\d+\.?\d*)\s*/\s*(\d+\.?\d*)", text_lower)
    if match:
        numerator = float(match.group(1))
        denominator = float(match.group(2))
        if denominator > 0:
            score = (numerator / denominator) * 100
            if 0 <= score <= 100:
                return score, reason

    return None, reason
