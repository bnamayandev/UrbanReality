/**
 * Building3DView.jsx — 3D Rendering Placeholder
 *
 * ═══════════════════════════════════════════════════════════════════════════
 * FOR REHAN / BEN (3D Rendering):
 *
 * This component receives a `renderPayload` prop every time the user
 * creates or modifies a building. Replace the placeholder UI below with
 * your Three.js / Mapbox fill-extrusion / WebGL renderer.
 *
 * Props:
 *   renderPayload  — the structured payload from useBuilding3D (see below)
 *   className      — optional CSS class
 *
 * Payload shape on CREATE (renderPayload.isUpdate === false):
 * {
 *   isUpdate: false,
 *   buildingId: 42,
 *   requestIndex: 1,
 *   naturalLanguage: "A 24-floor residential high-rise tower with a concrete
 *                     and glass facade, 2,000m² footprint...",
 *   spec: {
 *     type: "residential (high-rise)",
 *     floors: 24,
 *     footprint_m2: 2000,
 *     material: "glass",
 *     units_per_floor: 12,
 *     lat: 43.6532,
 *     lng: -79.3832,
 *     name: "King & Spadina Tower"
 *   },
 *   renderParams: {
 *     height_m: 84,       ← floors × 3.5m — use for extrusion height
 *     floors: 24,
 *     footprint_m2: 2000,
 *     type: "residential (high-rise)",
 *     material: "glass",  ← use to pick texture / color palette
 *     totalUnits: 288,
 *     gfa_m2: 48000,
 *     lat: 43.6532,
 *     lng: -79.3832,
 *   }
 * }
 *
 * Payload shape on UPDATE (renderPayload.isUpdate === true):
 * {
 *   isUpdate: true,
 *   buildingId: 43,
 *   requestIndex: 2,
 *   naturalLanguage: "Modified 1 property: added 1 floor (now 25 floors, ~87m tall).",
 *   spec: { ... },          ← full new spec
 *   previousSpec: { ... },  ← full old spec (for transition animation)
 *   diff: {
 *     fields: [
 *       { field: 'floors', label: 'floors', from: 24, to: 25, delta: 1, deltaText: '+1' }
 *     ],
 *     naturalLanguage: "Modified 1 property: added 1 floor..."
 *   },
 *   renderParams: { height_m: 87, floors: 25, ... }
 * }
 *
 * Suggested implementation:
 *
 *   useEffect(() => {
 *     if (!renderPayload) return
 *     if (renderPayload.isUpdate) {
 *       // Animate from renderPayload.previousSpec to renderPayload.spec
 *       // renderPayload.diff.fields tells you exactly what changed
 *       animateTransition(renderPayload.previousSpec, renderPayload.spec)
 *     } else {
 *       // Fresh build — construct from scratch
 *       buildModel(renderPayload.renderParams)
 *     }
 *   }, [renderPayload])
 *
 * ═══════════════════════════════════════════════════════════════════════════
 */

import { useEffect, useRef, useState } from 'react'
import { Box, ArrowUp, RefreshCw } from 'lucide-react'

// ── Material → color mapping for the placeholder ──────────────────────────
// Replace with your actual texture/material system
const MATERIAL_COLORS = {
  glass:       { facade: '#1a3a4a', window: '#00d4ff', glow: 'rgba(0,212,255,0.15)' },
  mass_timber: { facade: '#5c3a1e', window: '#c8a882', glow: 'rgba(200,168,130,0.15)' },
  steel:       { facade: '#2a3040', window: '#8ab4d4', glow: 'rgba(138,180,212,0.15)' },
  concrete:    { facade: '#2e2e34', window: '#6080a0', glow: 'rgba(96,128,160,0.15)' },
  brick:       { facade: '#5c2a1a', window: '#9090c0', glow: 'rgba(144,144,192,0.15)' },
}

