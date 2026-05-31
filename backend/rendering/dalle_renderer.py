"""
OpenAI building image generator (gpt-image-1).

Required env var:
  OPENAI_API_KEY=sk-...
"""

from __future__ import annotations

import os
import base64
from io import BytesIO
from typing import Optional

from dotenv import load_dotenv
from PIL import Image


def _build_prompt(user_description: str) -> str:
    return (
        f"Architectural front elevation of: {user_description}. "
        "Perfectly flat, dead-on front view, zero perspective. "
        "Solid light grey #D3D3D3 background — no sky, no ground, no gradient. "
        "Complete building visible from roofline to base, nothing cropped. "
        "Ultra-photorealistic architectural render, studio lighting. "
        "No people, no trees, no vehicles, no watermarks, no text."
    )


def _normalise(raw: bytes) -> bytes:
    img = Image.open(BytesIO(raw)).convert("RGB")
    canvas = Image.new("RGB", (800, 1000), (211, 211, 211))
    img.thumbnail((800, 1000), Image.LANCZOS)
    canvas.paste(img, ((800 - img.width) // 2, (1000 - img.height) // 2))
    buf = BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


def generate_dalle_image(user_description: str) -> Optional[bytes]:
    """Generate a building image via gpt-image-1. Returns PNG bytes or None."""
    load_dotenv(override=True)  # re-read on every call so key rotations take effect
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key.startswith("your_") or api_key.startswith("sk-your"):
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        result = client.images.generate(
            model="gpt-image-1",
            prompt=_build_prompt(user_description),
            size="1024x1536",
            quality="high",
            n=1,
        )

        b64 = result.data[0].b64_json
        if b64:
            return _normalise(base64.b64decode(b64))

    except Exception as e:
        import sys
        print(f"[dalle_renderer] Image generation failed: {e}", file=sys.stderr)

    return None
