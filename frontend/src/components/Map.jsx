import { useRef, useState, useEffect } from 'react'
import ReactMapGL, { Source, Layer, NavigationControl, Popup } from 'react-map-gl/mapbox'
import mapboxgl from 'mapbox-gl'
import * as THREE from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import * as turf from '@turf/turf'
import 'mapbox-gl/dist/mapbox-gl.css'

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN
const TORONTO = { longitude: -79.3832, latitude: 43.6532, zoom: 13.5, pitch: 55, bearing: -10 }
const BILLBOARD_LAYER_ID = 'ai-image-billboard'
const GLB_LAYER_ID = 'glb-building-model'
const EMPTY_GEO = { type: 'FeatureCollection', features: [] }

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

// ── Geometry helpers ───────────────────────────────────────────────────────────

function makeRectGeo(start, end) {
  const minLng = Math.min(start.lng, end.lng)
  const maxLng = Math.max(start.lng, end.lng)
  const minLat = Math.min(start.lat, end.lat)
  const maxLat = Math.max(start.lat, end.lat)
  return {
    type: 'Feature',
    geometry: {
      type: 'Polygon',
      coordinates: [[
        [minLng, minLat], [maxLng, minLat], [maxLng, maxLat],
        [minLng, maxLat], [minLng, minLat],
      ]],
    },
    properties: {},
  }
}

function rectCenter(start, end) {
  return { lng: (start.lng + end.lng) / 2, lat: (start.lat + end.lat) / 2 }
}

function rectDimensions(start, end) {
  const width = turf.distance(
    turf.point([start.lng, start.lat]),
    turf.point([end.lng, start.lat]),
    { units: 'meters' }
  )
  const depth = turf.distance(
    turf.point([start.lng, start.lat]),
    turf.point([start.lng, end.lat]),
    { units: 'meters' }
  )
  return { width, depth }
}

// Approximate square footprint for an existing building centred on its lat/lng
function buildingApproxFootprint(b) {
  const sideM = Math.sqrt(b.footprint_m2 || 2000)
  const halfLat = (sideM / 2) / 111320
  const halfLng = (sideM / 2) / (111320 * Math.cos(b.lat * Math.PI / 180))
  return turf.polygon([[
    [b.lng - halfLng, b.lat - halfLat],
    [b.lng + halfLng, b.lat - halfLat],
    [b.lng + halfLng, b.lat + halfLat],
    [b.lng - halfLng, b.lat + halfLat],
    [b.lng - halfLng, b.lat - halfLat],
  ]])
}

function hasConflict(rectGeo, buildings) {
  if (!rectGeo || !buildings?.length) return false
  return buildings.some(b => {
    try { return turf.booleanIntersects(rectGeo, buildingApproxFootprint(b)) }
    catch { return false }
  })
}

function compassLabel(deg) {
  const dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
  return dirs[Math.round(deg / 45) % 8]
}

// Rotated building footprint (meters) centred on coord → GeoJSON polygon.
// Negated az matches Three.js rotationY direction.
function footprintGeo(coord, widthM, depthM, rotDeg) {
  const az = -(rotDeg * Math.PI) / 180
  const cosA = Math.cos(az)
  const sinA = Math.sin(az)
  const w = widthM / 2
  const d = depthM / 2
  const mPerDegLat = 111320
  const mPerDegLng = 111320 * Math.cos(coord.lat * Math.PI / 180)

  const corners = [[-w, -d], [w, -d], [w, d], [-w, d]].map(([x, z]) => {
    const eastM  =  cosA * x + sinA * z
    const northM = -sinA * x + cosA * z
    return [coord.lng + eastM / mPerDegLng, coord.lat + northM / mPerDegLat]
  })

  return {
    type: 'Feature',
    geometry: { type: 'Polygon', coordinates: [[...corners, corners[0]]] },
    properties: {},
  }
}

// ── Three.js billboard hook (AI image) ────────────────────────────────────────
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

// ── GLB building layer ─────────────────────────────────────────────────────────

