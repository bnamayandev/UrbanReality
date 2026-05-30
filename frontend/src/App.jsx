import { useState, useEffect, useCallback } from 'react'
import { Header } from './components/Header'
import { Map } from './components/Map'
import { BuildingForm } from './components/BuildingForm'
import { ImpactPanel } from './components/ImpactPanel'
import { useBuilding } from './hooks/useBuilding'
import { useImpact } from './hooks/useImpact'
import { useBuilding3D } from './hooks/useBuilding3D'
import { getBuildings } from './api'

export default function App() {
  const [coord,         setCoord]         = useState(null)
  const [formData,      setFormData]       = useState({ floors: 24, footprint_m2: 2000, type: 'residential (high-rise)' })
  const [existing,      setExisting]       = useState([])
  const [selected,      setSelected]       = useState(null)
  const [panelOpen,     setPanelOpen]      = useState(false)
  const [renderPayload, setRenderPayload]  = useState(null)

  const { building, loading: buildingLoading, submit, reset } = useBuilding()
  const buildingId = building?.id || selected?.id
  const { impact, loading: impactLoading, error: impactError, loadingMessage } = useImpact(buildingId)

  // 3D rendering hook — emits structured payloads on every create/update
  const { emit: emit3D, reset: reset3D } = useBuilding3D(setRenderPayload)

  useEffect(() => {
    getBuildings().then(setExisting).catch(() => {})
  }, [])

  useEffect(() => {
    if (building || selected) setPanelOpen(true)
  }, [building, selected])

  const handleSubmit = async (data) => {
    setFormData({ floors: data.floors, footprint_m2: data.footprint_m2, type: data.type })
    setSelected(null)
    const result = await submit(data)
    if (result) {
      // Emit 3D render payload — isUpdate is determined automatically by the hook
      emit3D(result.id, data)
      getBuildings().then(setExisting).catch(() => {})
    }
  }

  const handleReset = () => {
    reset()
    reset3D()
    setCoord(null)
    setSelected(null)
    setPanelOpen(false)
    setRenderPayload(null)
  }

  const handleSelectExisting = (b) => {
    reset()
    reset3D()
    setCoord(null)
    setSelected(b)
    setRenderPayload(null)
  }

  const activeBuilding = building || selected

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
      <Header buildingCount={existing.length} />

      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', position: 'relative' }}>
        <Map
          onCoordSelect={setCoord}
          coord={coord}
          buildingForm={formData}
          existingBuildings={existing}
          onSelectExisting={handleSelectExisting}
        />

        {/* Floating form — visible when panel is closed */}
        {!panelOpen && (
          <BuildingForm
            coord={coord}
            onSubmit={handleSubmit}
            onReset={coord || building ? handleReset : null}
            loading={buildingLoading}
          />
        )}

        {/* Mini header when panel is open */}
        {panelOpen && !selected && (
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

        {/* Impact panel slides in from right */}
        <div style={{
          width: panelOpen ? 'var(--panel-w)' : '0',
          transition: 'width 0.25s ease',
          overflow: 'hidden',
          flexShrink: 0,
          display: 'flex',
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
      </div>
    </div>
  )
}
