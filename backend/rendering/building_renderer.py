"""
Building image generator.

Primary path: DALL-E 3 via OpenAI.
Fallback: a deterministic Pillow silhouette so the demo never breaks when
the OpenAI key is missing, rate-limited, or quota-exhausted.
"""

from __future__ import annotations

from io import BytesIO
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from rendering.dalle_renderer import generate_dalle_image


CANVAS = (800, 1000)
BG     = (211, 211, 211)


def _pillow_silhouette(building_type: str, style: str, floors: int) -> bytes:
    img = Image.new("RGB", CANVAS, BG)
    d   = ImageDraw.Draw(img)

    # Scale building height to floor count (capped to canvas)
    floor_h = max(8, min(20, int(800 / max(floors, 1))))
    height  = min(900, floors * floor_h)
    width   = int(CANVAS[0] * 0.55)
    x0      = (CANVAS[0] - width) // 2
    y0      = CANVAS[1] - 60 - height
    x1, y1  = x0 + width, CANVAS[1] - 60

    # Body
    body = {
        "modern_glass_tower":  (90, 110, 140),
        "brutalist_concrete":  (140, 140, 138),
        "traditional_brick":   (150, 80, 60),
        "retail_complex":      (110, 120, 130),
    }.get(style, (95, 115, 145))
    d.rectangle([x0, y0, x1, y1], fill=body)

    # Windows
    win = (230, 240, 250)
    margin_x, gap_x = 14, 10
    for row in range(floors):
        ry = y0 + 6 + row * floor_h
        if ry + floor_h - 4 > y1: break
        cx = x0 + margin_x
        while cx + 18 < x1 - margin_x:
            d.rectangle([cx, ry + 2, cx + 18, ry + floor_h - 4], fill=win)
            cx += 18 + gap_x

    # Roof line
    d.rectangle([x0 - 6, y0 - 6, x1 + 6, y0], fill=(60, 65, 80))
    # Ground line
    d.rectangle([0, y1, CANVAS[0], CANVAS[1]], fill=(190, 190, 190))

    try:
        font = ImageFont.load_default()
        d.text((x0, y1 + 14), f"{floors}F {building_type}", fill=(80, 80, 80), font=font)
    except Exception:
        pass

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def render_building(
    building_type: str,
    style: str,
    floors: int,
    size: str,
    user_description: str = "",
) -> Optional[bytes]:
    desc = user_description or f"{size} {style.replace('_', ' ')} {building_type} {floors} floors"
    png = generate_dalle_image(user_description=desc)
    if png:
        return png
    return _pillow_silhouette(building_type, style, floors)
