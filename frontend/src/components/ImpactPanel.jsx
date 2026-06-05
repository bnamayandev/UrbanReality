import { useState } from 'react'
import { Leaf, Car, TrendingUp, Building2, Home, ChevronDown, ChevronUp, Sparkles } from 'lucide-react'
import { ScoreBar } from './ScoreBar'
import { ChatBox } from './ChatBox'
import { Building3DView } from './Building3DView'

const DIMENSIONS = [
  { key: 'environmental', label: 'Environmental',  Icon: Leaf },
  { key: 'traffic',       label: 'Traffic Load',   Icon: Car },
  { key: 'economic',      label: 'Economic',        Icon: TrendingUp },
  { key: 'infrastructure',label: 'Infrastructure',  Icon: Building2 },
  { key: 'housing',       label: 'Housing Supply',  Icon: Home },
]

function LoadingState({ message }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1, gap: '20px', padding: '40px 24px' }}>
      <div style={{ position: 'relative', width: 56, height: 56 }}>
        <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', border: '2px solid var(--border)' }} />
        <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', border: '2px solid transparent', borderTopColor: 'var(--cyan)', animation: 'spin 1s linear infinite' }} />
        <div style={{ position: 'absolute', inset: 8, borderRadius: '50%', border: '2px solid transparent', borderTopColor: 'rgba(0,212,255,0.3)', animation: 'spin 1.5s linear infinite reverse' }} />
      </div>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: '12px', color: 'var(--cyan)', fontWeight: 500, marginBottom: '6px', minHeight: '18px' }}>{message}</div>
        <div style={{ fontSize: '11px', color: 'var(--text-3)' }}>NeMoTron on DGX Spark — this takes 15–45s</div>
      </div>
      <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {['Spatial context (500m radius)', 'XGBoost ML models', 'NeMoTron reasoning'].map((step, i) => (
          <div key={step} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', color: 'var(--text-3)' }}>
            <div style={{
              width: 5, height: 5, borderRadius: '50%',
              background: i === 0 ? 'var(--score-low)' : i === 1 ? 'var(--score-mid)' : 'var(--cyan)',
              boxShadow: `0 0 4px ${i === 0 ? 'var(--score-low)' : i === 1 ? 'var(--score-mid)' : 'var(--cyan)'}`,
              animation: 'pulse-dot 2s infinite', animationDelay: `${i * 0.4}s`,
            }} />
            {step}
          </div>
        ))}
      </div>
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse-dot { 0%, 100% { opacity: 0.4; } 50% { opacity: 1; } }
      `}</style>
    </div>
  )
}

export function ImpactPanel({
  building, impact, loading, loadingMessage, error, renderPayload,
  confirmedImageSrc, glbUrl, onAnalyzeImpact,
}) {
  const [expanded, setExpanded] = useState(true)
  const [showChat, setShowChat] = useState(false)

  if (!building && !loading && !glbUrl) return null

  const scores = impact ? DIMENSIONS.map(d => impact[d.key]?.score ?? 0) : []
  const avgScore = scores.length ? Math.round(scores.reduce((a, b) => a + b) / scores.length) : 0

  return (
    <div style={{
      width: 'var(--panel-w)', height: '100%',
      background: 'var(--bg-2)', borderLeft: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column', overflow: 'hidden', flexShrink: 0,
    }}>
      {/* Header */}
      <div style={{
        padding: '14px 16px', borderBottom: '1px solid var(--border)',
        background: 'var(--bg-3)', display: 'flex', flexDirection: 'column', gap: '8px', flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600, fontSize: '14px', marginBottom: '2px' }}>
              {building?.name || (glbUrl ? '3D Model Ready' : 'Proposed Building')}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-2)' }}>
              {building
                ? `${building.type} · ${building.floors}F · ${Number(building.footprint_m2).toLocaleString()} m²`
                : glbUrl ? '3D model ready' : ''}
            </div>
          </div>
          {impact && (
            <div style={{ textAlign: 'right', flexShrink: 0 }}>
              <div style={{
                fontFamily: 'var(--mono)', fontSize: '22px', fontWeight: 700,
                color: avgScore <= 30 ? 'var(--score-low)' : avgScore <= 60 ? 'var(--score-mid)' : avgScore <= 85 ? 'var(--score-high)' : 'var(--score-crit)',
              }}>
                {avgScore}
              </div>
              <div style={{ fontSize: '10px', color: 'var(--text-3)' }}>Impact Score</div>
              <div style={{ fontSize: '9px', color: 'var(--text-3)', maxWidth: 70, textAlign: 'right', lineHeight: 1.4 }}>
                {avgScore <= 30 ? 'Low Impact' : avgScore <= 60 ? 'Moderate' : avgScore <= 85 ? 'High Impact' : 'Critical'}
              </div>
            </div>
          )}
        </div>

        {building && (
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            <span className="tag tag-dim">{building.lat?.toFixed(4)}, {building.lng?.toFixed(4)}</span>
            <span className="tag tag-dim">{building.material || 'glass'}</span>
            <span className="tag tag-cyan">{building.status || 'Under Review'}</span>
          </div>
        )}
      </div>

      {/* Scrollable content */}
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>

        {/* 3D view — shown whenever we have image or GLB */}
        {(confirmedImageSrc || glbUrl) && (
          <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)' }}>
            <Building3DView
              imageSrc={confirmedImageSrc}
              glbUrl={glbUrl}
              style={{ width: '100%' }}
            />
            {renderPayload?.naturalLanguage && (
              <div style={{
                marginTop: 8, padding: '8px 10px',
                background: 'var(--surface)', border: '1px solid var(--border)',
                borderRadius: 'var(--radius)', fontSize: '11px', color: 'var(--text-2)', lineHeight: 1.6,
              }}>
                <span style={{ color: 'var(--text-3)', fontSize: '9px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', display: 'block', marginBottom: 3 }}>
                  Building description
                </span>
                {renderPayload.naturalLanguage}
              </div>
            )}
          </div>
        )}

        {/* Analyze Impact CTA — shown after 3D model, before impact runs */}
        {glbUrl && !building && !loading && (
          <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)' }}>
            <button
              className="btn btn-primary"
              onClick={onAnalyzeImpact}
              style={{ width: '100%', padding: '11px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, fontSize: 13 }}
            >
              <Sparkles size={14} />
              Analyze Impact
            </button>
            <div style={{ fontSize: 11, color: 'var(--text-3)', textAlign: 'center', marginTop: 8, lineHeight: 1.5 }}>
              Run NeMoTron impact analysis for this building
            </div>
          </div>
        )}

        {loading && <LoadingState message={loadingMessage} />}

        {error && !loading && (
          <div style={{ padding: '20px 16px', textAlign: 'center' }}>
            <div style={{ color: 'var(--score-crit)', fontSize: '13px', marginBottom: '8px' }}>Analysis failed</div>
            <div style={{ fontSize: '11px', color: 'var(--text-3)' }}>{error}</div>
          </div>
        )}

        {impact && !loading && (
          <>
            {/* Impact scores */}
            <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
                <div>
                  <span className="label">Impact Analysis</span>
                  <div style={{ fontSize: '10px', color: 'var(--text-3)', marginTop: 2 }}>Score 0–100 · higher means greater city impact</div>
                </div>
                <button onClick={() => setExpanded(e => !e)} style={{ background: 'none', border: 'none', color: 'var(--text-2)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '3px', fontSize: '11px' }}>
                  {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                  {expanded ? 'Collapse' : 'Expand'}
                </button>
              </div>
              {expanded && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  {DIMENSIONS.map(({ key, label, Icon }) => (
                    <ScoreBar key={key} icon={Icon} label={label} score={impact[key]?.score ?? 0} description={impact[key]?.description} />
                  ))}
                </div>
              )}
            </div>

            {/* Transit discount note */}
            {impact?.traffic?.transit_tier && impact.traffic.transit_tier !== 'none' && (
              <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--border)', background: 'var(--surface)' }}>
                <span className="label" style={{ display: 'block', marginBottom: 6 }}>Notes</span>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--score-low)',
                  background: 'rgba(74,222,128,0.08)', border: '1px solid rgba(74,222,128,0.2)',
                  borderRadius: 'var(--radius)', padding: '5px 10px',
                }}>
                  <span style={{ fontWeight: 600 }}>TTC proximity discount applied</span>
                  <span style={{ color: 'var(--text-2)' }}>
                    — {impact.traffic.transit_tier === 'transit_within_400m' ? '−30%' : '−15%'} vehicle trips
                    ({impact.traffic.daily_trips_base?.toLocaleString()} → {impact.traffic.daily_trips?.toLocaleString()}/day)
                  </span>
                </div>
              </div>
            )}

            {/* Chat toggle */}
            <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--border)' }}>
              <button className="btn btn-ghost" style={{ width: '100%', fontSize: '12px' }}
                onClick={() => setShowChat(s => !s)}>
                {showChat ? 'Hide' : 'Ask about this building'}
                {showChat ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              </button>
            </div>
          </>
        )}
      </div>

      {showChat && impact && (
        <div style={{ background: 'rgba(0,212,255,0.03)', borderTop: '1px solid rgba(0,212,255,0.15)' }}>
          <ChatBox buildingId={building?.id} />
        </div>
      )}
    </div>
  )
}
