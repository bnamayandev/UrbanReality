import { useState } from 'react'
import { Zap, MapPin, RotateCcw } from 'lucide-react'
import { BUILDING_TYPES, MATERIALS } from '../api'

const DEFAULT_FORM = {
  type:           'residential (high-rise)',
  material:       'glass',
  floors:         24,
  footprint_m2:   2000,
  units_per_floor: 10,
  name:           '',
}

export function BuildingForm({ coord, onSubmit, onReset, loading }) {
  const [form, setForm] = useState(DEFAULT_FORM)

  const set = (key, val) => setForm(f => ({ ...f, [key]: val }))

  const handleSubmit = () => {
    if (!coord) return
    onSubmit({
      ...form,
      lat: coord.lat,
      lng: coord.lng,
      floors:          Number(form.floors),
      footprint_m2:    Number(form.footprint_m2),
      units_per_floor: Number(form.units_per_floor),
    })
  }

  const hasCoord = !!coord

  return (
    <div style={{
      position: 'absolute',
      top: 60,
      left: 16,
      width: 'var(--form-w)',
      background: 'var(--bg-2)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius)',
      overflow: 'hidden',
      zIndex: 10,
    }}>
      {/* Header */}
      <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <Zap size={14} color="var(--cyan)" />
        <span style={{ fontWeight: 600, fontSize: '13px' }}>Place a Building</span>
        {onReset && (
          <button className="btn btn-ghost" onClick={onReset}
            style={{ marginLeft: 'auto', padding: '4px 8px', fontSize: '11px', gap: '4px' }}>
            <RotateCcw size={10} /> Reset
          </button>
        )}
      </div>

      {/* Coordinate indicator */}
      <div style={{
        padding: '8px 14px',
        background: hasCoord ? 'rgba(0,212,255,0.06)' : 'var(--surface)',
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: '6px',
      }}>
        <MapPin size={12} color={hasCoord ? 'var(--cyan)' : 'var(--text-3)'} />
        {hasCoord ? (
          <span className="mono" style={{ fontSize: '11px', color: 'var(--cyan)' }}>
            {coord.lat.toFixed(5)}, {coord.lng.toFixed(5)}
          </span>
        ) : (
          <span style={{ fontSize: '11px', color: 'var(--text-3)' }}>Click the map to place a building</span>
        )}
      </div>

      {/* Form body */}
      <div style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: '12px' }}>

        {/* Name (optional) */}
        <div>
          <div className="label" style={{ marginBottom: '5px' }}>Project Name <span style={{ color: 'var(--text-3)' }}>optional</span></div>
          <input type="text" placeholder="e.g. King & Spadina Tower"
            value={form.name} onChange={e => set('name', e.target.value)} />
        </div>

        {/* Building type */}
        <div>
          <div className="label" style={{ marginBottom: '5px' }}>Building Type</div>
          <select value={form.type} onChange={e => set('type', e.target.value)}>
            {BUILDING_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </div>

        {/* Material */}
        <div>
          <div className="label" style={{ marginBottom: '5px' }}>Primary Material</div>
          <select value={form.material} onChange={e => set('material', e.target.value)}>
            {MATERIALS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select>
        </div>

        {/* Floors */}
        <div>
          <div className="label" style={{ marginBottom: '5px', display: 'flex', justifyContent: 'space-between' }}>
            Floors
            <span style={{ fontFamily: 'var(--mono)', color: 'var(--cyan)', fontWeight: 600 }}>{form.floors}</span>
          </div>
          <input type="range" min={1} max={80} value={form.floors}
            onChange={e => set('floors', e.target.value)} />
        </div>

        {/* Footprint */}
        <div>
          <div className="label" style={{ marginBottom: '5px', display: 'flex', justifyContent: 'space-between' }}>
            Footprint
            <span style={{ fontFamily: 'var(--mono)', color: 'var(--cyan)', fontWeight: 600 }}>{Number(form.footprint_m2).toLocaleString()} m²</span>
          </div>
          <input type="range" min={200} max={8000} step={100} value={form.footprint_m2}
            onChange={e => set('footprint_m2', e.target.value)} />
        </div>

        {/* Units per floor */}
        <div>
          <div className="label" style={{ marginBottom: '5px', display: 'flex', justifyContent: 'space-between' }}>
            Units / Floor
            <span style={{ fontFamily: 'var(--mono)', color: 'var(--cyan)', fontWeight: 600 }}>{form.units_per_floor}</span>
          </div>
          <input type="range" min={2} max={40} value={form.units_per_floor}
            onChange={e => set('units_per_floor', e.target.value)} />
        </div>

        {/* Summary stats */}
        <div style={{
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius)',
          padding: '10px 12px',
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '6px',
        }}>
          {[
            ['Total GFA', `${(form.floors * form.footprint_m2 / 1000).toFixed(1)}k m²`],
            ['Total Units', (form.floors * form.units_per_floor).toLocaleString()],
          ].map(([k, v]) => (
            <div key={k}>
              <div style={{ fontSize: '10px', color: 'var(--text-3)', marginBottom: '2px' }}>{k}</div>
              <div style={{ fontFamily: 'var(--mono)', fontSize: '13px', fontWeight: 600, color: 'var(--text)' }}>{v}</div>
            </div>
          ))}
        </div>

        {/* Submit */}
        <button
          className="btn btn-primary"
          onClick={handleSubmit}
          disabled={!hasCoord || loading}
          style={{ width: '100%', padding: '10px' }}
        >
          {loading ? 'Analyzing...' : 'Analyze Impact'}
        </button>

        {!hasCoord && (
          <p style={{ textAlign: 'center', fontSize: '11px', color: 'var(--text-3)', margin: 0 }}>
            Click anywhere on the map first
          </p>
        )}
      </div>
    </div>
  )
}
