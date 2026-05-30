/**
 * useBuilding3D.js
 *
 * Tracks building spec history and produces structured payloads for the
 * 3D rendering pipeline. Every time the building spec changes this hook
 * emits a render payload via the `onRenderPayload` callback.
 *
 * ── Payload shape ───────────────────────────────────────────────────────────
 *
 * FIRST request  (isUpdate: false):
 * {
 *   isUpdate: false,
 *   buildingId: 42,
 *   requestIndex: 1,
 *   naturalLanguage: "A 24-floor residential high-rise tower...",
 *   spec: { type, floors, footprint_m2, material, units_per_floor, lat, lng, name },
 *   renderParams: {
 *     height_m: 84,
 *     floors: 24,
 *     footprint_m2: 2000,
 *     type: "residential (high-rise)",
 *     material: "glass",
 *     totalUnits: 288,
 *     gfa_m2: 48000,
 *     lat: 43.6532,
 *     lng: -79.3832,
 *   }
 * }
 *
 * SECOND+ request  (isUpdate: true):
 * {
 *   isUpdate: true,
 *   buildingId: 43,
 *   requestIndex: 2,
 *   naturalLanguage: "Modified 1 property: added 1 floor (now 25 floors, ~87m tall).",
 *   spec: { ... },           // full new spec
 *   previousSpec: { ... },   // previous spec for 3D engine to diff if needed
 *   diff: {
 *     fields: [{ field: 'floors', from: 24, to: 25, delta: 1, deltaText: '+1' }],
 *     naturalLanguage: "...",
 *   },
 *   renderParams: { height_m: 87, floors: 25, ... }
 * }
 *
 * ── How your 3D renderer should use this ────────────────────────────────────
 *
 *   if (payload.isUpdate) {
 *     // Animate the transition from previousSpec to spec
 *     // payload.diff.fields tells you exactly what changed
 *     // payload.diff.naturalLanguage is a human-readable summary
 *   } else {
 *     // Fresh build — construct the 3D model from scratch
 *   }
 *
 * ── Integration point ────────────────────────────────────────────────────────
 * Pass `onRenderPayload` to App.jsx and forward to your Three.js component.
 */

import { useRef, useCallback } from 'react'
import { describeBuilding, diffBuildings } from '../lib/buildingNL'

function toRenderParams(spec) {
  return {
    height_m:       Math.round((spec.floors || 1) * 3.5),
    floors:         spec.floors,
    footprint_m2:   spec.footprint_m2,
    type:           spec.type,
    material:       spec.material || 'glass',
    totalUnits:     spec.units_per_floor ? spec.floors * spec.units_per_floor : null,
    gfa_m2:         Math.round((spec.floors || 1) * (spec.footprint_m2 || 1)),
    lat:            spec.lat,
    lng:            spec.lng,
  }
}

export function useBuilding3D(onRenderPayload) {
  const previousSpecRef  = useRef(null)
  const requestIndexRef  = useRef(0)

  /**
   * Call this every time a building is submitted (created or updated).
   * `buildingId`  — the ID returned from POST /building
   * `spec`        — the full form data (type, floors, footprint_m2, material, etc.)
   */
  const emit = useCallback((buildingId, spec) => {
    requestIndexRef.current += 1
    const requestIndex  = requestIndexRef.current
    const previousSpec  = previousSpecRef.current
    const isUpdate      = previousSpec !== null
    const renderParams  = toRenderParams(spec)

    let payload

    if (!isUpdate) {
      payload = {
        isUpdate: false,
        buildingId,
        requestIndex,
        naturalLanguage: describeBuilding(spec),
        spec,
        renderParams,
      }
    } else {
      const diff = diffBuildings(previousSpec, spec)
      payload = {
        isUpdate: true,
        buildingId,
        requestIndex,
        naturalLanguage: diff.naturalLanguage,
        spec,
        previousSpec,
        diff,
        renderParams,
      }
    }

    previousSpecRef.current = spec

    // Log for debugging during development
    console.group(`[3D Render Payload] Request #${requestIndex} — ${isUpdate ? 'UPDATE' : 'CREATE'}`)
    console.log('isUpdate:', payload.isUpdate)
    console.log('naturalLanguage:', payload.naturalLanguage)
    console.log('renderParams:', payload.renderParams)
    if (isUpdate) console.log('diff:', payload.diff)
    console.log('Full payload:', payload)
    console.groupEnd()

    onRenderPayload?.(payload)
    return payload
  }, [onRenderPayload])

  const reset = useCallback(() => {
    previousSpecRef.current = null
    requestIndexRef.current = 0
  }, [])

  return { emit, reset }
}
