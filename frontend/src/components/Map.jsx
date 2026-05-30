import { useRef, useState, useEffect, useCallback } from 'react'
import ReactMapGL, { Source, Layer, NavigationControl, Popup } from 'react-map-gl/mapbox'
import 'mapbox-gl/dist/mapbox-gl.css'

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN
const TORONTO = { longitude: -79.3832, latitude: 43.6532, zoom: 13.5, pitch: 45, bearing: -10 }

// Map styles per mode
const MAP_STYLES = {
  builder: 'mapbox://styles/mapbox/dark-v11',
  citizen: 'mapbox://styles/mapbox/light-v11',
}

// 3D buildings layer — dark (builder) theme
const BUILDINGS_DARK = {
  id: 'existing-3d-buildings',
  source: 'composite',
  'source-layer': 'building',
  filter: ['==', 'extrude', 'true'],
  type: 'fill-extrusion',
  minzoom: 14,
  paint: {
    'fill-extrusion-color': [
      'interpolate', ['linear'], ['get', 'height'],
      0,   '#0f1624',
      50,  '#131d2e',
      100, '#162036',
      200, '#1a2540',
    ],
    'fill-extrusion-height':  ['get', 'height'],
    'fill-extrusion-base':    ['get', 'min_height'],
    'fill-extrusion-opacity': 0.9,
  },
}

// 3D buildings layer — light (citizen) theme
const BUILDINGS_LIGHT = {
  id: 'existing-3d-buildings',
  source: 'composite',
  'source-layer': 'building',
  filter: ['==', 'extrude', 'true'],
  type: 'fill-extrusion',
  minzoom: 14,
  paint: {
    'fill-extrusion-color': [
      'interpolate', ['linear'], ['get', 'height'],
      0,   '#d8dde8',
      50,  '#c8cede',
      100, '#b8c0d4',
      200, '#a8b2c8',
    ],
    'fill-extrusion-height':  ['get', 'height'],
    'fill-extrusion-base':    ['get', 'min_height'],
    'fill-extrusion-opacity': 0.85,
  },
}

// Converts footprint m² → approximate degree offset for the square polygon
function placedBuildingGeo(coord, floors, footprintM2) {
  if (!coord) return null
  const side = Math.sqrt(footprintM2) / 111320
  const { lat, lng } = coord
  return {
    type: 'Feature',
    geometry: {
      type: 'Polygon',
      coordinates: [[
        [lng - side / 2, lat - side / 2],
        [lng + side / 2, lat - side / 2],
        [lng + side / 2, lat + side / 2],
        [lng - side / 2, lat + side / 2],
        [lng - side / 2, lat - side / 2],
      ]],
    },
    properties: { height: floors * 3.5, base: 0 },
  }
}

function ExistingMarkers({ buildings, onSelect, selected }) {
  if (!buildings?.length) return null
  return buildings.map(b => (
    <Popup
      key={b.id}
      longitude={b.lng}
      latitude={b.lat}
      anchor="bottom"
      closeButton={false}
      closeOnClick={false}
      offset={[0, -6]}
    >
      <div
        onClick={() => onSelect(b)}
        style={{
          cursor: 'pointer',
          padding: '6px 4px 4px',
          minWidth: 150,
          borderLeft: `2px solid ${selected?.id === b.id ? 'var(--cyan)' : 'var(--border-2)'}`,
          paddingLeft: 8,
        }}
      >
        <div style={{ fontWeight: 600, fontSize: '12px', color: 'var(--text)', marginBottom: 2 }}>
          {b.name || `Building #${b.id}`}
        </div>
        <div style={{ fontSize: '11px', color: 'var(--text-2)', marginBottom: 4 }}>
          {b.type} · {b.floors}F
        </div>
        <div style={{
          display: 'inline-block',
          fontSize: '10px',
          fontWeight: 600,
          padding: '1px 6px',
          borderRadius: '3px',
          background: selected?.id === b.id ? 'var(--cyan)' : 'var(--surface-2)',
          color: selected?.id === b.id ? '#000' : 'var(--text-2)',
          border: '1px solid var(--border)',
        }}>
          {b.status || 'Under Review'}
        </div>
      </div>
    </Popup>
  ))
}

