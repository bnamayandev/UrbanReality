# UrbanForge — Frontend Spec
> For Rehan + Ben. Read this top to bottom before writing a line of code.
> Backend is live and tested. API calls in here are real and work right now.

---

## What you're building

Two-panel web app on a dark Toronto 3D map.

**Left panel (always visible):** Interactive Mapbox map of Toronto. 3D buildings. User clicks to place a proposed building.

**Right panel (slides in):** After placing a building — shows the AI impact analysis. 5 scores with descriptions. Chatbot at the bottom.

That's it. Don't add more.

---

## Design direction

**Vibe:** Dark. Data-dense. Like a Bloomberg terminal met a city planning dashboard. Not a SaaS landing page. Not generic AI.

- Background: `#0a0a0f` (near black, slight blue tint)
- Map style: Mapbox dark — `mapbox://styles/mapbox/dark-v11`
- Accent: `#00d4ff` (electric cyan) — use sparingly, only for highlights and active states
- Secondary accent: `#ff6b35` (orange) — for high-impact/warning scores
- Text: `#e8e8e8` primary, `#888` secondary
- Cards/panels: `rgba(255,255,255,0.04)` with `1px solid rgba(255,255,255,0.08)` border
- Font: `Inter` or `DM Sans` — nothing else
- No shadows. No gradients on cards. No rounded corners bigger than 6px.
- Score bars: thin (4px height), not chunky progress bars

**Do not:**
- Use Tailwind's default blue (`#3b82f6`) anywhere
- Use white backgrounds
- Use card shadows (`box-shadow`)
- Use emojis in the UI
- Make it look like a dashboard template

---

## Stack

```bash
npm create vite@latest frontend -- --template react
cd frontend
npm install mapbox-gl react-map-gl @turf/turf lucide-react
```

No UI component libraries (no shadcn, no MUI, no Chakra). Write your own components — they'll look better and be faster.

Set your Mapbox token in `.env`:
```
VITE_MAPBOX_TOKEN=your_token_here
VITE_API_BASE=http://100.93.45.108:8001
```

---

## Component structure

```
src/
├── App.jsx                  # Root — map + panel side by side
├── components/
│   ├── Map.jsx              # Mapbox map, building placement, 3D extrusions
│   ├── BuildingForm.jsx     # Sidebar form: floors, type, material
│   ├── ImpactPanel.jsx      # The 5-score result panel
│   ├── ScoreBar.jsx         # Single score row (label + bar + number)
│   ├── ChatBox.jsx          # Chatbot at bottom of panel
│   └── BuildingMarker.jsx   # Dot/pin on map for placed building
├── hooks/
│   ├── useBuilding.js       # POST /building, store id
│   └── useImpact.js         # GET /building/{id}/impact, poll until ready
├── api.js                   # All fetch calls in one place
└── index.css                # Global styles, CSS variables
```

---

## API calls — copy these exactly

Base URL: `http://100.93.45.108:8001`

### 1. Create a building (when user clicks map + submits form)
```js
const res = await fetch(`${API_BASE}/building`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    name: "My Tower",           // optional
    type: "residential (high-rise)",  // see types below
    floors: 40,
    footprint_m2: 2000,
    lat: 43.6532,
    lng: -79.3832,
    material: "glass",          // optional
    units_per_floor: 10         // optional, default 10
  })
})
const building = await res.json()
// building.id is what you use for everything else
```

**Valid `type` values:**
- `"residential (high-rise)"` — towers 20+ floors
- `"residential (mid-rise)"` — 6–19 floors
- `"mixed-use"` — retail + residential
- `"commercial office"`
- `"retail / podium"`
- `"industrial"`

### 2. Get impact analysis (after creating building)
```js
const res = await fetch(`${API_BASE}/building/${buildingId}/impact`)
const impact = await res.json()
```

**Real response shape** (this is actual data from the live server):
```json
{
  "building_id": 1,
  "environmental": {
    "score": 5,
    "description": "Predicted annual electricity: 1411 MWh (18 kWh/m²)..."
  },
  "traffic": {
    "score": 100,
    "description": "Estimated +3449 daily vehicle trips generated. Peak-hour impact on surrounding intersections: significant."
  },
  "economic": {
    "score": 95,
    "description": "Estimated 1783 person-years of construction employment (StatsCan I-O multiplier)..."
  },
  "infrastructure": {
    "score": 80,
    "description": "Estimated water demand: +88000 L/day. TTC stops nearby will see approximately +120 daily boardings."
  },
  "housing": {
    "score": 40,
    "description": "Adds 400 units to city supply against a 0.7% vacancy rate..."
  }
}
```

