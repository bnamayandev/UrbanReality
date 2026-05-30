import { useRef, useState, useEffect, useCallback } from 'react'
import ReactMapGL, { Source, Layer, NavigationControl, Popup } from 'react-map-gl/mapbox'
import mapboxgl from 'mapbox-gl'
import * as THREE from 'three'
import 'mapbox-gl/dist/mapbox-gl.css'

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN
const TORONTO = { longitude: -79.3832, latitude: 43.6532, zoom: 13.5, pitch: 45, bearing: -10 }
const BILLBOARD_LAYER_ID = 'ai-image-billboard'

const MAP_STYLES = {
  builder: 'mapbox://styles/mapbox/dark-v11',
  citizen: 'mapbox://styles/mapbox/light-v11',
}

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
      0, '#0f1624', 50, '#131d2e', 100, '#162036', 200, '#1a2540',
    ],
    'fill-extrusion-height':  ['get', 'height'],
    'fill-extrusion-base':    ['get', 'min_height'],
    'fill-extrusion-opacity': 0.9,
  },
}

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
      0, '#d8dde8', 50, '#c8cede', 100, '#b8c0d4', 200, '#a8b2c8',
    ],
    'fill-extrusion-height':  ['get', 'height'],
    'fill-extrusion-base':    ['get', 'min_height'],
    'fill-extrusion-opacity': 0.85,
  },
}

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

// ── Three.js billboard hook ────────────────────────────────────────────────────
// Renders the AI image as a vertical plane standing on the map at `coord`.
function useBillboardLayer(mapRef, coord, imageSrc, floors) {
  const rendererRef = useRef(null)

  useEffect(() => {
    const map = mapRef.current?.getMap?.()

    const cleanup = () => {
      try {
        const m = mapRef.current?.getMap?.()
        if (m?.getLayer(BILLBOARD_LAYER_ID)) m.removeLayer(BILLBOARD_LAYER_ID)
      } catch { /* layer may already be gone */ }
      if (rendererRef.current) { rendererRef.current.dispose(); rendererRef.current = null }
    }

    if (!map || !coord || !imageSrc) { cleanup(); return }

    const heightM = (floors || 24) * 3.5
    // Width: keep aspect ratio of the generated image (800×1000 → 0.8 ratio)
    const widthM = heightM * 0.8

    const mercator = mapboxgl.MercatorCoordinate.fromLngLat([coord.lng, coord.lat], 0)
    const mpu = mercator.meterInMercatorCoordinateUnits()

    let scene, camera, threeRenderer

    const layer = {
      id: BILLBOARD_LAYER_ID,
      type: 'custom',
      renderingMode: '3d',

      onAdd(_, gl) {
        camera = new THREE.Camera()
        scene = new THREE.Scene()

        const texture = new THREE.TextureLoader().load(imageSrc, () => map.triggerRepaint())
        texture.colorSpace = THREE.SRGBColorSpace

        const geo = new THREE.PlaneGeometry(widthM, heightM)
        const mat = new THREE.MeshBasicMaterial({ map: texture, side: THREE.DoubleSide })
        const mesh = new THREE.Mesh(geo, mat)
        // Lift centre so the image bottom sits on the ground
        mesh.position.set(0, heightM / 2, 0)
        scene.add(mesh)

        threeRenderer = new THREE.WebGLRenderer({ canvas: map.getCanvas(), context: gl, antialias: true })
        threeRenderer.autoClear = false
        threeRenderer.outputColorSpace = THREE.SRGBColorSpace
        rendererRef.current = threeRenderer
      },

      render(_, matrix) {
        if (!threeRenderer) return
        const translate = new THREE.Matrix4().makeTranslation(mercator.x, mercator.y, mercator.z)
        const scale    = new THREE.Matrix4().makeScale(mpu, -mpu, mpu)
        const rotX     = new THREE.Matrix4().makeRotationX(Math.PI / 2)

        camera.projectionMatrix = new THREE.Matrix4()
          .fromArray(matrix)
          .multiply(translate)
          .multiply(scale)
          .multiply(rotX)

        threeRenderer.resetState()
        threeRenderer.render(scene, camera)
        map.triggerRepaint()
      },
    }

    const addLayer = () => {
      if (map.getLayer(BILLBOARD_LAYER_ID)) map.removeLayer(BILLBOARD_LAYER_ID)
      map.addLayer(layer)
    }

    const onStyleLoad = () => addLayer()
    map.on('style.load', onStyleLoad)
    if (map.isStyleLoaded()) addLayer()
    else map.once('load', addLayer)

    return () => {
      map.off('style.load', onStyleLoad)
      cleanup()
    }
  }, [mapRef, coord, imageSrc, floors])
}

