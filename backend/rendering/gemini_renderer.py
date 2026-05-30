"""
Gemini Imagen 3 building image generator via LangChain.

Pipeline:
  1. ChatGoogleGenerativeAI (LangChain) — crafts a hyperrealistic Imagen 3 prompt
     from the building spec using a structured prompt-engineering chain.
  2. google-genai SDK — sends the enhanced prompt to Imagen 3
     (imagen-3.0-generate-002) and returns PNG bytes.

Required .env:
  GOOGLE_API_KEY=...   (Google AI Studio — aistudio.google.com/app/apikey)
"""

from __future__ import annotations

import os
import base64
from io import BytesIO
from typing import Optional

from PIL import Image

# ── Optional imports — fail gracefully if packages not installed ───────────────
_DEPS_OK = False
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from google import genai
    from google.genai import types as genai_types
    _DEPS_OK = True
except ImportError:
    pass


# ── Prompt-engineering chain ───────────────────────────────────────────────────

_SYSTEM = (
    "You are an expert architectural visualisation artist and Imagen 3 prompt engineer.\n\n"
    "Your sole task is to write image-generation prompts that produce a single output:\n"
    "a HYPERREALISTIC, HEAD-ON ARCHITECTURAL ELEVATION of a building — the kind of "
    "drawing an architect submits for a planning application.\n\n"
    "Visual contract — every prompt you write MUST enforce:\n"
    "  ANGLE   : perfectly flat, dead-on front elevation, 0° azimuth, camera at mid-building "
    "height, zero perspective tilt or convergence\n"
    "  SUBJECT : the complete building only — full height from roofline to base, "
    "full width including any wings or setbacks, nothing cropped\n"
    "  BG      : flat solid light grey (#E0E0E0) — no sky gradient, no ground plane, "
    "no shadows cast on the background\n"
    "  STYLE   : ultra-photorealistic architectural render — crisp material textures "
    "(glass reflections, brick courses, concrete grain), studio-quality diffuse lighting "
    "with no harsh shadows, razor-sharp focus edge-to-edge\n"
    "  EXCLUDE : no people, no vehicles, no trees, no landscaping, no street furniture, "
    "no signage, no motion blur, no vignetting, no lens distortion, "
    "no watermarks, no text overlays\n\n"
    "Include style-specific material and detail language (e.g. for Gothic: "
    "\"lancet arched windows, flying buttresses, carved limestone tracery\"; "
    "for Modern Glass: \"floor-to-ceiling curtain wall, aluminium mullions, "
    "blue-green tinted reflective glass\").\n\n"
    "Return ONLY the prompt — no preamble, no labels, no quotation marks."
)

_HUMAN_TEMPLATE = (
    "Generate a hyperrealistic head-on architectural elevation image for:\n\n"
    "  Building type : {building_type}\n"
    "  Style         : {style}\n"
    "  Floors        : {floors}\n"
    "  Scale         : {size}\n\n"
    "Write the Imagen 3 prompt now."
)


def _make_chain(api_key: str):
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=api_key,
        temperature=0.3,
        max_output_tokens=256,
    )
    prompt_tpl = ChatPromptTemplate.from_messages([
        ("system", _SYSTEM),
        ("human", _HUMAN_TEMPLATE),
    ])
    return prompt_tpl | llm | StrOutputParser()


# ── Fallback prompt (no LLM) ───────────────────────────────────────────────────

def _fallback_prompt(style: str, building_type: str, floors: int, size: str) -> str:
    style_desc = style.replace("_", " ")
    type_desc  = building_type.replace("_", " ")
    return (
        f"Hyperrealistic head-on architectural front elevation of a {style_desc} "
        f"{type_desc}, {floors} floors tall, {size} scale. "
        "Perfectly flat, dead-on 0-degree azimuth view, camera at mid-building height, "
        "zero perspective convergence. "
        "Solid flat light grey background #E0E0E0, no sky, no ground plane. "
        "Ultra-sharp material textures — crisp glass reflections, precise brickwork, "
        "fine concrete grain. Studio diffuse lighting, no harsh shadows. "
        "Full building visible from roofline to base, nothing cropped. "
        "No people, no trees, no vehicles, no signage, no lens distortion, no watermarks."
    )


# ── Image normalisation ────────────────────────────────────────────────────────

def _normalise(raw: bytes) -> bytes:
    img = Image.open(BytesIO(raw)).convert("RGB")
    canvas = Image.new("RGB", (800, 1000), (224, 224, 224))
    img.thumbnail((800, 1000), Image.LANCZOS)
    x = (800 - img.width) // 2
    y = (1000 - img.height) // 2
    canvas.paste(img, (x, y))
    buf = BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


# ── Public entry point ─────────────────────────────────────────────────────────

def generate_gemini_image(
    style: str,
    building_type: str,
    floors: int,
    size: str,
) -> Optional[bytes]:
    """
    Generate a hyperrealistic head-on building image via Google Imagen 3.

    Steps:
      1. LangChain chain (Gemini 2.0 Flash) → enhanced architectural prompt
      2. Imagen 3 (imagen-3.0-generate-002) → PNG image bytes

    Returns PNG bytes, or None if GOOGLE_API_KEY is missing / call fails.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key or not _DEPS_OK:
        return None

    # Step 1 — enhance prompt via LangChain chain
    try:
        chain = _make_chain(api_key)
        enhanced_prompt = chain.invoke({
            "building_type": building_type,
            "style": style,
            "floors": floors,
            "size": size,
        })
    except Exception as e:
        print(f"[gemini_renderer] Prompt chain failed, using fallback: {e}")
        enhanced_prompt = _fallback_prompt(style, building_type, floors, size)

    # Step 2 — generate image via Imagen 3
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_images(
            model="imagen-3.0-generate-002",
            prompt=enhanced_prompt,
            config=genai_types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="3:4",
                safety_filter_level="block_low_and_above",
                person_generation="dont_allow",
            ),
        )

        if not response.generated_images:
            print("[gemini_renderer] Imagen 3 returned no images")
            return None

        raw_bytes = response.generated_images[0].image.image_bytes
        return _normalise(raw_bytes)

    except Exception as e:
        print(f"[gemini_renderer] Imagen 3 call failed: {e}")
        return None
