import { useState, useCallback, useRef } from 'react'
import { Loader, X, RefreshCw, Cuboid } from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

async function startTrellisJob(imageB64) {
  const res = await fetch(`${API_BASE}/trellis/generate-3d`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ image_b64: imageB64 }),
  })
  if (!res.ok) throw new Error(`TRELLIS start failed: ${res.status}`)
  return res.json()
}

async function pollJob(jobId) {
  const res = await fetch(`${API_BASE}/trellis/status/${jobId}`)
  if (!res.ok) throw new Error(`Poll failed: ${res.status}`)
  return res.json()
}

const STEPS = [
  'Uploading image to GX10…',
  'TRELLIS.2 initializing…',
  'Generating 3D mesh…',
  'Exporting GLB…',
]

export function ImageConfirmModal({ imageSrc, imageB64, onConfirm, onDeny }) {
  const [state, setState] = useState('idle')   // idle | starting | pending | running | done | error
  const [errMsg, setErrMsg] = useState(null)
  const [stepIdx, setStepIdx] = useState(0)
  const pollRef = useRef(null)
  const stepRef = useRef(null)

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
          setTimeout(() => onConfirm(`${API_BASE}${data.glb_url}`), 400)
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
  }, [onConfirm])

  const handleCreate3D = async () => {
    setState('starting')
    setErrMsg(null)
    setStepIdx(0)

    // Cycle through step labels for visual feedback during the long wait
    let i = 0
    const cycleStep = () => {
      i = Math.min(i + 1, STEPS.length - 1)
      setStepIdx(i)
      if (i < STEPS.length - 1) stepRef.current = setTimeout(cycleStep, 20000)
    }
    stepRef.current = setTimeout(cycleStep, 10000)

    try {
      const b64 = imageB64.includes(',') ? imageB64.split(',')[1] : imageB64
      const { job_id } = await startTrellisJob(b64)
      setState('pending')
      schedulePoll(job_id)
    } catch (e) {
      setErrMsg(e.message)
      setState('error')
      clearTimers()
    }
  }

  const handleDeny = () => { clearTimers(); onDeny() }

  const isRunning = ['starting', 'pending', 'running'].includes(state)

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
          <span style={{ fontWeight: 600, fontSize: 13 }}>
            {state === 'done' ? 'Model ready!' : isRunning ? 'Generating 3D Model…' : 'Confirm Image'}
          </span>
          {!isRunning && state !== 'done' && (
            <button
              onClick={handleDeny}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-2)', padding: 4, display: 'flex' }}
            >
              <X size={16} />
            </button>
          )}
        </div>

        {/* Image */}
        <div style={{ position: 'relative', background: '#0a0a0f', aspectRatio: '4/3' }}>
          <img
            src={imageSrc}
            alt="Generated building"
            style={{ width: '100%', height: '100%', objectFit: 'contain', display: 'block' }}
          />
          {isRunning && (
            <div style={{
              position: 'absolute', inset: 0,
              background: 'rgba(0,0,0,0.65)',
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16,
            }}>
              <Loader size={40} color="var(--cyan)" style={{ animation: 'spin 1s linear infinite' }} />
              <div style={{ textAlign: 'center', padding: '0 24px' }}>
                <div style={{ color: 'var(--cyan)', fontWeight: 600, fontSize: 13, marginBottom: 6 }}>
                  {STEPS[stepIdx]}
                </div>
                <div style={{ color: 'rgba(255,255,255,0.45)', fontSize: 11 }}>
                  TRELLIS.2 on the GX10 — this takes 2–10 min
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Actions */}
        <div style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
          {state === 'idle' && (
            <>
              <button
                className="btn btn-primary"
                onClick={handleCreate3D}
                style={{ width: '100%', padding: '11px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, fontSize: 13 }}
              >
                <Cuboid size={15} />
                Create 3D Model
              </button>
              <button
                className="btn btn-ghost"
                onClick={handleDeny}
                style={{ width: '100%', padding: '10px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
              >
                <RefreshCw size={13} />
                Regenerate Image
              </button>
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
