'use client'

import { useEffect, useState, useCallback } from 'react'

type Column = { name: string; type: string }
type Dataset = {
  dataset_id: string
  table_name: string
  row_count: number
  columns: Column[]
}
type QueryResult = { columns: string[]; rows: (string | number | null)[][] }
type Turn = {
  turn_id: string
  question: string
  answer_text: string | null
  sql_text: string | null
  result: QueryResult | null
  status: string
  error?: string | null
  created_at?: string
}

const SESSION_KEY = 'sda_session_id'

function ResultTable({ result }: { result: QueryResult }) {
  if (!result || !result.columns?.length) return null
  return (
    <div className="mt-3 overflow-x-auto rounded-lg border border-gray-200">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50">
          <tr>
            {result.columns.map((c, i) => (
              <th
                key={i}
                className="px-3 py-2 text-left font-semibold text-gray-700 whitespace-nowrap"
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 bg-white">
          {result.rows.map((row, ri) => (
            <tr key={ri} className="hover:bg-gray-50">
              {row.map((cell, ci) => (
                <td key={ci} className="px-3 py-1.5 text-gray-800 whitespace-nowrap">
                  {cell === null ? <span className="text-gray-300">—</span> : String(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function SqlBlock({ sql }: { sql: string }) {
  return (
    <details className="mt-3">
      <summary className="cursor-pointer text-xs font-medium text-gray-500 hover:text-gray-700">
        Query run (read-only)
      </summary>
      <pre className="mt-2 overflow-x-auto rounded-md bg-gray-900 p-3 text-xs leading-relaxed text-gray-100">
        <code>{sql}</code>
      </pre>
    </details>
  )
}

function TurnCard({ turn }: { turn: Turn }) {
  const failed = turn.status === 'failed'
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <p className="text-sm font-semibold text-gray-900">{turn.question}</p>
      {failed ? (
        <div className="mt-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {turn.error || turn.answer_text || 'That query failed.'}
        </div>
      ) : (
        <>
          {turn.answer_text && (
            <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-gray-800">
              {turn.answer_text}
            </p>
          )}
          {turn.sql_text && <SqlBlock sql={turn.sql_text} />}
          {turn.result && <ResultTable result={turn.result} />}
        </>
      )}
    </div>
  )
}

function StubCard({
  title,
  description,
  phase,
}: {
  title: string
  description: string
  phase: string
}) {
  return (
    <div className="relative rounded-lg border border-dashed border-gray-300 bg-gray-50 p-4 opacity-80">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-600">{title}</h3>
        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-700">
          Coming soon · {phase}
        </span>
      </div>
      <p className="mt-1.5 text-xs text-gray-400">{description}</p>
      <button
        disabled
        className="mt-3 cursor-not-allowed rounded-md border border-gray-200 bg-white px-3 py-1.5 text-xs text-gray-300"
      >
        Not functional yet
      </button>
    </div>
  )
}

export default function Home() {
  // Upload state
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)

  // Session / dataset state
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [history, setHistory] = useState<Turn[]>([])

  // Ask state
  const [question, setQuestion] = useState('')
  const [asking, setAsking] = useState(false)
  const [askError, setAskError] = useState<string | null>(null)
  const [currentTurn, setCurrentTurn] = useState<Turn | null>(null)

  // Restore session from localStorage on load
  const loadSession = useCallback(async (id: string) => {
    try {
      const res = await fetch(`/sessions/${id}`)
      const body = await res.json()
      if (!res.ok) {
        // Stale/unknown session — clear it silently
        localStorage.removeItem(SESSION_KEY)
        setSessionId(null)
        return
      }
      const d = body.data
      setSessionId(d.session_id)
      if (d.dataset) setDataset(d.dataset)
      setHistory(d.turns ?? [])
    } catch {
      // Network issue — keep id but don't crash
    }
  }, [])

  useEffect(() => {
    const stored = typeof window !== 'undefined' ? localStorage.getItem(SESSION_KEY) : null
    if (stored) {
      setSessionId(stored)
      loadSession(stored)
    }
  }, [loadSession])

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault()
    if (!file) return
    setUploading(true)
    setUploadError(null)
    try {
      const form = new FormData()
      form.append('file', file)
      if (sessionId) form.append('session_id', sessionId)
      const res = await fetch('/datasets', { method: 'POST', body: form })
      const body = await res.json()
      if (!res.ok) {
        setUploadError(
          body.detail?.message ??
            body.error ??
            "Couldn't read that file — check it's a valid CSV."
        )
        return
      }
      const d = body.data
      setSessionId(d.session_id)
      localStorage.setItem(SESSION_KEY, d.session_id)
      setDataset({
        dataset_id: d.dataset_id,
        table_name: d.table_name,
        row_count: d.row_count,
        columns: d.columns,
      })
      // Refresh history for the (possibly new) session
      setHistory([])
      setCurrentTurn(null)
    } catch {
      setUploadError('Network error — is the server running?')
    } finally {
      setUploading(false)
    }
  }

  async function handleAsk(e: React.FormEvent) {
    e.preventDefault()
    if (!question.trim() || !sessionId) return
    setAsking(true)
    setAskError(null)
    setCurrentTurn(null)
    const asked = question
    try {
      const res = await fetch(`/sessions/${sessionId}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: asked }),
      })
      const body = await res.json()
      if (!res.ok) {
        setAskError(body.detail?.message ?? body.error ?? `Request failed (${res.status})`)
        return
      }
      const d = body.data as Turn
      const turn: Turn = { ...d, question: asked }
      setCurrentTurn(turn)
      if (d.status !== 'failed') {
        setHistory(prev => [...prev, turn])
        setQuestion('')
      }
    } catch {
      setAskError('Network error — is the server running?')
    } finally {
      setAsking(false)
    }
  }

  const priorTurns = history.filter(t => t.turn_id !== currentTurn?.turn_id)

  return (
    <main className="mx-auto max-w-5xl px-4 py-10">
      <header className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight text-gray-900">Senior Data Analyst</h1>
        <p className="mt-1 text-sm text-gray-500">
          Upload a CSV, ask questions in plain English, get an analyst-grade answer with the
          supporting rows. Read-only — your data never gets mutated.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Main column */}
        <div className="space-y-6 lg:col-span-2">
          {/* Upload panel */}
          <section className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
            <h2 className="text-sm font-semibold text-gray-900">1 · Upload a dataset</h2>
            <form onSubmit={handleUpload} className="mt-3 flex flex-wrap items-center gap-3">
              <input
                type="file"
                accept=".csv,.xlsx"
                onChange={e => setFile(e.target.files?.[0] ?? null)}
                disabled={uploading}
                className="block text-sm text-gray-600 file:mr-3 file:rounded-md file:border-0 file:bg-blue-600 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-blue-700"
              />
              <button
                type="submit"
                disabled={uploading || !file}
                className="inline-flex items-center gap-2 rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50"
              >
                {uploading && (
                  <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                )}
                {uploading ? 'Uploading…' : 'Upload'}
              </button>
            </form>

            {uploadError && (
              <div className="mt-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                {uploadError}
              </div>
            )}

            {dataset ? (
              <div className="mt-4 rounded-lg border border-green-200 bg-green-50 p-3">
                <p className="text-sm font-medium text-green-800">
                  Table {dataset.table_name} created — {dataset.row_count.toLocaleString()} rows
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {dataset.columns.map(c => (
                    <span
                      key={c.name}
                      className="inline-flex items-center gap-1 rounded-full bg-white px-2 py-0.5 text-xs text-gray-700 ring-1 ring-inset ring-gray-200"
                    >
                      <span className="font-medium">{c.name}</span>
                      <span className="text-gray-400">{c.type}</span>
                    </span>
                  ))}
                </div>
              </div>
            ) : (
              !uploadError && (
                <p className="mt-4 text-sm text-gray-400">Upload a CSV to begin.</p>
              )
            )}
          </section>

          {/* Ask panel */}
          <section className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
            <h2 className="text-sm font-semibold text-gray-900">2 · Ask a question</h2>
            <form onSubmit={handleAsk} className="mt-3 space-y-3">
              <textarea
                rows={3}
                value={question}
                onChange={e => setQuestion(e.target.value)}
                disabled={!dataset || asking}
                placeholder={
                  dataset
                    ? 'e.g. What is the total revenue by region?'
                    : 'Upload a dataset first…'
                }
                className="w-full rounded-lg border border-gray-300 p-3 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-400"
              />
              <button
                type="submit"
                disabled={!dataset || asking || !question.trim()}
                className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {asking && (
                  <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                )}
                {asking ? 'Analyzing…' : 'Ask'}
              </button>
            </form>

            {askError && (
              <div className="mt-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                {askError}
              </div>
            )}

            {asking && (
              <p className="mt-4 text-sm text-gray-400">Running the analyst…</p>
            )}

            {currentTurn && (
              <div className="mt-4">
                <TurnCard turn={currentTurn} />
              </div>
            )}

            {!asking && !currentTurn && !askError && dataset && (
              <p className="mt-4 text-sm text-gray-400">Your answer and result rows appear here.</p>
            )}
          </section>

          {/* History */}
          {priorTurns.length > 0 && (
            <section>
              <h2 className="mb-3 text-sm font-semibold text-gray-900">Session history</h2>
              <div className="space-y-3">
                {[...priorTurns].reverse().map(t => (
                  <TurnCard key={t.turn_id} turn={t} />
                ))}
              </div>
            </section>
          )}
        </div>

        {/* Sidebar — labelled non-functional stubs */}
        <aside className="space-y-4">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-400">
            On the roadmap
          </p>
          <StubCard
            title="Charts"
            description="Visualize query results as bar / line charts."
            phase="Phase 2"
          />
          <StubCard
            title="Multiple datasets"
            description="Upload several files and join across them."
            phase="Phase 3"
          />
          <StubCard
            title="Dashboards"
            description="Save multi-question dashboards you can reopen."
            phase="Phase 4"
          />
          <StubCard
            title="Audit log"
            description="Browse every read-only query that has run."
            phase="Phase 4"
          />
        </aside>
      </div>
    </main>
  )
}
