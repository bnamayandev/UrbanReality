"""
Impact Analysis Agent — calls NeMoTron with building specs + spatial context,
returns structured scores and descriptions for each impact dimension.
"""

import os
import json
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

MODEL_URL   = os.getenv("MODEL_URL",   "http://localhost:11434/v1")
MODEL_NAME  = os.getenv("MODEL_NAME",  "nemotron-3-super:latest")
NGC_API_KEY = os.getenv("NGC_API_KEY", "not-needed")

_client = AsyncOpenAI(base_url=MODEL_URL, api_key=NGC_API_KEY)

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
    traffic = spatial_context.get("traffic_intersections", [])
    trees   = spatial_context.get("street_trees", [])
    stops   = spatial_context.get("ttc_stops", [])
    bizs    = spatial_context.get("businesses", [])
    parks   = spatial_context.get("parks", [])
    zoning  = spatial_context.get("zoning", [])
    zh      = spatial_context.get("zoning_height")
    hood    = spatial_context.get("neighbourhood")

    # Aggregate real traffic numbers for the prompt
    total_vehicles = sum(t.get("total_vehicle", 0) or 0 for t in traffic)
    am_peak = sum(t.get("am_peak_vehicle", 0) or 0 for t in traffic)
    pm_peak = sum(t.get("pm_peak_vehicle", 0) or 0 for t in traffic)

    user_prompt = f"""
Building Specifications:
{json.dumps(building, indent=2)}

Neighbourhood Context:
{json.dumps(hood, indent=2) if hood else "Not available"}

Zoning:
- Land use: {json.dumps(zoning[:1], indent=2)}
- Height overlay: {json.dumps(zh, indent=2) if zh else "No height overlay found"}

Traffic (within 500m, {len(traffic)} intersections):
- Total daily vehicle volume: {total_vehicles:,}
- AM peak vehicles: {am_peak:,}
- PM peak vehicles: {pm_peak:,}
- Sample intersections: {json.dumps(traffic[:3], indent=2)}

Transit:
- TTC stops within 500m: {len(stops)}
- Nearest stops: {json.dumps(stops[:3], indent=2)}

Environment:
- Street trees within 500m: {len(trees)} (species sample: {[t.get('common_name') for t in trees[:5]]})
- Parks: {json.dumps(parks[:2], indent=2)}

Economy:
- Active businesses within 500m: {len(bizs)}
- Business categories: {list(set(b.get('Category','') for b in bizs[:20] if b.get('Category')))}

Produce the impact assessment JSON.
"""

    response = await _client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=1024,
    )
    content = response.choices[0].message.content.strip()

    # Strip markdown fences if model wraps the JSON
    if "```" in content:
        for part in content.split("```"):
            part = part.strip().lstrip("json").strip()
            try:
                return json.loads(part)
            except json.JSONDecodeError:
                continue

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
