"""
LangGraph Building Image Agent

Three-node pipeline:
  extract → validate → render

The LLM only touches the extract node. Everything downstream is
deterministic — same validated spec = pixel-identical PNG every time.

Compatible with any OpenAI-compatible endpoint (Qwen, NeMoTron, NVIDIA Build).
"""

from __future__ import annotations

import os
import base64
from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict

from rendering.building_renderer import render_building

load_dotenv()

# ── LLM client (reuses NEMORON_URL from .env) ─────────────────────────────────
_llm = ChatOpenAI(
    base_url=os.getenv("NEMORON_URL", "http://localhost:11434") + "/v1",
    api_key=os.getenv("NGC_API_KEY", "placeholder"),
    model=os.getenv("MODEL_NAME", "qwen3"),
    temperature=0,
)

OUTPUT_DIR = Path(os.getenv("IMAGE_OUTPUT_DIR", "/tmp/urbanforge_images"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ── Structured output schema ────────────────────────────────────────────────────
class BuildingSpec(BaseModel):
    building_type: Literal["skyscraper", "house", "suburban_building"] = Field(
        description="Type of building. Must be one of: skyscraper, house, suburban_building"
    )
    style: Literal[
        "modern_glass_tower", "traditional_brick",
        "brutalist_concrete", "retail_complex"
    ] = Field(
        description="Architectural style. Must be one of: modern_glass_tower, "
                    "traditional_brick, brutalist_concrete, retail_complex"
    )
    floors: int = Field(
        ge=1, le=100,
        description="Number of floors. 1–100 for skyscrapers, 1–3 for houses, 2–15 for suburban."
    )
    size: Literal["small", "medium", "large"] = Field(
        description="Footprint size: small, medium, or large"
    )


# ── Graph state ─────────────────────────────────────────────────────────────────
class BuildingImageState(TypedDict):
    prompt: str                          # raw user input
    spec: Optional[BuildingSpec]         # extracted + validated spec
    errors: list[str]                    # validation errors
    attempts: int                        # extraction retry count
    image_bytes: Optional[bytes]         # rendered PNG
    image_b64: Optional[str]             # base64 for API response
    image_path: Optional[str]            # saved file path
    metadata: dict                       # summary for UI


# ── Node 1: Extract ─────────────────────────────────────────────────────────────
_extractor = _llm.with_structured_output(BuildingSpec)

EXTRACT_SYSTEM = """You extract building parameters from user descriptions.
Map any building description to exactly one of these types:
  - skyscraper: tall buildings, towers, high-rises (>5 floors, narrow)
  - house: single-family homes, cottages, bungalows, residential houses
  - suburban_building: apartments, office parks, mid-rise buildings (2-15 floors, wider)

Map any style description to:
  - modern_glass_tower: glass, modern, contemporary, curtain wall
  - traditional_brick: brick, heritage, classical, Victorian
  - brutalist_concrete: brutalist, concrete, raw, industrial
  - retail_complex: retail, commercial, shopping, mixed-use

If floors are not specified, use sensible defaults:
  skyscraper=30, house=1, suburban_building=6
If size is not specified, use medium."""


def extract_node(state: BuildingImageState) -> BuildingImageState:
    prompt = state["prompt"]
    if state.get("errors"):
        prompt += f"\n\nPrevious errors to correct: {state['errors']}"

    try:
        spec: BuildingSpec = _extractor.invoke([
            {"role": "system", "content": EXTRACT_SYSTEM},
            {"role": "user",   "content": prompt},
        ])
        return {**state, "spec": spec, "errors": [], "attempts": state.get("attempts", 0) + 1}
    except Exception as e:
        return {
            **state,
            "spec": None,
            "errors": [f"Extraction failed: {e}"],
            "attempts": state.get("attempts", 0) + 1,
        }


# ── Node 2: Validate ────────────────────────────────────────────────────────────
FLOOR_LIMITS = {
    "skyscraper":        (5,  100),
    "house":             (1,    3),
    "suburban_building": (2,   15),
}


def validate_node(state: BuildingImageState) -> BuildingImageState:
    spec = state.get("spec")
    errors: list[str] = []

    if spec is None:
        errors.append("No spec extracted.")
        return {**state, "errors": errors}

    lo, hi = FLOOR_LIMITS.get(spec.building_type, (1, 100))
    if not (lo <= spec.floors <= hi):
        errors.append(
            f"{spec.building_type} supports {lo}–{hi} floors, got {spec.floors}. "
            f"Please adjust."
        )

    return {**state, "errors": errors}


# ── Node 3: Render ──────────────────────────────────────────────────────────────
def render_node(state: BuildingImageState) -> BuildingImageState:
    spec = state["spec"]

    # If validation failed and we're out of retries, clamp floors and continue
    if not spec:
        spec = BuildingSpec(
            building_type="skyscraper",
            style="modern_glass_tower",
            floors=20,
            size="medium",
        )

    floors = spec.floors
    lo, hi = FLOOR_LIMITS.get(spec.building_type, (1, 100))
    floors = max(lo, min(hi, floors))

    image_bytes = render_building(
        building_type=spec.building_type,
        style=spec.style,
        floors=floors,
        size=spec.size,
    )

    # Save to disk
    fname = f"{spec.building_type}_{spec.style}_{floors}fl_{spec.size}.png"
    path = OUTPUT_DIR / fname
    path.write_bytes(image_bytes)

    # Metadata for the UI / 3D pipeline
    floor_heights = {"skyscraper": 14, "house": 80, "suburban_building": 18}
    fh = floor_heights.get(spec.building_type, 14)
    size_mults = {"small": 0.72, "medium": 1.0, "large": 1.32}
    sm = size_mults.get(spec.size, 1.0)
    base_widths = {"skyscraper": 190, "house": 280, "suburban_building": 360}
    bw = base_widths.get(spec.building_type, 190)

    metadata = {
        "building_type":      spec.building_type,
        "style":              spec.style,
        "floors":             floors,
        "size":               spec.size,
        "canvas_px":          "800×1000",
        "background_hex":     "#E0E0E0",
        "tower_width_px":     int(bw * sm),
        "tower_height_px":    floors * fh,
        "floor_height_px":    fh,
        "ground_y_px":        870,
        "consistency_rule":   "width fixed per size; height = floors × floor_height",
    }

    return {
        **state,
        "image_bytes": image_bytes,
        "image_b64":   base64.b64encode(image_bytes).decode(),
        "image_path":  str(path),
        "metadata":    metadata,
    }


# ── Routing logic ────────────────────────────────────────────────────────────────
def _route_after_validate(state: BuildingImageState) -> str:
    if state["errors"] and state.get("attempts", 0) < 2:
        return "extract"   # retry extraction with error context
    return "render"        # render with whatever we have (or clamped defaults)


# ── Build the graph ──────────────────────────────────────────────────────────────
_builder = StateGraph(BuildingImageState)
_builder.add_node("extract",  extract_node)
_builder.add_node("validate", validate_node)
_builder.add_node("render",   render_node)

_builder.set_entry_point("extract")
_builder.add_edge("extract", "validate")
_builder.add_conditional_edges(
    "validate",
    _route_after_validate,
    {"extract": "extract", "render": "render"},
)
_builder.add_edge("render", END)

pipeline = _builder.compile()


# ── Convenience wrapper ──────────────────────────────────────────────────────────
def generate_building_image(
    prompt: str = "",
    building_type: str | None = None,
    style: str | None = None,
    floors: int | None = None,
    size: str | None = None,
) -> dict:
    """
    Call the agent from code or a FastAPI endpoint.

    If building_type/style/floors/size are provided directly, the LLM
    extraction node is bypassed and we go straight to validate → render.

    Returns dict with: image_b64, image_path, metadata
    """
    if building_type and floors is not None:
        # Direct call — skip LLM, build spec directly
        spec = BuildingSpec(
            building_type=building_type,
            style=style or "modern_glass_tower",
            floors=floors,
            size=size or "medium",
        )
        state: BuildingImageState = {
            "prompt":      prompt,
            "spec":        spec,
            "errors":      [],
            "attempts":    1,
            "image_bytes": None,
            "image_b64":   None,
            "image_path":  None,
            "metadata":    {},
        }
        # Jump straight to validate then render
        state = validate_node(state)
        state = render_node(state)
    else:
        # Full LangGraph pipeline with LLM extraction
        state = pipeline.invoke({
            "prompt":      prompt,
            "spec":        None,
            "errors":      [],
            "attempts":    0,
            "image_bytes": None,
            "image_b64":   None,
            "image_path":  None,
            "metadata":    {},
        })

    return {
        "image_b64":  state["image_b64"],
        "image_path": state["image_path"],
        "metadata":   state["metadata"],
    }
