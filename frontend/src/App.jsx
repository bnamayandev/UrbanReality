import { useState, useEffect, useCallback, useRef } from 'react'
import { Header } from './components/Header'
import { Map } from './components/Map'
import { BuildingForm } from './components/BuildingForm'
import { ImpactPanel } from './components/ImpactPanel'
import { CitizenPanel } from './components/CitizenPanel'
import { ImageConfirmModal } from './components/ImageConfirmModal'
import { ChatBox } from './components/ChatBox'
import { useBuilding } from './hooks/useBuilding'
import { useImpact } from './hooks/useImpact'
import { useBuilding3D } from './hooks/useBuilding3D'
import { getBuildings } from './api'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

const DEFAULT_FORM = { name: '', description: '', floors: 24 }

export default function App() {
  const [mode,             setMode]             = useState('builder')
  const [coord,            setCoord]            = useState(null)
  const [formData,         setFormData]         = useState({ floors: 24, footprint_m2: 2000, type: 'residential (high-rise)' })
  const [liveForm,         setLiveForm]         = useState(DEFAULT_FORM)
  const [existing,         setExisting]         = useState([])
  const [selected,         setSelected]         = useState(null)
  const [panelOpen,        setPanelOpen]        = useState(false)
  const [renderPayload,    setRenderPayload]    = useState(null)
  const [mapPreview,       setMapPreview]       = useState({ image: null, loading: false })
  const [imageModal,       setImageModal]       = useState({ open: false, imageSrc: null, imageB64: null })
  const [confirmedImageSrc, setConfirmedImageSrc] = useState(null)
  const [glbUrl,    setGlbUrl]   = useState(null)
  const [pendingFormData,  setPendingFormData]  = useState(null)

  const previewTimerRef = useRef(null)
  const previewAbortRef = useRef(null)

  const { building, loading: buildingLoading, submit, reset } = useBuilding()
  const buildingId = building?.id || selected?.id
  const { impact, loading: impactLoading, error: impactError, loadingMessage } = useImpact(buildingId)
  const { emit: emit3D, reset: reset3D } = useBuilding3D(setRenderPayload)

  useEffect(() => {
    document.documentElement.setAttribute('data-mode', 'builder')
  }, [])

  useEffect(() => {
    getBuildings().then(setExisting).catch(() => {})
  }, [])

  useEffect(() => {
    if (building || selected || glbUrl) setPanelOpen(true)
  }, [building, selected, glbUrl])

  const generateMapPreview = async (formData, coordVal) => {
    if (!coordVal) return
    if (previewAbortRef.current) previewAbortRef.current.abort()
    const controller = new AbortController()
    previewAbortRef.current = controller

    setMapPreview({ image: null, loading: true })
    try {
      const prompt = formData.description?.trim()
        || `A modern ${formData.floors || 24}-floor urban building in Toronto`
      const res = await fetch(`${API_BASE}/generate/building-image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt }),
        signal: controller.signal,
      })
      if (!res.ok) throw new Error(`${res.status}`)
      const data = await res.json()
      setMapPreview({ image: data.image_b64 ? `data:image/png;base64,${data.image_b64}` : null, loading: false })
    } catch (e) {
      if (e.name !== 'AbortError') setMapPreview({ image: null, loading: false })
    }
  }

  const handleFormChange = useCallback((data) => setLiveForm(data), [])

  const handleModeChange = useCallback((newMode) => {
    setMode(newMode)
    if (newMode === 'citizen') {
      reset(); reset3D()
      setCoord(null); setPanelOpen(false); setRenderPayload(null)
      setMapPreview({ image: null, loading: false })
      setGlbUrl(null); setConfirmedImageSrc(null); setPendingFormData(null)
      clearTimeout(previewTimerRef.current)
      if (previewAbortRef.current) previewAbortRef.current.abort()
    }
  }, [reset, reset3D])

  // Step 1: "Generate Image" — open confirm modal (reuse auto-preview or generate fresh)
  const handleSubmit = async (data) => {
    setPendingFormData(data)
    setFormData({ floors: data.floors, footprint_m2: 2000, type: 'mixed-use' })
    setSelected(null)

    if (mapPreview.image) {
      setImageModal({ open: true, imageSrc: mapPreview.image, imageB64: mapPreview.image })
      return
    }

    // No preview ready yet — generate now
    setMapPreview({ image: null, loading: true })
    try {
      const prompt = data.description?.trim()
        || `A modern ${data.floors || 24}-floor urban building in Toronto`
      const res = await fetch(`${API_BASE}/generate/building-image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt }),
      })
      if (!res.ok) throw new Error(`${res.status}`)
      const json = await res.json()
      const src = json.image_b64 ? `data:image/png;base64,${json.image_b64}` : null
      setMapPreview({ image: src, loading: false })
      if (src) setImageModal({ open: true, imageSrc: src, imageB64: src })
    } catch {
      setMapPreview({ image: null, loading: false })
    }
  }

  // Step 2a: user rejects image — close modal, let them try again
  const handleImageDeny = () => {
    setImageModal({ open: false, imageSrc: null, imageB64: null })
    setMapPreview({ image: null, loading: false })
  }

  // Step 2b: 3D model done — GLB URL arrives, panel opens
  // finalImageSrc is the image as it was when the user clicked Create 3D (may be edited)
  const handleModelComplete = (glbUrl, finalImageSrc) => {
    setGlbUrl(glbUrl)
    setConfirmedImageSrc(finalImageSrc || imageModal.imageSrc)
    setImageModal({ open: false, imageSrc: null, imageB64: null })
    setMapPreview({ image: null, loading: false }) // clear billboard so 3D takes over
  }

  // Step 3: "Analyze Impact" — run NeMoTron with the stored form data
  const handleAnalyzeImpact = async () => {
    if (!pendingFormData) return
    const result = await submit(pendingFormData)
    if (result) {
      emit3D(result.id, pendingFormData)
      getBuildings().then(setExisting).catch(() => {})
    }
  }

  const handleReset = () => {
    reset(); reset3D()
    setCoord(null); setSelected(null); setPanelOpen(false); setRenderPayload(null)
    setMapPreview({ image: null, loading: false })
    setGlbUrl(null); setConfirmedImageSrc(null); setPendingFormData(null)
    setImageModal({ open: false, imageSrc: null, imageB64: null })
    setLiveForm(DEFAULT_FORM)
    clearTimeout(previewTimerRef.current)
    if (previewAbortRef.current) previewAbortRef.current.abort()
  }

  const handleSelectExisting = (b) => {
    reset(); reset3D()
    setCoord(null); setSelected(b); setRenderPayload(null)
    setMapPreview({ image: null, loading: false })
  }

  const activeBuilding = building || selected
  const isCitizen = mode === 'citizen'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden', background: 'var(--bg)', transition: 'background 0.2s' }}>
      <Header
        buildingCount={existing.length}
        mode={mode}
        onModeChange={handleModeChange}
      />

      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', position: 'relative' }}>
        {/* ── CITIZEN left sidebar: NeMoTron chatbox ── */}
        {isCitizen && (
          <div style={{
            width: 320, height: '100%', flexShrink: 0,
            background: 'var(--bg-2)', borderRight: '1px solid var(--border)',
            display: 'flex', flexDirection: 'column', overflow: 'hidden',
          }}>
            <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)', background: 'var(--bg-3)' }}>
              <div style={{ fontWeight: 600, fontSize: '13px', marginBottom: 2 }}>Ask NeMoTron</div>
              <div style={{ fontSize: '11px', color: 'var(--text-2)' }}>
                {selected ? `Asking about: ${selected.name || `Building #${selected.id}`}` : 'Ask about any Toronto development'}
              </div>
            </div>
            <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
              <ChatBox buildingId={selected?.id} key={selected?.id ?? 'general'} />
            </div>
          </div>
        )}

        <Map
          onCoordSelect={isCitizen ? undefined : setCoord}
          coord={isCitizen ? null : coord}
          buildingForm={isCitizen ? null : formData}
          existingBuildings={existing}
          onSelectExisting={handleSelectExisting}
          readOnly={isCitizen}
          mode={mode}
          mapPreview={isCitizen ? null : mapPreview}
          glbUrl={glbUrl}
          onBack={!isCitizen && panelOpen ? handleReset : null}
        />

        {/* ── BUILDER mode UI ── */}
        {!isCitizen && !panelOpen && (
          <BuildingForm
            coord={coord}
            onSubmit={handleSubmit}
            onReset={coord || building ? handleReset : null}
            loading={buildingLoading || mapPreview.loading}
            onFormChange={handleFormChange}
          />
        )}

        {!isCitizen && panelOpen && !selected && (
          <div style={{
            position: 'absolute', top: 8, left: 16,
            background: 'var(--bg-2)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius)', padding: '8px 12px', zIndex: 10,
            display: 'flex', alignItems: 'center', gap: '10px',
          }}>
            <span style={{ fontSize: '12px', color: 'var(--text-2)' }}>
              {building?.name || (glbUrl ? '3D model ready' : `Building #${building?.id}`)}
            </span>
            <button className="btn btn-ghost" onClick={handleReset}
              style={{ padding: '4px 10px', fontSize: '11px' }}>
              New building
            </button>
          </div>
        )}

        {/* ── BUILDER impact panel ── */}
        {!isCitizen && (
          <div style={{
            width: panelOpen ? 'var(--panel-w)' : '0',
            transition: 'width 0.25s ease',
            overflow: 'hidden', flexShrink: 0, display: 'flex',
          }}>
            <ImpactPanel
              building={activeBuilding}
              impact={impact}
              loading={impactLoading}
              loadingMessage={loadingMessage}
              error={impactError}
              renderPayload={renderPayload}
              confirmedImageSrc={confirmedImageSrc}
              glbUrl={glbUrl}
              onAnalyzeImpact={handleAnalyzeImpact}
            />
          </div>
        )}

        {/* ── CITIZEN panel — always visible ── */}
        {isCitizen && (
          <CitizenPanel
            building={activeBuilding}
            impact={impact}
            loading={impactLoading}
            existingBuildings={existing}
          />
        )}
      </div>

      {/* DGX Spark watermark — bottom left */}
      <div style={{
        position: 'fixed', bottom: 8, left: 8, zIndex: 5,
        display: 'flex', alignItems: 'center', gap: 6,
        opacity: 0.45, pointerEvents: 'none',
      }}>
        <div style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--cyan)' }} />
        <span style={{ fontSize: 10, color: 'var(--text-2)', fontWeight: 500, letterSpacing: '0.03em' }}>
          DGX Spark · NeMoTron
        </span>
      </div>

      {/* Image confirm → 3D generation modal */}
      {imageModal.open && (
        <ImageConfirmModal
          imageSrc={imageModal.imageSrc}
          imageB64={imageModal.imageB64}
          onConfirm={handleModelComplete}
          onDeny={handleImageDeny}
        />
      )}

    </div>
  )
}
