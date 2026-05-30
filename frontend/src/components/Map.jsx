import { useRef, useState, useEffect, useCallback } from 'react'
import ReactMapGL, { Source, Layer, Popup } from 'react-map-gl/mapbox'
import 'mapbox-gl/dist/mapbox-gl.css'

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN
const TORONTO = { longitude: -79.3832, latitude: 43.6532, zoom: 13.5, pitch: 45, bearing: -10 }

// Existing Toronto 3D buildings layer
const EXISTING_BUILDINGS_LAYER = {
  id: 'existing-3d-buildings',
  source: 'composite',
  'source-layer': 'building',
  filter: ['==', 'extrude', 'true'],
  type: 'fill-extrusion',
  minzoom: 14,
  paint: {
    'fill-extrusion-color': '#12121e',
    'fill-extrusion-height': ['get', 'height'],
    'fill-extrusion-base': ['get', 'min_height'],
    'fill-extrusion-opacity': 0.85,
  },
}

// Placed building extrusion (cyan highlight)
function placedBuildingSource(coord, floors, footprintM2) {
  if (!coord) return null
  const side = Math.sqrt(footprintM2) / 111320   // approx degrees
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

// Existing building markers (from /buildings endpoint)
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
      offset={[0, -4]}
    >
      <div
        onClick={() => onSelect(b)}
        style={{
          cursor: 'pointer',
          padding: '4px 0',
          minWidth: 140,
          borderLeft: `2px solid ${selected?.id === b.id ? 'var(--cyan)' : 'rgba(255,255,255,0.2)'}`,
          paddingLeft: 8,
        }}
      >
        <div style={{ fontWeight: 600, fontSize: '11px', color: 'var(--text)', marginBottom: 2 }}>
          {b.name || `Building #${b.id}`}
        </div>
        <div style={{ fontSize: '10px', color: 'var(--text-2)' }}>
          {b.type} · {b.floors}F
        </div>
      </div>
    </Popup>
  ))
}

export function Map({ onCoordSelect, coord, buildingForm, existingBuildings, onSelectExisting, readOnly = false }) {
  const mapRef  = useRef(null)
  const [cursor, setCursor] = useState(readOnly ? 'default' : 'crosshair')
  const [selectedExisting, setSelectedExisting] = useState(null)

  const handleClick = useCallback((e) => {
    if (readOnly || !onCoordSelect) return
    const { lng, lat } = e.lngLat
    onCoordSelect({ lat, lng })
  }, [onCoordSelect, readOnly])

  // Fly to coord when placed
  useEffect(() => {
    if (!coord || !mapRef.current) return
    mapRef.current.flyTo({
      center: [coord.lng, coord.lat],
      zoom: Math.max(mapRef.current.getZoom(), 15),
      duration: 800,
    })
  }, [coord])

  const handleSelectExisting = (b) => {
    setSelectedExisting(b)
    onSelectExisting?.(b)
    mapRef.current?.flyTo({ center: [b.lng, b.lat], zoom: 15, duration: 600 })
  }

  // Build placed building GeoJSON
  const placedGeo = coord && buildingForm
    ? placedBuildingSource(coord, buildingForm.floors || 24, buildingForm.footprint_m2 || 2000)
    : null

  return (
    <div style={{ flex: 1, position: 'relative' }}>
      <ReactMapGL
        ref={mapRef}
        mapboxAccessToken={MAPBOX_TOKEN}
        initialViewState={TORONTO}
        style={{ width: '100%', height: '100%' }}
        mapStyle="mapbox://styles/mapbox/dark-v11"
        cursor={cursor}
        onClick={handleClick}
        onMouseEnter={() => setCursor('crosshair')}
      >
        {/* Existing Toronto 3D buildings */}
        <Layer {...EXISTING_BUILDINGS_LAYER} />

        {/* Placed building extrusion */}
        {placedGeo && (
          <Source id="placed-building" type="geojson" data={placedGeo}>
            <Layer
              id="placed-building-fill"
              type="fill-extrusion"
              paint={{
                'fill-extrusion-color': '#00d4ff',
                'fill-extrusion-height': ['get', 'height'],
                'fill-extrusion-base': ['get', 'base'],
                'fill-extrusion-opacity': 0.65,
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
      </ReactMapGL>

      {/* Map instructions overlay */}
      {!coord && (
        <div style={{
          position: 'absolute',
          bottom: 24,
          left: '50%',
          transform: 'translateX(-50%)',
          background: 'rgba(10,10,15,0.85)',
          border: '1px solid var(--border)',
          borderRadius: '20px',
          padding: '8px 18px',
          fontSize: '12px',
          color: 'var(--text-2)',
          pointerEvents: 'none',
          backdropFilter: 'blur(8px)',
          whiteSpace: 'nowrap',
        }}>
          Click anywhere on the map to place a building
        </div>
      )}

      {coord && (
        <div style={{
          position: 'absolute',
          bottom: 24,
          left: '50%',
          transform: 'translateX(-50%)',
          background: 'rgba(0,212,255,0.12)',
          border: '1px solid rgba(0,212,255,0.3)',
          borderRadius: '20px',
          padding: '8px 18px',
          fontSize: '12px',
          color: 'var(--cyan)',
          pointerEvents: 'none',
          backdropFilter: 'blur(8px)',
          whiteSpace: 'nowrap',
        }}>
          Building placed — click Analyze Impact in the sidebar
        </div>
      )}
    </div>
  )
}
