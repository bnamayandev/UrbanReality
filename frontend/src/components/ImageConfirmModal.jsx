import { useState, useCallback, useRef } from 'react'
import { Loader, X, RefreshCw, Cuboid, Pencil, Check, ArrowLeft } from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

async function startRender3dJob(imageB64) {
  const res = await fetch(`${API_BASE}/render3d/generate-3d`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ image_b64: imageB64 }),
  })
  if (!res.ok) throw new Error(`3D generation start failed: ${res.status}`)
  return res.json()
}

async function pollJob(jobId) {
  const res = await fetch(`${API_BASE}/render3d/status/${jobId}`)
  if (!res.ok) throw new Error(`Poll failed: ${res.status}`)
  return res.json()
}

const STEPS = [
  'Uploading image…',
  'Stable Fast 3D initializing…',
  'Generating 3D mesh…',
  'Exporting GLB…',
]

export function ImageConfirmModal({ imageSrc, imageB64, onConfirm, onDeny }) {
  // 3D generation state
  const [state, setState] = useState('idle')   // idle | starting | pending | running | done | error
  const [errMsg, setErrMsg] = useState(null)
  const [stepIdx, setStepIdx] = useState(0)
  const pollRef = useRef(null)
  const stepRef = useRef(null)

  // Track the current image — updated after each successful edit
  const [currentSrc, setCurrentSrc] = useState(imageSrc)
  const [currentB64, setCurrentB64] = useState(imageB64)

  // Edit state
  const [editMode, setEditMode] = useState(false)
  const [editPrompt, setEditPrompt] = useState('')
  const [editLoading, setEditLoading] = useState(false)
  const [editErr, setEditErr] = useState(null)

  const clearTimers = () => {
    clearTimeout(pollRef.current)
    clearTimeout(stepRef.current)
  }

  const schedulePoll = useCallback((jobId) => {
    pollRef.current = setTimeout(async () => {
      try {
        const data = await pollJob(jobId)
        if (data.status === 'done') {
          setState('done')
          clearTimeout(stepRef.current)
          setTimeout(() => onConfirm(`${API_BASE}${data.glb_url}`, currentSrc), 400)
        } else if (data.status === 'error') {
          setErrMsg(data.error || 'Unknown error')
          setState('error')
          clearTimeout(stepRef.current)
        } else {
          setState(data.status)
          schedulePoll(jobId)
        }
      } catch (e) {
        setErrMsg(e.message)
        setState('error')
        clearTimeout(stepRef.current)
      }
    }, 5000)
  }, [onConfirm, currentSrc])

  const handleCreate3D = async () => {
    setState('starting')
    setErrMsg(null)
    setStepIdx(0)

    let i = 0
    const cycleStep = () => {
      i = Math.min(i + 1, STEPS.length - 1)
      setStepIdx(i)
      if (i < STEPS.length - 1) stepRef.current = setTimeout(cycleStep, 20000)
    }
    stepRef.current = setTimeout(cycleStep, 10000)

    try {
      const b64 = currentB64.includes(',') ? currentB64.split(',')[1] : currentB64
      const { job_id } = await startRender3dJob(b64)
      setState('pending')
      schedulePoll(job_id)
    } catch (e) {
      setErrMsg(e.message)
      setState('error')
      clearTimers()
    }
  }

  const handleApplyEdit = async () => {
    if (!editPrompt.trim()) return
    setEditLoading(true)
    setEditErr(null)
    try {
      const raw = currentB64.includes(',') ? currentB64.split(',')[1] : currentB64
      const res = await fetch(`${API_BASE}/generate/edit-image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_b64: raw, edit_prompt: editPrompt }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `${res.status}`)
      }
      const data = await res.json()
      const newSrc = `data:image/png;base64,${data.image_b64}`
      setCurrentSrc(newSrc)
      setCurrentB64(newSrc)
      setEditMode(false)
      setEditPrompt('')
    } catch (e) {
      setEditErr(e.message)
    } finally {
      setEditLoading(false)
    }
  }

  const handleDeny = () => { clearTimers(); onDeny() }

  const isRunning = ['starting', 'pending', 'running'].includes(state)
  const busy = isRunning || editLoading

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: 'rgba(0,0,0,0.82)',
      backdropFilter: 'blur(6px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <div style={{
        background: 'var(--bg-2)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        width: 'min(480px, 94vw)',
        overflow: 'hidden',
        display: 'flex', flexDirection: 'column',
        boxShadow: '0 24px 64px rgba(0,0,0,0.6)',
      }}>
        {/* Header */}
        <div style={{
          padding: '13px 16px',
          borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          background: 'var(--bg-3)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {editMode && !busy && (
              <button
                onClick={() => { setEditMode(false); setEditErr(null) }}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-2)', padding: 2, display: 'flex' }}
              >
                <ArrowLeft size={15} />
              </button>
            )}
            <span style={{ fontWeight: 600, fontSize: 13 }}>
              {state === 'done' ? 'Model ready!' : isRunning ? 'Generating 3D Model…' : editMode ? 'Edit Image' : 'Building Image'}
            </span>
          </div>
          {!busy && state !== 'done' && (
            <button
              onClick={editMode ? () => { setEditMode(false); setEditErr(null) } : handleDeny}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-2)', padding: 4, display: 'flex' }}
            >
              <X size={16} />
            </button>
          )}
        </div>

        {/* Image */}
        <div style={{ position: 'relative', background: '#0a0a0f', aspectRatio: '4/3' }}>
          <img
            src={currentSrc}
            alt="Generated building"
            style={{ width: '100%', height: '100%', objectFit: 'contain', display: 'block' }}
          />
          {busy && (
            <div style={{
              position: 'absolute', inset: 0,
              background: 'rgba(0,0,0,0.65)',
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16,
            }}>
              <Loader size={40} color="var(--cyan)" style={{ animation: 'spin 1s linear infinite' }} />
              <div style={{ textAlign: 'center', padding: '0 24px' }}>
                <div style={{ color: 'var(--cyan)', fontWeight: 600, fontSize: 13, marginBottom: 6 }}>
                  {editLoading ? 'Applying edits…' : STEPS[stepIdx]}
                </div>
                {isRunning && (
                  <div style={{ color: 'rgba(255,255,255,0.45)', fontSize: 11 }}>
                    Stable Fast 3D running locally — usually under a minute
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Actions */}
        <div style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>

          {/* Default idle — pick action */}
          {state === 'idle' && !editMode && (
            <>
              <button
                className="btn btn-primary"
                onClick={handleCreate3D}
                style={{ width: '100%', padding: '11px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, fontSize: 13 }}
              >
                <Cuboid size={15} />
                Create 3D Model
              </button>
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  className="btn btn-ghost"
                  onClick={() => { setEditMode(true); setEditErr(null) }}
                  style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
                >
                  <Pencil size={13} />
                  Edit Image
                </button>
                <button
                  className="btn btn-ghost"
                  onClick={handleDeny}
                  style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
                >
                  <RefreshCw size={13} />
                  Regenerate
                </button>
              </div>
            </>
          )}

          {/* Edit mode — NLP prompt */}
          {state === 'idle' && editMode && (
            <>
              <textarea
                autoFocus
                placeholder={'Describe your changes… e.g. "add a green roof and solar panels" or "make the facade red brick"'}
                value={editPrompt}
                onChange={e => setEditPrompt(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleApplyEdit() }
                }}
                rows={3}
                disabled={editLoading}
                style={{
                  resize: 'vertical', fontSize: 12,
                  background: 'var(--surface-2)', border: '1px solid var(--border)',
                  borderRadius: 'var(--radius)', color: 'var(--text)',
                  padding: '8px 10px', fontFamily: 'var(--font)', outline: 'none',
                  lineHeight: 1.5,
                }}
              />
              {editErr && (
                <div style={{
                  fontSize: 11, color: '#f87171', padding: '6px 10px',
                  background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.2)',
                  borderRadius: 6,
                }}>
                  {editErr}
                </div>
              )}
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  className="btn btn-primary"
                  onClick={handleApplyEdit}
                  disabled={!editPrompt.trim() || editLoading}
                  style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
                >
                  {editLoading
                    ? <Loader size={13} style={{ animation: 'spin 1s linear infinite' }} />
                    : <Check size={13} />}
                  {editLoading ? 'Applying…' : 'Apply Edit'}
                </button>
                <button
                  className="btn btn-ghost"
                  onClick={() => { setEditMode(false); setEditErr(null); setEditPrompt('') }}
                  disabled={editLoading}
                  style={{ flex: 1 }}
                >
                  Cancel
                </button>
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-3)', textAlign: 'center' }}>
                Shift+Enter for new line · Enter to apply
              </div>
            </>
          )}

          {isRunning && (
            <div style={{
              padding: '10px 14px', textAlign: 'center',
              background: 'rgba(0,212,255,0.06)', border: '1px solid rgba(0,212,255,0.15)',
              borderRadius: 8, fontSize: 11, color: 'var(--text-3)',
            }}>
              Polling every 5 seconds — you can leave this open
            </div>
          )}

          {state === 'error' && (
            <>
              <div style={{
                padding: '10px 14px',
                background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.2)',
                borderRadius: 8, fontSize: 12, color: '#f87171',
              }}>
                {errMsg}
              </div>
              <button className="btn btn-primary" onClick={handleCreate3D} style={{ width: '100%' }}>Retry</button>
              <button className="btn btn-ghost" onClick={handleDeny} style={{ width: '100%' }}>Regenerate Image</button>
            </>
          )}
        </div>
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
