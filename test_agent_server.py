"""
Standalone test server for the building image agent.
No database required — only tests the generate endpoint.

Run:  python3 test_agent_server.py
Open: http://localhost:8080
"""

import sys, os, re, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "backend", ".env"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional

from rendering.ai_renderer import generate_ai_image
import base64

# ── Concept map — building archetype → (building_type, style) ─────────────────
# Covers real-world building names so "castle", "museum", "church" etc. all work.
CONCEPT_MAP = {
    # Gothic
    "castle":       ("skyscraper",        "gothic"),
    "fortress":     ("skyscraper",        "gothic"),
    "fort":         ("suburban_building", "gothic"),
    "cathedral":    ("skyscraper",        "gothic"),
    "church":       ("suburban_building", "gothic"),
    "chapel":       ("house",             "gothic"),
    "abbey":        ("suburban_building", "gothic"),
    "monastery":    ("suburban_building", "gothic"),
    "basilica":     ("suburban_building", "gothic"),
    "gothic":       ("skyscraper",        "gothic"),
    "tower of london": ("skyscraper",     "gothic"),

    # Baroque
    "palace":       ("skyscraper",        "baroque"),
    "mansion":      ("house",             "baroque"),
    "manor":        ("house",             "baroque"),
    "manor house":  ("house",             "baroque"),
    "estate":       ("house",             "baroque"),
    "chateau":      ("house",             "baroque"),
    "château":      ("house",             "baroque"),
    "opera house":  ("suburban_building", "baroque"),
    "opera":        ("suburban_building", "baroque"),
    "ballroom":     ("suburban_building", "baroque"),

    # Neoclassical
    "museum":       ("suburban_building", "neoclassical"),
    "art museum":   ("suburban_building", "neoclassical"),
    "gallery":      ("suburban_building", "neoclassical"),
    "courthouse":   ("suburban_building", "neoclassical"),
    "parliament":   ("suburban_building", "neoclassical"),
    "capitol":      ("suburban_building", "neoclassical"),
    "senate":       ("suburban_building", "neoclassical"),
    "city hall":    ("suburban_building", "neoclassical"),
    "town hall":    ("suburban_building", "neoclassical"),
    "bank":         ("suburban_building", "neoclassical"),
    "treasury":     ("suburban_building", "neoclassical"),
    "library":      ("suburban_building", "neoclassical"),
    "university":   ("suburban_building", "neoclassical"),
    "college":      ("suburban_building", "neoclassical"),
    "temple":       ("suburban_building", "neoclassical"),
    "pantheon":     ("suburban_building", "neoclassical"),
    "embassy":      ("suburban_building", "neoclassical"),
    "memorial":     ("suburban_building", "neoclassical"),
    "post office":  ("suburban_building", "neoclassical"),
    "old school":   ("suburban_building", "neoclassical"),

    # Art Deco
    "hotel":        ("skyscraper",        "art_deco"),
    "grand hotel":  ("skyscraper",        "art_deco"),
    "theater":      ("suburban_building", "art_deco"),
    "theatre":      ("suburban_building", "art_deco"),
    "cinema":       ("suburban_building", "art_deco"),
    "radio station":("suburban_building", "art_deco"),
    "train station":("suburban_building", "art_deco"),
    "deco":         ("skyscraper",        "art_deco"),

    # Industrial
    "factory":      ("suburban_building", "industrial"),
    "warehouse":    ("suburban_building", "industrial"),
    "brewery":      ("suburban_building", "industrial"),
    "distillery":   ("suburban_building", "industrial"),
    "mill":         ("suburban_building", "industrial"),
    "power plant":  ("suburban_building", "industrial"),
    "power station":("suburban_building", "industrial"),
    "depot":        ("suburban_building", "industrial"),
    "hangar":       ("suburban_building", "industrial"),
    "shipyard":     ("suburban_building", "industrial"),
    "studio":       ("suburban_building", "industrial"),
    "loft":         ("suburban_building", "industrial"),

    # Contemporary
    "hospital":     ("suburban_building", "contemporary"),
    "clinic":       ("suburban_building", "contemporary"),
    "airport":      ("suburban_building", "contemporary"),
    "terminal":     ("suburban_building", "contemporary"),
    "tech hub":     ("skyscraper",        "contemporary"),
    "startup":      ("skyscraper",        "contemporary"),
    "research center":("suburban_building","contemporary"),
    "data center":  ("suburban_building", "contemporary"),
    "pavilion":     ("suburban_building", "contemporary"),

    # Modern glass
    "office":       ("skyscraper",        "modern_glass_tower"),
    "headquarters": ("skyscraper",        "modern_glass_tower"),
    "hq":           ("skyscraper",        "modern_glass_tower"),
    "corporate":    ("skyscraper",        "modern_glass_tower"),
    "tower":        ("skyscraper",        "modern_glass_tower"),
    "skyscraper":   ("skyscraper",        "modern_glass_tower"),
    "high rise":    ("skyscraper",        "modern_glass_tower"),
    "highrise":     ("skyscraper",        "modern_glass_tower"),
    "condo":        ("skyscraper",        "modern_glass_tower"),

    # Traditional brick
    "school":       ("suburban_building", "traditional_brick"),
    "primary school":("suburban_building","traditional_brick"),
    "high school":  ("suburban_building", "traditional_brick"),
    "pub":          ("house",             "traditional_brick"),
    "inn":          ("house",             "traditional_brick"),
    "cottage":      ("house",             "traditional_brick"),
    "house":        ("house",             "traditional_brick"),
    "home":         ("house",             "traditional_brick"),
    "bungalow":     ("house",             "traditional_brick"),
    "townhouse":    ("house",             "traditional_brick"),
    "victorian house":("house",           "traditional_brick"),
    "fire station": ("suburban_building", "traditional_brick"),

    # Brutalist
    "prison":       ("suburban_building", "brutalist_concrete"),
    "jail":         ("suburban_building", "brutalist_concrete"),
    "bunker":       ("suburban_building", "brutalist_concrete"),
    "parking garage":("suburban_building","brutalist_concrete"),
    "car park":     ("suburban_building", "brutalist_concrete"),
    "soviet":       ("skyscraper",        "brutalist_concrete"),
    "brutalist":    ("skyscraper",        "brutalist_concrete"),

    # Retail
    "mall":         ("suburban_building", "retail_complex"),
    "shopping center":("suburban_building","retail_complex"),
    "shopping mall":("suburban_building", "retail_complex"),
    "retail park":  ("suburban_building", "retail_complex"),
    "strip mall":   ("suburban_building", "retail_complex"),
    "market":       ("suburban_building", "retail_complex"),
    "supermarket":  ("suburban_building", "retail_complex"),
    "store":        ("suburban_building", "retail_complex"),
    "plaza":        ("suburban_building", "retail_complex"),
}

