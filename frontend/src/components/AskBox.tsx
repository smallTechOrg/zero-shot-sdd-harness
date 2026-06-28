'use client'

import { useEffect, useState } from 'react'
import { StubBadge } from './StubPanel'

interface AskBoxProps {
  onAsk: (question: string) => void
  loading: boolean
}

const PHASES = ['Planning the analysis…', 'Running SQL on your data…', 'Writing the answer…']

const SUGGESTION_PLACEHOLDERS = [
  'Which region had the highest total sales?',
  'How did sales trend over time?',
  'What are the top 5 products?',
]

export function AskBox({ onAsk, loading }: AskBoxProps) {
  const [question, setQuestion] = useState('')
  const [phaseIdx, setPhaseIdx] = useState(0)

  // Cycle the working indicator so the ~30s wait feels alive.
  useEffect(() => {
    if (!loading) {
      setPhaseIdx(0)
      return
    }
    const t = setInterval(() => {
      setPhaseIdx((i) => (i + 1 < PHASES.length ? i + 1 : i))
    }, 4000)
    return () => clearInterval(t)
  }, [loading])

  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!question.trim() || loading) return
    onAsk(question.trim())
  }

  return (
    <section data-testid="ask-box" className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-gray-900">Ask a question</h2>

      <form onSubmit={submit} className="mt-3 flex flex-col gap-3 sm:flex-row">
        <input
          type="text"
          data-testid="question-input"
          className="flex-1 rounded-lg border border-gray-300 px-3 py-2.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50"
          placeholder="e.g. Which region had the highest total sales?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={loading}
        />
        <button
          type="submit"
          data-testid="ask-button"
          disabled={loading || !question.trim()}
          className="rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? 'Working…' : 'Ask'}
        </button>
      </form>

      {loading && (
        <div data-testid="ask-loading" className="mt-3 flex items-center gap-2 text-sm text-blue-700">
          <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
          </svg>
          <span aria-live="polite">{PHASES[phaseIdx]}</span>
        </div>
      )}

      {/* STUB: suggested questions (Phase 6) */}
      <div data-stub="true" aria-disabled="true" className="pointer-events-none mt-4 select-none">
        <div className="mb-2 flex items-center gap-2">
          <span className="text-xs font-medium text-gray-400">Suggested questions</span>
          <StubBadge phase="Phase 6" />
        </div>
        <div className="flex flex-wrap gap-2">
          {SUGGESTION_PLACEHOLDERS.map((s) => (
            <span
              key={s}
              className="rounded-full border border-dashed border-gray-300 bg-gray-50 px-3 py-1 text-xs text-gray-400"
            >
              {s}
            </span>
          ))}
        </div>
      </div>

      {/* STUB: follow-up (Phase 3) */}
      <div
        data-stub="true"
        aria-disabled="true"
        className="pointer-events-none mt-3 flex select-none items-center gap-2"
      >
        <input
          type="text"
          disabled
          placeholder="Ask a follow-up…"
          className="flex-1 cursor-not-allowed rounded-lg border border-dashed border-gray-300 bg-gray-50 px-3 py-2 text-sm text-gray-400 placeholder:text-gray-400"
        />
        <StubBadge phase="Phase 3" />
      </div>
    </section>
  )
}
