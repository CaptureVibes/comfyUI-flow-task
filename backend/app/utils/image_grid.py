"""4×2 八拼图切割工具。

用于阶段 2.5（lookbook_gen）：把图像生成模型产出的 4 列 × 2 行 = 8 panel
合成图切成 8 张独立 PNG，行优先编号 panel_1..panel_8（左上→右上→左下→右下）。

策略：
  1. **优先 gutter 检测**：扫水平 / 垂直方向投影找连续的白色（接近纯白）行/列，
     这就是 panel 之间的分隔条；据此定 4 个垂直分界 + 2 个水平分界
  2. **fallback 等分切割**：识别不到合理 gutter 时按等分宽度 / 高度切

无 Gemini 视觉 QA（这一步由上游图像生成模型保证）。
"""
from __future__ import annotations

import logging
from io import BytesIO
from typing import Literal

from PIL import Image

logger = logging.getLogger("app.image_grid")

# 投影行/列被认为"接近白色"的均值阈值
_WHITE_RGB_MIN = 240
# Gutter 占整体的最小比例（避免误把窄白边当 gutter）
_GUTTER_MIN_RATIO = 0.003
# Gutter 占整体的最大比例（避免把背景纯色当 gutter）
_GUTTER_MAX_RATIO = 0.15


def split_4x2(image_bytes: bytes) -> list[bytes]:
    """把 4×2 合成图切成 8 张 PNG bytes，行优先编号。

    返回长度始终为 8。优先 gutter 检测，识别失败 fallback 等分。
    """
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    width, height = img.size

    col_boundaries = _detect_gutter_boundaries(img, axis="vertical", segments=4)
    row_boundaries = _detect_gutter_boundaries(img, axis="horizontal", segments=2)

    if col_boundaries is None or row_boundaries is None:
        logger.info(
            "image_grid: gutter 识别失败 → fallback 等分 (col=%s row=%s w=%d h=%d)",
            col_boundaries is not None, row_boundaries is not None, width, height,
        )
        col_boundaries = [width * i // 4 for i in range(5)]
        row_boundaries = [height * i // 2 for i in range(3)]

    panels: list[bytes] = []
    for r in range(2):
        for c in range(4):
            box = (col_boundaries[c], row_boundaries[r],
                   col_boundaries[c + 1], row_boundaries[r + 1])
            panel = img.crop(box)
            buf = BytesIO()
            panel.save(buf, format="PNG", optimize=True)
            panels.append(buf.getvalue())
    return panels


def _detect_gutter_boundaries(
    img: Image.Image,
    *,
    axis: Literal["vertical", "horizontal"],
    segments: int,
) -> list[int] | None:
    """沿 axis 找 (segments-1) 条 gutter，返回 segments+1 个边界（含 0 与边长）。

    axis="vertical" → 找垂直 gutter（按列扫描），切成 N 列；
    axis="horizontal" → 找水平 gutter（按行扫描），切成 N 行。

    返回 None 表示识别失败（gutter 数量对不上）。
    """
    if segments < 2:
        return None

    width, height = img.size
    total = width if axis == "vertical" else height

    # 算每行/每列的"是否接近白色"布尔向量
    is_white = _line_is_white_vector(img, axis=axis)

    # 找连续白色段
    runs: list[tuple[int, int]] = []  # (start, end_exclusive)
    in_run = False
    run_start = 0
    for i, w in enumerate(is_white):
        if w and not in_run:
            run_start = i
            in_run = True
        elif not w and in_run:
            runs.append((run_start, i))
            in_run = False
    if in_run:
        runs.append((run_start, len(is_white)))

    # 过滤：剔除边缘 run（图像最外面的白边不是 gutter），剔除超大段
    min_len = max(1, int(total * _GUTTER_MIN_RATIO))
    max_len = max(min_len + 1, int(total * _GUTTER_MAX_RATIO))
    interior_runs = [
        (s, e) for (s, e) in runs
        if s > 0 and e < total and min_len <= (e - s) <= max_len
    ]

    if len(interior_runs) < segments - 1:
        return None

    # 当检测到的 gutter 多于需要（比如多余空白），用 K-means 思路简化为"取 segments-1 个最居中的"
    # 简化版：取理论中点附近的 gutter
    expected_centers = [total * i / segments for i in range(1, segments)]
    chosen: list[tuple[int, int]] = []
    used_indices: set[int] = set()
    for center in expected_centers:
        best_idx = -1
        best_dist = float("inf")
        for idx, (s, e) in enumerate(interior_runs):
            if idx in used_indices:
                continue
            mid = (s + e) / 2
            dist = abs(mid - center)
            if dist < best_dist:
                best_dist = dist
                best_idx = idx
        if best_idx < 0:
            return None
        chosen.append(interior_runs[best_idx])
        used_indices.add(best_idx)

    chosen.sort()
    # 用每个 gutter 的中点作为切割线
    cuts = [0] + [(s + e) // 2 for (s, e) in chosen] + [total]
    # 校验单调递增
    if any(cuts[i] >= cuts[i + 1] for i in range(len(cuts) - 1)):
        return None
    return cuts


def _line_is_white_vector(img: Image.Image, *, axis: str) -> list[bool]:
    """对每一行（horizontal）或每一列（vertical）算 RGB 均值，判断是否接近白色。

    用 PIL resize 做快速降采样：缩到 1 像素宽 / 高再读 pixel，比逐像素遍历快 100×。
    """
    if axis == "vertical":
        # 缩成 (W, 1)：每列一个均值像素
        line_img = img.resize((img.width, 1), Image.Resampling.BILINEAR)
        return [_is_white_pixel(line_img.getpixel((x, 0))) for x in range(img.width)]
    else:
        # 缩成 (1, H)：每行一个均值像素
        line_img = img.resize((1, img.height), Image.Resampling.BILINEAR)
        return [_is_white_pixel(line_img.getpixel((0, y))) for y in range(img.height)]


def _is_white_pixel(pixel) -> bool:
    if isinstance(pixel, int):
        return pixel >= _WHITE_RGB_MIN
    r, g, b = pixel[:3]
    return r >= _WHITE_RGB_MIN and g >= _WHITE_RGB_MIN and b >= _WHITE_RGB_MIN
