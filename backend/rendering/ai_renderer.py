"""
AI building image generator — uses Gemini (gemini-3.1-flash-image).

Required env var:
  GOOGLE_API_KEY=...
"""

from __future__ import annotations

from typing import Optional
from rendering.gemini_renderer import generate_gemini_image


def generate_ai_image(
    style: str,
    building_type: str,
    floors: int,
    size: str,
    user_description: str = "",
) -> tuple[Optional[bytes], str]:
    """Returns (png_bytes, source_label) or (None, 'none') if generation fails."""
    desc = user_description or f"{size} {style.replace('_', ' ')} {building_type} {floors} floors"

    result = generate_gemini_image(user_description=desc)
    if result:
        return result, "gemini-3.1-flash-image · Google"

    return None, "none"
