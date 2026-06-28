'use client'

import { useState } from 'react'

interface QuestionBoxProps {
  enabled: boolean
  streaming: boolean
  onAsk: (question: string) => void
}

export default function QuestionBox({ enabled, streaming, onAsk }: QuestionBoxProps) {
  const [question, setQuestion] = useState('')

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = question.trim()
    if (!trimmed || !enabled || streaming) return
    onAsk(trimmed)
  }

  return (
    <section aria-label="Ask a question" className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="mb-3">
        <h2 className="text-sm font-semibold text-gray-900">2 · Ask a question</h2>
        {!enabled && (
          <p className="mt-1 text-xs text-gray-400">Upload a CSV first to enable questions.</p>
        )}
      </div>
      <form onSubmit={handleSubmit} className="flex flex-col gap-3 sm:flex-row">
        <label htmlFor="question-input" className="sr-only">
          Your question
        </label>
        <input
          id="question-input"
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={!enabled || streaming}
          placeholder="e.g. How many orders are there for each order_status?"
          className="flex-1 rounded-lg border border-gray-300 px-3 py-2.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-400"
        />
        <button
          type="submit"
          disabled={!enabled || streaming || !question.trim()}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {streaming ? (
            <>
              <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Working…
            </>
          ) : (
            'Ask'
          )}
        </button>
      </form>
    </section>
  )
}
