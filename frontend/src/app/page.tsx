'use client'

import { useState } from 'react'
import {
  ApiError,
  NetworkError,
  askQuestion,
  uploadDataset,
  type AskResult,
  type Dataset,
} from '../lib/api'
import { AnswerPanel } from '../components/AnswerPanel'
import { AskBox } from '../components/AskBox'
import { ProfileCard } from '../components/ProfileCard'
import { Sidebar } from '../components/Sidebar'
import { Uploader } from '../components/Uploader'

export default function Home() {
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [uploadLoading, setUploadLoading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)

  const [result, setResult] = useState<AskResult | null>(null)
  const [askLoading, setAskLoading] = useState(false)
  const [askError, setAskError] = useState<string | null>(null)

  async function handleUpload(file: File) {
    setUploadLoading(true)
    setUploadError(null)
    setResult(null)
    setAskError(null)
    try {
      const ds = await uploadDataset(file)
      setDataset(ds)
    } catch (e) {
      if (e instanceof NetworkError) {
        setUploadError('Network error — is the server running?')
      } else if (e instanceof ApiError) {
        // Backend gives a clear message; default to the spec's friendly copy.
        setUploadError(e.message || "Couldn’t read that CSV — check it’s a valid file")
      } else {
        setUploadError("Couldn’t read that CSV — check it’s a valid file")
      }
    } finally {
      setUploadLoading(false)
    }
  }

  async function handleAsk(question: string) {
    if (!dataset) return
    setAskLoading(true)
    setAskError(null)
    setResult(null)
    try {
      const res = await askQuestion(dataset.id, question)
      setResult(res) // status may be "completed" or "failed"; AnswerPanel handles both
    } catch (e) {
      if (e instanceof NetworkError) {
        setAskError('Network error — is the server running?')
      } else if (e instanceof ApiError) {
        setAskError(e.message || `Request failed (${e.status})`)
      } else {
        setAskError('Something went wrong running that question.')
      }
    } finally {
      setAskLoading(false)
    }
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <header className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight text-gray-900">Local Data Analyst</h1>
        <p className="mt-1 text-sm text-gray-500">
          Upload a CSV, ask a question, get an auditable answer — all on your machine.
        </p>
      </header>

      <div className="flex flex-col gap-6 lg:flex-row">
        <Sidebar dataset={dataset} />

        <div className="min-w-0 flex-1 space-y-6">
          <Uploader
            onUpload={handleUpload}
            loading={uploadLoading}
            error={uploadError}
            hasDataset={!!dataset}
          />

          {dataset && <ProfileCard dataset={dataset} />}

          {dataset && <AskBox onAsk={handleAsk} loading={askLoading} />}

          {/* Transport-level ask error (network / 404 / 422) — distinct from an
              agent "failed" result, which renders inside AnswerPanel. */}
          {askError && (
            <div
              data-testid="ask-error"
              role="alert"
              className="rounded-xl border border-red-300 bg-red-50 p-4 text-sm font-medium text-red-700"
            >
              {askError}
            </div>
          )}

          {result && <AnswerPanel result={result} />}

          {!dataset && !uploadLoading && (
            <div
              data-testid="empty-state"
              className="rounded-xl border border-dashed border-gray-200 bg-white/60 p-10 text-center"
            >
              <p className="text-sm text-gray-400">
                Upload a CSV above to see its profile and start asking questions.
              </p>
            </div>
          )}
        </div>
      </div>
    </main>
  )
}