function PlaceholderBuilding({ spec, isUpdate }) {
  if (!spec) return null

  const material = spec.material || 'glass'
  const colors   = MATERIAL_COLORS[material] || MATERIAL_COLORS.glass
  const floors   = spec.floors || 24
  const maxFloors = 80
  const heightPct = Math.min((floors / maxFloors) * 100, 100)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px', width: '100%', height: '100%', justifyContent: 'flex-end', padding: '0 24px 16px' }}>
      {/* Building silhouette */}
      <div style={{ position: 'relative', width: 80, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        {/* Tower */}
        <div style={{
          width: 56,
          height: `${heightPct * 1.4}px`,
          minHeight: 40,
          maxHeight: 140,
          background: colors.facade,
          border: `1px solid ${colors.window}44`,
          borderRadius: '2px 2px 0 0',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          transition: 'all 0.6s cubic-bezier(0.4, 0, 0.2, 1)',
          boxShadow: `0 0 20px ${colors.glow}`,
          position: 'relative',
        }}>
          {/* Window grid */}
          {Array.from({ length: Math.min(floors, 20) }).map((_, i) => (
            <div key={i} style={{
              flex: 1,
              borderBottom: `1px solid ${colors.window}22`,
              display: 'flex',
              gap: 3,
              padding: '0 3px',
              alignItems: 'center',
            }}>
              <div style={{ flex: 1, height: '60%', background: colors.window + '44', borderRadius: '1px' }} />
              <div style={{ flex: 1, height: '60%', background: colors.window + '44', borderRadius: '1px' }} />
            </div>
          ))}
          {/* Glow on top */}
          <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 8, background: `linear-gradient(${colors.window}66, transparent)` }} />
        </div>
        {/* Podium */}
        <div style={{ width: 72, height: 12, background: colors.facade, borderTop: `1px solid ${colors.window}66`, borderRadius: '0 0 2px 2px' }} />
        {/* Ground shadow */}
        <div style={{ width: 80, height: 4, background: 'rgba(0,0,0,0.4)', borderRadius: '50%', filter: 'blur(4px)', marginTop: 2 }} />
      </div>

      {/* Stats */}
      <div style={{ display: 'flex', gap: '12px', fontSize: '11px', color: 'var(--text-3)' }}>
        <span style={{ fontFamily: 'var(--mono)', color: 'var(--text-2)' }}>{floors}F</span>
        <span>·</span>
        <span style={{ fontFamily: 'var(--mono)', color: 'var(--text-2)' }}>{Math.round(floors * 3.5)}m</span>
        <span>·</span>
        <span style={{ color: colors.window, fontFamily: 'var(--mono)' }}>{material}</span>
      </div>
    </div>
  )
}

