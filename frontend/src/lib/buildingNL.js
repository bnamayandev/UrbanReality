const MATERIAL_LABELS = {
  glass:       'concrete and glass curtain wall',
  mass_timber: 'mass timber',
  steel:       'steel frame',
  concrete:    'exposed concrete',
  brick:       'brick',
}

const TYPE_LABELS = {
  'residential (high-rise)': 'residential high-rise tower',
  'residential (mid-rise)':  'residential mid-rise building',
  'mixed-use':               'mixed-use development',
  'commercial office':       'commercial office tower',
  'retail / podium':         'retail podium',
  'industrial':              'industrial building',
}

export function describeBuilding(spec) {
  const type     = TYPE_LABELS[spec.type] || spec.type
  const material = MATERIAL_LABELS[spec.material] || spec.material || 'glass'
  const floors   = spec.floors || 1
  const fp       = Number(spec.footprint_m2 || 0).toLocaleString()
  const height   = Math.round(floors * 3.5)
  const units    = spec.units_per_floor ? floors * spec.units_per_floor : null

  let desc = `A ${floors}-floor ${type} with a ${material} facade, ${fp} m² footprint, approximately ${height} metres tall`
  if (units) desc += `, ${units.toLocaleString()} total units`
  if (spec.name) desc = `"${spec.name}" — ` + desc
  return desc + '.'
}

export function diffBuildings(prev, next) {
  const FIELD_LABELS = {
    floors:          { label: 'floors',          fmt: v => `${v} floors`,             height: v => `~${Math.round(v * 3.5)}m tall` },
    footprint_m2:    { label: 'footprint',        fmt: v => `${Number(v).toLocaleString()} m²` },
    type:            { label: 'building type',    fmt: v => TYPE_LABELS[v] || v },
    material:        { label: 'facade material',  fmt: v => MATERIAL_LABELS[v] || v },
    units_per_floor: { label: 'units per floor',  fmt: v => `${v} units/floor` },
  }

  const fields = []
  for (const [field] of Object.entries(FIELD_LABELS)) {
    const from = prev[field], to = next[field]
    if (from === to || (from == null && to == null)) continue
    const entry = { field, from, to }
    if (typeof from === 'number' && typeof to === 'number') {
      entry.delta     = to - from
      entry.deltaText = entry.delta > 0 ? `+${entry.delta}` : `${entry.delta}`
    }
    fields.push(entry)
  }

  if (fields.length === 0) {
    return { fields: [], naturalLanguage: 'No changes detected.' }
  }

  const parts = fields.map(f => {
    const cfg = FIELD_LABELS[f.field]
    if (f.field === 'floors') {
      const dir    = f.delta > 0 ? 'Increased' : 'Decreased'
      const height = Math.round((next.floors || 1) * 3.5)
      return `${dir} height by ${Math.abs(f.delta)} floor${Math.abs(f.delta) > 1 ? 's' : ''} — now ${f.to} floors, ~${height}m tall`
    }
    if (f.field === 'footprint_m2') {
      return `Changed footprint from ${Number(f.from).toLocaleString()} m² to ${Number(f.to).toLocaleString()} m²`
    }
    return `Changed ${cfg.label} from ${cfg.fmt(f.from)} to ${cfg.fmt(f.to)}`
  })

  const summary = `Modified ${fields.length} propert${fields.length === 1 ? 'y' : 'ies'}: ${parts.join('; ')}.`

  return { fields, naturalLanguage: summary }
}

export function buildAgentPrompt(payload, previousAgentPrompt) {
  const base = `You are an architectural visualization agent. Generate a hyper-realistic architectural render of a building on a completely white background. No surroundings, no sky, no ground — just the building. The building is: ${describeBuilding(payload.spec)}`

  if (!payload.isUpdate) {
    // If the user provided a free-form description, use it directly.
    // The backend _build_prompt() will wrap it in the standard preamble.
    if (payload.spec.renderPrompt && payload.spec.renderPrompt.trim()) {
      return payload.spec.renderPrompt.trim()
    }
    // ── FIRST REQUEST — auto-generated from spec ───────────────────────────
    return base
  }

  const prev = previousAgentPrompt || base
  return (
    `${prev}\n\n` +
    `Apply the following modifications to the design: ${payload.diff.naturalLanguage} ` +
    `Updated full specification: ${describeBuilding(payload.spec)}`
  )
}
