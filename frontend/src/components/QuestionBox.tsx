'use client'

import { useState } from 'react'

interface QuestionBoxProps {
  enabled: boolean
  loading: boolean
  onAsk: (text: string) => void
}

export default function QuestionBox({ enabled, loading, onAsk }: QuestionBoxProps) {
  const [text, setText] = useState('')

  function submit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = text.trim()
    if (!trimmed || !enabled || loading) return
    onAsk(trimmed)
  }

  return (
    <form
      onSubmit={submit}
      className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm"
    >
      <label htmlFor="question" className="mb-2 block text-sm font-medium text-gray-700">
        Ask a question about your data
      </label>
      <textarea
        id="question"
        rows={3}
        value={text}
        disabled={!enabled || loading}
        onChange={e => setText(e.target.value)}
        onKeyDown={e => {
          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) submit(e)
        }}
        placeholder={
          enabled
            ? 'e.g. What is the total revenue by region, highest first?'
            : 'Upload a CSV first to enable questions.'
        }
        className="w-full resize-y rounded-lg border border-gray-300 p-3 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-400"
      />
      <div className="mt-3 flex items-center justify-between">
        <span className="text-xs text-gray-400">⌘/Ctrl + Enter to ask</span>
        <button
          type="submit"
          disabled={!enabled || loading || !text.trim()}
          className="rounded-lg bg-gray-900 px-5 py-2 text-sm font-medium text-white shadow-sm hover:bg-gray-800 disabled:opacity-40"
        >
          {loading ? 'Analysing…' : 'Ask'}
        </button>
      </div>
    </form>
  )
}
