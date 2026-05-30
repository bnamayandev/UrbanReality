"""
AI building image generator — uses DALL-E 3 exclusively.

Required env var:
  OPENAI_API_KEY=sk-...
"""

from __future__ import annotations

from typing import Optional
from rendering.dalle_renderer import generate_dalle_image


def generate_ai_image(
    style: str,
    building_type: str,
    floors: int,
    size: str,
    user_description: str = "",
) -> tuple[Optional[bytes], str]:
    """Returns (png_bytes, source_label) or (None, 'none') if generation fails."""
    desc = user_description or f"{size} {style.replace('_', ' ')} {building_type} {floors} floors"

    result = generate_dalle_image(user_description=desc)
    if result:
        return result, "DALL-E 3 · OpenAI"

    return None, "none"
