from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.face_photo import FacePhoto
from app.services.pipeline_settings_service import get_or_create_pipeline_settings

logger = logging.getLogger("app.face_classification")

_GENDERS = {"男", "女", "其他", "不确定"}
_ETHNICITIES = {"东亚", "东南亚", "南亚", "中东", "白人", "黑人", "拉美", "混血", "不确定"}
_AGE_RANGES = {"18-", "18-25", "26-35", "36-50", "50+"}

DEFAULT_FACE_CLASSIFY_PROMPT = """你是专业造型/选角视觉助理。请只看图片中主体人物（如果有多个人，选取构图最显眼/最近镜头的那一位），输出该人物的客观可见特征。

# 任务
对该主体人物给出以下分类，只输出一个 JSON 对象，不要 markdown 代码块、不要任何额外文字、不要注释：

{
  "gender": "男" | "女" | "其他" | "不确定",
  "ethnicity": "东亚" | "东南亚" | "南亚" | "中东" | "白人" | "黑人" | "拉美" | "混血" | "不确定",
  "age_estimate": <整数，目测年龄岁>,
  "age_range": "18-" | "18-25" | "26-35" | "36-50" | "50+",
  "beauty_level": "普通" | "美丽",
  "beauty_percentile": <0-100 的整数>,
  "memorability_level": "普通" | "独特",
  "memorability_percentile": <0-100 的整数>,
  "notes": "<可选，10 字内的简短备注，例如『短发/戴墨镜/侧脸』，没有就给空字符串>"
}

# 美貌评分 beauty_percentile
- 0-100 的整数，表示随机 100 位短视频博主中这个人比多少人更好看。
- 只看脸：五官端正度、五官比例与协调感、皮肤状态、整体气质。
- 95-100 极罕见；85-94 明显出众；70-84 漂亮上镜；55-69 中上；40-54 普通端正；25-39 有明显短板；10-24 短板较多；0-9 看不到脸/非人物。
- 必须给具体整数，不要总用整十或整五。
- beauty_level 后端会按 beauty_percentile >= 78 校验修正。

# 特征锁定评分 memorability_percentile
- 用于判断人脸 remix / 换装混搭可行性，不是美貌评分。
- 分数越高，专属识别特征越强，越不适合参与 remix。
- 高分信号：明显痣/胎记/疤痕/纹身、明显医美签名、罕见生理特征、强签名发型发色、极强唯一骨相、明星脸或强独特感。
- 低分信号：五官比例大众、没有显著视觉锚点、发色发型主流，即使漂亮也属于标准美人。
- 90-100 几乎不能 remix；70-89 remix 后仍会被认出；50-69 要小心；30-49 中等通用；10-29 高度通用；0-9 看不到脸/非人物。
- memorability_level 后端会按 memorability_percentile >= 78 校验修正。

# 族裔判断
- 这是内部选角/造型素材分组，不是身份认定，只是粗分组。
- 需要基于肤色、发色发质、面部轮廓、五官比例等可见线索给出最可能的一个族裔。
- ethnicity = "不确定" 只在完全看不到人物面部/皮肤/头发，或线索强烈冲突时使用。

# 不清晰时
- 即使模糊、侧脸、低头、远景，也要尽力判断 gender、age_estimate、age_range、beauty_percentile。
- 在 notes 里写明侧脸/远景/戴墨镜/低头/盘发等。
- 若确实没有任何人，gender 和 ethnicity 填 "不确定"，分数给 0，notes 写 "无人物"。

# 仅输出 JSON
直接输出对象本身。"""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _strip_json_response(text: str) -> str:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.split("```")[0].strip()
    return cleaned


def _clamp_int(value: Any, min_value: int, max_value: int) -> int:
    try:
        parsed = int(round(float(value)))
    except (TypeError, ValueError):
        parsed = min_value
    return max(min_value, min(max_value, parsed))


