'use client'

import { useState } from 'react'
import CsvUpload from './components/CsvUpload'
import AnalysisResult from './components/AnalysisResult'

interface Dataset {
  dataset_id: string
  filename: string
  row_count: number
  column_names: string[]
}

interface AnalysisResultData {
  answer_text: string | null
  chart_json: string | null
  status: string
  error: string | null
}

export default function Home() {
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [question, setQuestion] = useState('')
  const [result, setResult] = useState<AnalysisResultData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleAnalyze(e: React.FormEvent) {
    e.preventDefault()
    if (!dataset || !question.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await fetch('/analyses', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dataset_id: dataset.dataset_id, question }),
      })
      const body = await res.json()
      if (!res.ok) {
        setError(body.detail?.message ?? `Request failed (${res.status})`)
      } else {
        setResult(body.data)
      }
    } catch {
      setError('Network error — is the server running?')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-12">
      {/* Header */}
      <h1 className="mb-2 text-3xl font-bold tracking-tight text-gray-900">
        Data Analysis Agent
      </h1>
      <p className="mb-8 text-sm text-gray-500">
        Upload a CSV, ask a question, get an answer + chart. All data stays local.
      </p>

      {/* Step 1: Upload CSV */}
      <section className="mb-8">
        <h2 className="mb-3 text-lg font-semibold text-gray-800">1. Upload a CSV File</h2>
        {!dataset ? (
          <CsvUpload
            onUploadSuccess={(ds) => {
              setDataset(ds)
              setResult(null)
              setError(null)
              setQuestion('')
            }}
            disabled={loading}
          />
        ) : (
          <div className="rounded-lg bg-green-50 border border-green-200 p-4">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm font-semibold text-green-800">
                  {dataset.filename} — {dataset.row_count.toLocaleString()} rows
                </p>
                <div className="mt-2 flex flex-wrap gap-1">
                  {dataset.column_names.map((col) => (
                    <span
                      key={col}
                      className="rounded-full bg-green-100 px-2 py-0.5 text-xs text-green-700"
                    >
                      {col}
                    </span>
                  ))}
                </div>
              </div>
              <button
                onClick={() => { setDataset(null); setResult(null); setError(null); setQuestion('') }}
                className="ml-4 text-xs text-green-600 underline hover:text-green-800"
              >
                Upload a different file
              </button>
            </div>
          </div>
        )}
      </section>

      {/* Step 2: Ask a question (only shown after upload) */}
      {dataset && (
        <section className="mb-8">
          <h2 className="mb-3 text-lg font-semibold text-gray-800">2. Ask a Question</h2>
          <form onSubmit={handleAnalyze} className="space-y-3">
            <textarea
              className="w-full rounded-lg border border-gray-300 p-3 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              rows={3}
              placeholder="e.g. What is the average value by category?"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !question.trim()}
              className="flex items-center gap-2 rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading && (
                <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                  />
                </svg>
              )}
              {loading ? 'Analyzing…' : 'Analyze'}
            </button>
          </form>
        </section>
      )}

      {/* Loading state */}
      {loading && (
        <section className="mb-8">
          <h2 className="mb-3 text-lg font-semibold text-gray-800">3. Result</h2>
          <div className="flex flex-col items-center justify-center rounded-lg border border-gray-200 bg-gray-50 p-12">
            <svg className="h-8 w-8 animate-spin text-blue-600" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <p className="mt-4 text-sm text-gray-600">Analyzing your data…</p>
          </div>
        </section>
      )}

      {/* Result (only shown when not loading) */}
      {!loading && (result || error) && (
        <section className="mb-8">
          <h2 className="mb-3 text-lg font-semibold text-gray-800">3. Result</h2>
          <AnalysisResult
            answer={result?.answer_text ?? null}
            chartJson={result?.chart_json ?? null}
            error={error ?? (result?.error ?? null)}
            onReset={() => { setError(null); setResult(null); setQuestion('') }}
          />
        </section>
      )}

      {/* Phase 2 stub — clearly labelled, non-functional */}
      <div className="mt-8 rounded-lg border border-dashed border-gray-300 p-4 text-center opacity-60">
        <p className="text-sm font-medium text-gray-500">SQL Database Connectivity</p>
        <p className="mt-1 text-xs text-gray-400">
          Coming in Phase 2 — connect to SQLite, PostgreSQL, or MySQL. Not yet functional.
        </p>
        <button
          disabled
          className="mt-3 cursor-not-allowed rounded-md bg-gray-200 px-4 py-2 text-sm text-gray-400"
          title="Coming in Phase 2"
        >
          Connect Database (Phase 2)
        </button>
      </div>
    </main>
  )
}
