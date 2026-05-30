import { useState } from 'react'
import { MapPin, RotateCcw, Sparkles } from 'lucide-react'

const DEFAULT_FORM = {
  name: '',
  description: '',
  floors: 24,
}

export function BuildingForm({ coord, onSubmit, onReset, loading, onFormChange }) {
  const [form, setForm] = useState(DEFAULT_FORM)

  const set = (key, val) => {
    const newForm = { ...form, [key]: val }
    setForm(newForm)
    onFormChange?.(newForm)
  }

  const handleSubmit = () => {
    if (!coord) return
    onSubmit({
      name:            form.name,
      description:     form.description,
      floors:          Number(form.floors),
      lat:             coord.lat,
      lng:             coord.lng,
      // renderPrompt drives the AI image generation in useBuilding3D
      renderPrompt:    form.description,
      // Defaults for the backend ML impact models
      type:            'mixed-use',
      material:        'glass',
      footprint_m2:    2000,
      units_per_floor: 10,
    })
  }

  const hasCoord = !!coord

  return (
    <div style={{
      position: 'absolute',
      top: 60,
      left: 16,
      width: 'var(--form-w)',
      maxHeight: 'calc(100vh - 80px)',
      background: 'var(--bg-2)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius)',
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
      zIndex: 10,
    }}>
      {/* Header */}
      <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
        <Sparkles size={14} color="var(--cyan)" />
        <span style={{ fontWeight: 600, fontSize: '13px' }}>Building Agent</span>
        {onReset && (
          <button className="btn btn-ghost" onClick={onReset}
            style={{ marginLeft: 'auto', padding: '4px 8px', fontSize: '11px', gap: '4px' }}>
            <RotateCcw size={10} /> Reset
          </button>
        )}
      </div>

      {/* Coordinate */}
      <div style={{
        padding: '8px 14px', flexShrink: 0,
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

      {/* Scrollable form body */}
      <div style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: '14px', overflowY: 'auto' }}>

        {/* Project Name */}
        <div>
          <div className="label" style={{ marginBottom: '5px' }}>
            Project Name <span style={{ color: 'var(--text-3)' }}>optional</span>
          </div>
          <input
            type="text"
            placeholder="e.g. King & Spadina Tower"
            value={form.name}
            onChange={e => set('name', e.target.value)}
          />
        </div>

        {/* Description — main prompt */}
        <div style={{
          background: 'rgba(0,212,255,0.05)',
          border: '1px solid rgba(0,212,255,0.22)',
          borderRadius: 'var(--radius)',
          padding: '10px 12px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px', marginBottom: '7px' }}>
            <Sparkles size={11} color="var(--cyan)" />
            <span className="label" style={{ color: 'var(--cyan)' }}>Describe your building</span>
          </div>
          <textarea
            rows={5}
            placeholder={'e.g. "A sleek 30-floor glass tower with a green roof, retail podium, and exposed concrete facade in downtown Toronto"'}
            value={form.description}
            onChange={e => set('description', e.target.value)}
            style={{
              resize: 'vertical',
              minHeight: 96,
              fontSize: '12px',
              lineHeight: 1.6,
              padding: '8px 10px',
            }}
          />
          <div style={{ fontSize: '10px', color: 'var(--text-3)', marginTop: 6, lineHeight: 1.5 }}>
            The AI renders your building from this description and analyzes its impact on Toronto.
          </div>
        </div>

        {/* Floors slider */}
        <div>
          <div className="label" style={{ marginBottom: '5px', display: 'flex', justifyContent: 'space-between' }}>
            Floors
            <span style={{ fontFamily: 'var(--mono)', color: 'var(--cyan)', fontWeight: 600 }}>{form.floors}</span>
          </div>
          <input
            type="range"
            min={1}
            max={80}
            value={form.floors}
            onChange={e => set('floors', e.target.value)}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--text-3)', marginTop: 2 }}>
            <span>1</span>
            <span>~{Math.round(form.floors * 3.5)}m tall</span>
            <span>80</span>
          </div>
        </div>

        {/* Submit */}
        <button
          className="btn btn-primary"
          onClick={handleSubmit}
          disabled={!hasCoord || loading}
          style={{ width: '100%', padding: '11px' }}
        >
          {loading ? 'Analyzing…' : 'Analyze Impact'}
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