# ── LLM fallback — calls model server when concept map doesn't match ───────────
_LLM_PROMPT = """You are a building parameter extractor. Given a building description,
return ONLY a JSON object with these exact keys — nothing else, no explanation:

{{"building_type": <"skyscraper"|"house"|"suburban_building">,
  "style": <"gothic"|"baroque"|"art_deco"|"neoclassical"|"industrial"|"contemporary"|"modern_glass_tower"|"traditional_brick"|"brutalist_concrete"|"retail_complex">,
  "floors": <integer 1-100>,
  "size": <"small"|"medium"|"large">}}

Style guide:
- castle/fortress/medieval → gothic
- palace/mansion/ornate/baroque → baroque
- museum/courthouse/government/temple/library/university → neoclassical
- art deco/hotel/1920s/stepped geometric → art_deco
- factory/warehouse/industrial/loft → industrial
- minimalist/contemporary/clean/white/modern hospital → contemporary
- glass/curtain wall/modern office/corporate → modern_glass_tower
- brick/victorian/heritage/traditional house → traditional_brick
- brutalist/concrete/prison/bunker → brutalist_concrete
- mall/retail/shopping/commercial → retail_complex

Building type guide:
- Very tall (>10 floors), towers, skyscrapers → skyscraper
- Small residential, 1-3 floors → house
- Mid-rise, wide buildings, 2-15 floors → suburban_building

Description: "{prompt}"
"""


