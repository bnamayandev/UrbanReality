import { useState } from 'react'
import { MapPin, TrendingUp, Home, Leaf, Car, Building2, ChevronDown, ChevronUp } from 'lucide-react'
import { ScoreBar } from './ScoreBar'

const DIMENSIONS = [
  { key: 'environmental', label: 'Environmental',  Icon: Leaf },
  { key: 'traffic',       label: 'Traffic Load',   Icon: Car },
  { key: 'economic',      label: 'Economic',        Icon: TrendingUp },
  { key: 'infrastructure',label: 'Infrastructure',  Icon: Building2 },
  { key: 'housing',       label: 'Housing Supply',  Icon: Home },
]

export function CitizenPanel({ building, impact, loading, existingBuildings = [] }) {
  const [showScores, setShowScores] = useState(true)

  return (
    <div style={{
      width: 'var(--panel-w)',
      height: '100%',
      background: 'var(--bg-2)',
      borderLeft: '1px solid var(--border)',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
      flexShrink: 0,
    }}>
      {/* Header */}
      <div style={{
        padding: '16px',
        borderBottom: '1px solid var(--border)',
        background: 'var(--bg-3)',
        flexShrink: 0,
      }}>
        <div style={{ fontWeight: 700, fontSize: '15px', marginBottom: '4px', color: 'var(--text)' }}>
          Explore Toronto Developments
        </div>
        <div style={{ fontSize: '12px', color: 'var(--text-2)' }}>
          {existingBuildings.length} active developments · click a marker to explore
        </div>
      </div>

      {/* No building selected */}
      {!building && !loading && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '12px', padding: '24px', color: 'var(--text-3)' }}>
          <MapPin size={32} strokeWidth={1} />
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-2)', marginBottom: '6px' }}>
              Select a development
            </div>
            <div style={{ fontSize: '12px', lineHeight: 1.6 }}>
              Click any building marker on the map to see its impact analysis and ask questions.
            </div>
          </div>

          {/* Quick stats */}
          <div style={{
            width: '100%', marginTop: '8px',
            display: 'grid', gridTemplateColumns: '1fr 1fr',
            gap: '8px',
          }}>
            {[
              ['Active developments', existingBuildings.length],
              ['Avg floors', existingBuildings.length
                ? Math.round(existingBuildings.reduce((a, b) => a + (b.floors || 0), 0) / existingBuildings.length)
                : '—'],
            ].map(([label, val]) => (
              <div key={label} style={{
                background: 'var(--surface)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius)',
                padding: '12px',
                textAlign: 'center',
              }}>
                <div style={{ fontWeight: 700, fontSize: '22px', color: 'var(--cyan)', fontFamily: 'var(--mono)' }}>{val}</div>
                <div style={{ fontSize: '10px', color: 'var(--text-2)', marginTop: '3px' }}>{label}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: '12px', color: 'var(--text-3)' }}>
          <div style={{ width: 32, height: 32, borderRadius: '50%', border: '2px solid var(--border)', borderTopColor: 'var(--cyan)', animation: 'spin 1s linear infinite' }} />
          <span style={{ fontSize: '12px' }}>Loading impact data...</span>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      )}

      {/* Building selected */}
      {building && impact && !loading && (
        <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>

          {/* Building info card */}
          <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)' }}>
            <div style={{ fontWeight: 600, fontSize: '15px', marginBottom: '4px', color: 'var(--text)' }}>
              {building.name || `Development #${building.id}`}
            </div>
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '10px' }}>
              <span className="tag tag-dim">{building.type ? building.type.charAt(0).toUpperCase() + building.type.slice(1) : 'Unknown'}</span>
              <span className="tag tag-dim">{building.floors} Floors</span>
              <span className="tag tag-cyan">{building.status ? building.status.charAt(0).toUpperCase() + building.status.slice(1) : 'Under Review'}</span>
            </div>

            {/* Plain-language summary — citizen friendly */}
            <div style={{
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius)',
              padding: '12px',
              fontSize: '12px',
              color: 'var(--text-2)',
              lineHeight: 1.7,
            }}>
              This <strong style={{ color: 'var(--text)' }}>{building.floors}-storey {building.type}</strong> will
              bring roughly <strong style={{ color: 'var(--text)' }}>{(building.floors * (building.units_per_floor || 10)).toLocaleString()}</strong> new
              homes to the neighbourhood.
              {impact.traffic?.score > 60
                ? ' Expect noticeable changes to traffic in the area.'
                : ' Traffic impact is expected to be manageable.'}
            </div>
          </div>

          {/* Impact scores */}
          <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)' }}>
            <button onClick={() => setShowScores(s => !s)} style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              width: '100%', background: 'none', border: 'none', cursor: 'pointer',
              padding: 0, marginBottom: showScores ? '14px' : 0,
              color: 'var(--text)',
            }}>
              <span className="label">Neighbourhood Impact</span>
              {showScores ? <ChevronUp size={13} color="var(--text-3)" /> : <ChevronDown size={13} color="var(--text-3)" />}
            </button>
            <div style={{ fontSize: '10px', color: 'var(--text-3)', marginBottom: showScores ? 12 : 0 }}>How this development affects your neighbourhood (0 = minimal, 100 = major)</div>
            {showScores && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                {DIMENSIONS.map(({ key, label, Icon }) => (
                  <ScoreBar
                    key={key}
                    icon={Icon}
                    label={label}
                    score={impact[key]?.score ?? 0}
                    description={impact[key]?.description}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
