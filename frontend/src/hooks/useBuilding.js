import { useState, useCallback } from 'react'
import { createBuilding } from '../api'

export function useBuilding() {
  const [building, setBuilding]   = useState(null)   // full building object from API
  const [loading,  setLoading]    = useState(false)
  const [error,    setError]      = useState(null)

  const submit = useCallback(async (formData) => {
    setLoading(true)
    setError(null)
    try {
      const result = await createBuilding(formData)
      setBuilding(result)
      return result
    } catch (err) {
      setError(err.message)
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  const reset = useCallback(() => {
    setBuilding(null)
    setError(null)
  }, [])

  return { building, loading, error, submit, reset }
}