export function Map({ onCoordSelect, coord, buildingForm, existingBuildings, onSelectExisting, readOnly = false, mode = 'builder', mapPreview = null }) {
  const mapRef = useRef(null)
  const [selectedExisting, setSelectedExisting] = useState(null)
  const isDark = mode === 'builder'

  const handleClick = useCallback((e) => {
    if (readOnly || !onCoordSelect) return
    const { lng, lat } = e.lngLat
    onCoordSelect({ lat, lng })
  }, [onCoordSelect, readOnly])

  // Fly to placed coord
  useEffect(() => {
    if (!coord || !mapRef.current) return
    mapRef.current.flyTo({
      center: [coord.lng, coord.lat],
      zoom: Math.max(mapRef.current.getZoom(), 15.5),
      pitch: 55,
      duration: 900,
      essential: true,
    })
  }, [coord])

  // Sync map style when mode switches
  useEffect(() => {
    if (!mapRef.current) return
    const map = mapRef.current.getMap?.()
    if (map) map.setStyle(MAP_STYLES[mode])
  }, [mode])

  const handleSelectExisting = (b) => {
    setSelectedExisting(b)
    onSelectExisting?.(b)
    mapRef.current?.flyTo({ center: [b.lng, b.lat], zoom: 15.5, pitch: 50, duration: 700 })
  }

  const placedGeo = coord && buildingForm
    ? placedBuildingGeo(coord, buildingForm.floors || 24, buildingForm.footprint_m2 || 2000)
    : null

  const hintBg    = isDark ? 'rgba(10,10,15,0.85)'     : 'rgba(245,246,250,0.90)'
  const hintColor = isDark ? 'var(--text-2)'            : 'var(--text-2)'
  const activeBg  = isDark ? 'rgba(0,212,255,0.12)'    : 'rgba(0,119,204,0.10)'
  const activeBorder = isDark ? 'rgba(0,212,255,0.35)' : 'rgba(0,119,204,0.35)'
  const activeColor  = isDark ? 'var(--cyan)'           : '#0077cc'

  return (
    <div style={{ flex: 1, position: 'relative' }}>
      <ReactMapGL
        ref={mapRef}
        mapboxAccessToken={MAPBOX_TOKEN}
        initialViewState={TORONTO}
        style={{ width: '100%', height: '100%' }}
        mapStyle={MAP_STYLES[mode]}
        cursor={readOnly ? 'default' : 'crosshair'}
        onClick={handleClick}
      >
        {/* Navigation controls */}
        <NavigationControl position="top-right" visualizePitch />

        {/* Toronto 3D buildings — style switches with mode */}
        <Layer {...(isDark ? BUILDINGS_DARK : BUILDINGS_LIGHT)} />

        {/* Placed building extrusion */}
        {placedGeo && (
          <Source id="placed-building" type="geojson" data={placedGeo}>
            <Layer
              id="placed-building-fill"
              type="fill-extrusion"
              paint={{
                'fill-extrusion-color':   isDark ? '#00d4ff' : '#0077cc',
                'fill-extrusion-height':  ['get', 'height'],
                'fill-extrusion-base':    ['get', 'base'],
                'fill-extrusion-opacity': 0.72,
              }}
            />
            {/* Outline glow */}
            <Layer
              id="placed-building-outline"
              type="fill-extrusion"
              paint={{
                'fill-extrusion-color':   isDark ? '#00d4ff' : '#0077cc',
                'fill-extrusion-height':  ['get', 'height'],
                'fill-extrusion-base':    ['get', 'base'],
                'fill-extrusion-opacity': 0.15,
              }}
            />
          </Source>
        )}

        {/* Existing building popups */}
        <ExistingMarkers
          buildings={existingBuildings}
          onSelect={handleSelectExisting}
          selected={selectedExisting}
        />

        {/* AI building preview popup — appears at placed coord */}
        {!readOnly && coord && mapPreview && (mapPreview.loading || mapPreview.image) && (
          <Popup
            longitude={coord.lng}
            latitude={coord.lat}
            anchor="bottom"
            closeButton={false}
            closeOnClick={false}
            offset={[0, -24]}
          >
            <div style={{
              width: 210,
              background: 'rgba(8,12,22,0.95)',
              borderRadius: 8,
              overflow: 'hidden',
              border: `1px solid ${isDark ? 'rgba(0,212,255,0.35)' : 'rgba(0,119,204,0.35)'}`,
              boxShadow: `0 4px 24px rgba(0,0,0,0.6), 0 0 0 1px ${isDark ? 'rgba(0,212,255,0.08)' : 'rgba(0,119,204,0.08)'}`,
            }}>
              {/* Header bar */}
              <div style={{
                padding: '6px 10px',
                background: isDark ? 'rgba(0,212,255,0.08)' : 'rgba(0,119,204,0.08)',
                borderBottom: `1px solid ${isDark ? 'rgba(0,212,255,0.15)' : 'rgba(0,119,204,0.15)'}`,
                display: 'flex', alignItems: 'center', gap: 6,
              }}>
                <div style={{
                  width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
                  background: isDark ? 'var(--cyan)' : '#0077cc',
                  boxShadow: `0 0 6px ${isDark ? 'var(--cyan)' : '#0077cc'}`,
                  animation: mapPreview.loading ? 'previewPulse 1.2s ease-in-out infinite' : 'none',
                }} />
                <span style={{ fontSize: 10, fontWeight: 600, color: isDark ? 'var(--cyan)' : '#0077cc', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  {mapPreview.loading ? 'Generating preview…' : 'AI Preview'}
                </span>
              </div>

              {/* Loading state */}
              {mapPreview.loading && (
                <div style={{ padding: '18px 0', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
                  <div style={{
                    width: 20, height: 20, borderRadius: '50%',
                    border: '2px solid rgba(255,255,255,0.1)',
                    borderTopColor: isDark ? 'var(--cyan)' : '#0077cc',
                    animation: 'previewSpin 0.8s linear infinite',
                  }} />
                  <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)' }}>Building render on its way</span>
                </div>
              )}

              {/* Generated image */}
              {mapPreview.image && !mapPreview.loading && (
                <img
                  src={mapPreview.image}
                  alt="Building preview"
                  style={{ width: '100%', height: 'auto', display: 'block' }}
                />
              )}
            </div>
            <style>{`
              @keyframes previewSpin { to { transform: rotate(360deg); } }
              @keyframes previewPulse { 0%,100% { opacity:0.5; } 50% { opacity:1; } }
              .mapboxgl-popup-content { background:transparent!important; padding:0!important; box-shadow:none!important; border-radius:8px!important; }
              .mapboxgl-popup-tip { display:none!important; }
            `}</style>
          </Popup>
        )}
      </ReactMapGL>

      {/* Bottom hint pill — builder mode */}
      {!readOnly && !coord && (
        <div style={{
          position: 'absolute', bottom: 24, left: '50%', transform: 'translateX(-50%)',
          background: hintBg, border: '1px solid var(--border)',
          borderRadius: '20px', padding: '8px 20px',
          fontSize: '12px', color: hintColor,
          pointerEvents: 'none', backdropFilter: 'blur(10px)', whiteSpace: 'nowrap',
        }}>
          Click anywhere on the map to place a building
        </div>
      )}

      {!readOnly && coord && (
        <div style={{
          position: 'absolute', bottom: 24, left: '50%', transform: 'translateX(-50%)',
          background: activeBg, border: `1px solid ${activeBorder}`,
          borderRadius: '20px', padding: '8px 20px',
          fontSize: '12px', color: activeColor,
          pointerEvents: 'none', backdropFilter: 'blur(10px)', whiteSpace: 'nowrap',
        }}>
          Building placed — click Analyze Impact in the sidebar
        </div>
      )}

      {/* Citizen hint */}
      {readOnly && !selectedExisting && (
        <div style={{
          position: 'absolute', bottom: 24, left: '50%', transform: 'translateX(-50%)',
          background: hintBg, border: '1px solid var(--border)',
          borderRadius: '20px', padding: '8px 20px',
          fontSize: '12px', color: hintColor,
          pointerEvents: 'none', backdropFilter: 'blur(10px)', whiteSpace: 'nowrap',
        }}>
          Click any building marker to explore its impact
        </div>
      )}
    </div>
  )
}
