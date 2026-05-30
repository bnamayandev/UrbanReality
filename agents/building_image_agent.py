"""
Building Image Agent
LangGraph pipeline: Extract → Validate → Render

Input:  natural language building description
Output: deterministic 2D front-elevation PNG + params JSON
        (background locked to #E0E0E0, fixed scale, no hallucinated angles)

Usage:
    python building_image_agent.py "40 floor glass skyscraper with retail podium"
    OR import and call generate_building_image(prompt) from FastAPI
"""

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Literal, TypedDict

from openai import OpenAI
from PIL import Image, ImageDraw
from pydantic import BaseModel, Field, ValidationError
from langgraph.graph import StateGraph, END

# ─── Config ───────────────────────────────────────────────────────────────────

NIM_BASE_URL = os.getenv("MODEL_URL",  "https://integrate.api.nvidia.com/v1")
NIM_API_KEY  = os.getenv("NGC_API_KEY", "not-needed")
MODEL_NAME   = os.getenv("MODEL_NAME",  "nvidia/nemotron-mini-4b-instruct")
OUTPUT_DIR   = Path(os.getenv("OUTPUT_DIR", "./agents/generated_buildings"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

client = OpenAI(base_url=NIM_BASE_URL, api_key=NIM_API_KEY)

# ─── Schema ───────────────────────────────────────────────────────────────────

BuildingType  = Literal["skyscraper", "residential_highrise", "residential_midrise",
                         "commercial", "mixed_use", "industrial"]
MaterialType  = Literal["glass", "concrete", "brick", "steel", "mass_timber"]
WindowStyle   = Literal["grid", "ribbon", "curtain_wall", "minimal"]


class BuildingParams(BaseModel):
    building_type:    BuildingType
    floors:           int  = Field(..., ge=1,  le=200)
    footprint_width:  int  = Field(..., ge=10, le=200, description="meters")
    footprint_depth:  int  = Field(..., ge=10, le=200, description="meters")
    material:         MaterialType
    window_style:     WindowStyle
    has_podium:       bool = False
    podium_floors:    int  = Field(0, ge=0, le=15)


# Per-type floor limits used in validation
FLOOR_LIMITS: dict[str, tuple[int, int]] = {
    "skyscraper":           (20,  200),
    "residential_highrise": (10,   60),
    "residential_midrise":  (3,    20),
    "commercial":           (2,    60),
    "mixed_use":            (5,    80),
    "industrial":           (1,    10),
}

# ─── Agent State ──────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    raw_prompt:       str
    building_params:  dict | None
    validation_errors: list[str]
    image_path:       str | None
    retry_count:      int


# ─── Node 1: Extract ──────────────────────────────────────────────────────────

_EXTRACT_SYSTEM = """\
You are a building parameter extractor for a 3D rendering pipeline.
Parse the user's description and return ONLY valid JSON — no markdown fences, no explanation.

Return exactly this structure:
{
  "building_type":   "skyscraper|residential_highrise|residential_midrise|commercial|mixed_use|industrial",
  "floors":          <integer 1-200>,
  "footprint_width": <integer 10-200 — estimated width in meters>,
  "footprint_depth": <integer 10-200 — estimated depth in meters>,
  "material":        "glass|concrete|brick|steel|mass_timber",
  "window_style":    "grid|ribbon|curtain_wall|minimal",
  "has_podium":      <true|false>,
  "podium_floors":   <integer 0-15>
}

Defaults when unspecified:
  skyscraper       → 40 floors, glass, curtain_wall, footprint 40x40
  condo/highrise   → residential_highrise, 25 floors, concrete, grid
  office           → commercial, 15 floors, glass, ribbon
  midrise/walkup   → residential_midrise, 8 floors, brick, grid
  warehouse        → industrial, 3 floors, concrete, minimal
  curtain_wall     → always glass material
  has_podium=true  → podium_floors = max(3, floors // 8)
"""


def extract_node(state: AgentState) -> AgentState:
    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system",  "content": _EXTRACT_SYSTEM},
            {"role": "user",    "content": state["raw_prompt"]},
        ],
        temperature=0.0,
        max_tokens=256,
    )
    raw = resp.choices[0].message.content.strip()

    # Strip markdown fences if the model wraps in ```json ... ```
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            try:
                params = json.loads(part)
                return {**state, "building_params": params, "validation_errors": []}
            except json.JSONDecodeError:
                continue
        return {**state, "building_params": None,
                "validation_errors": ["LLM returned non-parseable JSON"]}

    try:
        params = json.loads(raw)
        return {**state, "building_params": params, "validation_errors": []}
    except json.JSONDecodeError:
        return {**state, "building_params": None,
                "validation_errors": [f"LLM output was not JSON: {raw[:120]}"]}


# ─── Node 2: Validate ─────────────────────────────────────────────────────────

