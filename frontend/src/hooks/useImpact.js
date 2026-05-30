import { useState, useEffect, useRef } from 'react'
import { getImpact } from '../api'

// NeMoTron can take 15-45s. These messages cycle while waiting.
const LOADING_STAGES = [
  'Querying spatial layers...',
  'Analyzing 500m radius...',
  'Running traffic model...',
  'Running economic model...',
  'Running energy model...',
  'Consulting NeMoTron on DGX Spark...',
  'NeMoTron is reasoning...',
  'Blending XGBoost + NeMoTron scores...',
  'Finalizing impact report...',
]

export function useImpact(buildingId) {
  const [impact,  setImpact]  = useState(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState(null)
  const [stage,   setStage]   = useState(0)
  const timerRef = useRef(null)
  const stageRef = useRef(0)

  useEffect(() => {
    if (!buildingId) return

    setImpact(null)
    setError(null)
    setLoading(true)
    setStage(0)
    stageRef.current = 0

    // Cycle through loading stages every 3s
    timerRef.current = setInterval(() => {
      stageRef.current = (stageRef.current + 1) % LOADING_STAGES.length
      setStage(stageRef.current)
    }, 3000)

    getImpact(buildingId)
      .then(data => {
        setImpact(data)
        setError(null)
      })
      .catch(err => {
        setError(err.message)
      })
      .finally(() => {
        clearInterval(timerRef.current)
        setLoading(false)
      })

    return () => clearInterval(timerRef.current)
  }, [buildingId])

  return {
    impact,
    loading,
    error,
    loadingMessage: LOADING_STAGES[stage],
  }
}
