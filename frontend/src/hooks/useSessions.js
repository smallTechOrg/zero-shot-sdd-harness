import { useState, useEffect, useCallback } from 'react'
import { apiFetch } from '../api/client.js'

export function useSessions() {
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchSessions = useCallback(async () => {
    try {
      setLoading(true)
      const resp = await apiFetch('/sessions')
      setSessions(resp.data || [])
      setError(null)
    } catch (err) {
      setError(err.message || 'Failed to load sessions')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchSessions()
  }, [fetchSessions])

  const createSession = useCallback(async (title = 'New Session') => {
    const resp = await apiFetch('/sessions', {
      method: 'POST',
      body: JSON.stringify({ title }),
    })
    await fetchSessions()
    return resp.data
  }, [fetchSessions])

  return { sessions, loading, error, createSession, refresh: fetchSessions }
}