Score is 0–100. Higher = bigger impact (not necessarily bad — high economic score is good).

**Note:** First call can take several seconds (qwen3 is thinking, and the model may need to load into VRAM). Second call for the same building is instant (cached). Show a loading state.

### 3. List all buildings (for the public map view)
```js
const res = await fetch(`${API_BASE}/buildings`)
const buildings = await res.json()
// array of building objects
```

### 4. Generate building preview image
```js
const res = await fetch(`${API_BASE}/generate/building-image`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    building_type: "skyscraper",  // skyscraper | house | suburban_building
    style: "modern_glass_tower",  // modern_glass_tower | traditional_brick | brutalist_concrete | retail_complex
    floors: 40,
    size: "medium"               // small | medium | large
  })
})
const { image_b64 } = await res.json()
// Use as: <img src={`data:image/png;base64,${image_b64}`} />
```

### 5. Chat (WebSocket)
```js
const ws = new WebSocket(`ws://100.93.45.108:8001/chat/${sessionId}`)
ws.send(JSON.stringify({
  message: "What's the traffic impact?",
  building_id: 1   // optional — gives the AI building context
}))
ws.onmessage = (e) => {
  const { response } = JSON.parse(e.data)
  // stream the response into the chat UI
}
```

---

## Map setup

```jsx
import Map, { Source, Layer } from 'react-map-gl'

// Toronto center
const TORONTO = { longitude: -79.3832, latitude: 43.6532, zoom: 13 }

// 3D buildings layer (shows existing Toronto buildings)
const buildingsLayer = {
  id: 'add-3d-buildings',
  source: 'composite',
  'source-layer': 'building',
  filter: ['==', 'extrude', 'true'],
  type: 'fill-extrusion',
  minzoom: 14,
  paint: {
    'fill-extrusion-color': '#1a1a2e',
    'fill-extrusion-height': ['get', 'height'],
    'fill-extrusion-base': ['get', 'min_height'],
    'fill-extrusion-opacity': 0.8
  }
}
```

When user clicks the map, capture `event.lngLat` and show the building form.

When a building is placed, add a `fill-extrusion` for it in a highlighted color (`#00d4ff` at 0.6 opacity), height = `floors * 3.5` meters.

---

## Scoring — how to display

Score 0–30: `#4ade80` (green, low impact)
Score 31–60: `#facc15` (yellow, moderate)
Score 61–85: `#fb923c` (orange, significant)
Score 86–100: `#f87171` (red, high)

The 5 dimensions:
- Environmental — leaf icon
- Traffic — car icon  
- Economic — trending-up icon
- Infrastructure — building-2 icon
- Housing — home icon

Use `lucide-react` for icons.

---

## Loading state

The LLM can take several seconds. Show something real while waiting — not a spinner:

```
Analyzing 500m radius...
Running traffic model...
Consulting qwen3...
```

Cycle through these with a 3s interval. Makes the wait feel purposeful.

---

## What NOT to build (scope)

- No login/auth
- No user accounts
- No saving/sharing links
- No mobile layout (desktop only — this is a demo)
- No animations beyond simple CSS transitions
- No dark/light toggle

---

## Quick start checklist

- [ ] `npm create vite@latest frontend -- --template react`
- [ ] Install deps (see Stack above)
- [ ] Create `.env` with Mapbox token and API base
- [ ] `Map.jsx` — dark Mapbox map, Toronto center, click to place pin
- [ ] `BuildingForm.jsx` — floors slider, type dropdown, submit button
- [ ] `POST /building` on submit → store `building.id`
- [ ] `GET /building/{id}/impact` → show loading state → render scores
- [ ] `ImpactPanel.jsx` — 5 `ScoreBar` components + descriptions
- [ ] `GET /buildings` on load → show all existing buildings on map
- [ ] `ChatBox.jsx` — WebSocket chat at bottom of panel

Hit those 9 things and you have a demo.
