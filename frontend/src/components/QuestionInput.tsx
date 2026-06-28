'use client'

import { useEffect, useState } from 'react'

interface Props {
  disabled: boolean
  pending: string
  onAsk: (question: string) => void
}

export default function QuestionInput({ disabled, pending, onAsk }: Props) {
  const [value, setValue] = useState('')

  // Allow a clicked follow-up to populate the box.
  useEffect(() => {
    if (pending) setValue(pending)
  }, [pending])

  function submit(e: React.FormEvent) {
    e.preventDefault()
    const q = value.trim()
    if (!q || disabled) return
    onAsk(q)
    setValue('')
  }

  return (
    <form onSubmit={submit} className="flex items-end gap-2" data-testid="question-form">
      <textarea
        data-testid="question-input"
        className="min-h-[48px] flex-1 resize-none rounded-xl border border-slate-300 px-4 py-3 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:bg-slate-50"
        rows={1}
        placeholder="Ask a question about your data… e.g. What were total sales by region?"
        value={value}
        disabled={disabled}
        onChange={e => setValue(e.target.value)}
        onKeyDown={e => {
          if (e.key === 'Enter' && !e.shiftKey) submit(e)
        }}
      />
      <button
        type="submit"
        data-testid="ask-button"
        disabled={disabled || !value.trim()}
        className="rounded-xl bg-indigo-600 px-5 py-3 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50"
      >
        {disabled ? 'Running…' : 'Ask'}
      </button>
    </form>
  )
}