def _llm_parse(text: str) -> dict | None:
    """Try to parse with the configured model server. Returns None if unavailable."""
    url = os.getenv("NEMORON_URL") or os.getenv("MODEL_URL")
    key = os.getenv("NGC_API_KEY", "placeholder")
    model = os.getenv("MODEL_NAME", "local-model")
    if not url:
        return None
    try:
        import httpx
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": _LLM_PROMPT.format(prompt=text)}],
            "temperature": 0,
            "max_tokens": 120,
        }
        r = httpx.post(
            f"{url}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {key}"},
            timeout=8.0,
        )
        r.raise_for_status()
        raw = r.json()["choices"][0]["message"]["content"].strip()
        # Strip markdown fences if present
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
        # Validate keys exist
        assert all(k in data for k in ("building_type","style","floors","size"))
        return data
    except Exception:
        return None


# ── Main parser ────────────────────────────────────────────────────────────────
def parse_prompt(text: str) -> dict:
    t = text.lower().strip()

    # ── 1. Concept map — longest match wins ──────────────────────────────────
    building_type = None
    style         = None
    matched_concept = False

    sorted_concepts = sorted(CONCEPT_MAP.keys(), key=len, reverse=True)
    for concept in sorted_concepts:
        if concept in t:
            building_type, style = CONCEPT_MAP[concept]
            matched_concept = True
            break

    # ── 2. Style keyword overrides (if user adds an explicit style adjective) ─
    style_keywords = [
        (['gothic','cathedral','medieval','pointed arch','lancet','gargoyle'],       'gothic'),
        (['baroque','ornate','palatial','rococo','gilded','renaissance'],             'baroque'),
        (['art deco','deco','stepped geometric','gold trim','zigzag'],                'art_deco'),
        (['neoclassical','neo-classical','greek revival','roman column','corinthian'],'neoclassical'),
        (['industrial','exposed steel','exposed brick','factory loft'],               'industrial'),
        (['contemporary','minimalist','minimal','scandinavian','zen','sleek white'],  'contemporary'),
        (['glass curtain','curtain wall','all glass','floor to ceiling glass'],       'modern_glass_tower'),
        (['brutalist','raw concrete','concrete brutalism'],                           'brutalist_concrete'),
    ]
    for keywords, candidate_style in style_keywords:
        if any(kw in t for kw in keywords):
            style = candidate_style
            break

    # ── 3. Building type keywords (if not caught by concept map) ─────────────
    if not building_type:
        if any(w in t for w in ['skyscraper','high-rise','highrise','high rise',
                                 'tower block','tall building','condo tower']):
            building_type = 'skyscraper'
        elif any(w in t for w in ['house','home','cottage','bungalow','villa',
                                   'single family','townhouse','cabin','hut']):
            building_type = 'house'
        else:
            building_type = 'suburban_building'

    # ── 4. LLM fallback for anything still unresolved ────────────────────────
    if not matched_concept and style is None:
        llm_result = _llm_parse(text)
        if llm_result:
            return {
                'building_type': llm_result.get('building_type', building_type),
                'style':         llm_result.get('style',         'modern_glass_tower'),
                'floors':        int(llm_result.get('floors',    20)),
                'size':          llm_result.get('size',          'medium'),
            }

    # ── 5. Style default if nothing matched ───────────────────────────────────
    if not style:
        style = {
            'skyscraper':        'modern_glass_tower',
            'house':             'traditional_brick',
            'suburban_building': 'retail_complex',
        }[building_type]

    # ── Floors ────────────────────────────────────────────────────────────────
    floor_match = re.search(r'(\d+)\s*(?:floor|floors|storey|storeys|story|stories|fl\b)', t)
    if floor_match:
        floors = int(floor_match.group(1))
    else:
        nums = [int(n) for n in re.findall(r'\b(\d+)\b', t) if 1 <= int(n) <= 100]
        floors = nums[0] if nums else {'skyscraper':30,'house':1,'suburban_building':6}[building_type]

    limits = {'skyscraper':(5,100), 'house':(1,3), 'suburban_building':(2,15)}
    lo, hi = limits[building_type]
    floors = max(lo, min(hi, floors))

    # ── Size ──────────────────────────────────────────────────────────────────
    if any(w in t for w in ['small','tiny','little','compact','narrow','slim','miniature']):
        size = 'small'
    elif any(w in t for w in ['large','big','huge','massive','wide','sprawling','giant','grand','great']):
        size = 'large'
    else:
        size = 'medium'

    return {'building_type': building_type, 'style': style, 'floors': floors, 'size': size}

