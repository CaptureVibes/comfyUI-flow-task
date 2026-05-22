"""
人脸选择服务

流程：
1. 找到 tag 关联的随机一个视频（通过 video_source_tags）
2. 用 ffmpeg 抽取最多 10 帧（前 15s，每 1.5s 一帧）
3. 将帧图片上传到 CDN（需要公网 URL 才能传给 Gemini）
4. 调用 Gemini API，传入 10 张帧图片，让 AI 选择最合适的一张人脸
5. 解析 {"selected": N} 响应，保存到 face_photos 表
"""
from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.face_photo import FacePhoto
from app.models.tag import Tag, VideoSourceTag
from app.models.video_source import VideoSource
from app.services.face_classification_service import classify_face_photo
from app.services.pipeline_settings_service import get_or_create_pipeline_settings
from app.services.video_ai_service import _extract_frames, _upload_frame_to_cdn

logger = logging.getLogger("app.face_select")


async def select_face_for_tag(
    session: AsyncSession,
    tag_id: str,
    owner_id: str | None,
    *,
    is_admin: bool = False,
) -> FacePhoto:
    """
    为指定 tag 执行 AI 人脸选择。
    - 随机选一个关联视频
    - 抽帧、上传 CDN、调用 Gemini
    - 替换 face_photos 表中该 tag 的记录
    返回新建的 FacePhoto ORM 对象。
    """
    tag_uuid = uuid.UUID(tag_id)
    owner_uuid = uuid.UUID(owner_id) if owner_id else None

    # 1. 验证 tag 归属（admin 跳过）
    tag = await session.get(Tag, tag_uuid)
    if tag is None:
        raise RuntimeError("标签不存在")
    if not is_admin and owner_uuid is not None and tag.owner_id != owner_uuid:
        raise RuntimeError("无权操作此标签")

    # 2. 随机获取一个关联视频的 local_video_url（CDN）
    stmt = (
        select(VideoSource.local_video_url)
        .join(VideoSourceTag, VideoSourceTag.video_source_id == VideoSource.id)
        .where(VideoSourceTag.tag_id == tag_uuid)
        .where(VideoSource.local_video_url.isnot(None))
        .order_by(func.random())
        .limit(1)
    )
    video_url = await session.scalar(stmt)
    if not video_url:
        raise RuntimeError("此标签下没有已上传CDN的关联视频")

    logger.info("[人脸选择] tag_id=%s 选取视频 local_video_url=%s", tag_id, video_url[:80])

    # 3. 抽帧（base64 data URL 列表）
    data_urls = await _extract_frames(video_url, tag_id)
    if not data_urls:
        raise RuntimeError("视频抽帧失败，未获取到任何帧")

    logger.info("[人脸选择] 抽帧完成，共 %d 帧", len(data_urls))

    # 4. 上传帧图片到 CDN（需要公网 URL）
    cdn_urls: list[str] = []
    for i, data_url in enumerate(data_urls):
        cdn_url = await _upload_frame_to_cdn(data_url)
        cdn_urls.append(cdn_url)
        logger.info("[人脸选择] 帧 %d 上传完成: %s", i + 1, cdn_url[:80])

    # 5. 读取配置
    if owner_uuid:
        cfg = await get_or_create_pipeline_settings(session, owner_uuid)
        model = cfg.face_select_model or "gemini-3.1-pro-preview"
        prompt = cfg.face_select_prompt or ""
    else:
        model = "gemini-3.1-pro-preview"
        prompt = ""

    # 6. 调用 Gemini 多图接口
    json_instructions = (
        "\n\n请从以上图片中选择一张最适合作为人脸照片的图片（清晰、正面、表情自然）。"
        "请以JSON格式输出，格式如下：{\"selected\": <数字1-10>}"
    )
    final_prompt = (prompt + json_instructions) if prompt else (
        "以下是从视频中抽取的帧图片，请选择一张最适合作为人脸照片的图片（人脸清晰、正面、表情自然）。"
        + json_instructions
    )

    response_schema = {
        "type": "object",
        "properties": {
            "selected": {"type": "integer"},
        },
        "required": ["selected"],
    }

    from app.services.ai_api import call_gemini_api_with_images

    text = await call_gemini_api_with_images(
        model_name=model,
        prompt=final_prompt,
        image_urls=cdn_urls,
        temperature=0.1,
        response_schema=response_schema,
        timeout=120.0,
    )
    logger.info("[人脸选择] Gemini 响应: %s", text[:200])

    # 8. 解析 JSON 响应
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.split("```")[0].strip()

    try:
        result = json.loads(cleaned)
        selected = int(result.get("selected", 0))
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        raise RuntimeError(f"AI 返回格式无效: {text[:200]}") from exc

    if selected < 1 or selected > len(cdn_urls):
        raise RuntimeError(f"AI 返回的选择无效: selected={selected}, 可选范围 1-{len(cdn_urls)}")

    selected_url = cdn_urls[selected - 1]
    logger.info("[人脸选择] AI 选择第 %d 张: %s", selected, selected_url[:80])

    # 9. 替换 face_photos 记录（upsert：先删后插）
    await session.execute(delete(FacePhoto).where(FacePhoto.tag_id == tag_uuid))

    face_photo = FacePhoto(
        owner_id=owner_uuid,
        tag_id=tag_uuid,
        face_photo_url=selected_url,
        frame_index=selected,
    )
    session.add(face_photo)
    await session.commit()
    await session.refresh(face_photo)

    face_photo = await classify_face_photo(session, face_photo)

    return face_photo
