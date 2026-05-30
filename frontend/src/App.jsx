import { useState, useEffect, useCallback, useRef } from 'react'
import { Header } from './components/Header'
import { Map } from './components/Map'
import { BuildingForm } from './components/BuildingForm'
import { ImpactPanel } from './components/ImpactPanel'
import { CitizenPanel } from './components/CitizenPanel'
import { useBuilding } from './hooks/useBuilding'
import { useImpact } from './hooks/useImpact'
import { useBuilding3D } from './hooks/useBuilding3D'
import { getBuildings } from './api'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

const DEFAULT_FORM = { name: '', description: '', floors: 24 }

export default function App() {
  const [mode,         setMode]         = useState('builder')   // 'builder' | 'citizen'
  const [coord,        setCoord]        = useState(null)
  const [formData,     setFormData]     = useState({ floors: 24, footprint_m2: 2000, type: 'residential (high-rise)' })
  const [liveForm,     setLiveForm]     = useState(DEFAULT_FORM)
  const [existing,     setExisting]     = useState([])
  const [selected,     setSelected]     = useState(null)
  const [panelOpen,    setPanelOpen]    = useState(false)
  const [renderPayload, setRenderPayload] = useState(null)
  const [mapPreview,   setMapPreview]   = useState({ image: null, loading: false })

  const previewTimerRef = useRef(null)
  const previewAbortRef = useRef(null)

  const { building, loading: buildingLoading, submit, reset } = useBuilding()
  const buildingId = building?.id || selected?.id
  const { impact, loading: impactLoading, error: impactError, loadingMessage } = useImpact(buildingId)
  const { emit: emit3D, reset: reset3D } = useBuilding3D(setRenderPayload)

  // Apply mode to <html> so CSS variables switch
  useEffect(() => {
    document.documentElement.setAttribute('data-mode', mode)
  }, [mode])

  useEffect(() => {
    getBuildings().then(setExisting).catch(() => {})
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (building || selected) setPanelOpen(true)
  }, [building, selected])

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

  // Trigger map preview whenever building type, material, or coord changes
  // (popup already guards on coord being truthy, so no state reset needed here)
  useEffect(() => {
    if (!coord) return
    clearTimeout(previewTimerRef.current)
    previewTimerRef.current = setTimeout(() => {
      generateMapPreview(liveForm, coord)
    }, 900)
    return () => clearTimeout(previewTimerRef.current)
  }, [liveForm.description, coord]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleFormChange = useCallback((data) => setLiveForm(data), [])

  const handleModeChange = useCallback((newMode) => {
    setMode(newMode)
    if (newMode === 'citizen') {
      reset(); reset3D()
      setCoord(null); setPanelOpen(false); setRenderPayload(null)
      setMapPreview({ image: null, loading: false })
      clearTimeout(previewTimerRef.current)
      if (previewAbortRef.current) previewAbortRef.current.abort()
    }
  }, [reset, reset3D])

  const handleSubmit = async (data) => {
    setFormData({ floors: data.floors, footprint_m2: 2000, type: 'mixed-use' })
    setSelected(null)
    const result = await submit(data)
    if (result) {
      emit3D(result.id, data)
      getBuildings().then(setExisting).catch(() => {})
    }
  }

  const handleReset = () => {
    reset(); reset3D()
    setCoord(null); setSelected(null); setPanelOpen(false); setRenderPayload(null)
    setMapPreview({ image: null, loading: false })
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
        <Map
          onCoordSelect={isCitizen ? undefined : setCoord}
          coord={isCitizen ? null : coord}
          buildingForm={isCitizen ? null : formData}
          existingBuildings={existing}
          onSelectExisting={handleSelectExisting}
          readOnly={isCitizen}
          mode={mode}
          mapPreview={isCitizen ? null : mapPreview}
        />

        {/* ── BUILDER mode UI ── */}
        {!isCitizen && !panelOpen && (
          <BuildingForm
            coord={coord}
            onSubmit={handleSubmit}
            onReset={coord || building ? handleReset : null}
            loading={buildingLoading}
            onFormChange={handleFormChange}
          />
        )}

        {!isCitizen && panelOpen && !selected && (
          <div style={{
            position: 'absolute', top: 60, left: 16,
            background: 'var(--bg-2)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius)', padding: '8px 12px', zIndex: 10,
            display: 'flex', alignItems: 'center', gap: '10px',
          }}>
            <span style={{ fontSize: '12px', color: 'var(--text-2)' }}>
              {building?.name || `Building #${building?.id}`}
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
    </div>
  )
}
