'use client'

import { useState } from 'react'

export default function ChatInput({
  onAsk,
  disabled,
  running,
}: {
  onAsk: (question: string) => void
  disabled: boolean
  running: boolean
}) {
  const [question, setQuestion] = useState('')

  function submit(e: React.FormEvent) {
    e.preventDefault()
    const q = question.trim()
    if (!q || disabled || running) return
    onAsk(q)
    setQuestion('')
  }

  return (
    <form onSubmit={submit} className="flex items-end gap-2" data-testid="chat-form">
      <textarea
        rows={1}
        value={question}
        onChange={e => setQuestion(e.target.value)}
        onKeyDown={e => {
          if (e.key === 'Enter' && !e.shiftKey) submit(e)
        }}
        disabled={disabled || running}
        data-testid="question-input"
        placeholder={
          disabled ? 'Upload a dataset to start asking questions…' : 'Ask a question about your data…'
        }
        className="min-h-[48px] flex-1 resize-none rounded-xl border border-gray-300 px-4 py-3 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-400"
      />
      <button
        type="submit"
        disabled={disabled || running || !question.trim()}
        data-testid="ask-button"
        className="h-[48px] rounded-xl bg-blue-600 px-5 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {running ? 'Analyzing…' : 'Ask'}
      </button>
    </form>
  )
}
