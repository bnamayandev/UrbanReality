"""
AI building image generator.

Priority:
  1. DALL-E 3 (gpt-image-1) — OpenAI          (OPENAI_API_KEY)
  2. Imagen 3               — Google           (GOOGLE_API_KEY)
  3. FLUX.1-schnell          — Together AI      (TOGETHER_API_KEY)
  4. SDXL-Turbo              — NVIDIA Build     (NGC_API_KEY)
"""

from __future__ import annotations
import os, base64
from io import BytesIO
from typing import Optional

import httpx
from PIL import Image

from rendering.dalle_renderer import generate_dalle_image
from rendering.gemini_renderer import generate_gemini_image


def _normalise(raw: bytes) -> bytes:
    img = Image.open(BytesIO(raw)).convert("RGB")
    canvas = Image.new("RGB", (800, 1000), (211, 211, 211))  # #D3D3D3
    img.thumbnail((800, 1000), Image.LANCZOS)
    x = (800 - img.width) // 2
    y = (1000 - img.height) // 2
    canvas.paste(img, (x, y))
    buf = BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


def _together(user_description: str) -> Optional[bytes]:
    key = os.getenv("TOGETHER_API_KEY")
    if not key:
        return None
    try:
        r = httpx.post(
            "https://api.together.xyz/v1/images/generations",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model":  "black-forest-labs/FLUX.1-schnell-Free",
                "prompt": (
                    f"Architectural front elevation of: {user_description}. "
                    "Head-on flat view, solid #D3D3D3 background, no people, no trees, "
                    "ultra-photorealistic, full building visible, nothing cropped."
                ),
                "width":  832,
                "height": 1216,
                "n":      1,
                "response_format": "b64_json",
            },
            timeout=45.0,
        )
        r.raise_for_status()
        data = r.json()
        b64 = (data.get("data") or [{}])[0].get("b64_json")
        if b64:
            return _normalise(base64.b64decode(b64))
        url = (data.get("data") or [{}])[0].get("url")
        if url:
            return _normalise(httpx.get(url, timeout=20).content)
    except Exception as e:
        print(f"[ai_renderer] Together AI failed: {e}")
    return None


def _nvidia(user_description: str) -> Optional[bytes]:
    key = os.getenv("NGC_API_KEY")
    if not key or key == "your_ngc_api_key_here":
        return None
    try:
        r = httpx.post(
            "https://ai.api.nvidia.com/v1/genai/stabilityai/sdxl-turbo",
            headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
            json={
                "text_prompts": [
                    {"text": (
                        f"Architectural front elevation of {user_description}. "
                        "Head-on flat view, solid grey background, no people, no trees."
                    ), "weight": 1},
                    {"text": "perspective, isometric, people, cars, trees, sky, watermark", "weight": -1},
                ],
                "cfg_scale": 0,
                "steps":     4,
                "width":     512,
                "height":    768,
            },
            timeout=30.0,
        )
        r.raise_for_status()
        b64 = r.json()["artifacts"][0]["base64"]
        return _normalise(base64.b64decode(b64))
    except Exception as e:
        print(f"[ai_renderer] NVIDIA failed: {e}")
    return None


def generate_ai_image(
    style: str,
    building_type: str,
    floors: int,
    size: str,
    user_description: str = "",
) -> tuple[Optional[bytes], str]:
    """
    Returns (png_bytes, source_label) or (None, "none") if all renderers fail.
    Tries DALL-E 3 first, then falls back through Imagen 3, FLUX, SDXL.
    """
    desc = user_description or f"{size} {style.replace('_', ' ')} {building_type} {floors} floors"

    result = generate_dalle_image(user_description=desc)
    if result:
        return result, "DALL-E 3 · OpenAI"

    result = generate_gemini_image(style, building_type, floors, size)
    if result:
        return result, "Imagen 3 · Google"

    result = _together(desc)
    if result:
        return result, "FLUX · Together AI"

    result = _nvidia(desc)
    if result:
        return result, "SDXL · NVIDIA Build"

    return None, "none"
