'use client'

import { useRef, useState } from 'react'
import { ApiError, friendlyNetworkError, uploadDataset, type Dataset } from '@/lib/api'
import StubCard from './StubCard'

interface UploadBarProps {
  dataset: Dataset | null
  onUploaded: (dataset: Dataset) => void
}

export default function UploadBar({ dataset, onUploaded }: UploadBarProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleFile(file: File | undefined) {
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      const ds = await uploadDataset(file)
      onUploaded(ds)
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError(friendlyNetworkError())
      }
    } finally {
      setUploading(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-3">
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          onChange={e => handleFile(e.target.files?.[0])}
          data-testid="file-input"
        />
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={uploading}
          className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:opacity-50"
        >
          {uploading ? 'Uploading…' : dataset ? 'Replace CSV' : 'Upload CSV'}
        </button>

        {dataset ? (
          <div className="flex flex-1 flex-wrap items-center gap-x-3 gap-y-1 text-sm">
            <span className="font-semibold text-gray-900" data-testid="active-filename">
              {dataset.filename}
            </span>
            <span className="text-gray-400">·</span>
            <span className="text-gray-600">
              {dataset.row_count.toLocaleString()} rows
            </span>
            <span className="text-gray-400">·</span>
            <span className="text-gray-600">{dataset.column_count} cols</span>
          </div>
        ) : (
          <span className="text-sm text-gray-500">
            No file loaded yet — upload a CSV to start asking questions.
          </span>
        )}

        <div className="ml-auto w-44">
          <StubCard title="Add another file" phase="Phase 4" compact />
        </div>
      </div>

      {error && (
        <p
          role="alert"
          className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
        >
          {error}
        </p>
      )}

      {dataset && dataset.schema.length > 0 && (
        <details className="mt-3 text-sm">
          <summary className="cursor-pointer text-xs font-medium text-gray-500 hover:text-gray-700">
            Schema ({dataset.schema.length} columns)
          </summary>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {dataset.schema.map(col => (
              <span
                key={col.name}
                className="inline-flex items-center gap-1 rounded-md border border-gray-200 bg-gray-50 px-2 py-0.5 text-xs"
              >
                <span className="font-medium text-gray-700">{col.name}</span>
                <span className="text-gray-400">{col.type}</span>
              </span>
            ))}
          </div>
        </details>
      )}
    </section>
  )
}
