/**
 * Building3DView.jsx
 *
 * Shows the AI-generated building image from Rehan's renderer pipeline.
 * Passes renderPayload.agentPrompt directly to POST /generate/building-image.
 *
 * AI renderer priority (backend): DALL-E 3 → Imagen 3 → FLUX → NVIDIA SDXL
 * Falls back to the deterministic Pillow silhouette if all AI providers fail.
 *
 * FOR REHAN: to plug in Three.js / WebGL 3D rendering, replace the <img> block
 * inside the viewport div with your canvas. renderPayload.renderParams has all
 * geometry data (height_m, floors, footprint_m2, lat, lng).
 */

import { useEffect, useRef, useState } from 'react'
import { Box, RefreshCw, Loader, AlertTriangle } from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

async function fetchBuildingImage(agentPrompt) {
  const res = await fetch(`${API_BASE}/generate/building-image`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt: agentPrompt }),
  })
  if (res.status === 503) throw new Error('no_api_key')  // Rehan's renderer: no OPENAI_API_KEY
  if (!res.ok) throw new Error(`Image API ${res.status}`)
  return res.json()  // { image_b64, image_path, metadata }
}

export function Building3DView({ renderPayload, style }) {
  const prevPayloadRef = useRef(null)
  const [imgSrc,    setImgSrc]    = useState(null)
  const [imgSource, setImgSource] = useState('')    // e.g. "DALL-E 3 · OpenAI"
  const [loading,   setLoading]   = useState(false)
  const [error,     setError]     = useState(null)
  const [showPrompt, setShowPrompt] = useState(false)

  const isUpdate = renderPayload?.isUpdate
  const hasChanged = renderPayload && renderPayload !== prevPayloadRef.current

  // Fetch AI image whenever payload changes
  useEffect(() => {
    if (!renderPayload?.agentPrompt || !hasChanged) return
    prevPayloadRef.current = renderPayload

    setLoading(true)
    setError(null)
    setImgSrc(null)
    setImgSource('')

    fetchBuildingImage(renderPayload.agentPrompt)
      .then(data => {
        if (data.image_b64) {
          setImgSrc(`data:image/png;base64,${data.image_b64}`)
          setImgSource(data.metadata?.source || data.metadata?.renderer || '')
        } else {
          setError('No image returned')
        }
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [renderPayload])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', ...style }}>

      {/* ── Viewport ─────────────────────────────────────────────────────── */}
      <div style={{
        position: 'relative',
        background: '#d3d3d3',   // matches the AI renderer canvas colour
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius)',
        overflow: 'hidden',
        flex: 1,
        minHeight: 180,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>

        {/* ── FOR REHAN: replace this block with your Three.js canvas ───── */}
        {loading && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px' }}>
            <Loader size={22} color="#555" style={{ animation: 'spin 1s linear infinite' }} />
            <span style={{ fontSize: '11px', color: '#666' }}>
              {isUpdate ? 'Updating render...' : 'Generating render...'}
            </span>
          </div>
        )}

        {imgSrc && !loading && (
          <img
            src={imgSrc}
            alt="AI building render"
            style={{ width: '100%', height: '100%', objectFit: 'contain' }}
          />
        )}

        {error && !loading && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px', padding: '20px' }}>
            <AlertTriangle size={20} color={error === 'no_api_key' ? '#facc15' : '#f87171'} />
            <span style={{ fontSize: '11px', color: '#888', textAlign: 'center' }}>
              {error === 'no_api_key'
                ? <>Render ready — add <span style={{ color: '#facc15', fontFamily: 'monospace' }}>OPENAI_API_KEY</span> to .env</>
                : 'Image generation unavailable'}
            </span>
          </div>
        )}

        {!renderPayload && !loading && !imgSrc && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px', color: '#888' }}>
            <Box size={28} strokeWidth={1} />
            <span style={{ fontSize: '11px' }}>Building render will appear here</span>
          </div>
        )}
        {/* ── end Three.js replacement zone ───────────────────────────────── */}

        {/* Status badges */}
        {renderPayload && (
          <div style={{
            position: 'absolute', top: 8, left: 8, display: 'flex', gap: '4px', flexWrap: 'wrap',
          }}>
            <div style={{
              background: 'rgba(0,0,0,0.55)', border: '1px solid rgba(255,255,255,0.15)',
              borderRadius: '3px', padding: '2px 7px', fontSize: '10px', color: 'rgba(255,255,255,0.7)',
              display: 'flex', alignItems: 'center', gap: '4px',
            }}>
              <Box size={8} />
              {isUpdate ? 'Updated' : 'New build'}
            </div>
            {imgSource && (
              <div style={{
                background: 'rgba(0,0,0,0.55)', border: '1px solid rgba(255,255,255,0.15)',
                borderRadius: '3px', padding: '2px 7px', fontSize: '10px', color: 'rgba(255,255,255,0.7)',
              }}>
                {imgSource}
              </div>
            )}
          </div>
        )}

        {renderPayload && (
          <div style={{
            position: 'absolute', top: 8, right: 8,
            background: 'rgba(0,0,0,0.55)', border: '1px solid rgba(255,255,255,0.15)',
            borderRadius: '3px', padding: '2px 7px', fontSize: '10px',
            color: 'rgba(255,255,255,0.6)', fontFamily: 'var(--mono)',
          }}>
            req #{renderPayload.requestIndex}
          </div>
        )}

        {isUpdate && renderPayload.diff?.fields?.length > 0 && !loading && (
          <div style={{
            position: 'absolute', bottom: 8, right: 8,
            background: 'rgba(250,204,21,0.15)', border: '1px solid rgba(250,204,21,0.35)',
            borderRadius: '3px', padding: '3px 8px', fontSize: '10px',
            color: '#facc15', display: 'flex', alignItems: 'center', gap: '4px',
          }}>
            <RefreshCw size={9} />
            {renderPayload.diff.fields.map(f => f.deltaText || f.label).join(', ')}
          </div>
        )}

        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>

      {/* ── Agent prompt panel ────────────────────────────────────────────── */}
      {renderPayload?.agentPrompt && (
        <div style={{
          background: 'var(--surface)',
          border: `1px solid ${isUpdate ? 'rgba(250,204,21,0.2)' : 'rgba(0,212,255,0.2)'}`,
          borderRadius: 'var(--radius)',
          overflow: 'hidden',
        }}>
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
              {isUpdate ? 'Update prompt' : 'Image prompt'}
              <span style={{ fontWeight: 400, color: 'var(--text-3)', marginLeft: 6 }}>
                — sent to AI renderer
              </span>
            </span>
            <span style={{ fontSize: '9px', color: 'var(--text-3)' }}>{showPrompt ? 'hide' : 'show'}</span>
          </button>

          {showPrompt && (
            <div style={{ padding: '0 10px 10px', borderTop: '1px solid var(--border)' }}>
              <div style={{
                fontFamily: 'var(--mono)', fontSize: '10px', color: 'var(--text-2)',
                lineHeight: 1.7, padding: '10px', background: 'var(--bg-3)',
                borderRadius: '4px', marginTop: '8px',
                whiteSpace: 'pre-wrap', wordBreak: 'break-word',
              }}>
                {renderPayload.agentPrompt}
              </div>

              {isUpdate && renderPayload.diff?.fields?.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  <div style={{ fontSize: '9px', color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4 }}>
                    Changes
                  </div>
                  {renderPayload.diff.fields.map(f => (
                    <div key={f.field} style={{
                      display: 'flex', gap: '8px', fontSize: '11px', padding: '3px 0',
                      borderBottom: '1px solid var(--border)', alignItems: 'center',
                    }}>
                      <span style={{ fontFamily: 'var(--mono)', color: 'var(--text-3)', width: 80, flexShrink: 0 }}>{f.field}</span>
                      <span style={{ fontFamily: 'var(--mono)', color: 'var(--score-crit)' }}>{String(f.from)}</span>
                      <span style={{ color: 'var(--text-3)' }}>→</span>
                      <span style={{ fontFamily: 'var(--mono)', color: 'var(--score-low)' }}>{String(f.to)}</span>
                      {f.deltaText && (
                        <span style={{
                          marginLeft: 'auto', fontFamily: 'var(--mono)', fontSize: '10px',
                          color: f.delta > 0 ? 'var(--score-low)' : 'var(--score-crit)',
                          background: f.delta > 0 ? 'rgba(74,222,128,0.1)' : 'rgba(248,113,113,0.1)',
                          border: `1px solid ${f.delta > 0 ? 'rgba(74,222,128,0.2)' : 'rgba(248,113,113,0.2)'}`,
                          borderRadius: '3px', padding: '1px 5px',
                        }}>{f.deltaText}</span>
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
