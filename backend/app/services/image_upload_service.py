"""Image upload service for uploading to CDN."""
import logging
import tempfile
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger("app.image_upload")


class ImageUploadService:
    """Service for uploading images to CDN."""

    def __init__(self):
        self.upload_api_url = settings.video_image_upload_url

    async def upload_from_url(
        self,
        image_url: str,
        filename: str | None = None,
    ) -> dict[str, Any]:
        """
        Download image from URL and upload to CDN.

        Args:
            image_url: URL of the image to download
            filename: Optional filename to use

        Returns:
            Dictionary with upload result:
            - url: The CDN URL of uploaded image
            - filename: Original filename
            - size: File size in bytes
            - content_type: MIME type
        """
        if not filename:
            filename = Path(image_url).name or "image.png"

        # Download image
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Download image
            response = await client.get(image_url)
            response.raise_for_status()
            image_data = response.content
            content_type = response.headers.get("content-type", "image/png")

            logger.info(f"Downloaded image from {image_url}, size: {len(image_data)} bytes")

            # Upload to CDN
            return await self.upload_file(
                image_data=image_data,
                filename=filename,
                content_type=content_type,
            )

    async def upload_file(
        self,
        image_data: bytes,
        filename: str,
        content_type: str = "image/png",
    ) -> dict[str, Any]:
        """
        Upload image file to CDN.

        Args:
            image_data: Image binary data
            filename: Filename to use
            content_type: MIME type

        Returns:
            Dictionary with upload result
        """
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp_file:
            tmp_file.write(image_data)
            tmp_file_path = tmp_file.name

        try:
            # Prepare multipart upload
            files = {
                "file": (
                    filename,
                    image_data,
                    content_type,
                )
            }

            # Upload to CDN API
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.upload_api_url,
                    files=files,
                    headers={
                        "User-Agent": "confyUI-backend/1.0.0",
                    }
                )
                response.raise_for_status()

                result = response.json()

                if result.get("code") != 0:
                    raise Exception(f"Upload failed: {result.get('message', 'Unknown error')}")

                data = result.get("data", {})

                logger.info(f"Successfully uploaded image to CDN: {data.get('url')}")

                return {
                    "url": data.get("url"),
                    "filename": data.get("filename"),
                    "size": data.get("size", 0),
                    "content_type": data.get("content_type"),
                }
        finally:
            # Clean up temp file
            try:
                Path(tmp_file_path).unlink()
            except Exception:
                pass

    async def upload_multiple_from_urls(
        self,
        image_urls: list[str],
    ) -> list[dict[str, Any]]:
        """
        Upload multiple images from URLs.

        Args:
            image_urls: List of image URLs

        Returns:
            List of upload results
        """
        results = []

        for idx, url in enumerate(image_urls):
            try:
                filename = f"image_{idx + 1}.png"
                result = await self.upload_from_url(url, filename)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to upload image {idx + 1}: {e}")
                results.append({
                    "url": url,
                    "error": str(e),
                })

        return results


# Global service instance
image_upload_service = ImageUploadService()
