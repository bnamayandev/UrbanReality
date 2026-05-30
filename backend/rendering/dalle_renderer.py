"""
DALL-E 3 building image generator.

Takes the user's raw description and generates a 2D head-on architectural
elevation — no rigid type mapping, the user gets exactly what they asked for.
Background is always solid #D3D3D3.

Required .env:
  OPENAI_API_KEY=sk-...   (platform.openai.com → API keys)
"""

from __future__ import annotations

import base64
import os
from io import BytesIO
from typing import Optional

import httpx
from PIL import Image


def _build_prompt(user_description: str) -> str:
    return (
        f"Architectural front elevation of: {user_description}. "
        "STRICT REQUIREMENTS — follow every one: "
        "1. ANGLE: perfectly flat, dead-on front view, zero perspective, zero angle, camera level at mid-building height. "
        "2. BACKGROUND: solid flat uniform light grey #D3D3D3 fill — the entire background must be this exact colour, no gradient, no sky, no ground plane, no horizon. "
        "3. SUBJECT: the complete building only — full height from roofline to base, full width, nothing cropped. "
        "4. REALISM: ultra-photorealistic architectural render — crisp material textures, precise details, studio diffuse lighting, no harsh shadows, razor-sharp focus. "
        "5. EXCLUSIONS: absolutely no people, no trees, no vehicles, no landscaping, no street furniture, no signs, no watermarks, no text overlays. "
        "The building must look exactly like what was described — a mansion should look like a mansion, a castle like a castle, a cottage like a cottage. "
        "Professional architectural elevation illustration quality."
    )


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


def generate_dalle_image(
    user_description: str,
    style: str = "",
    building_type: str = "",
    floors: int = 0,
    size: str = "",
) -> Optional[bytes]:
    """
    Generate a 2D head-on building image via gpt-image-1 (DALL-E 3).
    Uses the raw user_description so the result matches exactly what was asked for.
    Returns PNG bytes on a #D3D3D3 canvas, or None if key missing / call fails.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your_openai_api_key_here":
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        prompt = _build_prompt(user_description)

        result = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1536",
            quality="high",
            output_format="png",
            n=1,
        )

        b64 = result.data[0].b64_json
        if b64:
            return _normalise(base64.b64decode(b64))

        image_url = result.data[0].url
        raw = httpx.get(image_url, timeout=30.0).content
        return _normalise(raw)

    except Exception as e:
        print(f"[dalle_renderer] DALL-E 3 failed: {e}")
        return None