app = FastAPI(title="UrbanForge — Building Image Agent Test")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ── Direct generate endpoint (no LLM — uses renderer directly) ────────────────
class GenerateRequest(BaseModel):
    building_type: str = "skyscraper"
    style: str         = "modern_glass_tower"
    floors: int        = 24
    size: str          = "medium"


@app.post("/generate/building-image")
def generate(req: GenerateRequest):
    floors = max(1, min(req.floors, 100))
    png, renderer = generate_ai_image(
        style         = req.style,
        building_type = req.building_type,
        floors        = floors,
        size          = req.size,
    )
    if png is None:
        return JSONResponse({"error": "All image renderers failed — check API keys in .env"}, status_code=503)

    b64 = base64.b64encode(png).decode()
    return {
        "image_b64":  b64,
        "renderer":   renderer,
        "metadata": {
            "building_type":  req.building_type,
            "style":          req.style,
            "floors":         floors,
            "size":           req.size,
            "canvas_px":      "800×1000",
            "background_hex": "#D3D3D3",
        },
    }


# ── Natural language prompt endpoint ─────────────────────────────────────────
class PromptRequest(BaseModel):
    prompt: str


@app.post("/generate/from-prompt")
def generate_from_prompt(req: PromptRequest):
    params = parse_prompt(req.prompt)

    # Try AI generation first, fall back to PIL
    png, renderer = generate_ai_image(
        style            = params["style"],
        building_type    = params["building_type"],
        floors           = params["floors"],
        size             = params["size"],
        user_description = req.prompt,
    )
    if png is None:
        return JSONResponse({"error": "All image renderers failed — check API keys in .env"}, status_code=503)

    b64 = base64.b64encode(png).decode()

    return {
        "image_b64":        b64,
        "extracted_params": params,
        "renderer":         renderer,
        "metadata": {
            "building_type":  params["building_type"],
            "style":          params["style"],
            "floors":         params["floors"],
            "size":           params["size"],
            "canvas_px":      "800×1000",
            "background_hex": "#E0E0E0",
            "renderer":       renderer,
        },
    }


@app.get("/health")
def health():
    return {"status": "ok", "renderer": "building_renderer.py", "agent": "prompt-parser + direct"}


