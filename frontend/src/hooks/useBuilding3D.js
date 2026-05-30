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
 *   agentPrompt: "You are an architectural visualization agent. Generate a
 *                 hyper-realistic architectural render of a building on a
 *                 completely white background... The building is: A 24-floor
 *                 residential high-rise tower with a concrete and glass curtain
 *                 wall facade, 2,000m² footprint, approximately 84 metres tall.",
 *   spec: { type, floors, footprint_m2, material, units_per_floor, lat, lng, name },
 *   renderParams: {
 *     height_m: 84, floors: 24, footprint_m2: 2000,
 *     type: "residential (high-rise)", material: "glass",
 *     totalUnits: 288, gfa_m2: 48000, lat: 43.6532, lng: -79.3832,
 *   }
 * }
 *
 * SECOND+ request  (isUpdate: true):
 * {
 *   isUpdate: true,
 *   buildingId: 43,
 *   requestIndex: 2,
 *   naturalLanguage: "Modified 1 property: added 1 floor (now 25 floors, ~87m tall).",
 *   agentPrompt: "You are an architectural visualization agent... Keep the previous
 *                 styling exactly as described: A 24-floor residential high-rise
 *                 tower with a concrete and glass curtain wall facade...
 *                 Apply the following modifications to the design: Increase the
 *                 building height by 1 floor — now 25 floors total, approximately
 *                 87 metres tall. Updated full specification: A 25-floor...",
 *   spec: { ... },           // full new spec
 *   previousSpec: { ... },   // full previous spec
 *   diff: {
 *     fields: [{ field: 'floors', from: 24, to: 25, delta: 1, deltaText: '+1' }],
 *     naturalLanguage: "Modified 1 property: added 1 floor...",
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
import { describeBuilding, diffBuildings, buildAgentPrompt } from '../lib/buildingNL'

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
  const previousSpecRef        = useRef(null)
  const previousAgentPromptRef = useRef(null)   // carries prompt context into update requests
  const requestIndexRef        = useRef(0)

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
      const partialPayload = {
        isUpdate: false,
        buildingId,
        requestIndex,
        naturalLanguage: describeBuilding(spec),
        spec,
        renderParams,
      }
      // Build agent prompt — no previous context on first request
      const agentPrompt = buildAgentPrompt(partialPayload, null)
      payload = { ...partialPayload, agentPrompt }
    } else {
      const diff = diffBuildings(previousSpec, spec)
      const partialPayload = {
        isUpdate: true,
        buildingId,
        requestIndex,
        naturalLanguage: diff.naturalLanguage,
        spec,
        previousSpec,
        diff,
        renderParams,
      }
      // Build agent prompt — passes previous prompt so update inherits styling context
      const agentPrompt = buildAgentPrompt(partialPayload, previousAgentPromptRef.current)
      payload = { ...partialPayload, agentPrompt }
    }

    // Store for next request's context
    previousSpecRef.current        = spec
    previousAgentPromptRef.current = payload.agentPrompt

    // Log for debugging during development
    console.group(`[3D Render Payload] Request #${requestIndex} — ${isUpdate ? 'UPDATE' : 'CREATE'}`)
    console.log('isUpdate:', payload.isUpdate)
    console.log('naturalLanguage:', payload.naturalLanguage)
    console.log('agentPrompt:', payload.agentPrompt)
    console.log('renderParams:', payload.renderParams)
    if (isUpdate) console.log('diff:', payload.diff)
    console.groupEnd()

    onRenderPayload?.(payload)
    return payload
  }, [onRenderPayload])

  const reset = useCallback(() => {
    previousSpecRef.current        = null
    previousAgentPromptRef.current = null
    requestIndexRef.current        = 0
  }, [])

  return { emit, reset }
}
