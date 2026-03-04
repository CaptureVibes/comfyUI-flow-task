"""Gemini AI service for video understanding."""
import logging
import os
import tempfile
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.video_source import VideoSource
from app.services.video_source_service import get_video_source_or_404

logger = logging.getLogger("app.gemini")


class GeminiService:
    """Service for interacting with Google Gemini API."""

    def __init__(self):
        self.api_key = settings.gemini_api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

    async def analyze_video(
        self,
        video_source: VideoSource,
        prompt: str | None = None,
    ) -> dict[str, Any]:
        """
        Analyze video using Gemini API.

        Args:
            video_source: Video source with video URL
            prompt: Optional custom prompt

        Returns:
            Dictionary with analysis results including:
            - description: Video content description
            - extracted_shots: List of key frame images (after upload)
        """
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured")

        # Default prompt for video analysis
        if not prompt:
            prompt = """请分析这个视频并提供以下信息：
1. 视频内容的详细描述（包括人物、场景、动作等）
2. 视频中的关键造型/穿搭/风格
3. 适合作为视频生成prompt的描述

请以JSON格式返回，包含以下字段：
{
  "description": "视频详细描述",
  "style_analysis": "风格分析",
  "key_shots": [
    {
      "timestamp": "时间戳",
      "description": "镜头描述",
      "prompt": "可用于生成图片的prompt"
    }
  ]
}"""

        # For now, return mock data since we need video file access
        # In production, you would:
        # 1. Download the video
        # 2. Upload to Gemini
        # 3. Get analysis
        # 4. Generate images from key frames
        # 5. Upload images to CDN

        logger.info(f"Analyzing video {video_source.id} with Gemini (mock)")

        # Mock response - replace with actual Gemini API call
        return {
            "description": self._generate_mock_description(video_source),
            "style_analysis": "时尚穿搭风格，简约优雅",
            "key_shots": [
                {
                    "timestamp": "00:05",
                    "description": "全身造型展示",
                    "prompt": f"{video_source.video_title or '时尚造型'}，全身照，高清，正面视角"
                },
                {
                    "timestamp": "00:15",
                    "description": "面部特写",
                    "prompt": f"{video_source.video_title or '时尚造型'}，面部特写，高清，自然光线"
                },
                {
                    "timestamp": "00:25",
                    "description": "细节展示",
                    "prompt": f"{video_source.video_title or '时尚造型'}，细节特写，高清"
                },
            ]
        }

    def _generate_mock_description(self, video_source: VideoSource) -> str:
        """Generate mock video description based on video metadata."""
        parts = []

        if video_source.blogger_name:
            parts.append(f"视频博主：{video_source.blogger_name}")

        if video_source.video_desc:
            parts.append(f"视频内容：{video_source.video_desc}")
        else:
            parts.append("视频内容：时尚穿搭展示")

        if video_source.platform:
            parts.append(f"来源平台：{video_source.platform}")

        return " | ".join(parts)

    async def generate_image_prompt(
        self,
        video_description: str,
        shot_description: str,
    ) -> str:
        """
        Generate detailed prompt for image generation based on video content.

        Args:
            video_description: Overall video description
            shot_description: Specific shot/frame description

        Returns:
            Detailed prompt for image generation
        """
        # This would call Gemini to generate an image prompt
        # For now, return a simple combination
        return f"{video_description}，{shot_description}，高清摄影，专业灯光，8k分辨率"


# Global service instance
gemini_service = GeminiService()
