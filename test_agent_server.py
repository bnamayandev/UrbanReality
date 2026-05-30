"""
Standalone test server for the building image agent.
No database required — only tests the generate endpoint.

Run:  python3 test_agent_server.py
Open: http://localhost:8080
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional

from rendering.building_renderer import render_building
import base64

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
    png = render_building(req.building_type, req.style, floors, req.size)
    b64 = base64.b64encode(png).decode()

    floor_heights = {"skyscraper": 14, "house": 80, "suburban_building": 18}
    size_mults    = {"small": 0.72, "medium": 1.0, "large": 1.32}
    base_widths   = {"skyscraper": 190, "house": 280, "suburban_building": 360}
    fh = floor_heights.get(req.building_type, 14)
    sm = size_mults.get(req.size, 1.0)
    bw = base_widths.get(req.building_type, 190)

    return {
        "image_b64":  b64,
        "image_path": f"(in-memory — {req.building_type}_{req.style}_{floors}fl_{req.size}.png)",
        "metadata": {
            "building_type":    req.building_type,
            "style":            req.style,
            "floors":           floors,
            "size":             req.size,
            "canvas_px":        "800×1000",
            "background_hex":   "#E0E0E0",
            "tower_width_px":   int(bw * sm),
            "tower_height_px":  floors * fh,
            "floor_height_px":  fh,
            "ground_y_px":      870,
            "consistency_rule": "width fixed per size; height = floors × floor_height_px",
        },
    }


@app.get("/health")
def health():
    return {"status": "ok", "renderer": "building_renderer.py", "agent": "direct (no LLM)"}


# ── Test UI ───────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def ui():
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>UrbanForge — Building Image Agent</title>
<style>
  :root {
    --bg:#050d1a;--surface:#0d1b2e;--surface2:#162039;--border:#1e3a5f;
    --green:#76b900;--blue:#00a3ff;--text:#dde8f2;--muted:#6a85a0;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--text);font-family:system-ui,sans-serif;
       font-size:13px;display:flex;flex-direction:column;align-items:center;
       padding:32px 16px;gap:24px;min-height:100vh}
  h1{font-size:22px;font-weight:700}
  h1 span{color:var(--green)}
  .sub{color:var(--muted);font-size:12px;margin-top:4px}

  .shell{display:grid;grid-template-columns:260px 1fr;gap:20px;width:100%;max-width:1000px}

  /* Controls */
  .controls{background:var(--surface);border:1px solid var(--border);
             border-radius:10px;padding:20px;display:flex;flex-direction:column;gap:14px}
  .ctrl-title{font-size:11px;font-weight:600;text-transform:uppercase;
              letter-spacing:.07em;color:var(--muted);margin-bottom:2px}
  .form-group{display:flex;flex-direction:column;gap:4px}
  .form-label{font-size:11px;color:var(--muted)}
  select,input[type=range]{background:var(--surface2);border:1px solid var(--border);
    color:var(--text);border-radius:5px;padding:6px 10px;font-size:12px;width:100%}
  input[type=range]{padding:0;accent-color:var(--green)}
  .range-val{font-size:12px;color:var(--green);font-weight:600;text-align:right}
  .btn{background:var(--green);color:#000;border:none;border-radius:6px;
       padding:9px;font-size:13px;font-weight:700;cursor:pointer;width:100%;margin-top:4px}
  .btn:hover{opacity:.85}
  .btn:disabled{opacity:.4;cursor:default}

  /* Output */
  .output{background:var(--surface);border:1px solid var(--border);border-radius:10px;
          overflow:hidden;display:flex;flex-direction:column}
  .out-header{padding:12px 16px;border-bottom:1px solid var(--border);font-size:12px;
              font-weight:600;display:flex;align-items:center;justify-content:space-between}
  .status-dot{width:7px;height:7px;border-radius:50%;background:var(--muted);display:inline-block;margin-right:6px}
  .status-dot.green{background:var(--green);box-shadow:0 0 6px var(--green)}
  .status-dot.amber{background:#f5a623;box-shadow:0 0 6px #f5a623}

  .img-wrap{background:#e0e0e0;display:flex;align-items:center;justify-content:center;
            min-height:420px;position:relative}
  #preview-img{max-width:100%;max-height:480px;display:none}
  .placeholder{color:#999;font-size:13px;text-align:center;padding:20px}

  /* Metadata */
  .meta-panel{padding:14px 16px;border-top:1px solid var(--border);
              display:grid;grid-template-columns:1fr 1fr;gap:6px}
  .meta-row{display:flex;flex-direction:column;gap:2px}
  .meta-key{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
  .meta-val{font-size:12px;color:var(--green);font-weight:600}

  /* Batch compare row */
  .compare-section{width:100%;max-width:1000px}
  .compare-title{font-size:13px;font-weight:600;color:var(--muted);margin-bottom:12px}
  .compare-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
  .compare-card{background:var(--surface);border:1px solid var(--border);
                border-radius:8px;overflow:hidden;display:flex;flex-direction:column}
  .compare-card img{width:100%;background:#e0e0e0}
  .compare-label{padding:6px 10px;font-size:10px;color:var(--muted);text-align:center}

  .download-btn{background:none;border:1px solid var(--border);color:var(--muted);
                border-radius:5px;padding:5px 12px;font-size:11px;cursor:pointer}
  .download-btn:hover{border-color:var(--green);color:var(--green)}
</style>
</head>
<body>

<div>
  <h1>UrbanForge — <span>Building Image Agent</span></h1>
  <p class="sub">Deterministic 2D elevation renderer · Background locked #E0E0E0 · POST /generate/building-image</p>
</div>

<div class="shell">

  <!-- Controls -->
  <div class="controls">
    <div class="ctrl-title">Agent Parameters</div>

    <div class="form-group">
      <div class="form-label">Building Type</div>
      <select id="type">
        <option value="skyscraper">Skyscraper</option>
        <option value="house">House</option>
        <option value="suburban_building">Suburban Building</option>
      </select>
    </div>

    <div class="form-group">
      <div class="form-label">Architectural Style</div>
      <select id="style">
        <option value="modern_glass_tower">Modern Glass Tower</option>
        <option value="traditional_brick">Traditional Brick</option>
        <option value="brutalist_concrete">Brutalist Concrete</option>
        <option value="retail_complex">Retail Complex</option>
      </select>
    </div>

    <div class="form-group">
      <div class="form-label">Floors <span class="range-val" id="floor-val">24</span></div>
      <input type="range" id="floors" min="1" max="80" value="24"
             oninput="document.getElementById('floor-val').textContent=this.value">
    </div>

    <div class="form-group">
      <div class="form-label">Size</div>
      <select id="size">
        <option value="small">Small</option>
        <option value="medium" selected>Medium</option>
        <option value="large">Large</option>
      </select>
    </div>

    <button class="btn" id="gen-btn" onclick="generate()">⚡ Generate Blueprint</button>

    <button class="btn" id="compare-btn"
            style="background:var(--blue);margin-top:0"
            onclick="runBatch()">⬛ Compare All Styles</button>

    <button class="download-btn" id="dl-btn" style="display:none" onclick="download()">
      ⬇ Save PNG
    </button>
  </div>

  <!-- Output -->
  <div class="output">
    <div class="out-header">
      <div><span class="status-dot" id="sdot"></span>Agent Output</div>
      <div id="out-label" style="color:var(--muted);font-size:11px">idle</div>
    </div>
    <div class="img-wrap">
      <div class="placeholder" id="placeholder">
        Configure parameters and click Generate Blueprint
      </div>
      <img id="preview-img" alt="Generated building elevation">
    </div>
    <div class="meta-panel" id="meta-panel" style="display:none">
      <div class="meta-row"><div class="meta-key">Canvas</div><div class="meta-val" id="m-canvas"></div></div>
      <div class="meta-row"><div class="meta-key">Background</div><div class="meta-val" id="m-bg"></div></div>
      <div class="meta-row"><div class="meta-key">Tower Width</div><div class="meta-val" id="m-w"></div></div>
      <div class="meta-row"><div class="meta-key">Tower Height</div><div class="meta-val" id="m-h"></div></div>
      <div class="meta-row"><div class="meta-key">Floor Height</div><div class="meta-val" id="m-fh"></div></div>
      <div class="meta-row"><div class="meta-key">Ground Y</div><div class="meta-val" id="m-gy"></div></div>
    </div>
  </div>

</div>

<!-- Batch compare -->
<div class="compare-section">
  <div class="compare-title" id="compare-title" style="display:none">Style comparison — same floors, same type, 4 styles side by side</div>
  <div class="compare-grid" id="compare-grid"></div>
</div>

<script>
let lastB64 = null;

async function generate() {
  const btn = document.getElementById('gen-btn');
  const dot = document.getElementById('sdot');
  const lbl = document.getElementById('out-label');
  btn.disabled = true;
  dot.className = 'status-dot amber';
  lbl.textContent = 'rendering…';

  const body = {
    building_type: document.getElementById('type').value,
    style:         document.getElementById('style').value,
    floors:        parseInt(document.getElementById('floors').value),
    size:          document.getElementById('size').value,
  };

  try {
    const res  = await fetch('/generate/building-image', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(body),
    });
    const data = await res.json();

    lastB64 = data.image_b64;
    const img = document.getElementById('preview-img');
    img.src = 'data:image/png;base64,' + data.image_b64;
    img.style.display = 'block';
    document.getElementById('placeholder').style.display = 'none';
    document.getElementById('dl-btn').style.display = 'inline-block';

    // Metadata
    const m = data.metadata;
    document.getElementById('meta-panel').style.display = 'grid';
    document.getElementById('m-canvas').textContent = m.canvas_px;
    document.getElementById('m-bg').textContent     = m.background_hex;
    document.getElementById('m-w').textContent      = m.tower_width_px + 'px';
    document.getElementById('m-h').textContent      = m.tower_height_px + 'px';
    document.getElementById('m-fh').textContent     = m.floor_height_px + 'px / floor';
    document.getElementById('m-gy').textContent     = m.ground_y_px + 'px (fixed)';

    dot.className = 'status-dot green';
    lbl.textContent = `${body.building_type} · ${body.style} · ${body.floors}fl · ${body.size}`;
  } catch(e) {
    lbl.textContent = 'error: ' + e.message;
    dot.className = 'status-dot';
  }
  btn.disabled = false;
}

async function runBatch() {
  const floors = parseInt(document.getElementById('floors').value);
  const btype  = document.getElementById('type').value;
  const size   = document.getElementById('size').value;
  const styles = ['modern_glass_tower','traditional_brick','brutalist_concrete','retail_complex'];
  const labels = ['Modern Glass Tower','Traditional Brick','Brutalist Concrete','Retail Complex'];

  const grid = document.getElementById('compare-grid');
  grid.innerHTML = '';
  document.getElementById('compare-title').style.display = 'block';

  await Promise.all(styles.map(async (style, i) => {
    const res  = await fetch('/generate/building-image', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({building_type: btype, style, floors, size}),
    });
    const data = await res.json();

    const card = document.createElement('div');
    card.className = 'compare-card';
    card.innerHTML = `
      <img src="data:image/png;base64,${data.image_b64}" alt="${labels[i]}">
      <div class="compare-label">${labels[i]}<br>${floors}fl · ${size}</div>`;
    grid.appendChild(card);
  }));
}

function download() {
  if (!lastB64) return;
  const a = document.createElement('a');
  const t = document.getElementById('type').value;
  const s = document.getElementById('style').value;
  const f = document.getElementById('floors').value;
  a.href = 'data:image/png;base64,' + lastB64;
  a.download = `${t}_${s}_${f}fl.png`;
  a.click();
}

// Auto-generate on load
window.onload = () => generate();
</script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    print("\n  UrbanForge Building Agent — test server")
    print("  http://localhost:8080\n")
    uvicorn.run(app, host="0.0.0.0", port=8080)