def normalize_face_classification(raw: dict[str, Any]) -> dict[str, Any]:
    gender = str(raw.get("gender") or "不确定").strip()
    if gender not in _GENDERS:
        gender = "不确定"

    ethnicity = str(raw.get("ethnicity") or "不确定").strip()
    if ethnicity not in _ETHNICITIES:
        ethnicity = "不确定"

    age_estimate = _clamp_int(raw.get("age_estimate"), 0, 120)
    age_range = str(raw.get("age_range") or "").strip()
    if age_range not in _AGE_RANGES:
        if age_estimate < 18:
            age_range = "18-"
        elif age_estimate <= 25:
            age_range = "18-25"
        elif age_estimate <= 35:
            age_range = "26-35"
        elif age_estimate <= 50:
            age_range = "36-50"
        else:
            age_range = "50+"

    beauty_percentile = _clamp_int(raw.get("beauty_percentile"), 0, 100)
    memorability_percentile = _clamp_int(raw.get("memorability_percentile"), 0, 100)

    notes = str(raw.get("notes") or "").strip()
    if len(notes) > 20:
        notes = notes[:20]

    return {
        "gender": gender,
        "ethnicity": ethnicity,
        "age_estimate": age_estimate,
        "age_range": age_range,
        "beauty_percentile": beauty_percentile,
        "beauty_level": "美丽" if beauty_percentile >= 78 else "普通",
        "memorability_percentile": memorability_percentile,
        "memorability_level": "独特" if memorability_percentile >= 78 else "普通",
        "notes": notes,
    }


async def classify_face_photo(session: AsyncSession, face_photo: FacePhoto) -> FacePhoto:
    cfg = None
    if face_photo.owner_id is not None:
        cfg = await get_or_create_pipeline_settings(session, face_photo.owner_id)

    model = (cfg.face_classify_model if cfg else "") or "gemini-3-pro-preview"
    prompt = (cfg.face_classify_prompt if cfg else "") or DEFAULT_FACE_CLASSIFY_PROMPT
    temperature = float((cfg.face_classify_temperature if cfg else None) or 0.5)

    face_photo.classification_status = "running"
    face_photo.classification_error = None
    face_photo.classification_model = model
    await session.commit()
    await session.refresh(face_photo)

    response_schema = {
        "type": "object",
        "properties": {
            "gender": {"type": "string"},
            "ethnicity": {"type": "string"},
            "age_estimate": {"type": "integer"},
            "age_range": {"type": "string"},
            "beauty_level": {"type": "string"},
            "beauty_percentile": {"type": "integer"},
            "memorability_level": {"type": "string"},
            "memorability_percentile": {"type": "integer"},
            "notes": {"type": "string"},
        },
        "required": [
            "gender",
            "ethnicity",
            "age_estimate",
            "age_range",
            "beauty_level",
            "beauty_percentile",
            "memorability_level",
            "memorability_percentile",
            "notes",
        ],
    }

    try:
        from app.services.ai_api import call_gemini_api_with_images

        text = await call_gemini_api_with_images(
            model_name=model,
            prompt=prompt,
            image_urls=[face_photo.face_photo_url],
            temperature=temperature,
            response_schema=response_schema,
            timeout=120.0,
        )
        raw = json.loads(_strip_json_response(text))
        if not isinstance(raw, dict):
            raise ValueError("AI 返回不是 JSON 对象")
        normalized = normalize_face_classification(raw)
    except Exception as exc:
        logger.exception("Face classification failed face_photo_id=%s", face_photo.id)
        face_photo.classification_status = "failed"
        face_photo.classification_error = str(exc)
        face_photo.classified_at = _utcnow()
        await session.commit()
        await session.refresh(face_photo)
        return face_photo

    face_photo.classification_status = "success"
    face_photo.classification_error = None
    face_photo.classification_raw = raw
    face_photo.classified_at = _utcnow()
    face_photo.gender = normalized["gender"]
    face_photo.ethnicity = normalized["ethnicity"]
    face_photo.age_estimate = normalized["age_estimate"]
    face_photo.age_range = normalized["age_range"]
    face_photo.beauty_percentile = normalized["beauty_percentile"]
    face_photo.beauty_level = normalized["beauty_level"]
    face_photo.memorability_percentile = normalized["memorability_percentile"]
    face_photo.memorability_level = normalized["memorability_level"]
    face_photo.notes = normalized["notes"]
    await session.commit()
    await session.refresh(face_photo)
    return face_photo
