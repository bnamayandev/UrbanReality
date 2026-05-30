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

import { useEffect, useRef } from 'react'
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
  const prevPayloadRef = useRef(null)
  const isUpdate = renderPayload?.isUpdate
  const justUpdated = isUpdate && renderPayload !== prevPayloadRef.current

  useEffect(() => {
    if (renderPayload) prevPayloadRef.current = renderPayload
  }, [renderPayload])

  return (
    <div style={{
      position: 'relative',
      background: 'var(--bg-3)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius)',
      overflow: 'hidden',
      ...style,
    }}>
      {/* ── TEAMMATE HANDOFF ZONE ──────────────────────────────────────────
          Replace everything inside this div with your Three.js canvas.
          The renderPayload prop has everything your renderer needs.
          See the JSDoc comment at the top of this file for the full spec.
      ─────────────────────────────────────────────────────────────────── */}

      {!renderPayload ? (
        /* Empty state */
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: '8px', color: 'var(--text-3)', padding: '20px' }}>
          <Box size={28} strokeWidth={1} />
          <span style={{ fontSize: '11px' }}>3D preview will appear here</span>
        </div>
      ) : (
        <PlaceholderBuilding spec={renderPayload.spec} isUpdate={isUpdate} />
      )}

      {/* ── Status badge ────────────────────────────────────────────────── */}
      <div style={{
        position: 'absolute', top: 8, left: 8,
        display: 'flex', alignItems: 'center', gap: '4px',
        background: 'rgba(0,0,0,0.6)',
        border: '1px solid var(--border)',
        borderRadius: '3px',
        padding: '2px 7px',
        fontSize: '10px',
        color: 'var(--text-2)',
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

      {/* ── Update indicator ─────────────────────────────────────────────── */}
      {justUpdated && isUpdate && renderPayload.diff?.fields?.length > 0 && (
        <div style={{
          position: 'absolute', bottom: 8, right: 8,
          background: 'rgba(250,204,21,0.12)',
          border: '1px solid rgba(250,204,21,0.25)',
          borderRadius: '3px',
          padding: '3px 8px',
          fontSize: '10px',
          color: 'var(--score-mid)',
          display: 'flex', alignItems: 'center', gap: '4px',
        }}>
          <RefreshCw size={9} />
          {renderPayload.diff.fields.map(f => f.deltaText || f.label).join(', ')}
        </div>
      )}

      {/* ── Request counter ──────────────────────────────────────────────── */}
      {renderPayload && (
        <div style={{
          position: 'absolute', top: 8, right: 8,
          background: 'rgba(0,0,0,0.6)',
          border: '1px solid var(--border)',
          borderRadius: '3px',
          padding: '2px 7px',
          fontSize: '10px',
          color: 'var(--text-3)',
          fontFamily: 'var(--mono)',
        }}>
          req #{renderPayload.requestIndex}
        </div>
      )}
    </div>
  )
}