def validate_node(state: AgentState) -> AgentState:
    p = state["building_params"]
    if not p:
        return {**state, "validation_errors": state["validation_errors"] or ["No params extracted"]}

    # Pydantic schema check
    try:
        bp = BuildingParams(**p)
    except ValidationError as e:
        errs = [f"{err['loc'][0]}: {err['msg']}" for err in e.errors()]
        return {**state, "validation_errors": errs}

    errors: list[str] = []

    # Floor range per building type
    lo, hi = FLOOR_LIMITS.get(bp.building_type, (1, 200))
    if bp.floors < lo:
        errors.append(f"{bp.building_type} needs ≥{lo} floors (got {bp.floors}). Raise floors.")
    if bp.floors > hi:
        errors.append(f"{bp.building_type} supports max {hi} floors (got {bp.floors}). Lower floors or change type.")

    # Podium logic
    if bp.has_podium:
        if bp.podium_floors == 0:
            p["podium_floors"] = max(3, bp.floors // 8)  # auto-fix silently
        elif bp.podium_floors >= bp.floors:
            errors.append(f"podium_floors ({bp.podium_floors}) must be less than floors ({bp.floors}).")

    # Curtain wall should be glass
    if bp.window_style == "curtain_wall" and bp.material != "glass":
        p["material"] = "glass"  # auto-fix: curtain wall is always glass

    return {**state, "building_params": p, "validation_errors": errors}


# ─── Node 3: Generate (Deterministic Pillow Renderer) ─────────────────────────

# Locked constants — the 3D pipeline depends on these never changing
IMG_W, IMG_H = 512, 512
BG_COLOR     = (224, 224, 224)   # #E0E0E0 — absolute, do not change
PADDING      = 44
GROUND_Y     = IMG_H - PADDING
MAX_BLDG_H   = GROUND_Y - PADDING
MAX_BLDG_W   = IMG_W - PADDING * 2

PALETTE: dict[str, dict[str, tuple]] = {
    "glass":       {"facade": (168, 200, 218), "window": (100, 172, 210), "frame": (50,  72,  90)},
    "concrete":    {"facade": (148, 158, 168), "window":  (90, 138, 168), "frame": (64,  80,  96)},
    "brick":       {"facade": (188, 108,  70), "window":  (90, 138, 168), "frame": (50,  60,  90)},
    "steel":       {"facade": (110, 130, 148), "window": (130, 180, 208), "frame": (40,  60,  78)},
    "mass_timber": {"facade": (200, 164, 104), "window":  (90, 138, 168), "frame": (88,  58,  36)},
}


def _floor_px(floors: int, available_h: int) -> float:
    """Pixels per floor, capped so tall buildings still fit."""
    return min(available_h / max(floors, 1), 10.0)


def _draw_windows(draw: ImageDraw.ImageDraw,
                  x0: int, y0: int, x1: int, y1: int,
                  floors: int, style: WindowStyle, colors: dict) -> None:
    if floors <= 0:
        return
    bw = x1 - x0
    bh = y1 - y0
    fh = bh / floors  # pixels per floor

    if style == "curtain_wall":
        # Fill with glass color, then draw structural grid lines
        draw.rectangle([x0, y0, x1, y1], fill=colors["window"])
        cols = max(3, bw // 24)
        for c in range(cols + 1):
            lx = x0 + int(c * bw / cols)
            draw.line([lx, y0, lx, y1], fill=colors["frame"], width=1)
        for f in range(floors + 1):
            ly = y0 + int(f * fh)
            draw.line([x0, ly, x1, ly], fill=colors["frame"], width=1)

    elif style == "ribbon":
        # Full-width horizontal bands on alternating floors
        for f in range(floors):
            if f % 2 == 0:
                wy0 = y0 + f * fh + fh * 0.12
                wy1 = y0 + f * fh + fh * 0.75
                draw.rectangle([x0 + 4, int(wy0), x1 - 4, int(wy1)],
                                fill=colors["window"])

    elif style == "minimal":
        cols = max(1, bw // 70)
        cw = bw / cols
        for f in range(floors):
            for c in range(cols):
                wx0 = x0 + c * cw + cw * 0.25
                wx1 = x0 + (c + 1) * cw - cw * 0.25
                wy0 = y0 + f * fh + fh * 0.2
                wy1 = y0 + (f + 1) * fh - fh * 0.2
                draw.rectangle([int(wx0), int(wy0), int(wx1), int(wy1)],
                                fill=colors["window"])

    else:  # grid (default)
        cols = max(2, bw // 36)
        cw = bw / cols
        for f in range(floors):
            for c in range(cols):
                wx0 = x0 + c * cw + cw * 0.12
                wx1 = x0 + (c + 1) * cw - cw * 0.12
                wy0 = y0 + f * fh + fh * 0.10
                wy1 = y0 + (f + 1) * fh - fh * 0.14
                draw.rectangle([int(wx0), int(wy0), int(wx1), int(wy1)],
                                fill=colors["window"])


def _render(params: dict) -> Image.Image:
    bp = BuildingParams(**params)
    colors = PALETTE[bp.material]

    img  = Image.new("RGB", (IMG_W, IMG_H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # ── Scale tower width: proportional to footprint_width (range 90–300px) ──
    w_norm  = (bp.footprint_width - 10) / 190          # 0–1
    bldg_w  = int(90 + w_norm * 210)
    bldg_w  = min(bldg_w, MAX_BLDG_W)

    tower_floors = bp.floors - bp.podium_floors
    px_per_fl    = _floor_px(bp.floors, MAX_BLDG_H)
    tower_h      = int(tower_floors * px_per_fl)
    podium_h     = int(bp.podium_floors * px_per_fl) if bp.has_podium else 0
    cx           = IMG_W // 2

    # ── Podium (wider than tower) ──
    if bp.has_podium and podium_h > 0:
        pod_w = min(int(bldg_w * 1.45), MAX_BLDG_W)
        px0 = cx - pod_w // 2
        px1 = cx + pod_w // 2
        py0 = GROUND_Y - podium_h
        draw.rectangle([px0, py0, px1, GROUND_Y],
                       fill=colors["facade"], outline=colors["frame"], width=2)
        _draw_windows(draw, px0, py0, px1, GROUND_Y,
                      bp.podium_floors, "grid", colors)

    # ── Tower ──
    tx0 = cx - bldg_w // 2
    tx1 = cx + bldg_w // 2
    ty0 = GROUND_Y - podium_h - tower_h
    ty1 = GROUND_Y - podium_h

    facade_fill = colors["window"] if bp.window_style == "curtain_wall" else colors["facade"]
    draw.rectangle([tx0, ty0, tx1, ty1],
                   fill=facade_fill, outline=colors["frame"], width=2)
    _draw_windows(draw, tx0, ty0, tx1, ty1,
                  tower_floors, bp.window_style, colors)

    # ── Rooftop cap ──
    draw.rectangle([tx0, ty0 - 4, tx1, ty0 + 2],
                   fill=colors["frame"])

    # ── Ground line ──
    draw.line([PADDING // 2, GROUND_Y, IMG_W - PADDING // 2, GROUND_Y],
              fill=(140, 140, 140), width=2)

    return img


def generate_node(state: AgentState) -> AgentState:
    img      = _render(state["building_params"])
    stem     = f"building_{uuid.uuid4().hex[:10]}"
    img_path = OUTPUT_DIR / f"{stem}.png"
    jsn_path = OUTPUT_DIR / f"{stem}.json"

    img.save(str(img_path))
    jsn_path.write_text(json.dumps(state["building_params"], indent=2))

    return {**state, "image_path": str(img_path)}


# ─── Node: Retry / Fail ───────────────────────────────────────────────────────

def retry_node(state: AgentState) -> AgentState:
    error_text = "; ".join(state["validation_errors"])
    corrected  = f"{state['raw_prompt']}\n\n[Auto-correction needed: {error_text}]"
    return {**state, "raw_prompt": corrected, "retry_count": state["retry_count"] + 1}


def fail_node(state: AgentState) -> AgentState:
    print(f"[Agent] Failed after {state['retry_count']} retries: {state['validation_errors']}")
    return state


# ─── Routing ──────────────────────────────────────────────────────────────────

def _route_validate(state: AgentState) -> str:
    if not state["validation_errors"]:
        return "generate"
    if state["retry_count"] >= 2:
        return "fail"
    return "retry"


# ─── Build Graph ──────────────────────────────────────────────────────────────

def _build_graph() -> "CompiledGraph":
    g = StateGraph(AgentState)
    g.add_node("extract",  extract_node)
    g.add_node("validate", validate_node)
    g.add_node("generate", generate_node)
    g.add_node("retry",    retry_node)
    g.add_node("fail",     fail_node)

    g.set_entry_point("extract")
    g.add_edge("extract", "validate")
    g.add_conditional_edges("validate", _route_validate, {
        "generate": "generate",
        "retry":    "retry",
        "fail":     "fail",
    })
    g.add_edge("retry",    "extract")   # re-run extract with corrected prompt
    g.add_edge("generate", END)
    g.add_edge("fail",     END)
    return g.compile()


_agent = _build_graph()


# ─── Public API ───────────────────────────────────────────────────────────────

def generate_building_image(prompt: str) -> dict:
    """
    Takes a natural language building description.
    Returns:
        { "image_path": str, "params": dict }   on success
        { "error": list[str] }                  on failure
    """
    result = _agent.invoke({
        "raw_prompt":       prompt,
        "building_params":  None,
        "validation_errors": [],
        "image_path":       None,
        "retry_count":      0,
    })
    if result["image_path"]:
        return {"image_path": result["image_path"], "params": result["building_params"]}
    return {"error": result["validation_errors"]}


# ─── FastAPI integration (drop into Wali's backend) ───────────────────────────
# from fastapi import APIRouter
# from pydantic import BaseModel as PBM
# router = APIRouter()
# class PromptReq(PBM):
#     prompt: str
# @router.post("/api/generate-image")
# def api_generate(req: PromptReq):
#     return generate_building_image(req.prompt)


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 \
             else "a 32 floor glass residential tower with a 4 floor retail podium"
    print(f"[Agent] Prompt: {prompt}\n")
    out = generate_building_image(prompt)
    if "image_path" in out:
        print(f"[Agent] Image saved: {out['image_path']}")
        print(f"[Agent] Params:      {json.dumps(out['params'], indent=2)}")
    else:
        print(f"[Agent] Error: {out['error']}")
