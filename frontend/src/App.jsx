import { useState, useEffect, useCallback } from 'react'
import { Header } from './components/Header'
import { Map } from './components/Map'
import { BuildingForm } from './components/BuildingForm'
import { ImpactPanel } from './components/ImpactPanel'
import { CitizenPanel } from './components/CitizenPanel'
import { ImageConfirmModal } from './components/ImageConfirmModal'
import AuthModal from './components/AuthModal'
import { useBuilding } from './hooks/useBuilding'
import { useImpact } from './hooks/useImpact'
import { useBuilding3D } from './hooks/useBuilding3D'
import { useAuth } from './context/AuthContext'
import { getBuildings } from './api'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'
const DEFAULT_FORM = { name: '', description: '', floors: 24 }

export default function App() {
  const [mode,     setMode]     = useState('builder')
  const [coord,    setCoord]    = useState(null)
  const [existing, setExisting] = useState([])
  const [selected, setSelected] = useState(null)
  const [panelOpen, setPanelOpen] = useState(false)
  const [renderPayload, setRenderPayload] = useState(null)
  const [mode,          setMode]          = useState('citizen')    // default citizen; builder unlocks on auth
  const [coord,         setCoord]         = useState(null)
  const [formData,      setFormData]      = useState({ floors: 24, footprint_m2: 2000, type: 'residential (high-rise)' })
  const [liveForm,      setLiveForm]      = useState(DEFAULT_FORM)
  const [existing,      setExisting]      = useState([])
  const [selected,      setSelected]      = useState(null)
  const [panelOpen,     setPanelOpen]     = useState(false)
  const [renderPayload, setRenderPayload] = useState(null)
  const [mapPreview,    setMapPreview]    = useState({ image: null, loading: false })
  const [showAuthModal, setShowAuthModal] = useState(false)

  const { isOrgUser } = useAuth()

  // ── Image + TRELLIS flow ──────────────────────────────────────────────────
  const [mapPreview,        setMapPreview]        = useState({ image: null, loading: false })
  const [confirmedImageSrc, setConfirmedImageSrc] = useState(null)
  const [imageModal,        setImageModal]        = useState({ open: false, imageSrc: null, imageB64: null })
  const [trellisGlbUrl,     setTrellisGlbUrl]     = useState(null)
  const [pendingFormData,   setPendingFormData]   = useState(null)
  const [imageLoading,      setImageLoading]      = useState(false)

  const { building, loading: buildingLoading, submit, reset } = useBuilding()
  const buildingId = building?.id || selected?.id
  const { impact, loading: impactLoading, error: impactError, loadingMessage } = useImpact(buildingId)
  const { emit: emit3D, reset: reset3D } = useBuilding3D(setRenderPayload)

  useEffect(() => {
    document.documentElement.setAttribute('data-mode', mode)
  }, [mode])

  useEffect(() => {
    getBuildings().then(setExisting).catch(() => {})
  }, [])

  // Open panel when TRELLIS finishes or a building is saved/selected
  useEffect(() => {
    if (building || selected || trellisGlbUrl) setPanelOpen(true)
  }, [building, selected, trellisGlbUrl])
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (building || selected) setPanelOpen(true)
  }, [building, selected])

  // If user switches to builder mode without org auth, show login modal instead
  const generateMapPreview = async (formData, coordVal) => {
    if (!coordVal) return
    if (previewAbortRef.current) previewAbortRef.current.abort()
    const controller = new AbortController()
    previewAbortRef.current = controller

  // ── Step 1: Generate image ────────────────────────────────────────────────
  const handleGenerateImage = useCallback(async (data) => {
    setImageLoading(true)
    setMapPreview({ image: null, loading: true })
    setPendingFormData(data)

    const prompt = data.description?.trim()
      || `A modern ${data.floors || 24}-floor urban building in Toronto`

    try {
      const res = await fetch(`${API_BASE}/generate/building-image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt }),
      })
      if (!res.ok) throw new Error(`Image generation failed (${res.status})`)
      const result = await res.json()

      if (result.image_b64) {
        const src = `data:image/png;base64,${result.image_b64}`
        setMapPreview({ image: src, loading: false })
        setConfirmedImageSrc(src)
        setImageModal({ open: true, imageSrc: src, imageB64: result.image_b64 })
      }
    } catch (e) {
      console.error('Image generation failed:', e)
      setMapPreview({ image: null, loading: false })
    } finally {
      setImageLoading(false)
    }
  }, [])

  // ── Step 2: User denies image → back to form ──────────────────────────────
  const handleImageDeny = useCallback(() => {
    setImageModal({ open: false, imageSrc: null, imageB64: null })
    setMapPreview({ image: null, loading: false })
    setConfirmedImageSrc(null)
  }, [])

  // ── Step 3: TRELLIS completes → GLB on map + open panel ──────────────────
  const handleTrellisComplete = useCallback((glbUrl) => {
    setTrellisGlbUrl(glbUrl)
    setImageModal({ open: false, imageSrc: null, imageB64: null })
    setMapPreview({ image: null, loading: false })  // remove billboard; 3D model takes over
  }, [])

  // ── Step 4: Analyze Impact (user-triggered from panel) ────────────────────
  const handleAnalyzeImpact = useCallback(async () => {
    if (!pendingFormData) return
    setSelected(null)
    const result = await submit(pendingFormData)
    if (result) {
      emit3D(result.id, pendingFormData)
      getBuildings().then(setExisting).catch(() => {})
    }
  }, [pendingFormData, submit, emit3D])

  // ── Mode + reset ──────────────────────────────────────────────────────────
  const handleModeChange = useCallback((newMode) => {
    if (newMode === 'builder' && !isOrgUser) {
      setShowAuthModal(true)
      return
    }
    setMode(newMode)
    if (newMode === 'citizen') {
      reset(); reset3D()
      setCoord(null); setPanelOpen(false); setRenderPayload(null)
      setMapPreview({ image: null, loading: false })
      setImageModal({ open: false, imageSrc: null, imageB64: null })
      setTrellisGlbUrl(null); setConfirmedImageSrc(null); setPendingFormData(null)
    }
  }, [isOrgUser, reset, reset3D])

  // When org auth is acquired while modal was open, switch to builder
  useEffect(() => {
    if (isOrgUser && showAuthModal) {
      setShowAuthModal(false)
      setMode('builder')
    }
  }, [isOrgUser, showAuthModal])

  const handleReset = () => {
    reset(); reset3D()
    setCoord(null); setSelected(null); setPanelOpen(false); setRenderPayload(null)
    setMapPreview({ image: null, loading: false })
    setImageModal({ open: false, imageSrc: null, imageB64: null })
    setTrellisGlbUrl(null); setConfirmedImageSrc(null); setPendingFormData(null)
  }

  const handleSelectExisting = (b) => {
    reset(); reset3D()
    setCoord(null); setSelected(b); setRenderPayload(null)
    setMapPreview({ image: null, loading: false })
    setTrellisGlbUrl(null); setConfirmedImageSrc(null)
  }

  const activeBuilding = building || selected
  const isCitizen = mode === 'citizen'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden', background: 'var(--bg)', transition: 'background 0.2s' }}>
      <Header buildingCount={existing.length} mode={mode} onModeChange={handleModeChange} />
      <Header
        buildingCount={existing.length}
        mode={mode}
        onModeChange={handleModeChange}
        onLoginClick={() => setShowAuthModal(true)}
      />

      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', position: 'relative' }}>
        <Map
          onCoordSelect={isCitizen ? undefined : setCoord}
          coord={isCitizen ? null : coord}
          buildingForm={isCitizen ? null : { floors: pendingFormData?.floors ?? 24, footprint_m2: 2000, type: 'mixed-use' }}
          existingBuildings={existing}
          onSelectExisting={handleSelectExisting}
          readOnly={isCitizen}
          mode={mode}
          mapPreview={isCitizen ? null : mapPreview}
          trellisGlbUrl={isCitizen ? null : trellisGlbUrl}
        />

        {/* Builder form — shown until panel opens */}
        {!isCitizen && !panelOpen && (
          <BuildingForm
            coord={coord}
            onSubmit={handleGenerateImage}
            onReset={coord ? handleReset : null}
            loading={imageLoading}
            onFormChange={() => {}}
          />
        )}

        {/* "New building" chip when panel is open */}
        {!isCitizen && panelOpen && !selected && (
          <div style={{
            position: 'absolute', top: 60, left: 16,
            background: 'var(--bg-2)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius)', padding: '8px 12px', zIndex: 10,
            display: 'flex', alignItems: 'center', gap: '10px',
          }}>
            <span style={{ fontSize: '12px', color: 'var(--text-2)' }}>
              {building?.name || (trellisGlbUrl ? '3D Model Ready' : `Building #${building?.id}`)}
            </span>
            <button className="btn btn-ghost" onClick={handleReset} style={{ padding: '4px 10px', fontSize: '11px' }}>
              New building
            </button>
          </div>
        )}

        {/* Impact panel */}
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
              trellisGlbUrl={trellisGlbUrl}
              onAnalyzeImpact={handleAnalyzeImpact}
            />
          </div>
        )}

        {isCitizen && (
          <CitizenPanel building={activeBuilding} impact={impact} loading={impactLoading} existingBuildings={existing} />
        )}
      </div>

      {/* Image confirm / TRELLIS modal */}
      {imageModal.open && (
        <ImageConfirmModal
          imageSrc={imageModal.imageSrc}
          imageB64={imageModal.imageB64}
          onConfirm={handleTrellisComplete}
          onDeny={handleImageDeny}
        />
      )}
      {/* Auth modal */}
      {showAuthModal && <AuthModal onClose={() => setShowAuthModal(false)} />}
    </div>
  )
}
