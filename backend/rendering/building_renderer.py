"""
Building image generator — delegates to DALL-E 3.
"""

from __future__ import annotations
from typing import Optional
from rendering.dalle_renderer import generate_dalle_image


def render_building(
    building_type: str,
    style: str,
    floors: int,
    size: str,
    user_description: str = "",
) -> Optional[bytes]:
    desc = user_description or f"{size} {style.replace('_', ' ')} {building_type} {floors} floors"
    return generate_dalle_image(user_description=desc)
