'use client'

import { useRef, useState } from 'react'
import { ApiError, uploadDataset, type Dataset } from '@/lib/api'

interface UploadPanelProps {
  dataset: Dataset | null
  onUploaded: (dataset: Dataset) => void
  disabled?: boolean
}

export default function UploadPanel({ dataset, onUploaded, disabled }: UploadPanelProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)

  async function handleFile(file: File | undefined) {
    if (!file) return
    setError(null)
    setUploading(true)
    try {
      const result = await uploadDataset(file)
      onUploaded(result)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Upload failed. Please try again.')
    } finally {
      setUploading(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  const busy = uploading || disabled

  return (
    <section aria-label="Upload a CSV" className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-900">1 · Upload a CSV</h2>
        {dataset && (
          <span className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700">
            Loaded
          </span>
        )}
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault()
          if (!busy) setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(false)
          if (busy) return
          handleFile(e.dataTransfer.files?.[0])
        }}
        className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-4 py-8 text-center transition-colors ${
          dragOver ? 'border-blue-400 bg-blue-50' : 'border-gray-300 bg-gray-50'
        } ${busy ? 'opacity-60' : ''}`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          className="sr-only"
          id="csv-file-input"
          disabled={busy}
          onChange={(e) => handleFile(e.target.files?.[0])}
        />
        {uploading ? (
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <Spinner />
            <span>Uploading &amp; profiling…</span>
          </div>
        ) : (
          <>
            <p className="mb-1 text-sm text-gray-600">Drag a CSV here, or</p>
            <label
              htmlFor="csv-file-input"
              className={`cursor-pointer rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 ${
                busy ? 'pointer-events-none opacity-50' : ''
              }`}
            >
              Upload CSV
            </label>
            <p className="mt-2 text-xs text-gray-400">CSV only · stays on your machine</p>
          </>
        )}
      </div>

      {error && (
        <div
          role="alert"
          className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
        >
          {error}
        </div>
      )}

      {dataset && (
        <div className="mt-4 space-y-3">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-sm">
            <span className="font-medium text-gray-900">{dataset.filename}</span>
            <span className="text-gray-500">
              {dataset.row_count.toLocaleString()} rows · {dataset.schema.length} columns
            </span>
          </div>
          <div>
            <p className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-400">Columns</p>
            <ul className="flex flex-wrap gap-1.5">
              {dataset.schema.map((col) => (
                <li
                  key={col.name}
                  className="rounded-md border border-gray-200 bg-gray-50 px-2 py-1 text-xs text-gray-700"
                  title={col.dtype}
                >
                  {col.name}
                  <span className="ml-1 text-gray-400">{col.dtype}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </section>
  )
}

function Spinner() {
  return (
    <svg className="h-4 w-4 animate-spin text-blue-600" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  )
}
