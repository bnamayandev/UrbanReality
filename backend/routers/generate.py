"""
POST /generate/building-image

Accepts either:
  - A natural language prompt (goes through LLM extraction)
  - Direct structured parameters (bypasses LLM, fully deterministic)

Returns base64-encoded PNG + metadata.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from agents.building_image_agent import generate_building_image

router = APIRouter(prefix="/generate", tags=["generate"])


class GenerateRequest(BaseModel):
    # Option A: natural language
    prompt: Optional[str] = None

    # Option B: direct params (faster, deterministic, no LLM needed)
    building_type: Optional[str] = None   # skyscraper | house | suburban_building
    style:         Optional[str] = None   # modern_glass_tower | traditional_brick | ...
    floors:        Optional[int] = None
    size:          Optional[str] = None   # small | medium | large


class GenerateResponse(BaseModel):
    image_b64: str      # PNG as base64 — prefix with "data:image/png;base64," for <img>
    image_path: str     # server-side saved path
    metadata: dict      # pixel geometry + consistency params for 3D pipeline


@router.post("/building-image", response_model=GenerateResponse)
def generate_image(req: GenerateRequest):
    result = generate_building_image(
        prompt=req.prompt or "",
        building_type=req.building_type,
        style=req.style,
        floors=req.floors,
        size=req.size,
    )
    return GenerateResponse(**result)
