import { useState } from 'react'
import { MapPin, TrendingUp, Home, Leaf, Car, Building2, ChevronDown, ChevronUp, Navigation, Loader2 } from 'lucide-react'
import { ScoreBar } from './ScoreBar'
import { ChatBox } from './ChatBox'
import { getNearbyBuildings } from '../api'

const DIMENSIONS = [
  { key: 'environmental', label: 'Environmental',  Icon: Leaf },
  { key: 'traffic',       label: 'Traffic Load',   Icon: Car },
  { key: 'economic',      label: 'Economic',        Icon: TrendingUp },
  { key: 'infrastructure',label: 'Infrastructure',  Icon: Building2 },
  { key: 'housing',       label: 'Housing Supply',  Icon: Home },
]

const SUGGESTED_QUESTIONS = [
  'Will this raise my rent?',
  'How bad is the traffic impact?',
  'How many jobs does this create?',
  'Is this area safe to invest in?',
  'What happens to the trees here?',
  'How does this affect transit?',
]

export function CitizenPanel({ building, impact, loading, existingBuildings = [] }) {
  const [showScores,    setShowScores]    = useState(true)
  const [showChat,      setShowChat]      = useState(false)
  const [nearbyLoading, setNearbyLoading] = useState(false)
  const [nearbyError,   setNearbyError]   = useState('')
  const [nearbyList,    setNearbyList]    = useState(null)  // null = not fetched yet

  async function handleNearMe() {
    setNearbyError('')
    if (!navigator.geolocation) {
      setNearbyError('Geolocation is not supported by your browser.')
      return
    }
    setNearbyLoading(true)
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const results = await getNearbyBuildings(pos.coords.latitude, pos.coords.longitude, 2)
          setNearbyList(results)
        } catch (err) {
          setNearbyError('Could not load nearby buildings.')
        } finally {
          setNearbyLoading(false)
        }
      },
      () => {
        setNearbyError('Location permission denied.')
        setNearbyLoading(false)
      }
    )
  }

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
        <div style={{ fontSize: '12px', color: 'var(--text-2)', marginBottom: '10px' }}>
          {existingBuildings.length} active developments · click a marker to explore
        </div>

        {/* Near me button */}
        <button
          onClick={handleNearMe}
          disabled={nearbyLoading}
          style={{
            width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            background: 'var(--cyan-dim)', border: '1px solid var(--cyan)',
            borderRadius: 6, padding: '7px 12px',
            color: 'var(--cyan)', fontSize: 12, fontWeight: 600, cursor: 'pointer',
          }}
        >
          {nearbyLoading
            ? <><Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} /> Finding buildings near you...</>
            : <><Navigation size={13} /> Buildings near me</>}
        </button>
        {nearbyError && <p style={{ fontSize: 11, color: '#f87171', marginTop: 6 }}>{nearbyError}</p>}
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>

      {/* Nearby buildings list (shown after "near me" is clicked) */}
      {nearbyList !== null && !building && (
        <div style={{ flex: 1, overflowY: 'auto', padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 4 }}>
            {nearbyList.length === 0
              ? 'No buildings found within 2 km.'
              : `${nearbyList.length} building${nearbyList.length !== 1 ? 's' : ''} within 2 km of your location`}
          </div>
          {nearbyList.map(b => (
            <div key={b.id} style={{
              background: 'var(--surface)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius)', padding: '10px 12px',
            }}>
              <div style={{ fontWeight: 600, fontSize: 12, color: 'var(--text)', marginBottom: 3 }}>
                {b.name || `Development #${b.id}`}
              </div>
              <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                <span className="tag tag-dim">{b.type}</span>
                <span className="tag tag-dim">{b.floors} floors</span>
                <span className="tag tag-cyan">{b.status}</span>
                {b.org_name && <span className="tag tag-dim">{b.org_name}</span>}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* No building selected (default idle state) */}
      {!building && !loading && nearbyList === null && (
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

      {/* Loading impact */}
      {loading && (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: '12px', color: 'var(--text-3)' }}>
          <div style={{ width: 32, height: 32, borderRadius: '50%', border: '2px solid var(--border)', borderTopColor: 'var(--cyan)', animation: 'spin 1s linear infinite' }} />
          <span style={{ fontSize: '12px' }}>Loading impact data...</span>
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
              <span className="tag tag-dim">{building.type}</span>
              <span className="tag tag-dim">{building.floors} floors</span>
              <span className="tag tag-cyan">{building.status || 'Under Review'}</span>
              {building.org_name && (
                <span className="tag tag-dim" title="Builder organization">{building.org_name}</span>
              )}
            </div>

            {/* Plain-language summary */}
            <div style={{
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius)',
              padding: '12px',
              fontSize: '12px',
              color: 'var(--text-2)',
              lineHeight: 1.7,
            }}>
              This <strong style={{ color: 'var(--text)' }}>{building.floors}-floor {building.type}</strong> development
              will add approximately <strong style={{ color: 'var(--text)' }}>{(building.floors * (building.units_per_floor || 10)).toLocaleString()} units</strong> of
              housing to the area and generate an estimated{' '}
              <strong style={{ color: 'var(--text)' }}>+{impact.traffic?.score > 60 ? 'significant' : 'moderate'} traffic</strong> impact
              on nearby intersections.
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
              <span className="label">Impact Scores</span>
              {showScores ? <ChevronUp size={13} color="var(--text-3)" /> : <ChevronDown size={13} color="var(--text-3)" />}
            </button>
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

          {/* Ask AI */}
          <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)' }}>
            <button className="btn btn-primary" style={{ width: '100%' }}
              onClick={() => setShowChat(s => !s)}>
              {showChat ? 'Hide AI Assistant' : 'Ask about this development'}
            </button>
            {!showChat && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '8px' }}>
                {SUGGESTED_QUESTIONS.slice(0, 4).map(q => (
                  <span key={q} style={{
                    fontSize: '11px', color: 'var(--text-2)',
                    background: 'var(--surface)', border: '1px solid var(--border)',
                    borderRadius: '12px', padding: '3px 9px', cursor: 'default',
                  }}>{q}</span>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Chat pinned to bottom */}
      {showChat && building && impact && (
        <ChatBox buildingId={building?.id} />
      )}
    </div>
  )
}
