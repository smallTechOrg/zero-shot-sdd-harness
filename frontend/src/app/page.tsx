'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import {
  ApiError,
  askQuestion,
  createSession,
  getMessages,
  listDatasets,
  listSessions,
  uploadDataset,
  type ApiMessage,
  type Dataset,
  type SessionSummary,
} from './lib/api'
import MessageBubble from './components/MessageBubble'
import StubButton from './components/StubBadge'

export default function Home() {
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [selectedDataset, setSelectedDataset] = useState<string | null>(null)
  const [messages, setMessages] = useState<ApiMessage[]>([])

  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [booting, setBooting] = useState(true)

  const fileRef = useRef<HTMLInputElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  // Initial load: datasets + sessions, ensure a session exists, load history.
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const [ds, ss] = await Promise.all([listDatasets(), listSessions()])
        if (cancelled) return
        setDatasets(ds)
        if (ds.length) setSelectedDataset(ds[0].id)

        let sess = ss
        let active: SessionSummary
        if (sess.length === 0) {
          active = await createSession()
          sess = [active]
        } else {
          active = sess[0]
        }
        if (cancelled) return
        setSessions(sess)
        setSessionId(active.id)
        const msgs = await getMessages(active.id)
        if (!cancelled) setMessages(msgs)
      } catch (e) {
        if (!cancelled)
          setLoadError(
            e instanceof Error
              ? `Could not reach the backend (${e.message}). Is it running on port 8001?`
              : 'Could not reach the backend.',
          )
      } finally {
        if (!cancelled) setBooting(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight })
  }, [messages, sending])

  const switchSession = useCallback(async (id: string) => {
    setSessionId(id)
    setMessages([])
    try {
      const msgs = await getMessages(id)
      setMessages(msgs)
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : 'Failed to load session.')
    }
  }, [])

  async function handleNewSession() {
    try {
      const s = await createSession()
      setSessions(prev => [s, ...prev])
      setSessionId(s.id)
      setMessages([])
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : 'Failed to create session.')
    }
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setUploadError(null)
    try {
      const ds = await uploadDataset(file)
      setDatasets(prev => [
        { id: ds.id, name: ds.name, row_count: ds.row_count },
        ...prev.filter(d => d.id !== ds.id),
      ])
      setSelectedDataset(ds.id)
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Upload failed.')
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  async function handleSend(e: React.FormEvent) {
    e.preventDefault()
    const question = input.trim()
    if (!question || !sessionId || !selectedDataset || sending) return

    const optimistic: ApiMessage = {
      id: `local-${Date.now()}`,
      role: 'user',
      content: question,
    }
    setMessages(prev => [...prev, optimistic])
    setInput('')
    setSending(true)
    try {
      const r = await askQuestion(sessionId, selectedDataset, question)
      setMessages(prev => [
        ...prev,
        {
          id: r.message_id,
          role: 'assistant',
          content: r.answer,
          sql: r.sql,
          result: r.result,
          dataset_id: selectedDataset,
        },
      ])
    } catch (err) {
      const detail =
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'Unknown error'
      setMessages(prev => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: 'assistant',
          content: `I couldn't answer that — the query failed.\n\n${detail}`,
          sql: null,
          result: null,
        },
      ])
    } finally {
      setSending(false)
    }
  }

  const hasDataset = datasets.length > 0
  const composerDisabled = !hasDataset || !sessionId || sending

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="flex w-72 flex-col gap-4 overflow-y-auto border-r border-gray-200 bg-white p-4">
        <div>
          <h1 className="text-lg font-bold tracking-tight">Data Analyst</h1>
          <p className="text-xs text-gray-500">Upload a CSV. Ask questions.</p>
        </div>

        {/* Datasets */}
        <section>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
            Datasets
          </h2>
          <input
            ref={fileRef}
            type="file"
            accept=".csv,text/csv"
            onChange={handleUpload}
            className="hidden"
          />
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            className="mb-2 w-full rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {uploading ? 'Uploading…' : 'Upload CSV'}
          </button>
          {uploadError && (
            <p className="mb-2 rounded-md bg-red-50 px-2 py-1 text-xs text-red-600">
              {uploadError}
            </p>
          )}
          <ul className="space-y-1">
            {datasets.length === 0 && !booting && (
              <li className="text-xs text-gray-400">No datasets yet.</li>
            )}
            {datasets.map(d => (
              <li key={d.id}>
                <button
                  type="button"
                  onClick={() => setSelectedDataset(d.id)}
                  className={`flex w-full items-center justify-between rounded-lg border px-3 py-2 text-left text-sm ${
                    selectedDataset === d.id
                      ? 'border-blue-300 bg-blue-50'
                      : 'border-gray-200 hover:bg-gray-50'
                  }`}
                >
                  <span className="truncate font-medium text-gray-800">
                    {d.name}
                  </span>
                  <span className="ml-2 shrink-0 text-xs text-gray-500">
                    {d.row_count.toLocaleString()} rows
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <div className="mt-2">
            <StubButton label="Add another dataset" />
          </div>
        </section>

        {/* Sessions */}
        <section>
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              Sessions
            </h2>
            <button
              type="button"
              onClick={handleNewSession}
              className="text-xs font-medium text-blue-600 hover:underline"
            >
              + New
            </button>
          </div>
          <ul className="space-y-1">
            {sessions.map(s => (
              <li key={s.id}>
                <button
                  type="button"
                  onClick={() => switchSession(s.id)}
                  className={`w-full truncate rounded-lg px-3 py-1.5 text-left text-sm ${
                    sessionId === s.id
                      ? 'bg-gray-100 font-medium text-gray-900'
                      : 'text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  {s.title || 'Untitled session'}
                </button>
              </li>
            ))}
          </ul>
        </section>

        <div className="mt-auto">
          <StubButton label="Audit log" />
        </div>
      </aside>

      {/* Chat panel */}
      <main className="flex flex-1 flex-col bg-gray-50">
        {loadError && (
          <div className="border-b border-red-200 bg-red-50 px-6 py-2 text-sm text-red-700">
            {loadError}
          </div>
        )}

        <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-6">
          <div className="mx-auto flex max-w-3xl flex-col gap-4">
            {booting ? (
              <p className="mt-20 text-center text-sm text-gray-400">Loading…</p>
            ) : messages.length === 0 ? (
              <div className="mt-20 text-center">
                <p className="text-sm text-gray-500">
                  {hasDataset
                    ? 'Ask a question about your dataset to get started.'
                    : 'Upload a CSV to start.'}
                </p>
              </div>
            ) : (
              messages.map(m => <MessageBubble key={m.id} message={m} />)
            )}

            {sending && (
              <div className="flex justify-start">
                <div className="flex items-center gap-2 rounded-2xl rounded-bl-sm border border-gray-200 bg-white px-4 py-3 text-sm text-gray-500">
                  <span className="h-2 w-2 animate-bounce rounded-full bg-gray-400 [animation-delay:-0.3s]" />
                  <span className="h-2 w-2 animate-bounce rounded-full bg-gray-400 [animation-delay:-0.15s]" />
                  <span className="h-2 w-2 animate-bounce rounded-full bg-gray-400" />
                  <span className="ml-1">Querying…</span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Composer */}
        <form
          onSubmit={handleSend}
          className="border-t border-gray-200 bg-white px-6 py-4"
        >
          <div className="mx-auto flex max-w-3xl items-end gap-2">
            <textarea
              rows={1}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSend(e)
                }
              }}
              disabled={composerDisabled}
              placeholder={
                hasDataset
                  ? 'Ask a question about your data…'
                  : 'Upload a CSV to start.'
              }
              className="max-h-40 flex-1 resize-none rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50"
            />
            <button
              type="submit"
              disabled={composerDisabled || !input.trim()}
              className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              Send
            </button>
          </div>
        </form>
      </main>
    </div>
  )
}