function buildGLBLayer(coord, rectWidth, rectDepth, rotationRef, onDimsReady, glbUrl) {
  const mercator = mapboxgl.MercatorCoordinate.fromLngLat([coord.lng, coord.lat], 0)
  const mpu = mercator.meterInMercatorCoordinateUnits()

  let renderer, scene, camera, _map
  let modelScale = mpu

  return {
    id: GLB_LAYER_ID,
    type: 'custom',
    renderingMode: '3d',

    onAdd(map, gl) {
      _map = map
      camera = new THREE.Camera()
      scene = new THREE.Scene()
      scene.add(new THREE.AmbientLight(0xffffff, 1.0))
      const sun = new THREE.DirectionalLight(0xffffff, 1.5)
      sun.position.set(0.5, -1, 1).normalize()
      scene.add(sun)

      new GLTFLoader().load(glbUrl, (gltf) => {
        const box = new THREE.Box3().setFromObject(gltf.scene)
        const size = new THREE.Vector3()
        const center = new THREE.Vector3()
        box.getSize(size)
        box.getCenter(center)

        gltf.scene.position.set(-center.x, -box.min.y, -center.z)

        const metersPerUnit = Math.min(rectWidth / size.x, rectDepth / size.z)
        modelScale = metersPerUnit * mpu

        onDimsReady?.({ width: size.x * metersPerUnit, depth: size.z * metersPerUnit })
        scene.add(gltf.scene)
        map.triggerRepaint()
      })

      renderer = new THREE.WebGLRenderer({ canvas: map.getCanvas(), context: gl, antialias: true })
      renderer.autoClear = false
      renderer.outputColorSpace = THREE.SRGBColorSpace
    },

    render(gl, matrix) {
      const azimuth = ((rotationRef?.current ?? 0) * Math.PI) / 180
      const translate = new THREE.Matrix4().makeTranslation(mercator.x, mercator.y, mercator.z)
      const scale = new THREE.Matrix4().makeScale(modelScale, -modelScale, modelScale)
      const rotX = new THREE.Matrix4().makeRotationX(Math.PI / 2)
      const rotY = new THREE.Matrix4().makeRotationY(azimuth)

      camera.projectionMatrix = new THREE.Matrix4()
        .fromArray(matrix)
        .multiply(translate)
        .multiply(scale)
        .multiply(rotX)
        .multiply(rotY)

      renderer.resetState()
      renderer.render(scene, camera)
      _map?.triggerRepaint()
    },
  }
}

function useGLBLayer(mapRef, coord, rectDims, rotationRef, onDimsReady, glbUrl) {
  useEffect(() => {
    if (!coord || !rectDims || !glbUrl) return
    const map = mapRef.current?.getMap?.()
    if (!map) return

    const create = () => buildGLBLayer(coord, rectDims.width, rectDims.depth, rotationRef, onDimsReady, glbUrl)

    const addLayer = () => {
      if (map.getLayer(GLB_LAYER_ID)) map.removeLayer(GLB_LAYER_ID)
      map.addLayer(create())
    }

    if (map.isStyleLoaded()) addLayer()
    else map.once('load', addLayer)

    const onStyleLoad = () => {
      if (map.getLayer(GLB_LAYER_ID)) map.removeLayer(GLB_LAYER_ID)
      map.addLayer(create())
    }
    map.on('style.load', onStyleLoad)

    return () => {
      map.off('style.load', onStyleLoad)
      if (map.getLayer(GLB_LAYER_ID)) map.removeLayer(GLB_LAYER_ID)
    }
  }, [coord, rectDims, mapRef, glbUrl])
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
          {b.floors} floors · {b.type ? b.type.charAt(0).toUpperCase() + b.type.slice(1) : 'Building'}
        </div>
        <div style={{
          display: 'inline-block', fontSize: '10px', fontWeight: 600,
          padding: '1px 6px', borderRadius: '3px',
          background: selected?.id === b.id ? 'var(--cyan)' : 'var(--surface-2)',
          color: selected?.id === b.id ? '#000' : 'var(--text-2)',
          border: '1px solid var(--border)',
        }}>
          {b.status ? b.status.charAt(0).toUpperCase() + b.status.slice(1) : 'Under Review'}
        </div>
      </div>
    </Popup>
  ))
}

