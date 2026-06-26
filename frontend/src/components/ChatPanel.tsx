'use client'

import { useEffect, useRef, useState } from 'react'
import { AnswerCard } from './AnswerCard'
import type { AnalysisResult } from './AnswerCard'
import type { UploadSession } from './UploadPanel'

interface Message {
  question: string
  result: AnalysisResult | null
  loading: boolean
  error: string | null
}

interface ChatPanelProps {
  session: UploadSession | null
}

const MAX_CHARS = 2000

export function ChatPanel({ session }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [question, setQuestion] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const charsLeft = MAX_CHARS - question.length
  const nearLimit = charsLeft <= 200

  async function handleAsk(e: React.FormEvent) {
    e.preventDefault()
    if (!session || !question.trim() || submitting) return

    const q = question.trim()
    setQuestion('')
    setSubmitting(true)

    const idx = messages.length
    setMessages((prev) => [...prev, { question: q, result: null, loading: true, error: null }])

    try {
      const res = await fetch(`/sessions/${session.session_id}/questions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q }),
      })
      const data = await res.json()

      if (!res.ok) {
        const msg =
          data.detail?.message ??
          data.error?.message ??
          `Request failed (${res.status})`
        setMessages((prev) => {
          const updated = [...prev]
          updated[idx] = { question: q, result: null, loading: false, error: msg }
          return updated
        })
        return
      }

      if (!data.ok) {
        const msg = data.error?.message ?? 'Unknown error.'
        setMessages((prev) => {
          const updated = [...prev]
          updated[idx] = { question: q, result: null, loading: false, error: msg }
          return updated
        })
        return
      }

      const result: AnalysisResult = data.data
      setMessages((prev) => {
        const updated = [...prev]
        updated[idx] = { question: q, result, loading: false, error: null }
        return updated
      })
    } catch {
      setMessages((prev) => {
        const updated = [...prev]
        updated[idx] = {
          question: q,
          result: null,
          loading: false,
          error: 'Network error — is the server running?',
        }
        return updated
      })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      <h2 className="text-base font-semibold text-gray-800 mb-4">Ask a Question</h2>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto space-y-4 mb-4 min-h-0">
        {messages.length === 0 && !session && (
          <div className="flex items-center justify-center h-32 text-sm text-gray-400 text-center">
            Upload a CSV file to get started.
          </div>
        )}
        {messages.length === 0 && session && (
          <div className="flex items-center justify-center h-32 text-sm text-gray-400 text-center">
            Ask a question about your data to get started.
          </div>
        )}
        {messages.map((msg, i) => (
          <AnswerCard
            key={i}
            question={msg.question}
            result={msg.result}
            loading={msg.loading}
            error={msg.error}
          />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input form */}
      <form onSubmit={handleAsk} className="flex flex-col gap-2">
        <div className="relative">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value.slice(0, MAX_CHARS))}
            disabled={!session || submitting}
            placeholder={
              session
                ? 'Ask a question about your data…'
                : 'Upload a CSV file first…'
            }
            maxLength={MAX_CHARS}
            className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:bg-gray-50 disabled:text-gray-400 pr-16"
          />
          {nearLimit && (
            <span
              className={`absolute right-3 top-1/2 -translate-y-1/2 text-xs ${
                charsLeft <= 50 ? 'text-red-500' : 'text-amber-500'
              }`}
            >
              {charsLeft}
            </span>
          )}
        </div>
        <button
          type="submit"
          disabled={!session || !question.trim() || submitting}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {submitting ? 'Thinking…' : 'Ask'}
        </button>
      </form>
    </div>
  )
}