# ── Test UI ───────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def ui():
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>UrbanForge — Building Agent</title>
<style>
  :root{--bg:#050d1a;--surface:#0d1b2e;--surface2:#162039;--border:#1e3a5f;
        --green:#76b900;--blue:#00a3ff;--text:#dde8f2;--muted:#6a85a0;}
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--text);font-family:system-ui,sans-serif;
       font-size:13px;display:flex;flex-direction:column;align-items:center;
       padding:32px 16px;gap:20px;min-height:100vh}
  h1{font-size:22px;font-weight:700}  h1 span{color:var(--green)}
  .sub{color:var(--muted);font-size:12px;margin-top:4px}

  /* ── Prompt bar ── */
  .prompt-bar{width:100%;max-width:900px;display:flex;gap:10px;align-items:stretch}
  #prompt-input{flex:1;background:var(--surface);border:1px solid var(--border);
    color:var(--text);border-radius:8px;padding:14px 16px;font-size:14px;
    outline:none;transition:border .15s}
  #prompt-input:focus{border-color:var(--green)}
  #prompt-input::placeholder{color:var(--muted)}
  .go-btn{background:var(--green);color:#000;border:none;border-radius:8px;
          padding:0 24px;font-size:14px;font-weight:700;cursor:pointer;white-space:nowrap}
  .go-btn:hover{opacity:.85}  .go-btn:disabled{opacity:.4;cursor:default}

  /* example chips */
  .chips{display:flex;flex-wrap:wrap;gap:6px;width:100%;max-width:900px}
  .chip{background:var(--surface2);border:1px solid var(--border);border-radius:20px;
        padding:4px 12px;font-size:11px;color:var(--muted);cursor:pointer;transition:all .15s}
  .chip:hover{border-color:var(--green);color:var(--green)}

  /* ── Main layout ── */
  .main{display:grid;grid-template-columns:1fr 300px;gap:16px;width:100%;max-width:900px}

  /* image panel */
  .img-panel{background:var(--surface);border:1px solid var(--border);
             border-radius:10px;overflow:hidden;display:flex;flex-direction:column}
  .img-header{padding:10px 14px;border-bottom:1px solid var(--border);
              font-size:11px;font-weight:600;display:flex;align-items:center;gap:8px}
  .dot{width:7px;height:7px;border-radius:50%;background:var(--muted)}
  .dot.green{background:var(--green);box-shadow:0 0 6px var(--green)}
  .dot.amber{background:#f5a623;box-shadow:0 0 6px #f5a623}
  .img-wrap{background:#e0e0e0;min-height:400px;display:flex;
            align-items:center;justify-content:center;position:relative}
  #preview-img{max-width:100%;max-height:500px;display:none}
  .img-placeholder{color:#999;font-size:13px;text-align:center;padding:20px;line-height:1.6}

  /* right panel */
  .right{display:flex;flex-direction:column;gap:12px}
  .info-card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px}
  .card-title{font-size:10px;text-transform:uppercase;letter-spacing:.07em;
              color:var(--muted);font-weight:600;margin-bottom:12px}

  /* extracted params */
  .param-row{display:flex;justify-content:space-between;align-items:center;
             padding:5px 0;border-bottom:1px solid var(--border)}
  .param-row:last-child{border:none}
  .param-key{font-size:11px;color:var(--muted)}
  .param-val{font-size:12px;color:var(--green);font-weight:600}

  /* pixel metadata */
  .meta-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:4px}
  .meta-item{display:flex;flex-direction:column;gap:2px}
  .meta-k{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
  .meta-v{font-size:11px;color:var(--text);font-weight:500}

  /* action btns */
  .dl-btn{background:none;border:1px solid var(--border);color:var(--muted);
          border-radius:6px;padding:8px;font-size:12px;cursor:pointer;width:100%;
          display:none;transition:all .15s}
  .dl-btn:hover{border-color:var(--green);color:var(--green)}
  .compare-btn{background:var(--surface2);border:1px solid var(--border);color:var(--text);
               border-radius:6px;padding:8px;font-size:12px;cursor:pointer;width:100%}
  .compare-btn:hover{border-color:var(--blue);color:var(--blue)}

  /* compare strip */
  .compare-strip{width:100%;max-width:900px;display:none}
  .compare-strip h3{font-size:12px;color:var(--muted);margin-bottom:10px}
  .compare-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
  .c-card{background:var(--surface);border:1px solid var(--border);border-radius:8px;overflow:hidden}
  .c-card img{width:100%;background:#e0e0e0;display:block}
  .c-label{padding:5px 8px;font-size:10px;color:var(--muted);text-align:center}
</style>
</head>
<body>

<div style="text-align:center">
  <h1>Urban<span>Forge</span> Building Agent</h1>
  <p class="sub">Describe any building — the agent parses it and generates a blueprint instantly</p>
</div>

<!-- Prompt bar -->
<div class="prompt-bar">
  <input id="prompt-input" placeholder="e.g. 40 floor glass skyscraper, large  |  small brick house  |  brutalist concrete office 8 floors"
         onkeydown="if(event.key==='Enter')sendPrompt()">
  <button class="go-btn" id="go-btn" onclick="sendPrompt()">Generate</button>
</div>

<!-- Example chips -->
<div class="chips">
  <div class="chip" onclick="setPrompt(this)">castle</div>
  <div class="chip" onclick="setPrompt(this)">museum</div>
  <div class="chip" onclick="setPrompt(this)">gothic cathedral</div>
  <div class="chip" onclick="setPrompt(this)">palace</div>
  <div class="chip" onclick="setPrompt(this)">prison</div>
  <div class="chip" onclick="setPrompt(this)">warehouse loft</div>
  <div class="chip" onclick="setPrompt(this)">grand hotel 40 floors</div>
  <div class="chip" onclick="setPrompt(this)">courthouse large</div>
  <div class="chip" onclick="setPrompt(this)">art deco tower 35 floors</div>
  <div class="chip" onclick="setPrompt(this)">small cottage</div>
  <div class="chip" onclick="setPrompt(this)">corporate headquarters 60 floors</div>
  <div class="chip" onclick="setPrompt(this)">old school building</div>
</div>

<!-- Main -->
<div class="main">

  <!-- Image -->
  <div class="img-panel">
    <div class="img-header">
      <div class="dot" id="dot"></div>
      <span id="status-text">Waiting for prompt</span>
      <span id="renderer-badge" style="margin-left:auto;font-size:10px;
        background:var(--surface2);border:1px solid var(--border);
        border-radius:4px;padding:2px 8px;color:var(--muted);display:none"></span>
    </div>
    <div class="img-wrap">
      <div class="img-placeholder" id="placeholder">
        Type a building description above<br>and hit Generate
      </div>
      <img id="preview-img" alt="Generated building">
    </div>
  </div>

  <!-- Right panel -->
  <div class="right">

    <div class="info-card">
      <div class="card-title">Extracted Parameters</div>
      <div class="param-row"><div class="param-key">Building Type</div><div class="param-val" id="p-type">—</div></div>
      <div class="param-row"><div class="param-key">Style</div><div class="param-val" id="p-style">—</div></div>
      <div class="param-row"><div class="param-key">Floors</div><div class="param-val" id="p-floors">—</div></div>
      <div class="param-row"><div class="param-key">Size</div><div class="param-val" id="p-size">—</div></div>
    </div>

    <div class="info-card" id="meta-card" style="display:none">
      <div class="card-title">Pixel Metadata (3D Pipeline)</div>
      <div class="meta-grid">
        <div class="meta-item"><div class="meta-k">Canvas</div><div class="meta-v" id="m-canvas"></div></div>
        <div class="meta-item"><div class="meta-k">Background</div><div class="meta-v" id="m-bg"></div></div>
        <div class="meta-item"><div class="meta-k">Width</div><div class="meta-v" id="m-w"></div></div>
        <div class="meta-item"><div class="meta-k">Height</div><div class="meta-v" id="m-h"></div></div>
        <div class="meta-item"><div class="meta-k">Floor px</div><div class="meta-v" id="m-fh"></div></div>
        <div class="meta-item"><div class="meta-k">Ground Y</div><div class="meta-v" id="m-gy"></div></div>
      </div>
    </div>

    <button class="dl-btn" id="dl-btn" onclick="download()">⬇ Save PNG</button>
    <button class="compare-btn" onclick="runCompare()">Compare all 4 styles →</button>

  </div>
</div>

<!-- Compare strip -->
<div class="compare-strip" id="compare-strip">
  <h3 id="compare-label">Style comparison</h3>
  <div class="compare-grid" id="compare-grid"></div>
</div>

<script>
let lastB64 = null, lastParams = null;

function setPrompt(el) {
  document.getElementById('prompt-input').value = el.textContent;
  sendPrompt();
}

async function sendPrompt() {
  const prompt = document.getElementById('prompt-input').value.trim();
  if (!prompt) return;

  const btn = document.getElementById('go-btn');
  const dot = document.getElementById('dot');
  const st  = document.getElementById('status-text');
  btn.disabled = true;
  dot.className = 'dot amber';
  st.textContent = 'Parsing prompt… generating image (may take 5–15s)';

  try {
    const res  = await fetch('/generate/from-prompt', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({prompt}),
    });
    const data = await res.json();

    if (!res.ok || data.error) {
      st.textContent = data.error || 'Renderer error — check server logs';
      dot.className = 'dot';
      btn.disabled = false;
      return;
    }

    lastB64    = data.image_b64;
    lastParams = data.extracted_params;

    // Renderer badge
    const badge = document.getElementById('renderer-badge');
    badge.textContent = data.renderer || '';
    badge.style.display = 'inline-block';
    badge.style.borderColor = 'var(--green)';
    badge.style.color = 'var(--green)';

    // Show image
    const img = document.getElementById('preview-img');
    img.src = 'data:image/png;base64,' + data.image_b64;
    img.style.display = 'block';
    document.getElementById('placeholder').style.display = 'none';
    document.getElementById('dl-btn').style.display = 'block';

    // Extracted params
    const p = data.extracted_params;
    document.getElementById('p-type').textContent   = p.building_type.replace(/_/g,' ');
    document.getElementById('p-style').textContent  = p.style.replace(/_/g,' ');
    document.getElementById('p-floors').textContent = p.floors + ' floors';
    document.getElementById('p-size').textContent   = p.size;

    // Metadata
    const m = data.metadata;
    document.getElementById('meta-card').style.display = 'block';
    document.getElementById('m-canvas').textContent = m.canvas_px || '800×1000';
    document.getElementById('m-bg').textContent     = m.background_hex || '#D3D3D3';
    document.getElementById('m-w').textContent      = (m.tower_width_px  || '—') + 'px';
    document.getElementById('m-h').textContent      = (m.tower_height_px || '—') + 'px';
    document.getElementById('m-fh').textContent     = (m.floor_height_px || '—') + 'px';
    document.getElementById('m-gy').textContent     = (m.ground_y_px     || '—') + 'px';

    dot.className = 'dot green';
    st.textContent = `${p.building_type.replace(/_/g,' ')} · ${p.style.replace(/_/g,' ')} · ${p.floors}fl`;
  } catch(e) {
    st.textContent = 'Error: ' + e.message;
    dot.className = 'dot';
  }
  btn.disabled = false;
}

async function runCompare() {
  if (!lastParams) return;
  const styles = ['modern_glass_tower','traditional_brick','brutalist_concrete','retail_complex'];
  const labels = ['Modern Glass','Traditional Brick','Brutalist Concrete','Retail Complex'];
  const strip  = document.getElementById('compare-strip');
  const grid   = document.getElementById('compare-grid');
  strip.style.display = 'block';
  grid.innerHTML = '<div style="color:var(--muted);font-size:12px;padding:8px">Generating 4 styles…</div>';

  document.getElementById('compare-label').textContent =
    `4 styles — ${lastParams.building_type.replace(/_/g,' ')} · ${lastParams.floors} floors · ${lastParams.size}`;

  const results = await Promise.all(styles.map(style =>
    fetch('/generate/building-image', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({...lastParams, style}),
    }).then(r => r.json()).then(d => ({style, label: labels[styles.indexOf(style)], b64: d.image_b64}))
  ));

  grid.innerHTML = '';
  results.forEach(({label, b64}) => {
    const card = document.createElement('div');
    card.className = 'c-card';
    card.innerHTML = `<img src="data:image/png;base64,${b64}"><div class="c-label">${label}</div>`;
    grid.appendChild(card);
  });
}

function download() {
  if (!lastB64 || !lastParams) return;
  const a = document.createElement('a');
  a.href = 'data:image/png;base64,' + lastB64;
  a.download = `${lastParams.building_type}_${lastParams.style}_${lastParams.floors}fl.png`;
  a.click();
}
</script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    print("\n  UrbanForge Building Agent — test server")
    print("  http://localhost:8080\n")
    uvicorn.run(app, host="0.0.0.0", port=8080)
