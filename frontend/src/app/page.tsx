'use client'

import { useEffect, useRef, useState } from 'react'
import {
  ApiError,
  askQuestion,
  friendlyNetworkError,
  getQuestion,
  type Dataset,
  type Question,
} from '@/lib/api'
import UploadBar from '@/components/UploadBar'
import QuestionBox from '@/components/QuestionBox'
import AnswerPanel from '@/components/AnswerPanel'
import LibrarySidebar from '@/components/LibrarySidebar'

export default function Home() {
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [question, setQuestion] = useState<Question | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Stop polling on unmount.
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  function stopPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  async function handleAsk(text: string) {
    if (!dataset) return
    stopPolling()
    setLoading(true)
    setError(null)
    setQuestion(null)
    try {
      const q = await askQuestion(dataset.id, text)
      setQuestion(q)
      if (q.status === 'pending') {
        // Poll for live step updates until terminal.
        pollRef.current = setInterval(async () => {
          try {
            const fresh = await getQuestion(q.id)
            setQuestion(fresh)
            if (fresh.status !== 'pending') {
              stopPolling()
              setLoading(false)
            }
          } catch {
            stopPolling()
            setLoading(false)
            setError(friendlyNetworkError())
          }
        }, 1200)
      } else {
        setLoading(false)
      }
    } catch (err) {
      setLoading(false)
      if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError(friendlyNetworkError())
      }
    }
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-gray-900">
              Personal Data Analyst
            </h1>
            <p className="text-xs text-gray-500">
              Ask questions about your CSV in plain language — your data never leaves this machine.
            </p>
          </div>
          <span className="hidden rounded-full bg-green-50 px-3 py-1 text-xs font-medium text-green-700 sm:inline">
            Local &amp; private
          </span>
        </div>
      </header>

      <main className="mx-auto grid max-w-6xl grid-cols-1 gap-6 px-4 py-6 lg:grid-cols-[16rem_1fr]">
        <LibrarySidebar />

        <div className="space-y-4">
          <UploadBar dataset={dataset} onUploaded={setDataset} />
          <QuestionBox enabled={!!dataset} loading={loading} onAsk={handleAsk} />
          <AnswerPanel
            question={question}
            loading={loading}
            error={error}
            hasDataset={!!dataset}
          />
        </div>
      </main>
    </div>
  )
}
