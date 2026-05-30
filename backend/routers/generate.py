"""
POST /generate/building-image

Accepts a natural language prompt describing the building.
Returns base64-encoded PNG + metadata.

503 is returned when OPENAI_API_KEY is not configured — the frontend
shows an "add your API key" message in that case.
"""

import os
import base64
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

from rendering.ai_renderer import generate_ai_image
from rendering.building_renderer import render_building

load_dotenv()

router = APIRouter(prefix="/generate", tags=["generate"])


class GenerateRequest(BaseModel):
    prompt: Optional[str] = None
    # Legacy structured params — kept for backwards compat
    building_type: Optional[str] = None
    style:         Optional[str] = None
    floors:        Optional[int] = None
    size:          Optional[str] = None


class GenerateResponse(BaseModel):
    image_b64: str
    image_path: str
    metadata: dict


def _infer_params(prompt: str) -> tuple[str, str, int, str]:
    """Derive (building_type, style, floors, size) from a free-form description."""
    p = prompt.lower()

    # Building type
    if any(w in p for w in ["skyscraper", "high-rise", "highrise", "tower", "condo"]):
        building_type = "skyscraper"
    elif any(w in p for w in ["house", "home", "bungalow", "cottage", "detached"]):
        building_type = "house"
    else:
        building_type = "suburban_building"

    # Style / material
    if any(w in p for w in ["timber", "wood", "mass timber"]):
        style = "traditional_brick"
    elif any(w in p for w in ["concrete", "brutalist", "brutalism"]):
        style = "brutalist_concrete"
    elif any(w in p for w in ["retail", "podium", "mall", "plaza", "commercial"]):
        style = "retail_complex"
    else:
        style = "modern_glass_tower"

    # Floors — scan for numbers followed by "floor" / "storey" / "story"
    import re
    m = re.search(r'(\d+)\s*[-]?\s*(floor|storey|story|fl)', p)
    floors = int(m.group(1)) if m else 20
    floors = max(1, min(floors, 80))

    # Size by floor count
    size = "large" if floors > 40 else "medium" if floors > 10 else "small"

    return building_type, style, floors, size


@router.post("/building-image", response_model=GenerateResponse)
def generate_image(req: GenerateRequest):
    # Return 503 when API key is missing — frontend shows a helpful message
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key.startswith("your_") or api_key.startswith("sk-your"):
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY not configured — add it to backend/.env")

    user_desc = req.prompt or (
        f"{req.size or 'medium'} {(req.style or 'modern_glass_tower').replace('_', ' ')} "
        f"{req.building_type or 'building'} {req.floors or 20} floors"
    )

    png, renderer = generate_ai_image(
        style=req.style or "modern_glass_tower",
        building_type=req.building_type or "skyscraper",
        floors=req.floors or 20,
        size=req.size or "medium",
        user_description=user_desc,
    )

    # Fallback: parse the prompt so the Pillow render at least matches the description
    if png is None:
        btype, style, floors, size = _infer_params(user_desc)
        # Override with explicit params when caller sends them
        btype  = req.building_type or btype
        style  = req.style or style
        floors = req.floors or floors
        size   = req.size or size
        png = render_building(btype, style, floors, size)
        renderer = "Pillow · local"

    return GenerateResponse(
        image_b64=base64.b64encode(png).decode(),
        image_path="(in-memory)",
        metadata={
            "renderer": renderer,
            "prompt_length": len(user_desc),
        },
    )
