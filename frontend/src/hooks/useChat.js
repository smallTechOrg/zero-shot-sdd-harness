import { useState, useEffect, useCallback } from 'react'
import { apiFetch } from '../api/client.js'

export function useChat(sessionId) {
  const [session, setSession] = useState(null)
  const [messages, setMessages] = useState([])
  const [datasets, setDatasets] = useState([])
  const [loading, setLoading] = useState(true)
  const [queryLoading, setQueryLoading] = useState(false)
  const [error, setError] = useState(null)
  const [tokenUsage, setTokenUsage] = useState(null)

  const fetchSession = useCallback(async () => {
    if (!sessionId) return
    try {
      setLoading(true)
      const [sessionResp, datasetsResp] = await Promise.all([
        apiFetch(`/sessions/${sessionId}`),
        apiFetch(`/sessions/${sessionId}/datasets`),
      ])
      setSession(sessionResp.data)
      setDatasets(datasetsResp.data || [])
      setError(null)
    } catch (err) {
      setError(err.message || 'Failed to load session')
    } finally {
      setLoading(false)
    }
  }, [sessionId])

  useEffect(() => {
    fetchSession()
  }, [fetchSession])

  const sendQuery = useCallback(async (question) => {
    if (!sessionId) return
    const userMsg = { role: 'user', content: question, id: Date.now() + '-user' }
    setMessages(prev => [...prev, userMsg])
    setQueryLoading(true)
    try {
      const resp = await apiFetch(`/sessions/${sessionId}/query`, {
        method: 'POST',
        body: JSON.stringify({ question }),
      })
      const d = resp.data
      setTokenUsage(d.token_usage)
      const asstMsg = {
        id: d.message_id,
        role: 'assistant',
        content: d.answer,
        sql: d.sql,
        results: d.results,
        token_usage: d.token_usage,
      }
      setMessages(prev => [...prev, asstMsg])
    } catch (err) {
      setMessages(prev => [
        ...prev,
        { id: Date.now() + '-err', role: 'assistant', content: `Error: ${err.message}` },
      ])
    } finally {
      setQueryLoading(false)
    }
  }, [sessionId])

  const uploadFile = useCallback(async (file) => {
    if (!sessionId) return
    const formData = new FormData()
    formData.append('file', file)
    const resp = await fetch(`/api/sessions/${sessionId}/upload`, {
      method: 'POST',
      body: formData,
    })
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}))
      throw { status: resp.status, message: body?.detail?.message || `Upload failed: ${resp.status}` }
    }
    const data = await resp.json()
    await fetchSession()
    return data.data
  }, [sessionId, fetchSession])

  return { session, messages, datasets, loading, queryLoading, error, tokenUsage, sendQuery, uploadFile, refresh: fetchSession }
}