// ── Main Map component ─────────────────────────────────────────────────────────
export function Map({ onCoordSelect, coord, buildingForm, existingBuildings, onSelectExisting, readOnly = false, mode = 'builder', mapPreview = null, trellisGlbUrl = null, onBack = null }) {
  const mapRef = useRef(null)
  const [selectedExisting, setSelectedExisting] = useState(null)
  const isDark = mode === 'builder'

  // 2D/3D toggle state
  const [is3D, setIs3D] = useState(true)

  // Draw state
  const [isDrawMode, setIsDrawMode] = useState(false)
  const [rectangle, setRectangle] = useState(null)
  const [rectArea, setRectArea] = useState(null)
  const [rectDims, setRectDims] = useState(null)
  const [rectCoord, setRectCoord] = useState(null)
  const [rotation, setRotation] = useState(0)
  const rotationRef = useRef(0)
  const [buildingFootprint, setBuildingFootprint] = useState(null)
  const [isBlocked, setIsBlocked] = useState(false)
  const existingBuildingsRef = useRef(existingBuildings)
  useEffect(() => { existingBuildingsRef.current = existingBuildings }, [existingBuildings])

  // Enable trackpad two-finger rotation on mount
  useEffect(() => {
    const map = mapRef.current?.getMap?.()
    if (map) {
      map.touchZoomRotate.enableRotation()
    }
  }, [])

  // GLB building at drawn area
  useGLBLayer(mapRef, rectCoord, rectDims, rotationRef, setBuildingFootprint, trellisGlbUrl)

  // AI image billboard at same coord (driven by parent's coord prop)
  useBillboardLayer(mapRef, coord, mapPreview?.image || null, buildingForm?.floors)

  // Draw interaction — active only while isDrawMode is true
  useEffect(() => {
    if (!isDrawMode || readOnly) return
    const map = mapRef.current?.getMap?.()
    if (!map) return

    map.dragPan.disable()
    let startPoint = null
    let isDown = false

    const onMouseDown = (e) => {
      if (e.originalEvent.button !== 0) return
      isDown = true
      startPoint = { lng: e.lngLat.lng, lat: e.lngLat.lat }
    }

    const onMouseMove = (e) => {
      if (!isDown || !startPoint) return
      const end = { lng: e.lngLat.lng, lat: e.lngLat.lat }
      const geo = makeRectGeo(startPoint, end)
      setRectangle(geo)
      setRectArea(turf.area(geo))
      setIsBlocked(hasConflict(geo, existingBuildingsRef.current))
    }

    const onMouseUp = (e) => {
      if (!isDown || !startPoint) return
      isDown = false
      const end = { lng: e.lngLat.lng, lat: e.lngLat.lat }
      const start = startPoint
      startPoint = null

      const geo = makeRectGeo(start, end)
      const blocked = hasConflict(geo, existingBuildingsRef.current)

      setRectangle(geo)
      setRectArea(turf.area(geo))
      setIsBlocked(blocked)
      setIsDrawMode(false)

      if (blocked) return  // don't place building — prompt user to redraw

      const dims = rectDimensions(start, end)
      const center = rectCenter(start, end)

      setRectDims(dims)
      setRectCoord(center)
      setRotation(0)
      rotationRef.current = 0
      setBuildingFootprint(null)
      onCoordSelect?.(center)

      mapRef.current?.flyTo({
        center: [center.lng, center.lat],
        zoom: Math.max(mapRef.current.getZoom(), 17),
        pitch: 60,
        duration: 900,
        essential: true,
      })
    }

    map.on('mousedown', onMouseDown)
    map.on('mousemove', onMouseMove)
    map.on('mouseup', onMouseUp)

    return () => {
      map.off('mousedown', onMouseDown)
      map.off('mousemove', onMouseMove)
      map.off('mouseup', onMouseUp)
      map.dragPan.enable()
    }
  }, [isDrawMode, readOnly, onCoordSelect])

  // Sync map style on mode switch
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

  // While drawing show the raw rectangle; once GLB loads switch to actual scaled footprint
  const displayGeo = (!isDrawMode && rectCoord && buildingFootprint)
    ? footprintGeo(rectCoord, buildingFootprint.width, buildingFootprint.depth, rotation)
    : (rectangle ?? EMPTY_GEO)

  const displayArea = buildingFootprint
    ? buildingFootprint.width * buildingFootprint.depth
    : (rectArea ?? 0)

  const accent       = isDark ? '#00d4ff' : '#0077cc'
  const accentBg     = isDark ? 'rgba(0,212,255,0.12)' : 'rgba(0,119,204,0.10)'
  const accentBorder = isDark ? 'rgba(0,212,255,0.35)' : 'rgba(0,119,204,0.35)'
  const hintBg       = isDark ? 'rgba(10,10,15,0.85)'  : 'rgba(245,246,250,0.90)'
  const hintColor    = 'var(--text-2)'

  const zoneColor  = isBlocked ? '#ff4444' : accent
  // eslint-disable-next-line no-unused-vars
  const zoneBg     = isBlocked ? 'rgba(255,68,68,0.12)' : accentBg
  // eslint-disable-next-line no-unused-vars
  const zoneBorder = isBlocked ? 'rgba(255,68,68,0.5)'  : accentBorder

  const pillBase = {
    borderRadius: 20, padding: '8px 20px', fontSize: 12,
    backdropFilter: 'blur(10px)', whiteSpace: 'nowrap',
    position: 'absolute', bottom: 24, left: '50%', transform: 'translateX(-50%)',
  }

  return (
    <div style={{ flex: 1, position: 'relative' }}>
      <ReactMapGL
        ref={mapRef}
        mapboxAccessToken={MAPBOX_TOKEN}
        initialViewState={TORONTO}
        style={{ width: '100%', height: '100%' }}
        mapStyle={MAP_STYLES[mode]}
        cursor={isDrawMode ? 'crosshair' : 'grab'}
        touchZoomRotate={true}
      >
        <NavigationControl position="top-right" visualizePitch />
        <style>{`
  .mapboxgl-ctrl-group button { opacity: 1 !important; }
  .mapboxgl-ctrl-group { background: rgba(15,15,24,0.9) !important; border: 1px solid rgba(255,255,255,0.12) !important; }
  .mapboxgl-ctrl-group button:hover { background: rgba(255,255,255,0.08) !important; }
  .mapboxgl-ctrl-icon { filter: invert(1) !important; }
  [data-mode="citizen"] .mapboxgl-ctrl-group { background: rgba(245,246,250,0.9) !important; border: 1px solid rgba(0,0,0,0.12) !important; }
  [data-mode="citizen"] .mapboxgl-ctrl-icon { filter: none !important; }
`}</style>
        <Layer {...(isDark ? BUILDINGS_DARK : BUILDINGS_LIGHT)} />

        {/* Buildable area / building footprint outline */}
        <Source id="draw-rect" type="geojson" data={displayGeo}>
          <Layer
            id="draw-rect-fill"
            type="fill"
            paint={{ 'fill-color': zoneColor, 'fill-opacity': 0.10 }}
          />
          <Layer
            id="draw-rect-outline"
            type="line"
            paint={{ 'line-color': zoneColor, 'line-width': 2, 'line-dasharray': isBlocked ? [2, 2] : [4, 2] }}
          />
        </Source>

        <ExistingMarkers
          buildings={existingBuildings}
          onSelect={handleSelectExisting}
          selected={selectedExisting}
        />
      </ReactMapGL>

      {/* Back button */}
      {onBack && (
        <button onClick={onBack} style={{
          position: 'absolute', top: 10, left: 10, zIndex: 5,
          background: isDark ? 'rgba(15,15,24,0.85)' : 'rgba(245,246,250,0.90)',
          border: `1px solid ${isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.12)'}`,
          borderRadius: 8, padding: '7px 14px',
          fontSize: 12, fontWeight: 600, color: 'var(--text)',
          cursor: 'pointer', backdropFilter: 'blur(8px)',
          display: 'flex', alignItems: 'center', gap: 6,
        }}>
          ← New Building
        </button>
      )}

      {/* 2D/3D toggle button */}
      <button
        onClick={() => {
          if (is3D) {
            mapRef.current?.easeTo({ pitch: 0, duration: 600 })
            setIs3D(false)
          } else {
            mapRef.current?.easeTo({ pitch: 55, bearing: -10, duration: 600 })
            setIs3D(true)
          }
        }}
        style={{
          position: 'absolute', bottom: 120, right: 10, zIndex: 5,
          background: 'rgba(15,15,24,0.85)',
          border: '1px solid rgba(255,255,255,0.15)',
          color: 'var(--text)',
          fontSize: 11, fontWeight: 600,
          padding: '5px 10px', borderRadius: 6,
          cursor: 'pointer', backdropFilter: 'blur(8px)',
        }}
      >
        {is3D ? '2D' : '3D'}
      </button>

      {/* Draw / Redraw / Cancel button */}
      {!readOnly && (
        <div style={{ position: 'absolute', top: 16, left: 16, zIndex: 1 }}>
          <button
            onClick={() => { setIsDrawMode(v => !v); setIsBlocked(false) }}
            style={{
              background: isDrawMode ? accent : isBlocked ? 'rgba(255,68,68,0.15)' : hintBg,
              color: isDrawMode ? '#000' : isBlocked ? '#ff6666' : accent,
              border: `1.5px solid ${isBlocked ? 'rgba(255,68,68,0.5)' : accentBorder}`,
              borderRadius: 8, padding: '8px 16px',
              fontSize: 12, fontWeight: 600, cursor: 'pointer',
              backdropFilter: 'blur(10px)', letterSpacing: '0.02em',
            }}
          >
            {isDrawMode ? '✕  Cancel' : rectCoord ? '⟳  Redraw Area' : '⬚  Draw Buildable Area'}
          </button>
        </div>
      )}

      {/* Blocked zone warning */}
      {isBlocked && !isDrawMode && !readOnly && (
        <div style={{
          position: 'absolute', bottom: 24, left: '50%', transform: 'translateX(-50%)',
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8,
        }}>
          <div style={{
            background: 'rgba(255,68,68,0.15)', border: '1px solid rgba(255,68,68,0.5)',
            borderRadius: 20, padding: '8px 20px',
            fontSize: 12, color: '#ff6666', fontWeight: 600,
            backdropFilter: 'blur(10px)', whiteSpace: 'nowrap',
          }}>
            Zone overlaps an existing building — redraw to continue
          </div>
        </div>
      )}

      {/* Area label + rotation control */}
      {rectCoord && !isBlocked && !isDrawMode && !readOnly && (
        <div style={{
          position: 'absolute', bottom: 24, left: '50%', transform: 'translateX(-50%)',
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8,
        }}>
          <div style={{
            background: accentBg, border: `1px solid ${accentBorder}`,
            borderRadius: 20, padding: '5px 16px',
            fontSize: 11, color: accent, fontWeight: 600,
            backdropFilter: 'blur(10px)', whiteSpace: 'nowrap',
          }}>
            {Math.round(displayArea).toLocaleString()} m²&nbsp;&nbsp;·&nbsp;&nbsp;
            {(buildingFootprint?.width ?? rectDims?.width ?? 0).toFixed(0)} m × {(buildingFootprint?.depth ?? rectDims?.depth ?? 0).toFixed(0)} m
          </div>

          <div style={{
            background: hintBg, border: '1px solid var(--border)',
            borderRadius: 12, padding: '10px 20px',
            backdropFilter: 'blur(10px)',
            display: 'flex', alignItems: 'center', gap: 12,
          }}>
            <span style={{ fontSize: 11, color: hintColor, minWidth: 80 }}>
              {rotation}°&nbsp;&nbsp;{compassLabel(rotation)}
            </span>
            <input
              type="range" min={0} max={359} value={rotation}
              style={{ width: 160, accentColor: accent, cursor: 'pointer' }}
              onChange={e => {
                const v = Number(e.target.value)
                setRotation(v)
                rotationRef.current = v
              }}
            />
          </div>

          {/* Show generate-image hint when building is placed but no image yet */}
          {!mapPreview?.loading && mapPreview?.image && (
            <div style={{
              background: accentBg, border: `1px solid ${accentBorder}`,
              borderRadius: 20, padding: '5px 16px',
              fontSize: 11, color: accent,
              backdropFilter: 'blur(10px)', whiteSpace: 'nowrap',
            }}>
              Building placed — describe it and click Analyze Impact
            </div>
          )}
        </div>
      )}

      {/* Loading indicator while image generates */}
      {!readOnly && rectCoord && mapPreview?.loading && (
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

      {/* Hints */}
      {!readOnly && !rectCoord && !isDrawMode && (
        <div style={{
          position: 'absolute', bottom: 24, left: '50%', transform: 'translateX(-50%)',
          background: isDark ? 'rgba(0,212,255,0.12)' : 'rgba(0,119,204,0.12)',
          border: `1px solid ${isDark ? 'rgba(0,212,255,0.4)' : 'rgba(0,119,204,0.4)'}`,
          borderRadius: '20px', padding: '9px 22px',
          fontSize: '12px', fontWeight: 600,
          color: isDark ? 'var(--cyan)' : '#0077cc',
          pointerEvents: 'none', backdropFilter: 'blur(10px)', whiteSpace: 'nowrap',
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <span style={{ fontSize: 14 }}>✦</span> Draw buildable area to place a building
        </div>
      )}
      {!readOnly && isDrawMode && (
        <div style={{ ...pillBase, background: accentBg, border: `1px solid ${accentBorder}`, color: accent, pointerEvents: 'none' }}>
          Click and drag to draw the buildable area
        </div>
      )}
      {readOnly && !selectedExisting && (
        <div style={{ ...pillBase, background: hintBg, border: '1px solid var(--border)', color: hintColor, pointerEvents: 'none' }}>
          Click any building marker to explore its impact
        </div>
      )}
    </div>
  )
}
