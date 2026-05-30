// Use Vite proxy (/api → backend) in dev to avoid CORS.
// In prod (deployed or DGX Spark), VITE_API_BASE points directly to the server.
const API_BASE = import.meta.env.VITE_API_BASE || '/api'
const WS_BASE  = API_BASE.startsWith('/')
  ? `ws://${window.location.host}/api`
  : API_BASE.replace(/^http/, 'ws')

// ── Buildings ──────────────────────────────────────────────────────────────

export async function createBuilding(data) {
  const res = await fetch(`${API_BASE}/building`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(`Failed to create building: ${res.status}`)
  return res.json()
}

export async function getBuildings() {
  const res = await fetch(`${API_BASE}/buildings`)
  if (!res.ok) throw new Error(`Failed to fetch buildings: ${res.status}`)
  return res.json()
}

export async function getImpact(buildingId) {
  const res = await fetch(`${API_BASE}/building/${buildingId}/impact`)
  if (!res.ok) throw new Error(`Failed to fetch impact: ${res.status}`)
  return res.json()
}

// ── Image generation ────────────────────────────────────────────────────────
// Placeholder: teammates will connect ML image generation here
// Pass building params → returns base64 PNG

export async function generateBuildingImage({ buildingType, style, floors, size }) {
  const res = await fetch(`${API_BASE}/generate/building-image`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      building_type: buildingType,
      style,
      floors,
      size,
    }),
  })
  if (!res.ok) throw new Error(`Image generation failed: ${res.status}`)
  return res.json()  // { image_b64, metadata }
}

// ── Health ──────────────────────────────────────────────────────────────────

export async function getHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`)
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
}

// ── WebSocket chat factory ──────────────────────────────────────────────────
// Returns a WebSocket connected to the chat endpoint.
// Caller is responsible for ws.onmessage, ws.onclose, ws.onerror.

export function createChatSocket(sessionId) {
  return new WebSocket(`${WS_BASE}/chat/${sessionId}`)
}

// ── Type helpers ────────────────────────────────────────────────────────────

export const BUILDING_TYPES = [
  { value: 'residential (high-rise)', label: 'Residential — High-rise (20+ floors)' },
  { value: 'residential (mid-rise)',  label: 'Residential — Mid-rise (6–19 floors)' },
  { value: 'mixed-use',              label: 'Mixed-Use (retail + residential)' },
  { value: 'commercial office',      label: 'Commercial Office' },
  { value: 'retail / podium',        label: 'Retail / Podium' },
  { value: 'industrial',             label: 'Industrial' },
]

export const MATERIALS = [
  { value: 'glass',        label: 'Concrete & Glass' },
  { value: 'mass_timber',  label: 'Mass Timber' },
  { value: 'steel',        label: 'Steel Frame' },
  { value: 'concrete',     label: 'Concrete' },
  { value: 'brick',        label: 'Brick' },
]

// Maps building type → image generation params
// TODO: teammates can refine these mappings when connecting ML
export function buildingTypeToImageParams(type, floors) {
  const floorCount = Math.min(floors, 100)
  if (type.includes('high-rise') || type.includes('commercial')) {
    return { buildingType: 'skyscraper', style: 'modern_glass_tower', floors: floorCount, size: floors > 40 ? 'large' : 'medium' }
  }
  if (type.includes('mid-rise') || type.includes('mixed')) {
    return { buildingType: 'suburban_building', style: 'brutalist_concrete', floors: Math.min(floorCount, 15), size: 'medium' }
  }
  if (type.includes('retail')) {
    return { buildingType: 'suburban_building', style: 'retail_complex', floors: Math.min(floorCount, 10), size: 'large' }
  }
  if (type.includes('industrial')) {
    return { buildingType: 'suburban_building', style: 'brutalist_concrete', floors: Math.min(floorCount, 5), size: 'large' }
  }
  return { buildingType: 'skyscraper', style: 'traditional_brick', floors: floorCount, size: 'medium' }
}