export function Building3DView({ renderPayload, style }) {
  const prevPayloadRef  = useRef(null)
  const [showPrompt, setShowPrompt] = useState(false)
  const isUpdate    = renderPayload?.isUpdate
  const justUpdated = isUpdate && renderPayload !== prevPayloadRef.current

  useEffect(() => {
    if (renderPayload) prevPayloadRef.current = renderPayload
  }, [renderPayload])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', ...style }}>

      {/* ── 3D viewport ───────────────────────────────────────────────────── */}
      <div style={{
        position: 'relative',
        background: 'var(--bg-3)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius)',
        overflow: 'hidden',
        flex: 1,
        minHeight: 160,
      }}>
        {/* ── TEAMMATE HANDOFF ZONE ────────────────────────────────────────
            Replace the content below with your Three.js / WebGL canvas.
            renderPayload.agentPrompt  → send this to your image-gen model
            renderPayload.renderParams → use for geometry (height, floors, etc.)
            renderPayload.isUpdate     → true = animate transition, false = fresh build
            renderPayload.diff         → exact field-level changes when isUpdate=true
        ─────────────────────────────────────────────────────────────────── */}

        {!renderPayload ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: '8px', color: 'var(--text-3)', padding: '20px' }}>
            <Box size={28} strokeWidth={1} />
            <span style={{ fontSize: '11px' }}>3D preview will appear here</span>
          </div>
        ) : (
          <PlaceholderBuilding spec={renderPayload.spec} isUpdate={isUpdate} />
        )}

        {/* Status badge */}
        <div style={{
          position: 'absolute', top: 8, left: 8,
          display: 'flex', alignItems: 'center', gap: '4px',
          background: 'rgba(0,0,0,0.7)', border: '1px solid var(--border)',
          borderRadius: '3px', padding: '2px 7px', fontSize: '10px', color: 'var(--text-2)',
        }}>
          <Box size={9} />
          <span>3D View</span>
          {renderPayload && (
            <>
              <span style={{ color: 'var(--text-3)' }}>·</span>
              <span style={{ color: isUpdate ? 'var(--score-mid)' : 'var(--cyan)' }}>
                {isUpdate ? 'Updated' : 'New build'}
              </span>
            </>
          )}
        </div>

        {/* Request counter */}
        {renderPayload && (
          <div style={{
            position: 'absolute', top: 8, right: 8,
            background: 'rgba(0,0,0,0.7)', border: '1px solid var(--border)',
            borderRadius: '3px', padding: '2px 7px', fontSize: '10px',
            color: 'var(--text-3)', fontFamily: 'var(--mono)',
          }}>
            req #{renderPayload.requestIndex}
          </div>
        )}

        {/* Update delta badge */}
        {isUpdate && renderPayload.diff?.fields?.length > 0 && (
          <div style={{
            position: 'absolute', bottom: 8, right: 8,
            background: 'rgba(250,204,21,0.12)', border: '1px solid rgba(250,204,21,0.25)',
            borderRadius: '3px', padding: '3px 8px', fontSize: '10px',
            color: 'var(--score-mid)', display: 'flex', alignItems: 'center', gap: '4px',
          }}>
            <RefreshCw size={9} />
            {renderPayload.diff.fields.map(f => f.deltaText || f.label).join(', ')}
          </div>
        )}
      </div>

      {/* ── Agent prompt panel ────────────────────────────────────────────── */}
      {renderPayload?.agentPrompt && (
        <div style={{
          background: 'var(--surface)',
          border: `1px solid ${isUpdate ? 'rgba(250,204,21,0.2)' : 'rgba(0,212,255,0.2)'}`,
          borderRadius: 'var(--radius)',
          overflow: 'hidden',
        }}>
          {/* Header row */}
          <button
            onClick={() => setShowPrompt(s => !s)}
            style={{
              width: '100%', background: 'none', border: 'none', cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: '8px',
              padding: '7px 10px', color: 'var(--text-2)',
            }}
          >
            <div style={{
              width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
              background: isUpdate ? 'var(--score-mid)' : 'var(--cyan)',
              boxShadow: `0 0 5px ${isUpdate ? 'var(--score-mid)' : 'var(--cyan)'}`,
            }} />
            <span style={{ fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', flex: 1, textAlign: 'left' }}>
              {isUpdate ? 'Update prompt' : 'Agent prompt'}
              <span style={{ fontWeight: 400, color: 'var(--text-3)', marginLeft: 6 }}>
                — send this to your image-gen model
              </span>
            </span>
            <span style={{ fontSize: '9px', color: 'var(--text-3)' }}>
              {showPrompt ? 'hide' : 'show'}
            </span>
          </button>

          {showPrompt && (
            <div style={{
              padding: '0 10px 10px',
              borderTop: '1px solid var(--border)',
            }}>
              {/* The ready-to-send prompt string */}
              <div style={{
                fontFamily: 'var(--mono)',
                fontSize: '10px',
                color: 'var(--text-2)',
                lineHeight: 1.7,
                padding: '10px',
                background: 'var(--bg-3)',
                borderRadius: '4px',
                marginTop: '8px',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}>
                {renderPayload.agentPrompt}
              </div>

              {/* Diff breakdown for update requests */}
              {isUpdate && renderPayload.diff?.fields?.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  <div style={{ fontSize: '9px', color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4 }}>
                    Changes injected into prompt
                  </div>
                  {renderPayload.diff.fields.map(f => (
                    <div key={f.field} style={{
                      display: 'flex', gap: '8px', fontSize: '11px',
                      padding: '3px 0', borderBottom: '1px solid var(--border)',
                      alignItems: 'center',
                    }}>
                      <span style={{ fontFamily: 'var(--mono)', color: 'var(--text-3)', width: 80, flexShrink: 0 }}>{f.field}</span>
                      <span style={{ fontFamily: 'var(--mono)', color: 'var(--score-crit)' }}>{String(f.from)}</span>
                      <span style={{ color: 'var(--text-3)' }}>→</span>
                      <span style={{ fontFamily: 'var(--mono)', color: 'var(--score-low)' }}>{String(f.to)}</span>
                      {f.deltaText && (
                        <span style={{ marginLeft: 'auto', fontFamily: 'var(--mono)', fontSize: '10px',
                          color: f.delta > 0 ? 'var(--score-low)' : 'var(--score-crit)',
                          background: f.delta > 0 ? 'rgba(74,222,128,0.1)' : 'rgba(248,113,113,0.1)',
                          border: `1px solid ${f.delta > 0 ? 'rgba(74,222,128,0.2)' : 'rgba(248,113,113,0.2)'}`,
                          borderRadius: '3px', padding: '1px 5px',
                        }}>
                          {f.deltaText}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
