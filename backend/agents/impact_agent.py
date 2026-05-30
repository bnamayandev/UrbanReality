"""
Impact Analysis Agent — calls NeMoTron with building specs + spatial context,
returns structured scores and descriptions for each impact dimension.
"""

import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

NEMORON_URL = os.getenv("NEMORON_URL", "http://localhost:8000")

SYSTEM_PROMPT = """You are an urban planning AI analyst for the city of Toronto.
Given a proposed building's specifications and nearby geospatial context data,
produce a structured impact assessment across five dimensions.

Respond ONLY with valid JSON in exactly this format:
{
  "environmental": { "score": <0-100>, "description": "<2 sentences>" },
  "traffic":       { "score": <0-100>, "description": "<2 sentences>" },
  "economic":      { "score": <0-100>, "description": "<2 sentences>" },
  "infrastructure":{ "score": <0-100>, "description": "<2 sentences>" },
  "housing":       { "score": <0-100>, "description": "<2 sentences>" }
}

Score meaning: 0 = minimal impact, 100 = extreme impact. Be specific and cite numbers.
"""


async def run_impact_analysis(building: dict, spatial_context: dict) -> dict:
    user_prompt = f"""
Building Specifications:
{json.dumps(building, indent=2)}

Nearby Context (within 500m):
- Traffic intersections: {len(spatial_context.get('traffic_intersections', []))} found
  {json.dumps(spatial_context.get('traffic_intersections', [])[:3], indent=2)}
- TTC stops: {len(spatial_context.get('ttc_stops', []))} found
  {json.dumps(spatial_context.get('ttc_stops', [])[:3], indent=2)}
- Street trees: {len(spatial_context.get('street_trees', []))} found
- Businesses: {len(spatial_context.get('businesses', []))} found
- Parks: {json.dumps(spatial_context.get('parks', [])[:2], indent=2)}
- Zoning: {json.dumps(spatial_context.get('zoning', [])[:1], indent=2)}

Produce the impact assessment JSON.
"""

    payload = {
        "model": "nvidia/llama-3.1-nemotron-70b-instruct",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 1024,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{NEMORON_URL}/v1/chat/completions",
            json=payload,
        )
        response.raise_for_status()

    content = response.json()["choices"][0]["message"]["content"]

    # Strip markdown code fences if model wraps the JSON
    content = content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]

    return json.loads(content)


def fallback_impact(building: dict) -> dict:
    """Deterministic fallback if NeMoTron is unreachable during demo."""
    floors = building.get("floors", 20)
    fp = building.get("footprint_m2", 2000)
    units = building.get("units_per_floor", 10)
    total_units = floors * units

    return {
        "environmental": {
            "score": min(90, int(fp / 100)),
            "description": f"Estimated {int(fp / 10)} trees displaced by footprint. "
                           f"Shadow cast across approximately {int(fp * floors * 0.0003):.0f}k m² of adjacent lots.",
        },
        "traffic": {
            "score": min(90, floors * 2),
            "description": f"Estimated +{floors * 14} daily vehicle trips added to nearby intersections. "
                           f"Peak-hour congestion at surrounding roads expected to increase.",
        },
        "economic": {
            "score": min(95, 50 + floors),
            "description": f"~{total_units} new residents projected to inject ~${total_units * 3200 // 1000}K/yr into local retail. "
                           f"Property values within 300m may shift +4–9% over 5 years.",
        },
        "infrastructure": {
            "score": min(85, floors * 2),
            "description": f"Estimated water demand: +{total_units * 220} L/day. "
                           f"TTC stops nearby will see approximately +{floors * 3} daily boardings.",
        },
        "housing": {
            "score": max(10, 80 - floors),
            "description": f"Adds {total_units} units to city supply against a 0.7% vacancy rate. "
                           f"Addresses approximately {int(total_units * 0.8)} units of unmet demand.",
        },
    }