// ── Existing building popups ───────────────────────────────────────────────────
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
          cursor: 'pointer', padding: '6px 4px 4px',
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
          display: 'inline-block', fontSize: '10px', fontWeight: 600,
          padding: '1px 6px', borderRadius: '3px',
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

// ── Main Map component ─────────────────────────────────────────────────────────
export function Map({ onCoordSelect, coord, buildingForm, existingBuildings, onSelectExisting, readOnly = false, mode = 'builder', mapPreview = null }) {
  const mapRef = useRef(null)
  const [selectedExisting, setSelectedExisting] = useState(null)
  const isDark = mode === 'builder'

  // Render AI image as a 3D billboard on the map
  useBillboardLayer(
    mapRef,
    coord,
    mapPreview?.image || null,
    buildingForm?.floors,
  )

  const handleClick = useCallback((e) => {
    if (readOnly || !onCoordSelect) return
    const { lng, lat } = e.lngLat
    onCoordSelect({ lat, lng })
  }, [onCoordSelect, readOnly])

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

  const hintBg      = isDark ? 'rgba(10,10,15,0.85)'     : 'rgba(245,246,250,0.90)'
  const hintColor   = isDark ? 'var(--text-2)'            : 'var(--text-2)'
  const activeBg    = isDark ? 'rgba(0,212,255,0.12)'    : 'rgba(0,119,204,0.10)'
  const activeBorder = isDark ? 'rgba(0,212,255,0.35)'   : 'rgba(0,119,204,0.35)'
  const activeColor  = isDark ? 'var(--cyan)'             : '#0077cc'

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
        <NavigationControl position="top-right" visualizePitch />
        <Layer {...(isDark ? BUILDINGS_DARK : BUILDINGS_LIGHT)} />

        {/* Placed building footprint extrusion */}
        {placedGeo && (
          <Source id="placed-building" type="geojson" data={placedGeo}>
            <Layer
              id="placed-building-fill"
              type="fill-extrusion"
              paint={{
                'fill-extrusion-color':   isDark ? '#00d4ff' : '#0077cc',
                'fill-extrusion-height':  ['get', 'height'],
                'fill-extrusion-base':    ['get', 'base'],
                'fill-extrusion-opacity': mapPreview?.image ? 0.25 : 0.72,
              }}
            />
          </Source>
        )}

        <ExistingMarkers
          buildings={existingBuildings}
          onSelect={handleSelectExisting}
          selected={selectedExisting}
        />
      </ReactMapGL>

      {/* Loading indicator while image is being generated */}
      {!readOnly && coord && mapPreview?.loading && (
        <div style={{
          position: 'absolute', bottom: 60, left: '50%', transform: 'translateX(-50%)',
          background: 'rgba(0,0,0,0.7)', borderRadius: 20, padding: '8px 16px',
          display: 'flex', alignItems: 'center', gap: 8, backdropFilter: 'blur(8px)',
          border: `1px solid ${isDark ? 'rgba(0,212,255,0.3)' : 'rgba(0,119,204,0.3)'}`,
          pointerEvents: 'none',
        }}>
          <div style={{
            width: 12, height: 12, borderRadius: '50%',
            border: '2px solid rgba(255,255,255,0.15)',
            borderTopColor: isDark ? 'var(--cyan)' : '#0077cc',
            animation: 'billSpin 0.8s linear infinite',
          }} />
          <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.7)' }}>Generating render…</span>
          <style>{`@keyframes billSpin { to { transform: rotate(360deg); } }`}</style>
        </div>
      )}

      {/* Bottom hint pills */}
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

      {!readOnly && coord && !mapPreview?.loading && (
        <div style={{
          position: 'absolute', bottom: 24, left: '50%', transform: 'translateX(-50%)',
          background: activeBg, border: `1px solid ${activeBorder}`,
          borderRadius: '20px', padding: '8px 20px',
          fontSize: '12px', color: activeColor,
          pointerEvents: 'none', backdropFilter: 'blur(10px)', whiteSpace: 'nowrap',
        }}>
          {mapPreview?.image ? 'Building rendered — fill the form and click Analyze Impact' : 'Building placed — describe it in the sidebar'}
        </div>
      )}

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
