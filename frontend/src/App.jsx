import { useState, useEffect, useCallback } from 'react'
import { Header } from './components/Header'
import { Map } from './components/Map'
import { BuildingForm } from './components/BuildingForm'
import { ImpactPanel } from './components/ImpactPanel'
import { CitizenPanel } from './components/CitizenPanel'
import { useBuilding } from './hooks/useBuilding'
import { useImpact } from './hooks/useImpact'
import { useBuilding3D } from './hooks/useBuilding3D'
import { getBuildings } from './api'

export default function App() {
  const [mode,         setMode]         = useState('builder')   // 'builder' | 'citizen'
  const [coord,        setCoord]        = useState(null)
  const [formData,     setFormData]     = useState({ floors: 24, footprint_m2: 2000, type: 'residential (high-rise)' })
  const [existing,     setExisting]     = useState([])
  const [selected,     setSelected]     = useState(null)
  const [panelOpen,    setPanelOpen]    = useState(false)
  const [renderPayload, setRenderPayload] = useState(null)

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
    if (building || selected) setPanelOpen(true)
  }, [building, selected])

  const handleModeChange = useCallback((newMode) => {
    setMode(newMode)
    // In citizen mode, clear any builder state
    if (newMode === 'citizen') {
      reset(); reset3D()
      setCoord(null); setPanelOpen(false); setRenderPayload(null)
    }
  }, [reset, reset3D])

  const handleSubmit = async (data) => {
    setFormData({ floors: data.floors, footprint_m2: data.footprint_m2, type: data.type })
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
  }

  const handleSelectExisting = (b) => {
    reset(); reset3D()
    setCoord(null); setSelected(b); setRenderPayload(null)
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
        />

        {/* ── BUILDER mode UI ── */}
        {!isCitizen && !panelOpen && (
          <BuildingForm
            coord={coord}
            onSubmit={handleSubmit}
            onReset={coord || building ? handleReset : null}
            loading={buildingLoading}
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
