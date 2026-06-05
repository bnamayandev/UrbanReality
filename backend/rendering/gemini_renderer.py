"""
Gemini building image generator (gemini-3.1-flash-image).

Drop-in replacement for the DALL-E renderer — same signatures and PNG-bytes
return contract. Reuses the prompt-building and canvas-normalisation helpers
from dalle_renderer so output framing stays identical.

Required env var:
  GOOGLE_API_KEY=...
Optional:
  GEMINI_IMAGE_MODEL=gemini-3.1-flash-image   # override the model id
"""

from __future__ import annotations

import os
import sys
import base64
from typing import Optional

from dotenv import load_dotenv

from rendering.dalle_renderer import _build_prompt, _normalise


_DEFAULT_MODEL = "gemini-3.1-flash-image"


def _model() -> str:
    return os.getenv("GEMINI_IMAGE_MODEL", _DEFAULT_MODEL)


def _api_key() -> Optional[str]:
    load_dotenv(override=True)  # re-read on every call so key rotations take effect
    key = os.getenv("GOOGLE_API_KEY", "")
    if not key or key.startswith("your_"):
        return None
    return key


def _extract_png(resp) -> Optional[bytes]:
    """Pull the first inline image out of a generate_content response."""
    candidates = getattr(resp, "candidates", None) or []
    for cand in candidates:
        content = getattr(cand, "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            inline = getattr(part, "inline_data", None)
            if inline is not None and getattr(inline, "data", None):
                return _normalise(inline.data)
    return None


def generate_gemini_image(user_description: str) -> Optional[bytes]:
    """Generate a building image via Gemini. Returns PNG bytes or None."""
    api_key = _api_key()
    if not api_key:
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=_model(),
            contents=[_build_prompt(user_description)],
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )
        return _extract_png(resp)

    except Exception as e:
        print(f"[gemini_renderer] Image generation failed: {e}", file=sys.stderr)
        return None


def edit_gemini_image(image_b64: str, edit_prompt: str) -> Optional[bytes]:
    """Edit an existing building image via Gemini. Returns PNG bytes or None."""
    api_key = _api_key()
    if not api_key:
        return None

    try:
        from google import genai
        from google.genai import types

        raw_b64 = image_b64.split(",")[1] if "," in image_b64 else image_b64
        raw = base64.b64decode(raw_b64)

        prompt = (
            f"{edit_prompt.strip()}. "
            "Maintain the photorealistic architectural render style. "
            "Solid light grey #D3D3D3 background — no sky, no ground, no people, no trees. "
            "Full building structure visible from base to roofline. "
            "Studio lighting, no text, no watermarks."
        )

        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=_model(),
            contents=[
                prompt,
                types.Part.from_bytes(data=raw, mime_type="image/png"),
            ],
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )
        return _extract_png(resp)

    except Exception as e:
        print(f"[gemini_renderer] Image edit failed: {e}", file=sys.stderr)
        return None
